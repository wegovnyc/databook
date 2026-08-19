"""ONE definition of "expiring", shared by the Renewal Queue and the Licenses page.

⚠⚠ WHY THIS EXISTS. Two pages count the same thing — licence contracts that end
in the future but before the horizon — through two different mechanisms: the
queue filters in SQL, the Licenses page filters in Python after loading its rows.
Same semantics, written twice, with the horizon typed as a literal in each. That
is the shape of every drift this codebase has paid for: nothing fails, the two
figures just stop agreeing, and neither page can tell you which one is wrong.

The horizon lives here once. Both mechanisms are still two mechanisms — a unit
test cannot prove a SQL string and a Python predicate agree — so what this module
buys is narrower and worth stating plainly: **the boundary cannot drift**, and a
guard can prove neither page defines its own.

⚠ The "counts agree" property itself is checked at RUNTIME against both payloads
by scripts/digital-licence-count-check.sh, because that is the only place the two
row sets actually exist.
"""

# ⚠ EXCLUSIVE upper bound, and the queue's copy was `< DATE '2030-01-01'` while
# the Licenses page's was `< "2030-01-01"` on an ISO string. Both exclusive, which
# is why they agreed; a future edit to one of them is what this constant prevents.
HORIZON = "2030-01-01"


def sql_clause(alias: str, col: str = "end_date") -> str:
    """The window as a SQL predicate over an MM/DD/YYYY text column.

    ⚠ The LENGTH check is part of the definition, not defensive noise: `contracts`
    carries blank and short end_date values, and `TO_DATE` on those either raises
    or invents a date. The Python side refuses the same rows for the same reason.
    """
    c = f"{alias}.{col}"
    return (f"{c} IS NOT NULL AND LENGTH({c}) = 10"
            f" AND TO_DATE({c}, 'MM/DD/YYYY') >= CURRENT_DATE"
            f" AND TO_DATE({c}, 'MM/DD/YYYY') < DATE '{HORIZON}'")


def is_expiring(end_date, today) -> bool:
    """Ends in the future but before HORIZON. `today` is an ISO date string.

    Compares ISO strings rather than dates on purpose: the source column is text,
    and a parse step here would be a second place for a timezone to creep in.
    """
    if not end_date or len(str(end_date).strip()) != 10:
        return False
    try:
        mm, dd, yy = str(end_date).strip().split("/")
    except ValueError:
        return False
    iso = f"{yy}-{mm}-{dd}"
    return today <= iso < HORIZON
