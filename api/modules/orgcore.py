"""Assemble the normalizer's `orgs` matching dictionary from the register.

Phase 2 of docs/ORG-DIRECTORY-OF-RECORD-PLAN.md. `GET /get/orgs/core` (main.py)
serves what this module builds; the normalizer's `CORE_RECIPES["orgs"]` fetches
it as a `url:` source, so a `POST /core/orgs/refresh` is a delete-and-reload of
exactly this output. That makes the shape of this feed load-bearing: every key
it emits becomes a match candidate, and every key it drops orphans any match
row that references it (3,683 exist, 2,588 of them `manual`).

The feed is ONE ROW PER NAME VARIANT, not per org. The core is keyed by name —
five ids are deliberately claimed by two entities each (`NYC Cyber Command` and
`Cyber Command` both -> 170100033) so both spellings resolve at ingest. A
one-row-per-org feed would delete the alias half of each pair on first refresh.

Three sources, in ascending precedence:

  1. live orgs        name + alternate_name + display_name, each carrying the
                      org's id. `Classification` / `Official` / `Public Figure`
                      rows are EXCLUDED — `District Attorneys` as a general
                      match target would swallow the five real DA offices.
  2. retired orgs     same variants, pointed at the `merged_into` successor.
                      The core deliberately holds `Commission on Gender
                      Equality` -> 170011004 so data still arriving under the
                      old name resolves; a live-orgs-only feed drops that.
  3. org_core_aliases a Postgres table of names the dictionary must keep
                      resolving that the register cannot derive: match-
                      referenced scaffolding names (`District Attorneys` IS
                      referenced by a manual payroll match), hand aliases
                      (`NYC Districting Commission`), id-less stubs, and the
                      incumbent id for each colliding variant. Seeded from a
                      snapshot of the hand-maintained core by
                      api/seed_org_core_aliases.py; rows here always win.

Collision policy (required, not optional — measured 2026-07-31: 23 variant
strings map to >1 org, worst case `DC37`, an alternate_name shared by 19
legitimately distinct bargaining units): a variant mapping to more than one
org is emitted ONLY via an org_core_aliases row naming its incumbent id —
otherwise it is omitted and listed in the report. Last-write-wins on a
19-way collision would pick an arbitrary local and the auto-matcher would
then link every payroll `DC37` to it.

Measured before the switch (2026-07-31, prod): today's 545 hand-maintained
entities are all preserved — every key is either a register variant with the
SAME id (0 disagreements) or one of the 16 seeded alias rows.
"""

import collections

# Chart scaffolding / person-role rows. In the register so the org chart can
# reference them; kept out of the general matching dictionary. An alias row can
# still admit a specific one where a match row already references it.
EXCLUDED_TYPES = ("Classification", "Official", "Public Figure")

# A retired org's merged_into may itself be retired; follow a short chain.
_MAX_MERGE_HOPS = 5


def _variants(row):
    for field in ("name", "alternate_name", "display_name"):
        v = (row.get(field) or "").strip()
        if v:
            yield v


def build_core_feed(org_rows, alias_rows):
    """Pure assembly: (org_rows, alias_rows) -> (feed, report).

    org_rows:   dicts with id, name, alternate_name, display_name, type, and
                (where the columns exist) retired_at + merged_into.
    alias_rows: dicts with name + org_id (org_id None = a known id-less stub:
                emitted with an empty id, exactly like today's core stub).

    feed:   [{"name": variant, "id": "170010002"}, ...] sorted by name — `name`
            is the entity key AND what gets stamped as `wegov-org-name`, `id`
            a string (today's core stores string ids; keep the stamped output
            byte-identical).
    report: what was omitted and why, for the ?report=1 diagnostics view and
            the pre-flight — silence about what was skipped is how earlier
            rounds of this work went wrong.
    """
    live_by_id, retired_by_id = {}, {}
    for r in org_rows:
        oid = int(r["id"])
        if r.get("retired_at") is not None:
            retired_by_id[oid] = r
        else:
            live_by_id[oid] = r

    def follow(oid):
        """Resolve an id through retirement merges to a live org id, or None."""
        for _ in range(_MAX_MERGE_HOPS):
            if oid in live_by_id:
                return oid
            nxt = (retired_by_id.get(oid) or {}).get("merged_into")
            if not nxt:
                return None
            oid = int(nxt)
        return None

    candidates = collections.defaultdict(set)   # variant -> {org id, ...}
    retired_unresolved = []
    for oid, r in live_by_id.items():
        if r.get("type") in EXCLUDED_TYPES:
            continue
        for v in _variants(r):
            candidates[v].add(oid)
    for oid, r in retired_by_id.items():
        if r.get("type") in EXCLUDED_TYPES:
            continue
        target = follow(oid)
        if target is None:
            retired_unresolved.append(r.get("name") or str(oid))
            continue
        for v in _variants(r):
            candidates[v].add(target)

    # Alias rows win unconditionally: they are the curated layer. An alias id
    # is still followed through retirements so a later merge cannot leave one
    # stamping a retired id.
    feed, alias_overrides, alias_dangling = {}, [], []
    for a in alias_rows:
        name = (a.get("name") or "").strip()
        if not name:
            continue
        oid = a.get("org_id")
        if oid is None:
            feed[name] = ""
            continue
        target = follow(int(oid))
        if target is None:
            alias_dangling.append(f"{name!r} -> {oid}")
            continue
        ids = candidates.get(name)
        if ids and target not in ids:
            alias_overrides.append(f"{name!r}: alias {target} over derived {sorted(ids)}")
        feed[name] = str(target)

    collisions_omitted = []
    for v, ids in candidates.items():
        if v in feed:
            continue                       # an alias already decided this key
        if len(ids) == 1:
            feed[v] = str(next(iter(ids)))
        else:
            collisions_omitted.append({"name": v, "org_ids": sorted(ids)})

    rows = [{"name": n, "id": i} for n, i in sorted(feed.items())]
    report = {
        "count": len(rows),
        "live_orgs": len(live_by_id),
        "retired_orgs": len(retired_by_id),
        "aliases": len(alias_rows),
        "alias_overrides": alias_overrides,
        "alias_dangling": alias_dangling,
        "collisions_omitted": sorted(collisions_omitted, key=lambda c: c["name"]),
        "retired_unresolved": retired_unresolved,
    }
    return rows, report
