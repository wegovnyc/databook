"""
Public v1 REST/JSON API for external consumers (e.g. Cloudflare Workers).

Plain HTTPS JSON, server-fetchable, NO OAuth. Public by default; if the env var
DATABOOK_PUBLIC_API_KEY is set, callers must send it in the `X-API-Key` header.
Permissive CORS (Access-Control-Allow-Origin: *) + a 1h response cache, since the
underlying data refreshes daily.

Backed by the same Postgres tables the procurement MCP tools query:
wegov_orgs, contracts, solicitations, expensebudgetonnycopendata.
"""
import os
import re
import time
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response, Header
from modules.postgrex.asyncmodel import PostgresModelAsync
from modules import orgfilter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Public API v1"])

PUBLIC_BASE = "https://databook.nyc"
# If set, requests must send this value as the `X-API-Key` header; otherwise public.
_API_KEY = os.environ.get("DATABOOK_PUBLIC_API_KEY") or None

_cache: dict = {}
_CACHE_TTL = 3600          # 1 hour (data refreshes daily)
_CACHE_MAX = 2000


def _slugify(name: str) -> str:
    """Match the frontend's Str::slug for /o/{id}-{slug} links."""
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def _require_key(x_api_key: Optional[str]):
    if _API_KEY and x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def _finalize(resp: Response):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Cache-Control"] = "public, max-age=3600"


def _cache_get(key):
    e = _cache.get(key)
    return e["data"] if e and (time.time() - e["ts"]) < _CACHE_TTL else None


def _cache_put(key, data):
    if len(_cache) >= _CACHE_MAX:
        del _cache[min(_cache, key=lambda k: _cache[k]["ts"])]
    _cache[key] = {"data": data, "ts": time.time()}


def _org_url(agency_id: str, slug: str) -> str:
    return f"{PUBLIC_BASE}/o/{agency_id}-{slug}"


@router.get("/orgs/search", summary="Resolve an agency name/acronym to Databook ids")
async def orgs_search(
    response: Response,
    q: str = Query(..., min_length=1, description="Agency name or acronym, e.g. 'FDNY'"),
    limit: int = Query(20, ge=1, le=50),
    x_api_key: Optional[str] = Header(None),
):
    _require_key(x_api_key)
    _finalize(response)
    ck = f"search|{q.lower().strip()}|{limit}"
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    # Match full name OR acronym (alternate_name, e.g. FDNY/DOT/HPD). Rank exact
    # acronym matches, then name prefix, then shortest name.
    # Retired orgs are merged-away duplicates; serving one is a bug (see
    # modules/orgfilter.py).
    live = await orgfilter.live_clause(
        lambda sql: PostgresModelAsync.select_safe(sql, []))
    rows = await PostgresModelAsync.select_safe(
        f"""
        SELECT id, name, type, alternate_name
        FROM wegov_orgs
        WHERE (name ILIKE $1 OR alternate_name ILIKE $1){live}
        ORDER BY (UPPER(COALESCE(alternate_name, '')) = UPPER($3)) DESC,
                 (name ILIKE $2) DESC,
                 length(name) ASC
        LIMIT $4
        """,
        [f"%{q}%", f"{q}%", q, limit],
    )
    out = []
    for r in rows or []:
        aid, slug = str(r["id"]), _slugify(r["name"])
        out.append({
            "agency_id": aid,
            "slug": slug,
            "name": r["name"],
            "type": r.get("type"),
            "url": _org_url(aid, slug),
        })
    _cache_put(ck, out)
    return out


@router.get("/orgs/{agency_id}/summary", summary="Server-side budget + procurement aggregates")
async def org_summary(
    agency_id: str,
    response: Response,
    x_api_key: Optional[str] = Header(None),
):
    _require_key(x_api_key)
    _finalize(response)
    ck = f"summary|{agency_id}"
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    org = await PostgresModelAsync.select_safe(
        "SELECT id, name, type FROM wegov_orgs WHERE id::text = $1", [agency_id]
    )
    if not org:
        raise HTTPException(status_code=404, detail="Agency not found")
    name = org[0]["name"]
    slug = _slugify(name)

    # ---- Budget (latest fiscal year) ---------------------------------------
    budget = {"latest_fy": None, "total_adopted": 0.0, "total_modified": 0.0, "currency": "USD"}
    try:
        brow = await PostgresModelAsync.select_safe(
            """
            SELECT "Fiscal Year" AS fy,
                   COALESCE(SUM(CASE WHEN "Adopted Budget Amount" ~ '^-?[0-9]+(\\.[0-9]+)?$' THEN "Adopted Budget Amount"::numeric ELSE 0 END), 0) AS adopted,
                   COALESCE(SUM(CASE WHEN "Current Modified Budget Amount" ~ '^-?[0-9]+(\\.[0-9]+)?$' THEN "Current Modified Budget Amount"::numeric ELSE 0 END), 0) AS modified
            FROM expensebudgetonnycopendata
            WHERE "Agency Name" ILIKE $1
              AND "Fiscal Year" = (SELECT MAX("Fiscal Year") FROM expensebudgetonnycopendata WHERE "Agency Name" ILIKE $1)
            GROUP BY "Fiscal Year"
            """,
            [f"%{name}%"],
        )
        if brow:
            budget["latest_fy"] = brow[0]["fy"]
            budget["total_adopted"] = float(brow[0]["adopted"] or 0)
            budget["total_modified"] = float(brow[0]["modified"] or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[public_v1] budget query failed for {name!r}: {exc}")

    # ---- Contracts ---------------------------------------------------------
    crow = await PostgresModelAsync.select_safe(
        """SELECT COUNT(*) AS count,
                  COALESCE(SUM(current_amount), 0) AS total_current,
                  COALESCE(SUM(award_amount), 0)   AS total_award
           FROM contracts WHERE LOWER(TRIM(agency)) = LOWER(TRIM($1))""",
        [name],
    )
    top_vendors = await PostgresModelAsync.select_safe(
        """SELECT vendor_name AS name, COALESCE(SUM(award_amount), 0) AS total
           FROM contracts
           WHERE LOWER(TRIM(agency)) = LOWER(TRIM($1))
             AND vendor_name IS NOT NULL AND vendor_name <> ''
           GROUP BY vendor_name ORDER BY total DESC LIMIT 5""",
        [name],
    )
    fy_spend = await PostgresModelAsync.select_safe(
        """SELECT EXTRACT(YEAR FROM TO_DATE(start_date, 'MM/DD/YYYY'))::INT AS fy,
                  COALESCE(SUM(award_amount), 0) AS total
           FROM contracts
           WHERE LOWER(TRIM(agency)) = LOWER(TRIM($1))
             AND start_date IS NOT NULL AND start_date <> ''
           GROUP BY 1 ORDER BY fy""",
        [name],
    )
    contracts = {
        "count": (crow[0]["count"] if crow else 0),
        "total_current_amount": float(crow[0]["total_current"] or 0) if crow else 0.0,
        "total_award_amount": float(crow[0]["total_award"] or 0) if crow else 0.0,
        "top_vendors": [{"name": r["name"], "total": float(r["total"] or 0)} for r in (top_vendors or [])],
        "fy_spend": [{"fy": r["fy"], "total": float(r["total"] or 0)} for r in (fy_spend or []) if r.get("fy") and float(r["total"] or 0) > 0],
    }

    # ---- Solicitations -----------------------------------------------------
    open_row = await PostgresModelAsync.select_safe(
        """SELECT COUNT(*) AS c FROM solicitations
           WHERE LOWER(TRIM("Agency")) = LOWER(TRIM($1)) AND "RFx Status" ILIKE 'Released'""",
        [name],
    )
    recent = await PostgresModelAsync.select_safe(
        """SELECT "EPIN" AS epin, "Procurement Name" AS procurement_name,
                  "Due Date" AS due_date, "RFx Status" AS rfx_status
           FROM solicitations WHERE LOWER(TRIM("Agency")) = LOWER(TRIM($1))
           ORDER BY "Release Date" DESC LIMIT 5""",
        [name],
    )
    solicitations = {
        "open_count": (open_row[0]["c"] if open_row else 0),
        "recent": [{
            "epin": r["epin"],
            "procurement_name": r["procurement_name"],
            "due_date": r["due_date"],
            "rfx_status": r["rfx_status"],
            "url": f"{PUBLIC_BASE}/procurement/solicitation/{r['epin']}",
        } for r in (recent or [])],
    }

    result = {
        "agency_id": str(org[0]["id"]),
        "name": name,
        "slug": slug,
        "url": _org_url(str(org[0]["id"]), slug),
        # Canonical agency procurement section (orgSection uses the -highlights suffix).
        "procurement_url": f"{PUBLIC_BASE}/o/{org[0]['id']}-{slug}/procurement-highlights",
        "budget": budget,
        "contracts": contracts,
        "solicitations": solicitations,
    }
    _cache_put(ck, result)
    return result
