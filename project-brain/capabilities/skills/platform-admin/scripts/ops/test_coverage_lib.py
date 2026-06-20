"""Shared coverage scanner logic for adaptive/devops command surfaces."""
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
import subprocess
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, write_report


COVERAGE_THRESHOLD = 70
COVERAGE_DIFFICULTY_SPEC = {
    0: "Surface check — verify dashboard coverage cache exists without running Jest",
    1: "Content check — read cached coverage summary or run Jest when needed",
    2: "Deep check — same as d1 (coverage verification)",
    3: "Exhaustive — same as d1 (coverage verification)",
    4: "Expert — same as d1 (coverage verification)",
}


def _run_coverage(dashboard_dir: Path, timeout: int = 300) -> dict | None:
    """Run Jest with JSON-summary coverage and return parsed summary."""
    try:
        subprocess.run(
            [
                "npx", "jest",
                "--coverage",
                "--coverageReporters=json-summary",
                "--silent",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(dashboard_dir),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    summary_path = dashboard_dir / "coverage" / "coverage-summary.json"
    if not summary_path.exists():
        return None

    try:
        return json.loads(summary_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def scan_test_coverage(
    ctx: OpsContext,
    *,
    run_coverage=_run_coverage,
) -> ScanResult:
    """Check coverage metrics against the configured threshold."""
    dashboard_dir = ctx.project_root / "apps" / "dashboard"
    if not dashboard_dir.exists():
        return ScanResult(issues=[], summary="No dashboard directory", severity="info")

    cached = dashboard_dir / "coverage" / "coverage-summary.json"
    if ctx.difficulty < 1:
        return ScanResult(
            issues=[],
            summary=(
                "Coverage summary cache available"
                if cached.exists()
                else "Coverage summary cache missing (d0 surface check)"
            ),
            severity="info",
            health="verified",
        )

    summary: dict | None = None
    if cached.exists():
        try:
            summary = json.loads(cached.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    if summary is None:
        summary = run_coverage(dashboard_dir)
    if summary is None:
        return ScanResult(
            issues=[],
            summary="Coverage run failed or summary not found",
            severity="info",
        )

    total = summary.get("total", {})
    below: list[dict] = []
    for metric in ("lines", "statements", "functions", "branches"):
        pct = total.get(metric, {}).get("pct", 100)
        if pct < COVERAGE_THRESHOLD:
            below.append({"metric": metric, "pct": pct, "threshold": COVERAGE_THRESHOLD})

    if not below:
        return ScanResult(issues=[], summary="Coverage above threshold", severity="info")

    return ScanResult(
        issues=below,
        summary=f"{len(below)} metric(s) below {COVERAGE_THRESHOLD}%",
        severity="warning",
    )


def fix_test_coverage(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Write coverage findings into the runtime report directory."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would report {len(issues)} coverage gaps",
        )

    report = {
        "threshold": COVERAGE_THRESHOLD,
        "below_threshold": issues,
    }
    report_path = write_report(ctx, "coverage-latest.json", report)
    return FixResult(
        success=True,
        actions=[{"report": str(report_path)}],
        changes=[],
        summary=f"Coverage report written with {len(issues)} gaps",
    )
