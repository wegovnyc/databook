"""One owner for the Digital Services Analysis scope.

⚠⚠ WHY THIS EXISTS. Until 2026-08-12 every digital-reform endpoint defined
"digital" as `vendor_name IN (<200 tagged names>)` — the `vendor_tags` keyword
heuristic — interpolated independently at SEVEN call sites in routers/oce.py.
Measured against the full-population classification, that gate was wrong in both
directions: 85.2% precision (444 of 2,993 admitted contracts are not tech —
Inter-Con SECURITY SYSTEMS ranked 5th on the public vendors table at "100%
digital share"), and it covered 200 of 6,964 vendors, hiding ~40% of the licence
inventory. See docs/DIGITAL-SERVICES-SECTION-PLAN.md.

The derived scope replaces the name heuristic with the classification itself:
a contract is digital because `digital_contract_enrichment.tech_relevant` says
so, and a vendor is digital because they hold such contracts.

⚠ FEATURE-GATED, DEFAULT OLD. `DIGITAL_SCOPE=tag` (default) preserves today's
published numbers exactly — same predicates, same amendment-ROW grain, same
award_amount sums. `DIGITAL_SCOPE=derived` switches to the licences-page
discipline: positive tech_relevant scope, ONE ROW PER CONTRACT, value =
current-else-award. The flip ships with the template rebuild, after the owner
has seen the deltas; the refactor alone must change nothing served.

⚠ THE GRAIN DIFFERENCE IS DELIBERATE AND LARGE. Tag mode counts amendment rows
(the dashboard's "3,343 contracts" tile counts ROWS, not contracts — a
pre-existing defect preserved by the gate); derived mode deduplicates on
contract_id with the same tiebreak as the licences page's _CONTRACTS CTE.
Do not "fix" tag mode: its only job is to serve the old numbers unchanged
until it is deleted.
"""
import os

from modules.errfmt import exc_str

MODE_ENV = "DIGITAL_SCOPE"
MODES = ("tag", "derived")
DEFAULT_MODE = "derived"

# ⚠⚠ THE RENEWAL QUEUE IS RE-SCOPED AHEAD OF THE OVERVIEW, so it does NOT read
# MODE_ENV. The three pages ship separately and the queue's turn came first; with
# the Licenses page already full-population, leaving the queue on the vendor-name
# tag is what made the two disagree about the same 242 contracts.
#
# ⚠ `DIGITAL_SCOPE=tag` therefore does not roll the queue back — that is
# deliberate. A page whose licence count is now checked against the Licenses page
# must not be able to fall back to the 85.2%-precision scope because an env var
# somewhere still says `tag`. QUEUE_MODE_ENV is the rollback lever, so the
# rollback is explicit and names the page it affects.
#
# ⚠ When MODE_ENV finally flips to `derived` this override becomes a no-op and
# should be deleted with the tag mode, not left as a second gate.
QUEUE_MODE_ENV = "DIGITAL_SCOPE_QUEUE"
QUEUE_DEFAULT_MODE = "derived"

# The licences-page dedup, verbatim semantics: one row per contract, keeping the
# row with the highest current value (then award) — amendment history collapses.
_DERIVED_TABLE = (
    "(SELECT DISTINCT ON (contract_id) * FROM contracts"
    " WHERE contract_id IS NOT NULL"
    " ORDER BY contract_id, coalesce(current_amount,0) DESC,"
    " coalesce(award_amount,0) DESC)"
)


def mode() -> str:
    """✅ FLIPPED TO `derived` 2026-08-13 (#247), with the Overview rebuild.

    ⚠ The gate defaulted to `tag` for exactly as long as a page still published the
    old numbers. The Overview was the last one, and it now states its own scope from
    the payload — so the default moves with the page that needed it, in code, where
    the decision is reviewable. `DIGITAL_SCOPE=tag` is the rollback lever and it
    still works; the tag path is kept until `vendor_tags` is retired for good.
    ⚠ The deltas this flip publishes: 3,343 -> 4,397 contracts, $6,467.9M ->
    $10,610.5M, 200 -> 967 vendors. Measured through the real code path, both modes.
    """
    m = (os.environ.get(MODE_ENV) or DEFAULT_MODE).strip().lower()
    return m if m in MODES else DEFAULT_MODE


def queue_mode() -> str:
    """The Renewal Queue's scope — `derived` unless explicitly overridden.

    ⚠ Falls back to QUEUE_DEFAULT_MODE, never to mode(): see QUEUE_MODE_ENV.
    An invalid value is ignored the same way mode() ignores one, because a typo in
    an env var must not silently change what a published page measures.
    """
    m = (os.environ.get(QUEUE_MODE_ENV) or QUEUE_DEFAULT_MODE).strip().lower()
    return m if m in MODES else QUEUE_DEFAULT_MODE


def quote_names(names) -> str:
    """The tag path's historical IN-list builder, centralised."""
    return ", ".join("'" + str(n).replace("'", "''") + "'" for n in names)


def table_sql(scope_mode: str) -> str:
    """What to put after FROM. Tag mode: the raw table, amendment-row grain,
    exactly as every query read before this module existed. Derived mode: one
    row per contract."""
    return "contracts" if scope_mode == "tag" else _DERIVED_TABLE


def where_sql(scope_mode: str, alias: str, vendor_list: str) -> str:
    """The scope predicate for a contracts alias.

    ⚠ Derived mode is a POSITIVE condition (the classifier confirmed it), never
    the tag path's exclude-the-confirmed-negatives shape — an unclassified
    contract is out until classified, which is what makes the derived numbers a
    measurement rather than a hope."""
    if scope_mode == "tag":
        return f"{alias}.vendor_name IN ({vendor_list})"
    return ("EXISTS (SELECT 1 FROM digital_contract_enrichment dce "
            f"WHERE dce.contract_id = {alias}.contract_id AND dce.tech_relevant)")


def value_sql(scope_mode: str, alias: str) -> str:
    """The money column. Tag mode: award_amount, matching every number the old
    page ever printed. Derived: current-else-award, the licences-page rule."""
    if scope_mode == "tag":
        return f"{alias}.award_amount"
    return f"coalesce({alias}.current_amount, {alias}.award_amount)"


def exclude_confirmed_nontech_sql(scope_mode: str, alias: str, enr_exists: bool) -> str:
    """Tag mode's compensating patch: drop contracts the AI explicitly confirmed
    non-tech. Redundant in derived mode (the scope is already positive)."""
    if scope_mode != "tag" or not enr_exists:
        return ""
    return (f" AND NOT EXISTS (SELECT 1 FROM digital_contract_enrichment dce "
            f"WHERE dce.contract_id = {alias}.contract_id AND dce.tech_relevant = false)")


def is_digital_expr_sql(scope_mode: str, alias: str, enr_exists: bool) -> str:
    """Row-level boolean used by FILTER(...) aggregates."""
    if scope_mode == "tag":
        if not enr_exists:
            return "TRUE"
        return (f"NOT EXISTS (SELECT 1 FROM digital_contract_enrichment dce "
                f"WHERE dce.contract_id = {alias}.contract_id AND dce.tech_relevant = false)")
    return (f"EXISTS (SELECT 1 FROM digital_contract_enrichment dce "
            f"WHERE dce.contract_id = {alias}.contract_id AND dce.tech_relevant)")


class Scope:
    """Everything an endpoint needs to scope itself, resolved once per request.

    ⚠ `empty` is tag-mode-only: with no tag rows the old endpoints returned
    zero-shells, and the gate preserves that. Derived mode is empty only if the
    enrichment table is missing — in which case serving zeros IS the honest
    answer, not a shell."""

    def __init__(self, scope_mode, vendor_meta, vendor_count, enr_exists, empty):
        self.mode = scope_mode
        self.vendor_meta = vendor_meta          # name -> {classification, description}
        self.vendor_count = vendor_count
        self.enr_exists = enr_exists
        self.empty = empty
        self._vendor_list = quote_names(vendor_meta.keys()) if vendor_meta else "''"

    def table(self) -> str:
        return table_sql(self.mode)

    def where(self, alias: str) -> str:
        return where_sql(self.mode, alias, self._vendor_list)

    def value(self, alias: str) -> str:
        return value_sql(self.mode, alias)

    def exclude_nontech(self, alias: str) -> str:
        return exclude_confirmed_nontech_sql(self.mode, alias, self.enr_exists)

    def is_digital(self, alias: str) -> str:
        return is_digital_expr_sql(self.mode, alias, self.enr_exists)

    def meta_for(self, vendor_name: str) -> dict:
        return self.vendor_meta.get(vendor_name, {})


async def load(pg, logger=None, mode_override=None) -> Scope:
    """Resolve the scope for one request. `pg` is PostgresModelAsync (passed in
    so this module stays importable without the DB stack — the same reason the
    licences tests load modules by path).

    `mode_override` lets ONE section of a payload run in a different scope from
    the rest — which is exactly the Renewal Queue's situation while the Overview
    is still unbuilt. An unrecognised override falls back to the gate rather than
    guessing.
    """
    scope_mode = mode_override if mode_override in MODES else mode()

    enr_exists = False
    try:
        chk = await pg.select_safe(
            "SELECT to_regclass('public.digital_contract_enrichment') AS t")
        enr_exists = bool(chk and chk[0].get("t"))
    except Exception as exc:  # noqa: BLE001
        if logger:
            logger.warning("digitalscope enrichment probe failed: %s", exc_str(exc))

    if scope_mode == "tag":
        rows = await pg.select_safe(
            "SELECT vendor_name, classification, description FROM vendor_tags "
            "WHERE tag = 'digital_services'") or []
        meta = {r["vendor_name"]: {"classification": r.get("classification"),
                                   "description": r.get("description")}
                for r in rows}
        return Scope(scope_mode, meta, len(meta), enr_exists, empty=not meta)

    # Derived: the vendor set is an OUTPUT of classification, never an input.
    vendor_count = 0
    if enr_exists:
        try:
            vc = await pg.select_safe(
                "SELECT COUNT(DISTINCT c.vendor_name) AS n FROM contracts c "
                "WHERE coalesce(c.vendor_name,'') <> '' AND "
                + where_sql("derived", "c", ""))
            vendor_count = int(vc[0]["n"]) if vc else 0
        except Exception as exc:  # noqa: BLE001
            if logger:
                logger.warning("digitalscope vendor count failed: %s", exc_str(exc))
    return Scope(scope_mode, {}, vendor_count, enr_exists, empty=not enr_exists)
