"""Every container this repo runs must have a bounded log.

Docker's default `json-file` driver has NO rotation, so a container log grows
until the container is RECREATED — and `docker compose restart` does not do
that. Measured on prod 2026-08-14: `databook-nginx` alone held **2.0 GB**,
essentially the whole of the box's container-log footprint, and the only reason
it had never mattered is that deploys which rebuild an image happen to reset it.

The single-service fix would rot immediately: the failure mode here is not the
services that exist today but the NEXT one added, which would default straight
back to unbounded. So this walks the compose file and requires a bound on every
service — the direction that catches the code nobody has written yet.

⚠ Asserts against the file, not against the box. The box's compose has drifted
from git before (ops scripts editing it in place), which is exactly why the
declaration is version-controlled and pinned here.
"""

import os

import pytest

yaml = pytest.importorskip("yaml")

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
COMPOSE = os.path.join(ROOT, "docker-compose.yml")


def _services():
    with open(COMPOSE, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    return doc.get("services") or {}


def test_every_service_bounds_its_log():
    services = _services()
    # ⚠ Assert the scan LOOKED. An empty or unparsed services map would make
    # every assertion below vacuously true -- the guard-that-scanned-zero-files
    # pattern this repo has already paid for twice.
    assert len(services) >= 6, (
        f"only found {len(services)} services in docker-compose.yml -- the "
        "file did not parse as expected and this guard is checking nothing"
    )

    missing, unbounded = [], []
    for name, svc in services.items():
        log = (svc or {}).get("logging")
        if not log:
            missing.append(name)
            continue
        opts = log.get("options") or {}
        # `max-file` alone does nothing without `max-size`: the driver only
        # rolls a file once it hits a size, so a max-file with no max-size is
        # still one unbounded file.
        if not opts.get("max-size"):
            unbounded.append(f"{name} (driver={log.get('driver')!r}, options={opts})")

    assert not missing, (
        "these services declare no `logging:` block, so they use the default "
        "json-file driver with NO rotation and their logs grow without bound: "
        + ", ".join(sorted(missing))
    )
    assert not unbounded, (
        "these services declare `logging:` but no max-size, which does not bound "
        "anything: " + ", ".join(sorted(unbounded))
    )


def test_the_bounds_are_actually_finite():
    """A `max-size` of 0/unlimited would satisfy the check above while bounding
    nothing, so the values themselves are validated."""
    import re

    unit = {"b": 1, "k": 1024, "m": 1024 ** 2, "g": 1024 ** 3}
    for name, svc in _services().items():
        opts = ((svc or {}).get("logging") or {}).get("options") or {}
        size = str(opts.get("max-size", ""))
        m = re.fullmatch(r"(\d+)([bkmg])", size.strip().lower())
        assert m, f"{name}: max-size {size!r} is not a parseable docker size"
        n_bytes = int(m.group(1)) * unit[m.group(2)]
        assert n_bytes > 0, f"{name}: max-size {size!r} bounds nothing"
        # A ceiling far larger than the disk would be a bound in name only.
        assert n_bytes <= 1024 ** 3, (
            f"{name}: max-size {size!r} is over 1 GiB -- that is not a bound, "
            "it is the status quo with extra steps"
        )

        files = str(opts.get("max-file", "1"))
        assert files.isdigit() and int(files) >= 1, (
            f"{name}: max-file {files!r} must be a positive integer"
        )
        # The real ceiling is max-size * max-file; keep the total sane so a
        # future edit cannot quietly restore multi-gigabyte logs.
        total = n_bytes * int(files)
        assert total <= 2 * 1024 ** 3, (
            f"{name}: max-size x max-file = {total / 1024 ** 3:.1f} GiB, which is "
            "at or above the 2.0 GB file that prompted this guard"
        )
