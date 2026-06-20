"""auto-context-audit: Monitor agent context token usage against budgets.

Reads state/mcp/context_stats.json and flags agents whose token count
exceeds the configured budget (default 100,000 tokens).  Fix generates
a structured report at state/reports/context-audit-latest.json.

See ADR-200 for the auto-command protocol.
"""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import json
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import get_runtime_dir
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, write_report

name = "auto-context-audit"

DEFAULT_BUDGET = 100_000


# ---------------------------------------------------------------------------
# Helpers (patchable in tests)
# ---------------------------------------------------------------------------

def _gather_context_stats(project_root: Path) -> dict:
    """Read and return context_stats.json contents from runtime state."""
    del project_root
    stats_path = get_runtime_dir() / "mcp" / "context_stats.json"
    if not stats_path.exists():
        return {}
    return json.loads(stats_path.read_text())


# ---------------------------------------------------------------------------
# Protocol implementation
# ---------------------------------------------------------------------------

def scan(ctx: OpsContext) -> ScanResult:
    """Scan for agents exceeding token budget."""
    budget = ctx.config.get("budget", DEFAULT_BUDGET)
    stats = _gather_context_stats(ctx.project_root)
    issues: list[dict] = []

    agents = stats.get("agents", {})
    for agent_id, agent_data in agents.items():
        tokens = agent_data.get("tokens", 0)
        if tokens > budget:
            issues.append({
                "type": "over_budget",
                "agent": agent_id,
                "tokens": tokens,
                "budget": budget,
                "overage": tokens - budget,
            })

    severity = "warning" if issues else "info"
    summary = (
        f"{len(issues)} agent(s) over token budget ({budget:,})"
        if issues
        else f"All agents within token budget ({budget:,})"
    )
    return ScanResult(issues=issues, summary=summary, severity=severity)


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Generate a context audit report."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            actions=[{"action": "dry_run", "description": "Would generate context audit report"}],
            summary="Dry run — no report generated",
        )

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "budget": issues[0]["budget"] if issues and "budget" in issues[0] else DEFAULT_BUDGET,
        "over_budget_agents": [
            {
                "agent": i["agent"],
                "tokens": i["tokens"],
                "budget": i["budget"],
                "overage": i["overage"],
            }
            for i in issues
        ],
        "count": len(issues),
    }
    report_path = write_report(ctx, "context-audit-latest.json", report)

    return FixResult(
        success=True,
        actions=[{"action": "generate_report", "path": str(report_path)}],
        changes=[f"Wrote context audit report to {report_path}"],
        summary=f"Generated context audit report with {len(issues)} finding(s)",
        fix_type="report",
    )
