"""Tests for entity_tier.py — typed knowledge graph (ADR-738).

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


def test_tier_thresholds_at_boundaries() -> None:
    er = _load("edge_rules", "edge_rules.py")
    ex = _load("edge_extractor", "edge_extractor.py")
    et = _load("entity_tier", "entity_tier.py")
    rs = er.RuleSet(
        edge_types={},
        tiers={"tier_1": {"min_inbound": 10, "min_source_types": 3},
               "tier_2": {"min_inbound": 3, "min_source_types": 1}},
    )
    # source_types maps each src page to its type
    src_types = {f"s{i}": ("url" if i < 4 else "memory" if i < 8 else "concept")
                 for i in range(12)}
    # 10 inbound across 3 source types -> Tier 1
    edges = [ex.Edge(f"s{i}", "hot", "mentions") for i in range(10)]
    assert et.compute_tier("hot", edges, src_types, rs) == 1
    # 3 inbound, 1 source type -> Tier 2
    edges = [ex.Edge(f"s{i}", "warm", "mentions") for i in range(3)]
    assert et.compute_tier("warm", edges, src_types, rs) == 2
    # 2 inbound -> Tier 3
    edges = [ex.Edge(f"s{i}", "cold", "mentions") for i in range(2)]
    assert et.compute_tier("cold", edges, src_types, rs) == 3


def test_recompute_all_returns_tier_per_entity() -> None:
    er = _load("edge_rules", "edge_rules.py")
    ex = _load("edge_extractor", "edge_extractor.py")
    et = _load("entity_tier", "entity_tier.py")
    rs = er.RuleSet(edge_types={}, tiers={"tier_2": {"min_inbound": 3, "min_source_types": 1}})
    edges = [ex.Edge(f"s{i}", "warm", "mentions") for i in range(3)]
    src_types = {f"s{i}": "url" for i in range(3)}
    tiers = et.recompute_all(edges, src_types, rs)
    assert tiers["warm"] == 2
