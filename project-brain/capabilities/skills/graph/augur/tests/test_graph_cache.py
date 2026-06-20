"""Tests for graph_cache.py — typed knowledge graph (ADR-738).

Imports via importlib.util.spec_from_file_location per feedback_skill_test_convention.
"""
from __future__ import annotations

import importlib.util
import json
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


def test_cache_roundtrip_and_rebuild(tmp_path: Path, monkeypatch) -> None:
    ex = _load("edge_extractor", "edge_extractor.py")
    gc = _load("graph_cache", "graph_cache.py")
    cache_dir = tmp_path / "graph"
    monkeypatch.setattr(gc, "_cache_dir", lambda: cache_dir)

    edges = [
        ex.Edge("note-a", "RRF", "mentions"),
        ex.Edge("note-b", "RRF", "cites"),
    ]
    gc.write_edges(edges)
    loaded = gc.load_edges()
    assert {(e.src, e.dst, e.type) for e in loaded} == {
        ("note-a", "RRF", "mentions"), ("note-b", "RRF", "cites")
    }
    # edges.jsonl is plain JSONL — one record per line
    lines = (cache_dir / "edges.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["type"] in {"mentions", "cites"}

    # meta.json records the count
    meta = json.loads((cache_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["edge_count"] == 2
