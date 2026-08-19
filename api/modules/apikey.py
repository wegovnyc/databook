"""Single place that checks the shared machine-to-machine API key.

The key must arrive in the **`X-API-Key` header**. The `api_key` QUERY PARAMETER
is deprecated and accepted only for backward compatibility.

Why the header
--------------
uvicorn logs the full request line, so a key sent as a query parameter is written
to the api's container log in plaintext on EVERY call — measured at 11
occurrences in 20 minutes during one normalizer ingest sweep, readable by anyone
with `docker logs`. A header is not logged. The value was rotated on 2026-08-03
once the leak was closed, because closing a leak does not undo it.

Why this is a module rather than a helper on each router
-------------------------------------------------------
Three call sites had three independent comparisons against the same secret
(`/import-csv`, `/upload`, and `org_admin.require_editor`) and they had already
drifted: two read the query parameter FIRST, and all three used `==`. A rotation
had to keep every one of them in step. Same argument as `dbcreds.py`.

It takes `configured` as an argument rather than importing Config, so it stays a
pure function — importable from `main` and from `routers/` with no circularity
and no config needed to test it.
"""

import logging
import secrets

logger = logging.getLogger(__name__)


def ok(header_key: str, query_key: str, configured: str) -> bool:
    """True when a supplied key matches `configured`. Header wins.

    Fails closed: an empty or missing `configured` never authenticates, so a
    config that has lost its key cannot turn into a state where an empty
    supplied key matches an empty configured one.

    The comparison is constant-time. `==` on a str short circuits at the first
    differing byte, and this is a secret.
    """
    if not configured:
        return False
    if header_key and secrets.compare_digest(header_key, configured):
        return True
    if query_key and secrets.compare_digest(query_key, configured):
        # WARNING, not a silent accept: this is how a straggling caller gets
        # found, so the compatibility shim does not become permanent by
        # accident. Logs neither the key nor the query string.
        logger.warning(
            "[auth] api_key arrived as a QUERY PARAMETER and is now in the "
            "access log in plaintext — send the X-API-Key header instead")
        return True
    return False
