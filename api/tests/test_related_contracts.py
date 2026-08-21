"""Guards for the contract page's "Related contracts" block (task 2eba1fce (a)).

⚠⚠ THE SECOND SIGNAL IS ALMOST PURE NOISE WITHOUT ITS TWO RULES. Measured across
all 56,806 contracts on 2026-08-18:
  * 46,607 contracts co-terminate with a DIFFERENT vendor at the same agency;
  * the largest group is 4,721 contracts (DYCD, 06/30/2023), then 1,873 / 1,835 /
    1,751 — and EVERY oversized group lands on 06/30, the NYC fiscal-year
    boundary, where a shared end date carries no information at all.
Dropping either rule re-admits a "4,721 related contracts" block. With both, 3,488
groups / 12,007 contracts survive — and MOCS's PASSPort, at 5 contracts and
$78.1M all ending 04/27/2027, is among them.
"""
import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
OCE = os.path.join(ROOT, 'api/routers/oce.py')
CTRL = os.path.join(ROOT, 'app/app/Http/Controllers/ProcurementController.php')
VIEW = os.path.join(ROOT, 'app/resources/views/procurement/contract_profile.blade.php')


def _read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


def _fn():
    s = _read(OCE)
    body = s[s.index('async def _related_contracts'):]
    return body[:body.index('\nasync def ', 5)]


def test_the_fiscal_year_boundary_is_excluded():
    """⚠ 06/30 is where hundreds of unrelated contracts expire together. Without
    this the block shows a DYCD contract 4,720 'related' ones.

    ⚠ ASSERTS THE PREDICATE, NOT THE STRING. This guard's first draft checked
    `'06/30' in code` after stripping `#` comments — and passed with the exclusion
    deleted, because the function's DOCSTRING explains the 06/30 rule and a
    docstring is not a `#` comment. Fourth time in one session that a scanner
    matched prose; assert the executable expression.
    """
    import ast
    tree = ast.parse(_read(OCE))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.AsyncFunctionDef) and n.name == '_related_contracts')
    # Ignore the docstring node entirely, then look for the real call.
    body = fn.body[1:] if (fn.body and isinstance(fn.body[0], ast.Expr)
                           and isinstance(fn.body[0].value, ast.Constant)) else fn.body
    calls = [n for n in ast.walk(ast.Module(body=body, type_ignores=[]))
             if isinstance(n, ast.Call)
             and getattr(n.func, 'attr', '') == 'startswith'
             and any(isinstance(a, ast.Constant) and a.value == '06/30' for a in n.args)]
    assert calls, (
        "the fiscal-year-boundary exclusion is gone from the CODE; without it a "
        "DYCD contract shows 4,720 'related' contracts")


def test_the_group_size_cap_exists_and_is_applied():
    """A program is a handful of contracts. The cap must gate the RESULT, not
    merely be defined — a constant nothing reads is not a rule."""
    src = _read(OCE)
    assert '_COTERM_MAX_GROUP' in src, "the group-size cap constant is gone"
    body = _fn()
    code = '\n'.join(l for l in body.splitlines() if not l.lstrip().startswith('#'))
    assert re.search(r'len\(peers\)\s*<=\s*_COTERM_MAX_GROUP', code), \
        "the cap is no longer applied to the peer group"


def test_the_two_kinds_are_never_merged():
    """⚠ They carry different evidential weight: same-vendor is a FACT, and
    co-termination is CIRCUMSTANTIAL. Merging them would launder the second."""
    body = _fn()
    assert '"same_vendor"' in body and '"co_terminating"' in body, \
        "the two relatedness kinds are no longer separate keys"


def test_the_page_does_not_claim_co_termination_proves_a_program():
    """⚠ THE STANDING RULE. Co-termination plus a shared agency is circumstantial;
    asserting a shared program from it is the same overreach as claiming a
    product identity from it (the Ivalua/PASSPort caution)."""
    view = _read(VIEW)
    assert 'not evidence that they are' in view, \
        "the page lost the sentence stopping it from asserting a shared program"
    assert 'fiscal-year boundary' in view, \
        "the page no longer discloses the 30 June exclusion"
    assert re.search(r'groups of \{\{ \$rcCap \}\} or fewer', view), \
        "the page no longer states the group-size cap, or hardcodes it instead of " \
        "rendering the served value"


def test_the_controller_passes_related_contracts_to_the_view():
    """⚠⚠ THE #247 DEFECT, and this controller is the shape that caused it — it
    NAMES each key rather than passing the payload wholesale, so a new key
    silently never arrives and `?? []` degrades politely. Only fetching the page
    would otherwise catch it."""
    ctrl = _read(CTRL)
    assert "'relatedContracts' => $data['related_contracts']" in ctrl, \
        "the controller does not pass related_contracts; the block renders empty"
    view = _read(VIEW)
    assert '$relatedContracts' in view, "the view no longer reads the key"


def test_the_endpoint_serves_the_key():
    src = _read(OCE)
    assert '"related_contracts": await _related_contracts(' in src, \
        "the contract endpoint no longer serves related_contracts"
