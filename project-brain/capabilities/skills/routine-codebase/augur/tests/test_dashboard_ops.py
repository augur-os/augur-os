"""Tests for auto-test-dashboard vertical."""
from pathlib import Path
from unittest.mock import patch, MagicMock
import importlib.util
import subprocess
import sys

from src.lib.ops_protocol import make_test_ctx


def _load_module():
    """Load ops module from hyphenated skill directory via file path."""
    module_file = Path(__file__).resolve().parents[2] / "scripts" / "test_dashboard_ops.py"
    spec = importlib.util.spec_from_file_location("test_dashboard_ops", module_file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["test_dashboard_ops"] = mod
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()
scan = _mod.scan
fix = _mod.fix
_normalize_test_paths = _mod._normalize_test_paths
_summarize_jest_failure = _mod._summarize_jest_failure


def test_scan_no_dashboard(tmp_path):
    result = scan(make_test_ctx(tmp_path))
    assert result.severity == "info"
    assert "No dashboard" in result.summary


def test_scan_jest_pass(tmp_path):
    (tmp_path / "apps/dashboard").mkdir(parents=True)
    mock_result = MagicMock(returncode=0, stdout="Tests: 10 passed", stderr="")
    with patch.object(_mod, "_run_jest", return_value=mock_result):
        result = scan(make_test_ctx(tmp_path))
    assert result.severity == "info"


def test_scan_jest_fail(tmp_path):
    (tmp_path / "apps/dashboard").mkdir(parents=True)
    (tmp_path / "tests/dashboard/api").mkdir(parents=True)
    (tmp_path / "tests/dashboard/api/agents-available.test.ts").write_text("test('ok', () => {})")
    mock_result = MagicMock(returncode=1, stdout="Tests: 2 failed, 8 passed", stderr="route import failed")
    with patch.object(_mod, "_run_jest", return_value=mock_result):
        result = scan(make_test_ctx(tmp_path))
    assert result.severity == "error"
    assert len(result.issues) == 1
    assert "route import failed" in result.issues[0]["error"]
    assert result.issues[0]["category"] == "test-failure"
    assert result.issues[0]["test_paths"] == ["../../tests/dashboard/api/agents-available.test.ts"]


def test_scan_jest_runner_missing_category(tmp_path):
    (tmp_path / "apps/dashboard").mkdir(parents=True)
    mock_result = MagicMock(returncode=254, stdout="", stderr='ERR_PNPM_RECURSIVE_EXEC_FIRST_FAIL Command "jest" not found')
    with patch.object(_mod, "_run_jest", return_value=mock_result):
        result = scan(make_test_ctx(tmp_path))
    assert result.issues[0]["category"] == "runner-missing"


def test_scan_hub_scoped(tmp_path):
    (tmp_path / "apps/dashboard").mkdir(parents=True)
    mock_result = MagicMock(returncode=0, stdout="Tests: 3 passed", stderr="")
    with patch.object(_mod, "_run_jest", return_value=mock_result) as mock_run:
        ctx = make_test_ctx(tmp_path)
        ctx.config["hub"] = "career"
        scan(ctx)
    call_args = mock_run.call_args
    hub_arg = call_args[0][1]  # second positional arg is hub
    assert hub_arg == "career"


def test_run_jest_uses_current_plural_hub_pattern_flag(tmp_path):
    dashboard_dir = tmp_path / "apps/dashboard"
    dashboard_dir.mkdir(parents=True)
    captured: dict[str, list[str]] = {}

    def fake_run(cmd, **_kwargs):
        captured["cmd"] = cmd
        return MagicMock(returncode=0, stdout="Tests: 3 passed", stderr="")

    with patch.object(_mod, "_jest_base_cmd", return_value=["jest"]), patch.object(
        _mod.subprocess,
        "run",
        side_effect=fake_run,
    ):
        _mod._run_jest(dashboard_dir, "browse", 300)

    assert "--testPathPatterns" in captured["cmd"]
    assert "--testPathPattern" not in captured["cmd"]


def test_run_jest_uses_utf8_replacement_decoding(tmp_path):
    dashboard_dir = tmp_path / "apps/dashboard"
    dashboard_dir.mkdir(parents=True)
    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        return MagicMock(returncode=0, stdout="Tests: 3 passed", stderr="")

    with patch.object(_mod, "_jest_base_cmd", return_value=["jest"]), patch.object(
        _mod.subprocess,
        "run",
        side_effect=fake_run,
    ):
        _mod._run_jest(dashboard_dir, None, 300, test_paths=["example.test.ts"])

    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"


def test_run_jest_generates_browse_item_actions_before_jest(tmp_path):
    dashboard_dir = tmp_path / "apps/dashboard"
    dashboard_dir.mkdir(parents=True)
    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="Tests: 3 passed", stderr="")

    with patch.object(_mod, "_jest_base_cmd", return_value=["jest"]), patch.object(
        _mod.subprocess,
        "run",
        side_effect=fake_run,
    ):
        _mod._run_jest(dashboard_dir, None, 300, test_paths=["example.test.ts"])

    assert calls[0][:2] == ["node", "scripts/build-scripts.mjs"]
    assert calls[1][:2] == ["node", "scripts/dist/generate-item-actions.mjs"]
    assert calls[2][0] == "jest"


def test_scan_timeout(tmp_path):
    (tmp_path / "apps/dashboard").mkdir(parents=True)
    with patch.object(_mod, "_run_jest", side_effect=subprocess.TimeoutExpired("jest", 300)):
        result = scan(make_test_ctx(tmp_path))
    assert result.severity == "error"
    assert "timed out" in result.summary


def test_fix_dry_run(tmp_path):
    ctx = make_test_ctx(tmp_path, dry_run=True)
    result = fix(ctx, [{"error": "test failed"}])
    assert result.success
    assert "Dry run" in result.summary


def test_fix_writes_report(tmp_path):
    import os

    with patch.dict(os.environ, {"AUGUR_STATE": str(tmp_path / "runtime")}):
        result = fix(make_test_ctx(tmp_path), [{"error": "test failed"}])
    assert result.success
    report = tmp_path / "runtime/reports/test-dashboard-latest.json"
    assert report.exists()


def test_normalize_test_paths_prefers_project_root_tests(tmp_path):
    dashboard_dir = tmp_path / "apps/dashboard"
    dashboard_dir.mkdir(parents=True)
    test_file = tmp_path / "tests/dashboard/api/agents-available.test.ts"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("test('ok', () => {})")

    assert _normalize_test_paths(
        tmp_path,
        dashboard_dir,
        ["tests/dashboard/api/agents-available.test.ts"],
    ) == ["../../tests/dashboard/api/agents-available.test.ts"]


def test_summarize_jest_failure_detects_runner_missing():
    summary = _summarize_jest_failure('ERR_PNPM_RECURSIVE_EXEC_FIRST_FAIL Command "jest" not found')
    assert summary["category"] == "runner-missing"


def test_summarize_jest_failure_detects_missing_build_dependency_as_runner_missing():
    summary = _summarize_jest_failure(
        "Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'esbuild' imported from "
        "apps/dashboard/scripts/build-scripts.mjs\n"
        "    at ModuleLoader.resolveSync (node:internal/modules/esm/loader:746:52)"
    )
    assert summary["category"] == "runner-missing"


def test_fix_runner_missing_installs_and_reruns(tmp_path):
    dashboard_dir = tmp_path / "apps/dashboard"
    dashboard_dir.mkdir(parents=True)
    with patch.object(_mod.subprocess, "run", return_value=MagicMock(returncode=0)), patch.object(
        _mod,
        "_run_jest",
        return_value=MagicMock(returncode=0, stdout="ok", stderr=""),
    ):
        result = fix(
            make_test_ctx(tmp_path),
            [{"error": 'Command "jest" not found', "category": "runner-missing", "hub": None, "test_paths": []}],
        )
    assert result.success
    assert "auto-fixed" in result.summary


def test_fix_cache_corruption_missing_build_dependency_installs_and_reruns(tmp_path):
    dashboard_dir = tmp_path / "apps/dashboard"
    dashboard_dir.mkdir(parents=True)
    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch.object(_mod.subprocess, "run", side_effect=fake_run), patch.object(
        _mod,
        "_run_jest",
        return_value=MagicMock(returncode=0, stdout="ok", stderr=""),
    ), patch.object(_mod, "_clear_jest_cache") as clear_cache:
        result = fix(
            make_test_ctx(tmp_path),
            [
                {
                    "error": "Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'esbuild' imported from "
                    "apps/dashboard/scripts/build-scripts.mjs\n"
                    "    at #cachedDefaultResolve (node:internal/modules/esm/loader:697:20)",
                    "category": "cache-corruption",
                    "hub": None,
                    "test_paths": [],
                }
            ],
        )

    assert result.success
    assert "auto-fixed" in result.summary
    assert any("install" in call for call in calls)
    clear_cache.assert_not_called()


def test_fix_test_failure_retries_after_cache_clear(tmp_path):
    dashboard_dir = tmp_path / "apps/dashboard"
    dashboard_dir.mkdir(parents=True)
    with patch.object(
        _mod,
        "_clear_jest_cache",
        return_value=MagicMock(returncode=0, stdout="", stderr=""),
    ), patch.object(
        _mod,
        "_run_jest",
        return_value=MagicMock(returncode=0, stdout="passed", stderr=""),
    ):
        result = fix(
            make_test_ctx(tmp_path),
            [{"error": "Expected true to be false", "category": "test-failure", "hub": None, "test_paths": []}],
        )
    assert result.success
    assert "auto-fixed" in result.summary
