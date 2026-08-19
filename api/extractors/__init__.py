from __future__ import annotations

"""
Shared utilities for Databook extractors.

Provides dynamic fiscal year calculation, S3 upload, and metadata tracking.
All extractors import from this module instead of duplicating these patterns.
"""

import datetime
import json
import os

import boto3
from modules.errfmt import exc_str


# =============================================================================
# S3 Configuration (reads from env, never hardcoded)
# =============================================================================

S3_BUCKET = os.environ.get("EXTRACTOR_S3_BUCKET", "databook2")
S3_PREFIX = os.environ.get("EXTRACTOR_S3_PREFIX", "pre-processed")


def get_current_fiscal_year() -> int:
    """
    Calculate the current NYC fiscal year dynamically.

    NYC fiscal year runs July 1 → June 30.
    If today is July 2026 or later, FY = 2027.
    If today is June 2026 or earlier, FY = 2026.
    """
    now = datetime.date.today()
    return now.year + 1 if now.month >= 7 else now.year


def upload_to_s3(file_path: str, s3_key: str) -> str | None:
    """
    Upload a local file to the databook2 S3 bucket.

    AWS credentials must be set via environment variables or IAM role,
    never hardcoded.

    Returns the public S3 URL on success, None on failure.
    """
    full_key = f"{S3_PREFIX}/{s3_key}" if S3_PREFIX else s3_key
    print(f"[extractor] Uploading {file_path} → s3://{S3_BUCKET}/{full_key}")

    try:
        s3 = boto3.client('s3')
        s3.upload_file(file_path, S3_BUCKET, full_key)
        url = f"https://{S3_BUCKET}.s3.amazonaws.com/{full_key}"
        print(f"[extractor] Upload OK: {url}")
        return url
    except Exception as e:
        print(f"[extractor] S3 upload failed: {exc_str(e)}")
        return None


def clean_text(text: str | None) -> str:
    """Sanitize a text value from XML/HTML sources."""
    if text:
        return text.replace('\n', ' ').replace('\r', '').strip()
    return ""


# =============================================================================
# CheckbookNYC API POST with retry + backoff
# =============================================================================

_CHECKBOOK_API_URL = "https://www.checkbooknyc.com/api"
# A stable, non-default User-Agent identifying the mirror.
_CHECKBOOK_UA = "DatabookBot/1.0 (+https://databook.nyc; NYC open-data mirror)"
# CheckbookNYC intermittently 403s a client under sustained/bursty load — a short
# WAF cooldown (~1-2 min) that then recovers. Retry those (+ 429/5xx) rather than
# dropping the page, which would silently TRUNCATE a fiscal year.
_CHECKBOOK_RETRY_STATUS = {403, 429, 500, 502, 503, 504}


def checkbook_post(payload: str, timeout: int = 90, max_attempts: int = 6,
                   base_delay: int = 15, label: str = "checkbook"):
    """POST to the CheckbookNYC XML API, retrying the SAME request with escalating
    backoff on transient throttling (403/429/5xx). Retries the identical offset so
    a mid-fiscal-year cooldown never truncates data. Raises after max_attempts.

    Shared by every checkbook_* extractor, so it protects the weekly refresh
    (scripts/oce-refresh.sh) and all ingests. Backoff 15→30→60→120→120s
    (~6 min total) comfortably outlasts an observed cooldown."""
    import time
    import requests
    import xml.etree.ElementTree as ET

    delay = base_delay
    last_exc = None
    resp = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(_CHECKBOOK_API_URL, data=payload, timeout=timeout,
                                 headers={"User-Agent": _CHECKBOOK_UA})
            if resp.status_code in _CHECKBOOK_RETRY_STATUS and attempt < max_attempts:
                print(f"[{label}] HTTP {resp.status_code} (attempt {attempt}/{max_attempts}) "
                      f"— backoff {delay}s")
                time.sleep(delay)
                delay = min(delay * 2, 120)
                continue
            resp.raise_for_status()
            # Throttling also shows up as a 200 with a NON-XML body (an error/slow-down
            # page). Downstream ET.fromstring would then raise and the extractor would
            # break its page loop — SILENTLY TRUNCATING the fiscal year. So validate the
            # body parses and retry a bad one as transient (same as a 403/5xx).
            try:
                ET.fromstring(resp.content)
            except ET.ParseError:
                if attempt < max_attempts:
                    print(f"[{label}] HTTP 200 but non-XML body ({len(resp.content)} bytes) "
                          f"(attempt {attempt}/{max_attempts}) — backoff {delay}s")
                    time.sleep(delay)
                    delay = min(delay * 2, 120)
                    continue
                # exhausted — surface it; the caller treats ParseError as a hard stop
                raise
            return resp
        except requests.exceptions.RequestException as e:
            last_exc = e
            if attempt < max_attempts:
                print(f"[{label}] {type(e).__name__} (attempt {attempt}/{max_attempts}) "
                      f"— backoff {delay}s")
                time.sleep(delay)
                delay = min(delay * 2, 120)
                continue
            raise
    if last_exc:
        raise last_exc
    return resp
