"""Databook's tokens and the shared package cannot silently diverge.

⚠⚠ WHY THIS IS A PARITY CHECK AND NOT AN ADOPTION. `sarapis/wegovnyc-design-tokens`
harvested its reference tier FROM `app/public/css/databook-tokens.css` — which is why
the package's raw values still carry the `--db-*` prefix — and Databook does NOT import
the package. Both files therefore claim the same reference values, and **nothing checked
that claim**. Measured 2026-08-14 before writing this: 73 of the 79 shared names were
already identical and the other 6 differed only in formatting. So the guarantee the
owner asked for ("unify the properties on one token system") is obtainable here for the
price of a comparison, with no build step, no git dependency, and no change to anything
prod serves.

⚠ The comparison is against a VENDORED SNAPSHOT
(`app/resources/design-tokens/wegovnyc-core.snapshot.css`), not a network fetch: a unit
test that reaches GitHub is flaky in CI and unavailable in a sandbox. The snapshot is
refreshed by `.github/workflows/token-parity-check.yml`, which fetches the package
monthly and opens an issue when it has moved — the same shape as this repo's existing
public-snapshot drift check.

⚠ FORMATTING IS NOT A VALUE. The package writes `.06` where Databook writes `0.06`, and
omits the space after commas in font stacks. Comparing raw strings would report six
divergences that do not exist, so values are normalised before comparison — and the
normaliser is itself pinned below, because a normaliser that flattens too much would
make this whole file vacuous.
"""
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATABOOK = os.path.join(ROOT, 'app/public/css/databook-tokens.css')
SNAPSHOT = os.path.join(ROOT, 'app/resources/design-tokens/wegovnyc-core.snapshot.css')

# Names Databook declares that the package's reference tier does not carry. Pinned, so
# that a value moving OUT of parity shows up as a change here rather than as silence.
DATABOOK_ONLY = 32


def _decls(path):
    src = open(path, encoding='utf-8').read()
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)   # a comment is not a declaration
    out = dict(re.findall(r'(--[a-z0-9-]+)\s*:\s*([^;}]+);', src))
    assert len(out) > 60, f"only {len(out)} declarations parsed from {path} -- vacuous"
    return out


def _norm(v):
    """Compare VALUES, not their spelling.

    ⚠ Deliberately narrow: lowercase, collapse whitespace, drop the space after a
    comma, and restore a leading zero on a bare decimal (`.06` -> `0.06`). It must NOT
    do anything cleverer — normalising colours to a common form, say, would let a real
    divergence pass as a formatting difference, which is the failure mode that matters.
    """
    v = ' '.join(v.lower().split())
    v = v.replace(', ', ',')
    return re.sub(r'(?<![\d.])\.(\d)', r'0.\1', v)


def test_the_normaliser_hides_formatting_and_nothing_else():
    """Pin it in both directions, or the parity test below can be defeated by making
    the normaliser more generous."""
    assert _norm('0.18s ease') == _norm('.18s  EASE')
    assert _norm("'Public Sans', 'Inter'") == _norm("'public sans','inter'")
    assert _norm('rgba(11,31,58,0.06)') == _norm('rgba(11,31,58,.06)')
    # …and these must stay DIFFERENT.
    assert _norm('#162e51') != _norm('#162e52')
    assert _norm('0 1px 2px rgba(11,31,58,0.06)') != _norm('0 1px 3px rgba(11,31,58,0.06)')
    assert _norm('8px') != _norm('9px')
    assert _norm('var(--db-gray-900)') != _norm('#171717'), \
        "the normaliser must not resolve var() -- that would hide a semantic change"


def test_every_shared_token_has_the_same_value_in_both_files():
    """⚠ THE POINT OF THE FILE. If a value moves in either place, this fails and whoever
    moved it has to move the other one (or update the snapshot deliberately). That is
    the whole unification guarantee, and it costs one comparison."""
    db, pkg = _decls(DATABOOK), _decls(SNAPSHOT)
    shared = sorted(set(db) & set(pkg))
    assert len(shared) > 70, f"only {len(shared)} shared names -- has a prefix changed?"
    bad = [(k, db[k].strip(), pkg[k].strip()) for k in shared if _norm(db[k]) != _norm(pkg[k])]
    assert not bad, (
        "Databook's tokens and the shared package have diverged:\n" +
        "\n".join(f"    {k}\n      databook: {a}\n      package : {b}" for k, a, b in bad) +
        "\n  Fix whichever is wrong, in BOTH places. If the package moved on purpose, "
        "refresh app/resources/design-tokens/wegovnyc-core.snapshot.css via the "
        "token-parity-check workflow rather than by hand.")


def test_the_shape_of_the_overlap_is_pinned():
    """Parity on shared names is only half the guarantee: a token could drop out of the
    overlap entirely and every value comparison would still pass. Pin the counts."""
    db, pkg = _decls(DATABOOK), _decls(SNAPSHOT)
    db_only = sorted(k for k in db if k.startswith('--db-') and k not in pkg)
    pkg_only = sorted(k for k in pkg if k.startswith('--db-') and k not in db)
    assert not pkg_only, (
        f"the package declares reference tokens Databook does not: {pkg_only}. Either "
        f"Databook lost them or the package invented them — both are divergence.")
    assert len(db_only) == DATABOOK_ONLY, (
        f"Databook-only reference tokens went {DATABOOK_ONLY} -> {len(db_only)}. That is "
        f"not automatically wrong — Databook is the source of truth and may add tokens "
        f"first — but it must be a deliberate number, not a drift. Now: {db_only}")


def test_the_snapshot_records_where_it_came_from_and_is_not_hand_edited():
    """⚠ A snapshot with no provenance is indistinguishable from a file someone edited
    until the test passed."""
    src = open(SNAPSHOT, encoding='utf-8').read()
    m = re.search(r'source commit\s*:\s*([0-9a-f]{40})', src)
    assert m, "the snapshot no longer records the package commit it was captured from"
    assert 'NEVER served and NEVER imported' in src, \
        "the snapshot lost the note saying it is reference-only"
    assert 'Do NOT hand-edit' in src
    # It must still be the package's file, not a Databook copy: the package's own
    # header states the relationship, and its semantic tier is what Databook lacks.
    assert '--wg-' in src, \
        "the snapshot has no --wg-* semantic tier -- that is not the package's core.css"


def test_databook_does_not_import_the_package():
    """⚠ Step 4 is a CHECK, not adoption. Consumption is a separate decision (the
    package is still moving — v0.6.0 to v0.7.0 inside a week), and this guard exists so
    the parity check cannot quietly become a build dependency."""
    for rel in ('app/resources/views/layout.blade.php', 'app/public/css/databook-tokens.css'):
        body = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        assert 'wegovnyc-design-tokens' not in body and 'variant-' not in body, (
            f"{rel} now references the package. If adopting it is the intent, that is a "
            f"deliberate change with a deploy story — not something this parity check "
            f"should be read as having approved.")
    # And the snapshot must not be inside the web root, where it would be served.
    assert not os.path.exists(os.path.join(ROOT, 'app/public/css/wegovnyc-core.snapshot.css'))
