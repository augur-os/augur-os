"""Tests for auto-test-pytest vertical."""
from pathlib import Path
from unittest.mock import patch, MagicMock
import importlib.util
import subprocess
import sys

from src.lib.ops_protocol import make_test_ctx


def _load_module():
    """Load ops module from hyphenated skill directory via file path."""
    module_file = Path(__file__).resolve().parents[2] / "scripts" / "test_pytest_ops.py"
    spec = importlib.util.spec_from_file_location("test_pytest_ops", module_file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["test_pytest_ops"] = mod
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()
scan = _mod.scan
fix = _mod.fix


def test_scan_no_test_dirs(tmp_path):
    result = scan(make_test_ctx(tmp_path))
    assert result.severity == "info"
    assert "No test directories" in result.summary


def test_scan_all_pass(tmp_path):
    (tmp_path / "project-brain/capabilities/skills/resume/augur/tests").mkdir(parents=True)
    mock_result = MagicMock(returncode=0, stdout="3 passed", stderr="")
    with patch.object(_mod, "_run_pytest", return_value=mock_result):
        result = scan(make_test_ctx(tmp_path))
    assert result.severity == "info"
    assert not result.issues


def test_scan_with_failures(tmp_path):
    (tmp_path / "project-brain/capabilities/skills/resume/augur/tests").mkdir(parents=True)
    mock_result = MagicMock(returncode=1, stdout="1 failed, 2 passed", stderr="FAILED test_x")
    with patch.object(_mod, "_run_pytest", return_value=mock_result):
        result = scan(make_test_ctx(tmp_path, difficulty=1))
    assert result.severity == "error"
    assert len(result.issues) == 1


def test_scan_uses_requested_repo_test_paths(tmp_path):
    requested = tmp_path / "tests" / "scripts" / "test_dashboard_start_dev.py"
    requested.parent.mkdir(parents=True)
    requested.write_text("def test_ok():\n    assert True\n")
    mock_result = MagicMock(returncode=0, stdout="1 passed", stderr="")

    with patch.object(_mod, "_run_pytest", return_value=mock_result) as mock_run:
        ctx = make_test_ctx(tmp_path, difficulty=1)
        ctx.config["smoke_test_paths"] = ["tests/scripts/test_dashboard_start_dev.py"]
        result = scan(ctx)

    assert result.severity == "info"
    call_args = mock_run.call_args[0]
    test_targets = call_args[1]
    assert test_targets == [requested]


def test_scan_reports_missing_requested_test_path(tmp_path):
    ctx = make_test_ctx(tmp_path, difficulty=1)
    ctx.config["smoke_test_paths"] = ["tests/scripts/missing.py"]

    result = scan(ctx)

    assert result.severity == "error"
    assert "Requested pytest target does not exist" in result.summary


def test_scan_hub_scoped(tmp_path):
    resume = tmp_path / "project-brain/capabilities/skills/resume"
    bridge = tmp_path / "project-brain/capabilities/skills/bridge"
    (resume / "augur/tests").mkdir(parents=True)
    (bridge / "augur/tests").mkdir(parents=True)
    (resume / "SKILL.md").write_text("---\nx-augur-hub: career\n---\n")
    (bridge / "SKILL.md").write_text("---\nx-augur-hub: ai\n---\n")
    mock_result = MagicMock(returncode=0, stdout="2 passed", stderr="")
    with patch.object(_mod, "_run_pytest", return_value=mock_result) as mock_run:
        ctx = make_test_ctx(tmp_path, difficulty=1)
        ctx.config["hub"] = "career"
        scan(ctx)
    # Should only pass career test paths to pytest
    call_args = mock_run.call_args[0]  # positional args
    test_dirs = call_args[1]  # second positional arg is test_dirs
    assert len(test_dirs) == 1
    assert "project-brain/capabilities/skills/resume/augur/tests" in Path(test_dirs[0]).as_posix()


def test_scan_timeout(tmp_path):
    (tmp_path / "project-brain/capabilities/skills/resume/augur/tests").mkdir(parents=True)
    with patch.object(_mod, "_run_pytest", side_effect=subprocess.TimeoutExpired("pytest", 300)):
        result = scan(make_test_ctx(tmp_path, difficulty=1))
    assert result.severity == "error"
    assert "timed out" in result.summary


def test_find_python_prefers_project_venv(tmp_path):
    venv_python = tmp_path / ".venv" / "bin" / "python3"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("#!/bin/sh\n")

    with patch.object(_mod.sys, "executable", "/usr/bin/python3"):
        assert _mod._find_python(tmp_path) == str(venv_python)


def test_fix_dry_run(tmp_path):
    ctx = make_test_ctx(tmp_path, dry_run=True)
    result = fix(ctx, [{"error": "test failed"}])
    assert result.success
    assert "Dry run" in result.summary


def test_fix_writes_report(tmp_path):
    result = fix(make_test_ctx(tmp_path), [{"error": "test failed"}])
    assert result.success
    report = Path(result.actions[0]["report"])
    assert report.exists()
