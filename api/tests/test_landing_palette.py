"""Guards for the landing-page harmonisation.

The landing was taken onto the token palette in the same wave that put a RATCHET on
`style.css` (see test_css_palette.py). It has no ratchet because it went to zero in one
pass: these assert it stays there, and that the band stays scoped.

⚠ The palette is parsed from token DECLARATIONS, never from the file's text —
`databook-tokens.css` records the values it replaced in comments, so a naive hex scan
reads historical values as current palette.
"""
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
TOKENS = os.path.join(ROOT, 'app/public/css/databook-tokens.css')
VIEW = os.path.join(ROOT, 'app/resources/views/root.blade.php')


def _norm(h):
    h = h.lower()
    return '#' + ''.join(c * 2 for c in h[1:]) if len(h) == 4 else h


def _palette():
    src = open(TOKENS, encoding='utf-8').read()
    decl = re.findall(r'(--db-[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8})\s*;', src)
    assert len(decl) > 30, f"only {len(decl)} token declarations parsed -- vacuous"
    return {_norm(v) for _, v in decl}


def _off_palette(css):
    palette = _palette()
    return [h for h in re.findall(r'#[0-9a-fA-F]{3,8}\b', css) if _norm(h) not in palette]


def test_the_landing_page_stays_on_palette():
    """The landing was harmonised in the same wave and has no ratchet: it must stay at
    zero. ⚠ The nine `.badge-*` section colours are excluded BY SELECTOR — they are a
    categorical palette (one hue per briefing section, the job DBChart.palette does for
    charts), not drift."""
    view = open(VIEW,
                encoding='utf-8').read()
    block = view[view.index('<style>'):view.index('</style>')]
    badges = block[block.index('.badge-hearing'):block.index('/* Scrollbar */')]
    scanned = block.replace(badges, '')
    assert len(scanned) > 2_000, "the landing style block looks empty -- scan is vacuous"
    off = _off_palette(scanned)
    assert not off, f"the landing style block regressed to literals: {sorted(set(off))}"
    # …and its inline style= attributes, which no <style> scan can see. 24 stat-tile
    # labels carried Bootstrap's #6c757d and were invisible to the handoff's grep.
    inline = ' '.join(re.findall(r'style="[^"]*"', view))
    off_inline = _off_palette(inline)
    assert not off_inline, f"inline style= attributes regressed: {sorted(set(off_inline))}"


def test_the_landing_band_is_scoped_and_cannot_repaint_the_site():
    """⚠⚠ THE ONE THAT MATTERS. The approved treatment styled `.inner_container`, which
    93 views use. Scoping is the whole reason this shipped as landing-only."""
    view = open(VIEW,
                encoding='utf-8').read()
    block = view[view.index('<style>'):view.index('</style>')]
    for rule in re.findall(r'(?m)^\s*([^@{}\n]+)\{', block):
        sel = rule.strip()
        assert not re.match(r'^\.inner_container\s*[,{]?\s*$', sel), (
            "the landing styles `.inner_container` again -- that selector is in 93 "
            "views and would repaint the whole site")
    assert '.db-home' in block, "the landing scope class is gone"
    assert 'inner_container db-home' in view, "the scope class is no longer on the div"
