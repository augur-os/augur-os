"""Tests for graph_ops.py — typed knowledge graph (ADR-738).

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


def test_index_page_extracts_writes_and_caches(tmp_path: Path, monkeypatch) -> None:
    gc = _load("graph_cache", "graph_cache.py")
    go = _load("graph_ops", "graph_ops.py")
    monkeypatch.setattr(gc, "_cache_dir", lambda: tmp_path / "graph")
    monkeypatch.setattr(go, "_edge_config_path", lambda: tmp_path / "graph_edges.yaml")
    (tmp_path / "graph_edges.yaml").write_text(
        "edge_types: {mentions: {rules: [{kind: body_wikilink, scope: bare}]}}\n"
        "tiers: {tier_2: {min_inbound: 3, min_source_types: 1}}\n",
        encoding="utf-8",
    )
    page = tmp_path / "note.md"
    page.write_text("---\ntitle: Note\n---\n\nbody links [[RRF]]\n", encoding="utf-8")

    result = go.index_page(page, source_type="memory")

    from src.lib.frontmatter_utils import parse_frontmatter

    meta, _ = parse_frontmatter(page)
    assert meta["_mentions"] == ["[[RRF]]"]                 # frontmatter written
    assert result["diff"]["added"] == ["_mentions:[[RRF]]"]
    assert any(e.dst == "RRF" for e in gc.load_edges())      # cache updated


def test_index_page_from_write_path_is_a_noop_under_pytest(tmp_path: Path) -> None:
    """The write-path hook must not touch the real cache during foreign test runs.

    pytest always sets PYTEST_CURRENT_TEST, so this guard is active here. The
    real cache is never patched by foreign suites — the guard is what stops
    ingest/knowledge tests from writing test-fixture edges into it.
    """
    go = _load("graph_ops", "graph_ops.py")
    page = tmp_path / "note.md"
    page.write_text("---\ntitle: Note\n---\n\nbody links [[RRF]]\n", encoding="utf-8")

    result = go.index_page_from_write_path(page, source_type="memory")

    assert result["ok"] and result["skipped"] == "pytest"
    # the page's frontmatter was NOT touched — no extraction ran
    assert "_mentions" not in page.read_text(encoding="utf-8")
