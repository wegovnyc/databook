"""Guards for the OTI agency-registry adoption (`api/adopt_nyc_orgs.py` +
`api/sync_normalizer_org_core.py`).

These are regression guards, not coverage for its own sake. Every one of them
fires on a mistake that was actually made, or on a documented decision that a
future edit could silently reverse.
"""

import importlib
import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'modules'))

adopt = importlib.import_module("adopt_nyc_orgs")
syncore = importlib.import_module("sync_normalizer_org_core")


# ── the Socrata typing trap ──────────────────────────────────────────────────

def test_scalar_unwraps_socrata_url_objects():
    """`url` and `principal_officer_contact` arrive as {"url": ...} objects.

    Binding one straight into asyncpg raises `TypeError: expected str, got dict`
    -- which is exactly how the first run of this script died.
    """
    assert adopt.scalar({"url": "https://example.gov/"}) == "https://example.gov/"
    assert adopt.scalar({"address": "1 Centre St"}) == "1 Centre St"


def test_scalar_stringifies_booleans_and_none():
    """`in_org_chart` / `listed_in_nyc_gov_agency` are real JSON booleans."""
    assert adopt.scalar(True) == "true"
    assert adopt.scalar(False) == "false"
    assert adopt.scalar(None) == ""
    assert adopt.scalar("already text") == "already text"


# ── the link predicate ───────────────────────────────────────────────────────

def test_imported_tier_is_a_link_tier():
    """Imported orgs carry tier `imported`; leaving it out of LINK_TIERS would
    make every imported org read as unlinked and re-import on the next run."""
    assert "imported" in adopt.LINK_TIERS
    assert adopt.LINK_TIERS == syncore.LINK_TIERS, \
        "the two scripts must agree on what counts as a link"


def test_link_tiers_do_not_rely_on_the_curated_boolean():
    """⚠ `curated = true` also covers human REJECTIONS (tier `rejected`), so it
    is not a safe link predicate -- the tier is. Documented in
    build_nyc_org_crosswalk.py; this pins it for the adoption path too."""
    assert "rejected" not in adopt.LINK_TIERS


# ── decisions a future edit must not quietly reverse ─────────────────────────

def test_reports_to_aliases_never_reinstate_a_rejected_pair():
    """A human explicitly refused `Deputy Mayor for Community Safety` ==
    `Deputy Mayor for Public Safety`. An alias map is a tempting place to
    silently undo that."""
    for src, dst in adopt.REPORTS_TO_ALIASES.items():
        pair = {adopt.norm(src), adopt.norm(dst)}
        assert pair != {adopt.norm("Deputy Mayor for Public Safety"),
                        adopt.norm("Deputy Mayor for Community Safety")}, \
            f"alias {src!r} -> {dst!r} reinstates a rejected match"


def test_our_nonprofit_type_is_renamed_onto_otis():
    """Owner decision: one concept, one name -- `Nonprofit` becomes OTI's
    `Nonprofit Organization` throughout, including rows OTI does not cover."""
    assert adopt.TYPE_RENAMES == {"Nonprofit": "Nonprofit Organization"}


def test_community_services_board_link_is_rejected():
    """Owner, 2026-07-30: OTI's `Community Services Board` (a DOHMH body) has no
    association with our `Manhattan Community Board # 1`. Recording it as
    `rejected` both unlinks it and stops a rebuild re-suggesting it."""
    key = ("NYC_GOID_000119", 170010341)
    assert key in adopt.REJECTED_LINKS
    assert adopt.REJECTED_LINKS[key].strip()


def test_no_type_mapping_survives():
    """⚠ OTI's `organization_type` is adopted VERBATIM. A reintroduced mapping
    would silently collapse distinctions OTI preserves -- 43 Mayoral Office + 32
    Mayoral Agency + 16 Division + 26 Advisory were all just `City Agency` to
    us."""
    assert not hasattr(adopt, "ORG_TYPE_MAP")
    assert not hasattr(adopt, "LOW_CONFIDENCE_TYPES")


# ── cross-script consistency ─────────────────────────────────────────────────

def test_extra_orgs_still_carry_their_legacy_core_keys():
    """The hand-maintained core reached the three EXTRA_ORGS bodies through
    these exact key strings (195 ingested rows). Since Phase 2 the dictionary
    is DERIVED from the register's name/alternate_name/display_name, so each
    key must survive as one of those variants on its EXTRA_ORGS spec — rename
    or drop one and the next `POST /core/orgs/refresh` silently orphans its
    match rows."""
    legacy_keys = ("Off Track Betting Corp.",
                   "Commission to Strengthen Local Democracy",
                   "Commission on Public Information and Communication")
    variants = set()
    for spec in adopt.EXTRA_ORGS:
        variants.update(v for v in (spec.get("name"), spec.get("alternate_name"))
                        if v)
    for key in legacy_keys:
        assert key in variants, \
            f"legacy core key {key!r} is no longer derivable from EXTRA_ORGS"


def test_extra_orgs_are_declared_without_an_oti_record_id():
    """EXTRA_ORGS exist precisely because OTI does not publish them (it is
    Active-only), so none may claim an OTI record_id."""
    for spec in adopt.EXTRA_ORGS:
        assert "nyc_record_id" not in spec
        assert spec.get("note"), "each extra org must say why it exists"


def test_type_filters_accept_both_vocabularies():
    """⚠ `wegov_orgs.type` is mixed: OTI's for the 306, ours for the ~930 it does
    not cover. A filter that lists only our vocabulary silently drops ~117
    agencies -- no error, just a smaller result. This is the tripwire for all
    four filters that had to change."""
    from modules import orgfilter
    # our government vocabulary survives
    for t in ("City Agency", "Elected Office", "Community Board"):
        assert t in orgfilter.DIRECTORY_TYPES
    # OTI's government vocabulary is admitted
    for t in ("Mayoral Office", "Mayoral Agency", "Division",
              "Advisory or Regulatory Organization", "Pension Fund",
              "Public Benefit or Development Organization",
              "State Government Agency"):
        assert t in orgfilter.DIRECTORY_TYPES, f"{t} would vanish from the directory"
        assert t in orgfilter.CHART_TYPES, f"{t} would vanish from the org chart"
        assert t in orgfilter.AGENCY_ENRICHMENT_TYPES, \
            f"{t} would silently lose Greenbook head/address enrichment"


def test_no_source_file_hardcodes_a_single_org_type_as_a_filter():
    """⚠ THE REGRESSION THIS EXISTS FOR.

    `/organizations/agencies` filtered itself, in JavaScript:
        column.search('^City Agency$', true, false)
    and `data_scheduler.py` counted `WHERE type = 'City Agency'`. When the OTI
    adoption retyped 240 orgs, City Agency went 167 -> 27, the page silently
    showed 28 rows, and the stat tile above it agreed with the wrong number.
    Nothing raised.

    The earlier guard only checked that `orgfilter` CONTAINED the right
    vocabulary — it could not see a filter that never consulted orgfilter at
    all. This checks the opposite direction: that nothing filters on a bare
    type literal. A type name may still appear in a *presentation* map (badge
    colours, icons); what is banned is using one as a selection predicate.
    """
    import re
    root = os.path.join(os.path.dirname(__file__), '..', '..')
    banned = []

    def strip_comments(src: str) -> str:
        """Blank out comments, keeping line numbers.

        Necessary because the fix for this very regression documents the banned
        pattern in prose — without this the guard fires on its own explanation.
        Approximate by design: it only needs to stop *discussion* of a filter
        being mistaken for one.
        """
        out, in_block = [], False
        for line in src.split("\n"):
            s = line.strip()
            if in_block:
                out.append("")
                if "*/" in s or "--}}" in s:
                    in_block = False
                continue
            if s.startswith(("#", "//", "*", "{{--", "/*", '"""', "'''")):
                if s.startswith(("/*", "{{--")) and not (s.endswith("*/") or s.endswith("--}}")):
                    in_block = True
                out.append("")
                continue
            out.append(line)
        return "\n".join(out)

    patterns = [
        # SQL: WHERE type = 'City Agency'  /  type IN ('City Agency')
        (re.compile(r"""type["']?\s*=\s*['"]City Agency['"]""", re.I), "SQL equality on a type literal"),
        # JS: DataTables regex filter on a type string
        (re.compile(r"""\.search\(\s*['"]\^[A-Z][A-Za-z ]+\$['"]"""), "client-side type regex filter"),
    ]
    for sub in ("api", "app/app", "app/resources/views"):
        base = os.path.normpath(os.path.join(root, sub))
        for dirpath, _dirs, files in os.walk(base):
            if any(p in dirpath for p in ("vendor", "node_modules", "__pycache__", "/tests")):
                continue
            for fn in files:
                if not fn.endswith((".py", ".php")):
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    src = strip_comments(open(p, encoding="utf-8",
                                              errors="replace").read())
                except OSError:
                    continue
                for rx, why in patterns:
                    for m in rx.finditer(src):
                        line = src[:m.start()].count("\n") + 1
                        banned.append(f"{os.path.relpath(p, root)}:{line} — {why}")
    assert not banned, (
        "org-type filtering must go through api/modules/orgfilter.py, because "
        "`wegov_orgs.type` is a mixed vocabulary and a bare literal fails "
        "SILENTLY:\n  " + "\n  ".join(banned))


def test_every_org_serving_query_filters_retired():
    """⚠ SECOND REGRESSION CLASS, same root cause as the first.

    Retirement is additive — the row stays in `wegov_orgs` — so any query that
    serves org rows and does not exclude it returns a merged-away duplicate.
    Measured 2026-07-30, after the two retirements shipped: both
    `/api/v1/orgs/search?q=public+design` and the MCP `search_organizations`
    tool returned the retired `Public Design Commission` next to the real one.

    Files that SELECT org rows for a user must reference `retired_at` (via
    orgfilter, which probes for the column) somewhere. This is a coarse check —
    it cannot prove the clause lands on the right query — but it fails loudly
    when a new serving file forgets entirely, which is the failure that
    happened.
    """
    import re
    api = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
    # (path, why it serves orgs)
    serving = [
        ("main.py", "org endpoints"),
        ("mcp_server.py", "MCP org tools"),
        ("chatbot.py", "chatbot org lookup"),
        ("routers/search.py", "global search"),
        ("routers/public_v1.py", "public API v1"),
        ("routers/oce.py", "agency name -> org resolution"),
    ]
    missing = []
    for rel, why in serving:
        p = os.path.join(api, rel)
        if not os.path.exists(p):
            continue
        src = open(p, encoding="utf-8", errors="replace").read()
        if "wegov_orgs" not in src:
            continue
        if "retired_at" not in src and "live_clause" not in src \
                and "_live_orgs" not in src and "_orgs_live" not in src:
            missing.append(f"{rel} ({why})")
    assert not missing, (
        "these select org rows but never exclude retired ones, so they will "
        "serve merged-away duplicates:\n  " + "\n  ".join(missing))


@pytest.mark.asyncio
async def test_live_clause_supports_a_table_alias():
    """`wegov_orgs` is joined as `o` inside the /oce/agencies subquery, where a
    bare `retired_at` would be ambiguous to read even where it parses."""
    from modules import orgfilter
    orgfilter.reset_cache()

    async def has_column(sql):
        return {"rows": [{"ok": 1}]}

    assert await orgfilter.live_clause(has_column, "AND", "o") \
        == " AND o.retired_at IS NULL"
    orgfilter.reset_cache()


def test_city_agency_types_are_city_level_only():
    """The agencies page is city agencies. State and non-government types must
    not leak into it, and Community Board / Elected Office have their own
    surfaces."""
    from modules import orgfilter
    for t in ("State Agency", "State Government Agency", "Community Board",
              "Elected Office", "Nonprofit Organization"):
        assert t not in orgfilter.CITY_AGENCY_TYPES
    # the OTI types that ARE city agencies must be present, or the page shrinks
    for t in ("Mayoral Office", "Mayoral Agency", "Division",
              "Advisory or Regulatory Organization"):
        assert t in orgfilter.CITY_AGENCY_TYPES


def test_nonprofits_stay_out_of_the_government_directory():
    """49 Cultural Institutions Group nonprofits hold records so their
    references resolve, but must not appear in a directory of government."""
    from modules import orgfilter
    assert "Nonprofit Organization" in orgfilter.OTI_TYPES
    assert "Nonprofit Organization" not in orgfilter.OTI_GOV_TYPES
    assert "Nonprofit Organization" not in orgfilter.DIRECTORY_TYPES
    assert "Nonprofit Organization" not in orgfilter.CHART_TYPES


def test_sql_type_list_escapes_quotes():
    """These are interpolated into concatenated SQL, so quoting is not optional."""
    from modules import orgfilter
    assert orgfilter.sql_type_list(("a'b",)) == "'a''b'"
    assert orgfilter.sql_type_list(("x", "y")) == "'x', 'y'"


def test_display_name_is_additive_not_a_rename():
    """⚠ `name` must stay put: oce.py::_resolve_org_id matches contracts.agency
    against it by exact equality, and /oce/agency/summary?name= is passed it
    directly, so renaming would zero the procurement figures on ~83 profiles.
    Every URL is built from it too. The adoption therefore writes display_name
    and never touches name."""
    src = open(os.path.join(os.path.dirname(__file__), '..',
                            'adopt_nyc_orgs.py'), encoding='utf-8').read()
    assert "display_name = $2" in src
    assert 'SET name =' not in src and 'SET "name" =' not in src, \
        "the adoption must never rewrite wegov_orgs.name"


def test_id_block_stays_in_the_1701_series():
    """Ids are minted into the existing `1701` series and must fit `integer`."""
    assert adopt.ID_BLOCK_LO == 170100000
    assert adopt.ID_BLOCK_HI < 2_147_483_647


# ── small pure helpers ───────────────────────────────────────────────────────

def test_no_synthetic_airtable_ids_are_minted_any_more():
    """⚠ Phase 6 retired Airtable as an IDENTITY scheme. Synthetic ids
    (`recOTI…`/`recEXTRA…`) existed only so `child_of` could address a new org,
    and `child_of` is gone — the parent is `parent_org_id` and identity is `id`.
    Minting one now would falsely claim Airtable provenance for a row that never
    came from there, and 140 such rows already exist from before the change."""
    assert not hasattr(adopt, "synthetic_airtable_id")
    # ⚠ Comments stripped first, or this fires on the comment that EXPLAINS the
    # banned pattern — the documented trap, hit three times in this session.
    src = "\n".join(ln for ln in inspect.getsource(adopt.import_missing).split("\n")
                    if not ln.lstrip().startswith("#"))
    assert "airtable_id" not in src, "import_missing still writes an airtable_id"
    assert "recEXTRA" not in src, "EXTRA_ORGS still mints a synthetic id"


def test_first_parent_takes_only_one_of_a_multi_parent_value():
    """5 OTI rows are `;`-separated. `main.py:320` joins child_of by EQUALITY
    after stripping brackets/quotes, so two ids in there resolve to no parent
    at all."""
    v = ("Office of the Borough President of The Bronx;"
         "Office of the Borough President of Brooklyn")
    assert adopt.first_parent(v) == "Office of the Borough President of The Bronx"
    assert adopt.first_parent("") == ""
    assert adopt.first_parent(None) == ""


def test_norm_is_order_and_punctuation_sensitive_but_case_blind():
    assert adopt.norm("Mayor's Office of X") == adopt.norm("MAYORS OFFICE OF X")
    assert adopt.norm("A & B") == adopt.norm("A and B")
    assert adopt.norm("Office of X") != adopt.norm("X Office of")


# ── the similarity guard in the normalizer sync ──────────────────────────────

def test_districting_commission_stub_has_an_alias():
    """⚠ The headline fix of the whole adoption. 12 datasets map by hand to the
    core key `NYC Districting Commission`, but the org's name -- OTI's -- is
    `New York City Districting Commission`, so the register-derived feed cannot
    emit the short form itself. Since Phase 2 the alias lives in the
    `org_core_aliases` seed; drop it and the next refresh orphans all 12."""
    import importlib
    seedmod = importlib.import_module("seed_org_core_aliases")
    seed = {name: org_id for name, org_id, _ in seedmod.SEED}
    assert seed.get("NYC Districting Commission") == 170100330


def test_similarity_guard_admits_real_variance():
    """`Cyber Command` and `NYC Cyber Command` are the same body."""
    assert syncore.sim("Cyber Command", "NYC Cyber Command") >= syncore.NAME_SIM_MIN


def test_similarity_guard_rejects_the_known_bad_crosswalk_link():
    """OTI's `Community Services Board` (a DOHMH body) is linked by the
    token-set pass to our `Manhattan Community Board # 1`. Repointing a core
    entity there would stamp that false positive onto ingested data, so the
    guard must hold it."""
    assert syncore.sim("Community Services Board",
                       "Manhattan Community Board # 1") < syncore.NAME_SIM_MIN


def test_only_the_token_set_tier_is_similarity_guarded():
    """⚠ The tier says HOW a link was made, which beats string similarity.
    Guarding `exact/alias` too held two CORRECT links on the first run --
    `NYC & Company` -> `New York City Tourism + Conventions` (renamed in 2023,
    sim 0.25) and `TSASC, Inc` -> `Tobacco Settlement Asset Securitization
    Corporation` (an acronym, sim 0.20). Both are legitimate alias matches."""
    assert syncore.GUARDED_TIERS == ("token-set",)
    # the two real links a blanket guard wrongly held
    assert syncore.sim("NYC & Company",
                       "New York City Tourism + Conventions") < syncore.NAME_SIM_MIN
    assert syncore.sim("TSASC, Inc",
                       "Tobacco Settlement Asset Securitization Corporation") \
        < syncore.NAME_SIM_MIN
    for tier in ("exact/alias", "curated", "imported"):
        assert tier not in syncore.GUARDED_TIERS


def test_only_the_oti_dataset_is_rewritten():
    """Every other dataset's org matches are years of human curation."""
    assert syncore.OTI_DATASET_ID == 328


# ── the serving filter ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_orgfilter_returns_empty_clause_when_column_absent():
    """A database that has not run the adoption must not 500 -- and must not
    silently return an empty org search either (routers/search.py::_rows
    swallows exceptions, cf. #146), which is why absence yields ''."""
    from modules import orgfilter
    orgfilter.reset_cache()

    async def no_column(sql):
        return []

    assert await orgfilter.live_clause(no_column) == ""
    orgfilter.reset_cache()


@pytest.mark.asyncio
async def test_orgfilter_emits_the_clause_when_column_present():
    from modules import orgfilter
    orgfilter.reset_cache()

    async def has_column(sql):
        return {"rows": [{"ok": 1}]}

    assert await orgfilter.live_clause(has_column) == " AND retired_at IS NULL"
    assert await orgfilter.live_clause(has_column, "WHERE") == \
        " WHERE retired_at IS NULL"
    orgfilter.reset_cache()


@pytest.mark.asyncio
async def test_orgfilter_probes_once_then_caches():
    """The probe hits information_schema; it must not run per request."""
    from modules import orgfilter
    orgfilter.reset_cache()
    calls = []

    async def counting(sql):
        calls.append(sql)
        return {"rows": [{"ok": 1}]}

    await orgfilter.live_clause(counting)
    await orgfilter.live_clause(counting)
    await orgfilter.live_clause(counting)
    assert len(calls) == 1
    orgfilter.reset_cache()


@pytest.mark.asyncio
async def test_orgfilter_survives_a_failing_probe():
    from modules import orgfilter
    orgfilter.reset_cache()

    async def boom(sql):
        raise RuntimeError("no such table")

    assert await orgfilter.live_clause(boom) == ""
    orgfilter.reset_cache()


# ── Phase 1: the restored org-chart scaffolding ──────────────────────────────

def test_chart_nodes_are_not_organizations():
    """`Classification` (a grouping node) and `Official` (a person-role node)
    are chart scaffolding, not organizations. They belong in the chart and must
    stay out of the directory, the all-orgs list, and the agencies page."""
    from modules import orgfilter
    restore = importlib.import_module("restore_org_chart_nodes")
    for spec in restore.CHART_NODES:
        assert spec["type"] in ("Classification", "Official"), spec["name"]
        assert spec["type"] not in orgfilter.DIRECTORY_TYPES
        assert spec["type"] not in orgfilter.CITY_AGENCY_TYPES
        assert spec["type"] in orgfilter.CHART_TYPES


def test_restored_nodes_keep_their_original_identifiers():
    """⚠ This is a RESTORATION, not an invention, and the identifiers are what
    make it one:

      * the original `airtable_id` came from the `child_of` of orgs still
        pointing at it, so recreating the row fixes every child with NO edit to
        any child;
      * the original `org_id` came from the normalizer core, which still held
        five of them — and those five are exactly the long-reported 'core
        entities whose id resolves to nothing'.

    Change either and the restoration silently becomes a re-parenting exercise
    that leaves the old references dangling."""
    restore = importlib.import_module("restore_org_chart_nodes")
    by_name = {s["name"]: s for s in restore.CHART_NODES}
    # ids recovered from the normalizer core, with the type it recorded
    assert by_name["Chief of Staff"]["org_id"] == 170100017
    assert by_name["District Attorneys"]["org_id"] == 170020021
    assert by_name["Chief Climate Officer"]["org_id"] == 170100240
    assert by_name["Chief Technology Officer"]["org_id"] == 170100034
    assert by_name["Deputy Mayor for Economic and Workforce Development"]["org_id"] == 170100230
    # airtable_ids recovered from the children still pointing at them
    assert by_name["Elected County Officials"]["airtable_id"] == "reckRTIpmsRKae8IU"
    assert by_name["District Attorneys"]["airtable_id"] == "recTJbjZQCIIagGse"
    assert by_name["The People of the City of New York"]["airtable_id"] == "rechr1BnnpiKGguXH"


def test_not_on_chart_bucket_is_never_restored_as_a_row():
    """It became a flag (owner decision, corroborated by OTI 24/24). Restoring
    it as a node would put "absent from the chart" back INTO the chart."""
    restore = importlib.import_module("restore_org_chart_nodes")
    names = {s["name"] for s in restore.CHART_NODES}
    assert "Additional Mayoral Agencies (Not on Chart)" not in names
    assert restore.NOT_ON_CHART_AIRTABLE_ID == "recTZLn26klvFYOxj"


@pytest.mark.asyncio
async def test_in_chart_clause_excludes_only_explicit_false():
    """NULL means 'not stated' and must stay on the chart — an org we have no
    opinion about behaves exactly as it did before the flag existed."""
    from modules import orgfilter
    orgfilter.reset_cache()

    async def has_column(sql):
        return {"rows": [{"ok": 1}]}

    clause = await orgfilter.in_chart_clause(has_column)
    assert clause == " AND in_org_chart IS NOT FALSE"
    assert "IS TRUE" not in clause, "IS TRUE would drop every unstated org"
    orgfilter.reset_cache()


@pytest.mark.asyncio
async def test_in_chart_clause_degrades_when_column_absent():
    from modules import orgfilter
    orgfilter.reset_cache()

    async def no_column(sql):
        return []

    assert await orgfilter.in_chart_clause(no_column) == ""
    orgfilter.reset_cache()


# ── Phase 4a: safe to run unattended ─────────────────────────────────────────

def test_rejected_links_are_keyed_on_the_pair_not_the_record():
    """⚠ Keyed on `nyc_record_id` alone, a rejection rejected EVERY row for that
    record — including the `imported` link to the org created FOR it. Measured on
    the first scheduled run: NYC_GOID_000119 gained a second rejected row that
    cut `Community Services Board` (170100385) off from its own OTI record, and
    coverage fell 306 -> 305.

    A rejection means "this record is not THAT org". It must never be readable as
    "this record belongs to no org"."""
    for key in adopt.REJECTED_LINKS:
        assert isinstance(key, tuple) and len(key) == 2, \
            f"REJECTED_LINKS key {key!r} must be (nyc_record_id, wrong_org_id)"
        rec, org_id = key
        assert isinstance(rec, str) and rec.startswith("NYC_GOID_")
        assert isinstance(org_id, int)
    # the specific pair the owner refused, and the org it must NOT touch
    assert ("NYC_GOID_000119", 170010341) in adopt.REJECTED_LINKS
    assert ("NYC_GOID_000119", 170100385) not in adopt.REJECTED_LINKS


def test_rejection_update_is_scoped_to_one_org():
    """The UPDATE must filter on wegov_org_id too, or it re-breaks the above."""
    src = open(os.path.join(os.path.dirname(__file__), '..',
                            'adopt_nyc_orgs.py'), encoding='utf-8').read()
    i = src.index("SET match_tier = 'rejected'")
    stmt = src[i:i + 240]
    assert "wegov_org_id = $2" in stmt, \
        "the rejection UPDATE must be scoped to the one wrong pair"


def test_crosswalk_rebuild_refuses_a_short_upstream_response():
    """⚠ The rebuild DELETEs every non-curated row before re-inserting, so a
    short or empty Socrata response would wipe the crosswalk and replace it with
    nothing. Socrata does return 200 with a truncated body under load — that is
    the documented cause of a silent fiscal-year truncation in the Checkbook
    extractors (#117). Now that this runs on a cron, the guard is essential."""
    src = open(os.path.join(os.path.dirname(__file__), '..',
                            'build_nyc_org_crosswalk.py'), encoding='utf-8').read()
    assert "NYC_ORG_MIN_EXPECTED" in src
    assert "refusing to rebuild" in src
    # and the delete/insert must be transactional, or a mid-run failure leaves a
    # partial crosswalk that reads as a successful rebuild with fewer matches
    assert "conn.transaction()" in src
    assert "tx.rollback()" in src
