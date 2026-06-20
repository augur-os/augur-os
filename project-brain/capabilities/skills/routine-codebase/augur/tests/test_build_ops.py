"""Tests for auto-test-build vertical."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.lib.ops_protocol import make_test_ctx


def _load_module():
    """Load test_build_ops from hyphenated skill directory."""
    skill_dir = Path(__file__).resolve().parents[2]
    module_file = skill_dir / "scripts" / "test_build_ops.py"
    spec = importlib.util.spec_from_file_location("test_build_ops", module_file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["test_build_ops"] = mod
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()
scan = _mod.scan
fix = _mod.fix


def test_scan_no_dashboard(tmp_path):
    result = scan(make_test_ctx(tmp_path))
    assert result.severity == "info"
    assert "No dashboard" in result.summary


def test_scan_build_success(tmp_path):
    (tmp_path / "apps/dashboard").mkdir(parents=True)
    mock_result = MagicMock(returncode=0, stderr="", stdout="")
    with patch.object(_mod, "_run_build", return_value=mock_result):
        result = scan(make_test_ctx(tmp_path))
    assert result.severity == "info"
    assert not result.issues


def test_run_build_uses_lifecycle_locked_posix_script_without_npm_prebuild(tmp_path):
    dashboard_dir = tmp_path / "apps/dashboard"
    dashboard_dir.mkdir(parents=True)
    mock_result = MagicMock(returncode=0, stderr="", stdout="")

    with (
        patch.object(_mod.os, "name", "posix"),
        patch.object(_mod.subprocess, "run", return_value=mock_result) as mock_run,
    ):
        result = _mod._run_build(dashboard_dir, timeout=123)

    assert result is mock_result
    assert mock_run.call_args.args[0] == ["./scripts/build.sh"]
    assert mock_run.call_args.kwargs["cwd"] == str(dashboard_dir)
    assert mock_run.call_args.kwargs["timeout"] == 123
    assert mock_run.call_args.kwargs["capture_output"] is True
    assert mock_run.call_args.kwargs["text"] is True


def test_run_build_uses_lifecycle_locked_windows_safe_build(tmp_path):
    dashboard_dir = tmp_path / "apps/dashboard"
    dashboard_dir.mkdir(parents=True)
    mock_result = MagicMock(returncode=0, stderr="", stdout="")

    with (
        patch.object(_mod.os, "name", "nt"),
        patch.object(_mod, "_pnpm_cmd", return_value=["pnpm.cmd"]),
        patch.object(_mod.subprocess, "run", return_value=mock_result) as mock_run,
    ):
        result = _mod._run_build(dashboard_dir, timeout=123)

    assert result is mock_result
    assert mock_run.call_args.args[0] == ["pnpm.cmd", "run", "build:safe"]
    assert mock_run.call_args.kwargs["cwd"] == str(dashboard_dir)
    assert mock_run.call_args.kwargs["timeout"] == 123
    assert mock_run.call_args.kwargs["capture_output"] is True
    assert mock_run.call_args.kwargs["text"] is True


def test_scan_build_failure(tmp_path):
    (tmp_path / "apps/dashboard").mkdir(parents=True)
    mock_result = MagicMock(returncode=1, stderr="Error: Cannot find module", stdout="")
    with patch.object(_mod, "_run_build", return_value=mock_result):
        result = scan(make_test_ctx(tmp_path, difficulty=3))
    assert result.severity == "error"
    assert len(result.issues) == 1
    assert result.issues[0]["category"] == "module-resolution"
    assert "module-resolution" in result.summary


def test_scan_build_timeout(tmp_path):
    (tmp_path / "apps/dashboard").mkdir(parents=True)
    with patch.object(_mod, "_run_build", side_effect=subprocess.TimeoutExpired("npm", 300)):
        result = scan(make_test_ctx(tmp_path, difficulty=1))
    assert result.severity == "error"
    assert "timed out" in result.summary


def test_fix_dry_run(tmp_path):
    ctx = make_test_ctx(tmp_path, dry_run=True)
    result = fix(ctx, [{"error": "build failed"}])
    assert result.success
    assert "Dry run" in result.summary


def test_fix_writes_report(tmp_path):
    with patch.dict("os.environ", {"AUGUR_STATE": str(tmp_path / "runtime")}):
        result = fix(make_test_ctx(tmp_path, difficulty=1), [{"error": "build failed"}])
    assert result.success
    report = Path(result.actions[0]["report"])
    assert report.name == "test-build-latest.json"
    assert report.exists()


def test_scan_d2_uses_deep_timeout(tmp_path):
    (tmp_path / "apps/dashboard").mkdir(parents=True)
    mock_result = MagicMock(returncode=0, stderr="", stdout="")
    with patch.object(_mod, "_run_build", return_value=mock_result) as mock_build:
        result = scan(make_test_ctx(tmp_path, difficulty=2, config={"build_timeout": 120, "deep_build_timeout": 700}))
    assert result.severity == "info"
    assert mock_build.call_args.kwargs["timeout"] == 700


def test_scan_d4_runs_typecheck_after_successful_build(tmp_path):
    (tmp_path / "apps/dashboard").mkdir(parents=True)
    build_result = MagicMock(returncode=0, stderr="", stdout="")
    typecheck_result = MagicMock(returncode=1, stderr="Type error: boom", stdout="")
    with patch.object(_mod, "_run_build", return_value=build_result), patch.object(_mod, "_run_typecheck", return_value=typecheck_result):
        result = scan(make_test_ctx(tmp_path, difficulty=4))
    assert result.severity == "error"
    assert result.issues[0]["phase"] == "typecheck"
    assert result.issues[0]["category"] == "type-error"


def test_summarize_build_failure_classifies_missing_node_modules_as_module_resolution():
    failure = _mod._summarize_build_failure(
        "Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'esbuild'\n"
        "Local package.json exists, but node_modules missing, did you mean to install?",
        "",
    )
    assert failure["category"] == "module-resolution"


def test_summarize_build_failure_classifies_turbopack_module_not_found_as_module_resolution():
    failure = _mod._summarize_build_failure(
        "Error: Turbopack build failed with 4 errors:\n"
        "./app/brain/[[...slug]]/registry.ts:6:18\n"
        "Module not found: Can't resolve '@/lib/configs/brain-books'\n",
        "",
    )
    assert failure["category"] == "module-resolution"
