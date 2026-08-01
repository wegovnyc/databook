"""Crosswalk our org directory to NYC's official agency registry.

Since September 2025 OTI has published `NYC Agencies and Governance
Organizations` (Socrata `t3jq-9nkf`): 306 City organizations, each with a stable
`record_id` (`NYC_GOID_000314`), an `organization_type`, a `reports_to` parent,
an `acronym`, and `alternate_or_former_names`. It is maintained; ours is not —
almost every `wegov_orgs` row was last touched in 2021-22.

This builds `nyc_org_crosswalk`, mapping our `wegov_orgs.id` to OTI's
`record_id`. It does NOT modify `wegov_orgs`: the crosswalk is the join, so
adopting OTI attributes stays a separate, reviewable decision.

Why a crosswalk table rather than a column
------------------------------------------
Same reasoning as `nycha_vendor_crosswalk` and `dos_entity_enrichment`: it keeps
tiers and scores alongside the link, supports a curated tier that a rebuild must
never overwrite, and leaves the 48-column serving table alone.

Matching
--------
Measured against prod 2026-07-29: **164 of 306 (54%) match confidently**, and the
naive exact-name match found only 114. The gap was almost entirely naming
convention, so two passes run before any fuzzy scoring:

  exact/alias  123  our name / alternate_name / code  vs  OTI name / former
                    names / acronym, each also tried with a leading
                    "Mayor's Office of", "Office of", "NYC" etc. stripped.
  token-set     41  order-insensitive match on the significant-token SET. This
                    is what catches the inversions: "Office of the Borough
                    President of Manhattan" == "Manhattan Borough President",
                    "Queens District Attorney's Office" == "District Attorney -
                    Queens", "Bronx County Public Administrator" ==
                    "Public Administrator - Bronx".

⚠ TWO RULES LEARNED THE HARD WAY — do not relax them:

1. **Organisational form words are significant.** BOARD / COMMISSION /
   AUTHORITY / COUNCIL / DEPARTMENT / CORPORATION / CABINET / COMMITTEE must
   match. Treating them as filler linked "Workforce Development BOARD" to
   "Office of Workforce Development", and the "NYC Housing Authority BOARD" to
   the Authority itself. "Office" IS droppable — "Office of the Borough
   President" is the same body as "Borough President" — but a Board is not an
   Office.

2. **Reject a fuzzy pair when EACH side has a distinguishing word the other
   lacks.** Plain similarity scored 0.79-0.85 on: LAND vs HOUSING Development
   Corporation, CONVENTION CENTER vs ECONOMIC Development Corporation, RACIAL vs
   GENDER Equity, COMMUNITY vs PUBLIC Safety, NONPROFIT vs CONTRACT Services.
   All five are different organizations. This is the same false-positive class as
   the NYCHA crosswalk's token-set shortcut (#148).

Tier contract — consumers MUST filter on it:

    exact/alias   link
    token-set     link
    curated       link, human-confirmed, survives a rebuild
    rejected      NOT a link. human-refused; survives so it is never re-suggested
    review        NOT a link. awaiting a human

    -> join on: match_tier IN ('exact/alias','token-set','curated')

⚠ Note `rejected` also carries `curated = true`, so "curated" alone is NOT a
safe link predicate — filter on the tier, never on the boolean. Reviewed
2026-07-30: 2 of 9 review rows accepted (Mayor's Office of Talent and Workforce
Development -> our Office of Workforce Development; Gracie Mansion Conservancy ->
our Gracie Mansion), 7 refused, including three different bodies all scoring 0.7+
against our single "Office of Workforce Development".

Rebuild semantics: `DELETE WHERE curated = false`, then re-insert, skipping any
pair already curated (the #149 lesson — an upsert-only generator leaves corrected
false positives in place).

Run:
    docker compose exec -T api python build_nyc_org_crosswalk.py
"""

import asyncio
import collections
import os
import re
import sys
from difflib import SequenceMatcher

import aiohttp
import asyncpg

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
from config import Config

try:
    import dbcreds
except ImportError:
    from modules import dbcreds


SOCRATA_ID = "t3jq-9nkf"
SOURCE_URL = f"https://data.cityofnewyork.us/resource/{SOCRATA_ID}.json?$limit=5000"

DDL = """
CREATE TABLE IF NOT EXISTS nyc_org_crosswalk (
    wegov_org_id    BIGINT NOT NULL,
    nyc_record_id   TEXT   NOT NULL,
    nyc_name        TEXT,
    wegov_name      TEXT,
    match_tier      TEXT   NOT NULL,
    match_score     NUMERIC,
    curated         BOOLEAN NOT NULL DEFAULT FALSE,
    built_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (wegov_org_id, nyc_record_id)
);
CREATE INDEX IF NOT EXISTS idx_nyc_xwalk_record ON nyc_org_crosswalk(nyc_record_id);
CREATE INDEX IF NOT EXISTS idx_nyc_xwalk_tier   ON nyc_org_crosswalk(match_tier);
"""

# Droppable wrappers. NOTE the deliberate absence of BOARD/COMMISSION/AUTHORITY/
# COUNCIL/DEPARTMENT/CORPORATION/CABINET/COMMITTEE — see rule 1 in the docstring.
FILLER = {"OF", "THE", "FOR", "AND", "NYC", "NEW", "YORK", "CITY", "OFFICE",
          "MAYORS", "MAYOR", "SERVICES", "NYCS", "COUNTY"}

STOP_PREFIX = [
    "MAYORS OFFICE OF THE", "MAYORS OFFICE OF", "MAYORS OFFICE FOR", "MAYORS OFFICE",
    "NEW YORK CITY", "NYC", "OFFICE OF THE", "OFFICE OF", "OFFICE FOR",
    "THE CITY OF NEW YORK", "CITY OF NEW YORK", "CITY", "THE",
    "DEPARTMENT OF", "COMMISSION ON", "BOROUGH OF",
]

RARE_MAX = 40          # a token rarer than this can license a fuzzy link
FUZZY_ACCEPT = 0.80    # stored as fuzzy-high (still not auto-linked by consumers)
FUZZY_REVIEW = 0.68


def base(s: str) -> str:
    s = (s or "").upper().replace("&", " AND ").replace("’", "'")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# NYC boroughs and their counties are used interchangeably in org names: our
# "District Attorney - Kings" is OTI's "Brooklyn District Attorney's Office", and
# our "District Attorney - Richmond" is their "Staten Island District Attorney's
# Office". Applied as EXTRA variants in both directions, never as a destructive
# rewrite, so a swap can only add a match.
BOROUGH_COUNTY = [
    ("NEW YORK COUNTY", "MANHATTAN"),   # phrase first — "NEW YORK" alone is far too common
    ("KINGS COUNTY", "BROOKLYN"),
    ("RICHMOND COUNTY", "STATEN ISLAND"),
    ("KINGS", "BROOKLYN"),
    ("RICHMOND", "STATEN ISLAND"),
]

# Trailing legal-form suffixes that a common name routinely drops: ours is
# "Health and Hospitals Corporation", OTI's is "NYC Health + Hospitals".
# ⚠ Deliberately excludes BOARD/COMMISSION/COUNCIL/AUTHORITY — those denote a
# distinct governing body, not a legal wrapper. Dropping BOARD is what linked
# "Workforce Development Board" to "Office of Workforce Development".
LEGAL_SUFFIX = ["CORPORATION", "CORP", "INCORPORATED", "INC", "LLC"]


def variants(name: str) -> set:
    """Normalized name plus every safe rewrite: wrapper prefixes removed,
    borough/county swapped, trailing legal suffix dropped. Additive only."""
    b = base(name)
    forms = {b}

    # borough <-> county, both directions
    for a, z in BOROUGH_COUNTY:
        for src, dst in ((a, z), (z, a)):
            forms |= {f.replace(src, dst).strip() for f in list(forms) if src in f}

    # leading generic wrappers
    for f in list(forms):
        for p in STOP_PREFIX:
            if f.startswith(p + " "):
                forms.add(f[len(p):].strip())

    # trailing legal form
    for f in list(forms):
        for s in LEGAL_SUFFIX:
            if f.endswith(" " + s):
                forms.add(f[: -len(s) - 1].strip())

    return {re.sub(r"\s+", " ", v).strip() for v in forms if v.strip()}


def ckey(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", base(s))


def sig_tokens(s: str) -> list:
    """Significant tokens: filler dropped, form words kept."""
    return [t for t in base(s).split() if t not in FILLER and len(t) > 2]


async def fetch_nyc_orgs(session) -> list:
    async with session.get(SOURCE_URL, timeout=aiohttp.ClientTimeout(total=120)) as r:
        r.raise_for_status()
        return await r.json()


def build_matches(nyc_orgs: list, ours: list) -> list:
    """Return [(wegov_org, nyc_org, tier, score)] for every resolvable pair."""
    df = collections.Counter()
    for name in [o["name"] for o in ours] + [r.get("name", "") for r in nyc_orgs]:
        for t in set(sig_tokens(name)):
            df[t] += 1

    def distinctive(s):
        return {t for t in sig_tokens(s) if df[t] <= RARE_MAX}

    by_key = collections.defaultdict(list)
    by_tokenset = collections.defaultdict(list)
    for o in ours:
        for src in (o["name"], o.get("alternate_name") or ""):
            if src.strip():
                for v in variants(src):
                    if ckey(v):
                        by_key[ckey(v)].append(o)
        if (o.get("code") or "").strip() and ckey(o["code"]):
            by_key[ckey(o["code"])].append(o)
        # index a token set for EVERY variant, so a borough/county swap or a
        # dropped legal suffix can satisfy the order-insensitive pass too
        for src in (o["name"], o.get("alternate_name") or ""):
            if src.strip():
                for v in variants(src):
                    ts = frozenset(sig_tokens(v))
                    if ts:
                        by_tokenset[ts].append(o)

    def nyc_keys(r):
        """(name_keys, acronym_keys) — kept apart on purpose.

        ⚠ An acronym is weak evidence. Our "NYC & Company" carries
        alternate_name "NYCC", which is also OTI's acronym for the New York City
        COUNCIL — a 4-letter collision between two unrelated bodies. A full-name
        or former-name match is strong; an acronym only breaks a tie.
        """
        names = [r.get("name")] + [
            a for a in (r.get("alternate_or_former_names") or "").split(";") if a.strip()
        ]
        nk = {ckey(v) for src in names for v in variants(src)}
        ak = {ckey(r["acronym"])} if r.get("acronym") else set()
        return {k for k in nk if k}, {k for k in ak if k}

    def pick(cands, r):
        """Disambiguate a key claimed by several of our orgs.

        ⚠ Acronyms collide: OTI's `CPC` (City Planning Commission) also matches our
        Chinese-American Planning Council. Taking the first candidate resolved that
        correctly only by iteration order. Break the tie on name similarity to the
        OTI name, and refuse rather than guess when nothing is close.
        """
        if len(cands) == 1:
            return cands[0]
        rn = base(r.get("name"))
        best = max(cands, key=lambda o: SequenceMatcher(None, rn, base(o["name"])).ratio())
        if SequenceMatcher(None, rn, base(best["name"])).ratio() < 0.45:
            return None
        return best

    out = []
    for r in nyc_orgs:
        hit = None
        name_keys, acro_keys = nyc_keys(r)
        for keys, strength in ((name_keys, "name"), (acro_keys, "acronym")):
            for k in keys:
                if k in by_key:
                    chosen = pick(by_key[k], r)
                    if chosen is None:
                        continue
                    hit = (chosen, "exact/alias", 1.0, strength)
                    break
            if hit:
                break
        if not hit:
            for v in variants(r.get("name")):
                ts = frozenset(sig_tokens(v))
                if ts and ts in by_tokenset:
                    hit = (by_tokenset[ts][0], "token-set", 1.0, "name")
                    break
        if not hit:
            rn, rd, best = base(r.get("name")), distinctive(r.get("name")), (None, 0.0)
            for o in ours:
                od = distinctive(o["name"])
                if not (rd & od):
                    continue
                if (rd - od) and (od - rd):   # rule 2 — each side has a distinguisher
                    continue
                sc = SequenceMatcher(None, rn, base(o["name"])).ratio()
                if sc > best[1]:
                    best = (o, sc)
            if best[0] and best[1] >= FUZZY_ACCEPT:
                hit = (best[0], "fuzzy-high", best[1], "fuzzy")
            elif best[0] and best[1] >= FUZZY_REVIEW:
                hit = (best[0], "review", best[1], "fuzzy")
        if hit:
            out.append((hit[0], r, hit[1], hit[2], hit[3]))

    # ── enforce one-to-one on the confident tiers ────────────────────────────
    # Two OTI records must not claim the same org. When they do, keep the
    # stronger claim (full-name/alias beats acronym, then name similarity) and
    # demote the loser to `review` rather than dropping it silently.
    CONF = {"exact/alias", "token-set"}
    RANK = {"name": 0, "acronym": 1, "fuzzy": 2}
    claims = collections.defaultdict(list)
    for i, (o, r, tier, sc, strength) in enumerate(out):
        if tier in CONF:
            claims[o["id"]].append(i)
    for oid, idxs in claims.items():
        if len(idxs) < 2:
            continue
        def quality(i):
            o, r, tier, sc, strength = out[i]
            return (-RANK[strength],
                    SequenceMatcher(None, base(r.get("name")), base(o["name"])).ratio())
        keep = max(idxs, key=quality)
        for i in idxs:
            if i != keep:
                o, r, tier, sc, strength = out[i]
                out[i] = (o, r, "review", sc, strength)
                print(f"[xwalk] one-to-one: our {oid} ({o['name'][:34]}) claimed by "
                      f"{len(idxs)}; kept {out[keep][1]['record_id']}, demoted "
                      f"{r['record_id']} ({r.get('name','')[:34]}) to review")
    return [(o, r, tier, sc) for o, r, tier, sc, _ in out]


async def main():
    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=dbcreds.password(),
        database=os.environ.get("POSTGRES_DB", "databook"),
    )
    try:
        for stmt in DDL.strip().split(";"):
            if stmt.strip():
                await conn.execute(stmt)

        rows = await conn.fetch(
            "SELECT id, name, COALESCE(alternate_name,'') AS alternate_name, "
            "COALESCE(code,'') AS code FROM wegov_orgs")
        ours = [dict(r) for r in rows]

        async with aiohttp.ClientSession() as session:
            nyc_orgs = await fetch_nyc_orgs(session)
        print(f"[xwalk] OTI orgs: {len(nyc_orgs)}   our orgs: {len(ours)}")

        # ⚠ SAFETY GUARD — this became essential when the rebuild went on a cron
        # (Phase 4a). The rebuild below DELETEs every non-curated row before
        # re-inserting, so a short or empty response would wipe the crosswalk and
        # replace it with nothing. Socrata does return 200 with a truncated or
        # error body under load — that is the documented cause of a silent
        # fiscal-year truncation in the Checkbook extractors (#117), so it is a
        # measured risk here, not a hypothetical one.
        MIN_EXPECTED = int(os.environ.get("NYC_ORG_MIN_EXPECTED", "250"))
        if len(nyc_orgs) < MIN_EXPECTED:
            raise RuntimeError(
                f"refusing to rebuild: OTI returned only {len(nyc_orgs)} orgs "
                f"(expected >= {MIN_EXPECTED}). The existing crosswalk is left "
                f"untouched.")

        matches = build_matches(nyc_orgs, ours)
        tiers = collections.Counter(m[2] for m in matches)

        # ⚠ One transaction around delete + re-insert. Without it a failure
        # part-way through leaves the crosswalk holding some links and missing
        # others, which reads as a successful rebuild with fewer matches.
        tx = conn.transaction()
        await tx.start()
        try:
            # #149: never leave a corrected false positive behind.
            deleted = await conn.execute(
                "DELETE FROM nyc_org_crosswalk WHERE curated = false")
            print(f"[xwalk] cleared non-curated rows ({deleted})")

            curated = {
                (r["wegov_org_id"], r["nyc_record_id"])
                for r in await conn.fetch(
                    "SELECT wegov_org_id, nyc_record_id FROM nyc_org_crosswalk "
                    "WHERE curated")
            }

            inserted = 0
            for o, r, tier, score in matches:
                if (o["id"], r["record_id"]) in curated:
                    continue
                await conn.execute(
                    """INSERT INTO nyc_org_crosswalk
                         (wegov_org_id, nyc_record_id, nyc_name, wegov_name,
                          match_tier, match_score)
                       VALUES ($1,$2,$3,$4,$5,$6)
                       ON CONFLICT (wegov_org_id, nyc_record_id) DO NOTHING""",
                    int(o["id"]), r["record_id"], r.get("name"), o["name"], tier,
                    round(float(score), 3))
                inserted += 1
            await tx.commit()
        except Exception:
            await tx.rollback()
            print("[xwalk] ROLLED BACK — the previous crosswalk is intact.")
            raise

        held = await conn.fetchrow(
            "SELECT count(*) FILTER (WHERE match_tier='curated')  AS accepted, "
            "       count(*) FILTER (WHERE match_tier='rejected') AS refused "
            "FROM nyc_org_crosswalk")
        print(f"[xwalk] curated held over: {held['accepted']} accepted, "
              f"{held['refused']} refused")
        confident = tiers["exact/alias"] + tiers["token-set"] + held["accepted"]
        print(f"[xwalk] inserted {inserted} rows")
        for t in ("exact/alias", "token-set", "fuzzy-high", "review"):
            if tiers[t]:
                print(f"           {t:<12} {tiers[t]}")
        print(f"[xwalk] confident links: {confident}/{len(nyc_orgs)} "
              f"({confident/len(nyc_orgs)*100:.0f}%)")
        print(f"[xwalk] OTI orgs with no match: {len(nyc_orgs) - len(matches)}")
        print("[xwalk] ⚠ link predicate is match_tier IN "
              "('exact/alias','token-set','curated') — NOT `curated = true`, "
              "which also covers human REJECTIONS.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
