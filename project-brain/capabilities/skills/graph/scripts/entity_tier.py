"""Deterministic entity tiering for the typed knowledge graph (ADR-738).

_entity_tier in {1, 2, 3}, computed from inbound-edge count and the diversity of
source-page types. Named distinctly from wiki_tier.py's signal-source tiers.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from edge_extractor import Edge  # sibling import
from edge_rules import RuleSet


def _inbound(entity: str, edges: Iterable[Edge], src_types: dict[str, str]) -> tuple[int, int]:
    """Return (inbound_count, distinct_source_type_count) for one entity."""
    srcs = {e.src for e in edges if e.dst == entity}
    types = {src_types.get(s, "unknown") for s in srcs}
    return len(srcs), len(types)


def compute_tier(
    entity: str, edges: Iterable[Edge], src_types: dict[str, str], ruleset: RuleSet
) -> int:
    """Compute the 1-3 tier for one entity. Higher tier number = less connected."""
    edges = list(edges)
    count, type_count = _inbound(entity, edges, src_types)
    t1 = ruleset.tiers.get("tier_1", {})
    t2 = ruleset.tiers.get("tier_2", {})
    if t1 and count >= t1.get("min_inbound", 10) and type_count >= t1.get("min_source_types", 3):
        return 1
    if t2 and count >= t2.get("min_inbound", 3) and type_count >= t2.get("min_source_types", 1):
        return 2
    return 3


def recompute_all(
    edges: Iterable[Edge], src_types: dict[str, str], ruleset: RuleSet
) -> dict[str, int]:
    """Compute tiers for every entity that appears as an edge destination."""
    edges = list(edges)
    by_dst: dict[str, list[Edge]] = defaultdict(list)
    for e in edges:
        by_dst[e.dst].append(e)
    return {
        entity: compute_tier(entity, by_dst[entity], src_types, ruleset)
        for entity in by_dst
    }
