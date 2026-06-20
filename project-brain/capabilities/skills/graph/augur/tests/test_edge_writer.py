"""Tests for edge_writer.py — typed knowledge graph (ADR-738).

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


def test_merge_is_additive_and_preserves_user_edges(tmp_path: Path) -> None:
    ex = _load("edge_extractor", "edge_extractor.py")
    ew = _load("edge_writer", "edge_writer.py")
    page = tmp_path / "note.md"
    # user has already hand-added a _depends_on edge via Obsidian's Properties panel
    page.write_text(
        '---\ntitle: Note\n_depends_on: ["[[hand-added]]"]\n---\n\nbody\n',
        encoding="utf-8",
    )
    edges = [ex.Edge("note", "RRF", "mentions"), ex.Edge("note", "BM25", "mentions")]
    diff = ew.merge(page, edges)

    from src.lib.frontmatter_utils import parse_frontmatter

    meta, _ = parse_frontmatter(page)
    assert sorted(meta["_mentions"]) == ["[[BM25]]", "[[RRF]]"]
    assert meta["_depends_on"] == ["[[hand-added]]"]      # user edge preserved
    assert meta["title"] == "Note"                        # user key untouched
    assert set(diff["added"]) == {"_mentions:[[RRF]]", "_mentions:[[BM25]]"}

    # second run is idempotent — nothing added
    diff2 = ew.merge(page, edges)
    assert diff2["added"] == []


def test_merge_preserves_system_metadata_that_is_not_edge_type(tmp_path: Path) -> None:
    ex = _load("edge_extractor", "edge_extractor.py")
    ew = _load("edge_writer", "edge_writer.py")
    page = tmp_path / "source-card.md"
    page.write_text(
        "---\n"
        "title: Source Card\n"
        "_source_type: inbox-file\n"
        "_confidence: high\n"
        "---\n\n"
        "body\n",
        encoding="utf-8",
    )
    edges = [ex.Edge("source-card", "inbox", "relates_to")]

    ew.merge(page, edges)

    from src.lib.frontmatter_utils import parse_frontmatter

    meta, _ = parse_frontmatter(page)
    assert meta["_source_type"] == "inbox-file"
    assert meta["_confidence"] == "high"
    assert meta["_relates_to"] == ["[[inbox]]"]
    raw = page.read_text(encoding="utf-8")
    assert "\nsource_type:" not in raw
    assert "\nconfidence:" not in raw


def test_prune_removes_unmatched_but_diffs_first(tmp_path: Path) -> None:
    ex = _load("edge_extractor", "edge_extractor.py")
    ew = _load("edge_writer", "edge_writer.py")
    page = tmp_path / "note.md"
    page.write_text(
        '---\ntitle: Note\n_mentions: ["[[stale]]", "[[RRF]]"]\n---\n\nbody\n',
        encoding="utf-8",
    )
    edges = [ex.Edge("note", "RRF", "mentions")]
    diff = ew.merge(page, edges, prune=True)

    from src.lib.frontmatter_utils import parse_frontmatter

    meta, _ = parse_frontmatter(page)
    assert meta["_mentions"] == ["[[RRF]]"]
    assert diff["removed"] == ["_mentions:[[stale]]"]


def test_merge_with_no_edge_changes_leaves_plain_page_untouched(tmp_path: Path) -> None:
    ew = _load("edge_writer", "edge_writer.py")
    page = tmp_path / "plain.md"
    original = "# Plain\n\nNo graph links here.\n"
    page.write_text(original, encoding="utf-8")

    diff = ew.merge(page, [])

    assert diff == {"added": [], "removed": [], "unchanged": []}
    assert page.read_text(encoding="utf-8") == original
