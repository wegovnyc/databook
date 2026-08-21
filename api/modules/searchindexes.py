"""The global-search GIN indexes, declared once and applied by every ingest path.

⚠⚠ WHY THIS MODULE EXISTS. These were declared in TWO places that could not see each
other — `scripts/search_indexes.sql` (a "run once on prod" script) and a literal list
inside `main.py`, applied only by `/import-csv`. `contracts` and `solicitations` do
NOT go through `/import-csv`: the extractor path COPYs into `_staging_<table>`, drops
the real table and renames staging over it, so their indexes were destroyed at every
ingest and nothing recreated them. Measured on prod 2026-08-13: **5 of the 19
declared search indexes were absent, all 5 of them on those two tables**, and global
search over contracts had been running as a sequential scan of all 55,806 rows.

A `CREATE INDEX IF NOT EXISTS` script is not a record that the index exists — it
re-runs cleanly whether or not anything persisted. Only `pg_indexes` knows.

⚠ THE RULE THIS ENCODES: an index on a pipeline-loaded table must be DECLARED where
a post-ingest hook can reapply it, never hand-created. Same rule as
`data_scheduler.TABLE_INDEXES`; this is its GIN half, because that map renders
`CREATE INDEX ... ON tbl(expr)` and cannot express `USING gin (... gin_trgm_ops)`.

⚠⚠ AND A DECLARED INDEX IS NOT AUTOMATICALLY A USED ONE. `routers/search.py` ORs
several columns together (`title ILIKE ... OR vendor ILIKE ... OR contract_id ILIKE
... OR to_tsvector(...) @@ ...`). Postgres can only build a BitmapOr when EVERY branch
is indexable, so with `contract_id` unindexed the planner ignored the other three and
seq-scanned anyway — measured: 393.9ms with the three title/vendor indexes present,
1.8ms once `contract_id` had one too. Hence the `_id_trgm` / `_epin_trgm` entries: they
exist to make the OTHER indexes reachable. **If a new OR branch is added to a search
query, it needs an index here or it silently disables the whole BitmapOr.**
"""
from typing import List, Tuple

# (index_name, table, index_body). The body follows `USING`.
INDEXES: List[Tuple[str, str, str]] = [
    ("idx_orgs_name_trgm",        "wegov_orgs",            'gin (name gin_trgm_ops)'),
    ("idx_orgs_altname_trgm",     "wegov_orgs",            'gin ("alternate_name" gin_trgm_ops)'),
    ("idx_orgs_name_fts",         "wegov_orgs",            "gin (to_tsvector('english', name))"),
    ("idx_orgs_altname_fts",      "wegov_orgs",            "gin (to_tsvector('english', \"alternate_name\"))"),
    ("idx_titles_descr_trgm",     "nyccivilservicetitles", 'gin ("Title Description" gin_trgm_ops)'),
    ("idx_titles_descr_fts",      "nyccivilservicetitles", "gin (to_tsvector('english', \"Title Description\"))"),
    ("idx_contracts_title_trgm",  "contracts",             'gin (contract_title gin_trgm_ops)'),
    ("idx_contracts_vendor_trgm", "contracts",             'gin (vendor_name gin_trgm_ops)'),
    ("idx_contracts_title_fts",   "contracts",             "gin (to_tsvector('english', contract_title))"),
    # ⚠ NOT decoration: `_contracts()` ORs `contract_id ILIKE` into the same WHERE,
    # and one unindexed branch forces a seq scan over all four. 393.9ms -> 1.8ms.
    ("idx_contracts_id_trgm",     "contracts",             'gin (contract_id gin_trgm_ops)'),
    ("idx_solic_name_trgm",       "solicitations",         'gin ("Procurement Name" gin_trgm_ops)'),
    ("idx_solic_name_fts",        "solicitations",         "gin (to_tsvector('english', \"Procurement Name\"))"),
    # Same reason as idx_contracts_id_trgm — `_solicitations()` ORs `"EPIN" ILIKE`.
    # ⚠ Distinct from `idx_solicitations_epin` (a btree from TABLE_INDEXES): a btree
    # cannot serve `ILIKE '%x%'`, so both are needed and neither is redundant.
    ("idx_solic_epin_trgm",       "solicitations",         'gin ("EPIN" gin_trgm_ops)'),
    ("idx_capproj_desc_trgm",     "capitalprojectslist",   'gin (description gin_trgm_ops)'),
    ("idx_capproj_desc_fts",      "capitalprojectslist",   "gin (to_tsvector('english', description))"),
    ("idx_crol_shorttitle_trgm",  "crol",                  'gin ("ShortTitle" gin_trgm_ops)'),
    ("idx_crol_shorttitle_fts",   "crol",                  "gin (to_tsvector('english', \"ShortTitle\"))"),
    # ⚠ THE NOTICE BODY, and it is NOT for interactive search — it exists so
    # `build_notice_product_links.py` can probe 757 product names against 1.1M
    # notices in one batch (measured: 0.79s, planned as 757 bitmap index scans).
    # Without it those probes are 774 sequential scans of a 464 MB heap.
    # 82 MB, ~45s to build, both measured on prod against the real row set
    # (the `simple` index is larger than a stemmed one — no stop-word removal —
    # but faster to build, because nothing is stemmed).
    #
    # ⚠ NO regexp_replace WRAPPER, deliberately. The bodies contain HTML in 3.9%
    # of rows and an earlier plan required stripping it at index AND query time,
    # byte-identically — the classic expression-index trap. It is unnecessary:
    # Postgres's default parser classifies `<p>`/`<b>` as token type `tag`, which
    # the `english` configuration maps to NO dictionary, so tags produce no
    # lexemes at all (verified with ts_debug, not assumed). A wrapper would cost
    # build time, buy nothing, and reintroduce the trap it was meant to avoid.
    #
    # ⚠⚠ `simple`, NOT `english` — the ONLY index here that is, and it is
    # load-bearing. This one matches PRODUCT NAMES, and the English snowball
    # stemmer collapses brand names onto ordinary stems: `Feedly` stems to
    # 'feed', so it matched 121 notices about data FEEDS in which the word
    # "Feedly" never appears at all. `Mobilize` stems to 'mobil' and matched
    # 2,388 notices, almost all of them saying "mobile". Measured on prod:
    # Feedly 121 -> 0 and Mobilize 2,388 -> 11 under `simple`, while genuinely
    # distinctive names are untouched (Oracle 363 -> 363, Gartner 48 -> 48,
    # DocuSign 18 -> 18). Stemming is right for prose search and wrong for
    # proper nouns.
    #
    # ⚠ The BODY-ONLY vector, not `setweight(title,'A') || setweight(body,'B')`.
    # The weighted form exists to rank titles above bodies for interactive search,
    # which nothing does — declaring it here would imply a ranking decision that
    # has no consumer. See docs/NOTICE-PRODUCT-CROSSWALK-PLAN.md for why body
    # search itself is not built (ranking makes it O(matches): "construction"
    # goes 150ms/7,893 rows to 831ms/15,321).
    ("idx_crol_body_fts",         "crol",                  "gin (to_tsvector('simple', coalesce(\"AdditionalDescription1\", '')))"),
    ("idx_schools_name_trgm",     "schoollocations",       'gin (location_name gin_trgm_ops)'),
    ("idx_schools_name_fts",      "schoollocations",       "gin (to_tsvector('english', location_name))"),
    ("idx_cla_name_trgm",         "civillistactive",       'gin ((("First Name" || \' \' || "Last Name")) gin_trgm_ops)'),
    ("idx_gb_name_trgm",          "nycgreenbook",          'gin ((("First Name" || \' \' || "Last Name")) gin_trgm_ops)'),
    # ⚠ THE PEOPLE-SEARCH TRIGRAMS, moved here from a THIRD declaration site —
    # `main.py::ensure_people_indexes()`, which runs at STARTUP rather than after an
    # ingest. Found by the one-owner guard below, not by reading: `idx_cla_name_trgm`
    # was declared in both places, so the same index had two homes and neither knew
    # about the other. Startup creation is a weak mechanism for a pipeline-loaded
    # table — it only heals on the next api restart — so they belong on the hook.
    ("idx_civillist_name_trgm",   "civillist",             'gin ("EMPLOYEE NAME" gin_trgm_ops)'),
    ("idx_payrolldata_name_trgm", "payrolldata",           'gin ((("First Name" || \' \' || "Last Name")) gin_trgm_ops)'),
]


def tables() -> set:
    """Every table carrying a search index."""
    return {tbl for _, tbl, _ in INDEXES}


def for_table(table: str) -> List[Tuple[str, str, str]]:
    return [row for row in INDEXES if row[1] == table]


async def ensure(conn, table: str, log=None) -> int:
    """Recreate this table's search indexes. Idempotent; returns how many succeeded.

    ⚠ BEST-EFFORT BY DESIGN, like the btree hook next to it: a missing column or a
    missing pg_trgm must not abort an ingest that has already written its rows. But
    every failure is LOGGED with the index name — a silent ✗ is how five of these came
    to be missing for months with nothing reporting it.
    """
    rows = for_table(table)
    if not rows:
        return 0
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    except Exception as exc:  # noqa: BLE001
        if log:
            log(f"[indexes] pg_trgm ensure failed: {type(exc).__name__}: {exc}")
    made = 0
    for name, tbl, body in rows:
        try:
            await conn.execute(f'CREATE INDEX IF NOT EXISTS {name} ON "{tbl}" USING {body}')
            made += 1
        except Exception as exc:  # noqa: BLE001
            if log:
                log(f"[indexes] ✗ search index {name} on {tbl}: {type(exc).__name__}: {exc}")
    return made
