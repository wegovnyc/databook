"""An error log line must never be empty.

Production produced these, for weeks:

    [scheduler] Socrata meta duz4-2gn9 error:
    [briefing] council hearings error:

because `str()` on several of the commonest exceptions is the empty string — and
the most important one for an unattended job, a timeout, is among them. So the
failure you most need to see logs nothing at all.
"""
import asyncio
import os
import re
import socket
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
API_DIR = os.path.realpath(os.path.join(HERE, ".."))
sys.path.insert(0, API_DIR)

from modules.errfmt import exc_str  # noqa: E402

import glob

# The always-running files: what someone actually reads during an incident.
GUARDED = [
    "data_scheduler.py",
    "main.py",
    "mcp_server.py",
    "chatbot.py",
    os.path.join("routers", "data_pipeline.py"),
    os.path.join("routers", "oce.py"),
]

# ⚠ extractors/ and scripts/ are guarded as GLOBS, not a fixed list. They run
# UNATTENDED — the weekly Checkbook refreshes at 02:00 Sunday, in an isolated
# container nobody is watching — and Checkbook is documented to return HTTP 200
# with truncated bodies under load and transient 403 cooldowns, i.e. exactly the
# conditions that raise timeouts and parse errors mid-pagination. A blank
# `[spending] error at offset 240000:` is the worst possible record of that.
#
# Globbed deliberately: a NEW extractor is the most likely place for this bug to
# reappear, and an explicit list would not cover a file that does not exist yet.
GUARDED += [
    os.path.relpath(p, API_DIR)
    for pat in ("extractors/*.py", "scripts/*.py")
    for p in sorted(glob.glob(os.path.join(API_DIR, pat)))
]

# Matches a log/print call interpolating the bare caught exception.
BARE_E = re.compile(r'(print|logger\.(error|warning|info|debug))\(f?"[^"]*\{e\}')


def test_exceptions_that_stringify_to_nothing_still_produce_a_message():
    """These are the ones that caused the empty lines. Each must name its type."""
    for exc in (
        asyncio.TimeoutError(),
        TimeoutError(),
        socket.timeout(),
        KeyError(),
        Exception(),
    ):
        out = exc_str(exc)
        assert out, f"{type(exc).__name__} produced an empty message"
        assert out == type(exc).__name__, out


def test_a_message_is_kept_and_prefixed_with_the_type():
    assert exc_str(ValueError("bad row")) == "ValueError: bad row"
    # KeyError's str() keeps the quoting, which is what tells you it was a missing
    # key rather than a value — hence str(e), not e.args[0].
    assert exc_str(KeyError("pwd")) == "KeyError: 'pwd'"


def test_whitespace_only_messages_count_as_empty():
    assert exc_str(RuntimeError("   \n ")) == "RuntimeError"


def test_a_broken_dunder_str_cannot_break_logging():
    class Hostile(Exception):
        def __str__(self):
            raise RuntimeError("nope")

    assert exc_str(Hostile()) == "Hostile"


def test_output_is_never_empty_for_any_builtin_exception():
    import builtins

    checked = 0
    for name in dir(builtins):
        obj = getattr(builtins, name)
        if isinstance(obj, type) and issubclass(obj, BaseException):
            try:
                inst = obj()
            except Exception:
                continue
            assert exc_str(inst), name
            checked += 1
    # ⚠ Assert it looked: a loop that inspects nothing passes silently.
    assert checked > 20, f"only inspected {checked} builtin exceptions"


# --- the guard ---------------------------------------------------------------------

def test_the_always_running_files_never_log_a_bare_exception():
    """⚠ This is the test that matters. Asserting exc_str() behaves cannot see a new
    `except Exception as e: print(f"... {e}")` added tomorrow — and that is exactly
    how the empty lines got there. So scan for the banned PATTERN instead.

    Same shape and same caveat as the orgfilter (#177) and dbcreds (#190) guards:
    strip comments first, or the comment explaining the rule satisfies the rule.
    """
    offenders, scanned = [], 0
    for rel in GUARDED:
        path = os.path.join(API_DIR, rel)
        assert os.path.exists(path), f"guarded file moved or renamed: {rel}"
        src = open(path, encoding="utf-8").read()
        src = re.sub(r'""".*?"""', "", src, flags=re.S)
        src = re.sub(r"'''.*?'''", "", src, flags=re.S)
        for i, line in enumerate(src.splitlines(), 1):
            code = line.split("#", 1)[0]
            scanned += 1
            if BARE_E.search(code):
                offenders.append(f"{rel}:{i}: {code.strip()[:88]}")

    # ⚠ ASSERT IT LOOKED. A tree-walking guard that matches nothing passes
    # unconditionally and is indistinguishable from one that never ran — how the
    # ?api_key= scanner vacuumed itself in #192.
    assert scanned > 5000, f"guard only scanned {scanned} lines; did the paths break?"
    assert not offenders, (
        "these log calls interpolate the bare exception, which prints NOTHING for a "
        "timeout (str(TimeoutError()) == ''). Use exc_str(e) from modules.errfmt:\n  "
        + "\n  ".join(offenders)
    )
