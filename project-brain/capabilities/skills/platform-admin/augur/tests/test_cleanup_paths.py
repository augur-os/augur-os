"""Tests for cleanup_paths.py — path validation utilities and cleanup report."""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cleanup_paths import (
    CleanupReport,
    PlacementIssue,
    SizeAlert,
    WrongPlacement,
    calculate_directory_size,
    clean_stale_runtime,
    is_script_file,
    is_user_data_file,
)


# ---------------------------------------------------------------------------
# CleanupReport
# ---------------------------------------------------------------------------


class TestCleanupReport:
    def test_empty_report(self):
        report = CleanupReport()
        assert report.total == 0
        assert report.total_size_mb == 0.0

    def test_add_tracks_files(self, tmp_path):
        f = tmp_path / "test.log"
        f.write_text("x" * 1024)

        report = CleanupReport()
        report.add(f, "stale_log", "old")
        assert report.total == 1
        assert report.total_size > 0

    def test_add_handles_missing_file(self, tmp_path):
        report = CleanupReport()
        report.add(tmp_path / "missing.log", "stale", "gone")
        assert report.total == 1
        assert report.total_size == 0  # OSError caught


# ---------------------------------------------------------------------------
# is_user_data_file
# ---------------------------------------------------------------------------


class TestIsUserDataFile:
    def test_detects_data_patterns(self, tmp_path):
        f = tmp_path / "data.yaml"
        f.write_text("entries:\n  - id: abc\n    created_at: 2026-01-01\n")
        assert is_user_data_file(f) is True

    def test_rejects_config_files(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text("name: my-skill\nversion: 1.0\n")
        assert is_user_data_file(f) is False

    def test_nonexistent_file(self, tmp_path):
        assert is_user_data_file(tmp_path / "nope.yaml") is False

    def test_non_yaml_file(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("print('hello')")
        assert is_user_data_file(f) is False


# ---------------------------------------------------------------------------
# is_script_file
# ---------------------------------------------------------------------------


class TestIsScriptFile:
    def test_detects_main_guard(self, tmp_path):
        f = tmp_path / "script.py"
        f.write_text('if __name__ == "__main__":\n    main()\n')
        assert is_script_file(f) is True

    def test_module_without_main(self, tmp_path):
        f = tmp_path / "lib.py"
        f.write_text("def helper():\n    return 1\n")
        assert is_script_file(f) is False

    def test_non_python_file(self, tmp_path):
        f = tmp_path / "data.yaml"
        f.write_text("key: value\n")
        assert is_script_file(f) is False


# ---------------------------------------------------------------------------
# calculate_directory_size
# ---------------------------------------------------------------------------


class TestCalculateDirectorySize:
    def test_nonexistent_returns_zero(self, tmp_path):
        assert calculate_directory_size(tmp_path / "nope") == 0.0

    def test_counts_file_sizes(self, tmp_path):
        (tmp_path / "a.txt").write_text("x" * 1024)
        (tmp_path / "b.txt").write_text("y" * 1024)
        size = calculate_directory_size(tmp_path)
        assert size > 0

    def test_excludes_git_dir(self, tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "objects").write_bytes(b"\x00" * 10000)
        (tmp_path / "src.py").write_text("x")
        size = calculate_directory_size(tmp_path)
        # Should be very small because .git is excluded
        assert size < 0.01


# ---------------------------------------------------------------------------
# clean_stale_runtime
# ---------------------------------------------------------------------------


class TestCleanStaleRuntime:
    def test_nonexistent_returns_empty(self, tmp_path):
        report = clean_stale_runtime(tmp_path / "nope")
        assert report.total == 0

    def test_identifies_old_logs(self, tmp_path):
        log = tmp_path / "old.log"
        log.write_text("stale data")
        old_time = time.time() - 30 * 86400
        os.utime(log, (old_time, old_time))

        report = clean_stale_runtime(tmp_path, dry_run=True)
        assert report.total >= 1
