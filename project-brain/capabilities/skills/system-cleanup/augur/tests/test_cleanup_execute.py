"""Tests for cleanup_execute.py — trash-safe, confirmation-gated execution."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import cleanup_common  # noqa: E402
import cleanup_execute  # noqa: E402


def _fixture(tmp_path: Path) -> tuple[dict[str, list[str]], Path]:
    caches = tmp_path / "Library" / "Caches"
    (caches / "com.example.app").mkdir(parents=True)
    (caches / "com.example.app" / "blob.bin").write_bytes(b"x" * 2048)
    (caches / "loose.dat").write_bytes(b"y" * 512)
    return {"app-caches": [str(caches)]}, caches


def _fake_trash(trash_dir: Path):
    """Monkeypatch target that simulates the OS Trash inside tmp."""
    trash_dir.mkdir(exist_ok=True)

    def fake(path):
        p = Path(path)
        shutil.move(str(p), str(trash_dir / p.name))
        return {"path": str(p), "trashed": True, "reversible": True, "error": None}

    return fake


class TestRefusesWithoutConfirmation:
    def test_dry_run_touches_nothing(self, tmp_path, monkeypatch):
        paths, caches = _fixture(tmp_path)
        calls = []
        monkeypatch.setattr(cleanup_common, "send_to_trash",
                            lambda p: calls.append(p))

        result = cleanup_execute.execute_cleanup(
            "app-caches", confirm=False,
            category_paths=paths, protected=[], home=tmp_path,
        )
        assert result["executed"] is False
        assert result["confirmed"] is False
        assert calls == []
        assert (caches / "com.example.app" / "blob.bin").exists()
        assert (caches / "loose.dat").exists()
        assert "--confirm" in result["message"]
        assert all(e["type"] != "success" for e in result["log"])

    def test_trash_category_is_report_only_even_with_confirm(self, tmp_path):
        result = cleanup_execute.execute_cleanup(
            "trash", confirm=True,
            category_paths={"trash": [str(tmp_path)]},
            protected=[], home=tmp_path,
        )
        assert result["executed"] is False
        assert result["trashed"] == 0
        assert "report-only" in result["message"]


class TestConfirmedExecution:
    def test_trashes_reversibly(self, tmp_path, monkeypatch):
        paths, caches = _fixture(tmp_path)
        trash_dir = tmp_path / ".FakeTrash"
        monkeypatch.setattr(cleanup_common, "send_to_trash",
                            _fake_trash(trash_dir))

        result = cleanup_execute.execute_cleanup(
            "app-caches", confirm=True,
            category_paths=paths, protected=[], home=tmp_path,
        )
        assert result["executed"] is True
        assert result["success"] is True
        assert result["trashed"] == 2
        assert result["reversible"] is True
        assert result["spaceReclaimed"] >= 2048 + 512
        # Items are recoverable from the (fake) trash, not gone
        assert (trash_dir / "com.example.app" / "blob.bin").exists()
        assert (trash_dir / "loose.dat").exists()
        assert not (caches / "loose.dat").exists()

    def test_items_subset_only_trashes_selection(self, tmp_path, monkeypatch):
        paths, caches = _fixture(tmp_path)
        trash_dir = tmp_path / ".FakeTrash"
        monkeypatch.setattr(cleanup_common, "send_to_trash",
                            _fake_trash(trash_dir))

        result = cleanup_execute.execute_cleanup(
            "app-caches", items=[str(caches / "loose.dat")], confirm=True,
            category_paths=paths, protected=[], home=tmp_path,
        )
        assert result["trashed"] == 1
        assert not (caches / "loose.dat").exists()
        assert (caches / "com.example.app" / "blob.bin").exists()

    def test_items_outside_scan_are_rejected(self, tmp_path, monkeypatch):
        paths, _ = _fixture(tmp_path)
        outside = tmp_path / "precious.txt"
        outside.write_text("not a scan candidate")
        calls = []
        monkeypatch.setattr(cleanup_common, "send_to_trash",
                            lambda p: calls.append(p))

        result = cleanup_execute.execute_cleanup(
            "app-caches", items=[str(outside)], confirm=True,
            category_paths=paths, protected=[], home=tmp_path,
        )
        assert result["unknownItems"] == 1
        assert result["trashed"] == 0
        assert result["success"] is False
        assert calls == []
        assert outside.exists()


class TestProtectedPaths:
    def test_protected_root_is_skipped(self, tmp_path, monkeypatch):
        paths, caches = _fixture(tmp_path)
        calls = []

        def recording_trash(p):
            calls.append(p)
            return {"path": str(p), "trashed": True, "reversible": True,
                    "error": None}

        monkeypatch.setattr(cleanup_common, "send_to_trash", recording_trash)

        result = cleanup_execute.execute_cleanup(
            "app-caches", confirm=True,
            category_paths=paths,
            protected=[(caches / "com.example.app").resolve()],
            home=tmp_path,
        )
        assert result["skippedProtected"] == 1
        assert (caches / "com.example.app" / "blob.bin").exists()
        # The unprotected sibling was still trashed
        assert calls == [str((caches / "loose.dat").resolve())]

    def test_outside_home_is_protected(self, tmp_path):
        assert cleanup_common.is_protected(
            "/etc/hosts", roots=[], home=tmp_path
        ) is True

    def test_home_itself_is_protected(self, tmp_path):
        assert cleanup_common.is_protected(
            tmp_path, roots=[], home=tmp_path
        ) is True

    def test_real_protected_roots_cover_repo_and_documents(self):
        roots = cleanup_common.protected_roots()
        repo = cleanup_common.find_project_root().resolve()
        assert repo in roots
        assert (Path.home() / "Documents").resolve() in roots


class TestCli:
    def test_help_exits_zero(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "cleanup_execute.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0
        assert "--confirm" in proc.stdout
        assert "Trash" in proc.stdout
