"""auto-analytics: Generate usage analytics from LLM execution logs.

Extracted from KnowledgeEnrichmentLoop._run_analytics (ADR-200).
Inlined generate_analytics to avoid cross-plugin import of nightly_maintainer.py,
which has heavy MCP module-level imports that fail outside daemon context.
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
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from src.config.paths import get_logs_dir, get_runtime_dir
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

name = "auto-analytics"


def _generate_analytics(log_file: Path) -> str:
    """Generate aggregated usage stats from LLM execution logs.

    Inlined from nightly_maintainer.generate_analytics to avoid loading
    MCP imports (prune_stale_sessions etc.) that break outside daemon context.
    """
    from src.config.paths import get_runtime_dir

    if not log_file.exists():
        return "No log file found"

    stats = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_requests": 0,
        "total_cost": 0.0,
        "total_tokens": 0,
        "errors": 0,
        "by_provider": defaultdict(lambda: {"cost": 0.0, "tokens": 0, "requests": 0}),
        "by_model": defaultdict(lambda: {"cost": 0.0, "tokens": 0, "requests": 0}),
    }

    with open(log_file, "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
                cost = entry.get("cost", 0.0)
                tokens = entry.get("total_tokens", 0)
                provider = entry.get("provider", "unknown")
                model = entry.get("model", "unknown")

                stats["total_requests"] += 1
                stats["total_cost"] += cost
                stats["total_tokens"] += tokens

                if not entry.get("success", True):
                    stats["errors"] += 1

                stats["by_provider"][provider]["cost"] += cost
                stats["by_provider"][provider]["tokens"] += tokens
                stats["by_provider"][provider]["requests"] += 1

                stats["by_model"][model]["cost"] += cost
                stats["by_model"][model]["tokens"] += tokens
                stats["by_model"][model]["requests"] += 1
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

    stats_dir = get_runtime_dir() / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)
    summary_file = stats_dir / "usage_summary.json"

    with open(summary_file, "w") as f:
        json.dump(stats, f, indent=2)

    return f"${stats['total_cost']:.4f} / {stats['total_tokens']} tokens / {stats['total_requests']} requests"


def scan(ctx: OpsContext) -> ScanResult:
    """Generate analytics only when fresh LLM logs need summarizing."""
    del ctx
    log_file = get_logs_dir() / "llm_logs.jsonl"
    summary_file = get_runtime_dir() / "stats" / "usage_summary.json"

    if not log_file.exists():
        return ScanResult(
            issues=[],
            summary="No LLM logs to summarize",
            severity="info",
        )

    if summary_file.exists() and summary_file.stat().st_mtime >= log_file.stat().st_mtime:
        return ScanResult(
            issues=[],
            summary="Analytics are current",
            severity="info",
        )

    return ScanResult(
        issues=[{"action": "generate-analytics", "category": "analytics-generation"}],
        summary="Analytics generation needed",
        severity="info",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Generate usage analytics from LLM logs."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary="Dry run: would generate analytics",
        )

    try:
        from src.config.paths import get_logs_dir

        log_file = get_logs_dir() / "llm_logs.jsonl"
        summary = _generate_analytics(log_file)
        return FixResult(
            success=True,
            summary=f"Analytics generated: {summary}",
        )
    except Exception as e:
        return FixResult(
            success=False,
            summary=f"Analytics generation failed: {e}",
        )
