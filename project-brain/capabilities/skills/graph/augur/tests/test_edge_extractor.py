"""Tests for edge_extractor.py — typed knowledge graph (ADR-738).

Imports via importlib.util.spec_from_file_location per feedback_skill_test_convention.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any


SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))  # let sibling `from edge_rules import ...` resolve


def _load(module_name: str, file_name: str) -> Any:
    full_name = f"graph_{module_name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    if module_name in sys.modules:  # already imported as a sibling — reuse, don't dup
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(full_name, SCRIPTS_DIR / file_name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    sys.modules[module_name] = module  # alias bare name so siblings resolve
    spec.loader.exec_module(module)
    return module


WIKILINK_FIXTURE = """---
title: Reciprocal Rank Fusion
related: ["[[hybrid search]]"]
tags: ["[[retrieval]]"]
---

# Reciprocal Rank Fusion

## Depends on
- [[BM25]]

## Sources
- [[Cormack 2009]]

Body mentions [[vector search]] inline.
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_extract_frontmatter_heading_and_bare_rules(tmp_path: Path) -> None:
    er = _load("edge_rules", "edge_rules.py")
    ex = _load("edge_extractor", "edge_extractor.py")
    cfg = _write(tmp_path, "graph_edges.yaml", (
        "edge_types:\n"
        "  relates_to: {rules: [{kind: frontmatter_key, key: related},"
        " {kind: frontmatter_key, key: tags}]}\n"
        "  depends_on: {rules: [{kind: body_wikilink, scope: heading,"
        " headings: [\"Depends on\"]}]}\n"
        "  cites: {rules: [{kind: body_wikilink, scope: heading, headings: [Sources]}]}\n"
        "  mentions: {rules: [{kind: concept_hook}, {kind: body_wikilink, scope: bare}]}\n"
        "tiers: {tier_1: {min_inbound: 10, min_source_types: 3},"
        " tier_2: {min_inbound: 3, min_source_types: 1}}\n"
    ))
    page = _write(tmp_path, "rrf.md", WIKILINK_FIXTURE)
    rs = er.load_rules(cfg)
    edges = ex.extract(page, ruleset=rs)
    pairs = {(e.type, e.dst) for e in edges}
    assert ("relates_to", "hybrid search") in pairs
    assert ("relates_to", "retrieval") in pairs
    assert ("depends_on", "BM25") in pairs
    assert ("cites", "Cormack 2009") in pairs
    assert ("mentions", "vector search") in pairs        # bare fallback
    # a link claimed by a heading rule is NOT also emitted as bare `mentions`
    assert ("mentions", "BM25") not in pairs
    assert all(e.src == "rrf" for e in edges)


def test_concept_hook_consumes_known(tmp_path: Path) -> None:
    er = _load("edge_rules", "edge_rules.py")
    ex = _load("edge_extractor", "edge_extractor.py")
    cfg = _write(tmp_path, "graph_edges.yaml", (
        "edge_types: {mentions: {rules: [{kind: concept_hook},"
        " {kind: body_wikilink, scope: bare}]}}\n"
        "tiers: {tier_2: {min_inbound: 3, min_source_types: 1}}\n"
    ))
    page = _write(tmp_path, "src.md", "---\ntitle: A source\n---\n\nNo wikilinks here.\n")
    rs = er.load_rules(cfg)
    edges = ex.extract(page, known={"concepts": ["RRF", "hybrid search"]}, ruleset=rs)
    assert {(e.type, e.dst) for e in edges} == {
        ("mentions", "RRF"), ("mentions", "hybrid search")
    }


def test_self_edges_are_dropped(tmp_path: Path) -> None:
    """A page that tags/links itself must not produce a src==dst edge."""
    er = _load("edge_rules", "edge_rules.py")
    ex = _load("edge_extractor", "edge_extractor.py")
    cfg = _write(tmp_path, "graph_edges.yaml", (
        "edge_types:\n"
        "  relates_to: {rules: [{kind: frontmatter_key, key: tags},"
        " {kind: frontmatter_key, key: related}]}\n"
        "  mentions: {rules: [{kind: body_wikilink, scope: bare}]}\n"
        "tiers: {tier_2: {min_inbound: 3, min_source_types: 1}}\n"
    ))
    # research.md tags itself + links itself in the body, and relates to a real other page
    page = _write(tmp_path, "research.md", (
        "---\ntitle: Research\ntags: [research]\nrelated: [\"[[methods]]\"]\n---\n\n"
        "see [[research]] and [[methods]]\n"
    ))
    rs = er.load_rules(cfg)
    edges = ex.extract(page, ruleset=rs)
    pairs = {(e.type, e.dst) for e in edges}
    assert ("relates_to", "research") not in pairs   # self-edge dropped
    assert ("mentions", "research") not in pairs      # self-edge dropped
    assert ("relates_to", "methods") in pairs         # real edge kept
    assert ("mentions", "methods") in pairs           # real edge kept
    assert all(e.src != e.dst for e in edges)
