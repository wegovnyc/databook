"""Editing surface for the org register — the API half of Phase 5.

Phase 5 of docs/ORG-DIRECTORY-OF-RECORD-PLAN.md. `wegov_orgs` has been the
system of record since Phase 2 and has NEVER been editable by a human: it is
`source_type='internal'`, created outside the pipeline, with no CRUD path and no
audit trail. Every change so far has been a hand-written migration script.

BUILT API-FIRST, DELIBERATELY
=============================
The UI is a separate change that consumes these endpoints. The invariants below
must hold for ANY client — a screen, a curl, a bulk script — so they live here
rather than in a form. It also means the audit trail and scripted bulk edits
exist before a single pixel does.

THE FIVE INVARIANTS, EACH FROM A REAL FAILURE
=============================================
1. **`type` is constrained to the vocabulary in `modules/orgfilter.py`.** Free
   text is exactly how a mixed vocabulary silently broke FOUR filters when the
   OTI adoption retyped 240 orgs (#173/#177) — including a page that rendered 28
   rows instead of 270 while its stat tile agreed with the wrong number.
2. **Renaming `name` requires explicit confirmation, and the response states the
   blast radius.** `name` is a JOIN KEY, not a label: `oce.py::_resolve_org_id`
   matches `contracts.agency` against it by `UPPER(TRIM(...))` equality, and the
   org page passes it to `/oce/agency/summary?name=`. Renaming `Fire Department`
   to `Fire Department of the City of New York` would match ZERO contracts and
   silently zero the procurement figures on that profile. OTI's official name
   belongs in `display_name`, which is freely editable.
3. **A parent may not create a cycle.** `App\Custom\OrgChart::packnode` recurses
   through children with no depth guard, so a cycle would not "look wrong" — it
   would blow the stack and 500 the whole org chart.
4. **Retirement, never deletion.** Retiring is additive (`retired_at` +
   `merged_into`) and therefore reversible, and it keeps every one of the 3,700
   org match rows and every ingested `wegov-org-id` resolving. A DELETE would
   orphan them silently. `DELETE` is answered with 405 and an explanation.
5. **Unknown fields are rejected, not ignored.** Silently dropping an
   unrecognised field is how this codebase repeatedly shipped a change that
   "succeeded" and did nothing.

⚠ AUTH — the plan's assumption was WRONG and this is worth reading. It said
"Cloudflare Access from Phase 0 covers it". It does not: Phase 0 put **nginx
basic auth on the normalizer's vhost**, a different host, and task `dda13bf3`
records that the origin answers direct connections so any Cloudflare-layer
policy is bypassable anyway. These endpoints therefore carry their own
origin-level control: a valid JWT (the existing `fastapi_login` manager over the
`users` table) whose user row has an editor `scope`, or the internal machine key
for scripted use — sent as the **`X-API-Key` header**, never `?api_key=` (see
`modules/apikey.py`: uvicorn logs the full request line, so the query form
published the secret to the container log). Phase 0's real lesson was that the
control must live at the origin — application auth is at the origin.

⚠ `Security(manager, scopes=['write'])` is deliberately NOT used, even though
four other endpoints use it: `/login` mints `scopes=['read']` hardcoded, so a
write-scoped dependency cannot be satisfied by any token it issues. Authorising
on the user row's `scope` column works today and does not widen what an existing
token can reach. See the note in the module for the separate finding.
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse

from postgrex import PostgresModelAsync

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'modules'))

try:
    from modules import orgfilter
except ImportError:  # pragma: no cover - import shape differs in tests
    import orgfilter


router = APIRouter(prefix="/admin/orgs", tags=["Organizations (admin)"])


# `users.scope` values allowed to edit the register. Prod's single user is
# 'full'. Checked on the USER ROW, not the token's scopes — see the module note.
EDITOR_SCOPES = ("full", "write", "admin")

# Fields a client may set. Anything else is a 400, never a silent no-op.
#   name          guarded by confirm_rename (join key)
#   display_name  free — this is where NYC's official name goes
EDITABLE_FIELDS = (
    "name", "display_name", "type", "alternate_name", "description", "url",
    "main_phone", "main_address", "code", "in_org_chart", "parent_org_id",
    "internal_notes",
)

# New ids continue the existing `1701` series (adopt_nyc_orgs.py uses the same
# range; max was 170100390 after Phase 1).
#
# ⚠ BOUNDED AT BOTH ENDS, and that matters. The register also holds legacy ids
# far outside the series — 811254850 (New York City Fire Museum), 272846763
# (Brooklyn Bridge Park Corporation), 222879323 — so `MAX(id) WHERE id >= MIN`
# picks the largest id in the WHOLE table and mints e.g. 811254851. Measured on
# prod 2026-07-31 by creating one. Within the series the max is 170100390.
ID_SERIES_MIN = 170100000
ID_SERIES_MAX = 170199999

AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS wegov_orgs_audit (
    id         SERIAL PRIMARY KEY,
    org_id     INTEGER     NOT NULL,
    action     TEXT        NOT NULL,
    field      TEXT,
    old_value  TEXT,
    new_value  TEXT,
    actor      TEXT        NOT NULL,
    note       TEXT,
    at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS wegov_orgs_audit_org_idx ON wegov_orgs_audit (org_id, at DESC);
"""

_AUDIT_READY = False


async def _ensure_audit_table():
    """Create the audit table on first use.

    `wegov_orgs` has no DDL in this repo, so there is nowhere else to put this;
    following the `adopt_nyc_orgs.py` precedent of idempotent inline DDL.
    """
    global _AUDIT_READY
    if _AUDIT_READY:
        return
    for stmt in [s.strip() for s in AUDIT_DDL.split(";") if s.strip()]:
        await PostgresModelAsync.execute(stmt)
    _AUDIT_READY = True


# =============================================================================
# auth
# =============================================================================

async def require_editor(request: Request) -> dict:
    """A valid JWT whose user row carries an editor scope, or the internal key.

    Returns the actor dict used for the audit trail — so every mutation is
    attributable, which no store in this system has ever been.
    """
    # ⚠ HEADER FIRST, and never a raw `==`. This used to read the query
    # parameter first and compare with `==`. Both were wrong: uvicorn logs the
    # full request line, so the query form wrote this secret into the api's
    # container log in plaintext on every call (the #192 exposure, which was
    # fixed on /import-csv and /upload but MISSED here), and `==` on a str short
    # circuits at the first differing byte. `modules.apikey` is now the single
    # resolver for all three call sites.
    try:
        from modules import apikey
    except ImportError:                                 # pragma: no cover
        import apikey
    try:
        from config import Config
        configured = (Config.fastapi or {}).get("key") or ""
    except Exception:                                   # pragma: no cover
        configured = ""
    if apikey.ok(request.headers.get("X-API-Key"),
                 request.query_params.get("api_key"),
                 configured):
        return {"id": None, "email": "api-key", "scope": "full"}

    token = (request.headers.get("Authorization") or "").replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(401, "authentication required: Bearer token or X-API-Key")
    try:
        from main import manager
        user = await manager.get_current_user(token)
    except Exception:
        raise HTTPException(401, "invalid credentials")
    if not user:
        raise HTTPException(401, "invalid credentials")
    if (user.get("scope") or "").lower() not in EDITOR_SCOPES:
        raise HTTPException(
            403, f"user scope {user.get('scope')!r} may not edit the org register")
    return user


# =============================================================================
# helpers
# =============================================================================

async def _one(sql: str, params=()):
    rows = await PostgresModelAsync.select_safe(sql, list(params))
    return rows[0] if rows else None


def _vocabulary() -> tuple:
    """Every org type the system knows about, from the ONE place that owns it."""
    return tuple(dict.fromkeys(
        orgfilter.OTI_TYPES + orgfilter.OURS_GOV_TYPES + orgfilter.CHART_TYPES
        + orgfilter.DIRECTORY_TYPES + orgfilter.CITY_AGENCY_TYPES))


async def _extra_types() -> tuple:
    """Types present in the data but not in the vocabulary constants.

    The register legitimately holds ~930 rows OTI does not cover (Unions,
    Political Clubs, BIDs, Publications…). Those types must remain selectable or
    the editor could not save an existing row without retyping it — a validator
    that rejects the data it is editing is worse than no validator.
    """
    rows = await PostgresModelAsync.select_safe(
        'SELECT DISTINCT "type" AS t FROM wegov_orgs WHERE COALESCE("type",\'\') <> \'\'')
    return tuple(sorted({r["t"] for r in rows}))


async def _allowed_types() -> tuple:
    return tuple(dict.fromkeys(_vocabulary() + await _extra_types()))


async def _rename_impact(name: str) -> dict:
    """How many contracts currently resolve through this exact name.

    Mirrors `oce.py::_resolve_org_id` — UPPER(TRIM()) equality on name or
    alternate_name — so the number quoted to the human is the number that would
    stop matching.
    """
    try:
        row = await _one(
            'SELECT count(*) AS c FROM contracts '
            'WHERE UPPER(TRIM(agency)) = UPPER(TRIM($1))', (name,))
        return {"contracts_matching_name": int(row["c"]) if row else 0}
    except Exception:
        # No contracts table in this environment — say so rather than claim 0.
        return {"contracts_matching_name": None}


async def _would_cycle(org_id: int, parent_id: int) -> Optional[list]:
    """Walk up from `parent_id`; return the path if it reaches `org_id`.

    ⚠ Not cosmetic. OrgChart::packnode recurses through children with no depth
    guard, so a cycle blows the stack and 500s the entire chart page.
    """
    seen, path, cur = set(), [], parent_id
    for _ in range(64):
        if cur is None:
            return None
        if cur == org_id:
            return path + [cur]
        if cur in seen:
            return None                 # pre-existing loop elsewhere, not ours
        seen.add(cur)
        path.append(cur)
        row = await _one("SELECT parent_org_id FROM wegov_orgs WHERE id = $1", (cur,))
        if not row:
            return None
        cur = row["parent_org_id"]
    return path


async def _audit(org_id: int, action: str, actor: dict, field=None,
                 old=None, new=None, note=None):
    await _ensure_audit_table()
    await PostgresModelAsync.execute(
        "INSERT INTO wegov_orgs_audit (org_id, action, field, old_value, "
        "new_value, actor, note) VALUES ($1,$2,$3,$4,$5,$6,$7)",
        [org_id, action, field,
         None if old is None else str(old),
         None if new is None else str(new),
         actor.get("email") or str(actor.get("id")), note])


# =============================================================================
# read
# =============================================================================

@router.get("/vocabulary", summary="Allowed org types (and why the list matters)")
async def vocabulary(request: Request):
    """The type list a client must choose from.

    Served so the UI cannot invent a type. `orgfilter` is the single owner of
    this vocabulary; a filter that drifts from it fails SILENTLY, which is the
    #177 regression.
    """
    await require_editor(request)
    return {
        "types": list(await _allowed_types()),
        "canonical": list(_vocabulary()),
        "note": ("`type` drives /get/orgs/{directory,chart,agencies} and the "
                 "Greenbook enrichment. A value outside this list makes rows "
                 "vanish from those surfaces with no error."),
    }


@router.get("/{org_id}", summary="The editable record, its parent, and its audit trail")
async def get_org(org_id: int, request: Request):
    await require_editor(request)
    org = await _one(
        "SELECT o.*, p.name AS parent_name, p.type AS parent_type, "
        "       s.name AS merged_into_name "
        "FROM wegov_orgs o "
        "LEFT JOIN wegov_orgs p ON p.id = o.parent_org_id "
        "LEFT JOIN wegov_orgs s ON s.id = o.merged_into "
        "WHERE o.id = $1", (org_id,))
    if not org:
        raise HTTPException(404, f"org {org_id} not found")
    await _ensure_audit_table()
    history = await PostgresModelAsync.select_safe(
        "SELECT action, field, old_value, new_value, actor, note, at "
        "FROM wegov_orgs_audit WHERE org_id = $1 ORDER BY at DESC, id DESC LIMIT 100",
        [org_id])
    return {
        "org": org,
        "audit": history,
        "rename_impact": await _rename_impact(org.get("name") or ""),
        "editable_fields": list(EDITABLE_FIELDS),
    }


# =============================================================================
# write
# =============================================================================

async def _validate(payload: dict, org_id: Optional[int], current: Optional[dict]):
    """Shared validation. Returns (clean_fields, warnings)."""
    unknown = [k for k in payload
               if k not in EDITABLE_FIELDS and k not in ("confirm_rename", "note")]
    if unknown:
        raise HTTPException(
            400, f"unknown field(s) {unknown}; editable: {list(EDITABLE_FIELDS)}")

    fields = {k: v for k, v in payload.items() if k in EDITABLE_FIELDS}
    warnings = []

    if "type" in fields:
        allowed = await _allowed_types()
        if (fields["type"] or "") not in allowed:
            raise HTTPException(
                400, f"type {fields['type']!r} is not in the vocabulary owned by "
                     f"modules/orgfilter.py — a value outside it makes the org "
                     f"vanish from the directory/chart/agencies with no error. "
                     f"Allowed: {sorted(allowed)}")

    if "name" in fields:
        new_name = (fields["name"] or "").strip()
        if not new_name:
            raise HTTPException(400, "name may not be empty — it is a join key")
        fields["name"] = new_name
        old_name = (current or {}).get("name")
        if current is not None and new_name != old_name:
            if not payload.get("confirm_rename"):
                impact = await _rename_impact(old_name or "")
                raise HTTPException(409, {
                    "error": "renaming `name` needs confirm_rename=true",
                    "why": ("`name` is a JOIN KEY: oce.py::_resolve_org_id matches "
                            "contracts.agency against it by UPPER(TRIM()) equality, "
                            "and the org page passes it to /oce/agency/summary?name=. "
                            "Renaming silently zeroes this profile's procurement "
                            "figures. To show a different name publicly, set "
                            "`display_name` instead."),
                    "from": old_name, "to": new_name,
                    "impact": impact,
                })
            warnings.append(
                f"renamed {old_name!r} -> {new_name!r}; procurement lookups keyed "
                f"on the old name will stop matching "
                f"({(await _rename_impact(old_name or '')).get('contracts_matching_name')} "
                f"contracts matched it)")

    if "parent_org_id" in fields and fields["parent_org_id"] is not None:
        pid = int(fields["parent_org_id"])
        if org_id is not None and pid == org_id:
            raise HTTPException(400, "an org cannot be its own parent")
        parent = await _one(
            "SELECT id, name, retired_at FROM wegov_orgs WHERE id = $1", (pid,))
        if not parent:
            raise HTTPException(400, f"parent_org_id {pid} does not exist")
        if parent.get("retired_at"):
            raise HTTPException(
                400, f"parent_org_id {pid} ({parent['name']!r}) is retired; "
                     f"parent must be a live org")
        if org_id is not None:
            cycle = await _would_cycle(org_id, pid)
            if cycle:
                raise HTTPException(
                    400, f"that parent would create a cycle ({cycle}); the org "
                         f"chart builder recurses without a depth guard, so a "
                         f"cycle 500s the whole chart")
        fields["parent_org_id"] = pid

    if "in_org_chart" in fields and fields["in_org_chart"] is not None:
        # Tri-state on purpose: TRUE / FALSE / NULL where NULL is "not stated".
        if not isinstance(fields["in_org_chart"], bool):
            raise HTTPException(400, "in_org_chart must be true, false or null")

    return fields, warnings


@router.post("", summary="Create an org (id assigned by the server)")
async def create_org(request: Request, payload: dict = Body(...)):
    actor = await require_editor(request)
    if "id" in payload:
        raise HTTPException(
            400, "id is assigned by the server, not the client — it is the "
                 "register's primary key and the value ingested data references")
    if not (payload.get("name") or "").strip():
        raise HTTPException(400, "name is required")
    if not (payload.get("type") or "").strip():
        raise HTTPException(400, "type is required — see GET /admin/orgs/vocabulary")

    fields, warnings = await _validate(payload, None, None)

    dup = await _one("SELECT id FROM wegov_orgs WHERE UPPER(TRIM(name)) = "
                     "UPPER(TRIM($1)) AND retired_at IS NULL", (fields["name"],))
    if dup:
        warnings.append(f"an org named {fields['name']!r} already exists "
                        f"(id {dup['id']}) — duplicates are legitimate for "
                        f"bargaining units, but check first")

    row = await _one(f"SELECT COALESCE(MAX(id), {ID_SERIES_MIN}) AS m "
                     f"FROM wegov_orgs "
                     f"WHERE id BETWEEN {ID_SERIES_MIN} AND {ID_SERIES_MAX}")
    new_id = int(row["m"]) + 1
    if new_id > ID_SERIES_MAX:
        # Fail loudly rather than wrap into someone else's range.
        raise HTTPException(
            500, f"the {ID_SERIES_MIN}-{ID_SERIES_MAX} id series is exhausted; "
                 f"widen it deliberately rather than minting outside it")

    # ⚠ NO airtable_id is minted. Phase 6 retired Airtable as an identity
    # scheme: a synthetic id existed only so `child_of` could address a new org,
    # and the parent is `parent_org_id` now. Claiming Airtable provenance for a
    # row created here would be a lie.
    cols = dict(fields)
    cols["last_updated"] = datetime.now(timezone.utc).date().isoformat()

    names = ", ".join(f'"{k}"' for k in cols)
    holders = ", ".join(f"${i + 2}" for i in range(len(cols)))
    await PostgresModelAsync.execute(
        f'INSERT INTO wegov_orgs (id, {names}) VALUES ($1, {holders})',
        [new_id] + list(cols.values()))
    await _audit(new_id, "create", actor, note=payload.get("note")
                 or f"created {fields['name']!r}")
    return {"ok": True, "id": new_id, "warnings": warnings}


@router.patch("/{org_id}", summary="Update fields on one org")
async def update_org(org_id: int, request: Request, payload: dict = Body(...)):
    actor = await require_editor(request)
    current = await _one("SELECT * FROM wegov_orgs WHERE id = $1", (org_id,))
    if not current:
        raise HTTPException(404, f"org {org_id} not found")

    fields, warnings = await _validate(payload, org_id, current)
    changed = {k: v for k, v in fields.items() if current.get(k) != v}
    if not changed:
        return {"ok": True, "id": org_id, "changed": {}, "warnings": warnings,
                "note": "no field differed from its stored value"}

    sets = ", ".join(f'"{k}" = ${i + 2}' for i, k in enumerate(changed))
    await PostgresModelAsync.execute(
        f"UPDATE wegov_orgs SET {sets} WHERE id = $1",
        [org_id] + list(changed.values()))
    for k, v in changed.items():
        await _audit(org_id, "update", actor, field=k, old=current.get(k),
                     new=v, note=payload.get("note"))
    return {"ok": True, "id": org_id, "changed": changed, "warnings": warnings}


@router.post("/{org_id}/retire", summary="Retire an org into a successor")
async def retire_org(org_id: int, request: Request, payload: dict = Body(...)):
    """Retirement is ADDITIVE and reversible — never a DELETE.

    `merged_into` is required: 3,700 org match rows and every ingested
    `wegov-org-id` may point at this org, and they must keep resolving to
    something. `get_organization_profile` deliberately still answers for a
    retired id, reporting the successor.
    """
    actor = await require_editor(request)
    org = await _one("SELECT id, name, retired_at FROM wegov_orgs WHERE id = $1",
                     (org_id,))
    if not org:
        raise HTTPException(404, f"org {org_id} not found")
    if org.get("retired_at"):
        raise HTTPException(409, f"org {org_id} is already retired")

    into = payload.get("merged_into")
    if into is None:
        raise HTTPException(
            400, "merged_into is required: match rows and ingested wegov-org-id "
                 "values pointing at this org must keep resolving")
    into = int(into)
    if into == org_id:
        raise HTTPException(400, "an org cannot be merged into itself")
    successor = await _one(
        "SELECT id, name, retired_at FROM wegov_orgs WHERE id = $1", (into,))
    if not successor:
        raise HTTPException(400, f"merged_into {into} does not exist")
    if successor.get("retired_at"):
        raise HTTPException(400, f"merged_into {into} is itself retired")

    kids = await PostgresModelAsync.select_safe(
        "SELECT id, name FROM wegov_orgs WHERE parent_org_id = $1 "
        "AND retired_at IS NULL", [org_id])
    warnings = []
    if kids:
        warnings.append(
            f"{len(kids)} live org(s) still name this as their parent "
            f"({[k['id'] for k in kids][:10]}); they would point at a retired "
            f"org — re-parent them")

    await PostgresModelAsync.execute(
        "UPDATE wegov_orgs SET retired_at = $2, merged_into = $3 WHERE id = $1",
        [org_id, datetime.now(timezone.utc), into])
    await _audit(org_id, "retire", actor, field="merged_into", old=None, new=into,
                 note=payload.get("note") or f"retired into {successor['name']!r}")
    return {"ok": True, "id": org_id, "merged_into": into,
            "successor": successor["name"], "warnings": warnings}


@router.post("/{org_id}/unretire", summary="Reverse a retirement")
async def unretire_org(org_id: int, request: Request, payload: dict = Body(default={})):
    """The reversibility that makes retirement safe is only real if it is
    actually reachable, so it is an endpoint rather than a manual UPDATE."""
    actor = await require_editor(request)
    org = await _one("SELECT id, name, retired_at FROM wegov_orgs WHERE id = $1",
                     (org_id,))
    if not org:
        raise HTTPException(404, f"org {org_id} not found")
    if not org.get("retired_at"):
        raise HTTPException(409, f"org {org_id} is not retired")
    await PostgresModelAsync.execute(
        "UPDATE wegov_orgs SET retired_at = NULL, merged_into = NULL WHERE id = $1",
        [org_id])
    await _audit(org_id, "unretire", actor, note=payload.get("note"))
    return {"ok": True, "id": org_id}


@router.api_route("/{org_id}", methods=["DELETE"], include_in_schema=True,
                  summary="Refused — retirement, not deletion")
async def delete_org(org_id: int, request: Request):
    """⚠ Deliberately answers 405.

    Deleting an org would orphan every one of the 3,700 org match rows and every
    ingested `wegov-org-id` pointing at it — silently, because those are string
    references the database does not police. Retirement is additive, reversible,
    and keeps them resolving.
    """
    await require_editor(request)
    return JSONResponse(status_code=405, content={
        "error": "orgs are retired, not deleted",
        "why": ("3,700 org match rows and every ingested wegov-org-id may "
                "reference this org; a DELETE orphans them with no error. "
                "Retirement is additive and reversible."),
        "use": f"POST /admin/orgs/{org_id}/retire with merged_into",
    })
