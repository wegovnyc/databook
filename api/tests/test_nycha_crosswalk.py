"""Unit tests for the NYCHA->PASSPort crosswalk matching logic (pure functions;
no DB/DuckDB needed)."""
import importlib

xw = importlib.import_module("build_nycha_vendor_crosswalk")


def test_norm_strips_suffix_and_punct():
    assert xw.norm("Fine Touch Constructions, Inc.") == "FINE TOUCH CONSTRUCTIONS"
    assert xw.norm("A&M Fire-Out, LLC") == "A M FIRE OUT"


def test_norm_strips_apostrophes():
    # ADAM'S -> ADAMS (dropped, not spaced) so it exact-matches NYCHA "ADAMS".
    assert xw.norm("ADAM'S EUROPEAN CONTRACTING INC") == "ADAMS EUROPEAN CONTRACTING"
    assert xw.norm("ADAMS EUROPEAN CONTRACTING INC.") == xw.norm("ADAM'S EUROPEAN CONTRACTING INC")
    assert xw.norm("O'Brien & Sons") == "OBRIEN SONS"


def test_fuzzy_high_accepts_clear_variants():
    pv = [("ACTION CARTING ENVIRONMENTAL SERVICES", "1", "Action Carting Environmental Services Inc")]
    high, review = xw._fuzzy_matches(["ACTION CARTING ENVIRONMENTAL SERVICE INC."], pv)
    assert [h[0] for h in high] == ["ACTION CARTING ENVIRONMENTAL SERVICE INC."]
    assert high[0][1] == "1" and high[0][3] >= xw.FUZZY_HIGH


def test_fuzzy_rejects_identity_token_swap():
    """BERNARDO'S vs GERARD'S (same generic tokens, different identity) must NOT
    auto-link — a false positive that motivated the conservative threshold."""
    pv = [("GERARDS PLUMBING HEATING", "2", "Gerards Plumbing Heating Corp")]
    high, review = xw._fuzzy_matches(["BERNARDOS PLUMBING & HEATING CORP"], pv)
    assert [h[0] for h in high] == []  # not in the auto-link tier


def test_fuzzy_rejects_generic_token_collapse():
    """Different firms whose names collapse to a shared generic token (GROUP/CORP
    stripped, short identity dropped) must NOT auto-link — the magnet-cluster bug
    (e.g. "B2 CONSTRUCTION" vs "J & N Construction Group Corp")."""
    pv = [(xw.norm("J & N Construction Group Corp"), "9", "J & N Construction Group Corp")]
    high, review = xw._fuzzy_matches(["B2 CONSTRUCTION CORP"], pv)
    assert [h[0] for h in high] == []


def test_load_curated_absent(monkeypatch):
    monkeypatch.delenv("NYCHA_CURATED_XWALK_CSV", raising=False)
    assert xw._load_curated() == []


def test_load_curated_parses_confirms_and_rejections(tmp_path, monkeypatch):
    """Curated CSV: a real id = confirmed link; a '-' marker = reviewed rejection
    (id None) so the pair neither auto-links nor returns to the review queue."""
    # Names are QUOTED — 47 of the 212 reviewed NYCHA names contain a comma
    # ("C.D.E. AIR CONDITIONING CO, INC."), so the file must be real CSV.
    p = tmp_path / "curated.csv"
    p.write_text(
        "nycha_vendor_name,passport_supplier_id,note\n"
        '"W.B. MASON CO., INC.",1623399,confirmed same vendor\n'
        "DF CONTRACTING INC,-,NOT MDF CONTRACTING CORP\n"
        '"SAM\'S TECHNICAL SERVICES INC.",none,NOT SLAM Technical Services\n',
        encoding="utf-8")
    monkeypatch.setenv("NYCHA_CURATED_XWALK_CSV", str(p))
    rows = xw._load_curated()
    assert len(rows) == 3
    by = {r[0]: r[1] for r in rows}
    assert by["W.B. MASON CO., INC."] == "1623399"          # confirmed
    assert by["DF CONTRACTING INC"] is None                  # '-' -> rejection
    assert by["SAM'S TECHNICAL SERVICES INC."] is None       # 'none' -> rejection


def test_load_curated_defaults_to_data_lake_path(tmp_path, monkeypatch):
    """With no env var set, the generator picks up <DATA>/nycha_curated_xwalk.csv
    so the weekly auto-refresh applies the review with no env plumbing."""
    monkeypatch.delenv("NYCHA_CURATED_XWALK_CSV", raising=False)
    monkeypatch.setattr(xw, "DATA", str(tmp_path))
    assert xw._load_curated() == []                          # absent -> no rows
    (tmp_path / "nycha_curated_xwalk.csv").write_text(
        "nycha_vendor_name,passport_supplier_id,note\nFOO INC,999,ok\n", encoding="utf-8")
    assert xw._load_curated() == [("FOO INC", "999", "ok")]
