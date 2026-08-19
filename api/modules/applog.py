"""One owner for the api process's logging configuration.

⚠⚠ READ THIS BEFORE "FIXING THE SWALLOWED WARNINGS" AGAIN — the obvious
reading of the container log is wrong, and I shipped a handoff that made it.

uvicorn configures logging for its OWN three loggers (`uvicorn`,
`uvicorn.error`, `uvicorn.access`) and **never touches the root logger**. Its
dictConfig has no `root` key, so a module logger created the normal way
(`logging.getLogger(__name__)` → `routers.oce`, `modules.orgfilter`) inherits
root's defaults: level WARNING, and an empty handler list. Measured in the prod
api container 2026-08-13 — `root level: 30, root handlers: []`.

That has two consequences and only ONE of them is what it looks like:

* `logger.info(...)` is dropped at the **level check**, before any handler is
  consulted. It never reaches the log, and it never reaches Sentry either — the
  LoggingIntegration's breadcrumb handler only sees records that get as far as
  `Logger.callHandlers`. This is why `[oce] digital spend map ready` could not
  be observed, and why the repo carried a documented instruction ("wait for it
  in the api log") that nobody could follow.

* `logger.warning(...)` and `logger.error(...)` are **NOT** dropped. With no
  handler anywhere on the chain, `logging.lastResort` (a stderr handler at
  WARNING) prints them, and docker captures stderr. **Proven in the live
  process**, not reasoned about: a real `[oce] org vendor-activity lookup
  failed for 99999999999999: ... (value out of int32 range)` was made to fire
  against prod and appeared in `docker logs` immediately.

The second point is precisely why the log read as though every warning were
swallowed: `lastResort` emits the **bare message** — no timestamp, no level
name, no logger name — so a warning is visually indistinguishable from a
`print()`, and `grep -c WARNING` over a log full of them returns **0**.
**An absent level name is not an absent warning**, and a log that never says
"WARNING" is indistinguishable from a service that has never degraded. That is
the same family as the permanently-red monitor and the guard that scanned zero
files.

What this module does, therefore, is small and deliberate:

* installs ONE root handler with a format carrying **timestamp, level name and
  logger name**, so warnings are greppable by level and cannot be misread as
  prints again;
* raises the level of the loggers this codebase owns (`routers.*`,
  `modules.*`) to INFO, so readiness signals and degradation notes are
  observable;
* leaves the **root level at WARNING**, so third-party libraries stay as quiet
  as they are today. Turning root up to INFO would import a noise problem in
  exchange for nothing.

⚠ Volume was measured before enabling INFO, not assumed: across 4h of real prod
traffic there were **11,333 uvicorn access lines and 0 requests** to the only
endpoint that logs INFO per request (`/oce/dashboard/stats`). Every other
`logger.info` site in `routers/` and `modules/` is either startup or a
degradation path. Enabling INFO is therefore a rounding error against the
access log — and the degradation lines are the entire point.

⚠ Adding a root handler does NOT duplicate uvicorn's access log: `uvicorn` and
`uvicorn.access` are configured `propagate: false`, so their records stop
before reaching root. Checked against the installed uvicorn (0.39.0), and
pinned by a guard test so a future upgrade that flips it cannot silently double
every line.

⚠ Sentry, for the record (also measured, sentry_sdk 2.66.1): LoggingIntegration
is auto-enabled, with an **EventHandler at ERROR** and a BreadcrumbHandler at
INFO. So `logger.error` raises a Sentry *event*, while `logger.warning` is only
a *breadcrumb* — it is attached to a later error event in the same scope, and
if no error follows it is never sent anywhere. Whether the degradation warnings
in `oce.py` deserve to be events is a real question, and a deliberate decision
for the owner rather than a side effect of this change.
"""

import logging
import os
import sys

# The logger-name roots this codebase owns. Everything in `api/` that calls
# `logging.getLogger(__name__)` lives under `api/routers/` or `api/modules/`,
# so these two cover it — and a guard test walks the tree and fails if a new
# `getLogger` site ever appears under a root that is not listed here, which is
# the direction that catches the code nobody has written yet.
#
# ⚠ `mcp_server.py` is deliberately absent: it runs in its own container with
# its own `logging.basicConfig`, and is never imported by the api process.
# ⚠ `data_scheduler` is a TOP-LEVEL module, not under routers/ or modules/, so it
# needs naming explicitly — added 2026-08-18 when the scheduler loop gained a
# logger so that a cycle dying could raise a Sentry event instead of being a bare
# `print` nobody was alerted by. The one-logger-per-configured-root guard in
# test_applog.py is what caught the omission.
APP_LOGGER_ROOTS = ("routers", "modules", "data_scheduler")

# Carries the level name and the logger name on purpose — see the module
# docstring. A format without `%(levelname)s` is how the previous state became
# unreadable.
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

# Marks our handler so `configure()` is idempotent. It can be called more than
# once (imports, tests, a reload), and installing a second handler would print
# every line twice — the failure this attribute exists to prevent.
_HANDLER_NAME = "databook-app"

# Third-party noise stays where it is; only what we own is raised.
ROOT_LEVEL = logging.WARNING


def _level_from_env(default=logging.INFO):
    """Resolve LOG_LEVEL, degrading to the default rather than raising.

    A malformed level must never be able to stop the api from starting; the
    cost of a typo here should be the level you asked for, not an outage.
    """
    raw = (os.getenv("LOG_LEVEL") or "").strip().upper()
    if not raw:
        return default
    resolved = logging.getLevelName(raw)
    return resolved if isinstance(resolved, int) else default


def configure(stream=None):
    """Install the root handler and raise our own loggers to INFO.

    Idempotent. Safe to call before or after the routers are imported: a
    logger's level and handlers are resolved at emit time, not at creation, so
    `logging.getLogger(__name__)` at module import needs no coordination with
    this call.
    """
    root = logging.getLogger()

    existing = [h for h in root.handlers if getattr(h, "name", None) == _HANDLER_NAME]
    if not existing:
        handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
        handler.name = _HANDLER_NAME
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        root.addHandler(handler)

    # Root stays at WARNING so third-party libraries are no louder than they
    # are today; only the packages we own are raised.
    root.setLevel(ROOT_LEVEL)

    level = _level_from_env()
    for name in APP_LOGGER_ROOTS:
        logging.getLogger(name).setLevel(level)

    return level
