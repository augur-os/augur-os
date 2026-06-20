"""Tests for devops/scripts/ops/todo_outdated.py — TODO_OUTDATED marker scanner."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OPS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "ops"
if str(OPS_DIR) not in sys.path:
    sys.path.insert(0, str(OPS_DIR))

from todo_outdated import (
    _get_latest_commit,
    fix,
    name,
    scan,
)


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------

class TestScan:
    @patch("todo_outdated.subprocess.run")
    def test_finds_markers(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="src/old_module.py\nplugins/dev/stale.ts\n",
        )
        ctx = OpsContext(project_root=tmp_path, config={"scan_timeout": 10})
        result = scan(ctx)
        assert isinstance(result, ScanResult)
        assert result.severity == "warning"
        assert len(result.issues) == 2
        assert result.issues[0]["marker"] == "TODO_OUTDATED"

    @patch("todo_outdated.subprocess.run")
    def test_no_markers_returns_info(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        ctx = OpsContext(project_root=tmp_path, config={"scan_timeout": 10})
        result = scan(ctx)
        assert result.severity == "info"
        assert result.issues == []

    @patch("todo_outdated.subprocess.run")
    def test_timeout_returns_info(self, mock_run, tmp_path):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="grep", timeout=30)
        ctx = OpsContext(project_root=tmp_path, config={"scan_timeout": 1})
        result = scan(ctx)
        assert result.severity == "info"

    @patch("todo_outdated.subprocess.run")
    def test_caps_at_20_files(self, mock_run, tmp_path):
        files = "\n".join(f"file{i}.py" for i in range(30))
        mock_run.return_value = MagicMock(returncode=0, stdout=files)
        ctx = OpsContext(project_root=tmp_path, config={"scan_timeout": 10})
        result = scan(ctx)
        assert len(result.issues) == 20

    def test_uses_default_timeout_from_config(self, tmp_path):
        ctx = OpsContext(project_root=tmp_path, config={})
        with patch("todo_outdated.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            scan(ctx)
            # Default timeout should be 30
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["timeout"] == 30


# ---------------------------------------------------------------------------
# fix
# ---------------------------------------------------------------------------

class TestFix:
    def test_dry_run(self, tmp_path):
        ctx = OpsContext(project_root=tmp_path, dry_run=True, config={})
        result = fix(ctx, [{"file": "x.py", "marker": "TODO_OUTDATED"}])
        assert result.success is True
        assert "Dry run" in result.summary

    @patch("todo_outdated._find_cli")
    def test_no_cli_returns_failure(self, mock_cli, tmp_path):
        mock_cli.return_value = None
        ctx = OpsContext(project_root=tmp_path, config={})
        result = fix(ctx, [{"file": "x.py"}])
        assert result.success is False
        assert "No CLI" in result.summary

    @patch("todo_outdated._get_latest_commit")
    @patch("todo_outdated.subprocess.run")
    @patch("todo_outdated._find_cli")
    def test_successful_fix(self, mock_cli, mock_run, mock_commit, tmp_path):
        mock_cli.return_value = "/usr/bin/claude"
        mock_run.return_value = MagicMock(returncode=0)
        mock_commit.return_value = "abc1234"
        ctx = OpsContext(project_root=tmp_path, config={"max_turns": 5, "fix_timeout": 60})
        result = fix(ctx, [{"file": "x.py"}])
        assert result.success is True
        assert len(result.changes) == 1


# ---------------------------------------------------------------------------
# _get_latest_commit
# ---------------------------------------------------------------------------

class TestGetLatestCommit:
    @patch("todo_outdated.subprocess.run")
    def test_returns_hash(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="abc1234\n")
        assert _get_latest_commit(tmp_path) == "abc1234"

    @patch("todo_outdated.subprocess.run")
    def test_returns_none_on_failure(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=128, stdout="")
        assert _get_latest_commit(tmp_path) is None


# ---------------------------------------------------------------------------
# Module attrs
# ---------------------------------------------------------------------------

def test_module_name():
    assert name == "auto-todo-outdated"
