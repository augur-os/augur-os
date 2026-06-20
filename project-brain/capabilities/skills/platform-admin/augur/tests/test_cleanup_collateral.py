"""Tests for cleanup_collateral.py — file age, directory cleanup, log truncation."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Import helpers — patch heavy imports at module scope
# ---------------------------------------------------------------------------


@pytest.fixture()
def cc(monkeypatch):
    """Import cleanup_collateral with env-based project root."""
    import importlib
    import sys

    scripts_dir = Path(__file__).resolve().parent.parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    # Ensure the module can be imported (it uses src.config.paths at module level)
    mod = importlib.import_module("skills.platform-admin.scripts.cleanup_collateral")
    return mod


# ---------------------------------------------------------------------------
# get_file_age_days
# ---------------------------------------------------------------------------


class TestGetFileAgeDays:
    def test_recent_file_is_young(self, cc, tmp_path):
        f = tmp_path / "recent.txt"
        f.write_text("hello")
        age = cc.get_file_age_days(f)
        assert age < 1

    def test_old_file_has_positive_age(self, cc, tmp_path):
        f = tmp_path / "old.txt"
        f.write_text("hello")
        # Set mtime to 10 days ago
        old_time = time.time() - 10 * 86400
        os.utime(f, (old_time, old_time))
        age = cc.get_file_age_days(f)
        assert age >= 9.5


# ---------------------------------------------------------------------------
# cleanup_directory
# ---------------------------------------------------------------------------


class TestCleanupDirectory:
    def test_nonexistent_directory_returns_empty_stats(self, cc, tmp_path):
        stats = cc.cleanup_directory(tmp_path / "nope", days=7)
        assert stats["deleted"] == 0

    def test_dry_run_does_not_delete(self, cc, tmp_path):
        f = tmp_path / "old.log"
        f.write_text("data")
        old_time = time.time() - 30 * 86400
        os.utime(f, (old_time, old_time))

        stats = cc.cleanup_directory(tmp_path, days=7, dry_run=True)
        assert stats["deleted"] == 1
        assert f.exists()  # Not actually deleted

    def test_live_run_deletes_old_files(self, cc, tmp_path):
        old = tmp_path / "old.log"
        old.write_text("old data")
        old_time = time.time() - 30 * 86400
        os.utime(old, (old_time, old_time))

        recent = tmp_path / "recent.log"
        recent.write_text("recent data")

        stats = cc.cleanup_directory(tmp_path, days=7, dry_run=False)
        assert stats["deleted"] == 1
        assert not old.exists()
        assert recent.exists()


# ---------------------------------------------------------------------------
# truncate_logs
# ---------------------------------------------------------------------------


class TestTruncateLogs:
    def test_small_log_not_truncated(self, cc, tmp_path):
        log = tmp_path / "small.log"
        log.write_text("small content")
        stats = cc.truncate_logs(tmp_path, dry_run=True)
        assert stats["truncated"] == 0

    def test_large_log_flagged_in_dry_run(self, cc, tmp_path):
        log = tmp_path / "big.log"
        # Write content bigger than MAX_LOG_SIZE_MB
        log.write_bytes(b"x" * (int(cc.MAX_LOG_SIZE_MB * 1024 * 1024) + 1024))
        stats = cc.truncate_logs(tmp_path, dry_run=True)
        assert stats["truncated"] == 1
        # File still has original size in dry run
        assert log.stat().st_size > cc.MAX_LOG_SIZE_MB * 1024 * 1024


# ---------------------------------------------------------------------------
# deep_clean_caches
# ---------------------------------------------------------------------------


class TestDeepCleanCaches:
    def test_removes_pycache_in_dry_run(self, cc, tmp_path):
        cache_dir = tmp_path / "project" / "__pycache__"
        cache_dir.mkdir(parents=True)
        (cache_dir / "mod.pyc").write_bytes(b"\x00" * 100)

        stats = cc.deep_clean_caches(tmp_path / "project", dry_run=True)
        assert stats["deleted_dirs"] >= 1
        assert cache_dir.exists()  # dry run doesn't delete

    def test_removes_dsstore(self, cc, tmp_path):
        ds = tmp_path / "subdir" / ".DS_Store"
        ds.parent.mkdir(parents=True)
        ds.write_text("")

        stats = cc.deep_clean_caches(tmp_path, dry_run=False)
        assert stats["deleted_files"] >= 1
        assert not ds.exists()
