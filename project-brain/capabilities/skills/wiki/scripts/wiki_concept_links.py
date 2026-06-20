"""Concept-first wiki wikilink resolver and lint helpers."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, TypedDict

from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.wiki_utils import WIKILINK_RE


class BrokenLink(TypedDict):
    page: str
    target: str


class LegacyPage(TypedDict):
    page: str
    reasons: list[str]


class DuplicateAlias(TypedDict):
    alias: str
    pages: list[str]


class WikiLink(TypedDict):
    page: str
    target: str
    resolved: str | None


class ConceptLinkLintResult(TypedDict):
    ok: bool
    path: str
    pages: int
    broken_links: list[BrokenLink]
    legacy_pages: list[LegacyPage]
    duplicate_aliases: list[DuplicateAlias]
    links: list[WikiLink]


_SLUG_CHARS_RE = re.compile(r"[^\w\s/-]")
_SPACING_RE = re.compile(r"[\s_]+")
_DASH_RE = re.compile(r"-+")


def _normalize_page_name(name: str) -> str:
    normalized = name.strip().replace("\\", "/")
    if normalized.endswith(".md"):
        normalized = normalized[:-3]
    normalized = normalized.strip("/")
    normalized = _SLUG_CHARS_RE.sub("", normalized)
    normalized = _SPACING_RE.sub("-", normalized)
    normalized = _DASH_RE.sub("-", normalized).strip("-/")
    return normalized or "note"


def _normalize_lookup_key(value: str) -> str:
    return _normalize_page_name(value).lower()


def _page_name(path: Path, wiki_dir: Path) -> str:
    return str(path.relative_to(wiki_dir).with_suffix(""))


def _aliases(meta: dict[str, Any]) -> list[str]:
    raw = meta.get("aliases", [])
    if not isinstance(raw, list):
        return []
    return [
        str(item).strip()
        for item in raw
        if str(item).strip()
    ]


def build_concept_link_index(wiki_dir: Path) -> dict[str, list[str]]:
    """Build a deterministic resolver index for wiki links."""
    wiki_dir = Path(wiki_dir)
    index: dict[str, set[str]] = {}
    if not wiki_dir.is_dir():
        return {}

    for path in sorted(wiki_dir.rglob("*.md")):
        page = _page_name(path, wiki_dir)
        meta, _body = parse_frontmatter(path)
        title = str(meta.get("title") or "").strip()
        page_type = str(meta.get("page_type") or "").strip()
        candidates = {
            page,
            Path(page).name,
        }
        if title:
            candidates.add(title)
        candidates.update(_aliases(meta))
        if page_type in {"concept", "query"} or page.startswith(("concepts/", "queries/")):
            candidates.add(Path(page).stem)

        for candidate in candidates:
            key = _normalize_lookup_key(candidate)
            if key:
                index.setdefault(key, set()).add(page)

    return {
        key: sorted(pages)
        for key, pages in sorted(index.items())
    }


def resolve_wikilink(target: str, index: dict[str, list[str]]) -> str | None:
    """Resolve a wikilink target to a page name, returning None when missing or ambiguous."""
    matches = index.get(_normalize_lookup_key(target), [])
    return matches[0] if len(matches) == 1 else None


def lint_concept_links(wiki_dir: Path) -> ConceptLinkLintResult:
    """Validate concept wikilinks and legacy source-shaped wiki pages."""
    wiki_dir = Path(wiki_dir)
    if not wiki_dir.is_dir():
        return {
            "ok": False,
            "path": str(wiki_dir),
            "pages": 0,
            "broken_links": [],
            "legacy_pages": [],
            "duplicate_aliases": [],
            "links": [],
        }

    index = build_concept_link_index(wiki_dir)
    broken_links: list[BrokenLink] = []
    legacy_reasons: dict[str, set[str]] = {}
    links: list[WikiLink] = []
    alias_index: dict[str, set[str]] = {}

    for path in sorted(wiki_dir.rglob("*.md")):
        page = _page_name(path, wiki_dir)
        meta, body = parse_frontmatter(path)
        page_type = str(meta.get("page_type") or "").strip()
        if page_type in {"source-summary", "query-output"}:
            legacy_reasons.setdefault(page, set()).add(f"page_type:{page_type}")
        if page == "sources" or page.startswith("sources/"):
            legacy_reasons.setdefault(page, set()).add("path:sources")

        for alias in _aliases(meta):
            alias_index.setdefault(_normalize_lookup_key(alias), set()).add(page)

        for target in WIKILINK_RE.findall(body):
            resolved = resolve_wikilink(target, index)
            links.append({"page": page, "target": target, "resolved": resolved})
            if resolved is None:
                broken_links.append({"page": page, "target": target})

    legacy_pages = [
        {"page": page, "reasons": sorted(reasons)}
        for page, reasons in sorted(legacy_reasons.items())
    ]
    duplicate_aliases = [
        {"alias": alias, "pages": sorted(pages)}
        for alias, pages in sorted(alias_index.items())
        if len(pages) > 1
    ]

    return {
        "ok": not broken_links and not legacy_pages and not duplicate_aliases,
        "path": str(wiki_dir),
        "pages": len({_page_name(path, wiki_dir) for path in wiki_dir.rglob("*.md")}),
        "broken_links": broken_links,
        "legacy_pages": legacy_pages,
        "duplicate_aliases": duplicate_aliases,
        "links": links,
    }
