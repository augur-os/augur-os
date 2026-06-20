"""File-first rebuildable cache for the typed knowledge graph (ADR-738).

edges.jsonl + entities.jsonl + meta.json under get_cache_dir()/graph/. Fully
rebuildable from vault frontmatter; deleting it loses nothing. No database.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from edge_extractor import Edge  # sibling import


def _cache_dir() -> Path:
    from src.config.paths import get_cache_dir

    d = get_cache_dir() / "graph"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_edges(edges: Iterable[Edge]) -> Path:
    """Replace edges.jsonl with the given edge set and refresh meta.json."""
    edges = list(edges)
    cache = _cache_dir()
    cache.mkdir(parents=True, exist_ok=True)  # robust even when _cache_dir is patched
    edges_path = cache / "edges.jsonl"
    with edges_path.open("w", encoding="utf-8") as fh:
        for e in edges:
            fh.write(json.dumps({"src": e.src, "dst": e.dst, "type": e.type}) + "\n")
    (cache / "meta.json").write_text(
        json.dumps(
            {
                "rebuilt_at": datetime.now(timezone.utc).isoformat(),
                "edge_count": len(edges),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return edges_path


def load_edges() -> list[Edge]:
    """Load all edges from edges.jsonl (empty list if the cache is absent)."""
    edges_path = _cache_dir() / "edges.jsonl"
    if not edges_path.exists():
        return []
    out: list[Edge] = []
    for line in edges_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        out.append(Edge(rec["src"], rec["dst"], rec["type"]))
    return out


def write_entities(entities: list[dict[str, Any]]) -> Path:
    """Replace entities.jsonl with the given entity records."""
    cache = _cache_dir()
    cache.mkdir(parents=True, exist_ok=True)  # robust even when _cache_dir is patched
    entities_path = cache / "entities.jsonl"
    with entities_path.open("w", encoding="utf-8") as fh:
        for ent in entities:
            fh.write(json.dumps(ent) + "\n")
    return entities_path


def load_entities() -> list[dict[str, Any]]:
    """Load all entity records from entities.jsonl."""
    entities_path = _cache_dir() / "entities.jsonl"
    if not entities_path.exists():
        return []
    return [
        json.loads(line)
        for line in entities_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
