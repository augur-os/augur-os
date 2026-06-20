"""Deterministic typed-edge extraction (ADR-738).

extract(path, known=..., ruleset=...) -> list[Edge]. No LLM. Three rule kinds,
applied in order so a link claimed by a specific rule is never double-emitted as
the bare `mentions` fallback.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.lib.frontmatter_utils import parse_frontmatter

from edge_rules import RuleSet, load_rules  # sibling import (scripts/ on sys.path)

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*$")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")


@dataclass(frozen=True)
class Edge:
    """A typed edge: src --type--> dst, both page-id strings."""

    src: str
    dst: str
    type: str


def _page_id(path: Path) -> str:
    """Page id = filename stem (matches how [[wikilinks]] resolve)."""
    return path.stem


def _norm(target: str) -> str:
    """Normalize a link target / frontmatter value to a bare page id."""
    m = _WIKILINK_RE.search(target) if "[[" in target else None
    return (m.group(1) if m else target).strip()


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def _headings_with_links(body: str) -> tuple[dict[str, set[str]], set[str]]:
    """Return ({heading: {link, ...}}, {all links anywhere}).

    A heading "owns" only the [[wikilinks]] that appear in list-item lines within
    its section. Loose prose links are never heading-scoped — they fall through to
    the bare `mentions` fallback. This keeps heading-scoped edge types (cites,
    depends_on) deterministic: they claim bulleted references, not inline mentions.
    """
    by_heading: dict[str, set[str]] = {}
    all_links: set[str] = set()
    current = ""
    for line in body.splitlines():
        h = _HEADING_RE.match(line)
        if h:
            current = h.group(1).strip()
            by_heading.setdefault(current, set())
            continue
        is_list_item = bool(_LIST_ITEM_RE.match(line))
        for m in _WIKILINK_RE.finditer(line):
            link = m.group(1).strip()
            all_links.add(link)
            if current and is_list_item:
                by_heading[current].add(link)
    return by_heading, all_links


def extract(
    path: str | Path,
    *,
    known: dict[str, Any] | None = None,
    ruleset: RuleSet | None = None,
) -> list[Edge]:
    """Extract typed edges for one page. Deterministic, no model calls."""
    path = Path(path)
    rs = ruleset or load_rules()
    known = known or {}
    src = _page_id(path)
    meta, body = parse_frontmatter(path)
    by_heading, all_links = _headings_with_links(body)

    edges: set[Edge] = set()
    claimed: set[str] = set()  # links claimed by a specific (non-bare) rule

    # 1. frontmatter_key rules
    for edge_type, rule in rs.rules_for_kind("frontmatter_key"):
        for raw in _as_list(meta.get(rule["key"])):
            dst = _norm(raw)
            if dst:
                edges.add(Edge(src, dst, edge_type))

    # 2. concept_hook rules — consume concepts the caller already extracted
    for edge_type, _rule in rs.rules_for_kind("concept_hook"):
        for concept in known.get("concepts", []):
            dst = _norm(str(concept))
            if dst:
                edges.add(Edge(src, dst, edge_type))

    # 3a. body_wikilink heading-scoped rules
    for edge_type, rule in rs.rules_for_kind("body_wikilink"):
        if rule.get("scope") != "heading":
            continue
        wanted = {h.lower() for h in rule.get("headings", [])}
        for heading, links in by_heading.items():
            if heading.lower() in wanted:
                for link in links:
                    edges.add(Edge(src, link, edge_type))
                    claimed.add(link)

    # 3b. body_wikilink bare fallback — any link not already claimed
    for edge_type, rule in rs.rules_for_kind("body_wikilink"):
        if rule.get("scope") != "bare":
            continue
        for link in all_links - claimed:
            edges.add(Edge(src, link, edge_type))

    # Drop self-edges: a page that tags/links itself (e.g. research.md with
    # `tags: [research]`) is not a relationship — it is extraction noise.
    edges = {e for e in edges if e.src != e.dst}

    return sorted(edges, key=lambda e: (e.type, e.dst))
