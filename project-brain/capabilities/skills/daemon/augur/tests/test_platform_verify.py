"""Tests for the shared adaptive platform verification runner."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.lib.ops_protocol import ScanResult, declare_ops_capabilities

from skills.daemon.scripts.adaptive import platform_verify as mod


def _entry(
    *,
    name: str,
    loop_name: str,
    capabilities,
    scan_result: ScanResult | None = None,
) -> SimpleNamespace:
    result = scan_result or ScanResult(issues=[], summary="clean", severity="info")
    module = SimpleNamespace(scan=lambda ctx: result, OPS_CAPABILITIES=capabilities)
    return SimpleNamespace(
        name=name,
        loop_name=loop_name,
        capabilities=capabilities,
        module=module,
        config={},
    )


def test_main_reports_report_only_entries(tmp_path: Path, capsys) -> None:
    registry = {
        "auto-dependency-audit": _entry(
            name="auto-dependency-audit",
            loop_name="hardening",
            capabilities=declare_ops_capabilities(
                platforms=("cross_platform",),
                windows_fix_mode="report_only",
            ),
            scan_result=ScanResult(
                issues=[{"package": "lodash"}],
                summary="1 vulnerable package",
                severity="warning",
            ),
        )
    }

    with patch.object(mod, "discover_auto_commands", return_value=registry):
        exit_code = mod.main([
            "--loop",
            "hardening",
            "--platform",
            "windows",
            "--mode",
            "verify",
            "--project-root",
            str(tmp_path),
        ])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "auto-dependency-audit: report_only" in captured.out
    assert "actionable=1" in captured.out
    assert "summary: 1 supported, 1 report_only, 0 skipped, 1 failed" in captured.out


def test_main_skips_unsupported_entries_without_failure(tmp_path: Path, capsys) -> None:
    registry = {
        "auto-macos-only": _entry(
            name="auto-macos-only",
            loop_name="hardening",
            capabilities=declare_ops_capabilities(
                platforms=("macos",),
                windows_fix_mode="unsupported",
                skip_reason="launchd-only check",
            ),
        )
    }

    with patch.object(mod, "discover_auto_commands", return_value=registry):
        exit_code = mod.main([
            "--loop",
            "hardening",
            "--platform",
            "windows",
            "--mode",
            "verify",
            "--project-root",
            str(tmp_path),
        ])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "skipped_unsupported" in captured.out
    assert "launchd-only check" in captured.out
    assert "summary: 0 supported, 0 report_only, 1 skipped, 0 failed" in captured.out


def test_verify_ignores_maintenance_only_findings(tmp_path: Path, capsys) -> None:
    registry = {
        "auto-evolution-gap": _entry(
            name="auto-evolution-gap",
            loop_name="hardening",
            capabilities=declare_ops_capabilities(
                platforms=("cross_platform",),
                windows_fix_mode="report_only",
            ),
            scan_result=ScanResult(
                issues=[{"kind": "maintenance", "message": "add more Windows coverage"}],
                summary="1 maintenance gap",
                severity="info",
            ),
        )
    }

    with patch.object(mod, "discover_auto_commands", return_value=registry):
        exit_code = mod.main([
            "--loop",
            "hardening",
            "--platform",
            "windows",
            "--mode",
            "verify",
            "--project-root",
            str(tmp_path),
        ])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "actionable=" not in captured.out
    assert "summary: 1 supported, 1 report_only, 0 skipped, 0 failed" in captured.out


def test_verify_ignores_scanner_defect_findings(tmp_path: Path, capsys) -> None:
    registry = {
        "auto-scanner-defect": _entry(
            name="auto-scanner-defect",
            loop_name="hardening",
            capabilities=declare_ops_capabilities(
                platforms=("cross_platform",),
                windows_fix_mode="report_only",
            ),
            scan_result=ScanResult(
                issues=[{"kind": "scanner-defect", "message": "mocked parser drift"}],
                summary="1 scanner defect",
                severity="warning",
            ),
        )
    }

    with patch.object(mod, "discover_auto_commands", return_value=registry):
        exit_code = mod.main([
            "--loop",
            "hardening",
            "--platform",
            "windows",
            "--mode",
            "verify",
            "--project-root",
            str(tmp_path),
        ])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "actionable=" not in captured.out
    assert "summary: 1 supported, 1 report_only, 0 skipped, 0 failed" in captured.out


def test_verify_ignores_external_manual_findings(tmp_path: Path, capsys) -> None:
    registry = {
        "auto-dependency-audit": _entry(
            name="auto-dependency-audit",
            loop_name="hardening",
            capabilities=declare_ops_capabilities(
                platforms=("cross_platform",),
                windows_fix_mode="report_only",
            ),
            scan_result=ScanResult(
                issues=[
                    {
                        "kind": "external",
                        "fixability": "manual",
                        "root_cause_type": "external_dependency",
                        "package": "next",
                    }
                ],
                summary="1 upstream advisory needs manual review",
                severity="warning",
            ),
        )
    }

    with patch.object(mod, "discover_auto_commands", return_value=registry):
        exit_code = mod.main([
            "--loop",
            "hardening",
            "--platform",
            "windows",
            "--mode",
            "verify",
            "--project-root",
            str(tmp_path),
        ])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "actionable=" not in captured.out
    assert "summary: 1 supported, 1 report_only, 0 skipped, 0 failed" in captured.out


def test_verify_skips_entries_without_declared_capabilities(tmp_path: Path, capsys) -> None:
    registry = {
        "auto-legacy-check": SimpleNamespace(
            name="auto-legacy-check",
            loop_name="hardening",
            capabilities=declare_ops_capabilities(),
            module=SimpleNamespace(scan=lambda ctx: ScanResult(issues=[], summary="clean", severity="info")),
            config={},
        )
    }

    with patch.object(mod, "discover_auto_commands", return_value=registry):
        exit_code = mod.main([
            "--loop",
            "hardening",
            "--platform",
            "windows",
            "--mode",
            "verify",
            "--project-root",
            str(tmp_path),
        ])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "auto-legacy-check: skipped_unsupported" in captured.out
    assert "OPS_CAPABILITIES not declared" in captured.out
    assert "summary: 0 supported, 0 report_only, 1 skipped, 0 failed" in captured.out


def test_verify_does_not_fail_on_broken_health_without_actionable_findings(tmp_path: Path, capsys) -> None:
    registry = {
        "auto-diagnostic": _entry(
            name="auto-diagnostic",
            loop_name="hardening",
            capabilities=declare_ops_capabilities(
                platforms=("cross_platform",),
                windows_fix_mode="report_only",
            ),
            scan_result=ScanResult(
                issues=[{"kind": "scanner-defect", "message": "parser drift"}],
                summary="scanner drift",
                severity="warning",
                health="broken",
            ),
        )
    }

    with patch.object(mod, "discover_auto_commands", return_value=registry):
        exit_code = mod.main([
            "--loop",
            "hardening",
            "--platform",
            "windows",
            "--mode",
            "verify",
            "--project-root",
            str(tmp_path),
        ])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "scan=broken" in captured.out
    assert "actionable=" not in captured.out
    assert "summary: 1 supported, 1 report_only, 0 skipped, 0 failed" in captured.out
