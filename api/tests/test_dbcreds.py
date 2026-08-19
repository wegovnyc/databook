"""Guards the single Postgres credential resolver (api/modules/dbcreds.py).

This code decides how every process in the stack authenticates to the database,
so its failure modes are all silent-then-total: pick the wrong source and either
nothing connects, or — worse — something connects with a stale credential that
still happens to work.

The precedence is deliberate. A Docker secret wins over an environment variable
because the env var is visible in `docker inspect`, in `docker compose config`
output, and in /proc/<pid>/environ; the caller's fallback (env.yaml) exists only
so local development keeps working without secret files.
"""

import importlib.util
import os
import pathlib

import pytest

# Loaded straight off disk on purpose: conftest.py replaces the whole `modules`
# package with a MagicMock so the test suite never touches a real database, and
# `from modules import dbcreds` would therefore hand back a mock.
_spec = importlib.util.spec_from_file_location(
    "dbcreds_under_test",
    pathlib.Path(__file__).resolve().parents[1] / "modules" / "dbcreds.py",
)
dbcreds = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dbcreds)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("POSTGRES_PASSWORD_FILE", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    for k in ("POSTGRES_USER", "POSTGRES_DB", "POSTGRES_HOST", "POSTGRES_PORT"):
        monkeypatch.delenv(k, raising=False)


def _secret(tmp_path, value, name="pw"):
    p = tmp_path / name
    p.write_text(value)
    return str(p)


def test_secret_file_beats_the_environment_variable(tmp_path, monkeypatch):
    """The whole point: a mounted secret must win over an env var."""
    monkeypatch.setenv("POSTGRES_PASSWORD_FILE", _secret(tmp_path, "from-secret"))
    monkeypatch.setenv("POSTGRES_PASSWORD", "from-env")
    assert dbcreds.password("from-yaml") == "from-secret"


def test_environment_variable_beats_the_fallback(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "from-env")
    assert dbcreds.password("from-yaml") == "from-env"


def test_fallback_is_used_when_nothing_is_set():
    assert dbcreds.password("from-yaml") == "from-yaml"
    assert dbcreds.password() == ""


def test_trailing_newline_in_the_secret_file_is_stripped(tmp_path, monkeypatch):
    """`echo pw > file` adds a newline; Postgres would reject it as part of the
    password, which looks exactly like a wrong credential."""
    monkeypatch.setenv("POSTGRES_PASSWORD_FILE", _secret(tmp_path, "abc123\n"))
    assert dbcreds.password() == "abc123"


def test_missing_secret_file_degrades_to_the_env_var(monkeypatch, tmp_path):
    """A half-applied compose change must not take the process down.

    If POSTGRES_PASSWORD_FILE points at a path that does not exist, resolution
    falls through rather than raising — failing closed on startup would turn a
    config mistake into an outage.
    """
    monkeypatch.setenv("POSTGRES_PASSWORD_FILE", str(tmp_path / "nope"))
    monkeypatch.setenv("POSTGRES_PASSWORD", "from-env")
    assert dbcreds.password() == "from-env"


def test_empty_secret_file_degrades_to_the_env_var(tmp_path, monkeypatch):
    """An empty or whitespace-only secret is treated as absent, not as ''."""
    monkeypatch.setenv("POSTGRES_PASSWORD_FILE", _secret(tmp_path, "   \n"))
    monkeypatch.setenv("POSTGRES_PASSWORD", "from-env")
    assert dbcreds.password() == "from-env"


def test_unreadable_secret_file_does_not_raise(tmp_path, monkeypatch):
    path = _secret(tmp_path, "nope")
    os.chmod(path, 0o000)
    monkeypatch.setenv("POSTGRES_PASSWORD_FILE", path)
    monkeypatch.setenv("POSTGRES_PASSWORD", "from-env")
    try:
        assert dbcreds.password() == "from-env"
    finally:
        os.chmod(path, 0o600)


def test_source_reports_provenance_and_never_the_value(tmp_path, monkeypatch):
    """Startup logging must be able to say WHERE the credential came from
    without printing it."""
    path = _secret(tmp_path, "topsecret")
    monkeypatch.setenv("POSTGRES_PASSWORD_FILE", path)
    src = dbcreds.source()
    assert "secret file" in src and path in src
    assert "topsecret" not in src

    monkeypatch.delenv("POSTGRES_PASSWORD_FILE")
    monkeypatch.setenv("POSTGRES_PASSWORD", "topsecret")
    assert dbcreds.source() == "environment variable"
    assert "topsecret" not in dbcreds.source()

    monkeypatch.delenv("POSTGRES_PASSWORD")
    assert "fallback" in dbcreds.source()


def test_settings_prefers_environment_then_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "databook_api")
    monkeypatch.setenv("POSTGRES_PASSWORD_FILE", _secret(tmp_path, "s3cret"))
    s = dbcreds.settings({"user": "yaml_user", "pwd": "yaml_pw",
                          "dbname": "yaml_db", "host": "yaml_host"})
    assert s["user"] == "databook_api"      # env wins
    assert s["password"] == "s3cret"        # secret file wins
    assert s["database"] == "yaml_db"       # falls back
    assert s["host"] == "yaml_host"
    assert s["port"] == 5432               # documented default


def test_settings_port_is_an_int(monkeypatch):
    monkeypatch.setenv("POSTGRES_PORT", "6543")
    assert dbcreds.settings()["port"] == 6543


def test_settings_survives_a_config_with_no_pwd_key(monkeypatch):
    """A defaults dict WITHOUT 'pwd' must resolve, not raise KeyError.

    This is the production shape since the credential moved to Docker secrets:
    #171 deleted `pwd:` from the box's api/env.yaml and made .env the single
    source of truth. Four call sites kept reading `Config.db['pwd']` by
    subscript and so raised `KeyError: 'pwd'` on prod from 2026-07-30 —
    /pipeline/briefing (cache never built), /pipeline/dataset-counts (swallowed
    it and served zeros), and both CSV importers, where it surfaced as the
    normalizer's "500 Internal Server Error" from /import-csv.
    """
    monkeypatch.setenv("POSTGRES_PASSWORD", "from-env")
    s = dbcreds.settings({"user": "databook_api", "dbname": "databook",
                          "host": "postgres"})     # note: no "pwd"
    assert s["password"] == "from-env"
    assert s["user"] == "databook_api"
    # Exactly the asyncpg.connect() keyword names, so callers can **-expand it.
    assert set(s) == {"user", "password", "database", "host", "port"}


def test_no_api_source_reads_a_credential_key_by_subscript():
    """Fail the build if any api source resolves a credential outside dbcreds.

    Direction matters. A test asserting dbcreds *itself* behaves correctly
    cannot see a call site that never calls dbcreds — which is exactly how the
    four `Config.db['pwd']` reads survived the #171 migration and broke prod.
    So this scans for the banned PATTERN instead of checking an approved list,
    the same shape as the orgfilter guard in test_adopt_nyc_orgs.py.

    Reading these keys with .get() and a fallback is fine, and dbcreds.py is
    itself exempt — it is the one place allowed to know the key names.
    """
    import re

    root = pathlib.Path(__file__).resolve().parents[1]
    # ['pwd'] / ["password"] / ['pwd'] off any object, e.g. Config.db['pwd'].
    banned = re.compile(r"""\[\s*['"](?:pwd|password)['"]\s*\]""")
    exempt = {root / "modules" / "dbcreds.py"}

    offenders = []
    for path in sorted(root.rglob("*.py")):
        if path in exempt or "/tests/" in str(path) or "/vendor/" in str(path):
            continue
        for n, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            # Strip comments and docstring prose first, or this guard fires on
            # its own explanation — the trap the orgfilter guard documents.
            code = line.split("#", 1)[0]
            if banned.search(code):
                offenders.append(f"{path.relative_to(root)}:{n}: {line.strip()}")

    assert not offenders, (
        "These read a Postgres credential by subscript instead of via "
        "modules/dbcreds.py, which raises KeyError once the key leaves "
        "env.yaml:\n  " + "\n  ".join(offenders))
