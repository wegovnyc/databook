import os
import re
import json
import asyncpg
import asyncio
from decimal import Decimal
from config import Config

# Bounded connection pool — prevents Postgres exhaustion under production traffic.
# max_size=20 caps connections from the API; min_size=2 keeps warm connections ready.
_pool: asyncpg.Pool = None

async def _get_pool() -> asyncpg.Pool:
    """Get or create the singleton connection pool."""
    global _pool
    if _pool is None or _pool._closed:
        _pool = await asyncpg.create_pool(
            user=Config.db['user'],
            password=Config.db['pwd'],
            database=Config.db['dbname'],
            host=Config.db['host'],
            min_size=2,
            max_size=20,
            command_timeout=30,
        )
    return _pool


class PostgresModelAsync:
    db = None

    async def connect():
        """Pre-warm the connection pool at startup."""
        await _get_pool()

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
