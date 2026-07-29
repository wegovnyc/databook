"""Post-ingest hook: load the MOCS Doing Business Database (Local Law 34).

Two NYC Open Data sets published by the Mayor's Office of Contract Services:

    72mk-a8z7  Doing Business Search - Entities   10,787 organizations
    2sps-j9st  Doing Business Search - People     60,545 named principals

LL34 (2007) caps municipal campaign contributions from the principal officers,
owners and senior managers of entities doing business with the City, and
mandates this database so the City can enforce it. It carries two things the
PASSPort vendor sub-tables (api/enrich_vendor.py) do not:

  * **registered lobbyists** (3,094 rows) — absent from PASSPort entirely;
  * an **independently maintained** view of who runs a company, collected for
    enforcement rather than self-disclosed during vendor registration. For a
    transparency product, corroboration from a second custodian is the point.

Joining
-------
⚠ There is NO id and NO EIN — the only join key is the organization NAME. We
therefore link conservatively (see build_crosswalk): exact normalized-name
matches, plus exact matches against the DBA / trade names PASSPort itself
publishes in `vendor_other_names`. Near-misses are STORED BUT NOT LINKED, in
the `fuzzy-review` tier, for the same human-review treatment the NYCHA vendor
crosswalk got (#145/#155). Attaching a named individual to the wrong company is
a much worse error here than missing a link.

Measured against prod 2026-07-27: 5,010 of 10,763 entities (46.6%) match a
PASSPort vendor exactly, +66 via DBA aliases, carrying 31,874 people rows and
giving 4,474 of 36,335 vendors (12.3%) a Doing Business panel.

Two source defects, both handled here
-------------------------------------
1. ⚠ **Every date is corrupt at source.** They arrive as `0017-07-01`, i.e. the
   century is missing; the range is 0008-0024 and LL34 began in 2007, so +2000
   recovers them exactly. `repair_year` does that and keeps the raw value so
   the damage stays auditable. Never display the raw date.
2. ⚠ **The feed is stale.** `rowsUpdatedAt` has read 2025-11-21 since at least
   2026-07-27 despite the dataset advertising "Update Frequency: Monthly,
   Automation: Yes" — 8 months. We record that timestamp as the vintage and the
   UI labels it, rather than implying the panel is current.

Role codes
----------
⚠ MOCS publishes `relationship_type_code` with **no public dictionary**. The
dataset's own attached data dictionary says only "stakeholder type: CFO, COO,
Owner, etc"; the LL34 Q&A, the Doing Business Data Form and the database
removal form define the *categories* but never the codes. Checked 2026-07-27.

So we label only what is documented or demonstrable, and pass everything else
through as its raw code rather than inventing a meaning:

  documented   CEO / CFO / COO   principal officers, named in the LL34 Q&A
               OWN               "Owner" per the attached data dictionary
               LOB               lobbyist, a category named in LL34
  demonstrated EWN               an ORGANIZATION that owns >=10%, not a person:
                                 99.9% have no first name and the surname field
                                 holds corporate names (GOLDMAN SACHS, NORTHERN
                                 TRUST CORPORATION, KRM 2021 IRREVOCABLE TRUST).
                                 Matches the form's "NEW FOR 2018: the DBDF must
                                 report organizations, as well as individuals,
                                 that own 10% or more". These must never be
                                 rendered as people.
  grouped only MCT MRP MPI MED   89.3% of organizations carry at least one, and
               MLU MFC MGR       LL34 requires at least one senior manager per
                                 entity, so they are grouped as "Senior manager"
                                 — but the per-code meaning (they look like
                                 transaction types) is NOT documented and is not
                                 asserted. The raw code is shown alongside.
  unknown      POL and anything else — shown as the raw code only.

If MOCS ever publishes the dictionary, extend _ROLES; nothing else changes.
"""

import csv
import io
import os
import re
from datetime import datetime, timezone

import aiohttp
import asyncpg

SOCRATA_BASE = os.environ.get("SOCRATA_BASE", "https://data.cityofnewyork.us")
ENTITIES_ID = "72mk-a8z7"
PEOPLE_ID = "2sps-j9st"

BATCH = 2000
PAGE = 50000  # SODA's per-request ceiling

# Role code -> (label, group, is_organization). Only documented or demonstrated
# meanings appear here; see the module docstring. Unlisted codes fall through to
# ("", "Other", False) and are rendered as the bare code.
_ROLES = {
    "CEO": ("Chief Executive Officer", "Principal officer", False),
    "CFO": ("Chief Financial Officer", "Principal officer", False),
    "COO": ("Chief Operating Officer", "Principal officer", False),
    "OWN": ("Owner", "Owner", False),
    "LOB": ("Lobbyist", "Lobbyist", False),
    "EWN": ("Owner (organization)", "Owner", True),
}
# Grouped as senior managers, but deliberately given no per-code label.
_SENIOR_MANAGER_CODES = {"MCT", "MRP", "MPI", "MED", "MLU", "MFC", "MGR"}

# From the dataset's own attached data dictionary. ⚠ It is out of sync with the
# data: it lists Joint Venture as "JV" while the feed sends "JNT", and the feed
# also carries IND / GOV which the dictionary never mentions. Undocumented codes
# are passed through raw rather than guessed.
_OWNERSHIP = {
    "COR": "Business Corporation",
    "PRO": "Sole Proprietorship",
    "PAR": "Partnership",
    "LLC": "Limited Liability Company",
    "JV": "Joint Venture",
    "OTH": "Other",
}


def norm_name(value) -> str:
    """[A-Z0-9] skeleton — the same key shape used by enrich_vendor and _sbs_profile."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", value.upper())


def repair_year(value):
    """Repair MOCS's century-less dates: '0017-07-01T00:00:00.000' -> '2017-07-01'.

    Every date in both feeds is missing its century. Observed years span 0008 to
    0024 and Local Law 34 took effect in 2007, so +2000 is unambiguous. Anything
    already sane is passed through; anything unparseable returns None rather
    than a fabricated date.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    m = re.match(r"^(\d{1,4})-(\d{2})-(\d{2})", value.strip())
    if not m:
        return None
    year, month, day = int(m.group(1)), m.group(2), m.group(3)
    if year < 100:
        year += 2000
    if not (1900 <= year <= 2100):
        return None
    return f"{year:04d}-{month}-{day}"


def role_of(code):
    """(label, group, is_organization) for a relationship_type_code."""
    c = (code or "").strip().upper()
    if c in _ROLES:
        return _ROLES[c]
    if c in _SENIOR_MANAGER_CODES:
        return ("", "Senior manager", False)
    return ("", "Other", False)


def ownership_label(code):
    """Human label for ownership_structure_code, or '' when undocumented.

    ⚠ The feed carries case duplicates ('cor'/'COR', 'llc'/'LLC'), so uppercase
    before looking up.
    """
    return _OWNERSHIP.get((code or "").strip().upper(), "")


_ENTITIES_DDL = """
CREATE TABLE IF NOT EXISTS doing_business_entities (
    organization_name        text,
    org_name_norm            text,
    ownership_structure_code text,
    ownership_structure      text,
    organization_phone       text,
    start_date               text,
    start_date_raw           text
)
"""

_PEOPLE_DDL = """
CREATE TABLE IF NOT EXISTS doing_business_people (
    mocs_people_id    text,
    organization_name text,
    org_name_norm     text,
    full_name         text,
    first_name        text,
    middle_name       text,
    last_name         text,
    suffix            text,
    role_code         text,
    role_label        text,
    role_group        text,
    is_organization   boolean,
    start_date        text,
    end_date          text
)
"""

_XWALK_DDL = """
CREATE TABLE IF NOT EXISTS doing_business_crosswalk (
    org_name_norm          text PRIMARY KEY,
    organization_name      text,
    passport_supplier_id   text,
    candidate_supplier_id  text,
    candidate_vendor_name  text,
    confidence             text,
    match_score            real,
    source                 text DEFAULT 'doing_business',
    derived_at             timestamptz DEFAULT now(),
    curated                boolean DEFAULT false,
    curated_note           text
)
"""

_INDEXES = [
    ("idx_db_entities_norm", "doing_business_entities", "org_name_norm"),
    ("idx_db_people_norm", "doing_business_people", "org_name_norm"),
    ("idx_db_xwalk_supplier", "doing_business_crosswalk", "passport_supplier_id"),
]


async def _fetch_rows(session, dataset_id: str) -> list:
    """Page the SODA endpoint and return list[dict]. Raises on a bad response."""
    out = []
    offset = 0
    while True:
        url = (f"{SOCRATA_BASE}/resource/{dataset_id}.csv"
               f"?$limit={PAGE}&$offset={offset}&$order=:id")
        timeout = aiohttp.ClientTimeout(total=600, sock_read=120)
        async with session.get(url, timeout=timeout) as resp:
            if resp.status != 200:
                raise RuntimeError(f"{dataset_id}: HTTP {resp.status}")
            text = await resp.text()
        rows = list(csv.DictReader(io.StringIO(text)))
        out.extend(rows)
        if len(rows) < PAGE:
            return out
        offset += PAGE


async def _vintage(session, dataset_id: str) -> str:
    """The feed's own rowsUpdatedAt as YYYY-MM-DD ('' if unavailable).

    Used both as the skip signal and as the "as of" date shown to users — this
    dataset claims monthly updates but has not moved since 2025-11-21.
    """
    try:
        async with session.get(f"{SOCRATA_BASE}/api/views/{dataset_id}.json",
                               timeout=aiohttp.ClientTimeout(total=60)) as r:
            if r.status != 200:
                return ""
            meta = await r.json()
    except Exception:  # noqa: BLE001
        return ""
    ts = meta.get("rowsUpdatedAt")
    if not isinstance(ts, int):
        return ""
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


async def _swap(conn, table: str, ddl: str, columns: list, records: list) -> int:
    """Stage into a temp table and swap atomically; refuse a >50% row drop."""
    live = 0
    await conn.execute(ddl)
    try:
        live = await conn.fetchval(f"SELECT count(*) FROM {table}")
    except Exception:  # noqa: BLE001
        live = 0
    if not records:
        raise RuntimeError("parsed 0 rows")
    if live > 0 and len(records) < live * 0.5:
        raise RuntimeError(f"refusing swap: {len(records)} rows vs {live} live (>50% drop)")

    staging = f"_staging_{table}"
    await conn.execute(f"DROP TABLE IF EXISTS {staging}")
    await conn.execute(ddl.replace(
        f"CREATE TABLE IF NOT EXISTS {table}", f"CREATE TABLE {staging}", 1))
    for i in range(0, len(records), BATCH):
        await conn.copy_records_to_table(
            staging, records=records[i:i + BATCH], columns=columns)
    async with conn.transaction():
        await conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        await conn.execute(f"ALTER TABLE {staging} RENAME TO {table}")
    return len(records)


async def build_crosswalk(conn) -> dict:
    """Link Doing Business organizations to PASSPort vendors by name.

    Conservative by design — see the module docstring. Tiers:

      curated       human-set, never overwritten (a NULL supplier id is a
                    reviewed "no match" and keeps the row out of the queue,
                    the same marker the NYCHA crosswalk uses)
      exact         normalized organization name == normalized vendor name
      exact-dba     == a DBA / trade name PASSPort publishes for that vendor
                    in vendor_other_names (loaded by enrich_vendor.py)
      fuzzy-review  stored, NOT linked; awaiting human review

    Rebuilt from scratch each run except for curated rows, because an
    upsert-only generator silently preserves corrected false positives (#149).
    """
    await conn.execute(_XWALK_DDL)
    # CREATE TABLE IF NOT EXISTS is a no-op on an existing table, so a column
    # added to _XWALK_DDL later would silently never appear on a box that
    # already ran an older build. Curated rows make dropping the table
    # unacceptable, so bring the schema forward explicitly instead.
    for col, typ in (("candidate_supplier_id", "text"),
                     ("candidate_vendor_name", "text"),
                     ("curated_note", "text")):
        await conn.execute(
            f"ALTER TABLE doing_business_crosswalk ADD COLUMN IF NOT EXISTS {col} {typ}")
    await conn.execute("DELETE FROM doing_business_crosswalk WHERE curated = false")

    # exact — on the vendor's own name.
    exact = await conn.execute("""
        INSERT INTO doing_business_crosswalk
            (org_name_norm, organization_name, passport_supplier_id, confidence, match_score, derived_at)
        SELECT DISTINCT ON (e.org_name_norm)
               e.org_name_norm, e.organization_name, v."PASSPort Supplier-ID", 'exact', 1.0, now()
        FROM doing_business_entities e
        JOIN vendors v
          ON upper(regexp_replace(v."Vendor Name", '[^A-Za-z0-9]', '', 'g')) = e.org_name_norm
        WHERE e.org_name_norm <> ''
        ORDER BY e.org_name_norm, v."PASSPort Supplier-ID"
        ON CONFLICT (org_name_norm) DO NOTHING
    """)

    # exact-dba — PASSPort's own alias list. Firms register under a formal name
    # and file Doing Business forms under a trade name (the same mismatch the
    # SBS panel hit in #158).
    dba = await conn.execute("""
        INSERT INTO doing_business_crosswalk
            (org_name_norm, organization_name, passport_supplier_id, confidence, match_score, derived_at)
        SELECT DISTINCT ON (e.org_name_norm)
               e.org_name_norm, e.organization_name, v."PASSPort Supplier-ID", 'exact-dba', 0.99, now()
        FROM doing_business_entities e
        JOIN vendor_other_names o
          ON upper(regexp_replace(o.other_name, '[^A-Za-z0-9]', '', 'g')) = e.org_name_norm
        JOIN vendors v
          ON o.vendor_name_norm = upper(regexp_replace(v."Vendor Name", '[^A-Za-z0-9]', '', 'g'))
        WHERE e.org_name_norm <> ''
        ORDER BY e.org_name_norm, v."PASSPort Supplier-ID"
        ON CONFLICT (org_name_norm) DO NOTHING
    """)

    # fuzzy-review — near-misses are recorded for a human, never auto-linked.
    #
    # ⚠ The candidate lands in `candidate_supplier_id`, NOT `passport_supplier_id`,
    # which stays NULL. The NYCHA crosswalk stores unreviewed candidates in the
    # real id column and relies on every consumer remembering to filter out the
    # 'fuzzy-review' tier — one missed filter silently publishes an unreviewed
    # match. Here a join on passport_supplier_id cannot go wrong.
    #
    # Reuses build_nycha_vendor_crosswalk's matcher rather than reimplementing:
    # it already carries the fixes from #148 (a token-set shortcut auto-linked
    # different firms sharing one generic token) and the distinctive-token gate.
    try:
        from build_nycha_vendor_crosswalk import _fuzzy_matches, norm as fuzzy_norm

        unmatched = [r["organization_name"] for r in await conn.fetch("""
            SELECT DISTINCT e.organization_name FROM doing_business_entities e
            WHERE e.org_name_norm <> '' AND e.organization_name IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM doing_business_crosswalk x
                              WHERE x.org_name_norm = e.org_name_norm)
        """)]
        vendors = [(fuzzy_norm(r["n"]), r["id"], r["n"]) for r in await conn.fetch(
            'SELECT "PASSPort Supplier-ID" AS id, "Vendor Name" AS n FROM vendors '
            'WHERE "Vendor Name" IS NOT NULL')]
        if unmatched and vendors:
            high, review = _fuzzy_matches(unmatched, vendors)
            # Both tiers are stored unlinked: this crosswalk auto-links exact
            # matches only. Attaching named individuals to the wrong company is
            # the failure mode to avoid.
            rows = [(norm_name(n), n, pid, pname, round(float(s), 4))
                    for n, pid, pname, s in (high + review) if norm_name(n)]
            if rows:
                await conn.executemany("""
                    INSERT INTO doing_business_crosswalk
                        (org_name_norm, organization_name, passport_supplier_id,
                         candidate_supplier_id, candidate_vendor_name,
                         confidence, match_score, derived_at)
                    VALUES ($1, $2, NULL, $3, $4, 'fuzzy-review', $5, now())
                    ON CONFLICT (org_name_norm) DO NOTHING
                """, rows)
    except Exception as e:  # noqa: BLE001 — the exact tiers must survive this
        print(f"[doing_business] · fuzzy-review pass skipped: {e}")

    linked = await conn.fetchval(
        "SELECT count(*) FROM doing_business_crosswalk WHERE passport_supplier_id IS NOT NULL")
    total = await conn.fetchval("SELECT count(*) FROM doing_business_crosswalk")
    by_tier = await conn.fetch(
        "SELECT confidence, count(*) FROM doing_business_crosswalk GROUP BY 1 ORDER BY 1")
    return {"linked": linked, "rows": total,
            "tiers": {r[0]: r[1] for r in by_tier}}


async def derive_doing_business_hook(conn: asyncpg.Connection):
    """Load both Doing Business feeds and rebuild the crosswalk.

    Registered on `vendors` — the crosswalk is name-matched against the vendor
    list, so it must be rebuilt whenever that list changes. Guarded end to end:
    this is enrichment, and a vendor profile must render without it.
    """
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS vendor_enrichment_meta (
            table_name text PRIMARY KEY, source_file text, etag text,
            last_modified text, row_count integer,
            refreshed_at timestamptz DEFAULT now())
    """)
    async with aiohttp.ClientSession() as session:
        vintage = await _vintage(session, PEOPLE_ID)
        prev = await conn.fetchrow(
            "SELECT last_modified, row_count FROM vendor_enrichment_meta "
            "WHERE table_name = 'doing_business_people'")
        live = 0
        try:
            live = await conn.fetchval("SELECT count(*) FROM doing_business_people")
        except Exception:  # noqa: BLE001
            live = 0
        # The feed has not moved since 2025-11-21; re-pulling 71k rows nightly
        # for an unchanged dataset is waste. The crosswalk is still rebuilt
        # below, because `vendors` changes daily even when this does not.
        unchanged = bool(vintage and prev and prev["last_modified"] == vintage and live > 0)

        if not unchanged:
            try:
                erows = await _fetch_rows(session, ENTITIES_ID)
                precords = await _fetch_rows(session, PEOPLE_ID)
            except Exception as e:  # noqa: BLE001
                print(f"[doing_business] ✗ fetch failed: {e}")
                return

            ents = []
            for r in erows:
                name = (r.get("organization_name") or "").strip()
                raw = (r.get("doing_business_start_date") or "").strip()
                code = (r.get("ownership_structure_code") or "").strip()
                ents.append((name, norm_name(name) or None, code or None,
                             ownership_label(code) or None,
                             (r.get("organization_phone") or "").strip() or None,
                             repair_year(raw), raw or None))

            ppl = []
            for r in precords:
                org = (r.get("organization_name") or "").strip()
                code = (r.get("relationship_type_code") or "").strip().upper()
                label, group, is_org = role_of(code)
                first = (r.get("person_name_first") or "").strip()
                mid = (r.get("person_name_middle") or "").strip()
                last = (r.get("person_name_last") or "").strip()
                suf = (r.get("person_name_suffix") or "").strip()
                full = " ".join(p for p in (first, mid, last, suf) if p)
                ppl.append((
                    (r.get("mocs_peopleid") or "").strip() or None,
                    org, norm_name(org) or None, full or None,
                    first or None, mid or None, last or None, suf or None,
                    code or None, label or None, group, is_org,
                    repair_year(r.get("doing_business_start_date")),
                    repair_year(r.get("doing_business_end_date"))))

            try:
                ne = await _swap(conn, "doing_business_entities", _ENTITIES_DDL,
                                 ["organization_name", "org_name_norm",
                                  "ownership_structure_code", "ownership_structure",
                                  "organization_phone", "start_date", "start_date_raw"],
                                 ents)
                np_ = await _swap(conn, "doing_business_people", _PEOPLE_DDL,
                                  ["mocs_people_id", "organization_name", "org_name_norm",
                                   "full_name", "first_name", "middle_name", "last_name",
                                   "suffix", "role_code", "role_label", "role_group",
                                   "is_organization", "start_date", "end_date"],
                                  ppl)
            except Exception as e:  # noqa: BLE001
                print(f"[doing_business] ✗ load failed: {e}")
                return
            print(f"[doing_business] ✓ entities {ne} · people {np_} (vintage {vintage or 'unknown'})")

            for tbl, name in (("doing_business_entities", "entities"),
                              ("doing_business_people", "people")):
                await conn.execute(
                    """INSERT INTO vendor_enrichment_meta
                           (table_name, source_file, last_modified, row_count, refreshed_at)
                       VALUES ($1, $2, $3, $4, $5)
                       ON CONFLICT (table_name) DO UPDATE SET
                           source_file = EXCLUDED.source_file,
                           last_modified = EXCLUDED.last_modified,
                           row_count = EXCLUDED.row_count,
                           refreshed_at = EXCLUDED.refreshed_at""",
                    tbl, ENTITIES_ID if name == "entities" else PEOPLE_ID, vintage,
                    ne if name == "entities" else np_, datetime.now(timezone.utc))
        else:
            print(f"[doing_business] · feeds unchanged (vintage {vintage}), {live} people rows")

    for idx, tbl, col in _INDEXES:
        try:
            await conn.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON {tbl}({col})")
        except Exception:  # noqa: BLE001 — crosswalk table may not exist yet
            pass

    try:
        stats = await build_crosswalk(conn)
        print(f"[doing_business] ✓ crosswalk: {stats['linked']} linked "
              f"of {stats['rows']} rows {stats['tiers']}")
    except Exception as e:  # noqa: BLE001
        print(f"[doing_business] ✗ crosswalk failed: {e}")
    for idx, tbl, col in _INDEXES:
        try:
            await conn.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON {tbl}({col})")
        except Exception:  # noqa: BLE001
            pass
    try:
        await conn.execute("ANALYZE doing_business_people")
        await conn.execute("ANALYZE doing_business_crosswalk")
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    # Manual / first run:  docker compose exec -T api python enrich_doing_business.py
    import asyncio

    async def _main():
        conn = await asyncpg.connect(
            host=os.environ.get("POSTGRES_HOST", "postgres"),
            user=os.environ.get("POSTGRES_USER", "postgres"),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
            database=os.environ.get("POSTGRES_DB", "databook"),
        )
        try:
            await derive_doing_business_hook(conn)
        finally:
            await conn.close()

    asyncio.run(_main())
