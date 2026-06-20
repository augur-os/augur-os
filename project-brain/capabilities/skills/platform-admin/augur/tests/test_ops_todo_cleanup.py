"""Tests for auto-todo-cleanup ops module."""
from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, make_test_ctx


def _ctx(tmp_path: Path, **kwargs) -> OpsContext:
    return make_test_ctx(tmp_path, **kwargs)


def _todo_cleanup_module():
    return importlib.import_module("skills.platform-admin.scripts.ops.todo_cleanup")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestScan:
    @patch("subprocess.run")
    def test_scan_finds_todo_cleanup_markers(self, mock_run: MagicMock, tmp_path: Path):
        todo_cleanup = _todo_cleanup_module()

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="src/old_module.py\nplugins/test/helper.ts\n",
            stderr="",
        )

        result = todo_cleanup.scan(_ctx(tmp_path))

        assert isinstance(result, ScanResult)
        assert len(result.issues) == 2
        assert result.issues[0]["marker"] == "TODO_CLEANUP"
        assert result.severity == "warning"

    @patch("subprocess.run")
    def test_scan_no_markers_found(self, mock_run: MagicMock, tmp_path: Path):
        todo_cleanup = _todo_cleanup_module()

        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")

        result = todo_cleanup.scan(_ctx(tmp_path))

        assert result.issues == []
        assert result.severity == "info"
        assert "No TODO_CLEANUP" in result.summary

    @patch("subprocess.run")
    def test_scan_caps_results_at_20(self, mock_run: MagicMock, tmp_path: Path):
        todo_cleanup = _todo_cleanup_module()

        files = "\n".join(f"file_{i}.py" for i in range(30))
        mock_run.return_value = MagicMock(returncode=0, stdout=files, stderr="")

        result = todo_cleanup.scan(_ctx(tmp_path))

        assert len(result.issues) <= 20

    @patch("subprocess.run")
    def test_scan_handles_timeout(self, mock_run: MagicMock, tmp_path: Path):
        todo_cleanup = _todo_cleanup_module()

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="grep", timeout=30)

        result = todo_cleanup.scan(_ctx(tmp_path))

        assert isinstance(result, ScanResult)
        assert result.issues == []

    @patch("subprocess.run")
    def test_scan_handles_grep_not_found(self, mock_run: MagicMock, tmp_path: Path):
        todo_cleanup = _todo_cleanup_module()

        mock_run.side_effect = FileNotFoundError("grep not found")

        result = todo_cleanup.scan(_ctx(tmp_path))

        assert result.issues == []


class TestFix:
    def test_fix_dry_run(self, tmp_path: Path):
        todo_cleanup = _todo_cleanup_module()

        result = todo_cleanup.fix(
            _ctx(tmp_path, dry_run=True),
            [{"action": "todo-cleanup", "file": "test.py", "marker": "TODO_CLEANUP"}],
        )

        assert isinstance(result, FixResult)
        assert result.success is True
        assert "Dry run" in result.summary


class TestModuleInterface:
    def test_has_name(self):
        todo_cleanup = _todo_cleanup_module()
        assert todo_cleanup.name == "auto-todo-cleanup"

    def test_has_scan_callable(self):
        todo_cleanup = _todo_cleanup_module()
        assert callable(todo_cleanup.scan)

    def test_has_fix_callable(self):
        todo_cleanup = _todo_cleanup_module()
        assert callable(todo_cleanup.fix)
