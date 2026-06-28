"""Unit tests for src.lib.ingest.wiki_status_read.

Exercises the pure / deterministic helpers that derive wiki status from
persisted runtime state and on-disk wiki pages. All filesystem access is
isolated to tmp_path; the real vault/runtime is never touched.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.lib.ingest.wiki_status_read import (
    _batch_status,
    _compiler_from_state,
    _compounding_health_from_wiki_dir,
    _concept_page_records,
    _coverage_from_state,
    _index_status,
    _load_compiler_state_raw,
    _recommended_actions,
    _structure_from_wiki_dir,
)

# ── _load_compiler_state_raw ──────────────────────────────────────────────────


def test_load_compiler_state_raw_missing_file_returns_empty(tmp_path: Path) -> None:
    assert _load_compiler_state_raw(tmp_path) == {}


def test_load_compiler_state_raw_reads_valid_json(tmp_path: Path) -> None:
    payload = {"compiler_version": "v3", "sources": {"a": {"concept_slugs": ["x"]}}}
    (tmp_path / "concept-compiler-state.json").write_text(json.dumps(payload), encoding="utf-8")
    assert _load_compiler_state_raw(tmp_path) == payload


def test_load_compiler_state_raw_invalid_json_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "concept-compiler-state.json").write_text("{not json", encoding="utf-8")
    assert _load_compiler_state_raw(tmp_path) == {}


# ── _compiler_from_state ──────────────────────────────────────────────────────


def test_compiler_from_state_counts_concept_and_bare_sources() -> None:
    raw = {
        "compiler_version": "v9",
        "sources": {
            "s1": {"concept_slugs": ["alpha", "beta"]},
            "s2": {"concept_slugs": []},
            "s3": {},
            "s4": "not-a-dict",
        },
    }
    compiler = _compiler_from_state(raw)
    assert compiler["compiler_version"] == "v9"
    assert compiler["sources_in_state"] == 4
    assert compiler["sources_total"] == 4
    assert compiler["sources_compiled_with_concepts"] == 1
    # Only dict-valued sources without concepts count (s2, s3); the
    # non-dict s4 entry is skipped entirely.
    assert compiler["sources_processed_no_concepts"] == 2
    # Fields that need a live source scan are zeroed out.
    assert compiler["sources_pending_or_changed"] == 0
    assert compiler["current"] is None


def test_compiler_from_state_empty_state() -> None:
    compiler = _compiler_from_state({})
    assert compiler["sources_in_state"] == 0
    assert compiler["sources_compiled_with_concepts"] == 0
    assert compiler["compiler_version"] == ""


# ── _coverage_from_state ──────────────────────────────────────────────────────


def test_coverage_ratio_computed_from_sources() -> None:
    raw = {
        "sources": {
            "a": {"concept_slugs": ["x"]},
            "b": {"concept_slugs": ["y"]},
            "c": {"concept_slugs": []},
            "d": {},
        }
    }
    coverage = _coverage_from_state(raw)
    # 2 of 4 sources have concepts -> 0.5
    assert coverage["concept_coverage_ratio"] == 0.5
    assert coverage["top_uncovered_source_families"] == []


def test_coverage_no_sources_returns_full_ratio() -> None:
    # No sources at all -> treated as fully covered (1.0).
    assert _coverage_from_state({"sources": {}})["concept_coverage_ratio"] == 1.0


def test_coverage_non_dict_sources_returns_zero() -> None:
    coverage = _coverage_from_state({"sources": ["bad"]})
    assert coverage["concept_coverage_ratio"] == 0.0


# ── _structure_from_wiki_dir ──────────────────────────────────────────────────


def test_structure_none_dir_not_ok() -> None:
    structure = _structure_from_wiki_dir(None)
    assert structure == {"ok": False, "pages": 0, "missing_links": [], "orphan_pages": []}


def test_structure_counts_markdown_recursively(tmp_path: Path) -> None:
    (tmp_path / "concepts").mkdir()
    (tmp_path / "a.md").write_text("x", encoding="utf-8")
    (tmp_path / "concepts" / "b.md").write_text("y", encoding="utf-8")
    (tmp_path / "ignore.txt").write_text("z", encoding="utf-8")
    structure = _structure_from_wiki_dir(tmp_path)
    assert structure["pages"] == 2
    assert structure["ok"] is True


# ── _concept_page_records + _compounding_health_from_wiki_dir ──────────────────


def _write_concept_page(concepts_dir: Path, name: str, sources: list[str]) -> None:
    src_block = "\n".join(f"  - {s}" for s in sources)
    body = f"---\npage_type: concept\nsources:\n{src_block}\n---\nbody text\n"
    (concepts_dir / name).write_text(body, encoding="utf-8")


def test_concept_page_records_dedups_sources_and_skips_non_concept(tmp_path: Path) -> None:
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    # Duplicate source slug should count once.
    _write_concept_page(concepts, "alpha.md", ["s1", "s1", "s2"])
    # Non-concept page is ignored.
    (concepts / "note.md").write_text("---\npage_type: note\n---\nbody\n", encoding="utf-8")
    records = _concept_page_records(tmp_path)
    assert len(records) == 1
    assert records[0]["page"] == "concepts/alpha.md"
    assert records[0]["source_count"] == 2


def test_concept_page_records_no_concepts_dir(tmp_path: Path) -> None:
    assert _concept_page_records(tmp_path) == []


def test_compounding_health_flags_thin_pages(tmp_path: Path) -> None:
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    # Thin page: below MIN_COMPOUND_SOURCE_COUNT (8).
    _write_concept_page(concepts, "thin.md", ["s1", "s2"])
    # Healthy page: 10 sources.
    _write_concept_page(concepts, "rich.md", [f"r{i}" for i in range(10)])
    health = _compounding_health_from_wiki_dir(tmp_path, structure={})
    assert health["concept_page_count"] == 2
    assert health["thin_page_count"] == 1
    assert health["average_sources_per_concept_page"] == 6.0  # (2 + 10) / 2
    assert health["target_sources_per_page"] == "10-15"


def test_compounding_health_none_dir() -> None:
    health = _compounding_health_from_wiki_dir(None, structure={})
    assert health["concept_page_count"] == 0
    assert health["average_sources_per_concept_page"] == 0.0
    assert health["thin_page_count"] == 0


# ── _batch_status ─────────────────────────────────────────────────────────────


def test_batch_status_no_dir(tmp_path: Path) -> None:
    status = _batch_status(tmp_path)
    assert status["batch_count"] == 0
    assert status["last_batch"] is None
    assert status["needs_update"] is False


def test_batch_status_reads_latest_batch_and_flag(tmp_path: Path) -> None:
    batch_dir = tmp_path / "concept-batches"
    batch_dir.mkdir()
    older = batch_dir / "batch-001.json"
    newer = batch_dir / "batch-002.json"
    older.write_text(json.dumps({"created": "2026-01-01", "mode": "full"}), encoding="utf-8")
    newer.write_text(json.dumps({"created": "2026-06-24", "mode": "incremental"}), encoding="utf-8")
    # Ensure 'newer' has a strictly later mtime so max() is deterministic.
    import os

    os.utime(older, (1_000_000, 1_000_000))
    os.utime(newer, (2_000_000, 2_000_000))
    (tmp_path / "needs-update.flag").write_text("", encoding="utf-8")

    status = _batch_status(tmp_path)
    assert status["batch_count"] == 2
    assert status["last_batch_handle"] == "batch-002"
    assert status["last_batch_created"] == "2026-06-24"
    assert status["last_batch_mode"] == "incremental"
    assert status["needs_update"] is True
    assert status["needs_update_flag"] is not None


# ── _index_status ─────────────────────────────────────────────────────────────


def test_index_status_missing_dir(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    status = _index_status(missing)
    assert status["indexed"] is False
    assert status["wiki_rag_entries"] == 0


def test_index_status_counts_entries(tmp_path: Path) -> None:
    (tmp_path / "one.md").write_text("a", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "two.md").write_text("b", encoding="utf-8")
    status = _index_status(tmp_path)
    assert status["indexed"] is True
    assert status["wiki_rag_entries"] == 2


# ── _recommended_actions ──────────────────────────────────────────────────────


def test_recommended_actions_pending_sources_high_priority() -> None:
    actions = _recommended_actions(
        structure={"pages": 0},
        compiler={"sources_pending_or_changed": 3},
        batches={"needs_update": False},
        coverage={"concept_coverage_ratio": 0.5},
        index={"indexed": True, "wiki_rag_entries": 5},
        compounding_health={},
    )
    assert any(a["id"] == "prepare-incremental-batch" and a["priority"] == "high" for a in actions)
    reason = next(a["reason"] for a in actions if a["id"] == "prepare-incremental-batch")
    assert "3 pending" in reason


def test_recommended_actions_needs_update_flag_when_no_pending() -> None:
    actions = _recommended_actions(
        structure={"pages": 0},
        compiler={"sources_pending_or_changed": 0},
        batches={"needs_update": True},
        coverage={"concept_coverage_ratio": 0.5},
        index={"indexed": True, "wiki_rag_entries": 5},
        compounding_health={},
    )
    assert [a["id"] for a in actions] == ["prepare-incremental-batch"]
    assert "needs-update.flag" in actions[0]["reason"]


def test_recommended_actions_unindexed_pages_trigger_reindex() -> None:
    actions = _recommended_actions(
        structure={"pages": 12},
        compiler={"sources_pending_or_changed": 0},
        batches={"needs_update": False},
        coverage={"concept_coverage_ratio": 0.5},
        index={"indexed": False, "wiki_rag_entries": 0},
        compounding_health={},
    )
    assert any(a["id"] == "refresh-wiki-index" for a in actions)


def test_recommended_actions_zero_coverage_triggers_rebuild() -> None:
    actions = _recommended_actions(
        structure={"pages": 0},
        compiler={"sources_pending_or_changed": 0},
        batches={"needs_update": False},
        coverage={"concept_coverage_ratio": 0.0},
        index={"indexed": True, "wiki_rag_entries": 1},
        compounding_health={},
    )
    assert [a["id"] for a in actions] == ["rebuild-concepts"]


def test_recommended_actions_healthy_state_no_actions() -> None:
    actions = _recommended_actions(
        structure={"pages": 10},
        compiler={"sources_pending_or_changed": 0},
        batches={"needs_update": False},
        coverage={"concept_coverage_ratio": 0.9},
        index={"indexed": True, "wiki_rag_entries": 10},
        compounding_health={},
    )
    assert actions == []
