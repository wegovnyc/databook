"""The vendor profile lists one row per CONTRACT, never one per amendment.

⚠⚠ THE DEFECT. `contracts` carries a row per amendment / change order —
**53,260 rows for 36,421 distinct contract_ids, 32% duplicates** — while the
Checkbook spend map is keyed on `contract_id`. So a query that lists every row
attributes the SAME paid figure to each amendment and then sums them.

Measured on prod 2026-08-18: ACCENTURE LLP's `CT1-057-20228806565` appears **4
times**, each carrying the whole **$13.3M**. The profile therefore reported
paying **197.9% of what it awarded**, and both `paid` and `awarded` were
inflated by amendment count.

⚠ It surfaced only when the ceiling fix (#261) removed master-agreement headroom
from the denominator. The inflated denominator had been masking it — one sampled
vendor showed 151.2% with no ceilings at all, so the double-count predates that
change entirely.

⚠⚠ AND THE DEDUPE KEY IS THE TRAP. `DISTINCT ON (contract_id)` alone collapses
every NULL-id row of a vendor into one, and **2,546 rows across 1,866 vendors
have no contract_id** (the unregistered rows keyed on EPIN). INFOPEOPLE
CORPORATION has 11 — ten real contracts would vanish from its page. The key must
fall back to something row-unique.
"""

import os
import re

_API_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def _vendor_query():
    """The SQL the vendor profile uses to list a vendor's contracts."""
    with open(os.path.join(_API_DIR, "routers", "oce.py"), encoding="utf-8") as fh:
        src = fh.read()
    i = src.index("async def get_vendor(")
    body = src[i:i + 4000]
    m = re.search(r"contracts = await PostgresModelAsync\.select_safe\((.*?)\)\s*\n",
                  body, re.S)
    assert m, "could not locate the vendor contract query — re-scope this guard"
    return m.group(1)


def test_the_vendor_contract_list_is_deduped_per_contract():
    q = _vendor_query()
    assert "DISTINCT ON" in q, (
        "the vendor profile lists every amendment row again — the spend map is "
        "keyed on contract_id, so paid is multiplied by amendment count"
    )


def test_the_dedupe_key_does_not_collapse_id_less_rows():
    """⚠ The half that loses data rather than inflating it."""
    q = _vendor_query()
    assert re.search(r"DISTINCT ON \(\s*coalesce\(", q), (
        "DISTINCT ON must key on coalesce(contract_id, <row-unique>) — keying on "
        "contract_id alone collapses a vendor's 11 unregistered rows into 1"
    )
    assert "ctid" in q, (
        "the fallback must be row-unique; 2,546 rows across 1,866 vendors have "
        "no contract_id"
    )


def test_distinct_on_is_ordered_by_its_own_key_first():
    """Postgres requires it, and getting it wrong is a runtime error rather than
    a wrong number — pinned so the ORDER BY cannot be 'tidied' into a break."""
    q = _vendor_query()
    # ⚠ Do NOT split the ORDER BY on commas — the key itself contains one, inside
    # `coalesce(contract_id, 'row:' || ctid::text)`. The first draft of this guard
    # did, and failed on correct SQL. Compare by prefix instead.
    m = re.search(r"DISTINCT ON \((.*?)\)\s*\*", q, re.S)
    assert m, "no DISTINCT ON found"
    key = re.sub(r"\s+", "", m.group(1))
    assert "ORDER BY" in q, "the DISTINCT ON query has no ORDER BY"
    order = re.sub(r"\s+", "", q.split("ORDER BY", 1)[1])
    assert order.startswith(key), (
        f"DISTINCT ON key {key!r} must lead the ORDER BY, which starts "
        f"{order[:len(key)]!r} — Postgres errors otherwise"
    )


def test_the_largest_current_value_wins():
    """Amendments RESTATE a contract's total rather than adding to it, so the
    surviving row must be the largest — verified on the Ivalua contract, whose
    amendment rows run 2.3 / 3.1 / 3.9 / 6.5 / 17.8 / 37.9 where 37.9 is the
    whole agreement."""
    q = _vendor_query()
    assert re.search(r"current_amount\s+DESC", q), (
        "the surviving row must be the one with the largest current_amount, or "
        "the profile reports a stale amendment as the contract"
    )
