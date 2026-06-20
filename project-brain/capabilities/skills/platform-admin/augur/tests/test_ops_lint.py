"""Tests for auto-lint ops module and lint_lib shared implementation."""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, make_test_ctx


def _ctx(tmp_path: Path, **kwargs) -> OpsContext:
    return make_test_ctx(tmp_path, **kwargs)


def _lint_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "lint.py"
    spec = importlib.util.spec_from_file_location("platform_admin_ops_lint_test", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestScan:
    def test_scan_no_dashboard_dir_returns_clean(self, tmp_path: Path):
        lint = _lint_module()

        result = lint.scan(_ctx(tmp_path))

        assert isinstance(result, ScanResult)
        assert result.issues == []
        assert "No dashboard" in result.summary

    def test_scan_d0_surface_check_only(self, tmp_path: Path):
        lint = _lint_module()

        (tmp_path / "apps" / "dashboard").mkdir(parents=True)
        result = lint.scan(_ctx(tmp_path, difficulty=0))

        assert result.issues == []
        assert result.health == "verified"

    @patch("subprocess.run")
    def test_scan_d1_reports_eslint_issues(self, mock_run: MagicMock, tmp_path: Path):
        lint = _lint_module()

        (tmp_path / "apps" / "dashboard").mkdir(parents=True)

        eslint_output = '[{"messages": [{"severity": 2, "fix": true}]}]'
        mock_run.return_value = MagicMock(
            returncode=1, stdout=eslint_output, stderr=""
        )

        result = lint.scan(_ctx(tmp_path, difficulty=1))

        assert len(result.issues) == 1
        assert result.issues[0]["action"] == "lint-autofix"
        assert result.issues[0]["fixable_count"] == 1

    @patch("subprocess.run")
    def test_scan_d1_clean_eslint_output(self, mock_run: MagicMock, tmp_path: Path):
        lint = _lint_module()

        (tmp_path / "apps" / "dashboard").mkdir(parents=True)
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = lint.scan(_ctx(tmp_path, difficulty=1))

        assert result.issues == []

    def test_scan_d1_uses_windows_cmd_launcher(
        self,
        monkeypatch,
        tmp_path: Path,
    ):
        lint = _lint_module()

        (tmp_path / "apps" / "dashboard").mkdir(parents=True)
        (tmp_path / "apps" / "dashboard" / "package.json").write_text(
            '{"packageManager":"pnpm@10.32.1"}',
            encoding="utf-8",
        )
        monkeypatch.setattr(lint._lint_lib.os, "name", "nt")
        monkeypatch.setattr(
            lint._lint_lib.shutil,
            "which",
            lambda command: (
                "C:/tools/pnpm.cmd" if command == "pnpm.cmd" else None
            ),
        )
        calls = []

        def fake_run(command, *args, **kwargs):
            calls.append(command)
            return MagicMock(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(lint._lint_lib.subprocess, "run", fake_run)

        result = lint.scan(_ctx(tmp_path, difficulty=1))

        assert result.issues == []
        assert calls[0][:3] == ["C:/tools/pnpm.cmd", "exec", "eslint"]

    @patch("subprocess.run")
    def test_scan_handles_timeout(self, mock_run: MagicMock, tmp_path: Path):
        lint = _lint_module()

        (tmp_path / "apps" / "dashboard").mkdir(parents=True)
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="npx", timeout=120)

        result = lint.scan(_ctx(tmp_path, difficulty=1))

        assert result.issues == []
        assert result.health == "broken"


class TestFix:
    def test_fix_dry_run(self, tmp_path: Path):
        lint = _lint_module()

        result = lint.fix(
            _ctx(tmp_path, dry_run=True),
            [{"action": "lint-autofix", "fixable_count": 5}],
        )

        assert isinstance(result, FixResult)
        assert result.success is True
        assert "Dry run" in result.summary

    @patch("subprocess.run")
    def test_fix_runs_eslint_fix(self, mock_run: MagicMock, tmp_path: Path):
        lint = _lint_module()

        (tmp_path / "apps" / "dashboard").mkdir(parents=True)

        # First call: eslint --fix, second: git diff --cached, etc.
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = lint.fix(
            _ctx(tmp_path),
            [{"action": "lint-autofix", "fixable_count": 3}],
        )

        assert isinstance(result, FixResult)
        assert result.success is True


class TestModuleInterface:
    def test_has_name(self):
        lint = _lint_module()
        assert lint.name == "auto-lint"

    def test_has_scan_callable(self):
        lint = _lint_module()
        assert callable(lint.scan)

    def test_has_fix_callable(self):
        lint = _lint_module()
        assert callable(lint.fix)

    def test_has_difficulty_spec(self):
        lint = _lint_module()
        assert hasattr(lint, "DIFFICULTY_SPEC")
        assert 0 in lint.DIFFICULTY_SPEC
