"""Tests for dev_clean inactive dashboard worktree cache cleanup."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEV_CLEAN_SCRIPTS = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "platform-admin" / "scripts"
if str(DEV_CLEAN_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DEV_CLEAN_SCRIPTS))

import dev_clean  # noqa: E402


def _touch_tree(path: Path, *, age_days: int, payload: bytes = b"x" * 128) -> None:
    path.mkdir(parents=True)
    artifact = path / "next" / "dev" / "cache" / "turbopack" / "artifact.bin"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(payload)
    stamp = time.time() - age_days * 86_400
    for item in sorted(path.rglob("*"), reverse=True):
        os.utime(item, (stamp, stamp))
    os.utime(path, (stamp, stamp))


def test_dashboard_worktree_cache_dry_run_counts_inactive_caches(monkeypatch, tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    stale = cache_root / "dashboard-worktree-3003"
    fresh = cache_root / "dashboard-worktree-3006"
    locked = cache_root / "dashboard-worktree-3010"
    main_dashboard = cache_root / "dashboard"
    _touch_tree(stale, age_days=5, payload=b"a" * 128)
    _touch_tree(fresh, age_days=0, payload=b"b" * 512)
    _touch_tree(locked, age_days=6, payload=b"c" * 1024)
    _touch_tree(main_dashboard, age_days=8, payload=b"d" * 2048)
    lock_path = locked / "next" / "dev" / "lock"
    lock_path.write_text(json.dumps({"pid": 12345}), encoding="utf-8")

    monkeypatch.setattr(dev_clean, "get_cache_dir", lambda: cache_root)
    monkeypatch.setattr(dev_clean, "_pid_is_running", lambda pid: pid == 12345)

    result = dev_clean.op_stale_dashboard_worktree_caches(dry_run=True)

    assert result.name == "stale-dashboard-worktree-caches"
    assert result.targets_touched == 2
    assert result.bytes_reclaimed == 640
    assert result.files_reclaimed == 2
    assert stale.exists()
    assert fresh.exists()
    assert locked.exists()
    assert main_dashboard.exists()
    assert any("active lock" in note for note in result.notes)


def test_dashboard_worktree_cache_execute_removes_only_inactive_caches(monkeypatch, tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    stale = cache_root / "dashboard-worktree-3003"
    fresh = cache_root / "dashboard-worktree-3006"
    locked = cache_root / "dashboard-worktree-3010"
    _touch_tree(stale, age_days=5)
    _touch_tree(fresh, age_days=0)
    _touch_tree(locked, age_days=5)
    lock_path = locked / "next" / "dev" / "lock"
    lock_path.write_text(json.dumps({"pid": 12345}), encoding="utf-8")

    monkeypatch.setattr(dev_clean, "get_cache_dir", lambda: cache_root)
    monkeypatch.setattr(dev_clean, "_pid_is_running", lambda pid: pid == 12345)

    result = dev_clean.op_stale_dashboard_worktree_caches(dry_run=False)

    assert result.targets_touched == 2
    assert result.files_reclaimed == 2
    assert not stale.exists()
    assert not fresh.exists()
    assert locked.exists()


def test_build_operations_includes_stale_dashboard_worktree_cache_cleanup() -> None:
    operation_names = {operation.name for operation in dev_clean.build_operations(include_git=False)}

    assert "stale-dashboard-worktree-caches" in operation_names
