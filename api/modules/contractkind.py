"""One owner for whether a contract's dollar figure is MONEY or a CEILING.

⚠⚠ THE DEFECT THIS EXISTS TO PREVENT. PASSPort issues two different kinds of
instrument under one `contract_id` column, and their amounts mean different
things:

* an **ordinary contract** (`CT`, `CTA`, `RCT`, `CTR`) — money committed to this
  agreement, drawn down by payments filed against this id;
* a **master agreement** (`MA`, `MMA`) — a **ceiling agencies may buy against**.
  Agencies purchase from it on their own purchase orders, which carry their own
  ids, so the money is filed elsewhere. That is what a master IS.

Summing the two produces a number that looks like spend and is not. Measured on
the live renewal queue 2026-08-17:

    kind                    rows      value      with >=1 payment
    CT / CTA / RCT           633   $2,178.5M     555   (88%)
    MA / MMA                  57   $1,623.9M       0   ( 0%)
    ------------------------------------------------------------
    headline                 690   $3,802.4M

**43% of that headline has never been drawn against**, and not one master
carries a payment under its own id. The same split was measured independently on
the licence set (29 masters, $727.4M, 0 with a payment, against 92% of ordinary
contracts) — so this is a property of the instrument, not of one page's filter.

The worst single case is the "Citywide System Integration Class 3" family: 17
vehicles, $441.0M, seven at exactly $50.0M. Each reads as $50M of spend about to
renew; none has ever been drawn against.

⚠⚠ THE PARSE IS A LEADING-ALPHA RUN, NEVER A PREFIX MATCH, and getting this
wrong fails silently in the expensive direction. `contract_id.startswith("MA")`
does **not** match `MMA1-858-20268803269` — that is **1,180 contracts and
$23.4B** classified as committed money. Extract the alphabetic run and compare it
to a set.

Measured vocabulary across all 56,806 contract rows (2026-08-17):

    CT      48,876    $141,323.0M     ordinary
    (none)   2,550     $14,535.5M     no contract_id at all — unregistered rows
                                      keyed on EPIN, which the queue excludes
    CTA      2,192      $2,049.4M     ordinary
    MMA      1,180     $23,443.9M     MASTER
    MA         975      $7,156.0M     MASTER
    RCT         32        $130.6M     ordinary
    CTR          1          $7.0M     ordinary

⚠ `CTR` is why the run is extracted rather than prefix-matched from the other
end too: it is its own kind, not a `CT`. Nothing depends on that today, but a
`startswith` here would be right by luck rather than by rule.

⚠ **This module classifies; it does not filter.** Masters belong in the renewal
queue — they expire, and renewing one IS a decision. What must not happen is
adding their ceilings into a figure captioned as spend. The Overview's pipeline
block already established the convention: label the aggregate `ceiling` rather
than `value`, "so the key itself resists summing".
"""

import re

# The two instrument kinds whose amount is a ceiling to buy against.
MASTER_KINDS = frozenset({"MA", "MMA"})

# Leading alphabetic run of a PASSPort contract id: 'MMA1-858-...' -> 'MMA'.
_LEADING_ALPHA = re.compile(r"^\s*([A-Za-z]+)")


def kind(contract_id) -> str:
    """The instrument kind, upper-cased. '' when there is no id or no letters.

    An id-less row is deliberately NOT a master: those are the unregistered rows
    keyed on EPIN, a different question with its own treatment.
    """
    if not contract_id:
        return ""
    m = _LEADING_ALPHA.match(str(contract_id))
    return m.group(1).upper() if m else ""


def is_master(contract_id) -> bool:
    """True when this id names a master agreement, so its amount is a CEILING."""
    return kind(contract_id) in MASTER_KINDS


def split_amounts(rows, amount, contract_id=lambda r: r.get("contract_id")):
    """Split an iterable of rows into (committed, ceiling, n_committed, n_ceiling).

    `amount` and `contract_id` are callables over a row, so this works for dicts,
    asyncpg Records and objects alike without the caller re-deriving the rule.
    Returns floats and ints, never None, so a caller can serialise it directly.
    """
    committed = ceiling = 0.0
    n_committed = n_ceiling = 0
    for r in rows:
        v = float(amount(r) or 0)
        if is_master(contract_id(r)):
            ceiling += v
            n_ceiling += 1
        else:
            committed += v
            n_committed += 1
    return committed, ceiling, n_committed, n_ceiling


def sql_is_master(col: str) -> str:
    """The same rule as a SQL predicate, for aggregates done in Postgres.

    ⚠ Must stay equivalent to `is_master`. A guard test asserts both agree on the
    full measured vocabulary — a Python rule and a SQL rule that drift are two
    owners wearing one name, which is the defect this module exists to end.
    """
    kinds = ", ".join(f"'{k}'" for k in sorted(MASTER_KINDS))
    return f"substring({col} from '^[A-Za-z]+') IN ({kinds})"
