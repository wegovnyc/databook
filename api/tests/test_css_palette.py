"""A RATCHET on colour drift in the site's CSS.

⚠ WHY A RATCHET AND NOT A ONE-TIME CLEANUP. `app/public/css/style.css` accumulated 51
distinct off-palette colours over years — Bootstrap greys, Tailwind slates, ad-hoc
blues — beside a fully tokenized design system. A cleanup fixes that once; this repo's
own history says the snapshot is what fails ("an exclusion list is a snapshot; new
files land in old categories"). So the count is PINNED and may only go down: the
cleanup can land in reviewable batches, each lowering the ceiling, and when it reaches
zero this becomes the permanent "no new drift" invariant with no further work.

⚠ THE PALETTE IS PARSED FROM DECLARATIONS, NOT FROM THE FILE'S TEXT. `databook-tokens.css`
documents the values it replaced in comments — `--db-gray-100: #f0f2f4;  /* was #f0f0f0 */`
— so a naive hex scan of that file reads HISTORICAL values as current palette. I made
exactly that mistake while sizing this work and reported `#f0f0f0` and `#4299e1` as
"already token values"; they are drift, and the handoff had them right.

⚠ 3-DIGIT SHORTHAND COUNTS. The handoff's proposed check was
`grep -oE '#[0-9a-fA-F]{6}'`, which cannot see `#fff` (32 occurrences) or `#000` (13).
A check that cannot see half the problem is the guard-that-scanned-zero-files pattern.
"""
import os
import re
from collections import Counter

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
TOKENS = os.path.join(ROOT, 'app/public/css/databook-tokens.css')
STYLE = os.path.join(ROOT, 'app/public/css/style.css')

# The ratchet. Lower these as batches land; never raise them.
# ⚠ ZERO. The ratchet has reached its floor, so this is no longer "drift may only
# shrink" — it is "no literal colour in style.css, full stop". 99 -> 60 (the 39
# near-identical values) -> 16 (deleting 78 fossil rule blocks whose selectors cannot
# match) -> 0 (the 16 that genuinely render).
MAX_OFF_PALETTE_HEX = 0
MIN_TOKEN_REFERENCES = 134        # var(--db-*) uses, so a swap cannot be undone.
                                  # Fell 143 -> 118 deleting the fossil rules
                                  # (they used tokens too), then rose to 134.


def _norm(h):
    h = h.lower()
    return '#' + ''.join(c * 2 for c in h[1:]) if len(h) == 4 else h


def _palette():
    """Every colour a token actually declares."""
    src = open(TOKENS, encoding='utf-8').read()
    decl = re.findall(r'(--db-[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8})\s*;', src)
    assert len(decl) > 30, f"only {len(decl)} token declarations parsed -- palette is vacuous"
    palette = {_norm(v) for _, v in decl}
    # ⚠⚠ A TOO-WIDE PALETTE DEFEATS THE RATCHET SILENTLY, and an empty one does not:
    # widening makes drift count as compliant, so the count falls and every assertion
    # passes. Found by mutation — pointing this parser at every hex in the file (the
    # mistake I made by hand) was NOT caught until this check existed. These three
    # values appear ONLY in the token file's "(was #…)" comments, so their presence
    # proves the parser has started reading prose as palette.
    for historical in ('#f0f0f0', '#f9f9f9', '#1a3a5c'):
        assert historical in src, f"{historical} is no longer in the token comments -- pick another canary"
        assert historical not in palette, (
            f"the palette parser is reading the token file's COMMENTS: {historical} is a "
            f"historical value, not a declaration. That silently widens the palette and "
            f"makes the drift ratchet vacuous.")
    return palette


def _strip_css_comments(css):
    """⚠ A COMMENT IS NOT A PAINTED COLOUR, and this guard fired on its own prose the
    moment style.css gained a comment quoting the values it had removed — the same
    trap as reading the token file's "(was #f0f0f0)" notes as palette. Strip first."""
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


def _off_palette(css):
    palette = _palette()
    return [h for h in re.findall(r'#[0-9a-fA-F]{3,8}\b', _strip_css_comments(css))
            if _norm(h) not in palette]


def test_the_ratchet_states_what_it_does_not_cover():
    """⚠ ZERO HEX IS NOT ZERO LITERALS, and claiming otherwise would be the kind of
    reassuring measurement this repo keeps paying for. Still in style.css and NOT
    counted: 15 named colours (`white`, `red`, `green`, `orange`) and 41 rgb()/rgba()
    values — most of the latter are alpha overlays that no hex token can express, which
    is why they were left rather than forced onto the palette. This test exists so the
    limit is written down beside the ceiling, not discovered later.
    """
    css = _strip_css_comments(open(STYLE, encoding='utf-8').read())
    named = re.findall(r'(?<![-\w#])(white|black|red|blue|green|orange)\b(?!\s*[-\w])', css, re.I)
    rgba = re.findall(r'\brgba?\([^)]*\)', css)
    assert len(named) <= 15, (
        f"named colour literals grew to {len(named)} from 15 -- the hex ratchet does "
        f"not see these, so they need their own decision, not silent growth")
    assert len(rgba) <= 41, f"rgb()/rgba() literals grew to {len(rgba)} from 41"


def test_colour_drift_in_style_css_only_ever_goes_down():
    css = open(STYLE, encoding='utf-8').read()
    assert len(css) > 10_000, "style.css looks truncated -- the scan would be vacuous"
    off = _off_palette(css)
    assert len(off) <= MAX_OFF_PALETTE_HEX, (
        f"colour drift went UP: {len(off)} off-palette literals against a ceiling of "
        f"{MAX_OFF_PALETTE_HEX}. Use a token from databook-tokens.css, or lower the "
        f"ceiling in the same commit if you are fixing drift. Most common now: "
        f"{Counter(_norm(h) for h in off).most_common(5)}")


def test_the_mechanical_token_swap_cannot_be_undone():
    """101 literals that were provably identical to a token became `var()` references.
    Swapping any back would not raise the off-palette count (they are ON palette), so
    the ratchet above cannot see it — this floor can."""
    css = open(STYLE, encoding='utf-8').read()
    refs = len(re.findall(r'var\(--db-', _strip_css_comments(css)))
    assert refs >= MIN_TOKEN_REFERENCES, (
        f"token references dropped to {refs} from {MIN_TOKEN_REFERENCES} -- a var() "
        f"was replaced with a literal")


def test_the_ceiling_is_zero_so_the_ratchet_cannot_go_slack():
    """⚠ A ceiling above the real count is a ratchet that has stopped ratcheting: drift
    could double and still pass. It is now 0, which is the only value that needs no
    maintenance — every literal is a failure, so there is nothing to keep in step."""
    assert MAX_OFF_PALETTE_HEX == 0, (
        "the ceiling was raised. Colour drift in style.css reached zero on 2026-08-14; "
        "raising it re-opens the door instead of using a token.")
    assert not _off_palette(open(STYLE, encoding='utf-8').read())


def test_style_css_never_redeclares_a_design_token():
    """⚠⚠ A SECOND DECLARATION SITE, one layer down from the ones this repo fixed in
    the API today. `style.css` opened with a `:root` block redeclaring 15 `--db-*`
    tokens, NINE of them with the same name and a different value — its own
    `--db-shadow-sm: rgba(0,0,0,0.05)` against the canonical `rgba(11,31,58,0.06)`,
    `--db-transition: 0.2s` against `0.18s`.

    Every one was dead: `databook-tokens.css` loads later and won every collision,
    measured on the live site. Dead and WRONG is worse than duplicated — anyone
    reading style.css saw values the site does not use. The canonical file is the only
    place a token may be declared.
    """
    css = open(STYLE, encoding='utf-8').read()
    decls = re.findall(r'(?m)^\s*(--db-[a-z0-9-]+)\s*:', css)
    assert not decls, (
        f"style.css declares design tokens again: {sorted(set(decls))}. Tokens live in "
        f"databook-tokens.css; this file may only reference them with var().")
    # …and it must still be USING them, or "no declarations" is trivially satisfied by
    # a file that went back to literals.
    assert len(re.findall(r'var\(--db-', _strip_css_comments(css))) >= MIN_TOKEN_REFERENCES
