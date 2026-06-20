"""Mechanical toy auto-command for ADR-755 orchestrator tests."""
from __future__ import annotations

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult


name = "auto-mech"


def scan(ctx: OpsContext) -> ScanResult:
    """Return one narrow autofixable issue."""
    issue = {
        "kind": "actionable",
        "severity": "warning",
        "path": "fixtures/toy_loop/auto_mech.py",
        "detail": "Tool name has a deterministic typo.",
        "tool_name_mismatch": True,
        "autofix": True,
        "fixability": "auto",
    }
    return ScanResult(
        issues=[issue],
        summary="1 mechanical toy issue",
        severity="warning",
        items_scanned=1,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Return one deterministic action for the mechanical issue."""
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} issue(s)")
    return FixResult(
        success=True,
        actions=[{"kind": "rename", "from": "toy-toool", "to": "toy-tool"}],
        changes=["fixtures/toy_loop/tool-name.txt"],
        summary="Renamed deterministic toy tool reference.",
        fix_type="code-fix",
    )
