"""Automatic command KPI loop entry."""
from __future__ import annotations

from typing import Any

from src.lib.ops_protocol import OpsContext, ScanResult, report_only_fix
from skills.evals.scripts import command_kpi_runner


name = "command-kpi"


def scan(ctx: OpsContext) -> ScanResult:
    result = command_kpi_runner.run_command_kpis(run_id=None)
    gate = result.get("gate") or {}
    issues = gate.get("issues") or []
    passed = bool(gate.get("passed"))
    summary = result.get("summary") or ("command KPI gate passed" if passed else "command KPI gate failed")
    return ScanResult(
        issues=issues,
        summary=summary,
        severity="info" if passed else "warning",
        health="verified" if passed else "degraded",
        items_scanned=int(result.get("scenario_count") or 0),
    )


def fix(ctx: OpsContext, issues: list[dict]) -> Any:
    return report_only_fix(ctx, "command-kpi-latest.json", issues, noun="command KPI issue")
