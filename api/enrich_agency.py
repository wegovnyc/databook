"""Post-ingest hook: derive agency head + contact enrichment from nycgreenbook.

No NYC dataset lists agency leadership, and wegov_orgs addresses (from a static
WeGov Airtable seed) are thin. Both are derived from the NYC Greenbook, which
auto-refreshes daily. This hook runs after each `nycgreenbook` ingestion so the
derived tables never go stale.

The SQL here mirrors the canonical scripts scripts/agency_head_*.sql and
scripts/agency_contact_*.sql (kept for one-time setup / manual runs). Keep them
in sync. The scheduler executes SQL over an asyncpg connection — it does not
shell out to psql — so the DDL + derivations are embedded as statements.

Both derivations are idempotent (ON CONFLICT upsert) and respect the `curated`
flag: rows with curated=true are human overrides and are never overwritten.
"""

import os
import sys

import asyncpg

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
try:
    import orgfilter
except ImportError:
    from modules import orgfilter

# ⚠ Both derivations used to filter `w.type = 'City Agency'`. Since the OTI
# registry adoption (2026-07-30) `wegov_orgs.type` is a MIXED vocabulary, and
# ~117 of those agencies now carry OTI's type instead (`Mayoral Agency`,
# `Mayoral Office`, `Division`, `Advisory or Regulatory Organization`…). Left
# alone, this hook would have silently stopped enriching them — the derived
# tables would just get smaller, with nothing raising. Substituted at import so
# the vocabulary lives in exactly one place.
_GOV_TYPES_SQL = orgfilter.sql_type_list(orgfilter.AGENCY_ENRICHMENT_TYPES)

# --- Agency heads -----------------------------------------------------------

_HEAD_DDL = """
CREATE TABLE IF NOT EXISTS agency_head_enrichment (
    org_id       integer PRIMARY KEY,
    agency_name  text,
    head_name    text,
    head_title   text,
    confidence   text,
    rank         integer,
    source       text DEFAULT 'nycgreenbook',
    derived_at   timestamptz DEFAULT now(),
    curated      boolean DEFAULT false,
    curated_note text
)
"""

# Score each City Agency person's "Office Title"; keep the top one per agency.
# The CASE excludes deputies/assistants/bureau heads and functional (HR/IT/
# finance/...) directors so only the actual head scores > 0. \y = word boundary
# (regex escapes survive standard_conforming_strings single-quoted literals).
_HEAD_DERIVE = r"""
WITH scored AS (
    SELECT
        w.id AS org_id,
        w.name AS agency_name,
        regexp_replace(TRIM(CONCAT_WS(' ', gb."First Name", gb."Middle Initial", gb."Last Name", gb."Name Suffix")), '\s+', ' ', 'g') AS person,
        gb."Office Title" AS title,
        CASE
          WHEN gb."Office Title" ~* '(deputy|assistant|associate|\yvice[ -]president\y|bureau|division|acting|interim|to the )' THEN 0
          WHEN gb."Office Title" ~* '(designee|of deeds)' THEN 0
          WHEN gb."Office Title" ~* 'chancellor' THEN 100
          WHEN gb."Office Title" ~* '\ycommissioner\y' THEN 90
          WHEN gb."Office Title" ~* '(chair(man|woman|person)?)\y' THEN 85
          WHEN gb."Office Title" ~* '\ypresident\y' THEN 80
          WHEN gb."Office Title" ~* '(chief medical examiner|corporation counsel|\ycomptroller\y|special commissioner of investigation)' THEN 78
          WHEN gb."Office Title" ~* '(executive director|\yadministrator\y|\ydirector\y)'
               AND gb."Office Title" !~* '(human resources|human capital|procurement|\yacco\y|purchasing|administration|administrative|finance|fiscal|budget|information technology|information systems|\ytechnology\y|communications|press office|public information|operations|labor relations|external affairs|public affairs|governmental|legislative|\ypolicy\y|engineer|equal employment|\yeeo\y|diversity|contracts|facilities|\yaudit\y|payroll|personnel|training|marketing|constituent|records management|representation|treasurer|partnerships|vendex|\yunit\y)'
               THEN CASE WHEN gb."Office Title" ~* 'executive director' THEN 75
                         WHEN gb."Office Title" ~* '\yadministrator\y' THEN 70
                         ELSE 60 END
          ELSE 0
        END AS rank
    FROM wegov_orgs w
    JOIN nycgreenbook gb ON gb."wegov-org-id" = w.id::text
    WHERE w.type IN (__GOV_TYPES__)
      AND COALESCE(gb."First Name",'') !~* '^vacant$'
      AND COALESCE(gb."Last Name",'')  !~* '^vacant$'
),
ranked AS (
    SELECT DISTINCT ON (org_id)
        org_id, agency_name, person AS head_name, title AS head_title, rank
    FROM scored
    WHERE rank > 0
    ORDER BY org_id, rank DESC, length(title), person
)
INSERT INTO agency_head_enrichment
    (org_id, agency_name, head_name, head_title, confidence, rank, source, derived_at, curated)
SELECT
    org_id, agency_name, head_name, head_title,
    CASE WHEN rank >= 78 THEN 'A' ELSE 'B' END,
    rank, 'nycgreenbook', now(), false
FROM ranked
ON CONFLICT (org_id) DO UPDATE SET
    agency_name = EXCLUDED.agency_name,
    head_name   = EXCLUDED.head_name,
    head_title  = EXCLUDED.head_title,
    confidence  = EXCLUDED.confidence,
    rank        = EXCLUDED.rank,
    source      = EXCLUDED.source,
    derived_at  = now()
WHERE agency_head_enrichment.curated = false
"""

# --- Agency contact (modal address) ----------------------------------------

_CONTACT_DDL = """
CREATE TABLE IF NOT EXISTS agency_contact_enrichment (
    org_id         integer PRIMARY KEY,
    agency_name    text,
    address        text,
    address_source text DEFAULT 'nycgreenbook',
    address_rows   integer,
    derived_at     timestamptz DEFAULT now(),
    curated        boolean DEFAULT false,
    curated_note   text
)
"""

_CONTACT_DERIVE = """
WITH addr AS (
    SELECT
        w.id AS org_id,
        w.name AS agency_name,
        NULLIF(TRIM(gb."Address"), '')  AS street,
        NULLIF(TRIM(gb."City"), '')     AS city,
        NULLIF(TRIM(gb."State"), '')    AS state,
        NULLIF(TRIM(gb."Zip Code"), '') AS zip
    FROM wegov_orgs w
    JOIN nycgreenbook gb ON gb."wegov-org-id" = w.id::text
    WHERE w.type IN (__GOV_TYPES__)
),
grouped AS (
    SELECT org_id, agency_name, street, city, state, zip, count(*) AS n
    FROM addr
    WHERE street IS NOT NULL
    GROUP BY org_id, agency_name, street, city, state, zip
),
modal AS (
    SELECT DISTINCT ON (org_id)
        org_id, agency_name, street, city, state, zip, n
    FROM grouped
    ORDER BY org_id, n DESC, (zip IS NOT NULL) DESC, (city IS NOT NULL) DESC, length(street) DESC
)
INSERT INTO agency_contact_enrichment
    (org_id, agency_name, address, address_source, address_rows, derived_at, curated)
SELECT
    org_id, agency_name,
    TRIM(BOTH ', ' FROM CONCAT_WS(', ', street, city, TRIM(CONCAT_WS(' ', state, zip)))),
    'nycgreenbook', n, now(), false
FROM modal
ON CONFLICT (org_id) DO UPDATE SET
    agency_name    = EXCLUDED.agency_name,
    address        = EXCLUDED.address,
    address_source = EXCLUDED.address_source,
    address_rows   = EXCLUDED.address_rows,
    derived_at     = now()
WHERE agency_contact_enrichment.curated = false
"""


async def derive_agency_enrichment_hook(conn: asyncpg.Connection):
    """Rebuild agency_head_enrichment + agency_contact_enrichment from nycgreenbook.

    Registered in POST_INGEST_HOOKS["nycgreenbook"]. Ensures the tables exist
    (safe on a fresh box), then re-derives both — curated rows are preserved.
    """
    for label, ddl, derive in (
        ("agency_head_enrichment", _HEAD_DDL, _HEAD_DERIVE),
        ("agency_contact_enrichment", _CONTACT_DDL, _CONTACT_DERIVE),
    ):
        try:
            await conn.execute(ddl)
            # __GOV_TYPES__ is substituted here rather than at module scope
            # because these SQL bodies contain regex metacharacters that make
            # f-strings and .format() hazardous. See _GOV_TYPES_SQL.
            await conn.execute(derive.replace("__GOV_TYPES__", _GOV_TYPES_SQL))
            n = await conn.fetchval(f"SELECT count(*) FROM {label}")
            print(f"[enrich_agency] ✓ {label}: {n} rows")
        except Exception as e:
            print(f"[enrich_agency] ✗ {label} failed: {e}")
