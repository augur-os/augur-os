"""Tests for cleanup_scan.py — read-only disk-waste category scanning."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import cleanup_scan  # noqa: E402


def _fixture_paths(tmp_path: Path) -> dict[str, list[str]]:
    caches = tmp_path / "Library" / "Caches"
    (caches / "com.example.app").mkdir(parents=True)
    (caches / "com.example.app" / "blob.bin").write_bytes(b"x" * 2048)
    (caches / "loose.dat").write_bytes(b"y" * 512)

    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    (downloads / "installer.dmg").write_bytes(b"z" * 4096)
    (downloads / "keep.txt").write_text("not an installer")

    return {
        "app-caches": [str(caches)],
        "downloads-installers": [str(downloads / "*.dmg")],
    }


class TestScanCategory:
    def test_reports_items_and_sizes(self, tmp_path):
        paths = _fixture_paths(tmp_path)
        result = cleanup_scan.scan_category("app-caches", category_paths=paths)
        assert result["category"] == "app-caches"
        names = {item["name"] for item in result["items"]}
        assert {"com.example.app", "loose.dat"} <= names
        assert result["totalSize"] >= 2048 + 512
        # Sorted largest-first
        sizes = [item["size"] for item in result["items"]]
        assert sizes == sorted(sizes, reverse=True)

    def test_glob_category_matches_pattern_only(self, tmp_path):
        paths = _fixture_paths(tmp_path)
        result = cleanup_scan.scan_category(
            "downloads-installers", category_paths=paths
        )
        names = {item["name"] for item in result["items"]}
        assert names == {"installer.dmg"}

    def test_unknown_category_errors(self, tmp_path):
        result = cleanup_scan.scan_category(
            "nonsense", category_paths=_fixture_paths(tmp_path)
        )
        assert result["items"] == []
        assert "Unknown category" in result["error"]

    def test_scan_is_side_effect_free(self, tmp_path):
        paths = _fixture_paths(tmp_path)
        before = sorted(str(p) for p in tmp_path.rglob("*"))
        cleanup_scan.scan_category("all", category_paths=paths,
                                   dev_scan_roots=[], large_file_dirs=[])
        after = sorted(str(p) for p in tmp_path.rglob("*"))
        assert before == after

    def test_all_combines_categories(self, tmp_path):
        paths = _fixture_paths(tmp_path)
        result = cleanup_scan.scan_category(
            "all", category_paths=paths, dev_scan_roots=[], large_file_dirs=[]
        )
        names = {item["name"] for item in result["items"]}
        assert {"com.example.app", "loose.dat", "installer.dmg"} <= names

    def test_dev_artifacts_fixture(self, tmp_path):
        project = tmp_path / "Projects" / "demo"
        (project / "node_modules" / "pkg").mkdir(parents=True)
        (project / "node_modules" / "pkg" / "index.js").write_bytes(b"a" * 1024)
        (project / "src").mkdir()
        result = cleanup_scan.scan_dev_artifacts(
            scan_roots=[str(tmp_path / "Projects")]
        )
        assert result["category"] == "dev-artifacts"
        assert any(i["name"] == "demo/node_modules" for i in result["items"])
        assert result["totalSize"] > 0


class TestCli:
    def test_help_exits_zero(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "cleanup_scan.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0
        assert "--category" in proc.stdout
