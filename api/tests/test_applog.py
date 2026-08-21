"""Guards for the api's logging configuration (`modules/applog.py`).

The defect these exist to prevent is not "logging is broken" — it is
**misreading the log**. Before this configuration existed, `logger.info` was
dropped at the root level check while `logger.warning` printed through
`logging.lastResort` as a bare, level-less line. The result was a container log
in which `grep -c WARNING` returned 0 while warnings were in fact being
emitted, and a handoff that concluded every degradation warning was silently
swallowed. It was not; it was unlabelled.

So the properties pinned here are the ones whose absence made the log
unreadable, plus the seam that makes the whole thing take effect at all.

⚠ `applog` is loaded BY PATH. `conftest.py` does
`sys.modules.setdefault("modules", MagicMock())`, so a plain
`from modules import applog` yields a mock whose every attribute satisfies
almost any assertion — the trap that let an earlier round of tests "pass"
against nothing.
"""

import importlib.util
import logging
import os
import re

import pytest

_API_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def _load_applog():
    path = os.path.join(_API_DIR, "modules", "applog.py")
    spec = importlib.util.spec_from_file_location("_applog_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


applog = _load_applog()


@pytest.fixture
def clean_logging():
    """Snapshot and restore global logging state around a test."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    saved_app_levels = {
        name: logging.getLogger(name).level for name in applog.APP_LOGGER_ROOTS
    }
    yield
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)
    for name, level in saved_app_levels.items():
        logging.getLogger(name).setLevel(level)


# ---------------------------------------------------------------------------
# What the configuration must actually do
# ---------------------------------------------------------------------------


def test_our_loggers_are_enabled_for_info_after_configure(clean_logging):
    """The whole point: `logger.info` in routers/ and modules/ must survive.

    This is the property that made `digital spend map ready` — a readiness
    signal this repo documented as an instruction — impossible to observe.
    """
    applog.configure()
    for name in ("routers.oce", "routers.licenses", "modules.orgfilter"):
        assert logging.getLogger(name).isEnabledFor(logging.INFO), (
            f"{name} must be enabled for INFO, or its readiness and "
            f"degradation lines are dropped before any handler sees them"
        )


def test_root_stays_at_warning_so_third_party_libraries_stay_quiet(clean_logging):
    """Raising root to INFO would buy the noise of every dependency.

    Only the packages we own are raised; root keeps the level it has today.
    """
    applog.configure()
    assert logging.getLogger().level == logging.WARNING


def test_a_record_carries_its_level_and_logger_name(clean_logging):
    """`grep WARNING` must find a warning. This is the actual bug.

    `logging.lastResort` emits the bare message, so a warning was
    indistinguishable from a `print()` and a log full of them reported zero
    warnings to anyone grepping by level.
    """
    import io

    buf = io.StringIO()
    applog.configure(stream=buf)
    logging.getLogger("routers.oce").warning("[oce] canary degradation")

    out = buf.getvalue()
    assert "WARNING" in out, "a warning must name its level in the log line"
    assert "routers.oce" in out, "a warning must name the logger it came from"
    assert "[oce] canary degradation" in out


def test_configure_is_idempotent(clean_logging):
    """Calling twice must not install a second handler and double every line."""
    applog.configure()
    applog.configure()
    applog.configure()
    ours = [
        h for h in logging.getLogger().handlers
        if getattr(h, "name", None) == "databook-app"
    ]
    assert len(ours) == 1, f"expected exactly one handler, found {len(ours)}"


def test_a_malformed_log_level_degrades_instead_of_raising(clean_logging):
    """A typo in LOG_LEVEL must not be able to stop the api from starting."""
    saved = os.environ.get("LOG_LEVEL")
    try:
        os.environ["LOG_LEVEL"] = "LOUDER"
        assert applog.configure() == logging.INFO
        os.environ["LOG_LEVEL"] = "warning"
        assert applog.configure() == logging.WARNING
    finally:
        if saved is None:
            os.environ.pop("LOG_LEVEL", None)
        else:
            os.environ["LOG_LEVEL"] = saved


# ---------------------------------------------------------------------------
# The seams — configuration that is never invoked configures nothing
# ---------------------------------------------------------------------------


def _source_without_comments(path):
    """Strip comment lines before scanning source.

    A guard that reads its own explanation as code fires on the comment that
    describes it — the mistake already recorded against the org-type guard.
    """
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            out.append(line)
    return out


def test_main_configures_logging_before_it_imports_any_router():
    """Order is the whole seam.

    A router imported before the handler exists would still work — levels are
    resolved at emit time — but anything logging at import time would vanish,
    and the ordering is the only thing making that impossible. Pinning it costs
    nothing and removes a class of "why is this line missing" entirely.
    """
    lines = _source_without_comments(os.path.join(_API_DIR, "main.py"))

    configure_at = next(
        (i for i, l in enumerate(lines) if "applog.configure()" in l), None
    )
    assert configure_at is not None, "main.py must call applog.configure()"

    first_router = next(
        (i for i, l in enumerate(lines) if re.match(r"\s*from routers\.", l)), None
    )
    assert first_router is not None, "expected main.py to import routers"

    assert configure_at < first_router, (
        "applog.configure() must run BEFORE the routers are imported "
        f"(configure at line {configure_at}, first router import at "
        f"{first_router})"
    )


def test_every_logger_in_the_api_lives_under_a_configured_root():
    """Catches the code nobody has written yet.

    `configure()` raises named roots, so a future module logging under a root
    that is not listed would be silently dropped at INFO — the exact failure
    this whole change exists to remove, reintroduced by omission.
    """
    exempt = {
        # Runs in its own container with its own basicConfig; never imported
        # by the api process.
        os.path.join("api", "mcp_server.py"),
    }

    scanned = 0
    offenders = []
    for dirpath, dirnames, filenames in os.walk(_API_DIR):
        dirnames[:] = [
            d for d in dirnames
            if d not in {"tests", "__pycache__", "seed", "venv", ".venv"}
        ]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            full = os.path.join(dirpath, fn)
            scanned += 1
            rel = os.path.relpath(full, os.path.dirname(_API_DIR))
            if rel in exempt:
                continue
            with open(full, "r", encoding="utf-8", errors="replace") as fh:
                src = fh.read()
            if "getLogger(__name__)" not in src:
                continue
            # The logger's name is its dotted module path relative to api/.
            parts = os.path.relpath(full, _API_DIR).split(os.sep)
            root = parts[0] if len(parts) > 1 else parts[0][:-3]
            if root not in applog.APP_LOGGER_ROOTS:
                offenders.append(rel)

    # A guard that scans nothing passes unconditionally. Assert it looked.
    assert scanned > 40, f"expected to scan the api tree, only saw {scanned} files"
    assert not offenders, (
        "these modules log under a root applog.configure() does not raise, so "
        f"their INFO lines would be dropped: {offenders}. Add the root to "
        "APP_LOGGER_ROOTS."
    )


def test_uvicorns_own_loggers_do_not_propagate_to_root():
    """A root handler must not duplicate the access log.

    `uvicorn` and `uvicorn.access` ship `propagate: false`, which is the only
    reason adding a root handler does not print every access line twice. If an
    upgrade ever flips that, this fails here rather than doubling the log
    volume on prod.
    """
    from uvicorn.config import LOGGING_CONFIG

    for name in ("uvicorn", "uvicorn.access"):
        assert LOGGING_CONFIG["loggers"][name].get("propagate") is False, (
            f"uvicorn's {name!r} logger no longer sets propagate=False; a root "
            f"handler would now duplicate every line it emits"
        )

    assert "root" not in LOGGING_CONFIG, (
        "uvicorn now configures the root logger itself; applog's assumptions "
        "about root level and handlers need re-measuring"
    )
