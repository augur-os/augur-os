"""Tests for graph_rebuild.py — typed knowledge graph (ADR-738).

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


def test_rebuild_is_idempotent_and_dry_run_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    gc = _load("graph_cache", "graph_cache.py")
    go = _load("graph_ops", "graph_ops.py")
    gr = _load("graph_rebuild", "graph_rebuild.py")
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    (vault / "wiki" / "a.md").write_text("---\ntitle: A\n---\nlinks [[B]]\n", encoding="utf-8")
    monkeypatch.setattr(gc, "_cache_dir", lambda: tmp_path / "graph")
    monkeypatch.setattr(go, "_edge_config_path", lambda: tmp_path / "graph_edges.yaml")
    monkeypatch.setattr(gr, "_vault_dir", lambda: vault)
    (tmp_path / "graph_edges.yaml").write_text(
        "edge_types: {mentions: {rules: [{kind: body_wikilink, scope: bare}]}}\n"
        "tiers: {tier_2: {min_inbound: 3, min_source_types: 1}}\n",
        encoding="utf-8",
    )

    dry = gr.rebuild(dry_run=True)
    assert dry["pages_scanned"] == 1
    assert not (tmp_path / "graph" / "edges.jsonl").exists()   # dry run wrote nothing

    real = gr.rebuild()
    assert real["pages_scanned"] == 1
    assert real["edges_total"] == 1
    real2 = gr.rebuild()                                      # idempotent
    assert real2["edges_total"] == 1


def test_rebuild_writes_entity_tiers_to_entity_frontmatter(
    tmp_path: Path, monkeypatch
) -> None:
    gc = _load("graph_cache", "graph_cache.py")
    go = _load("graph_ops", "graph_ops.py")
    gr = _load("graph_rebuild", "graph_rebuild.py")
    vault = tmp_path / "vault"
    (vault / "sources" / "files").mkdir(parents=True)
    (vault / "memory" / "entries").mkdir(parents=True)
    (vault / "wiki" / "concepts").mkdir(parents=True)
    (vault / "sources" / "files" / "source-a.md").write_text(
        "---\ntitle: Source A\n---\nlinks [[Hub]]\n",
        encoding="utf-8",
    )
    (vault / "memory" / "entries" / "source-b.md").write_text(
        "---\ntitle: Source B\n---\nlinks [[Hub]]\n",
        encoding="utf-8",
    )
    (vault / "wiki" / "concepts" / "source-c.md").write_text(
        "---\ntitle: Source C\n---\nlinks [[Hub]]\n",
        encoding="utf-8",
    )
    entity = vault / "wiki" / "concepts" / "Hub.md"
    entity.write_text("---\ntitle: Hub\n---\nentity page\n", encoding="utf-8")
    monkeypatch.setattr(gc, "_cache_dir", lambda: tmp_path / "graph")
    monkeypatch.setattr(go, "_edge_config_path", lambda: tmp_path / "graph_edges.yaml")
    monkeypatch.setattr(gr, "_vault_dir", lambda: vault)
    (tmp_path / "graph_edges.yaml").write_text(
        "edge_types: {mentions: {rules: [{kind: body_wikilink, scope: bare}]}}\n"
        "tiers:\n"
        "  tier_1: {min_inbound: 3, min_source_types: 3}\n"
        "  tier_2: {min_inbound: 2, min_source_types: 1}\n",
        encoding="utf-8",
    )

    dry = gr.rebuild(dry_run=True)

    from src.lib.frontmatter_utils import parse_frontmatter

    meta, _ = parse_frontmatter(entity)
    assert dry["entity_tiers_written"] == 0
    assert "_entity_tier" not in meta

    real = gr.rebuild()

    meta, _ = parse_frontmatter(entity)
    assert real["entity_tiers_written"] == 1
    assert meta["_entity_tier"] == 1
