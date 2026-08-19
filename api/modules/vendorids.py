"""Vendor name -> PASSPort supplier id, for profile links. ONE owner.

⚠⚠ WHY THIS EXISTS — A JOIN THAT DUPLICATED CONTRACTS. Every digital-reform
query resolved the supplier id with

    LEFT JOIN vendors v ON LOWER(c.vendor_name) = LOWER(v."Vendor Name")

and **48 vendor names hold more than one row in `vendors`** (measured
2026-08-12), so a matching contract came back TWICE. On the Renewal Queue it
inflated exactly one row — `CT1-017-20248805602`, Absorb Software's LMS, whose
name resolves to supplier ids 1871820 and 2073456 — which is why the queue
reported **243** expiring licences where the Licenses page reported **242**.
A one-row error, but the two pages disagreeing about the same set is the defect,
not the size of it.

⚠ The Licenses page never had it, because it never joined: it built this map in
Python and accepted a name ONLY where the name resolves to exactly one supplier
id. That rule is the whole point and it is the same one the DOS crosswalk uses
(`confidence='ambiguous'` -> NULL, never a guess): linking an ambiguous name
sends a reader to an arbitrary one of two companies, which is worse than leaving
the name unlinked.

⚠ A map cannot duplicate a row. That is the structural reason to prefer it over
a `HAVING`-filtered join here — the failure mode is "no link", never "two rows".
"""
from modules.errfmt import exc_str

# ⚠ `HAVING count(DISTINCT ...) = 1` IS THE GUARD, not an optimisation. Dropping
# it (or replacing it with `min(...)` alone) makes the map start guessing between
# two companies. A test pins this clause.
#
# ⚠ PUBLIC, because not every caller has a PostgresModelAsync. The daily briefing
# runs all of its queries on one dedicated connection, so it fetches with SQL +
# from_rows() instead of unique_map(). Exposing the query beats letting a second
# caller write its own: two spellings of `lower(trim(...))` is how the folding
# drifts and the map silently resolves nothing.
SQL = """
    SELECT lower(trim("Vendor Name")) AS nm,
           min("PASSPort Supplier-ID") AS vendor_id
    FROM vendors
    WHERE coalesce(trim("Vendor Name"), '') <> ''
    GROUP BY lower(trim("Vendor Name"))
    HAVING count(DISTINCT "PASSPort Supplier-ID") = 1
"""


def key(vendor_name) -> str:
    """The map's key for a contracts.vendor_name. Folded identically on both
    sides — a different folding here would silently resolve nothing."""
    return (vendor_name or "").strip().lower()


def from_rows(rows) -> dict:
    """Build the map from rows already fetched with SQL, for a caller that owns its
    own connection. The keying lives here so it cannot differ between callers."""
    return {r["nm"]: r["vendor_id"] for r in (rows or [])}


async def unique_map(pg, logger=None) -> dict:
    """{lower(trim(name)): supplier_id} for names resolving to EXACTLY ONE id.

    `pg` is PostgresModelAsync, passed in so this module stays importable without
    the DB stack (the same reason digitalscope takes it as an argument).

    ⚠ Degrades to `{}` rather than raising: an unresolvable supplier id must cost
    a hyperlink, never a page.
    """
    try:
        return from_rows(await pg.select_safe(SQL))
    except Exception as exc:  # noqa: BLE001
        if logger:
            logger.warning("vendor id lookup failed: %s", exc_str(exc))
        return {}
