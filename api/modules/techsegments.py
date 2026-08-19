"""How technology spend divides up — the Overview's headline lens, in ONE place.

⚠⚠ THE PLAN'S SIX-SEGMENT BAR MIXED TWO AXES, AND MEASURING IT IS WHAT SHOWED
THAT. `docs/DIGITAL-SERVICES-SECTION-PLAN.md` §2 asks for "hardware / people / data
platforms / licences / telecom / payments". But **`licences` is not a
function_category** — `is_license` is a FLAG that cuts across every one of them.
Measured 2026-08-13 on the derived scope: of 584 Data/analytics contracts **400 are
licences**, 158 of 160 Office productivity, 147 of 870 Hardware/infrastructure. A
bar with "licences" beside "hardware" would count a Microsoft ELA in both or in
whichever segment came first.

So the partition is: **a contract bought as a licence is a licence; everything else
is named by its function.** One axis, one bucket per contract, and it closes —
verified against the whole universe: 15 segments, 4,397 contracts, $10,610.5M, no
remainder. It also reproduces the plan's own §3a table to the dollar (Staffing
$2,872.6M, Hardware $2,798.1M, Telecom $1,875.5M, licences $1,770.3M …), which is
how we know §3a computed it this way too and the plan's prose was the loose part.

⚠ `function_category` is the classifier's FREE-TEXT bucket with no curation layer —
the coarse cousin of the licence set's 47-tag vocabulary. It is displayed as it is
stored, never mapped into friendlier names here: an invented display name would be
a second vocabulary, and §5b already records that one segment's top two rows once
carried a $1.93B error. Corrections belong in
`api/seed/contract_enrichment_curated.csv`, at contract grain, where they are
reviewable.
"""
import re

# The one cross-cutting segment. Everything else is a function_category verbatim.
LICENCE_SEGMENT = "Software licences"

# Sentinel for a contract the classifier confirmed as tech but never gave a
# function. ⚠ Reported as its own segment rather than folded into a real one:
# quietly defaulting it would overstate how much has actually been categorised.
UNCLASSIFIED_SEGMENT = "(uncategorised)"

# ⚠ THE BAR IS CAPPED AND THE PAGE SAYS SO. 15 segments in one stacked bar is not a
# lens, it is a rug; six of them are under 0.3% of value and render as invisible
# slivers. Segments below this share of total value fold into one OTHER band, whose
# contract count and value are still reported — a threshold a reader cannot see is
# indistinguishable from an opinion.
BAR_MIN_SHARE = 0.01
OTHER_SEGMENT = "Other technology"


def slug(name: str) -> str:
    """A stable URL key for a segment. Kept here so the bar and the drill-down
    cannot disagree about what a segment is called."""
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (name or "").lower())).strip("-")


def segment_of(is_license, function_category) -> str:
    """The ONE bucket a contract belongs to."""
    if is_license:
        return LICENCE_SEGMENT
    fc = (function_category or "").strip()
    return fc or UNCLASSIFIED_SEGMENT


def resolve_slug(seg_slug: str, segments) -> str:
    """slug -> the segment's stored name, using the segments the page just computed.

    ⚠ Resolved against the DATA, not by reversing the slug function. A category is
    free text from the classifier ("Telecom/network", "ERP/financials"), and slugging
    is lossy — reversing it would guess at the punctuation and match nothing. Returns
    "" when the slug names no segment, which callers treat as "no filter" rather than
    as an empty result set.
    """
    s = (seg_slug or "").strip().lower()
    if not s:
        return ""
    for a in (segments or []):
        if a.get("slug") == s:
            return a.get("segment") or ""
    return ""


def sql_predicate(segment_name: str, param_index: int, enr_alias: str = "e"):
    """SQL for "this contract is in `segment_name`", as (sql, params).

    `param_index` is the caller's next free placeholder number, so the free-text
    category is BOUND rather than interpolated — these strings come from the
    classifier, not from us.

    ⚠ THE `NOT is_license` HALF IS LOAD-BEARING. Without it, drilling into
    "Data/analytics" would also return the 400 licence contracts the bar counted
    under licences, so the drill-down would not add up to the segment it was reached
    from — the exact defect this partition exists to prevent.
    """
    name = (segment_name or "").strip()
    if not name:
        return None
    if name == LICENCE_SEGMENT:
        return (f"{enr_alias}.is_license", [])
    if name == UNCLASSIFIED_SEGMENT:
        return (f"NOT {enr_alias}.is_license AND "
                f"coalesce(nullif(trim({enr_alias}.function_category), ''), '') = ''", [])
    return (f"NOT {enr_alias}.is_license AND trim({enr_alias}.function_category) = ${param_index}",
            [name])


def rollup(rows, value_of=None):
    """[{segment, slug, contracts, value, licences, active_contracts, active_value}]
    ordered by value, plus the bar's capped view.

    `rows` are dicts with `is_license`, `function_category`, `ended` and a value.
    Returns (segments, bar) where `bar` folds sub-threshold segments into OTHER.

    ⚠ Counted over the FULL set and capped only for the bar, with the folded count
    carried — reading a count off a truncated list is the count-before-you-cap
    defect this codebase has already paid for twice.
    """
    val = value_of or (lambda r: float(r.get("value") or 0))
    acc = {}
    # ⚠⚠ THE BRIDGE BETWEEN THE TWO AXES, and the page's actual argument. A
    # per-segment "licences" count is VACUOUS under this partition — it equals the
    # segment for licences and 0 for everything else, which is a field that can only
    # restate its own row. What is worth knowing is the cross-cut the partition
    # necessarily hides: how many contracts doing THIS JOB were bought as licences
    # and are therefore counted under the licence segment. Measured: Data/analytics
    # shows 184 non-licence contracts here while **400 more** Data/analytics
    # contracts are licences; Office productivity is 2 against 158.
    lic_by_function = {}
    for r in rows:
        key = segment_of(r.get("is_license"), r.get("function_category"))
        a = acc.setdefault(key, {"segment": key, "slug": slug(key), "contracts": 0,
                                 "value": 0.0, "active_contracts": 0, "active_value": 0.0})
        v = val(r)
        a["contracts"] += 1
        a["value"] += v
        if not r.get("ended"):
            a["active_contracts"] += 1
            a["active_value"] += v
        if r.get("is_license"):
            fc = (r.get("function_category") or "").strip() or UNCLASSIFIED_SEGMENT
            f = lic_by_function.setdefault(fc, {"function": fc, "contracts": 0, "value": 0.0})
            f["contracts"] += 1
            f["value"] += v
    segments = sorted(acc.values(), key=lambda a: -a["value"])

    for a in segments:
        if a["segment"] == LICENCE_SEGMENT:
            # What the licences actually DO — the licence segment's own function mix,
            # counted in full and capped only for display.
            fns = sorted(lic_by_function.values(), key=lambda f: -f["value"])
            a["functions"] = fns[:8]
            a["functions_total"] = len(fns)
        else:
            sib = lic_by_function.get(a["segment"])
            a["licence_siblings"] = sib["contracts"] if sib else 0
            a["licence_siblings_value"] = sib["value"] if sib else 0.0

    total = sum(a["value"] for a in segments)
    floor = total * BAR_MIN_SHARE
    keep = [a for a in segments if a["value"] >= floor]
    fold = [a for a in segments if a["value"] < floor]
    bar = [{"segment": a["segment"], "slug": a["slug"], "contracts": a["contracts"],
            "value": a["value"], "share": (a["value"] / total) if total else 0}
           for a in keep]
    if fold:
        folded_value = sum(a["value"] for a in fold)
        bar.append({"segment": OTHER_SEGMENT, "slug": "", "folded": len(fold),
                    "contracts": sum(a["contracts"] for a in fold),
                    "value": folded_value,
                    "share": (folded_value / total) if total else 0,
                    "segments": [a["segment"] for a in fold]})
    return segments, bar
