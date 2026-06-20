"""Tests for src/lib/index/incremental.py — incremental RAG sync engine."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

from src.lib.index.incremental import sync_categories
from src.lib.index.sync_lock import SyncLockHeld

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def fixture_env(tmp_path, monkeypatch):
    """Tiny vault + empty rag dir, with the lock path monkeypatched."""
    vault = tmp_path / "vault"
    (vault / "notes").mkdir(parents=True)
    (vault / "notes" / "alpha.md").write_text("---\ntitle: Alpha\n---\n\n# Alpha\n\nFirst note about espresso.\n")
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()
    lock_path = tmp_path / "rag_sync.lock"
    monkeypatch.setattr("src.lib.index.incremental._lock_path", lambda: lock_path)
    return {"vault": vault, "rag_dir": rag_dir, "lock": lock_path, "root": PROJECT_ROOT}


def test_vault_sync_matches_direct_category_rebuild(fixture_env, tmp_path):
    env = fixture_env
    # Use an empty shared_vault_dir so neither side scans the real project-brain,
    # keeping the test fast and hermetic (both sides get the same sentinel).
    empty_shared = tmp_path / "empty_shared"
    empty_shared.mkdir()

    stats = sync_categories(
        {"vault"},
        project_root=env["root"],
        rag_dir=env["rag_dir"],
        vault_dir=env["vault"],
        shared_vault_dir=empty_shared,
    )
    assert stats["vault"] >= 1
    incremental_tree = sorted(p.relative_to(env["rag_dir"]) for p in (env["rag_dir"] / "vault").rglob("*.md"))

    from src.lib.index.unified_indexer import reindex_category

    ref_rag = tmp_path / "rag_ref"
    ref_rag.mkdir()
    reindex_category(
        "vault",
        env["root"],
        ref_rag,
        vault_dir=env["vault"],
        shared_vault_dir=empty_shared,
    )
    reference_tree = sorted(p.relative_to(ref_rag) for p in (ref_rag / "vault").rglob("*.md"))
    assert incremental_tree == reference_tree


def test_manifest_patched_for_synced_category_only(fixture_env, tmp_path):
    env = fixture_env
    meta = env["rag_dir"] / "_meta"
    meta.mkdir()
    (meta / "manifest.yaml").write_text(
        yaml.dump(
            {
                "version": "2.0",
                "indexed_at": "2020-01-01T00:00:00+00:00",
                "root": str(env["rag_dir"]),
                "stats": {"adrs": 7},
                "total": 7,
                "entries": [
                    {"name": "old-adr", "category": "adrs", "hub": "", "path": "adrs/x.md", "description": "kept"},
                ],
            }
        )
    )

    empty_shared = tmp_path / "empty_shared"
    empty_shared.mkdir()

    sync_categories(
        {"vault"},
        project_root=env["root"],
        rag_dir=env["rag_dir"],
        vault_dir=env["vault"],
        shared_vault_dir=empty_shared,
    )
    manifest = yaml.safe_load((meta / "manifest.yaml").read_text())
    assert manifest["stats"]["adrs"] == 7  # untouched
    assert manifest["stats"]["vault"] >= 1  # patched
    assert manifest["indexed_at"] > "2020-01-01"
    cats = {e["category"] for e in manifest["entries"]}
    assert "adrs" in cats and "vault" in cats
    checksum = yaml.safe_load((meta / "checksums" / "vault.yaml").read_text())
    assert checksum["category"] == "vault"


def test_deleted_source_file_disappears_from_index(fixture_env, tmp_path):
    env = fixture_env
    empty_shared = tmp_path / "empty_shared"
    empty_shared.mkdir()

    sync_categories(
        {"vault"},
        project_root=env["root"],
        rag_dir=env["rag_dir"],
        vault_dir=env["vault"],
        shared_vault_dir=empty_shared,
    )
    before = list((env["rag_dir"] / "vault").rglob("*alpha*"))
    assert before
    (env["vault"] / "notes" / "alpha.md").unlink()
    sync_categories(
        {"vault"},
        project_root=env["root"],
        rag_dir=env["rag_dir"],
        vault_dir=env["vault"],
        shared_vault_dir=empty_shared,
    )
    assert not list((env["rag_dir"] / "vault").rglob("*alpha*"))


def test_sync_raises_when_lock_held(fixture_env):
    env = fixture_env
    # A live holder (our own pid counts — the lock is non-reentrant).
    env["lock"].write_text(json.dumps({"pid": os.getpid(), "acquired_at": "now"}))
    with pytest.raises(SyncLockHeld):
        sync_categories({"vault"}, project_root=env["root"], rag_dir=env["rag_dir"], vault_dir=env["vault"])
    env["lock"].unlink()
