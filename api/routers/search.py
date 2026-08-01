"""
Internal global search — federates ILIKE queries across the core entity tables.

Two surfaces share one set of per-type query builders (so result shaping —
URLs, the people perm-id hash — stays identical across both):
  • GET /get/search          → results grouped by type for the /search page.
  • GET /get/search/suggest  → a flat, tight, ranked list for navbar typeahead.

Each entity type is a small, independently-capped query run concurrently. One
round-trip from Laravel; querying lives here (next to the Postgres data) rather
than in Laravel or the browser. Large tables (crol, civillistactive) rely on
pg_trgm GIN indexes — see scripts/search_indexes.sql.

Upgrade path: the {groups:[...]} / {suggestions:[...]} contracts are
engine-agnostic, so the internals can move to Postgres FTS or an external index
later without touching Laravel.
"""
import asyncio
import hashlib
import logging
import re
from urllib.parse import quote

from fastapi import APIRouter, Query
from modules.postgrex.asyncmodel import PostgresModelAsync
from modules.duckpool import to_duckdb_thread
from modules import orgfilter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Search"])

PER_TYPE = 8        # results shown per type in the grouped /search preview
SUGGEST_PER_TYPE = 4  # per-type cap before the flat suggest list is trimmed
SUGGEST_TOTAL = 8     # max rows in the typeahead dropdown


def _slug(s: str) -> str:
    """Match the frontend's Str::slug used in /o/{id}-{slug}, /people/{id}-{slug}."""
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


async def _rows(sql: str, params: list) -> list:
    """Run a query, returning [] on any failure (one slow/failed type must not
    sink the whole federated search)."""
    try:
        return await PostgresModelAsync.select_safe(sql, params) or []
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[search] query failed: {exc}")
        return []


# ---- per-type query builders -------------------------------------------------
# Each takes the prepared match params + a limit and returns shaped result dicts
# ({title, url, meta, [external]}). Shared by both /get/search and the typeahead
# so a result links to the same place from either surface.
#
# Matching/ranking (Search v2): the phrase-y types match on EITHER substring
# (ILIKE, kept for recall on fragments + codes + typo-trgm) OR full-text
# (to_tsvector @@ websearch_to_tsquery, for word-order independence + stemming),
# then rank exact > prefix > ts_rank. The to_tsvector(...) expressions are kept
# byte-identical to the expression GIN indexes (main.py SEARCH_INDEXES /
# scripts/search_fts_indexes.sql) so the planner uses them. People stay
# substring-only — English stemming/ranking hurts proper names.

_HAS_DISPLAY_NAME = None


async def _has_display_name() -> bool:
    """Probe once for `wegov_orgs.display_name` — same reasoning as orgfilter."""
    global _HAS_DISPLAY_NAME
    if _HAS_DISPLAY_NAME is None:
        rows = await _rows(
            "SELECT 1 AS ok FROM information_schema.columns "
            "WHERE table_name = 'wegov_orgs' AND column_name = 'display_name'", [])
        _HAS_DISPLAY_NAME = bool(rows)
    return _HAS_DISPLAY_NAME


async def _orgs(like, term, prefix, limit):
    # Retired (merged-away) orgs must not surface here. The clause is probed
    # once — inlining it would make this group silently return [] on a database
    # without the column, because _rows() swallows the error (cf. #146).
    live = await orgfilter.live_clause(lambda sql: _rows(sql, []))
    # `display_name` holds NYC's official name where it differs from ours (see
    # adopt_nyc_orgs.py). It is shown as the title and matched on for recall, but
    # the URL slug stays derived from `name` so existing links do not move.
    # COALESCE'd rather than assumed present: a database that has not run the
    # adoption has no such column, and _rows() swallows the error into [] — the
    # orgs group would go silently empty (#146).
    dn = "display_name" if await _has_display_name() else "NULL::text"
    rows = await _rows(f"""
        WITH q AS (SELECT plainto_tsquery('english', $5) AS tsq)
        SELECT id, name, type, {dn} AS display_name,
               ts_rank(to_tsvector('english', name), q.tsq) AS rnk
        FROM wegov_orgs, q
        WHERE (name ILIKE $1 OR "alternate_name" ILIKE $1
           OR {dn} ILIKE $1
           OR to_tsvector('english', name) @@ q.tsq
           OR to_tsvector('english', "alternate_name") @@ q.tsq){live}
        ORDER BY (name ILIKE $2) DESC, (name ILIKE $3) DESC, rnk DESC NULLS LAST, length(name)
        LIMIT $4
    """, [like, term, prefix, limit, term])
    return [{"title": r.get("display_name") or r["name"],
             "url": f"/o/{r['id']}-{_slug(r['name'])}",
             "meta": r.get("type") or "Organization"} for r in rows]


async def _titles(like, term, prefix, limit):
    rows = await _rows("""
        WITH q AS (SELECT plainto_tsquery('english', $5) AS tsq)
        SELECT "Title Code" AS code, "Title Description" AS descr,
               "Minimum Salary Rate" AS minr, "Maximum Salary Rate" AS maxr,
               ts_rank(to_tsvector('english', "Title Description"), q.tsq) AS rnk
        FROM nyccivilservicetitles, q
        WHERE "Title Description" ILIKE $1 OR "Title Code" ILIKE $1
           OR to_tsvector('english', "Title Description") @@ q.tsq
        ORDER BY ("Title Description" ILIKE $2) DESC, ("Title Description" ILIKE $3) DESC,
                 rnk DESC NULLS LAST
        LIMIT $4
    """, [like, term, prefix, limit, term])
    out = []
    for r in rows:
        meta = f"Civil Service Title · Code {r['code']}"
        out.append({"title": r["descr"] or r["code"], "url": f"/t/{r['code']}", "meta": meta})
    return out


async def _contracts(like, term, prefix, limit):
    rows = await _rows("""
        WITH q AS (SELECT plainto_tsquery('english', $4) AS tsq)
        SELECT ctr_id, contract_id, contract_title, vendor_name, agency,
               ts_rank(to_tsvector('english', contract_title), q.tsq) AS rnk
        FROM contracts, q
        WHERE contract_title ILIKE $1 OR vendor_name ILIKE $1 OR contract_id ILIKE $1
           OR to_tsvector('english', contract_title) @@ q.tsq
        ORDER BY (contract_title ILIKE $2) DESC, rnk DESC NULLS LAST
        LIMIT $3
    """, [like, prefix, limit, term])
    out = []
    for r in rows:
        title = r.get("contract_title") or r.get("contract_id") or "Contract"
        meta = " · ".join(x for x in ["Contract", r.get("vendor_name"), r.get("agency")] if x)
        out.append({"title": title, "url": f"/procurement/contract/{r['ctr_id']}", "meta": meta})
    return out


async def _solicitations(like, term, prefix, limit):
    rows = await _rows("""
        WITH q AS (SELECT plainto_tsquery('english', $3) AS tsq)
        SELECT "Procurement Name" AS name, "EPIN" AS epin, "Agency" AS agency,
               "RFx Status" AS status,
               ts_rank(to_tsvector('english', "Procurement Name"), q.tsq) AS rnk
        FROM solicitations, q
        WHERE "Procurement Name" ILIKE $1 OR "EPIN" ILIKE $1
           OR to_tsvector('english', "Procurement Name") @@ q.tsq
        ORDER BY ("Procurement Name" ILIKE $1) DESC, rnk DESC NULLS LAST
        LIMIT $2
    """, [like, limit, term])
    out = []
    for r in rows:
        meta = " · ".join(x for x in ["Solicitation", r.get("agency"), r.get("status")] if x)
        out.append({"title": r["name"] or r.get("epin") or "Solicitation",
                    "url": "/procurement/solicitations", "meta": meta})
    return out


async def _schools(like, term, prefix, limit):
    rows = await _rows("""
        WITH q AS (SELECT plainto_tsquery('english', $4) AS tsq)
        SELECT location_code AS code, location_name AS name,
               "location_type_description" AS typ,
               ts_rank(to_tsvector('english', location_name), q.tsq) AS rnk
        FROM schoollocations, q
        WHERE location_name ILIKE $1
           OR to_tsvector('english', location_name) @@ q.tsq
        ORDER BY (location_name ILIKE $2) DESC, rnk DESC NULLS LAST
        LIMIT $3
    """, [like, prefix, limit, term])
    return [{"title": r["name"], "url": f"/s/{r['code']}-{_slug(r['name'])}",
             "meta": " · ".join(x for x in ["School", r.get("typ")] if x)} for r in rows]


async def _projects(like, term, prefix, limit):
    rows = await _rows("""
        WITH q AS (SELECT plainto_tsquery('english', $3) AS tsq)
        SELECT maprojid, description, magencyname,
               ts_rank(to_tsvector('english', description), q.tsq) AS rnk
        FROM capitalprojectslist, q
        WHERE description ILIKE $1 OR projectid ILIKE $1
           OR to_tsvector('english', description) @@ q.tsq
        ORDER BY (description ILIKE $1) DESC, rnk DESC NULLS LAST
        LIMIT $2
    """, [like, limit, term])
    return [{"title": r.get("description") or r["maprojid"],
             "url": f"/p/{r['maprojid']}",
             "meta": " · ".join(x for x in ["Capital Project", r.get("magencyname")] if x)}
            for r in rows]


async def _notices(like, term, prefix, limit):
    # crol is 1M+ rows; both the ILIKE (trgm) and @@ (fts) clauses are index-backed.
    # Rank by relevance first, then recency among equally-relevant notices.
    rows = await _rows("""
        WITH q AS (SELECT plainto_tsquery('english', $3) AS tsq)
        SELECT "RequestID" AS rid, "ShortTitle" AS title,
               "AgencyName" AS agency, "TypeOfNoticeDescription" AS typ,
               ts_rank(to_tsvector('english', "ShortTitle"), q.tsq) AS rnk
        FROM crol, q
        WHERE "ShortTitle" ILIKE $1
           OR to_tsvector('english', "ShortTitle") @@ q.tsq
        ORDER BY rnk DESC NULLS LAST, start_date_parsed DESC NULLS LAST
        LIMIT $2
    """, [like, limit, term])
    return [{"title": r.get("title") or "Notice",
             "url": f"https://a856-cityrecord.nyc.gov/RequestDetail/{r['rid']}",
             "external": True,
             "meta": " · ".join(x for x in ["Notice", r.get("agency"), r.get("typ")] if x)}
            for r in rows]


async def _people(like, term, prefix, limit):
    # Search the small, fast authoritative sources for the preview; the
    # dedicated /people/search page covers the 3M+/6M+ historical tables.
    rows = await _rows("""
        SELECT TRIM("First Name" || ' ' || "Last Name") AS fullname,
               COALESCE("List Agency Desc", '') AS org, "Published Date" AS dt,
               'civillistactive' AS tbl
        FROM civillistactive
        WHERE ("First Name" || ' ' || "Last Name") ILIKE $1
        LIMIT $2
        UNION ALL
        SELECT TRIM("First Name" || ' ' || "Last Name") AS fullname,
               COALESCE("wegov-org-name", '') AS org, '' AS dt,
               'nycgreenbook' AS tbl
        FROM nycgreenbook
        WHERE ("First Name" || ' ' || "Last Name") ILIKE $1
        LIMIT $2
    """, [like, limit])
    prefixes = {'civillistactive': 'cla', 'nycgreenbook': 'gb'}
    out = []
    for r in rows:
        # perm-id MUST match search_people()'s scheme so the person page resolves.
        key = f"{r['fullname']}|{r['dt']}|{r['org']}|{r['tbl']}"
        h = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)
        pid = prefixes.get(r['tbl'], 'xx') + str(h)
        out.append({"title": r["fullname"],
                    "url": f"/people/{pid}-{_slug(r['fullname'])}",
                    "meta": " · ".join(x for x in ["Person", r.get("org")] if x)})
    return out


# NYCHA vendors live in the DuckDB lake (not Postgres) — a separate authority
# whose vendors have no City PASSPort row. Federate them so a search finds e.g.
# ADAMS EUROPEAN CONTRACTING (a top NYCHA vendor with no City profile). Matched
# vendors link to the City profile; unmatched to the NYCHA-native profile.
_NYCHA_SLUG = "170020034-nyc-housing-authority"


async def _nycha_vendors(like, term, prefix, limit):
    from routers import nycha  # lazy: avoid import cycle; DuckDB-backed
    rows = await to_duckdb_thread(nycha.search_vendors, term, limit)
    out = []
    for r in rows:
        name = r.get("vendor") or ""
        if r.get("vendor_id"):
            url = f"/procurement/vendor/{r['vendor_id']}"
        else:
            url = f"/o/{_NYCHA_SLUG}/procurement-nycha-vendor?name={quote(name)}"
        n = r.get("contracts") or 0
        meta = "NYCHA Vendor" + (f" · {n} contract{'' if n == 1 else 's'}" if n else "")
        out.append({"title": name, "url": url, "meta": meta})
    return out


# (key, label, builder) — order is also the typeahead's type-priority order.
GROUPS_DEF = [
    ("organizations", "Organizations", _orgs),
    ("people", "People", _people),
    ("titles", "Civil Service Titles", _titles),
    ("contracts", "Contracts", _contracts),
    ("nycha_vendors", "NYCHA Vendors", _nycha_vendors),
    ("solicitations", "Solicitations", _solicitations),
    ("projects", "Capital Projects", _projects),
    ("schools", "Schools", _schools),
    ("notices", "Notices", _notices),
]

# Typeahead surfaces only types that resolve to a real on-site detail page —
# excludes solicitations (link to a list, not a row) and notices (external).
SUGGEST_KEYS = {"organizations", "people", "titles", "contracts", "nycha_vendors", "projects", "schools"}


def _prep(q: str):
    """Normalize the raw query → (term, like, prefix) or None if too short."""
    term = re.sub(r"\s+", " ", (q or "").replace("+", " ")).strip()
    if len(term) < 2:
        return None
    return term, f"%{term}%", f"{term}%"


@router.get("/get/search")
async def global_search(q: str = Query("", description="search term"),
                        type: str = Query("all")):
    prep = _prep(q)
    if not prep:
        return {"query": (q or "").strip(), "total": 0, "groups": []}
    term, like, prefix = prep

    wanted = GROUPS_DEF if type == "all" else [g for g in GROUPS_DEF if g[0] == type]
    results = await asyncio.gather(*(fn(like, term, prefix, PER_TYPE) for _, _, fn in wanted))

    groups, total = [], 0
    for (key, label, _), res in zip(wanted, results):
        if res:
            total += len(res)
            groups.append({"type": key, "label": label, "count": len(res), "results": res})
    return {"query": term, "total": total, "groups": groups}


@router.get("/get/search/suggest")
async def suggest(q: str = Query("", description="search term")):
    """Navbar typeahead: a single flat, ranked list capped at SUGGEST_TOTAL.

    Each type contributes up to SUGGEST_PER_TYPE rows; we then interleave in
    type-priority order (orgs, people, titles, …) so the dropdown leads with the
    most navigationally useful matches rather than dumping one type."""
    prep = _prep(q)
    if not prep:
        return {"query": (q or "").strip(), "suggestions": []}
    term, like, prefix = prep

    wanted = [(key, label, fn) for key, label, fn in GROUPS_DEF if key in SUGGEST_KEYS]
    results = await asyncio.gather(
        *(fn(like, term, prefix, SUGGEST_PER_TYPE) for _, _, fn in wanted))

    # Tag each row with its type, then round-robin across types so no single
    # type crowds out the rest before the total cap is hit.
    buckets = []
    for (key, label, _), res in zip(wanted, results):
        buckets.append([{**row, "type": key, "type_label": label} for row in res])

    suggestions = []
    for i in range(SUGGEST_PER_TYPE):
        for bucket in buckets:
            if i < len(bucket):
                suggestions.append(bucket[i])
            if len(suggestions) >= SUGGEST_TOTAL:
                break
        if len(suggestions) >= SUGGEST_TOTAL:
            break

    return {"query": term, "suggestions": suggestions}
