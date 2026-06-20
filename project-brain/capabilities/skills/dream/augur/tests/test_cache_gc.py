"""Tests for dream-cache-gc (ADR-744 task 9).

Filesystem GC against an allowlisted set of subdirectories under the cache
root. Spec correction baked in: this is NOT a thin delegate to the
``cache-control`` MCP tool — that tool is an in-memory skill-cache
invalidator, not a disk GC. dream-cache-gc owns its own filesystem-GC logic
and opportunistically calls the in-memory invalidator after a non-empty
purge.
"""
from __future__ import annotations

import importlib.util
import os
import time
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "cache_gc.py"
_SPEC = importlib.util.spec_from_file_location("dream_cache_gc", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _age_file(path: Path, days_old: int) -> None:
    """Backdate the file's mtime so the GC sees it as ``days_old`` days old."""
    past = time.time() - days_old * 86400
    os.utime(path, (past, past))


@pytest.fixture
def cache_tree(tmp_path: Path) -> Path:
    root = tmp_path / "cache"
    (root / "graph").mkdir(parents=True)
    (root / "graph" / "old.jsonl").write_text("x", encoding="utf-8")
    _age_file(root / "graph" / "old.jsonl", days_old=60)
    (root / "graph" / "fresh.jsonl").write_text("y", encoding="utf-8")
    # A non-allowlisted subdir that should NEVER be touched.
    (root / "user-precious").mkdir()
    (root / "user-precious" / "irreplaceable.dat").write_text("never delete me",
                                                              encoding="utf-8")
    _age_file(root / "user-precious" / "irreplaceable.dat", days_old=9999)
    return root


def test_purges_files_older_than_retention(cache_tree: Path):
    result = mod.dream_cache_gc(
        cache_root=cache_tree,
        retention_days=30,
        paths=["graph"],
    )
    assert not (cache_tree / "graph" / "old.jsonl").exists()
    assert (cache_tree / "graph" / "fresh.jsonl").exists()
    purged = result["purged"]
    assert any(str(cache_tree / "graph" / "old.jsonl") in p for p in purged)


def test_respects_allowlist_only(cache_tree: Path):
    """Files outside the allowlist subdirs must NEVER be purged, regardless of age."""
    mod.dream_cache_gc(
        cache_root=cache_tree,
        retention_days=1,
        paths=["graph"],
    )
    assert (cache_tree / "user-precious" / "irreplaceable.dat").exists()


def test_dry_run_reports_without_deleting(cache_tree: Path):
    result = mod.dream_cache_gc(
        cache_root=cache_tree,
        retention_days=30,
        paths=["graph"],
        dry_run=True,
    )
    assert (cache_tree / "graph" / "old.jsonl").exists()
    assert result["purged"]  # still reports what would be purged
    assert result.get("dry_run") is True


def test_reports_bytes_freed(cache_tree: Path):
    result = mod.dream_cache_gc(
        cache_root=cache_tree,
        retention_days=30,
        paths=["graph"],
    )
    assert result["bytes_freed"] >= 1


def test_handles_missing_subdir_gracefully(tmp_path: Path):
    """Allowlist references a subdir that doesn't exist — should not raise."""
    cache = tmp_path / "cache"
    cache.mkdir()
    result = mod.dream_cache_gc(
        cache_root=cache,
        retention_days=1,
        paths=["graph", "missing-subdir"],
    )
    assert result["purged"] == []
    assert result["bytes_freed"] == 0
