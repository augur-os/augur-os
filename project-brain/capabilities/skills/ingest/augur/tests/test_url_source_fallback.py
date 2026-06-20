"""Tests for the source-aware URL-capture fallback (GitHub raw README) that keeps
`/keep <url>` from saving JS-rendered stubs. See url_ingest.fetch_and_extract."""
from __future__ import annotations

import httpx
import pytest

from skills.ingest.scripts import url_ingest

_README = (
    "# Test Project\n\n"
    "Test Project turns inputs into outputs. " * 10
)
_STUB_HTML = (
    "<html><head><title>GitHub - owner/repo</title></head><body>"
    "<main>To see all available qualifiers, see our documentation. "
    "There was an error while loading. Please reload this page.</main></body></html>"
)
_GOOD_HTML = (
    "<html><head><title>Real Article</title></head><body><article>"
    + ("This is a genuinely long article body with plenty of real words. " * 8)
    + "</article></body></html>"
)
_SHORT_HTML = (
    "<html><head><title>Short</title></head><body><article>"
    "Just a few words here.</article></body></html>"
)


def _transport(routes: dict[str, tuple[int, str, str]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        u = str(request.url)
        for key, (status, body, ct) in routes.items():
            if key in u:
                return httpx.Response(status, content=body.encode("utf-8"),
                                      headers={"content-type": ct} if ct else {})
        return httpx.Response(404)
    return httpx.MockTransport(handler)


# --- _github_repo ---

@pytest.mark.parametrize(("url", "expected"), [
    ("https://github.com/microsoft/SkillOpt", ("microsoft", "SkillOpt")),
    ("https://github.com/opendataloader-project/opendataloader-pdf?tab=x", ("opendataloader-project", "opendataloader-pdf")),
    ("https://github.com/owner/repo.git", ("owner", "repo")),
    ("https://github.com/owner", None),
    ("https://github.com/features/copilot", None),
    ("https://example.com/owner/repo", None),
])
def test_github_repo(url, expected):
    assert url_ingest._github_repo(url) == expected


def test_has_stub_marker():
    assert url_ingest._has_stub_marker("There was an error while loading") is True
    assert url_ingest._has_stub_marker("a normal sentence of prose") is False


# --- _source_fallback ---

def test_source_fallback_github_main():
    t = _transport({"raw.githubusercontent.com/o/r/main/README.md": (200, _README, "text/plain")})
    res = url_ingest._source_fallback("https://github.com/o/r", _transport=t)
    assert res is not None
    assert res["title"] == "Test Project"
    assert "Test Project turns inputs" in res["body"]


def test_source_fallback_falls_through_to_master():
    t = _transport({
        "main/README.md": (404, "", ""),
        "master/README.md": (200, _README, "text/plain"),
    })
    res = url_ingest._source_fallback("https://github.com/o/r", _transport=t)
    assert res is not None and "Test Project" in res["body"]


def test_source_fallback_non_github_is_none():
    assert url_ingest._source_fallback("https://example.com/a/b") is None


# --- fetch_and_extract integration ---

def test_github_stub_falls_back_to_readme():
    t = _transport({
        "github.com/o/r": (200, _STUB_HTML, "text/html"),
        "raw.githubusercontent.com/o/r/main/README.md": (200, _README, "text/plain"),
    })
    res = url_ingest.fetch_and_extract("https://github.com/o/r", _transport=t)
    assert res["title"] == "Test Project"
    assert "error while loading" not in res["body"].lower()


def test_github_504_falls_back_to_readme():
    t = _transport({
        "github.com/o/r": (504, "gateway timeout", "text/html"),
        "raw.githubusercontent.com/o/r/main/README.md": (200, _README, "text/plain"),
    })
    res = url_ingest.fetch_and_extract("https://github.com/o/r", _transport=t)
    assert "Test Project turns inputs" in res["body"]


def test_non_github_good_content_returned():
    t = _transport({"example.com/article": (200, _GOOD_HTML, "text/html")})
    res = url_ingest.fetch_and_extract("https://example.com/article", _transport=t)
    assert "genuinely long article" in res["body"]


def test_non_github_short_page_not_regressed():
    # Short, non-stub, non-github page must still be returned (no false fallback).
    t = _transport({"example.com/short": (200, _SHORT_HTML, "text/html")})
    res = url_ingest.fetch_and_extract("https://example.com/short", _transport=t)
    assert "few words" in res["body"].lower()
