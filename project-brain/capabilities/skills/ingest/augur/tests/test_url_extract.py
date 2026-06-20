from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from skills.ingest.scripts.url_ingest import ExtractionError, fetch_and_extract

FIXTURES = Path(__file__).parent / "fixtures"


def _transport_for(html_path: Path, content_type: str = "text/html; charset=utf-8") -> httpx.MockTransport:
    body = html_path.read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"content-type": content_type})

    return httpx.MockTransport(handler)


def test_extract_simple_article() -> None:
    transport = _transport_for(FIXTURES / "article_simple.html")
    result = fetch_and_extract("https://example.com/a", _transport=transport)

    assert result["title"] == "Why Trees Matter"
    assert "lungs of the planet" in result["body"]


def test_extract_strips_nav_and_footer() -> None:
    transport = _transport_for(FIXTURES / "article_messy.html")
    result = fetch_and_extract("https://example.com/b", _transport=transport)

    assert "BUY OUR PRODUCT" not in result["body"]
    assert "Cookie banner" not in result["body"]
    assert "Site Header" not in result["body"]
    assert "Divination by tea" in result["body"]


def test_extract_empty_body_raises() -> None:
    transport = _transport_for(FIXTURES / "article_empty.html")

    with pytest.raises(ExtractionError, match="empty"):
        fetch_and_extract("https://example.com/c", _transport=transport)


def test_extract_rejects_non_html() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"%PDF-1.4", headers={"content-type": "application/pdf"})

    transport = httpx.MockTransport(handler)
    with pytest.raises(ExtractionError, match="content-type"):
        fetch_and_extract("https://example.com/d.pdf", _transport=transport)


def test_extract_propagates_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with pytest.raises(ExtractionError, match="404"):
        fetch_and_extract("https://example.com/missing", _transport=transport)
