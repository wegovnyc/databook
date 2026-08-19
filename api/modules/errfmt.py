"""Format a caught exception so the log line is never empty.

WHY THIS EXISTS
---------------
`print(f"[scheduler] Socrata meta {socrata_id} error: {e}")` produced, in
production:

    [scheduler] Socrata meta duz4-2gn9 error:
    [briefing] council hearings error:

…because **several of the most common exceptions stringify to the empty string**:

    str(asyncio.TimeoutError())  == ''      <- aiohttp's ClientTimeout raises this
    str(TimeoutError())          == ''
    str(socket.timeout())        == ''
    str(KeyError())              == ''
    str(Exception())             == ''

So the failure that matters most for an unattended job — *it timed out* — is
exactly the one that logs nothing at all. An error line with no message is
indistinguishable from a line nobody can diagnose, which is the same class as the
permanently-red monitor and the crosswalk failure that logged `FAIL:` with no
traceback above it: the alert fires and tells you nothing.

`exc_str()` always includes the exception TYPE, so the output cannot be empty:

    exc_str(asyncio.TimeoutError())        -> 'TimeoutError'
    exc_str(ValueError("bad row"))         -> 'ValueError: bad row'
    exc_str(KeyError("pwd"))               -> "KeyError: 'pwd'"

⚠ Use this in any `except` handler whose message is a plain `{e}`. It is not a
substitute for a traceback — where a stack matters, use `logger.exception(...)`,
which records both.
"""
from __future__ import annotations


def exc_str(e: BaseException) -> str:
    """`TypeName: message`, or just `TypeName` when the message is empty.

    ⚠ KeyError is why this uses `str(e)` rather than `e.args`: `str(KeyError('pwd'))`
    is `"'pwd'"` (quoted, which is the useful form), while `e.args[0]` would drop the
    quoting that tells you it was a missing key rather than a value.
    """
    name = type(e).__name__
    try:
        msg = str(e).strip()
    except Exception:  # a __str__ that itself raises must not break logging
        return name
    return f"{name}: {msg}" if msg else name
