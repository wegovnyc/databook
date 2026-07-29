"""Dedicated thread pool for blocking DuckDB / Parquet work.

WHY THIS EXISTS (incident 2026-07-27)
-------------------------------------
Sentry showed ~190 `TimeoutError`/24h in tight 30-60s bursts, firing SIMULTANEOUSLY
across four unrelated Postgres endpoints (/get/orgs/profile/{id}, /oce/contract/{id},
/get/people/{pid}, /get/titles/{id}). The stack was always the same:

    postgrex/asyncmodel.py select_safe
      -> asyncpg/pool.py _get_new_connection -> connection.connect
      -> CancelledError inside _create_ssl_connection / getaddrinfo

It read like Postgres connection exhaustion. It was NOT: Postgres had 8 of 100 client
backends in use during a burst, and the same endpoints serve in ~0.04s warm.

The real mechanism is EXECUTOR STARVATION:

  * Every heavy DuckDB lake scan was dispatched with `asyncio.to_thread(...)`, which
    runs on the loop's DEFAULT ThreadPoolExecutor. That executor is sized
    min(32, cpu_count + 4) = 12 threads on this 8-vCPU box.
  * `loop.getaddrinfo()` — which asyncpg MUST call to open a new pool connection —
    also runs on the DEFAULT executor.
  * So when a crawler walked the NYCHA DuckDB endpoints (measured: 26 hits on
    procurement-nycha-contract + 18 on procurement-nycha-spending inside one 60s
    burst window), 12 multi-second Parquet scans occupied every default-executor
    thread. Any concurrent Postgres endpoint that needed a NEW connection had its
    DNS lookup QUEUED behind them until asyncpg's 60s connect timeout fired.

Raising the pool's warm baseline (PG_POOL_MIN_SIZE 2 -> 10, commit d066358) reduced
how often a new connection was needed, but could not fix this: any demand above the
current pool size still triggers a getaddrinfo that can queue behind DuckDB.

THE FIX: give DuckDB its own bounded executor, so blocking Parquet scans can never
occupy the threads that DNS resolution (and every other default-executor user) needs.
Bounding it also caps how many full-lake scans a traffic burst can run at once, which
protects CPU and the 2 GB DuckDB memory budget.

Use `to_duckdb_thread(fn, *args)` in place of `asyncio.to_thread(fn, *args)` for any
call that touches DuckDB or Parquet. Keep `asyncio.to_thread` for everything else.
"""

import asyncio
import contextvars
import functools
import os
from concurrent.futures import ThreadPoolExecutor

# 6 workers on 8 vCPU: enough concurrency that normal traffic never queues, low
# enough that a crawler can't pin every core on full-lake scans. The shared
# persistent DuckDB connection is capped at threads=2 / memory_limit=2GB, and that
# budget is per-instance (shared across cursors), so this bound is about CPU and
# queue depth, not DuckDB's own parallelism.
DUCKDB_MAX_WORKERS = int(os.environ.get("DUCKDB_MAX_WORKERS", "6"))

_executor: ThreadPoolExecutor = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=DUCKDB_MAX_WORKERS,
            thread_name_prefix="duckdb",
        )
    return _executor


async def to_duckdb_thread(func, /, *args, **kwargs):
    """Run a blocking DuckDB call on the dedicated pool.

    Behaviourally identical to `asyncio.to_thread` — including copying the current
    contextvars context, which Sentry relies on to attach the active transaction /
    scope to anything raised inside the worker thread — except that it uses the
    DuckDB executor instead of the loop's default one.
    """
    loop = asyncio.get_running_loop()
    ctx = contextvars.copy_context()
    call = functools.partial(ctx.run, func, *args, **kwargs)
    return await loop.run_in_executor(_get_executor(), call)


def pool_status() -> str:
    """Human-readable executor state, for startup/diagnostic logging.

    Reads ThreadPoolExecutor internals, so it is fully defensive: this is called
    from the startup path and a logging helper must never be able to prevent boot.
    """
    if _executor is None:
        return f"not initialized (max_workers={DUCKDB_MAX_WORKERS})"
    try:
        return (
            f"{len(_executor._threads)} threads spawned "
            f"(max={DUCKDB_MAX_WORKERS}, queued={_executor._work_queue.qsize()})"
        )
    except Exception:  # noqa: BLE001 — never let diagnostics break startup
        return f"initialized (max_workers={DUCKDB_MAX_WORKERS})"


def shutdown(wait: bool = False) -> None:
    """Release the executor on app shutdown."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=wait)
        _executor = None
