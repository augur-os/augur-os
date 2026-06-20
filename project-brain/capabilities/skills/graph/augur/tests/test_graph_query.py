"""Tests for graph_query.py — typed knowledge graph (ADR-738).

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


def test_query_by_type_entity_and_neighbors(tmp_path: Path, monkeypatch) -> None:
    ex = _load("edge_extractor", "edge_extractor.py")
    gc = _load("graph_cache", "graph_cache.py")
    gq = _load("graph_query", "graph_query.py")
    monkeypatch.setattr(gc, "_cache_dir", lambda: tmp_path / "graph")
    gc.write_edges([
        ex.Edge("note-a", "RRF", "mentions"),
        ex.Edge("note-a", "BM25", "depends_on"),
        ex.Edge("note-b", "RRF", "cites"),
    ])
    assert {e.src for e in gq.query(edge_type="cites")} == {"note-b"}
    # everything touching RRF (as src or dst)
    touching = gq.query(entity="RRF")
    assert {(e.src, e.type) for e in touching} == {("note-a", "mentions"), ("note-b", "cites")}
    # neighbors_of returns the dst ids reachable from a src
    assert set(gq.neighbors_of("note-a")) == {"RRF", "BM25"}
