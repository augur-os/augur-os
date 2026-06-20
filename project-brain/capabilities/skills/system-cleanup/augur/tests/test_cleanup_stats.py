"""Tests for cleanup_stats.py — system stats and category size estimates."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import cleanup_stats  # noqa: E402


class TestGatherSystemStats:
    def test_returns_expected_keys(self):
        stats = cleanup_stats.gather_system_stats()
        assert set(stats) >= {"cpu", "memory", "disk", "uptime", "timestamp"}
        assert stats["disk"]["total"] > 0
        if sys.platform == "darwin":
            assert stats["memory"]["total"] > 0


class TestGatherCategorySizes:
    def test_fixture_sizes(self, tmp_path):
        caches = tmp_path / "Caches"
        caches.mkdir()
        (caches / "blob.bin").write_bytes(b"x" * 4096)
        results = cleanup_stats.gather_category_sizes(
            category_paths={"app-caches": [str(caches)]},
            dev_scan_roots=[],
            large_file_dirs=[],
        )
        by_id = {r["id"]: r for r in results}
        assert set(by_id) == {"app-caches", "dev-artifacts", "large-files"}
        assert by_id["app-caches"]["size"] >= 4096
        assert by_id["dev-artifacts"]["size"] == 0


class TestCli:
    def test_help_exits_zero(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "cleanup_stats.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0
        assert "read-only" in proc.stdout
