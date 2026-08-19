"""A response built from a COLD contract spend map must never be cached.

`_get_contract_spend_map()` is deliberately non-blocking: for ~1 minute after every
api restart (including the daily 04:00 cron) it returns `{}` while a background scan
runs, and callers render nothing rather than a false $0. That is right for a live
request and wrong to store — the Cloudflare edge TTL would pin an empty spend
section for the whole TTL, so a routine restart could blank the figures on every
contract page for 10 minutes.

⚠ The guard at the bottom is the important test. Asserting that the helper behaves
is easy and nearly worthless on its own: it cannot see a NEW endpoint that reads the
spend map and forgets the header. That is the same shape as the `orgfilter` miss
(#177), where a test asserted the constant held the right values while a filter that
ignored the constant emptied a whole page. So this scans for the *pattern* instead,
and asserts it actually looked at something.
"""
import os
import re

import pytest

HERE = os.path.dirname(os.path.realpath(__file__))
API_DIR = os.path.realpath(os.path.join(HERE, ".."))
OCE_PATH = os.path.join(API_DIR, "routers", "oce.py")
MAIN_PATH = os.path.join(API_DIR, "main.py")


class _Resp:
    """Minimal stand-in for the header bag on fastapi's Response."""

    def __init__(self):
        self.headers = {}


def _helper():
    import sys
    sys.path.insert(0, API_DIR)
    from routers.oce import _spend_cache_headers  # noqa: E402
    return _spend_cache_headers


def test_a_cold_map_is_not_stored():
    r = _Resp()
    _helper()(r, {})
    assert r.headers["Cache-Control"] == "no-store", (
        "an empty spend map means the payload is correct but INCOMPLETE; storing it "
        "pins an empty spend section for the whole edge TTL"
    )


def test_a_warm_map_is_cacheable():
    r = _Resp()
    _helper()(r, {"CT100220191425144": {"spent_to_date": 1.0}})
    cc = r.headers["Cache-Control"]
    assert cc.startswith("public, max-age="), cc
    assert int(cc.rsplit("=", 1)[1]) > 0


def test_falsy_but_present_map_still_counts_as_cold():
    # Defensive: `{}` is the documented cold value, and any other falsy map (None)
    # must behave the same rather than raising.
    for cold in ({}, None):
        r = _Resp()
        _helper()(r, cold)
        assert r.headers["Cache-Control"] == "no-store", cold


# --- the guard ---------------------------------------------------------------------

def _strip_comments_and_docstrings(src: str) -> str:
    """Comments explaining this rule must not satisfy the rule. Same caveat as the
    orgfilter and dbcreds guards."""
    src = re.sub(r'""".*?"""', "", src, flags=re.S)
    src = re.sub(r"'''.*?'''", "", src, flags=re.S)
    return "\n".join(l.split("#", 1)[0] for l in src.splitlines())


def _handler_bodies(src: str):
    """Yield (name, body) for each `async def` / `def` at module level."""
    lines = src.splitlines()
    starts = [
        (i, m.group(1))
        for i, l in enumerate(lines)
        if (m := re.match(r"^(?:async )?def (\w+)\(", l))
    ]
    for idx, (line_no, name) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        yield name, "\n".join(lines[line_no:end])


def test_every_spend_map_reader_sets_its_cache_headers():
    src = _strip_comments_and_docstrings(open(OCE_PATH, encoding="utf-8").read())
    readers, offenders = [], []
    for name, body in _handler_bodies(src):
        if "_get_contract_spend_map()" not in body:
            continue
        if name.startswith("_"):        # internal plumbing, not a response path
            continue
        readers.append(name)
        if "_spend_cache_headers" not in body:
            offenders.append(name)

    # ⚠ ASSERT IT LOOKED. A guard that walks a tree and silently matches nothing
    # passes unconditionally and is indistinguishable from one that never ran —
    # exactly how the ?api_key= scanner vacuumed itself in #192.
    assert len(readers) >= 4, (
        f"expected to find the known spend-map endpoints, found {readers!r}. "
        "If the endpoints were renamed, update this guard; do not delete it."
    )
    assert not offenders, (
        "these endpoints read the contract spend map but never set Cache-Control, so "
        f"a cold-map response would be cached at the edge: {offenders!r}. Call "
        "_spend_cache_headers(response, spend_map) after reading the map."
    )


def test_the_default_cache_header_is_applied_by_middleware_not_per_handler():
    """The middleware is what stops a NEW /oce/ endpoint dropping out of the cache by
    omission once the Cloudflare rule respects origin headers."""
    src = _strip_comments_and_docstrings(open(MAIN_PATH, encoding="utf-8").read())
    assert "CACHEABLE_API_PREFIXES" in src
    assert '"/oce/"' in src and '"/get/"' in src
    # Must not clobber a handler that opted out with no-store.
    assert "cache-control" in src, (
        "the middleware must skip responses that already set Cache-Control, or it "
        "would overwrite the no-store that protects a cold spend map"
    )
