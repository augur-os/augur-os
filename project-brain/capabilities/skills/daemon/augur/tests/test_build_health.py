from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.lib.ops_protocol import OpsContext

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "ops"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_health


def _ctx(tmp_path: Path, **overrides) -> OpsContext:
    dashboard_dir = tmp_path / "apps" / "dashboard"
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    return OpsContext(project_root=tmp_path, config=overrides)


def test_declares_windows_report_only_capabilities():
    assert build_health.OPS_CAPABILITIES.platforms == ("cross_platform",)
    assert build_health.OPS_CAPABILITIES.windows_fix_mode == "report_only"


def test_verify_dashboard_build_uses_package_typecheck_preflight(tmp_path: Path):
    dashboard_dir = tmp_path / "apps" / "dashboard"
    dashboard_dir.mkdir(parents=True)

    with patch("build_health.subprocess.run", return_value=SimpleNamespace(returncode=0)) as run:
        build_health._verify_dashboard_build(
            OpsContext(project_root=tmp_path, config={"scan_timeout": 33}),
            dashboard_dir,
        )

    run.assert_called_once()
    assert run.call_args.args[0] == ["pnpm", "run", "typecheck"]
    assert run.call_args.kwargs["timeout"] == 33


def test_fix_tracks_actual_changed_files_not_only_reported_issue(tmp_path: Path):
    issue = {
        "file": "apps/dashboard/scripts/generate-tab-registry.ts",
        "errors": ["scripts/generate-tab-registry.ts(10,1): error TS2322"],
    }

    with (
        patch.object(build_health, "_find_cli", return_value="/opt/homebrew/bin/codex"),
        patch.object(build_health, "_verify_dashboard_build", return_value=SimpleNamespace(returncode=0)),
        patch.object(build_health, "_list_changed_paths", side_effect=[set(), {"apps/dashboard/lib/tabs/types.ts"}]),
        patch.object(build_health, "_commit_files", return_value="abc123") as commit_files,
        patch("build_health.subprocess.run", return_value=SimpleNamespace(returncode=0)),
    ):
        result = build_health.fix(_ctx(tmp_path), [issue])

    assert result.success is True
    assert "Fixed 1 file(s)" in result.summary
    assert result.fix_type == "code-fix"
    assert result.changes == ["apps/dashboard/lib/tabs/types.ts"]
    commit_files.assert_called_once()
    assert commit_files.call_args.kwargs["paths"] == ["apps/dashboard/lib/tabs/types.ts"]


def test_fix_treats_clean_verify_without_delta_as_resolved_not_broken(tmp_path: Path):
    issue = {
        "file": "apps/dashboard/scripts/generate-tab-registry.ts",
        "errors": ["scripts/generate-tab-registry.ts(10,1): error TS2322"],
    }

    with (
        patch.object(build_health, "_find_cli", return_value="/opt/homebrew/bin/codex"),
        patch.object(build_health, "_verify_dashboard_build", return_value=SimpleNamespace(returncode=0)),
        patch.object(build_health, "_list_changed_paths", side_effect=[set(), set()]),
        patch.object(build_health, "_commit_files") as commit_files,
        patch("build_health.subprocess.run", return_value=SimpleNamespace(returncode=0)),
    ):
        result = build_health.fix(_ctx(tmp_path), [issue])

    assert result.success is True
    assert result.fix_type == "code-fix"
    assert "Resolved build errors without new local changes" in result.summary
    assert result.changes == []
    assert result.actions == [{"resolved": "apps/dashboard/scripts/generate-tab-registry.ts", "changes": []}]
    commit_files.assert_not_called()


def test_fix_unresolved_issues_return_report_not_failure(tmp_path: Path):
    """When CLI runs but tsc still fails, return report-only, not failure."""
    issue = {
        "file": "tests/dashboard/python/OverviewTab.test.tsx",
        "errors": ["error TS2307: Cannot find module"],
    }

    with (
        patch.object(build_health, "_find_cli", return_value="/opt/homebrew/bin/codex"),
        patch.object(build_health, "_verify_dashboard_build", return_value=SimpleNamespace(returncode=1)),
        patch.object(build_health, "_list_changed_paths", return_value=set()),
        patch("build_health.subprocess.run", return_value=SimpleNamespace(returncode=0)),
    ):
        result = build_health.fix(_ctx(tmp_path), [issue])

    assert result.success is True
    assert result.fix_type == "report"
    assert "unresolved" in result.actions[0]


def test_fix_no_cli_returns_report_not_failure(tmp_path: Path):
    """When no CLI is available, return report-only, not failure."""
    issue = {
        "file": "apps/dashboard/lib/foo.ts",
        "errors": ["error TS2322"],
    }

    with patch.object(build_health, "_find_cli", side_effect=RuntimeError("no CLI")):
        result = build_health.fix(_ctx(tmp_path), [issue])

    assert result.success is True
    assert result.fix_type == "report"
    assert "no CLI" in result.summary
