"""Structural toy auto-command for ADR-755 orchestrator tests."""
from __future__ import annotations

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult


name = "auto-struct"


def scan(ctx: OpsContext) -> ScanResult:
    """Return one issue that should be routed through design gating."""
    issue = {
        "kind": "manual",
        "severity": "error",
        "path": "fixtures/toy_loop/auto_struct.py",
        "detail": "Changing scheduler ownership requires a design gate.",
        "scheduler_change": True,
        "design_gate": True,
        "fixability": "design-gated",
    }
    return ScanResult(
        issues=[issue],
        summary="1 structural toy issue",
        severity="error",
        items_scanned=1,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Report the design-gated action without mutating files."""
    return FixResult(
        success=True,
        actions=[{"kind": "design-gate", "issues": len(issues)}],
        summary="Structural toy issue requires design gate before mutation.",
        fix_type="report",
    )
