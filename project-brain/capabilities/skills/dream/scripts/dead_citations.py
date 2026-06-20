"""Dream-cycle dead-citation scanner (ADR-744 task 5).

Walks every wiki page's ``## Timeline`` section, extracts each ``_source:`` URI,
and flags those that resolve to nothing. Flag-only — never deletes or rewrites
the citing page.

Resolved schemes:

- ``vault://<path>``        → ``<vault_root>/<path>`` must exist
- ``source-card://<id>``    → ``<vault_root>/source-cards/<id>.md`` must exist
- ``graph://<entity_id>``   → entity must appear as ``src`` or ``dst`` in
                              ``<cache_root>/graph/edges.jsonl``

The MCP wrapper in ``scripts/mcp/__init__.py`` passes the real
``get_vault_dir()`` and ``get_cache_dir()`` values; this module accepts both
roots as parameters so the test suite can drive deterministic input.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_TIMELINE_HEADING_RE = re.compile(r"(?m)^## Timeline\s*$")
_NEXT_HEADING_RE = re.compile(r"(?m)^## ")
_TIMELINE_ENTRY_RE = re.compile(
    r"(?m)^- _at: (?P<at>\S+)\s+_source: (?P<source>\S+)\s*$"
)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)
_FRONTMATTER_KV_RE = re.compile(
    r"(?m)^(?P<key>[A-Za-z_][A-Za-z0-9_]*):\s*(?P<value>.*)$"
)
_URI_RE = re.compile(r"^(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*)://(?P<rest>.+)$")


def dream_dead_citations(
    *,
    vault_root: Path,
    cache_root: Path,
) -> dict[str, Any]:
    """Flag timeline ``_source:`` URIs that resolve to nothing.

    Returns ``{"flagged": [{"page_slug", "timeline_at", "source_uri",
    "scheme", "reason"}, ...]}``. ``reason`` is currently always ``"missing"``;
    future expansions (e.g. ``"unreachable"``, ``"redirected"``) reuse the
    same record shape.
    """
    graph_entities = _graph_entities(cache_root)
    flagged: list[dict[str, Any]] = []

    for page_path in _iter_wiki_pages(vault_root):
        slug = _slug_for(page_path)
        if slug is None:
            continue
        text = page_path.read_text(encoding="utf-8")
        section = _timeline_section(text)
        for match in _TIMELINE_ENTRY_RE.finditer(section):
            source_uri = match.group("source").strip()
            timeline_at = match.group("at").strip()
            scheme, rest = _split_uri(source_uri)
            if scheme is None:
                continue
            if _resolves(scheme, rest, vault_root=vault_root, graph_entities=graph_entities):
                continue
            flagged.append(
                {
                    "page_slug": slug,
                    "timeline_at": timeline_at,
                    "source_uri": source_uri,
                    "scheme": scheme,
                    "reason": "missing",
                }
            )

    flagged.sort(key=lambda entry: (entry["page_slug"], entry["timeline_at"]))
    return {"flagged": flagged}


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _iter_wiki_pages(vault_root: Path):
    from src.lib.brain_layout import brain_wiki_dir

    wiki_dir = brain_wiki_dir(vault_root)
    if not wiki_dir.is_dir():
        return
    yield from sorted(wiki_dir.glob("*.md"))


def _slug_for(page_path: Path) -> str | None:
    text = page_path.read_text(encoding="utf-8")
    fm_match = _FRONTMATTER_RE.match(text)
    if fm_match:
        for kv in _FRONTMATTER_KV_RE.finditer(fm_match.group("body")):
            if kv.group("key") == "slug":
                slug = kv.group("value").strip().strip('"').strip("'")
                if slug:
                    return slug
    return page_path.stem or None


def _timeline_section(text: str) -> str:
    match = _TIMELINE_HEADING_RE.search(text)
    if not match:
        return ""
    start = match.end()
    rest = text[start:]
    next_heading = _NEXT_HEADING_RE.search(rest)
    end = next_heading.start() if next_heading else len(rest)
    return rest[:end]


def _split_uri(uri: str) -> tuple[str | None, str]:
    match = _URI_RE.match(uri)
    if not match:
        return None, ""
    return match.group("scheme"), match.group("rest")


def _graph_entities(cache_root: Path) -> set[str]:
    """All entity ids that appear as src or dst in edges.jsonl."""
    edges_path = cache_root / "graph" / "edges.jsonl"
    if not edges_path.is_file():
        return set()
    entities: set[str] = set()
    for line in edges_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        for key in ("src", "dst"):
            value = record.get(key)
            if value:
                entities.add(value)
    return entities


def _resolves(
    scheme: str,
    rest: str,
    *,
    vault_root: Path,
    graph_entities: set[str],
) -> bool:
    if scheme == "vault":
        return (vault_root / rest.lstrip("/")).exists()
    if scheme == "source-card":
        return (vault_root / "source-cards" / f"{rest}.md").exists()
    if scheme == "graph":
        return rest in graph_entities
    # Unknown scheme — be conservative and call it resolved (don't false-flag).
    return True


__all__ = ["dream_dead_citations"]
