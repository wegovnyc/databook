"""Guards the fix for the 2026-07-27 TimeoutError incident.

The bug was invisible in normal tests: every endpoint worked, Postgres was healthy,
and the only symptom was that blocking DuckDB scans and asyncpg's DNS resolution
competed for the SAME default ThreadPoolExecutor. These tests pin the invariant
directly — DuckDB work must run on its own named pool, and must never consume a
default-executor thread (which is what `loop.getaddrinfo()` needs).

See modules/duckpool.py for the full incident writeup.
"""

import asyncio
import re
import threading
from pathlib import Path

import pytest

from modules import duckpool


async def test_runs_on_dedicated_named_threads():
    """Work lands on a 'duckdb'-prefixed thread, not asyncio's default pool."""
    name = await duckpool.to_duckdb_thread(lambda: threading.current_thread().name)
    assert name.startswith("duckdb"), f"ran on {name!r}, expected the duckdb executor"
    # asyncio's default executor names its threads asyncio_%d.
    assert not name.startswith("asyncio"), "still on the default executor"


async def test_does_not_occupy_default_executor():
    """The regression that caused the incident.

    Saturating the DuckDB pool with blocking work must leave the loop's DEFAULT
    executor completely free — that is the pool getaddrinfo() runs on. If DuckDB
    work ever lands there again, a burst of lake scans will time out Postgres
    connects, exactly as it did on 2026-07-24 and 2026-07-27.
    """
    loop = asyncio.get_running_loop()
    release = threading.Event()
    started = threading.Barrier(duckpool.DUCKDB_MAX_WORKERS + 1, timeout=10)

    def blocker():
        started.wait()          # signal that every worker is occupied
        release.wait(timeout=10)  # then hold the thread
        return True

    tasks = [
        asyncio.create_task(duckpool.to_duckdb_thread(blocker))
        for _ in range(duckpool.DUCKDB_MAX_WORKERS)
    ]
    try:
        await asyncio.to_thread(started.wait)  # every duckdb worker is now blocked

        # With the DuckDB pool fully saturated, the default executor must still
        # serve work promptly. This is the stand-in for loop.getaddrinfo().
        got = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: "default-executor-free"), timeout=5
        )
        assert got == "default-executor-free"
    finally:
        release.set()
        await asyncio.gather(*tasks)


async def test_bounded_worker_count():
    """The pool must stay bounded — an unbounded pool would let a crawler run
    arbitrarily many full-lake scans and blow the CPU / DuckDB memory budget."""
    assert 1 <= duckpool.DUCKDB_MAX_WORKERS <= 12
    ran = await asyncio.gather(
        *(duckpool.to_duckdb_thread(lambda: threading.current_thread().name)
          for _ in range(duckpool.DUCKDB_MAX_WORKERS * 3))
    )
    assert len(set(ran)) <= duckpool.DUCKDB_MAX_WORKERS


async def test_propagates_exceptions_and_kwargs():
    """Behavioural parity with asyncio.to_thread for the call shapes in routers/."""
    assert await duckpool.to_duckdb_thread(lambda a, b=0: a + b, 1, b=2) == 3

    def boom():
        raise ValueError("duckdb query failed")

    with pytest.raises(ValueError, match="duckdb query failed"):
        await duckpool.to_duckdb_thread(boom)


async def test_propagates_contextvars():
    """Sentry attaches its scope via contextvars; asyncio.to_thread copies the
    context, so our replacement must too or errors raised inside DuckDB work lose
    their transaction context in Sentry."""
    import contextvars

    var = contextvars.ContextVar("probe")
    var.set("carried")
    assert await duckpool.to_duckdb_thread(var.get) == "carried"


def test_routers_use_the_dedicated_pool_for_duckdb():
    """No router may reach for asyncio.to_thread again — that is the bug.

    Comments/docstrings are allowed to mention it; actual awaited calls are not.
    """
    routers = Path(__file__).resolve().parent.parent / "routers"
    offenders = []
    for path in routers.glob("*.py"):
        for i, line in enumerate(path.read_text().splitlines(), 1):
            code = line.split("#", 1)[0]
            if re.search(r"\basyncio\.to_thread\s*\(", code):
                offenders.append(f"{path.name}:{i}: {line.strip()}")
    assert not offenders, (
        "DuckDB work must use to_duckdb_thread (modules/duckpool.py), not the "
        "default executor:\n" + "\n".join(offenders)
    )


def test_pool_status_never_raises():
    """pool_status() is called from the startup path, so it must be safe even if
    CPython's ThreadPoolExecutor internals change shape."""
    assert isinstance(duckpool.pool_status(), str)

    class Broken:
        _threads = property(lambda self: (_ for _ in ()).throw(AttributeError("gone")))

    saved = duckpool._executor
    try:
        duckpool._executor = Broken()
        assert "max_workers" in duckpool.pool_status()  # degraded, not raised
    finally:
        duckpool._executor = saved
