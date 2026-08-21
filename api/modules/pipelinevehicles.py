"""Purchasing vehicles that have NOT reached registration — one owner, one figure.

⚠⚠ WHY THIS EXISTS AT ALL (#238). PASSPort assigns `contract_id` at REGISTRATION,
and every query in this section keys on it — so **2,546 rows worth $14.5B** sit in
approval invisible to every figure the section publishes. Excluding them from the
totals is RIGHT: they are ceilings on unsigned paper, mostly covering far more than
the thing being analysed. Saying nothing about them was wrong, because the section's
argument is that the City should consolidate onto citywide agreements — and the
citywide agreements were precisely the blind spot ($75M CITYWIDE SALESFORCE, a $1.2B
CITYWIDE IT vehicle).

⚠⚠ AND IT MUST NEVER BE MERGED INTO A TOTAL. The value is named `ceiling`, not
`value`, so the key itself resists summing; one leaked row adds a $1.2B ceiling to a
page whose headline is smaller than that. Both consuming pages test-pin the
separation.

⚠ KEYED ON EPIN, because `contract_id` is exactly what these rows lack. Deduplicated
on epin with the same tiebreak as the registered set, so one row per agreement and
no amendment-history inflation.

⚠ THE VENDOR FILTER RUNS BEFORE THE DEDUP, ON PURPOSE, and it changes the count by
one. Measured 2026-08-13: **2 unregistered epins carry rows from more than one
vendor**, and for `81625Z0011001` the highest-value row belongs to a non-tech vendor
while a lower row belongs to a tech one. Filtering first keeps that vehicle (257
rows); filtering after the dedup would drop it (256). Keeping it is right — the
vehicle does involve a vendor who sells the City technology — but note the
consequence: for those 2 epins the displayed `ceiling` is the tech vendor's row, not
the whole vehicle's largest. One row per (agreement, chosen vendor), not strictly per
agreement.

⚠ Moved out of routers/licenses.py (#247) because the block's canonical home is the
section OVERVIEW: scoped to the whole derived tech vendor set it is 256 rows /
$3,220.8M, against 121 rows / $1,610.4M when scoped only to vendors who sell
licences. Two pages publishing two different pipeline figures for the same idea is
the "second answer to the same question" defect; the Licenses page now points here
instead of computing its own.
"""
from modules.errfmt import exc_str

# Vehicles below this are noise beside a multi-billion page; the count and the
# combined ceiling are still reported over the FULL set, so the cap is disclosed
# rather than hidden.
DISPLAY_FLOOR = 1_000_000

_SQL = """
    SELECT DISTINCT ON (epin)
           epin, contract_title, vendor_name, agency, contract_type,
           status, award_amount, current_amount, start_date, end_date,
           procurement_method
    -- RAW-CONTRACTS-JOIN-OK: deduped on EPIN because these rows have no
    -- contract_id, which is the entire reason they are invisible elsewhere.
    FROM contracts
    WHERE contract_id IS NULL
      AND coalesce(epin, '') <> ''
      AND vendor_name = ANY($1)
    ORDER BY epin, coalesce(current_amount, 0) DESC, coalesce(award_amount, 0) DESC
"""


async def load(pg, vendor_names, logger=None) -> dict:
    """The pipeline block for a given vendor set.

    ⚠ The vendor set is passed IN, computed by the caller from rows it already has
    in Python — never re-derived here by joining `contracts` again, and never taken
    from `vendor_tags`, which is a name heuristic that admits janitorial services
    and ship repair onto a technology page.

    Degrades to an empty block rather than raising: a missing pipeline costs a
    disclosure, not the page.
    """
    names = sorted({(n or "").strip() for n in (vendor_names or []) if (n or "").strip()})
    empty = {"rows": [], "count": 0, "ceiling": 0.0, "masters": 0,
             "floor": DISPLAY_FLOOR, "vendors": 0}
    if not names:
        return empty
    try:
        rows = await pg.select_safe(_SQL, [names]) or []
    except Exception as exc:  # noqa: BLE001
        if logger:
            logger.warning("pipeline vehicles unavailable: %s", exc_str(exc))
        return empty

    out = []
    for r in rows:
        d = dict(r)
        # ⚠ `ceiling`, not `value`. See the module docstring.
        d["ceiling"] = float(d.get("current_amount") or d.get("award_amount") or 0)
        d.pop("current_amount", None)
        d.pop("award_amount", None)
        d["is_master"] = "MA1" in (d.get("contract_type") or "")
        out.append(d)
    out.sort(key=lambda a: -a["ceiling"])
    return {
        # Capped for display; every figure beside it is counted on the full set.
        "rows": [r for r in out if r["ceiling"] >= DISPLAY_FLOOR],
        "count": len(out),
        "ceiling": sum(r["ceiling"] for r in out),
        "masters": sum(1 for r in out if r["is_master"]),
        "floor": DISPLAY_FLOOR,
        "vendors": len({r.get("vendor_name") for r in out if r.get("vendor_name")}),
    }
