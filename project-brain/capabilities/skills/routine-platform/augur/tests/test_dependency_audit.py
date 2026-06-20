"""Tests for auto-dependency-audit scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dependency_audit.py"
_SPEC = importlib.util.spec_from_file_location("dependency_audit_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_scan_no_dashboard(tmp_path: Path) -> None:
    result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert result.issues == []
    assert "No dashboard" in result.summary


def test_scan_npm_audit_fails(tmp_path: Path) -> None:
    """scan returns info when npm audit produces no output."""
    (tmp_path / "apps" / "dashboard").mkdir(parents=True)
    with patch.object(mod, "_npm_audit", return_value=None):
        result = mod.scan(_ctx(tmp_path))
    assert result.issues == []
    assert "failed" in result.summary.lower() or "no output" in result.summary.lower()


def test_npm_audit_does_not_generate_package_lock(tmp_path: Path) -> None:
    dashboard_dir = tmp_path / "apps" / "dashboard"
    dashboard_dir.mkdir(parents=True)

    with patch.object(mod.subprocess, "run") as run:
        run.return_value.stdout = '{"vulnerabilities": {}}'

        result = mod._npm_audit(dashboard_dir)

    assert result == {"vulnerabilities": {}}
    assert "--package-lock=false" in run.call_args.args[0]


def test_scan_no_vulnerabilities(tmp_path: Path) -> None:
    (tmp_path / "apps" / "dashboard").mkdir(parents=True)
    with patch.object(mod, "_npm_audit", return_value={"vulnerabilities": {}}):
        result = mod.scan(_ctx(tmp_path))
    assert result.issues == []
    assert "No vulnerabilities" in result.summary


def test_scan_finds_vulnerabilities(tmp_path: Path) -> None:
    (tmp_path / "apps" / "dashboard").mkdir(parents=True)
    with patch.object(mod, "_npm_audit", return_value={
        "vulnerabilities": {
            "lodash": {"severity": "high", "via": ["Prototype Pollution"], "fixAvailable": True},
        },
    }):
        result = mod.scan(_ctx(tmp_path))
    assert len(result.issues) == 1
    assert result.issues[0]["package"] == "lodash"
    assert result.severity == "error"


def test_scan_classifies_breaking_change_fix_as_manual(tmp_path: Path) -> None:
    # When npm's suggested fix is isSemVerMajor (breaking change), the issue
    # should be classified as manual/external — auto-fix won't take it and
    # leaving it as 'actionable' just produces noise on every loop run.
    (tmp_path / "apps" / "dashboard").mkdir(parents=True)
    with patch.object(mod, "_npm_audit", return_value={
        "vulnerabilities": {
            "next": {
                "severity": "moderate",
                "via": ["postcss"],
                "fixAvailable": {"name": "next", "version": "9.3.3", "isSemVerMajor": True},
            },
        },
    }):
        result = mod.scan(_ctx(tmp_path))
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue["package"] == "next"
    assert issue["kind"] == "external"
    assert issue["fixability"] == "manual"
    assert issue["root_cause_type"] == "external_dependency"


def test_scan_keeps_safe_fix_as_actionable(tmp_path: Path) -> None:
    # Non-breaking fixes (or no isSemVerMajor flag) stay actionable so the
    # loop's auto-fix path at d2+ can still apply them.
    (tmp_path / "apps" / "dashboard").mkdir(parents=True)
    with patch.object(mod, "_npm_audit", return_value={
        "vulnerabilities": {
            "lodash": {
                "severity": "high",
                "via": ["Prototype Pollution"],
                "fixAvailable": {"name": "lodash", "version": "4.17.22", "isSemVerMajor": False},
            },
        },
    }):
        result = mod.scan(_ctx(tmp_path))
    issue = result.issues[0]
    assert issue["kind"] == "actionable"
    assert issue["fixability"] == "auto"


def test_fix_dry_run(tmp_path: Path) -> None:
    result = mod.fix(_ctx(tmp_path, dry_run=True), [{"package": "lodash"}])
    assert isinstance(result, FixResult)
    assert result.success is True
    assert "Dry run" in result.summary


def test_declares_windows_report_only_capabilities() -> None:
    assert mod.OPS_CAPABILITIES.platforms == ("cross_platform",)
    assert mod.OPS_CAPABILITIES.windows_fix_mode == "report_only"
