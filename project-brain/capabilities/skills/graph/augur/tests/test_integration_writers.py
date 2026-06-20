"""Integration test: /wiki, /ask, /save, /profile write paths (ADR-738).

Imports via importlib.util.spec_from_file_location per feedback_skill_test_convention.
Pins the graph_ops.index_page contract every wired write path invokes.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

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


@pytest.mark.parametrize("source_type", ["concept", "memory", "profile"])
def test_index_page_contract_for_each_writer(tmp_path: Path, monkeypatch, source_type: str) -> None:
    gc = _load("graph_cache", "graph_cache.py")
    go = _load("graph_ops", "graph_ops.py")
    monkeypatch.setattr(gc, "_cache_dir", lambda: tmp_path / source_type)
    monkeypatch.setattr(go, "_edge_config_path", lambda: tmp_path / "graph_edges.yaml")
    (tmp_path / "graph_edges.yaml").write_text(
        "edge_types: {mentions: {rules: [{kind: body_wikilink, scope: bare}]}}\n"
        "tiers: {tier_2: {min_inbound: 3, min_source_types: 1}}\n",
        encoding="utf-8",
    )
    page = tmp_path / f"{source_type}.md"
    page.write_text(f"---\ntitle: {source_type}\n---\n\nlinks [[Target]]\n", encoding="utf-8")
    result = go.index_page(page, source_type=source_type)
    assert result["ok"]
    assert any(e.dst == "Target" for e in gc.load_edges())
