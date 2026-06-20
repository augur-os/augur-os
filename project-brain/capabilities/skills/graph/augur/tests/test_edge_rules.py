"""Tests for edge_rules.py — typed knowledge graph (ADR-738).

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


def test_load_rules_parses_seed_schema(tmp_path: Path) -> None:
    er = _load("edge_rules", "edge_rules.py")
    cfg = tmp_path / "graph_edges.yaml"
    cfg.write_text(
        "edge_types:\n"
        "  cites:\n"
        "    rules:\n"
        "      - {kind: frontmatter_key, key: cited_sources}\n"
        "  mentions:\n"
        "    rules:\n"
        "      - {kind: body_wikilink, scope: bare}\n"
        "tiers:\n"
        "  tier_1: {min_inbound: 10, min_source_types: 3}\n"
        "  tier_2: {min_inbound: 3, min_source_types: 1}\n",
        encoding="utf-8",
    )
    rs = er.load_rules(cfg)
    assert set(rs.edge_types) == {"cites", "mentions"}
    assert rs.tiers["tier_1"]["min_inbound"] == 10
    fk = rs.rules_for_kind("frontmatter_key")
    assert ("cites", {"kind": "frontmatter_key", "key": "cited_sources"}) in fk


def test_malformed_config_fails_closed(tmp_path: Path) -> None:
    er = _load("edge_rules", "edge_rules.py")
    cfg = tmp_path / "broken.yaml"
    cfg.write_text("edge_types: [this is not a mapping", encoding="utf-8")
    rs = er.load_rules(cfg)  # must not raise
    # fail-closed: a minimal ruleset with only the bare-wikilink mentions rule
    assert set(rs.edge_types) == {"mentions"}
    assert rs.rules_for_kind("body_wikilink") == [
        ("mentions", {"kind": "body_wikilink", "scope": "bare"})
    ]
