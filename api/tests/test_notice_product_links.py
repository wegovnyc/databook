"""Guards for the licence-product <-> City Record notice crosswalk.

Four things can silently break this, and three of them fail in the reassuring
direction — the panel simply renders nothing, which is indistinguishable from
"this product appears in no notices":

1. the index expression and the batch's query expression drift, so the planner
   cannot use idx_crol_body_fts and 774 probes become 774 sequential scans of a
   464 MB heap. Nothing errors; the hook just takes minutes instead of 2.4s.
2. the batch runs against an unbuilt catalogue and writes a near-empty table,
   which reads exactly like "no product is mentioned anywhere".
3. an exclusion is dropped, so an ordinary English word starts attaching
   hundreds of false notices to a named vendor's page (Streetscape: 144).
4. the panel loses its disclaimer and starts implying that a mention is a
   purchase.

⚠ modules/ is a MagicMock under conftest.py, so anything dependency-free is
loaded BY PATH.
"""
import importlib.util
import io
import os
import re

import pytest

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
BUILDER = os.path.join(ROOT, 'api/build_notice_product_links.py')
SCHEDULER = os.path.join(ROOT, 'api/data_scheduler.py')
LICENSES = os.path.join(ROOT, 'api/routers/licenses.py')
FAMILY_VIEW = os.path.join(
    ROOT, 'app/resources/views/procurement/digital-reform-license-family.blade.php')
SEED = os.path.join(ROOT, 'api/seed/license_family_notice_exclusions.csv')


def _read(path):
    with io.open(path, encoding='utf-8') as fh:
        return fh.read()


def _load_by_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _builder():
    return _load_by_path('_npl', BUILDER)


# ---------------------------------------------- 1. the expressions cannot drift

def _tsvector_exprs(text):
    """Every `to_tsvector(<config>, coalesce(...))` as (config, column).

    ⚠ The CONFIG is captured, not hardcoded. An `english` index with a `simple`
    query is the same silent failure as a mismatched column — the index simply
    is not used, with no error.
    """
    out = []
    for m in re.finditer(
            r"to_tsvector\(\s*'(\w+)'\s*,\s*coalesce\(([^)]*)\)\s*\)", text):
        out.append((m.group(1), re.sub(r'\s+', '', m.group(2))))
    return out


def _tsquery_configs(text):
    """Every text-search config named in a phraseto_tsquery call."""
    return set(re.findall(r"phraseto_tsquery\(\s*'(\w+)'", text))


def test_the_index_expression_and_the_batch_query_are_the_same_expression():
    """⚠ THE SILENT ONE. Postgres matches an expression index on the parsed
    expression, so a DIFFERENT expression is simply not served by the index — no
    error, no warning, just 774 seq scans of a 464 MB heap on every crol ingest.

    Compared as normalised text rather than by eye, and asserted to have found
    something on BOTH sides, so it cannot pass by matching nothing.
    """
    idx = _load_by_path('_si', os.path.join(ROOT, 'api/modules/searchindexes.py'))
    decl = [body for name, _tbl, body in idx.INDEXES if name == 'idx_crol_body_fts']
    assert decl, "idx_crol_body_fts is no longer declared in searchindexes.py"

    from_index = _tsvector_exprs(decl[0])
    from_batch = _tsvector_exprs(_read(BUILDER))
    assert from_index, "could not read the tsvector argument out of the declaration"
    assert from_batch, "could not read the tsvector argument out of the batch query"

    # The batch aliases the table, so compare on the column, not the qualifier.
    norm = lambda e: e.split('.')[-1].replace('"', '').lower()
    assert norm(from_index[0][1]).startswith('additionaldescription1'), from_index
    assert {(c, norm(e)) for c, e in from_batch} == {(from_index[0][0],
                                                     norm(from_index[0][1]))}, (
        f"batch queries {from_batch} but the index declares {from_index} — "
        "the index cannot serve this query")
    # And every tsquery must name that same configuration.
    assert _tsquery_configs(_read(BUILDER)) == {from_index[0][0]}, (
        "a phraseto_tsquery names a different text-search configuration than the "
        "index — the index cannot serve it")


def test_the_notice_index_does_not_stem():
    """⚠ `simple`, not `english`. The snowball stemmer collapses brand names onto
    ordinary stems, so a distinctive product name matches notices that never
    contain it: `Feedly` -> 'feed' matched 121 notices about data feeds, and
    `Mobilize` -> 'mobil' matched 2,388 saying "mobile". Measured english ->
    simple: Feedly 121 -> 0, Mobilize 2,388 -> 11, while Oracle stays 363."""
    idx = _load_by_path('_si3', os.path.join(ROOT, 'api/modules/searchindexes.py'))
    body = [b for n, _t, b in idx.INDEXES if n == 'idx_crol_body_fts'][0]
    assert "'simple'" in body and "'english'" not in body, \
        "the notice-body index started stemming again; brand names will match " \
        "ordinary words (Feedly -> 'feed')"


def test_the_declared_index_is_the_body_only_vector():
    """The weighted `setweight(title,'A') || setweight(body,'B')` form exists to
    rank titles above bodies for interactive search, which nothing does. Declaring
    it would imply a ranking decision with no consumer, and cost 2 MB for it."""
    idx = _load_by_path('_si2', os.path.join(ROOT, 'api/modules/searchindexes.py'))
    body = [b for n, _t, b in idx.INDEXES if n == 'idx_crol_body_fts'][0]
    assert 'setweight' not in body, \
        "the notice-body index became a weighted vector; nothing ranks these"


def test_the_batch_does_not_strip_html():
    """Postgres's parser maps token type `tag` to no dictionary, so tags produce
    no lexemes — verified with ts_debug on prod, and only 3.9% of bodies contain
    one. A regexp_replace wrapper would cost build time, buy nothing, and
    reintroduce the byte-identical index/query trap it was meant to avoid."""
    src = _read(BUILDER)
    code = '\n'.join(l for l in src.splitlines() if not l.strip().startswith('#'))
    assert 'regexp_replace' not in code, \
        "HTML stripping reintroduced — see the module docstring for why it is not needed"


# ------------------------------------------- 2. a run that considered nothing

class _StubConn:
    """Minimal asyncpg stand-in: enough to drive run() without a database."""

    def __init__(self, families):
        self._families = families
        self.executed = []

    async def execute(self, sql, *args):
        self.executed.append(sql)

    async def fetch(self, sql, *args):
        if 'license_family' in sql:
            return [{'family': f} for f in self._families]
        return []          # nothing is unqueryable

    async def fetchval(self, sql, *args):
        return 0

    def transaction(self):
        class _T:
            async def __aenter__(self_inner):
                return self_inner

            async def __aexit__(self_inner, *a):
                return False
        return _T()


@pytest.mark.asyncio
async def test_a_run_against_an_unbuilt_catalogue_raises_instead_of_writing():
    """⚠ THE ZERO-FILES-SCANNED CLASS. A batch that considered nothing and a batch
    that found nothing produce the same empty table. The classifier that printed
    "Done. 0 classified" and exited 0 is the same bug, and its cron pinged SUCCESS.
    """
    npl = _builder()
    conn = _StubConn(['Microsoft', 'Citrix'])          # a catalogue of 2
    with pytest.raises(RuntimeError, match='refusing'):
        await npl.run(conn, apply=True, verbose=False)
    assert not any('INSERT INTO _staging' in s for s in conn.executed), \
        "it wrote rows despite the catalogue being unbuilt"


@pytest.mark.asyncio
async def test_a_healthy_catalogue_is_matched_and_the_skips_are_reported(capsys):
    """The skip counts must be PRINTED. MIN_NAME_LEN is a threshold, and a
    threshold nobody can see is indistinguishable from an opinion — the rule this
    page already applies to the consolidation badge."""
    npl = _builder()
    fams = [f'Product{i:04d}' for i in range(800)] + ['Box', 'Zoom', 'Streetscape']
    await npl.run(_StubConn(fams), apply=False, verbose=True)
    out = capsys.readouterr().out
    assert re.search(r'shorter than \d+ chars:\s*\d+', out), \
        "the short-name skip is no longer reported"
    assert 'curated exclusions:' in out, "the exclusion skip is no longer reported"
    assert 'Streetscape' in out, "excluded families are no longer named with a reason"


# --------------------------------------------------------- 3. the exclusions

def _seed_rows():
    import csv
    with io.open(SEED, encoding='utf-8') as fh:
        return list(csv.DictReader(l for l in fh if not l.startswith('#')))


def test_every_exclusion_states_why_and_none_is_duplicated():
    rows = _seed_rows()
    assert len(rows) >= 10, f"the exclusion seed collapsed to {len(rows)} rows"
    fams = [r['family'].strip() for r in rows]
    assert len(fams) == len(set(fams)), "a family is excluded twice"
    for r in rows:
        assert (r.get('reason') or '').strip(), \
            f"{r['family']} is excluded with no stated reason"


def test_the_ordinary_english_words_stay_excluded():
    """Each of these was MEASURED as noise. Losing one silently attaches hundreds
    of false notices to a real vendor's product page — Mobilize alone is 2,388."""
    fams = {r['family'].strip() for r in _seed_rows()}
    for f in ('Mobilize', 'Reach', 'Summer', 'CLEAR', 'Streetscape', 'Box'):
        assert f in fams, f"{f} is no longer excluded from notice matching"


def test_webex_and_zoom_stay_excluded_by_owner_decision():
    """Owner decision, 2026-08-18. Both are genuine products the City buys, so a
    later reader may reasonably think their exclusion is a mistake — it is not.
    The mentions are 'join the hearing via Webex', and word boundaries do not
    help (Zoom: 1,563 naive vs 1,557 word-bounded)."""
    rows = {r['family'].strip(): r['reason'] for r in _seed_rows()}
    for f in ('Webex', 'Zoom'):
        assert f in rows, f"{f} was un-excluded; this was an explicit owner decision"
        assert 'wner decision' in rows[f], \
            f"{f}'s reason no longer records that this was an owner decision"


def test_the_second_owner_review_stays_excluded():
    """Owner decision, 2026-08-18, after seeing the post-exclusion top list.

    ⚠ Two of these are not product names at all, which is why they read oddly in
    an exclusion list of "ordinary English words": `Mainframe Software` was read
    by the classifier off the contract title "MAINFRAME SOFTWARE MAINTENANCE
    (ACCENTURE)", and `Community Software Solutions` is the VENDOR's name. The
    other two are real products — Articulate 360 and the Domino data-science
    platform — whose names are an ordinary verb and an ordinary noun.
    """
    rows = {r['family'].strip(): r['reason'] for r in _seed_rows()}
    for f in ('Articulate', 'Domino', 'Mainframe Software',
              'Community Software Solutions'):
        assert f in rows, f"{f} was un-excluded; this was an explicit owner decision"
        assert 'wner decision' in rows[f], \
            f"{f}'s reason no longer records that this was an owner decision"


# --------------------------------------------- 4. registration and the panel

def test_the_hook_is_registered_on_crol_so_it_lands_after_the_index_hook():
    """The registration loop does insert(0, index_lambda) for every table in
    TABLE_INDEXES | searchindexes.tables(), and crol is in both. Naming crol in
    the dict literal therefore leaves the order [indexes, links]. Reversed, the
    probes seq-scan."""
    src = _read(SCHEDULER)
    assert 'derive_notice_product_links_hook' in src, "the hook is not registered"
    literal = src[src.index('POST_INGEST_HOOKS = {'):]
    literal = literal[:literal.index('\n}')]
    assert re.search(r'"crol":\s*\[derive_notice_product_links_hook\]', literal), \
        "crol is no longer registered in the POST_INGEST_HOOKS literal"


def test_the_crol_import_path_actually_INVOKES_the_hooks():
    """⚠⚠ THE BUG THIS PR SHIPPED AND THIS TEST EXISTS TO PREVENT. Registering a
    hook on `POST_INGEST_HOOKS['crol']` is not enough: crol does NOT arrive through
    the scheduler. All four `run_post_ingest_hooks` call sites live in
    data_scheduler and fire only for tables the scheduler ingests, while crol comes
    in through main.py's /import-crol endpoint (the normalizer POSTs to it).

    Measured on prod 2026-08-18: after a real crol ingest the index WAS restored
    (main.py calls recreate_table_indexes directly) but
    `notice_product_links.built_at` never moved, because nothing invoked the hooks.
    The tell in the log is that contracts/solicitations/vendors each print
    "[hooks] Running N post-ingest hook(s)" before their index lines and crol
    printed its index lines with no such wrapper.

    This is the same family as `register_untracked_tables()` being unreachable in
    prod and the unmapped-entity scan starved by the other path's success: a
    declaration on a mechanism that never runs. Verifying that a hook is REGISTERED
    and correctly ORDERED says nothing about whether anything CALLS it.
    """
    src = _read(os.path.join(ROOT, 'api/main.py'))
    # Both crol import paths must go through the hook runner.
    calls = re.findall(r"run_post_ingest_hooks\(\s*['\"]crol['\"]", src)
    assert len(calls) >= 2, (
        f"only {len(calls)} crol import path(s) invoke run_post_ingest_hooks; "
        "a hook registered on crol will silently never fire")
    # And none of them may quietly go back to rebuilding indexes only, which
    # restores the index and skips every other hook — the exact failure above.
    assert "recreate_table_indexes(db, 'crol')" not in src, \
        "a crol import path rebuilds indexes directly again, bypassing the hooks"


def test_the_panel_says_a_mention_is_not_a_purchase():
    """⚠ The whole panel rests on this sentence. Per-product yield is 5-24 notices
    and the matcher is a name match on prose, so without the disclaimer the page
    implies procurement activity it has not measured."""
    view = _read(FAMILY_VIEW)
    assert 'notices' in view, "the notices panel is gone from the family view"
    assert 'A mention is not a purchase' in view, \
        "the panel lost the sentence that stops it implying procurement activity"


def test_the_family_payload_reports_the_unsliced_notice_total():
    """A capped list presented as the whole set is the `by_vendor` defect — 25 of
    88 rows under a heading implying all of them."""
    src = _read(LICENSES)
    assert '"notices_total"' in src, "the unsliced total is no longer served"
    body = src[src.index('async def _notices_for_family'):]
    body = body[:body.index('\nasync def ', 10)] if '\nasync def ' in body[10:] else body
    assert 'count(*) OVER ()' in body, \
        "the total is no longer measured on the unsliced set"
    assert 'LIMIT $2' in body, "the notice list is no longer capped"
