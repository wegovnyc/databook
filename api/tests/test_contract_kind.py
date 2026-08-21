"""A contract's amount is either committed money or a ceiling — one owner for which.

⚠⚠ THE DEFECT. PASSPort issues ordinary contracts (`CT`, `CTA`, `RCT`, `CTR`) and
master agreements (`MA`, `MMA`) under one `contract_id` column. A master's figure
is a **ceiling agencies may buy against**, drawn down through purchase orders
that carry their own ids — so it carries no payments under its own id at all.
Measured on the live renewal queue: **0 of 57 masters have a payment, against 88%
of 633 ordinary contracts**, while masters contribute **$1,623.9M of the $3,802.4M
headline — 43%**.

Three surfaces made that judgement separately by not making it at all: the queue
headline, the vendor profile's awarded total, and the `vendor_lock_in` flag's
published "this vendor holds $189M citywide". These guards exist so the rule has
one home and cannot drift back apart.
"""

import importlib.util
import os
import re

import pytest

_API_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def _load(name):
    """Load by PATH.

    ⚠ `conftest.py` does `sys.modules.setdefault("modules", MagicMock())`, so
    `from modules import contractkind` yields a mock whose every attribute
    satisfies almost any assertion. This repo has been bitten by that twice.
    """
    path = os.path.join(_API_DIR, "modules", f"{name}.py")
    spec = importlib.util.spec_from_file_location(f"_{name}_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ck = _load("contractkind")

# The complete measured vocabulary, 2026-08-17, across all 56,806 contract rows.
# (kind, example id, is it a ceiling)
MEASURED = [
    ("CT",   "CT1-002-20248805109",   False),
    ("CTA",  "CTA1-857-20218800132",  False),
    ("RCT",  "RCT1-856-20198801234",  False),
    ("CTR",  "CTR1-850-20208800001",  False),
    ("MA",   "MA1-858-20268801889",   True),
    ("MMA",  "MMA1-858-20268803269",  True),
]


@pytest.mark.parametrize("kind,example,ceiling", MEASURED)
def test_every_measured_kind_classifies_as_measured(kind, example, ceiling):
    assert ck.kind(example) == kind
    assert ck.is_master(example) is ceiling


def test_a_prefix_match_would_miss_MMA_which_is_the_expensive_direction():
    """⚠⚠ THE TRAP THIS MODULE EXISTS FOR.

    `contract_id.startswith("MA")` is False for `MMA1-858-...`, so the naive
    rule would classify **1,180 contracts and $23.4B** of ceiling as committed
    money — silently, and in the direction that overstates spend.
    """
    mmid = "MMA1-858-20268803269"
    assert not mmid.startswith("MA"), "premise of this guard has changed"
    assert ck.is_master(mmid), "MMA must be a master; a prefix match would miss it"


def test_an_id_less_row_is_not_a_master():
    """2,550 contract rows carry no contract_id — the unregistered rows keyed on
    EPIN. They are a different question, and must not be swept into `ceiling`."""
    for empty in (None, "", "   "):
        assert ck.kind(empty) == ""
        assert ck.is_master(empty) is False


def test_split_amounts_separates_and_never_loses_money():
    rows = [
        {"contract_id": "CT1-002-1",  "v": 100.0},
        {"contract_id": "MMA1-858-1", "v": 50.0},
        {"contract_id": "MA1-858-1",  "v": 25.0},
        {"contract_id": None,         "v": 7.0},
    ]
    committed, ceiling, nc, nk = ck.split_amounts(rows, amount=lambda r: r["v"])
    assert (committed, ceiling) == (107.0, 75.0)
    assert (nc, nk) == (2, 2)
    # The whole point: the two are reported separately AND still account for
    # every row, so nothing falls into an undisclosed gap.
    assert committed + ceiling == sum(r["v"] for r in rows)
    assert nc + nk == len(rows)


def test_the_sql_rule_and_the_python_rule_agree():
    """⚠ A Python rule and a SQL rule that drift are two owners wearing one name —
    exactly the defect this module ends. The SQL is used for the lock-in
    denominator, which is a PUBLISHED claim about a named vendor."""
    sql = ck.sql_is_master("c.contract_id")
    assert "substring(" in sql and "^[A-Za-z]+" in sql, (
        "the SQL must extract the leading alpha run, not prefix-match — a "
        "LIKE 'MA%' would both miss MMA and match nothing else correctly"
    )
    quoted = set(re.findall(r"'([A-Z]+)'", sql))
    assert quoted == set(ck.MASTER_KINDS), (
        f"SQL names {sorted(quoted)} but MASTER_KINDS is "
        f"{sorted(ck.MASTER_KINDS)} — they have drifted"
    )


def test_master_kinds_has_not_silently_grown_or_shrunk():
    """Pins the set itself. Adding a kind here reclassifies published dollar
    figures on three surfaces, so it should be a deliberate diff."""
    assert set(ck.MASTER_KINDS) == {"MA", "MMA"}


# ---------------------------------------------------------------------------
# The call sites. Guards that the rule is USED, not merely available — the
# direction that catches a surface reverting to its own arithmetic.
# ---------------------------------------------------------------------------

def _oce():
    with open(os.path.join(_API_DIR, "routers", "oce.py"), encoding="utf-8") as fh:
        return fh.read()


def test_the_queue_summary_reports_both_committed_and_ceiling():
    src = _oce()
    for key in ("'committed_value'", "'ceiling_value'",
                "'committed_count'", "'ceiling_count'"):
        assert key in src, f"the queue summary no longer serves {key}"


def test_every_queue_row_carries_its_amount_kind():
    src = _oce()
    assert "'amount_kind'" in src, (
        "rows must say whether their money is committed or a ceiling, or the "
        "page cannot label a $50.0M master differently from a $50.0M contract"
    )


def test_the_lock_in_denominator_excludes_ceilings():
    """The flag publishes a dollar figure about a NAMED VENDOR, which makes it
    the most sensitive of the three surfaces."""
    src = _oce()
    assert "committed_total" in src, "the lock-in query no longer splits its total"

    # ⚠ SCOPED TO THE STATEMENT, NOT THE WORD. `vcommitted >= 150_000_000` appears
    # twice — once as the threshold and once as the display condition — so a bare
    # `in src` check passes even when the THRESHOLD reverts to `vtotal`. Verified:
    # mutating only the threshold left the guard green until this was tightened.
    # ⚠ `if vagencies >= 6 or` — the trailing `or` is what separates the THRESHOLD
    # from the display line `if vagencies >= 6: bits.append(...)` three lines
    # below it, which starts identically. Selecting on the shorter prefix matched
    # both and made this guard misreport.
    tests = [ln.strip() for ln in src.splitlines()
             if ln.strip().startswith("if vagencies >= 6 or")]
    assert len(tests) == 1, (
        f"expected exactly one lock-in threshold statement, found {len(tests)} — "
        "re-scope this guard before trusting it"
    )
    threshold = tests[0]
    assert "vcommitted" in threshold, (
        f"the lock-in threshold must test COMMITTED money, got: {threshold}"
    )
    assert "vtotal" not in threshold, (
        f"the lock-in threshold tests `vtotal`, so it trips on ceilings nobody "
        f"has been paid: {threshold}"
    )


def test_the_vendor_profile_divides_utilisation_by_committed_money():
    src = _oce()
    assert '"ceiling": ceiling' in src, (
        "the vendor profile no longer reports ceilings separately"
    )
    assert "paid / awarded" in src, "pct_used changed shape — re-check the denominator"


def test_no_surface_re_derives_the_master_rule_itself():
    """⚠ The direction that catches the code nobody has written yet: a new
    surface hand-rolling `startswith('MA')` or an inline SQL IN-list instead of
    calling the module.

    ⚠⚠ IT READS THE AST, NOT THE TEXT, and the first draft proved why: it fired
    on the comment in `oce.py` that EXPLAINS this trap. A scanner that reads
    prose as code reports problems that are not there — the mirror of the guard
    that scanned zero files. Comments are invisible to `ast`, and docstrings are
    excluded explicitly, while ordinary string literals are still scanned
    because that is where an inline SQL IN-list would hide.
    """
    import ast as _ast

    sql_inlist = re.compile(r"IN\s*\(\s*'MM?A'\s*,", re.I)
    offenders, scanned = [], 0

    for sub in ("routers", "modules"):
        for dirpath, dirnames, filenames in os.walk(os.path.join(_API_DIR, sub)):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fn in filenames:
                if not fn.endswith(".py") or fn == "contractkind.py":
                    continue
                p = os.path.join(dirpath, fn)
                rel = os.path.relpath(p, _API_DIR)
                with open(p, encoding="utf-8") as fh:
                    try:
                        tree = _ast.parse(fh.read())
                    except SyntaxError:
                        continue
                scanned += 1

                doc_ids = set()
                for node in _ast.walk(tree):
                    if isinstance(node, (_ast.Module, _ast.FunctionDef,
                                         _ast.AsyncFunctionDef, _ast.ClassDef)) and node.body:
                        first = node.body[0]
                        if (isinstance(first, _ast.Expr)
                                and isinstance(first.value, _ast.Constant)
                                and isinstance(first.value.value, str)):
                            doc_ids.add(id(first.value))

                for node in _ast.walk(tree):
                    # a real `x.startswith("MA")` call, not the words in a comment
                    if (isinstance(node, _ast.Call)
                            and isinstance(node.func, _ast.Attribute)
                            and node.func.attr == "startswith"
                            and node.args
                            and isinstance(node.args[0], _ast.Constant)
                            and str(node.args[0].value).upper() in {"MA", "MMA"}):
                        offenders.append(f"{rel}:{node.lineno} startswith(...)")
                    # an inline SQL IN-list, which lives in a real string literal
                    if (isinstance(node, _ast.Constant)
                            and isinstance(node.value, str)
                            and id(node) not in doc_ids
                            and sql_inlist.search(node.value)):
                        offenders.append(f"{rel}:{getattr(node,'lineno',0)} inline SQL IN-list")

    assert scanned > 10, f"only scanned {scanned} files — the walk is vacuous"
    assert not offenders, (
        "these re-derive the master-agreement rule instead of using "
        "modules/contractkind:\n  " + "\n  ".join(offenders)
    )
