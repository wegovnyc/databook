"""Build the NYCHA -> PASSPort vendor crosswalk (tiered matching).

NYCHA (Checkbook _NYCHA) vendors are name-only; City vendor profiles are keyed by
PASSPort Supplier-ID. This matches each distinct NYCHA vendor name to a PASSPort
vendor across confidence TIERS, then writes:
  - Postgres  nycha_vendor_crosswalk  (all tiers, for review + joins),
  - Parquet   /data/nycha_vendor_crosswalk.parquet  (auto-linking tiers only:
    nycha_vendor_name, passport_supplier_id) so the DuckDB NYCHA endpoints LEFT
    JOIN it.

Tiers (highest first; `confidence` column):
  - 'curated'      manual, human-confirmed (never overwritten). Optionally seeded
                   from a CSV (env NYCHA_CURATED_XWALK_CSV: name,id[,note]).
  - 'exact'        exact NORMALIZED-name match (Phase 1).
  - 'fuzzy'        Phase 3 high-confidence fuzzy (token-blocked, ratio >= HIGH) —
                   AUTO-LINKS (written to the parquet).
  - 'fuzzy-review' Phase 3 borderline (REVIEW <= ratio < HIGH) — stored for human
                   curation but NOT written to the parquet (does NOT auto-link).

Idempotent + curated-respecting (never overwrites curated=true rows). Run in an
isolated container (has DuckDB + Postgres access), e.g.:
  docker run --rm -m 4g -v /home/ubuntu/databook-data:/data -w /app \
    -e POSTGRES_HOST -e POSTGRES_USER -e POSTGRES_PASSWORD -e POSTGRES_DB \
    databook-api python build_nycha_vendor_crosswalk.py
"""
import os
import re
import csv
import difflib
import asyncio
from collections import defaultdict

import duckdb
import asyncpg

DATA = os.environ.get("DATA_LAKE_PATH", "/data")
_SUFFIX = re.compile(r"\b(INC|LLC|LLP|LP|CORP|CO|LTD|COMPANY|THE|INCORPORATED|GROUP|USA)\b")

# Fuzzy tiers. HIGH auto-links; [REVIEW, HIGH) is stored for human review only.
# Deliberately conservative — auto-linking a WRONG City vendor is worse than not
# linking a right one (an unmatched vendor still gets a NYCHA-native profile).
# 0.96 after auditing every auto-link against prod: below it, two different firms
# sharing two real words but differing only in a short/similar identity token
# (ASR vs SRA OFFICE SOLUTIONS; CASA vs ASIA BUILDING MATERIALS; SAM'S vs SLAM
# TECHNICAL SERVICES, all .950-.957) score as high as real punctuation-only
# variants. The 0.96+ band audited clean; the [0.86, 0.96) band (incl. some real
# matches) goes to the review tier for a human. Paired with the distinctive-token
# gate below (an auto-link must share a non-generic token).
FUZZY_HIGH = 0.96
FUZZY_REVIEW = 0.86
JACCARD_MIN = 0.5          # must share meaningful tokens (guards coincidental chars)
MIN_NORM_LEN = 6           # skip tiny names (too easy to false-match)
COMMON_TOKEN_DF = 400      # tokens in >this many PASSPort vendors are too generic to block on
DISTINCTIVE_TOKEN_DF = 150 # an auto-link must share >=1 token in <=this many PASSPort vendors
MAX_CANDIDATES = 600       # per-vendor candidate cap (bounds runtime)

# DDL inlined (the api image doesn't bundle scripts/); mirror of
# scripts/nycha_vendor_crosswalk.sql — keep in sync. match_score added Phase 3;
# ALTER makes the upgrade idempotent on pre-existing tables.
_DDL = """
CREATE TABLE IF NOT EXISTS nycha_vendor_crosswalk (
    nycha_vendor_name     text PRIMARY KEY,
    passport_supplier_id  text,
    passport_vendor_name  text,
    confidence            text DEFAULT 'exact',
    match_source          text DEFAULT 'normalized-name',
    match_score           double precision,
    derived_at            timestamptz DEFAULT now(),
    curated               boolean DEFAULT false,
    curated_note          text
);
ALTER TABLE nycha_vendor_crosswalk ADD COLUMN IF NOT EXISTS match_score double precision;
CREATE INDEX IF NOT EXISTS idx_nycha_xwalk_passport ON nycha_vendor_crosswalk (passport_supplier_id);
"""


def norm(s: str) -> str:
    s = (s or "").upper()
    # Drop apostrophes rather than spacing them so ADAM'S -> ADAMS (not ADAM S);
    # otherwise apostrophe names miss the exact tier (PASSPort "ADAM'S EUROPEAN"
    # vs NYCHA "ADAMS EUROPEAN"). Covers straight + curly + modifier-letter apos.
    s = re.sub(r"[‘’ʼ'`´]", "", s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = _SUFFIX.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(n: str) -> list:
    return [t for t in n.split() if len(t) >= 3]


def _nycha_vendors() -> list:
    con = duckdb.connect()
    q = f"""
        SELECT DISTINCT vendor FROM (
            SELECT vendor FROM read_parquet('{DATA}/nycha_contracts/nycha_contracts.parquet')
            UNION
            SELECT vendor FROM read_parquet('{DATA}/nycha_spending/**/*.parquet', union_by_name=true)
        ) WHERE vendor IS NOT NULL AND vendor <> ''
    """
    rows = [r[0] for r in con.execute(q).fetchall()]
    con.close()
    return rows


def _nycha_contract_vendors() -> list:
    """Distinct CONTRACT vendors only — the fuzzy pass is scoped to these (the
    meaningful procurement relationships; the ~41k spending-tail payees are mostly
    tiny one-offs not in PASSPort, and fuzzing them all is costly + noisy)."""
    con = duckdb.connect()
    rows = [r[0] for r in con.execute(
        f"SELECT DISTINCT vendor FROM read_parquet('{DATA}/nycha_contracts/nycha_contracts.parquet') "
        f"WHERE vendor IS NOT NULL AND vendor <> ''"
    ).fetchall()]
    con.close()
    return rows


def _fuzzy_matches(unmatched: list, pv_entries: list) -> tuple:
    """Token-blocked fuzzy match of `unmatched` NYCHA names against PASSPort
    `pv_entries` [(norm, id, name)]. Returns (high, review) lists of
    (nycha_name, id, passport_name, score)."""
    # Token -> candidate indices, and token document-frequency (to skip generics).
    tok_index = defaultdict(list)
    tok_df = defaultdict(int)
    for i, (n, _id, _name) in enumerate(pv_entries):
        for t in set(_tokens(n)):
            tok_index[t].append(i)
            tok_df[t] += 1

    def candidates(n: str) -> set:
        toks = set(_tokens(n))
        distinctive = [t for t in toks if tok_df.get(t, 0) <= COMMON_TOKEN_DF]
        use = distinctive or list(toks)  # fall back to all tokens if all generic
        idxs = set()
        for t in sorted(use, key=lambda t: tok_df.get(t, 0)):  # rarest first
            idxs.update(tok_index.get(t, ()))
            if len(idxs) >= MAX_CANDIDATES:
                break
        return idxs

    high, review = [], []
    for v in unmatched:
        n = norm(v)
        if len(n) < MIN_NORM_LEN:
            continue
        ta = set(_tokens(n))
        if not ta:
            continue
        best = None  # (score, id, name, distinctive)
        for i in candidates(n):
            pn, pid, pname = pv_entries[i]
            tb = set(_tokens(pn))
            union = ta | tb
            shared = ta & tb
            jac = len(shared) / len(union) if union else 0.0
            if jac < JACCARD_MIN:
                continue
            # Pure string ratio — do NOT shortcut equal token-SETS to a high score:
            # GROUP/CORP are stripped as suffixes and short identity tokens (J N, B2,
            # T&T) drop out, so many generic names collapse to a single shared token
            # like {CONSTRUCTION}/{REMODELING} and would falsely tie (e.g. "B2
            # CONSTRUCTION" == "J & N Construction Group"). The real ratio (~0.8)
            # correctly keeps those out of the auto-link tier.
            score = difflib.SequenceMatcher(None, n, pn).ratio()
            # A match is only "distinctive" if it shares a non-generic token. Two
            # different firms sharing only a common descriptor (ASR vs SRA OFFICE
            # SOLUTIONS; CASA vs ASIA BUILDING MATERIALS) can score >0.95 when the
            # short identity token is dropped — the tail carries the ratio. Require
            # a distinctive shared token to AUTO-LINK; else it can still go to review.
            distinctive = any(tok_df.get(t, 0) <= DISTINCTIVE_TOKEN_DF for t in shared)
            if best is None or score > best[0]:
                best = (score, pid, pname, distinctive)
        if best:
            score, pid, pname, distinctive = best
            if score >= FUZZY_HIGH and distinctive:
                high.append((v, pid, pname, round(score, 4)))
            elif score >= FUZZY_REVIEW:
                review.append((v, pid, pname, round(score, 4)))
    return high, review


# A curated row whose id is one of these means "reviewed and NOT a match" — stored
# as curated with a NULL passport_supplier_id so the pair never auto-links AND
# never returns to the review queue. Without this, every human rejection would be
# re-proposed as fuzzy-review on the next run, so the review work wouldn't stick.
_NO_MATCH = {"-", "", "none", "null", "no", "nomatch", "no-match", "x"}


def _load_curated() -> list:
    """Curated seed CSV — rows of nycha_vendor_name,passport_supplier_id[,note],
    where passport_supplier_id may be a _NO_MATCH marker (e.g. "-") to record a
    reviewed rejection. Path: env NYCHA_CURATED_XWALK_CSV, else
    <DATA>/nycha_curated_xwalk.csv (so the weekly auto-refresh picks it up with no
    env plumbing). Returns [(name, id_or_None, note)]; [] if absent."""
    path = os.environ.get("NYCHA_CURATED_XWALK_CSV") or f"{DATA}/nycha_curated_xwalk.csv"
    if not os.path.exists(path):
        return []
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if not row or not row[0].strip():
                continue
            if row[0].strip().lower() in ("nycha_vendor_name", "name"):  # header
                continue
            raw = row[1].strip() if len(row) > 1 else ""
            pid = None if raw.lower() in _NO_MATCH else raw
            out.append((row[0].strip(), pid, (row[2].strip() if len(row) > 2 else None)))
    return out


async def main():
    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
        database=os.environ.get("POSTGRES_DB", "databook"),
    )
    try:
        await conn.execute(_DDL)

        # --- curated tier (optional seed; upserted first so later tiers can't
        #     clobber it via the curated=false guard) ---------------------------
        curated = _load_curated()
        if curated:
            await conn.executemany(
                """INSERT INTO nycha_vendor_crosswalk
                     (nycha_vendor_name, passport_supplier_id, passport_vendor_name,
                      confidence, match_source, derived_at, curated, curated_note)
                   VALUES ($1, $2, NULL, 'curated', 'curated-csv', now(), true, $3)
                   ON CONFLICT (nycha_vendor_name) DO UPDATE SET
                     passport_supplier_id = EXCLUDED.passport_supplier_id,
                     confidence = 'curated', match_source = 'curated-csv',
                     curated = true, curated_note = EXCLUDED.curated_note, derived_at = now()""",
                curated,
            )
        _conf = sum(1 for c in curated if c[1])
        print(f"[xwalk] curated seed rows: {len(curated)} "
              f"({_conf} confirmed links, {len(curated) - _conf} reviewed rejections)")

        # Reconcile: drop all machine-derived rows (keep curated) so a name that no
        # longer matches — or that dropped a tier this run (e.g. fuzzy -> nothing
        # after a threshold/logic change) — does NOT linger with a stale link. The
        # generator was upsert-only, so stale fuzzy rows (incl. corrected false
        # positives) survived and were re-written into the parquet. Curated rows are
        # never touched.
        removed = await conn.execute("DELETE FROM nycha_vendor_crosswalk WHERE curated = false")
        print(f"[xwalk] cleared machine-derived rows: {removed}")

        # PASSPort vendors -> normalized-name. by_norm dedupes for the exact pass;
        # pv_entries keeps every candidate for fuzzy blocking.
        pv = await conn.fetch(
            'SELECT "PASSPort Supplier-ID" AS id, "Vendor Name" AS name FROM vendors '
            'WHERE "Vendor Name" IS NOT NULL AND "PASSPort Supplier-ID" IS NOT NULL '
            'ORDER BY "Vendor Name", "PASSPort Supplier-ID"'
        )
        by_norm: dict = {}
        pv_entries = []
        for r in pv:
            n = norm(r["name"])
            if not n:
                continue
            pv_entries.append((n, r["id"], r["name"]))
            if n not in by_norm:
                by_norm[n] = (r["id"], r["name"])

        # --- exact tier ------------------------------------------------------
        nycha = _nycha_vendors()
        matched = [(v, *by_norm[norm(v)]) for v in nycha if norm(v) in by_norm]
        exact_names = {m[0] for m in matched}
        print(f"[xwalk] NYCHA vendors={len(nycha)} PASSPort norm={len(by_norm)} "
              f"exact matches={len(matched)} ({100*len(matched)//max(len(nycha),1)}%)")

        await conn.executemany(
            """INSERT INTO nycha_vendor_crosswalk
                 (nycha_vendor_name, passport_supplier_id, passport_vendor_name,
                  confidence, match_source, match_score, derived_at)
               VALUES ($1, $2, $3, 'exact', 'normalized-name', NULL, now())
               ON CONFLICT (nycha_vendor_name) DO UPDATE SET
                 passport_supplier_id = EXCLUDED.passport_supplier_id,
                 passport_vendor_name = EXCLUDED.passport_vendor_name,
                 confidence = EXCLUDED.confidence, match_source = EXCLUDED.match_source,
                 match_score = NULL, derived_at = now()
               WHERE nycha_vendor_crosswalk.curated = false""",
            [(m[0], m[1], m[2]) for m in matched],
        )

        # --- fuzzy tiers (over unmatched CONTRACT vendors) -------------------
        contract_vendors = _nycha_contract_vendors()
        unmatched = [v for v in contract_vendors if v not in exact_names]
        high, review = _fuzzy_matches(unmatched, pv_entries)
        print(f"[xwalk] fuzzy over {len(unmatched)} unmatched contract vendors -> "
              f"high(auto-link)={len(high)} review(hold)={len(review)}")

        # fuzzy-high auto-links; guard so it never clobbers curated OR the
        # stronger exact tier (a name could be exact this run but slipped into the
        # contract-only fuzzy set across data shifts).
        await conn.executemany(
            """INSERT INTO nycha_vendor_crosswalk
                 (nycha_vendor_name, passport_supplier_id, passport_vendor_name,
                  confidence, match_source, match_score, derived_at)
               VALUES ($1, $2, $3, 'fuzzy', 'fuzzy-token-ratio', $4, now())
               ON CONFLICT (nycha_vendor_name) DO UPDATE SET
                 passport_supplier_id = EXCLUDED.passport_supplier_id,
                 passport_vendor_name = EXCLUDED.passport_vendor_name,
                 confidence = 'fuzzy', match_source = 'fuzzy-token-ratio',
                 match_score = EXCLUDED.match_score, derived_at = now()
               WHERE nycha_vendor_crosswalk.curated = false
                 AND nycha_vendor_crosswalk.confidence <> 'exact'""",
            [(h[0], h[1], h[2], h[3]) for h in high],
        )
        # fuzzy-review is stored (for curation) but must NOT auto-link — excluded
        # from the parquet below. Same guards.
        await conn.executemany(
            """INSERT INTO nycha_vendor_crosswalk
                 (nycha_vendor_name, passport_supplier_id, passport_vendor_name,
                  confidence, match_source, match_score, derived_at)
               VALUES ($1, $2, $3, 'fuzzy-review', 'fuzzy-token-ratio', $4, now())
               ON CONFLICT (nycha_vendor_name) DO UPDATE SET
                 passport_supplier_id = EXCLUDED.passport_supplier_id,
                 passport_vendor_name = EXCLUDED.passport_vendor_name,
                 confidence = 'fuzzy-review', match_source = 'fuzzy-token-ratio',
                 match_score = EXCLUDED.match_score, derived_at = now()
               WHERE nycha_vendor_crosswalk.curated = false
                 AND nycha_vendor_crosswalk.confidence NOT IN ('exact', 'fuzzy')""",
            [(r[0], r[1], r[2], r[3]) for r in review],
        )

        total = await conn.fetchval("SELECT count(*) FROM nycha_vendor_crosswalk")
        by_tier = await conn.fetch(
            "SELECT confidence, count(*) FROM nycha_vendor_crosswalk GROUP BY confidence ORDER BY 1")
        print(f"[xwalk] nycha_vendor_crosswalk rows now: {total} "
              f"({', '.join(f'{r[0]}={r[1]}' for r in by_tier)})")

        # Parquet = auto-linking tiers only: exclude 'fuzzy-review' (and NULL ids,
        # e.g. curated rejections marking 'no match').
        rows = await conn.fetch(
            "SELECT nycha_vendor_name, passport_supplier_id FROM nycha_vendor_crosswalk "
            "WHERE passport_supplier_id IS NOT NULL AND confidence <> 'fuzzy-review'"
        )
    finally:
        await conn.close()

    con = duckdb.connect()
    con.execute("CREATE TABLE xw (nycha_vendor_name VARCHAR, passport_supplier_id VARCHAR)")
    con.executemany("INSERT INTO xw VALUES (?, ?)", [(r["nycha_vendor_name"], r["passport_supplier_id"]) for r in rows])
    out = f"{DATA}/nycha_vendor_crosswalk.parquet"
    con.execute(f"COPY xw TO '{out}' (FORMAT PARQUET)")
    con.close()
    print(f"[xwalk] wrote {len(rows)} auto-linking rows -> {out}")


if __name__ == "__main__":
    asyncio.run(main())
