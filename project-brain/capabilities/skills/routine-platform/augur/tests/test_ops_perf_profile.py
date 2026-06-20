"""Tests for auto-perf-profile cleanup behavior."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

from src.lib.ops_protocol import make_test_ctx


def _load_module():
    module_name = "test_perf_profile_module"
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "perf_profile.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_fix_truncates_large_logs_and_prunes_old_manual_backups(tmp_path: Path):
    module = _load_module()
    ctx = make_test_ctx(tmp_path)
    module.IO_THRESHOLDS_MB["state/backups"] = 0.001

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    large_log = logs_dir / "dashboard.stdout.log"
    large_log.write_bytes(b"x" * (6 * 1024 * 1024))

    backup_root = tmp_path / "state" / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    now_ts = module.datetime.now(module.timezone.utc).timestamp()
    for index in range(12):
        backup_dir = backup_root / f"manual-{index:02d}"
        backup_dir.mkdir()
        (backup_dir / "snapshot.txt").write_bytes(b"backup-data\n" * 16384)
        age_days = 20 - index
        stamp = now_ts - (age_days * 86400)
        backup_dir.chmod(0o755)
        for path in (backup_dir, backup_dir / "snapshot.txt"):
            path.touch()
            os.utime(path, (stamp, stamp))

    result = module.fix(
        ctx,
        [
            {"type": "disk_bloat", "path": "logs", "size_mb": 61.0},
            {"type": "disk_bloat", "path": "state/backups", "size_mb": 5541.0},
        ],
    )

    remaining_backups = sorted(p.name for p in backup_root.iterdir())

    assert result.success is True
    assert result.fix_type == "code-fix"
    assert any(action["action"] == "truncate_logs" for action in result.actions)
    assert any(action["action"] == "prune_backups" for action in result.actions)
    assert large_log.stat().st_size <= int(module.LOG_RETENTION.keep_log_size_mb * 1024 * 1024)
    assert len(remaining_backups) == module.BACKUP_KEEP_LATEST


def test_fix_reports_without_code_fix_when_no_cleanup_applies(tmp_path: Path):
    module = _load_module()
    ctx = make_test_ctx(tmp_path)

    result = module.fix(
        ctx,
        [{"type": "disk_bloat", "path": "logs", "size_mb": 73.2}],
    )

    assert result.success is True
    assert result.fix_type == "report"
    assert result.changes == []


def test_scan_flags_inactive_dashboard_worktree_cache_bloat(monkeypatch, tmp_path: Path):
    module = _load_module()
    ctx = make_test_ctx(tmp_path, difficulty=1)
    cache_root = tmp_path / "cache"
    stale = cache_root / "dashboard-worktree-3003" / "next" / "dev" / "cache" / "turbopack"
    fresh = cache_root / "dashboard-worktree-3006" / "next" / "dev" / "cache" / "turbopack"
    locked = cache_root / "dashboard-worktree-3010" / "next" / "dev" / "cache" / "turbopack"
    stale.mkdir(parents=True)
    fresh.mkdir(parents=True)
    locked.mkdir(parents=True)
    (stale / "artifact.bin").write_bytes(b"a" * (2 * 1024 * 1024))
    (fresh / "artifact.bin").write_bytes(b"b" * 4096)
    (locked / "artifact.bin").write_bytes(b"c" * (2 * 1024 * 1024))
    lock_path = cache_root / "dashboard-worktree-3010" / "next" / "dev" / "lock"
    lock_path.write_text(json.dumps({"pid": 12345}), encoding="utf-8")
    old_stamp = time.time() - 3 * 86_400
    stale_root = cache_root / "dashboard-worktree-3003"
    for path in [*stale_root.rglob("*"), stale_root]:
        os.utime(path, (old_stamp, old_stamp))

    monkeypatch.setattr(module, "get_cache_dir", lambda: cache_root)
    monkeypatch.setattr(module, "_pid_is_running", lambda pid: pid == 12345)
    module.DASHBOARD_WORKTREE_CACHE_LIMIT_MB = 1

    result = module.scan(ctx)

    issues = [
        issue for issue in result.issues if issue.get("path") == "get_cache_dir()/dashboard-worktree-*"
    ]
    assert len(issues) == 1
    assert issues[0]["type"] == "cache_bloat"
    assert issues[0]["inactive_cache_count"] == 2


def test_scan_flags_fresh_inactive_dashboard_worktree_cache_bloat(monkeypatch, tmp_path: Path):
    module = _load_module()
    ctx = make_test_ctx(tmp_path, difficulty=1)
    cache_root = tmp_path / "cache"
    fresh = cache_root / "dashboard-worktree-3006" / "next" / "dev" / "cache" / "turbopack"
    fresh.mkdir(parents=True)
    (fresh / "artifact.bin").write_bytes(b"a" * (2 * 1024 * 1024))

    monkeypatch.setattr(module, "get_cache_dir", lambda: cache_root)
    module.DASHBOARD_WORKTREE_CACHE_LIMIT_MB = 1

    result = module.scan(ctx)

    issues = [
        issue for issue in result.issues if issue.get("path") == "get_cache_dir()/dashboard-worktree-*"
    ]
    assert len(issues) == 1
    assert issues[0]["type"] == "cache_bloat"
    assert issues[0]["stale_cache_count"] == 1


def test_fix_does_not_purge_main_next_cache_for_worktree_cache_issue(tmp_path: Path):
    module = _load_module()
    ctx = make_test_ctx(tmp_path)
    next_cache = tmp_path / "apps" / "dashboard" / ".next" / "cache"
    next_cache.mkdir(parents=True)
    marker = next_cache / "artifact.bin"
    marker.write_bytes(b"keep")

    result = module.fix(
        ctx,
        [
            {
                "type": "cache_bloat",
                "path": "get_cache_dir()/dashboard-worktree-*",
                "size_mb": 2048.0,
            }
        ],
    )

    assert result.success is True
    assert marker.exists()
    assert not any(action["action"] == "purge_cache" for action in result.actions)
