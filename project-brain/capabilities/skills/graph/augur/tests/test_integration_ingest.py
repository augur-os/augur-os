"""Integration test: /ingest write path calls graph_ops.index_page (ADR-738).

Imports via importlib.util.spec_from_file_location per feedback_skill_test_convention.
Pins the contract the source_cards.py / url_ingest.py call sites invoke.
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


def test_ingest_helper_indexes_source_card(tmp_path: Path, monkeypatch) -> None:
    gc = _load("graph_cache", "graph_cache.py")
    go = _load("graph_ops", "graph_ops.py")
    monkeypatch.setattr(gc, "_cache_dir", lambda: tmp_path / "graph")
    monkeypatch.setattr(go, "_edge_config_path", lambda: tmp_path / "graph_edges.yaml")
    (tmp_path / "graph_edges.yaml").write_text(
        "edge_types: {mentions: {rules: [{kind: concept_hook},"
        " {kind: body_wikilink, scope: bare}]}}\n"
        "tiers: {tier_2: {min_inbound: 3, min_source_types: 1}}\n",
        encoding="utf-8",
    )
    card = tmp_path / "card.md"
    card.write_text("---\ntitle: A source\n---\n\nsummary\n", encoding="utf-8")
    # this is exactly the call source_cards.py / url_ingest.py make:
    result = go.index_page(card, source_type="url", known={"concepts": ["RRF", "BM25"]})
    assert result["ok"] and result["edges"] == 2
    assert {e.dst for e in gc.load_edges()} == {"RRF", "BM25"}
