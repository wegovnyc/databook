"""Single resolver for "is this org row live?".

`wegov_orgs.retired_at` marks a record that was merged into another one
(`merged_into`) by `api/adopt_nyc_orgs.py`. Retirement is deliberately
ADDITIVE -- a duplicate is never DELETEd, so the merge stays reversible and the
history survives. The cost of that choice is that **every serving query has to
exclude retired rows**, or a merged duplicate keeps showing up in the
directory, the org chart, and search.

⚠ Why this is a shared helper and not `AND retired_at IS NULL` inlined:

  * A database that has not run `adopt_nyc_orgs.py` has no such column, and
    `wegov_orgs` has no DDL in this repo to add it to (it is `source_type =
    'internal'` and created outside the pipeline). Referencing a missing column
    would 500 every org endpoint.
  * In `routers/search.py` it would be worse than a 500: `_rows()` swallows
    exceptions and returns `[]`, so the orgs group would silently go EMPTY --
    exactly the #146 failure, where a DuckDB reserved word made a search group
    return nothing with no error surfaced.

So the column's existence is probed once per process and cached. Callers get
back either the clause or an empty string. Following the `dbcreds.py`
precedent: one resolver, not a copy per call site.
"""

import logging

logger = logging.getLogger(__name__)


# ── org type vocabulary ──────────────────────────────────────────────────────
#
# `wegov_orgs.type` is now a MIXED vocabulary, on purpose:
#   * the 306 orgs in NYC's official registry carry **OTI's** `organization_type`
#     verbatim (adopted 2026-07-30 — OTI maintains it, we do not);
#   * the ~930 others (unions, political clubs, BIDs, publications…) keep ours,
#     because OTI has no opinion about them.
#
# ⚠ So any query that filters on `type` must accept BOTH vocabularies. Four
# places did not, and each would have failed silently rather than loudly:
#   main.py /get/orgs/directory + /get/orgs/chart  -> ~117 agencies vanish
#   enrich_agency.py (x2, `type = 'City Agency'`)  -> Greenbook head + address
#       enrichment silently stops covering them
# Centralised here so the next filter cannot drift from these.

# OTI's nine `organization_type` values (t3jq-9nkf, verified 2026-07-30).
OTI_TYPES = (
    "Advisory or Regulatory Organization",
    "Division",
    "Elected Office",
    "Mayoral Agency",
    "Mayoral Office",
    "Nonprofit Organization",
    "Pension Fund",
    "Public Benefit or Development Organization",
    "State Government Agency",
)

# The subset of OTI's types that are government bodies. `Nonprofit Organization`
# is deliberately excluded: 49 Cultural Institutions Group nonprofits (MoMA,
# Prospect Park Alliance) hold records so their references resolve, but they do
# not belong in a directory of government.
OTI_GOV_TYPES = tuple(t for t in OTI_TYPES if t != "Nonprofit Organization")

# Our own legacy types that mean "a government body", for the ~930 rows OTI
# does not cover.
OURS_GOV_TYPES = (
    "City Agency", "City Fund", "Community Board",
    "Economic Development Organization", "Elected Office", "State Agency",
)

# What `/get/orgs/directory` serves.
DIRECTORY_TYPES = tuple(dict.fromkeys(OURS_GOV_TYPES + OTI_GOV_TYPES))

# What the "City Agencies" page (`/organizations/agencies`) serves: city-level
# government bodies. Excludes Community Board and Elected Office (they have
# their own surfaces), State Agency / State Government Agency (not city), and
# Nonprofit Organization.
#
# ⚠ This exists because the page used to do the filtering ITSELF, in JavaScript:
#     column.search('^City Agency$', true, false)
# When the OTI adoption retyped 240 orgs onto OTI's vocabulary, `City Agency`
# went 167 -> 27 and the page silently showed 28 rows of leftovers. A Python
# grep for type filters could not see it — it was a regex inside a Blade
# template. Hence: the server owns the vocabulary, the page renders what it is
# given.
CITY_AGENCY_TYPES = (
    "City Agency", "City Fund", "Economic Development Organization",
    "Mayoral Agency", "Mayoral Office", "Division",
    "Advisory or Regulatory Organization", "Pension Fund",
    "Public Benefit or Development Organization",
)

# What `/get/orgs/chart` serves — the org-chart builder additionally wants the
# structural pseudo-types.
CHART_TYPES = tuple(dict.fromkeys(
    ("City Agency", "Elected Office", "Boards and Comissions", "Classification",
     "Community Board", "Official") + OTI_GOV_TYPES))

# Which orgs the Greenbook agency enrichment should consider (api/enrich_agency.py).
AGENCY_ENRICHMENT_TYPES = tuple(dict.fromkeys(("City Agency",) + OTI_GOV_TYPES))


def sql_type_list(types) -> str:
    """Render a type tuple as a SQL IN-list literal.

    These are module constants, never user input, and they are interpolated into
    SQL built by string concatenation elsewhere in main.py -- so quotes are
    doubled anyway rather than relying on the values being clean.
    """
    return ", ".join("'" + t.replace("'", "''") + "'" for t in types)


_HAS_RETIRED_COL = None

_PROBE = ("SELECT 1 AS ok FROM information_schema.columns "
          "WHERE table_name = 'wegov_orgs' AND column_name = 'retired_at'")


async def _probe(runner) -> bool:
    try:
        rows = await runner(_PROBE)
        if isinstance(rows, dict):        # main.select() shape
            rows = rows.get("rows") or []
        return bool(rows)
    except Exception as exc:              # noqa: BLE001
        logger.warning("[orgfilter] retired_at probe failed, assuming absent: %s", exc)
        return False


async def live_clause(runner, prefix: str = "AND", alias: str = "") -> str:
    """Return e.g. `AND retired_at IS NULL`, or '' if the column is absent.

    `runner` is an async callable taking a SQL string -- `main.select` or a
    thin wrapper over `PostgresModelAsync`. Passed in rather than imported so
    this module stays free of both, and so tests can hand in a stub.

    Pass `prefix='WHERE'` when the query has no WHERE clause yet, and `alias`
    when `wegov_orgs` is joined under one (`alias='o'` -> `o.retired_at`).

    ⚠ EVERY query that serves org rows to a user needs this. Retirement is
    additive -- the row stays in the table -- so an unfiltered query happily
    returns a merged-away duplicate. Measured 2026-07-30, after the two
    retirements shipped: `/api/v1/orgs/search?q=public+design` and the MCP
    `search_organizations` tool both returned the retired
    `Public Design Commission` alongside the real one.
    """
    global _HAS_RETIRED_COL
    if _HAS_RETIRED_COL is None:
        _HAS_RETIRED_COL = await _probe(runner)
        logger.info("[orgfilter] wegov_orgs.retired_at present: %s", _HAS_RETIRED_COL)
    if not _HAS_RETIRED_COL:
        return ""
    col = f"{alias}.retired_at" if alias else "retired_at"
    return f" {prefix} {col} IS NULL"


_HAS_CHART_COL = None

_CHART_PROBE = ("SELECT 1 AS ok FROM information_schema.columns "
                "WHERE table_name = 'wegov_orgs' AND column_name = 'in_org_chart'")


async def in_chart_clause(runner, prefix: str = "AND") -> str:
    """`AND in_org_chart IS NOT FALSE`, or '' where the column is absent.

    `in_org_chart` is tri-state on purpose: TRUE / FALSE / NULL, where NULL is
    "not stated" and is NOT the same as false. So the chart selects candidates
    by type as it always did, and this removes only the EXPLICIT exclusions --
    32 orgs that used to express "not on the chart" by being parented to a
    bucket named `Additional Mayoral Agencies (Not on Chart)`, plus whatever
    OTI marks `in_org_chart = false`.

    `IS NOT FALSE` rather than `IS TRUE` is the whole point: an org we have no
    opinion about stays on the chart, as it did before the flag existed.
    """
    global _HAS_CHART_COL
    if _HAS_CHART_COL is None:
        try:
            rows = await runner(_CHART_PROBE)
            if isinstance(rows, dict):
                rows = rows.get("rows") or []
            _HAS_CHART_COL = bool(rows)
        except Exception as exc:                      # noqa: BLE001
            logger.warning("[orgfilter] in_org_chart probe failed: %s", exc)
            _HAS_CHART_COL = False
        logger.info("[orgfilter] wegov_orgs.in_org_chart present: %s", _HAS_CHART_COL)
    return f" {prefix} in_org_chart IS NOT FALSE" if _HAS_CHART_COL else ""


# ── the parent link ──────────────────────────────────────────────────────────
#
# Phase 3 of docs/ORG-DIRECTORY-OF-RECORD-PLAN.md. `wegov_orgs.parent_org_id` is
# an INTEGER REFERENCES wegov_orgs(id), so a parent that resolves to nothing is
# structurally impossible.
#
# What it replaces: `child_of`, which held an Airtable `rec...` id as TEXT
# (sometimes JSON-wrapped, `["recABC"]`) and was joined to `airtable_id` by
# string equality after stripping brackets. That is why 63 orgs had a parent
# resolving to nothing, and why importing an org required minting a synthetic
# `recOTI...` id -- `child_of` had no other way to reference a new row.
#
# ⚠ Probed and cached, like the two above, because `wegov_orgs` has no DDL in
# this repo (`source_type = 'internal'`, created outside the pipeline) so a
# local or CI database may predate the column. Referencing it unconditionally
# would 500 every org profile, and in `routers/search.py` -- which swallows
# exceptions -- it would instead make a whole search group silently EMPTY.

_HAS_PARENT_FK = None

_PARENT_PROBE = ("SELECT 1 AS ok FROM information_schema.columns "
                 "WHERE table_name = 'wegov_orgs' AND column_name = 'parent_org_id'")

_LEGACY_PARENT_ON = (r"{parent}.airtable_id = "
                     r"regexp_replace({child}.child_of, '[\[\]\"]', '', 'g')")


async def has_parent_fk(runner) -> bool:
    """Is `wegov_orgs.parent_org_id` present? Probed once per process."""
    global _HAS_PARENT_FK
    if _HAS_PARENT_FK is None:
        _HAS_PARENT_FK = await _probe_sql(runner, _PARENT_PROBE)
        logger.info("[orgfilter] wegov_orgs.parent_org_id present: %s", _HAS_PARENT_FK)
    return _HAS_PARENT_FK


async def parent_join(runner, child: str = "org", parent: str = "p") -> str:
    """A LEFT JOIN resolving `<child>`'s parent row as `<parent>`.

    Callers select whatever they need off the alias (`p.name AS parent_name`).
    Which mechanism resolved it is not their business -- that is the point of
    putting it here rather than inlining either form at four call sites.
    """
    if await has_parent_fk(runner):
        return f" LEFT JOIN wegov_orgs {parent} ON {parent}.id = {child}.parent_org_id"
    return (f" LEFT JOIN wegov_orgs {parent} ON "
            + _LEGACY_PARENT_ON.format(child=child, parent=parent))


async def parent_id_projection(runner, child: str = "org",
                               parent: str = "pp") -> tuple:
    """`(select_fragment, join_fragment)` guaranteeing a `parent_org_id` key.

    Both are EMPTY once the FK exists, because `SELECT <child>.*` already
    carries the column. Before then the legacy string join supplies it under
    the same name.

    ⚠ The point is that the CONSUMER has exactly one code path. The org chart is
    built in Blade/PHP where `php -l` cannot validate a conditional and the only
    test is rendering the page, so the compatibility shim belongs here in
    Python -- not in the template layer.
    """
    if await has_parent_fk(runner):
        return "", ""
    return (f", {parent}.id AS parent_org_id",
            f" LEFT JOIN wegov_orgs {parent} ON "
            + _LEGACY_PARENT_ON.format(child=child, parent=parent))


async def _probe_sql(runner, sql: str) -> bool:
    try:
        rows = await runner(sql)
        if isinstance(rows, dict):
            rows = rows.get("rows") or []
        return bool(rows)
    except Exception as exc:                          # noqa: BLE001
        logger.warning("[orgfilter] column probe failed, assuming absent: %s", exc)
        return False


def reset_cache() -> None:
    """Test hook -- forget the probe results."""
    global _HAS_RETIRED_COL, _HAS_CHART_COL, _HAS_PARENT_FK
    _HAS_RETIRED_COL = None
    _HAS_CHART_COL = None
    _HAS_PARENT_FK = None
