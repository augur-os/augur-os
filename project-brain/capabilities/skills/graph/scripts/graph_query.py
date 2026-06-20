"""Query layer over the typed knowledge graph cache (ADR-738).

Read-only. Loads edges.jsonl and filters in memory — the graph is small enough
that a linear scan is correct and fast. No query language; richer access is via
the MCP tools, never a query engine (spec Non-Goals).
"""
from __future__ import annotations

from collections import Counter
from typing import Any

import graph_cache  # sibling import
from edge_extractor import Edge


def query(
    *, edge_type: str | None = None, entity: str | None = None
) -> list[Edge]:
    """Return edges filtered by type and/or entity (entity matches src OR dst)."""
    edges = graph_cache.load_edges()
    if edge_type is not None:
        edges = [e for e in edges if e.type == edge_type]
    if entity is not None:
        edges = [e for e in edges if e.src == entity or e.dst == entity]
    return edges


def neighbors_of(entity: str) -> list[str]:
    """Return the distinct dst ids of every edge originating at `entity`."""
    return sorted({e.dst for e in graph_cache.load_edges() if e.src == entity})


def stats() -> dict[str, Any]:
    """Aggregate counts for graph-stats: totals, per-type, tier distribution, dangling."""
    edges = graph_cache.load_edges()
    entities = graph_cache.load_entities()
    all_ids = {e.src for e in edges} | {e.dst for e in edges}
    known_ids = {ent["id"] for ent in entities}
    dangling = sorted(d for d in {e.dst for e in edges} if d not in known_ids and d not in all_ids)
    return {
        "edge_count": len(edges),
        "entity_count": len(entities),
        "by_type": dict(Counter(e.type for e in edges)),
        "tier_distribution": dict(Counter(ent.get("tier", 3) for ent in entities)),
        "dangling_targets": dangling,
    }
