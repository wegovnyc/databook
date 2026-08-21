"""Precompute the per-contract payment timeline, payee rollup and spend map.

    docker compose exec -T api python build_contract_timeline.py          # REPORT
    docker compose exec -T api python build_contract_timeline.py --apply  # write

⚠ PREFER AN ISOLATED CONTAINER for the real run — see the invocation in
scripts/oce-refresh.sh. This does a full-lake DuckDB pass, and doing that inside
the api process is the exact contention this exists to remove.

WHY
---
`/oce/contract/{id}` ran a DuckDB Parquet scan per request. Measured on prod
2026-08-18 with a Postgres-only control endpoint timed during each burst:

    concurrency   contract endpoint   UNRELATED postgres-only probe
        1              0.053s              0.26s  (baseline 0.27s)
        6         0.9 - 3.1s               0.495s
       12         0.9 - 4.4s               0.595s   -> recovers instantly after

An endpoint touching no Parquet slowed 2.3x purely because DuckDB scans were
running. The single-request cost is only 53ms, so the problem is contention, not
query cost — which means the fix has to REMOVE the scan from the request path
rather than make it faster. A connection pool would share the starvation; this
ends it.

⚠⚠ THE SCOPING IS THE WHOLE TRICK, AND GETTING IT WRONG REBUILDS A KNOWN OOM.
The lake holds 46,929,170 payment rows across 8,651,319 DISTINCT contract_ids —
purchase orders and document numbers, not contracts. Grouping over all of them is
what produced the ~5.5 GB dict that OOM-crash-looped the api before #103. But
`/oce/contract/{id}` can only ever serve a REGISTERED contract, so scoping to the
36,421 ids in `contracts` collapses the job:

    relevant payment rows      1,133,178   (2.4% of the lake)
    contracts with payments       31,648
    timeline rows                323,498   0.5s   3.7 MiB
    payee rows (top 25)           41,369   0.4s   0.8 MiB
    spend rows                    31,648   0.4s
    WHOLE PRECOMPUTE              ~1.3s    ~4.5 MiB

⚠ `raw_variants` IS CORRECTNESS, NOT POLISH. Some lake rows carry a raw
contract_id whose normalized form differs (dashed `PON...` purchase orders).
Measured 2026-08-18: 13,860 such rows, of which **0** normalize to a registered
contract — but that count was 13,783 when the live docstring was written, so the
set GROWS. The normalization here is therefore identical to
`oce._normalize_contract_id` (upper, strip non-alnum) and the variants are stored,
so a future Checkbook refresh introducing one is carried rather than silently
dropping that contract's payments.
"""
import argparse
import asyncio
import os

import asyncpg

try:
    from modules import dbcreds
except ImportError:  # pragma: no cover - path differs between run styles
    import dbcreds

# Refuse to publish a rebuild that loses more than this share of any table.
MAX_DROP = 0.50
# A run that considered fewer registered contracts than this has not read the
# contracts table properly; writing its result would empty every timeline.
MIN_KEYS = 30_000
# Payee rows kept per contract. Matches the LIMIT 25 in oce._query_contract_detail
# so the precomputed answer is the same answer, not a different one.
TOP_PAYEES = 25

SCHEMA = """
CREATE TABLE IF NOT EXISTS contract_spend (
    nkey          text PRIMARY KEY,
    spent_to_date double precision NOT NULL DEFAULT 0,
    payment_count integer NOT NULL DEFAULT 0,
    first_payment text,
    last_payment  text,
    raw_variants  text[],
    built_at      timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS contract_timeline (
    nkey     text NOT NULL,
    month    text NOT NULL,
    total    double precision NOT NULL DEFAULT 0,
    built_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (nkey, month)
);
CREATE TABLE IF NOT EXISTS contract_payees (
    nkey       text NOT NULL,
    rank       integer NOT NULL,
    payee_name text,
    sub_vendor text,
    prime      text,
    spent      double precision NOT NULL DEFAULT 0,
    n          integer NOT NULL DEFAULT 0,
    built_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (nkey, rank)
);
CREATE INDEX IF NOT EXISTS idx_contract_timeline_nkey ON contract_timeline (nkey);
CREATE INDEX IF NOT EXISTS idx_contract_payees_nkey ON contract_payees (nkey);
"""

# ⚠ Must stay byte-identical in meaning to oce._normalize_contract_id. Two
# implementations of one key is how a precompute silently stops matching.
NKEY = "REGEXP_REPLACE(UPPER(contract_id), '[^A-Z0-9]', '', 'g')"


def _spending_glob() -> str:
    base = os.getenv("SPENDING_DATA_BASE", "/data")
    return f"{base.rstrip('/')}/spending/fiscal_year=*/*.parquet"


def build_duckdb(keys: list):
    """One pass over the lake; returns (spend, timeline, payees) as row lists."""
    import duckdb
    con = duckdb.connect()
    con.execute("SET memory_limit='2GB'")
    con.execute("CREATE TABLE keys(k VARCHAR)")
    con.executemany("INSERT INTO keys VALUES (?)", [(k,) for k in keys])
    lake = f"read_parquet('{_spending_glob()}', hive_partitioning=1)"

    # Materialize the relevant slice ONCE — 2.4% of the lake — then aggregate it
    # three ways. Same reasoning as _query_contract_detail's single scan.
    con.execute(
        f"CREATE TABLE rel AS SELECT {NKEY} AS nkey, contract_id, check_amount, "
        f"issue_date, payee_name, sub_vendor, associated_prime_vendor "
        f"FROM {lake} WHERE contract_id IS NOT NULL AND contract_id <> '' "
        f"AND {NKEY} IN (SELECT k FROM keys)")

    spend = con.execute(
        "SELECT nkey, COALESCE(SUM(TRY_CAST(check_amount AS DOUBLE)),0), COUNT(*), "
        "MIN(issue_date), MAX(issue_date), "
        "ARRAY_AGG(DISTINCT contract_id) FILTER (WHERE contract_id <> nkey) "
        "FROM rel GROUP BY nkey").fetchall()
    timeline = con.execute(
        "SELECT nkey, strftime(TRY_CAST(issue_date AS DATE), '%Y-%m') AS m, "
        "COALESCE(SUM(TRY_CAST(check_amount AS DOUBLE)),0) "
        "FROM rel WHERE issue_date IS NOT NULL GROUP BY 1,2").fetchall()
    payees = con.execute(
        "SELECT nkey, rn, payee_name, sub_vendor, associated_prime_vendor, spent, n FROM ("
        "  SELECT nkey, payee_name, sub_vendor, associated_prime_vendor, "
        "         COALESCE(SUM(TRY_CAST(check_amount AS DOUBLE)),0) AS spent, COUNT(*) AS n, "
        "         row_number() OVER (PARTITION BY nkey ORDER BY "
        "           COALESCE(SUM(TRY_CAST(check_amount AS DOUBLE)),0) DESC) AS rn "
        "  FROM rel GROUP BY 1,2,3,4) "
        f"WHERE rn <= {TOP_PAYEES}").fetchall()
    con.close()
    return spend, timeline, payees


async def _swap(conn, table: str, cols: str, rows: list, apply: bool) -> int:
    """Stage, guard against a large drop, then swap. Returns the row count."""
    if not apply:
        return len(rows)
    stg = f"_staging_{table}"
    await conn.execute(f"DROP TABLE IF EXISTS {stg}")
    await conn.execute(f"CREATE TABLE {stg} (LIKE {table} INCLUDING ALL)")
    await conn.copy_records_to_table(stg, records=rows,
                                     columns=[c.strip() for c in cols.split(",")])
    new = await conn.fetchval(f"SELECT count(*) FROM {stg}")
    old = await conn.fetchval(f"SELECT count(*) FROM {table}")
    # ⚠ Guard the SWAP, not the build: a truncated lake or a half-loaded contracts
    # table would otherwise blank every contract page's spend section at once, and
    # an empty timeline is indistinguishable from a contract with no payments.
    if old and new < old * (1 - MAX_DROP):
        await conn.execute(f"DROP TABLE IF EXISTS {stg}")
        raise RuntimeError(f"refusing swap on {table}: {new} rows vs {old} "
                           f"previously (>{int(MAX_DROP*100)}% drop)")
    async with conn.transaction():
        await conn.execute(f"DROP TABLE {table}")
        await conn.execute(f"ALTER TABLE {stg} RENAME TO {table}")
    return new


async def run(conn, apply: bool, verbose: bool = True):
    if apply:
        for stmt in [s.strip() for s in SCHEMA.split(";") if s.strip()]:
            await conn.execute(stmt)

    rows = await conn.fetch(
        "SELECT DISTINCT upper(regexp_replace("
        "  coalesce(normalized_contract_id, contract_id), '[^A-Za-z0-9]', '', 'g')) AS k "
        "FROM contracts WHERE coalesce(normalized_contract_id, contract_id) IS NOT NULL")
    keys = [r["k"] for r in rows if r["k"]]

    # ⚠ A RUN THAT CONSIDERED NOTHING MUST NOT LOOK LIKE A RUN THAT FOUND NOTHING.
    if len(keys) < MIN_KEYS:
        raise RuntimeError(
            f"only {len(keys)} registered contract keys (expected >{MIN_KEYS}) — "
            "the contracts table looks unloaded; refusing to rebuild from it")

    spend, timeline, payees = build_duckdb(keys)
    # asyncpg wants tuples in column order, and text[] must be a real list.
    spend = [(k, float(s or 0), int(n or 0), fd, ld, list(v or []))
             for k, s, n, fd, ld, v in spend]
    timeline = [(k, m, float(t or 0)) for k, m, t in timeline]
    payees = [(k, int(rn), p, sv, pv, float(sp or 0), int(n or 0))
              for k, rn, p, sv, pv, sp, n in payees]

    ns = await _swap(conn, "contract_spend",
                     "nkey,spent_to_date,payment_count,first_payment,last_payment,raw_variants",
                     spend, apply)
    nt = await _swap(conn, "contract_timeline", "nkey,month,total", timeline, apply)
    np_ = await _swap(conn, "contract_payees",
                      "nkey,rank,payee_name,sub_vendor,prime,spent,n", payees, apply)
    if verbose:
        print(f"[contract-timeline] registered keys: {len(keys)}")
        print(f"[contract-timeline]   spend rows:    {ns}")
        print(f"[contract-timeline]   timeline rows: {nt}")
        print(f"[contract-timeline]   payee rows:    {np_}")
        variants = sum(1 for r in spend if r[5])
        print(f"[contract-timeline]   contracts carrying raw_variants: {variants}")
    return ns, nt, np_


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="write the tables (default is a dry run)")
    args = ap.parse_args()
    conn = await asyncpg.connect(**dbcreds.settings({}))
    try:
        print(f"[contract-timeline] mode: "
              f"{'APPLY' if args.apply else 'REPORT (pass --apply)'}\n")
        await run(conn, args.apply)
        if not args.apply:
            print("\n[contract-timeline] nothing written. Re-run with --apply.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
