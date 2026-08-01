import os
import re
import json
import asyncpg
import asyncio
from decimal import Decimal
from config import Config

# Credential resolution lives in one place — see modules/dbcreds.py.
try:
    import dbcreds
except ImportError:  # when imported as part of the modules package
    from modules import dbcreds


# Bounded connection pool — prevents Postgres exhaustion under production traffic.
# max_size caps connections from the API; min_size is the WARM BASELINE opened
# eagerly by create_pool() at startup, before any traffic.
#
# ⚠ Why min_size == max_size (fully pre-opened, pool NEVER grows under traffic):
#
# Symptom: bursts of `TimeoutError` raised out of asyncpg's getaddrinfo inside
# _get_new_connection, firing SIMULTANEOUSLY across unrelated per-id endpoints
# (contract/{id}, people/{pid}, orgs/profile/{id}, titles/{id}) — ~200 on
# 2026-07-24 and ~190/24h still on 2026-07-27. It looks exactly like Postgres
# connection exhaustion. It is NOT: during a measured burst Postgres had 8 of 100
# client backends in use, and the same endpoints serve in ~0.04s warm.
#
# ROOT CAUSE (found 2026-07-27) is executor starvation, and it lives in
# modules/duckpool.py — read that file for the full writeup. In short: heavy DuckDB
# lake scans ran on the loop's DEFAULT ThreadPoolExecutor (12 threads here), and
# `loop.getaddrinfo()` — which asyncpg must call to open a new connection — runs on
# that same default executor. A crawler hammering the DuckDB endpoints filled all 12
# threads, so DNS for a new Postgres connection queued behind multi-second Parquet
# scans until asyncpg's 60s connect timeout fired. DuckDB now has its own executor.
#
# This setting is the second layer: if the pool is fully open before any traffic and
# never has to grow, the request path never calls getaddrinfo at all, so it cannot be
# starved by anything. (Raising the baseline 2 -> 10 in d066358 only made a new
# connection RARER — any demand above the current size still triggered a lookup,
# which is why the bursts continued after that fix shipped.)
#
# Cost is negligible: 20 idle asyncpg connections against max_connections=100, and
# the mcp container does not share this pool. See also
# routers/data_pipeline.py::get_dataset_counts, which already bypasses the pool for
# a related startup-contention reason.
_POOL_MAX = int(os.environ.get("PG_POOL_MAX_SIZE", "20"))
_POOL_MIN = int(os.environ.get("PG_POOL_MIN_SIZE", str(_POOL_MAX)))
_pool: asyncpg.Pool = None

async def _get_pool() -> asyncpg.Pool:
    """Get or create the singleton connection pool."""
    global _pool
    if _pool is None or _pool._closed:
        _pool = await asyncpg.create_pool(
            # Environment first, env.yaml only as a fallback.
            #
            # Why: the credential used to live in BOTH .env (compose -> container
            # env) and api/env.yaml, and this pool read only the YAML. That meant a
            # rotation had to edit two files in two formats and keep them in step,
            # and env.yaml additionally carried an `addr:` DSN embedding a third
            # copy. Reading the environment here makes the container env the single
            # source of truth and lets the secrets come out of env.yaml entirely.
            # Matches the precedent in setup_oce_postgres.py.
            user=os.environ.get('POSTGRES_USER') or Config.db.get('user'),
            password=dbcreds.password(Config.db.get('pwd') or ''),
            database=os.environ.get('POSTGRES_DB') or Config.db.get('dbname'),
            host=os.environ.get('POSTGRES_HOST') or Config.db.get('host'),
            port=int(os.environ.get('POSTGRES_PORT', '5432')),
            min_size=_POOL_MIN,
            max_size=_POOL_MAX,
            command_timeout=30,
        )
    return _pool


class PostgresModelAsync:
    db = None

    async def connect():
        """Pre-warm the connection pool at startup."""
        await _get_pool()

    def pool_status():
        """Human-readable pool state, for startup logging — makes the warm
        baseline visible so a cold-start connect storm is diagnosable from logs."""
        if _pool is None or _pool._closed:
            return "not initialized"
        return f"{_pool.get_size()} open (min={_POOL_MIN}, max={_POOL_MAX})"

    async def disconnect():
        """Close the pool on shutdown."""
        global _pool
        if _pool and not _pool._closed:
            await _pool.close()
            _pool = None

    async def select_safe(sql, dd=[]):
        """Execute a SELECT and return rows as list of dicts with stripped strings."""
        pool = await _get_pool()
        async with pool.acquire() as db:
            req = await db.prepare(sql)
            rr = await req.fetch(*dd)
        return [{k: v.strip() if type(v) == str else v for k, v in dict(r).items()} for r in rr]

    async def select_safe_with_timeout(sql, dd=[], timeout_seconds=60):
        """Execute a SELECT with a custom statement_timeout for expensive queries.
        
        Why: PostgreSQL has a global 15s statement_timeout and the asyncpg pool
        has a 30s command_timeout. Some aggregations (e.g. SUM + regexp_replace
        on 3.2M row civillist) need more time. This overrides both timeouts.
        """
        pool = await _get_pool()
        async with pool.acquire() as db:
            try:
                await db.execute(f"SET statement_timeout = '{timeout_seconds}s'")
                rr = await db.fetch(sql, *dd, timeout=timeout_seconds)
            finally:
                await db.execute("SET statement_timeout = '15s'")
        return [{k: v.strip() if type(v) == str else v for k, v in dict(r).items()} for r in rr]

    def jsonsafe(dd):
        def deff(obj):
            s = str(obj)
            if isinstance(obj, Decimal):
                if re.search('\.', s):
                    return float(obj)
                else:
                    return int(obj)
            else:
                return s
        return json.dumps(dd, ensure_ascii=False, default=deff)

    async def select(sql, params=[]):
        rr = await __class__.select_safe(sql, params)
        return {'rows': json.loads(__class__.jsonsafe(rr))}

    async def execute(sql, params=[]):
        """Execute INSERT/UPDATE/DELETE statements."""
        pool = await _get_pool()
        async with pool.acquire() as db:
            result = await db.execute(sql, *params)
            return result
