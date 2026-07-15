"""Tests for the shared CheckbookNYC request helper (extractors.checkbook_post)."""
from unittest import mock

import requests


class _Resp:
    def __init__(self, status, content):
        self.status_code = status
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")


def test_checkbook_post_retries_bad_status_then_succeeds():
    from extractors import checkbook_post
    seq = [_Resp(503, b""), _Resp(200, b"<response><transaction/></response>")]
    calls = {"n": 0}

    def fake_post(url, data, timeout, headers):
        r = seq[calls["n"]]; calls["n"] += 1; return r

    with mock.patch("requests.post", side_effect=fake_post), mock.patch("time.sleep", lambda s: None):
        r = checkbook_post("x", base_delay=0, label="t")
    assert calls["n"] == 2 and r.status_code == 200


def test_checkbook_post_retries_non_xml_200_body():
    """A 200 with a non-XML body (throttle/slow-down page) must be retried, not
    passed through to ET.fromstring downstream where it would truncate the FY."""
    from extractors import checkbook_post
    seq = [_Resp(200, b"<html>slow down</html> not-xml <<"),
           _Resp(200, b"<response><transaction><a>1</a></transaction></response>")]
    calls = {"n": 0}

    def fake_post(url, data, timeout, headers):
        r = seq[calls["n"]]; calls["n"] += 1; return r

    with mock.patch("requests.post", side_effect=fake_post), mock.patch("time.sleep", lambda s: None):
        r = checkbook_post("x", base_delay=0, label="t")
    assert calls["n"] == 2
    assert b"transaction" in r.content


def test_checkbook_post_raises_after_exhausting_retries():
    from extractors import checkbook_post
    def always_bad(url, data, timeout, headers):
        return _Resp(200, b"garbage <<< not xml")
    with mock.patch("requests.post", side_effect=always_bad), mock.patch("time.sleep", lambda s: None):
        try:
            checkbook_post("x", max_attempts=3, base_delay=0, label="t")
            raised = False
        except Exception:
            raised = True
    assert raised, "should raise after exhausting retries on a persistently bad body"
