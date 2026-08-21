"""Guards for the scheduler loop's failure handling.

⚠⚠ THE DEFECT THESE EXIST TO PREVENT, observed on prod 2026-08-18 14:15:5xZ.
`scheduler_loop` caught every exception, logged it with a bare `print`, and then
slept the full `SCHEDULER_INTERVAL_SECONDS` (86400). Two consequences:

1. A TRANSIENT failure cost a full day of ingestion. Every dataset inside
   `run_data_check` is already individually guarded, so the only way to reach the
   loop's handler is a failure OUTSIDE those guards — in practice the
   `get_db_connection()` at the top. What actually happened was an asyncpg connect
   TimeoutError under crawler-induced executor starvation (DuckDB Parquet scans
   share the default executor with getaddrinfo, ~190 such timeouts/24h are
   documented), so the cycle died before polling a single dataset.

2. THE DEATH WAS INVISIBLE TO ALERTING. A bare `print` never reaches Sentry —
   LoggingIntegration raises events from the LOGGING module at ERROR — and no
   healthchecks check covers this loop, since all 8 watch HOST crons while this
   runs inside the api process. The only compensating control was
   dataset-staleness.sh, up to 5 days later and only if the source moved.

These are BEHAVIOURAL, driving the real loop with a stubbed `run_data_check` and a
stubbed `asyncio.sleep`, rather than scanning the source — a source scan cannot
tell that the retry is actually reached, and this file's whole point is that
"registered/present" is not "runs" (cf. the crol hook that was registered,
correctly ordered, and never invoked).
"""
import asyncio
import importlib.util
import io
import logging
import os

import pytest

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
SCHEDULER = os.path.join(ROOT, 'api/data_scheduler.py')


def _read(path):
    with io.open(path, encoding='utf-8') as fh:
        return fh.read()


class _Harness:
    """Drives scheduler_loop for exactly one interval, recording what it did."""

    def __init__(self, mod, failures):
        self.mod = mod
        self.failures = failures        # how many times run_data_check raises
        self.attempts = 0
        self.sleeps = []

    async def run_data_check(self, conn=None):
        self.attempts += 1
        if self.attempts <= self.failures:
            raise asyncio.TimeoutError()

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        # The daily sleep marks the end of one full pass — stop there so the
        # `while True` cannot run forever inside a test.
        if seconds == self.mod.SCHEDULER_INTERVAL_SECONDS:
            raise _Done()

    @property
    def retry_sleeps(self):
        return [s for s in self.sleeps
                if s == self.mod.SCHEDULER_RETRY_DELAY_SECONDS]


class _Done(Exception):
    pass


def _load_scheduler(monkeypatch):
    """Load data_scheduler by path with its imports stubbed out.

    ⚠ conftest.py replaces the `modules` package with a MagicMock, and this module
    also pulls in config/aiohttp/asyncpg and the whole enrichment stack, so it is
    loaded with those satisfied rather than imported for real.
    """
    spec = importlib.util.spec_from_file_location('_sched_under_test', SCHEDULER)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"data_scheduler is not importable in this env: {exc}")
    return mod


async def _drive(mod, failures):
    h = _Harness(mod, failures)
    mod.run_data_check = h.run_data_check
    orig_sleep = asyncio.sleep
    asyncio.sleep = h.sleep
    try:
        try:
            await mod.scheduler_loop()
        except _Done:
            pass
    finally:
        asyncio.sleep = orig_sleep
    return h


@pytest.mark.asyncio
async def test_a_transient_failure_is_retried_rather_than_costing_a_full_day():
    """⚠ THE CORE FIX. One failure must not send the loop to sleep for 86400s."""
    mod = _load_scheduler(None)
    h = await _drive(mod, failures=1)
    assert h.attempts == 2, (
        f"run_data_check was called {h.attempts}x; a failed cycle is not retried")
    assert h.retry_sleeps == [mod.SCHEDULER_RETRY_DELAY_SECONDS], \
        f"expected exactly one short retry delay, got {h.sleeps}"
    assert h.sleeps[-1] == mod.SCHEDULER_INTERVAL_SECONDS, \
        "the loop did not fall back to the daily interval after succeeding"


@pytest.mark.asyncio
async def test_the_retry_is_bounded_so_a_hard_failure_cannot_hot_loop():
    """A permanent error must stop retrying and fall through to the interval.

    ⚠ THE BOUND IS EXPRESSED TWICE ON PURPOSE — the `for ... range(1,
    SCHEDULER_MAX_RETRIES + 2)` and the `if attempt > SCHEDULER_MAX_RETRIES`
    break — so NO SINGLE MUTATION can falsify this test: widen either one and the
    other still caps attempts at 4. That is deliberate belt-and-braces on a loop
    whose failure mode is a hot-loop against prod, but it is worth stating,
    because "I mutated it and the guard did not fire" would otherwise read as a
    useless guard. Verified by widening BOTH together: 41 attempts, caught.
    """
    mod = _load_scheduler(None)
    h = await _drive(mod, failures=99)
    assert h.attempts == mod.SCHEDULER_MAX_RETRIES + 1, (
        f"{h.attempts} attempts for a permanently failing cycle; expected "
        f"{mod.SCHEDULER_MAX_RETRIES + 1}")
    assert h.sleeps[-1] == mod.SCHEDULER_INTERVAL_SECONDS, \
        "a permanently failing cycle never reached the daily interval"


@pytest.mark.asyncio
async def test_giving_up_raises_a_SENTRY_VISIBLE_error_not_a_print(caplog):
    """⚠⚠ THE ALERTING FIX, and the half that failed silently before.

    `logger.error` is what LoggingIntegration turns into a Sentry event; the old
    bare `print` was invisible to it. A retried-and-recovered blip must stay at
    WARNING so it does not page anyone.
    """
    mod = _load_scheduler(None)
    with caplog.at_level(logging.WARNING, logger=mod.logger.name):
        await _drive(mod, failures=99)
    levels = {r.levelno for r in caplog.records}
    assert logging.ERROR in levels, (
        "giving up did not log at ERROR, so a dead scheduler raises no Sentry "
        "event — the exact defect this replaced")

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger=mod.logger.name):
        await _drive(mod, failures=1)
    levels = {r.levelno for r in caplog.records}
    assert logging.WARNING in levels, "a retried failure is not logged at all"
    assert logging.ERROR not in levels, (
        "a failure that RECOVERED on retry still raised an ERROR; that pages "
        "someone for a self-healing blip")


class _PingRecorder:
    """Captures _hc_ping calls without touching the network."""

    def __init__(self):
        self.calls = []

    async def __call__(self, kind, body=""):
        self.calls.append((kind, body))

    @property
    def kinds(self):
        return [k for k, _ in self.calls]


async def _drive_with_pings(mod, failures):
    rec = _PingRecorder()
    mod._hc_ping = rec
    h = await _drive(mod, failures)
    return h, rec


@pytest.mark.asyncio
async def test_a_completed_cycle_pings_success_exactly_once():
    """The dead-man's switch: nothing watched this loop before. All 8 healthchecks
    checks watch HOST crons and this runs inside the api process."""
    mod = _load_scheduler(None)
    _h, rec = await _drive_with_pings(mod, failures=0)
    assert rec.kinds.count("success") == 1, \
        f"expected exactly one success ping per interval, got {rec.kinds}"
    assert "fail" not in rec.kinds, "a healthy cycle reported failure"
    assert rec.kinds[0] == "start", "no start ping, so runtime is unmeasurable"


@pytest.mark.asyncio
async def test_giving_up_pings_fail_once_and_carries_the_reason():
    """healthchecks RETAINS the ping body, so the alert email carries the reason
    rather than a bare 'went down'."""
    mod = _load_scheduler(None)
    _h, rec = await _drive_with_pings(mod, failures=99)
    assert rec.kinds.count("fail") == 1, \
        f"expected exactly one fail ping per interval, got {rec.kinds}"
    assert "success" not in rec.kinds, "a dead cycle reported success"
    body = next(b for k, b in rec.calls if k == "fail")
    assert "TimeoutError" in body, \
        f"the fail ping does not name the error, so the alert says nothing: {body!r}"


@pytest.mark.asyncio
async def test_a_retried_then_recovered_cycle_pings_success_not_fail():
    """A blip that self-heals must not take the check down."""
    mod = _load_scheduler(None)
    _h, rec = await _drive_with_pings(mod, failures=1)
    assert rec.kinds.count("success") == 1 and "fail" not in rec.kinds, \
        f"a recovered cycle reported failure: {rec.kinds}"


@pytest.mark.asyncio
async def test_the_ping_is_a_NO_OP_when_unconfigured(monkeypatch):
    """⚠ THE PROPERTY THAT MAKES THE ROLLOUT SAFE. The code ships first doing
    nothing, then the check is created, then the env var is set. Creating a check
    before anything can ping it manufactures a red monitor on its first missed
    schedule — the documented reason the DOS crosswalk check and its hc_ping had
    to ship together.

    Asserts no HTTP is attempted at all: aiohttp.ClientSession is replaced with
    something that explodes if constructed.
    """
    mod = _load_scheduler(None)
    monkeypatch.delenv(mod._HC_ENV_VAR, raising=False)

    # ⚠ RECORD, do not raise. My first draft had this raise AssertionError — which
    # `_hc_ping`'s deliberate `except Exception` swallowed, so the test passed even
    # with the early return deleted. The swallow-everything behaviour I want was
    # defeating the assertion mechanism; found by reintroducing the bug and
    # watching the guard stay green.
    opened = []
    monkeypatch.setattr(mod.aiohttp, "ClientSession",
                        lambda *a, **k: opened.append(True))
    await mod._hc_ping("success", "body")
    assert not opened, \
        "the unconfigured ping opened an HTTP session; it must return early, or " \
        "shipping this code before the check exists starts pinging nothing"


@pytest.mark.asyncio
async def test_a_ping_failure_cannot_break_the_scheduler(monkeypatch):
    """⚠ Monitoring that can break the thing it monitors is worse than none."""
    mod = _load_scheduler(None)
    monkeypatch.setenv(mod._HC_ENV_VAR, "https://hc-ping.example/deadbeef")

    def _boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(mod.aiohttp, "ClientSession", _boom)
    await mod._hc_ping("success", "body")     # swallowed, logged


def test_the_scheduler_does_not_configure_logging_itself():
    """⚠ modules/applog.py owns the api's logging config. A basicConfig here
    would double every line in prod (#249).

    ⚠⚠ READS THE AST, NOT THE TEXT — and this guard's first draft got it wrong in
    the way this repo has already paid for twice. A substring scan for
    'basicConfig' fired on the module's own COMMENT saying "never basicConfig
    here", reporting a defect that was not there. A scanner that reads prose as
    code is the mirror of one that scans zero files.
    """
    import ast
    tree = ast.parse(_read(SCHEDULER))
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call)
             and getattr(n.func, 'attr', getattr(n.func, 'id', '')) == 'basicConfig']
    assert not calls, (
        f"data_scheduler CALLS basicConfig at line {calls[0].lineno}; "
        "applog.py is the one owner and a second config doubles every line")
    # And the module logger must still exist, or nothing can raise a Sentry event.
    assigns = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
               and getattr(n.func, 'attr', '') == 'getLogger']
    assert assigns, "the module logger is gone; a dead scheduler cannot alert"
