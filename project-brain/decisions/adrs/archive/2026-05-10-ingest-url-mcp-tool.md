# Ingest URL MCP Tool — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a single MCP tool `ingest-url(url, tags=None, note=None) -> json` on the existing `ingest` skill that captures a URL into the source-card pipeline so the wiki compounder picks it up. Synchronous, idempotent, no scanner changes, no vault-skill creation.

**Architecture (one slice):** Five pure helpers (canonicalize, slugify, content-hash, fetch-and-extract, dedup-scan) feed one persistence call (`write_url_source_card`) wrapped by one MCP registration (`register_url_tools`). All five helpers are independently unit-testable. The MCP tool composes them and is integration-tested against a fixture HTML page (no live network).

**Tech Stack:** Python 3.11, pytest, `httpx>=0.25.0` (already in `pyproject.toml`), `trafilatura` (new dep), `beautifulsoup4` (new dep), `mcp.server.fastmcp.FastMCP`, Augur `ingest` skill (`shared-vault/skills/ingest/`), Augur frontmatter utilities (`src/lib/frontmatter_utils.py`).

**Spec:** [`docs/superpowers/specs/2026-05-10-ingest-url-mcp-tool-design.md`](../specs/2026-05-10-ingest-url-mcp-tool-design.md)

**ADR:** ADR-724 (Accepted) — supersedes Cancelled ADR-624.

---

## File Structure

### Created files

| Path | Responsibility |
|---|---|
| `shared-vault/skills/ingest/scripts/url_ingest.py` | Pure helpers: `canonicalize_url`, `slugify_url`, `compute_content_hash`, `fetch_and_extract`, `find_existing_url_card`, `write_url_source_card` |
| `shared-vault/skills/ingest/scripts/mcp/url_tools.py` | `register_url_tools(mcp, interceptor, metrics)` registering the `ingest-url` MCP tool |
| `shared-vault/skills/ingest/augur/tests/test_url_canonicalize.py` | Unit tests for `canonicalize_url` + `slugify_url` |
| `shared-vault/skills/ingest/augur/tests/test_url_content_hash.py` | Unit tests for `compute_content_hash` (stability + dedup contract) |
| `shared-vault/skills/ingest/augur/tests/test_url_extract.py` | Unit tests for `fetch_and_extract` using fixture HTML on disk (no network) |
| `shared-vault/skills/ingest/augur/tests/test_url_source_card.py` | Unit tests for `write_url_source_card` (frontmatter shape, path layout) |
| `shared-vault/skills/ingest/augur/tests/test_url_ingest_mcp.py` | Integration test for the registered `ingest-url` MCP tool, including dedup re-run |
| `shared-vault/skills/ingest/augur/tests/fixtures/article_simple.html` | Fixture: well-formed article with `<title>` and `<article>` |
| `shared-vault/skills/ingest/augur/tests/fixtures/article_messy.html` | Fixture: dirty HTML (nav, footer, ads) — exercises trafilatura's prose extraction |
| `shared-vault/skills/ingest/augur/tests/fixtures/article_empty.html` | Fixture: page with no extractable body — exercises the error path |

### Modified files

| Path | Change |
|---|---|
| `shared-vault/skills/ingest/scripts/mcp/__init__.py` | Import + call `register_url_tools` next to the existing two registrars |
| `pyproject.toml` | Add `trafilatura>=1.6` and `beautifulsoup4>=4.12` to project dependencies |

### Untouched (intentional)

- `shared-vault/skills/ingest/scripts/source_cards.py` — the existing `write_source_card` is for inbox-routed files with a `RouteDecision`; URLs need a simpler frontmatter shape. We reuse the `_unique_card_path` and `_compute_content_hash` *patterns* but write our own `write_url_source_card` to avoid polluting the inbox API.
- `shared-vault/skills/ingest/scripts/wiki_scanner.py` — already walks `<vault>/sources/` recursively under `source_surface="vault"`. New cards flow through unchanged.
- `~/Projects/Au-vault/skills/vault/` — the existing vault skill provides browse/edit/search. Not touched.

---

# Phase 1 — Pure helpers

Three pure functions, each with a single test file. All three are deterministic, network-free, and side-effect-free.

## Task 1: `canonicalize_url` + `slugify_url`

**Files:**
- Create: `shared-vault/skills/ingest/scripts/url_ingest.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_url_canonicalize.py`

- [ ] **Step 1: Write the failing test**

Create `shared-vault/skills/ingest/augur/tests/test_url_canonicalize.py`:

```python
from __future__ import annotations

import pytest

from skills.ingest.scripts.url_ingest import canonicalize_url, slugify_url


@pytest.mark.parametrize(
    "raw,expected",
    [
        # tracking params stripped
        ("https://example.com/a?utm_source=x&id=1", "https://example.com/a?id=1"),
        ("https://example.com/a?fbclid=abc&id=1", "https://example.com/a?id=1"),
        ("https://example.com/a?gclid=abc", "https://example.com/a"),
        ("https://example.com/a?mc_cid=x&mc_eid=y", "https://example.com/a"),
        ("https://example.com/a?ref=twitter&ref_src=feed", "https://example.com/a"),
        ("https://example.com/a?igshid=xx", "https://example.com/a"),
        # fragment stripped
        ("https://example.com/a#section", "https://example.com/a"),
        # trailing slash stripped (but not on root)
        ("https://example.com/a/", "https://example.com/a"),
        ("https://example.com/", "https://example.com/"),
        # host lowercased
        ("HTTPS://EXAMPLE.COM/A", "https://example.com/A"),
        # query keys sorted
        ("https://example.com/a?b=2&a=1", "https://example.com/a?a=1&b=2"),
    ],
)
def test_canonicalize_url(raw: str, expected: str) -> None:
    assert canonicalize_url(raw) == expected


def test_canonicalize_url_idempotent() -> None:
    once = canonicalize_url("https://EXAMPLE.com/a/?utm_source=x&id=1#hash")
    twice = canonicalize_url(once)
    assert once == twice == "https://example.com/a?id=1"


def test_slugify_url_basic() -> None:
    assert slugify_url("https://example.com/articles/why-trees-matter") == "example-com-articles-why-trees-matter"


def test_slugify_url_root() -> None:
    assert slugify_url("https://example.com/") == "example-com"


def test_slugify_url_truncates_long_paths() -> None:
    long = "https://example.com/" + ("a" * 200)
    slug = slugify_url(long)
    assert len(slug) <= 80
    assert slug.startswith("example-com-")
```

- [ ] **Step 2: Run the test, confirm it fails** (module doesn't exist yet)
- [ ] **Step 3: Implement `canonicalize_url` and `slugify_url`** in `shared-vault/skills/ingest/scripts/url_ingest.py`:

```python
"""URL ingest helpers — pure functions for the ingest-url MCP tool."""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "ref", "ref_src",
})

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def canonicalize_url(url: str) -> str:
    """Return a deterministic canonical form for idempotency.

    Strips tracking params, fragments, host case, and trailing slashes (except root).
    Sorts remaining query keys.
    """
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query_pairs = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    query_pairs.sort()
    query = urlencode(query_pairs)
    return urlunsplit((scheme, netloc, path, query, ""))


def slugify_url(url: str, *, max_len: int = 80) -> str:
    """Return a filesystem-safe slug for the URL's host + path."""
    parts = urlsplit(canonicalize_url(url))
    raw = f"{parts.netloc}{parts.path}".lower()
    slug = _SLUG_RE.sub("-", raw).strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or "untitled"
```

- [ ] **Step 4: Run the test, confirm it passes**
- [ ] **Step 5: Commit** `feat(ingest): canonicalize and slugify URL helpers`

## Task 2: `compute_content_hash`

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/url_ingest.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_url_content_hash.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from skills.ingest.scripts.url_ingest import compute_content_hash


def test_hash_format() -> None:
    h = compute_content_hash("https://example.com/a", "body text")
    assert h.startswith("sha256:")
    assert len(h) == len("sha256:") + 64


def test_hash_stable_across_runs() -> None:
    a = compute_content_hash("https://example.com/a", "body text")
    b = compute_content_hash("https://example.com/a", "body text")
    assert a == b


def test_hash_changes_on_body_diff() -> None:
    a = compute_content_hash("https://example.com/a", "body text")
    b = compute_content_hash("https://example.com/a", "body text v2")
    assert a != b


def test_hash_changes_on_url_diff() -> None:
    a = compute_content_hash("https://example.com/a", "body text")
    b = compute_content_hash("https://example.com/b", "body text")
    assert a != b


def test_hash_unicode_safe() -> None:
    h = compute_content_hash("https://example.com/é", "résumé text — emoji 🌳")
    assert h.startswith("sha256:")
```

- [ ] **Step 2: Run, confirm fails**
- [ ] **Step 3: Implement** in `url_ingest.py`:

```python
import hashlib


def compute_content_hash(canonical_url: str, body: str) -> str:
    """Return `sha256:<hex>` over canonical_url + body."""
    encoded = f"{canonical_url}\n{body}".encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
```

- [ ] **Step 4: Run, confirm passes**
- [ ] **Step 5: Commit** `feat(ingest): compute_content_hash for URL idempotency`

---

# Phase 2 — Extraction layer

`fetch_and_extract(url) -> {"title": str, "body": str}` wraps httpx + trafilatura + BeautifulSoup. Tested against fixture HTML on disk; no live network calls.

## Task 3: Test fixtures

**Files:**
- Create: `shared-vault/skills/ingest/augur/tests/fixtures/article_simple.html`
- Create: `shared-vault/skills/ingest/augur/tests/fixtures/article_messy.html`
- Create: `shared-vault/skills/ingest/augur/tests/fixtures/article_empty.html`

- [ ] **Step 1: Write `article_simple.html`** — minimal, well-formed:

```html
<!doctype html>
<html><head><title>Why Trees Matter</title></head>
<body><article><h1>Why Trees Matter</h1>
<p>Trees are the lungs of the planet. They sequester carbon and stabilize soil.</p>
<p>Without forests we would lose biodiversity at an alarming rate.</p>
</article></body></html>
```

- [ ] **Step 2: Write `article_messy.html`** — with nav, footer, ads:

```html
<!doctype html>
<html><head><title>The Long Read — Tea Leaves</title></head>
<body>
<nav><a href="/">Home</a> | <a href="/about">About</a></nav>
<header>Site Header</header>
<aside class="ad">BUY OUR PRODUCT</aside>
<main><article>
<h1>The Art of Reading Tea Leaves</h1>
<p>Divination by tea has a longer history than the printing press.</p>
<p>Practitioners describe a pattern language of shapes and motions.</p>
</article></main>
<footer>Cookie banner. Subscribe!</footer>
</body></html>
```

- [ ] **Step 3: Write `article_empty.html`** — no extractable body:

```html
<!doctype html>
<html><head><title>Empty</title></head><body></body></html>
```

- [ ] **Step 4: Commit** `test(ingest): add HTML fixtures for url extract`

## Task 4: `fetch_and_extract` with httpx + trafilatura + BS4 fallback

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/url_ingest.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_url_extract.py`

- [ ] **Step 1: Write the failing test** — uses `httpx.MockTransport` to feed fixture HTML without network:

```python
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from skills.ingest.scripts.url_ingest import fetch_and_extract, ExtractionError

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
```

- [ ] **Step 2: Run, confirm fails**
- [ ] **Step 3: Add deps + implement** in `url_ingest.py`:

```python
class ExtractionError(RuntimeError):
    """Raised when a URL fetch or content extraction cannot produce a usable card."""


def fetch_and_extract(url: str, *, _transport: object | None = None) -> dict[str, str]:
    """Fetch URL and return {'title': str, 'body': str}.

    `_transport` is a test seam — production callers leave it None.
    """
    import httpx  # local import keeps module import cheap

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36 Augur/1.0"
        ),
    }
    client_kwargs: dict[str, object] = {
        "follow_redirects": True,
        "timeout": 20.0,
        "headers": headers,
    }
    if _transport is not None:
        client_kwargs["transport"] = _transport

    try:
        with httpx.Client(**client_kwargs) as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        raise ExtractionError(f"fetch failed: {exc}") from exc

    if response.status_code >= 400:
        raise ExtractionError(f"HTTP {response.status_code} for {url}")

    content_type = response.headers.get("content-type", "").lower()
    if "html" not in content_type and "xml" not in content_type:
        raise ExtractionError(f"unsupported content-type: {content_type or '(none)'}")

    html = response.text
    title, body = _extract_prose(html)
    if not body.strip():
        raise ExtractionError("extraction produced empty body")
    return {"title": title or url, "body": body.strip()}


def _extract_prose(html: str) -> tuple[str, str]:
    """Return (title, body) using trafilatura with BeautifulSoup fallback."""
    title = ""
    body = ""
    try:
        import trafilatura  # type: ignore[import-untyped]
        body = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
        metadata = trafilatura.extract_metadata(html)
        if metadata and metadata.title:
            title = metadata.title
    except Exception:  # pragma: no cover — fall through to BS4
        body = ""

    if not body.strip():
        from bs4 import BeautifulSoup  # type: ignore[import-untyped]

        soup = BeautifulSoup(html, "html.parser")
        if soup.title and soup.title.string:
            title = title or soup.title.string.strip()
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        article = soup.find("article") or soup.find("main") or soup.body
        if article is not None:
            body = article.get_text(separator="\n\n", strip=True)
    return title, body
```

- [ ] **Step 4: Add dependencies** to `pyproject.toml`:

```toml
"trafilatura>=1.6",
"beautifulsoup4>=4.12",
```

- [ ] **Step 5: Run `uv sync`** to pull deps.
- [ ] **Step 6: Run tests, confirm pass**
- [ ] **Step 7: Commit** `feat(ingest): fetch_and_extract with trafilatura + BS4 fallback`

---

# Phase 3 — Source-card writer

A new `write_url_source_card(meta, body)` that wraps `write_vault_frontmatter` with the URL-flavored frontmatter shape and the `<vault>/sources/urls/` layout. Independent of the inbox writer to avoid polluting that API.

## Task 5: `write_url_source_card` + dedup lookup

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/url_ingest.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_url_source_card.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter

from skills.ingest.scripts.url_ingest import (
    find_existing_url_card,
    write_url_source_card,
)


def _meta(**overrides) -> dict:
    base = {
        "title": "Why Trees Matter",
        "canonical_url": "https://example.com/a",
        "content_hash": "sha256:" + ("0" * 64),
        "tags": ["trees", "ecology"],
        "captured_at": "2026-05-10T12:00:00Z",
        "note": None,
    }
    base.update(overrides)
    return base


def test_write_url_card_creates_file_in_urls_dir(tmp_path: Path) -> None:
    path = write_url_source_card(
        vault_dir=tmp_path,
        meta=_meta(),
        body="Trees are the lungs of the planet.",
        today=date(2026, 5, 10),
    )
    assert path.parent == tmp_path / "sources" / "urls"
    assert path.name.startswith("2026-05-10-")
    assert path.name.endswith(".md")


def test_write_url_card_frontmatter_shape(tmp_path: Path) -> None:
    path = write_url_source_card(
        vault_dir=tmp_path,
        meta=_meta(),
        body="Trees are the lungs of the planet.",
        today=date(2026, 5, 10),
    )
    fm, body = parse_frontmatter(path)
    assert fm["title"] == "Why Trees Matter"
    assert fm["source_type"] == "url"
    assert fm["canonical_url"] == "https://example.com/a"
    assert fm["content_hash"].startswith("sha256:")
    assert fm["tags"] == ["trees", "ecology"]
    assert fm["captured_at"] == "2026-05-10T12:00:00Z"
    assert "lungs of the planet" in body


def test_write_url_card_optional_note(tmp_path: Path) -> None:
    path = write_url_source_card(
        vault_dir=tmp_path,
        meta=_meta(note="reading list"),
        body="b",
        today=date(2026, 5, 10),
    )
    fm, _ = parse_frontmatter(path)
    assert fm["note"] == "reading list"


def test_write_url_card_collision_safe(tmp_path: Path) -> None:
    first = write_url_source_card(
        vault_dir=tmp_path,
        meta=_meta(content_hash="sha256:" + ("a" * 64)),
        body="first",
        today=date(2026, 5, 10),
    )
    second = write_url_source_card(
        vault_dir=tmp_path,
        meta=_meta(content_hash="sha256:" + ("b" * 64)),
        body="second",
        today=date(2026, 5, 10),
    )
    assert first != second
    assert first.exists() and second.exists()


def test_find_existing_url_card_by_hash(tmp_path: Path) -> None:
    h = "sha256:" + ("c" * 64)
    written = write_url_source_card(
        vault_dir=tmp_path,
        meta=_meta(content_hash=h),
        body="b",
        today=date(2026, 5, 10),
    )
    found = find_existing_url_card(tmp_path, h)
    assert found == written


def test_find_existing_url_card_missing(tmp_path: Path) -> None:
    (tmp_path / "sources" / "urls").mkdir(parents=True)
    assert find_existing_url_card(tmp_path, "sha256:nope") is None
```

- [ ] **Step 2: Run, confirm fails**
- [ ] **Step 3: Implement** in `url_ingest.py`:

```python
from datetime import date as _date
from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter, write_vault_frontmatter


def _unique_path(target: Path) -> Path:
    """Return target or target-2, target-3, ... until we find an unused name."""
    if not target.exists():
        return target
    for index in range(2, 10_000):
        candidate = target.with_name(f"{target.stem}-{index}{target.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find available source card path for {target}")


def write_url_source_card(
    *,
    vault_dir: Path,
    meta: dict[str, object],
    body: str,
    today: _date | None = None,
) -> Path:
    """Write a URL source card under <vault>/sources/urls/<date>-<slug>.md."""
    today = today or _date.today()
    canonical_url = str(meta["canonical_url"])
    slug = slugify_url(canonical_url)
    target = vault_dir / "sources" / "urls" / f"{today.isoformat()}-{slug}.md"
    target = _unique_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    frontmatter = {
        "title": meta.get("title") or canonical_url,
        "source_type": "url",
        "canonical_url": canonical_url,
        "content_hash": meta["content_hash"],
        "tags": list(meta.get("tags") or []),
        "captured_at": meta["captured_at"],
        "_source_type": "ingest-url",
    }
    if meta.get("note"):
        frontmatter["note"] = meta["note"]

    summary = body[:800] or "No readable summary was captured."
    summary_callout = "\n".join(f"> {line}" if line else ">" for line in summary.splitlines())
    card_body = f"""# {frontmatter['title']}

> [!summary]
{summary_callout}

## Source

- URL: {canonical_url}
- Captured: {frontmatter['captured_at']}

## Body

{body}
"""
    write_vault_frontmatter(target, frontmatter, card_body)
    return target


def find_existing_url_card(vault_dir: Path, content_hash: str) -> Path | None:
    """Return path of an existing card with the given content_hash, or None."""
    urls_dir = vault_dir / "sources" / "urls"
    if not urls_dir.is_dir():
        return None
    for path in urls_dir.glob("*.md"):
        try:
            meta, _ = parse_frontmatter(path)
        except Exception:
            continue
        if meta.get("content_hash") == content_hash:
            return path
    return None
```

- [ ] **Step 4: Run, confirm pass**
- [ ] **Step 5: Commit** `feat(ingest): write_url_source_card + dedup lookup`

---

# Phase 4 — MCP tool registration

Wire the helpers into a FastMCP tool. Use the same `register_*_tools` pattern as `inbox_tools.py` and `wiki_tools.py`.

## Task 6: `register_url_tools` and `ingest-url` entry

**Files:**
- Create: `shared-vault/skills/ingest/scripts/mcp/url_tools.py`
- Modify: `shared-vault/skills/ingest/scripts/mcp/__init__.py`

- [ ] **Step 1: Implement** `shared-vault/skills/ingest/scripts/mcp/url_tools.py`:

```python
"""MCP tool definition for `ingest-url` — URL → source-card capture."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

_skill_root = Path(__file__).resolve().parents[2]
_scripts_dir = _skill_root / "scripts"
if str(_skill_root) not in sys.path:
    sys.path.insert(0, str(_skill_root))
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

try:
    from augur_mcp.logging import get_entity_logger
    from augur_mcp.annotations import tool_annotations
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        return importlib.import_module("logging").getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations

from skills.ingest.scripts.url_ingest import (
    ExtractionError,
    canonicalize_url,
    compute_content_hash,
    fetch_and_extract,
    find_existing_url_card,
    write_url_source_card,
)
from src.config.paths import get_vault_dir

logger = get_entity_logger("ingest-url")


def register_url_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any = None,
) -> None:
    @mcp.tool(
        name="ingest-url",
        annotations=tool_annotations(
            {
                "title": "Ingest URL",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def ingest_url_tool(
        url: str = "",
        tags: str = "[]",
        note: str = "",
    ) -> str:
        """Capture a URL as a source card so the wiki compounder picks it up.

        Args:
            url: URL to capture.
            tags: JSON-encoded list of tag strings, e.g. '["ecology","trees"]'.
            note: Optional one-line note from the caller.

        Returns:
            JSON: {success, path, sha256, deduplicated, canonical_url, title}
        """
        if metrics:
            metrics.track_tool("ingest_url", skill="ingest")

        try:
            if not url.strip():
                return json.dumps({"success": False, "error": "url is required"})

            parsed_tags = json.loads(tags) if isinstance(tags, str) else tags
            if not isinstance(parsed_tags, list):
                return json.dumps({"success": False, "error": "tags must be a JSON list"})

            canonical = canonicalize_url(url)
            extracted = fetch_and_extract(canonical)
            body = extracted["body"]
            title = extracted["title"]

            content_hash = compute_content_hash(canonical, body)
            vault_dir = get_vault_dir()

            existing = find_existing_url_card(vault_dir, content_hash)
            if existing is not None:
                return json.dumps(
                    {
                        "success": True,
                        "path": str(existing),
                        "sha256": content_hash,
                        "deduplicated": True,
                        "canonical_url": canonical,
                        "title": title,
                    },
                    indent=2,
                )

            path = write_url_source_card(
                vault_dir=vault_dir,
                meta={
                    "title": title,
                    "canonical_url": canonical,
                    "content_hash": content_hash,
                    "tags": parsed_tags,
                    "captured_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    "note": note or None,
                },
                body=body,
            )
            return json.dumps(
                {
                    "success": True,
                    "path": str(path),
                    "sha256": content_hash,
                    "deduplicated": False,
                    "canonical_url": canonical,
                    "title": title,
                },
                indent=2,
            )
        except ExtractionError as exc:
            logger.warning("ingest-url extraction failed for %s: %s", url, exc)
            return json.dumps({"success": False, "error": str(exc)})
        except Exception as exc:
            logger.error("ingest-url failed: %s", exc, exc_info=True)
            return json.dumps({"success": False, "error": str(exc)})


__all__ = ["register_url_tools"]
```

- [ ] **Step 2: Wire into the registrar** — modify `shared-vault/skills/ingest/scripts/mcp/__init__.py`:

```python
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from .inbox_tools import register_inbox_tools
from .url_tools import register_url_tools
from .wiki_tools import register_wiki_tools

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any = None,
) -> None:
    register_inbox_tools(mcp, mcp_tool_interceptor, metrics)
    register_wiki_tools(mcp, mcp_tool_interceptor, metrics)
    register_url_tools(mcp, mcp_tool_interceptor, metrics)


__all__ = ["register_tools"]
```

- [ ] **Step 3: Commit** `feat(ingest): register ingest-url MCP tool`

---

# Phase 5 — Integration test

End-to-end test that exercises the full registered MCP tool against a stubbed HTTP layer and a real temp vault. Includes the dedup re-run.

## Task 7: Full-flow integration test

**Files:**
- Test: `shared-vault/skills/ingest/augur/tests/test_url_ingest_mcp.py`

- [ ] **Step 1: Write the integration test**

```python
"""Integration test for the registered ingest-url MCP tool.

Strategy: drive the underlying helpers directly (the MCP decorator wraps an async
function; we test the wrapped logic end-to-end without spinning up a FastMCP
server). Network is stubbed via httpx.MockTransport.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx

from src.lib.frontmatter_utils import parse_frontmatter

from skills.ingest.scripts.url_ingest import (
    canonicalize_url,
    compute_content_hash,
    fetch_and_extract,
    find_existing_url_card,
    write_url_source_card,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _run_ingest(url: str, vault_dir: Path, tags: list[str], note: str | None) -> dict:
    """Reproduce the body of ingest_url_tool without the FastMCP decorator."""
    from datetime import UTC, datetime

    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200,
            content=(FIXTURES / "article_simple.html").read_bytes(),
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )

    canonical = canonicalize_url(url)
    extracted = fetch_and_extract(canonical, _transport=transport)
    content_hash = compute_content_hash(canonical, extracted["body"])

    existing = find_existing_url_card(vault_dir, content_hash)
    if existing is not None:
        return {
            "success": True,
            "path": str(existing),
            "sha256": content_hash,
            "deduplicated": True,
        }

    path = write_url_source_card(
        vault_dir=vault_dir,
        meta={
            "title": extracted["title"],
            "canonical_url": canonical,
            "content_hash": content_hash,
            "tags": tags,
            "captured_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "note": note,
        },
        body=extracted["body"],
    )
    return {
        "success": True,
        "path": str(path),
        "sha256": content_hash,
        "deduplicated": False,
    }


def test_first_capture_writes_card(tmp_path: Path) -> None:
    result = _run_ingest(
        "https://example.com/why-trees-matter?utm_source=newsletter",
        vault_dir=tmp_path,
        tags=["ecology", "trees"],
        note=None,
    )
    assert result["success"] is True
    assert result["deduplicated"] is False
    card_path = Path(result["path"])
    assert card_path.parent == tmp_path / "sources" / "urls"
    fm, body = parse_frontmatter(card_path)
    assert fm["title"] == "Why Trees Matter"
    assert fm["source_type"] == "url"
    # canonicalization stripped utm_source
    assert fm["canonical_url"] == "https://example.com/why-trees-matter"
    assert fm["tags"] == ["ecology", "trees"]
    assert "lungs of the planet" in body


def test_second_capture_deduplicates(tmp_path: Path) -> None:
    first = _run_ingest(
        "https://example.com/why-trees-matter",
        vault_dir=tmp_path,
        tags=["ecology"],
        note=None,
    )
    second = _run_ingest(
        # different tracking params, same canonical URL
        "https://example.com/why-trees-matter?utm_campaign=spring",
        vault_dir=tmp_path,
        tags=["ecology"],
        note=None,
    )
    assert second["deduplicated"] is True
    assert second["path"] == first["path"]
    assert second["sha256"] == first["sha256"]
    # only one card exists on disk
    cards = list((tmp_path / "sources" / "urls").glob("*.md"))
    assert len(cards) == 1


def test_canonicalization_strips_tracking_before_hash(tmp_path: Path) -> None:
    a = _run_ingest(
        "https://example.com/a?utm_source=twitter",
        vault_dir=tmp_path,
        tags=[],
        note=None,
    )
    b = _run_ingest(
        "https://example.com/a?gclid=xyz",
        vault_dir=tmp_path,
        tags=[],
        note=None,
    )
    assert a["sha256"] == b["sha256"]
    assert b["deduplicated"] is True
```

- [ ] **Step 2: Run, confirm pass**
- [ ] **Step 3: Commit** `test(ingest): integration test for ingest-url with dedup`

## Task 8: Manual smoke (operator checklist)

- [ ] **Step 1: Restart the MCP server** so the new registrar mounts:

  ```bash
  /dev-build  # or whichever loop reloads the ingest MCP
  ```

- [ ] **Step 2: From an MCP client, call:**

  ```
  ingest-url url="https://en.wikipedia.org/wiki/Tea" tags='["beverages"]'
  ```

  Expect: `{"success": true, "deduplicated": false, "path": "/.../<date>-en-wikipedia-org-wiki-tea.md", ...}`

- [ ] **Step 3: Re-run the same call.** Expect `"deduplicated": true` and the same path.
- [ ] **Step 4: Verify wiki pickup.** Run `wiki-scan-sources` (or whichever the current loop is) and confirm the new card appears in the source list with `source_surface: vault`.
- [ ] **Step 5: Cleanup** — delete the smoke-test card if desired.

---

# Verification matrix

| Probe | What it proves |
|---|---|
| `test_url_canonicalize.py` | Tracking-param stripping, fragment removal, query sort, host case, idempotency |
| `test_url_content_hash.py` | Hash stability across runs, sensitivity to body and URL changes, unicode safety |
| `test_url_extract.py` | httpx + trafilatura works on simple article, BS4 fallback strips nav/footer/ads, empty body raises, non-HTML rejected, HTTP errors raise |
| `test_url_source_card.py` | Card lands in `<vault>/sources/urls/<date>-<slug>.md`, frontmatter shape matches spec, collision-safe filename, dedup lookup works |
| `test_url_ingest_mcp.py` | Full flow: first call writes, second call dedupes, canonicalization happens before hash so tracking-param variants collapse |
| Manual smoke against Wikipedia | Real-network sanity check; deduplicated re-run; wiki scanner pickup |

---

# Rollback plan

The change is additive and isolated:

1. Revert the three commits (`feat(ingest): canonicalize…`, `feat(ingest): compute_content_hash…`, `feat(ingest): fetch_and_extract…`, `feat(ingest): write_url_source_card…`, `feat(ingest): register ingest-url MCP tool`).
2. Drop the new `url_ingest.py` and `mcp/url_tools.py`.
3. Remove `trafilatura` and `beautifulsoup4` from `pyproject.toml`; run `uv sync`.
4. Restore the original `mcp/__init__.py` (remove the third registrar call).

Cards already written to `<vault>/sources/urls/` remain valid markdown with valid frontmatter; the scanner continues to consume them. No vault data loss on rollback.

---

# Out of scope (re-confirming spec)

- No vault skill creation (the existing `~/Projects/Au-vault/skills/vault/` provides browse/edit/search).
- No `/brain/vault` page redesign.
- No bulk-URL ingest endpoint — single URL per call; loop client-side.
- No background URL fetching — synchronous within the MCP call.
- No rate-limiting, robots.txt respect, per-domain auth — future hardening ADR if needed.
- No HTML archive snapshot — body-only persistence for now.
