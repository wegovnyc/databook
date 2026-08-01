"""Single place that resolves the Postgres credential.

Resolution order, highest first:

  1. POSTGRES_PASSWORD_FILE  — a Docker secret, mounted at /run/secrets/<name>
  2. POSTGRES_PASSWORD       — a plain environment variable
  3. the caller's fallback   — env.yaml, for local development

Why the file wins
-----------------
An environment variable is readable by anyone who can run `docker inspect` on
the container, appears in `docker compose config` output, and is visible in
`/proc/<pid>/environ` to every process in the container. A Docker secret is a
file mounted at /run/secrets, so it stays out of all three.

This exists as one function rather than being inlined because the credential was
previously resolved independently in fourteen places, each with its own
fallback, and a rotation had to keep every one of them in step. See the
`postgres-roles-credentials` notes for how that went wrong: api/env.yaml ended
up with three copies and the rotation script updated only one of them.

Every caller should use these helpers rather than reading os.environ directly.
"""

import os

_FILE_ENV = "POSTGRES_PASSWORD_FILE"
_PLAIN_ENV = "POSTGRES_PASSWORD"


def _read_secret_file(path: str) -> str:
    """Contents of a Docker secret, or '' if it cannot be read.

    Never raises: a missing or unreadable secret file must fall through to the
    environment variable rather than take the process down, so that a
    half-applied compose change degrades instead of failing closed on startup.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def password(default: str = "") -> str:
    """The Postgres password: secret file, then env var, then `default`."""
    path = os.environ.get(_FILE_ENV)
    if path:
        value = _read_secret_file(path)
        if value:
            return value
    return os.environ.get(_PLAIN_ENV) or default


def source() -> str:
    """Where the password came from — for startup logging. Never the value."""
    path = os.environ.get(_FILE_ENV)
    if path and _read_secret_file(path):
        return f"secret file ({path})"
    if os.environ.get(_PLAIN_ENV):
        return "environment variable"
    return "fallback (env.yaml)"


def settings(defaults: dict = None) -> dict:
    """user / password / database / host / port, environment first.

    `defaults` supplies local-dev fallbacks (typically from env.yaml) under the
    keys user / pwd / dbname / host.
    """
    d = defaults or {}
    return {
        "user": os.environ.get("POSTGRES_USER") or d.get("user"),
        "password": password(d.get("pwd") or ""),
        "database": os.environ.get("POSTGRES_DB") or d.get("dbname"),
        "host": os.environ.get("POSTGRES_HOST") or d.get("host"),
        "port": int(os.environ.get("POSTGRES_PORT", "5432")),
    }
