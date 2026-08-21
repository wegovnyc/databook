"""Resolving a vendor NAME to a PASSPort supplier id — the one rule, everywhere.

⚠⚠ THE DEFECT CLASS. `contracts` identifies a vendor only by `vendor_name`: it
carries no supplier id and no FMS code. So every surface that wants to link a
contract to a vendor profile has to resolve the name — and **48 vendor names hold
more than one row in `vendors`** (PASSPort duplicate registrations; 42 of them with
a distinct FMS vendor code per record, ABSORB SOFTWARE INC being 1871820/FNR0000088
and 2073456/FNR0000453, identical in every other field).

Resolved with a `LEFT JOIN`, one contract comes back as two rows. That has now been
found on three surfaces, with three different consequences:

  Renewal Queue          a contract listed twice -> 243 expiring licences where the
                         Licenses page said 242                              (#244)
  Agency profile         a vendor listed twice -> the Vendors badge read 1-3
                         higher than the Vendors tile on 12 agencies         (#245)
  Daily briefing         `LIMIT 10`, so the duplicate DROPS a real new vendor
                         off the briefing entirely                           (#246)

The fix is always the same: `modules/vendorids`, a map keyed only where a name
resolves to exactly ONE supplier id. A map cannot duplicate a row, and an ambiguous
name goes unlinked rather than sending a reader to an arbitrary one of two companies.

⚠ THIS FILE'S JOB IS THE DIRECTION THAT CATCHES CODE NOBODY HAS WRITTEN YET. The
per-surface guards in test_queue_rescope.py assert that three known call sites do
not join. This one holds the INVENTORY: the complete set of name-joins that still
exist, with the reason each survives. A new one anywhere in `api/` fails here.
"""
import importlib.util
import os
import re
import sys
import types

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
API = os.path.join(ROOT, 'api')

# ⚠ EVERY REMAINING name-join on `vendors`, and why it is still there. Measured
# 2026-08-12 by walking api/ — this is an inventory, not a wishlist. Adding a line
# here is a decision that needs a reason beside it; a join NOT listed here fails.
ALLOWED_NAME_JOINS = {
    # The OLD tag-scope dashboard. Its only job is to keep publishing exactly what
    # it published until the Overview rebuild replaces it, and the owner confirmed
    # that on 2026-08-12: fixing these would move a published number by one row for
    # no reader's benefit. Measured: ABSORB SOFTWARE INC is the only affected vendor
    # in that scope and it ranks 183rd, i.e. page 8 of a 25-row table.
    # ⚠ These four keys were WRITTEN BY HAND FIRST AND THREE WERE WRONG — I guessed
    # the endpoint names. The guard reported the real ones, which is the argument for
    # an inventory that is measured rather than described.
    ('api/routers/oce.py', 'get_digital_vendors'): 1,
    ('api/routers/oce.py', 'get_digital_contracts'): 1,
    # ⚠ `get_digital_reform_all` USED to hold 2 (in _vendors and _contracts) and the
    # stale-entry half of this guard is what caught their removal in the Overview
    # rebuild (#247). Both now resolve ids through the map, so the entry is gone.
    # A batch matcher, not a page, and it does NOT duplicate: both queries are
    # `SELECT DISTINCT ON (e.org_name_norm) ... ORDER BY ..., v."PASSPort Supplier-ID"`,
    # so a two-id name yields ONE row.
    # ⚠ It resolves the tie by taking the LOWEST id, which is a guess of the kind
    # vendorids refuses — benign for a duplicate registration (both ids are the same
    # company, and the vendor sub-tables key on the name anyway) but wrong if two
    # genuinely different firms ever share a name. Recorded, not fixed here.
    ('api/enrich_doing_business.py', 'build_crosswalk'): 2,
}

# Files whose *prose* discusses the ban. A guard that reads its own explanation as
# code reports problems that are not there.
_PROSE_ONLY = ('api/tests/', 'api/modules/vendorids.py')


def _load_vendorids():
    errfmt = types.ModuleType('modules.errfmt')
    errfmt.exc_str = lambda e: f"{type(e).__name__}: {e}"
    sys.modules.setdefault('modules.errfmt', errfmt)
    spec = importlib.util.spec_from_file_location(
        '_vendorids', os.path.join(API, 'modules', 'vendorids.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _enclosing_def(src: str, pos: int) -> str:
    """Name of the innermost top-level `def` containing `pos`, or '<module>'.

    ⚠ `[ \t]*`, never `\\s*`: `\\s` matches newlines, so an `^(\\s*)def` pattern
    anchors on a blank line and mis-measures the indent. That exact slip made a
    sibling guard extract an empty function body and pass vacuously.
    """
    best = '<module>'
    for m in re.finditer(r'(?m)^[ \t]*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(', src):
        if m.start() > pos:
            break
        # Only remember defs at the OUTERMOST level, so a nested helper reports its
        # enclosing endpoint — which is the unit the allowlist is written in.
        indent = len(m.group(0)) - len(m.group(0).lstrip())
        if indent == 0:
            best = m.group(1)
    return best


def _strip_py_comments(src: str) -> str:
    return re.sub(r'(?m)^\s*#.*$', '', src)


def test_every_vendor_name_join_in_the_api_is_accounted_for():
    """A new `JOIN vendors ... vendor_name` anywhere in api/ fails until it is
    either removed or listed above with a reason."""
    found = {}
    scanned = 0
    for dirpath, dirnames, filenames in os.walk(API):
        dirnames[:] = [d for d in dirnames
                       if d not in ('__pycache__', 'node_modules', '.git', 'data')]
        for fn in filenames:
            if not fn.endswith('.py'):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, ROOT)
            if any(rel.startswith(p) or rel == p for p in _PROSE_ONLY):
                continue
            scanned += 1
            code = _strip_py_comments(open(path, encoding='utf-8').read())
            for m in re.finditer(r'JOIN\s+vendors\b', code):
                # Only a join whose ON clause resolves on the NAME is the defect;
                # joining on the supplier id is exact and fine.
                tail = code[m.end():m.end() + 400]
                if not re.search(r'Vendor Name', tail):
                    continue
                found[(rel, _enclosing_def(code, m.start()))] = \
                    found.get((rel, _enclosing_def(code, m.start())), 0) + 1

    # ⚠ A guard that walks the tree must assert it looked. api/ holds well over 60
    # python files; a root that resolves wrong scans none and passes.
    assert scanned > 60, f"scanned only {scanned} files — the walk broke"

    unexpected = {k: v for k, v in found.items() if k not in ALLOWED_NAME_JOINS}
    assert not unexpected, (
        "vendor-name JOIN in a place the inventory does not cover — 48 names hold "
        "more than one row in `vendors`, so this duplicates rows. Use "
        "modules/vendorids.unique_map(), or add the site to ALLOWED_NAME_JOINS "
        f"with the reason it must stay:\n  {unexpected}")

    # And the inventory must not rot in the other direction: a line left behind
    # after its join is gone reads as "we still have that problem".
    stale = {k: v for k, v in ALLOWED_NAME_JOINS.items() if k not in found}
    assert not stale, (
        f"ALLOWED_NAME_JOINS lists joins that no longer exist: {stale}. Delete the "
        "entries — an inventory that overstates the problem is as misleading as one "
        "that hides it.")

    # Counts too, so a SECOND join inside an already-listed function is caught.
    wrong = {k: (ALLOWED_NAME_JOINS[k], v) for k, v in found.items()
             if ALLOWED_NAME_JOINS.get(k) != v}
    assert not wrong, f"name-join count changed (expected, found): {wrong}"


def test_the_briefing_resolves_vendor_ids_through_the_shared_query():
    """⚠ The daily briefing runs on its own dedicated connection, so it cannot call
    unique_map(). It must still use the SHARED query rather than writing a second
    one: two spellings of `lower(trim(...))` is how the folding drifts and a map
    silently resolves nothing.

    ⚠ And the consequence here is the worst of the three surfaces: `LIMIT 10` means
    a duplicated row DROPS a real new vendor off the briefing.
    """
    src = open(os.path.join(API, 'routers/data_pipeline.py'), encoding='utf-8').read()
    code = _strip_py_comments(src)
    assert 'vendorids.SQL' in code, \
        "the briefing no longer fetches the shared vendor-id query"
    assert 'vendorids.from_rows(' in code, \
        "the briefing builds the map itself instead of through vendorids.from_rows"
    assert 'vendorids.key(' in code, \
        "the briefing folds the lookup key itself — it must match the map's keying"
    assert 'PASSPort Supplier-ID' not in code, \
        "the briefing spells out the supplier-id column again — that is a second " \
        "copy of the lookup, which is what drifts"
    # The fallback matters: an unresolved name must still reach a real destination.
    assert 'if passport_id:' in code and '/procurement/contract/' in code, \
        "the briefing lost the contract-page fallback for an unlinkable vendor"


def test_the_shared_query_is_one_query_with_the_uniqueness_rule_intact():
    """`SQL` and `from_rows` are public so a caller with its own connection cannot
    justify writing its own. Both halves must stay, and so must the rule."""
    vi = _load_vendorids()
    assert re.search(r'HAVING\s+count\(DISTINCT\s+"PASSPort Supplier-ID"\)\s*=\s*1', vi.SQL), \
        "the shared query lost its uniqueness condition — the map now guesses"
    assert vi.from_rows([{"nm": "x", "vendor_id": "1"}]) == {"x": "1"}
    assert vi.from_rows(None) == {}
    # Keying is folded in ONE place, and identically on both sides.
    assert vi.key('  Absorb Software Inc ') == 'absorb software inc'
    assert vi.key(None) == ''


def test_the_legacy_expiring_endpoint_agrees_with_its_own_total():
    """⚠ A CORRECTION TO #244. That PR put /oce/digital-reform/expiring on the
    queue's scope so it could not be "a second answer to the same question", and left
    its duplicating join in place — while its own count query has no join. So the
    endpoint disagreed with the page AND with its own `total`.
    """
    src = open(os.path.join(API, 'routers/oce.py'), encoding='utf-8').read()
    m = re.search(r'(?m)^async def get_expiring_digital_contracts\(', src)
    assert m, "the legacy expiring endpoint is gone — this guard scans nothing"
    nxt = re.search(r'(?m)^(?:@router|async def |def )', src[m.end():])
    body = src[m.start():m.end() + (nxt.start() if nxt else len(src))]
    assert len(body.split('\n')) > 40, "the endpoint body extraction broke"
    code = _strip_py_comments(body)
    assert 'JOIN vendors' not in code, \
        "the legacy expiring endpoint joins `vendors` by name again — its paginated " \
        "rows would hold a duplicate while its count query does not"
    assert 'vendorids.unique_map(' in code, "it no longer resolves ids through the map"
    # Paginated with OFFSET, so the order must be total.
    assert 'c.contract_id ASC' in code, \
        "the paginated legacy endpoint lost its ordering tiebreak — tied end_dates " \
        "can swap between pages and show one contract twice"
