"""URL ingest helpers for the ingest-url MCP tool."""
from __future__ import annotations

import hashlib
import inspect
import re
from collections.abc import Awaitable, Callable
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.config.paths import get_pending_enrichment_queue_path
from src.lib.brain_layout import brain_capture_dir
from src.lib.frontmatter_utils import parse_frontmatter, write_vault_frontmatter

from src.lib.ingest.pending_enrichment_queue import enqueue
from skills.ingest.scripts.slug_policy import capture_slug, unique_name

_TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "igshid",
        "ref",
        "ref_src",
    }
)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class ExtractionError(RuntimeError):
    """Raised when URL fetch or extraction cannot produce usable content."""


def canonicalize_url(url: str) -> str:
    """Return a stable URL form for idempotency and content hashing."""
    raw = url.strip()
    if "://" not in raw and not raw.startswith("//"):
        raw = f"https://{raw}"

    parts = urlsplit(raw)
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAMS
    ]
    query_pairs.sort()
    query = urlencode(query_pairs)
    return urlunsplit((scheme, netloc, path, query, ""))


def slugify_url(url: str, *, max_len: int = 80) -> str:
    """Return a filesystem-safe slug derived from the URL host and path."""
    parts = urlsplit(canonicalize_url(url))
    raw = f"{parts.netloc}{parts.path}".lower()
    slug = _SLUG_RE.sub("-", raw).strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or "untitled"


def compute_content_hash(canonical_url: str, body: str) -> str:
    """Return ``sha256:<hex>`` over canonical URL plus extracted body."""
    # TODO_BUG: dedup is fragile when extraction includes volatile page chrome.
    # Some sites (e.g. Substack) leak live engagement counts ("26 2 Share") and
    # nav into the extracted body, so the same URL hashes differently across
    # fetches and re-noting spawns duplicate cards instead of deduplicating.
    # Consider hashing on canonical_url + a normalized/boilerplate-stripped body,
    # or url-only dedup with a separate content-change signal.
    encoded = f"{canonical_url}\n{body}".encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


# --- Source-aware fallback for JS-rendered / erroring pages (e.g. GitHub repos) ---
# Many sites render their content via JavaScript, so an HTML fetch returns an app
# shell ("There was an error while loading…") or errors (e.g. 504). For hosts with
# a known plain-text source, fall back to that source so capture yields real prose
# instead of a stub. Currently: GitHub repo -> raw README.
_GITHUB_HOSTS = frozenset({"github.com", "www.github.com"})
_GITHUB_NON_REPO = frozenset({
    "orgs", "features", "topics", "sponsors", "marketplace", "settings", "about",
    "pricing", "collections", "explore", "notifications", "issues", "pulls",
    "login", "join", "search", "new",
})
_STUB_MARKERS = (
    "there was an error while loading",
    "please reload this page",
    "to see all available qualifiers",
    "you need to enable javascript",
    "enable javascript to run this app",
)
_STUB_MIN_WORDS = 40


def _has_stub_marker(body: str) -> bool:
    low = body.lower()
    return any(marker in low for marker in _STUB_MARKERS)


def _github_repo(url: str) -> tuple[str, str] | None:
    """Return (owner, repo) for a github.com repository URL, else None."""
    parts = urlsplit(url if "://" in url else f"https://{url}")
    if parts.netloc.lower() not in _GITHUB_HOSTS:
        return None
    segs = [s for s in parts.path.split("/") if s]
    if len(segs) < 2 or segs[0].lower() in _GITHUB_NON_REPO:
        return None
    repo = segs[1][:-4] if segs[1].endswith(".git") else segs[1]
    return segs[0], repo


def _readme_title(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def _clean_readme(markdown: str) -> str:
    """Strip HTML comment blocks (AI-AGENT-SUMMARY etc.) and collapse blank runs."""
    text = re.sub(r"<!--.*?-->", "", markdown, flags=re.DOTALL)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _source_fallback(url: str, *, _transport: object | None = None) -> dict[str, str] | None:
    """Return {title, body} from a known plain-text source for *url*, or None.

    GitHub repo -> raw README (tries main/master and common README names)."""
    repo = _github_repo(url)
    if repo is None:
        return None
    owner, name = repo
    import httpx

    client_kwargs: dict[str, object] = {
        "follow_redirects": True, "timeout": 20.0,
        "headers": {"User-Agent": "Augur/1.0"},
    }
    if _transport is not None:
        client_kwargs["transport"] = _transport
    for branch in ("main", "master"):
        for fname in ("README.md", "readme.md", "README.rst", "README"):
            raw = f"https://raw.githubusercontent.com/{owner}/{name}/{branch}/{fname}"
            try:
                with httpx.Client(**client_kwargs) as client:
                    resp = client.get(raw)
            except httpx.HTTPError:
                continue
            if resp.status_code == 200 and resp.text.strip():
                body = _clean_readme(resp.text)
                if body:
                    return {"title": _readme_title(resp.text) or f"{owner}/{name}", "body": body}
    return None


def fetch_and_extract(url: str, *, _transport: object | None = None) -> dict[str, str]:
    """Fetch a URL and return extracted title/body. Falls back to a source feed
    (e.g. GitHub raw README) when the page is JS-rendered (stub) or errors."""
    import httpx

    client_kwargs: dict[str, object] = {
        "follow_redirects": True,
        "timeout": 20.0,
        "headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36 Augur/1.0"
            ),
        },
    }
    if _transport is not None:
        client_kwargs["transport"] = _transport

    primary_error: str | None = None
    title, body = "", ""
    try:
        with httpx.Client(**client_kwargs) as client:
            response = client.get(url)
        if response.status_code >= 400:
            primary_error = f"HTTP {response.status_code} for {url}"
        else:
            content_type = response.headers.get("content-type", "").lower()
            if "html" not in content_type and "xml" not in content_type:
                primary_error = f"unsupported content-type: {content_type or '(none)'}"
            else:
                title, body = _extract_prose(response.text)
                body = body.strip()
    except httpx.HTTPError as exc:
        primary_error = f"fetch failed: {exc}"

    # Good primary content -> use it.
    if body and not _has_stub_marker(body) and len(body.split()) >= _STUB_MIN_WORDS:
        return {"title": title or url, "body": body}

    # Primary failed, empty, stub-marked, or too thin -> source-aware fallback.
    fallback = _source_fallback(url, _transport=_transport)
    if fallback is not None:
        return fallback

    # No fallback for this host: keep a non-empty, non-stub body even if thin
    # (do not regress legitimately short pages).
    if body and not _has_stub_marker(body):
        return {"title": title or url, "body": body}

    raise ExtractionError(primary_error or f"extraction produced empty or stub body for {url}")


def _extract_prose(html: str) -> tuple[str, str]:
    """Return title and body using trafilatura with local parser fallbacks."""
    title = ""
    body = ""
    try:
        import trafilatura  # type: ignore[import-untyped]

        body = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
        ) or ""
        metadata = trafilatura.extract_metadata(html)
        if metadata and metadata.title:
            title = metadata.title.strip()
    except Exception:
        body = ""

    if not body.strip() or not title:
        fallback_title, fallback_body = _extract_prose_fallback(html)
        title = title or fallback_title
        if not body.strip():
            body = fallback_body
    return title, body


def _extract_prose_fallback(html: str) -> tuple[str, str]:
    try:
        from bs4 import BeautifulSoup  # type: ignore[import-untyped]
    except ImportError:
        return _extract_prose_with_html_parser(html)

    soup = BeautifulSoup(html, "html.parser")
    title = ""
    body = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    article = soup.find("article") or soup.find("main") or soup.body
    if article is not None:
        body = article.get_text(separator="\n\n", strip=True)
    return title, body


class _ProseHTMLParser(HTMLParser):
    _SKIP_TAGS = frozenset({"script", "style", "nav", "footer", "header", "aside"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.article_parts: list[str] = []
        self.main_parts: list[str] = []
        self.body_parts: list[str] = []
        self._skip_depth = 0
        self._title_depth = 0
        self._article_depth = 0
        self._main_depth = 0
        self._body_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        normalized = tag.lower()
        if normalized in self._SKIP_TAGS:
            self._skip_depth += 1
        if normalized == "title":
            self._title_depth += 1
        elif normalized == "article":
            self._article_depth += 1
        elif normalized == "main":
            self._main_depth += 1
        elif normalized == "body":
            self._body_depth += 1

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if normalized == "title" and self._title_depth:
            self._title_depth -= 1
        elif normalized == "article" and self._article_depth:
            self._article_depth -= 1
        elif normalized == "main" and self._main_depth:
            self._main_depth -= 1
        elif normalized == "body" and self._body_depth:
            self._body_depth -= 1

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self._title_depth:
            self.title_parts.append(text)
            return
        if self._skip_depth:
            return
        if self._article_depth:
            self.article_parts.append(text)
        if self._main_depth:
            self.main_parts.append(text)
        if self._body_depth:
            self.body_parts.append(text)


def _extract_prose_with_html_parser(html: str) -> tuple[str, str]:
    parser = _ProseHTMLParser()
    parser.feed(html)
    parser.close()
    title = " ".join(parser.title_parts).strip()
    body_parts = parser.article_parts or parser.main_parts or parser.body_parts
    body = "\n\n".join(body_parts).strip()
    return title, body


def _unique_path(target: Path) -> Path:
    if not target.exists():
        return target
    for index in range(2, 10_000):
        candidate = target.with_name(f"{target.stem}-{index}{target.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find available source card path for {target}")


def _summary_callout(body: str) -> str:
    summary = body[:800] or "No readable summary was captured."
    return "\n".join(f"> {line}" if line else ">" for line in summary.splitlines())


def card_target_path(
    vault_dir: Path,
    canonical_url: str,
    today: date | None = None,  # kept for callers that still pass it; no longer used for name
    title: str | None = None,
) -> Path:
    """Return the (deduplicated) target path for a URL source card.

    Naming spec 2026-06-12 Wave 3: date-free slug derived from the page title
    when available, falling back to the URL.  ``today`` is accepted for
    backward-compat but no longer included in the filename (date lives in
    frontmatter).
    """
    # Prefer title over URL as slug source; fall back to URL (capture_slug
    # strips scheme/www noise from either source).
    slug = capture_slug(title) if title and title.strip() else "untitled"
    if slug == "untitled":
        # Title missing or slugged to nothing (emoji-only/punctuation-only):
        # slug the URL instead so cards never pile up as untitled-N.md.
        slug = capture_slug(canonical_url)
    capture_dir = brain_capture_dir(vault_dir)
    capture_dir.mkdir(parents=True, exist_ok=True)
    return capture_dir / f"{unique_name(capture_dir, slug)}.md"


def write_url_source_card(
    *,
    vault_dir: Path,
    meta: dict[str, object],
    body: str,
    today: date | None = None,
) -> Path:
    """Write a URL source card under the vault capture dir."""
    today = today or date.today()
    canonical_url = str(meta["canonical_url"])
    title = str(meta.get("title") or canonical_url)
    target = card_target_path(vault_dir, canonical_url, today, title=title)
    target.parent.mkdir(parents=True, exist_ok=True)

    frontmatter: dict[str, object] = {
        "title": title,
        "source_type": "url",
        "x-augur-note-type": "url",
        "canonical_url": canonical_url,
        "content_hash": meta["content_hash"],
        "tags": list(meta.get("tags") or []),
        "captured_at": meta["captured_at"],
    }
    if meta.get("note"):
        frontmatter["note"] = meta["note"]

    card_body = f"""# {title}

> [!summary]
{_summary_callout(body)}

## Source

- URL: {canonical_url}
- Captured: {frontmatter["captured_at"]}

## Body

{body}
"""
    write_vault_frontmatter(target, frontmatter, card_body)

    try:
        enqueue(get_pending_enrichment_queue_path(), note_path=target, reason="new")
    except Exception:  # noqa: BLE001 — enrichment queue must never block note capture
        pass

    # ADR-738 — emit typed edges as part of the URL source-card write. Pass any
    # concepts the caller already extracted so `mentions` edges are exact.
    try:
        import sys as _sys
        _graph_scripts = str(
            Path(__file__).resolve().parents[2] / "graph" / "scripts"
        )
        if _graph_scripts not in _sys.path:
            _sys.path.insert(0, _graph_scripts)
        import graph_ops  # type: ignore[import-not-found]

        _concepts = list(meta.get("concepts") or [])
        graph_ops.index_page_from_write_path(
            target,
            source_type="url",
            known={"concepts": _concepts} if _concepts else None,
        )
    except Exception:  # noqa: BLE001 — graph is best-effort, never breaks ingest
        pass

    return target


def find_existing_url_card(vault_dir: Path, content_hash: str) -> Path | None:
    """Return the existing URL note path for ``content_hash`` if present."""
    urls_dir = brain_capture_dir(vault_dir)
    if not urls_dir.is_dir():
        return None

    for path in sorted(urls_dir.glob("*.md")):
        try:
            metadata, _ = parse_frontmatter(path)
        except Exception:
            continue
        if metadata.get("content_hash") == content_hash:
            return path
    return None


FetchResult = dict[str, str] | Awaitable[dict[str, str]]
Fetcher = Callable[[str], FetchResult]


async def maybe_await_fetch(fetcher: Fetcher, url: str) -> dict[str, str]:
    """Call a sync or async fetcher and normalize to an extracted payload."""
    result = fetcher(url)
    if inspect.isawaitable(result):
        return await result
    return result


__all__ = [
    "ExtractionError",
    "Fetcher",
    "canonicalize_url",
    "compute_content_hash",
    "fetch_and_extract",
    "find_existing_url_card",
    "maybe_await_fetch",
    "slugify_url",
    "write_url_source_card",
]
