"""auto-dependency-audit: npm audit vulnerability scanner and fixer.

Runs ``npm audit --json`` in the dashboard directory, parses
vulnerabilities, and optionally runs ``npm audit fix`` at higher
difficulty levels.  Never performs major upgrades.

See ADR-200 for the scan-fix protocol.
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
import subprocess
from pathlib import Path

from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    declare_ops_capabilities,
    write_report,
)

name = "auto-dependency-audit"
OPS_CAPABILITIES = declare_ops_capabilities(
    platforms=("cross_platform",),
    windows_fix_mode="report_only",
    skip_reason="npm audit fix stays report-only on Windows in v1",
)


# ---------------------------------------------------------------------------
# Helpers (patchable)
# ---------------------------------------------------------------------------

def _npm_audit(dashboard_dir: Path, timeout: int = 120) -> dict | None:
    """Run ``npm audit --json`` and return parsed output, or *None* on failure."""
    try:
        result = subprocess.run(
            ["npm", "audit", "--json", "--package-lock=false"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(dashboard_dir),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    # npm audit exits non-zero when vulnerabilities exist — that is expected
    if not result.stdout or not result.stdout.strip():
        return None

    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return None


def _npm_audit_fix(dashboard_dir: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """Run ``npm audit fix`` (never ``--force``, never major upgrades)."""
    return subprocess.run(
        ["npm", "audit", "fix"],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(dashboard_dir),
    )


# ---------------------------------------------------------------------------
# Protocol entry points
# ---------------------------------------------------------------------------

def scan(ctx: OpsContext) -> ScanResult:
    """Detect npm vulnerabilities in the dashboard."""
    dashboard_dir = ctx.project_root / "apps" / "dashboard"
    if not dashboard_dir.exists():
        return ScanResult(issues=[], summary="No dashboard directory", severity="info")

    audit_data = _npm_audit(dashboard_dir)
    if audit_data is None:
        return ScanResult(
            issues=[],
            summary="npm audit failed or produced no output",
            severity="info",
        )

    vulnerabilities = audit_data.get("vulnerabilities", {})
    if not vulnerabilities:
        return ScanResult(issues=[], summary="No vulnerabilities found", severity="info")

    issues: list[dict] = []
    for pkg_name, info in vulnerabilities.items():
        fix_available = info.get("fixAvailable", False)
        # When npm flags the suggested fix as isSemVerMajor (a breaking change
        # — usually a major-version downgrade or upgrade we cannot apply
        # automatically) treat the issue as manual/external. The default
        # 'npm audit fix' path skips these too, so leaving them classified
        # as actionable just produces noise on every loop run.
        is_breaking = (
            isinstance(fix_available, dict)
            and bool(fix_available.get("isSemVerMajor"))
        )
        issues.append({
            "package": pkg_name,
            "severity": info.get("severity", "unknown"),
            "via": [str(v) if isinstance(v, str) else v.get("title", "") for v in info.get("via", [])],
            "fixAvailable": fix_available,
            "kind": "external" if is_breaking else "actionable",
            "fixability": "manual" if is_breaking else "auto",
            "root_cause_type": "external_dependency" if is_breaking else "unknown",
        })

    max_sev = "info"
    for issue in issues:
        sev = issue.get("severity", "info")
        if sev in ("critical", "high"):
            max_sev = "error"
            break
        if sev == "moderate":
            max_sev = "warning"

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} vulnerable package(s)",
        severity=max_sev,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix vulnerabilities: report-only at low difficulty, npm audit fix at >= 2."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would address {len(issues)} vulnerabilities",
        )

    dashboard_dir = ctx.project_root / "apps" / "dashboard"

    if ctx.difficulty >= 2 and dashboard_dir.exists():
        # Skip npm audit fix when every remaining vulnerability is classified
        # as external/breaking — npm's safe (non-force) audit fix path won't
        # apply those, so calling it just produces a misleading 'fix failed'
        # summary every run. The breaking-change vulns surface in the report
        # for manual review instead.
        all_external = bool(issues) and all(
            issue.get("kind") == "external" for issue in issues
        )
        if all_external:
            report = {
                "vulnerabilities": issues,
                "fix_applied": False,
                "reason": "all vulnerabilities require manual review (breaking-change fixes)",
            }
            summary = (
                f"{len(issues)} vulnerability(ies) require manual review "
                "— npm audit's safe fix path cannot apply breaking-change downgrades"
            )
        else:
            result = _npm_audit_fix(dashboard_dir)
            fix_applied = result.returncode == 0
            report = {
                "vulnerabilities": issues,
                "fix_applied": fix_applied,
                "fix_output": result.stdout[:1000] if result.stdout else "",
            }
            summary = "npm audit fix applied" if fix_applied else "npm audit fix failed"
    else:
        report = {
            "vulnerabilities": issues,
            "fix_applied": False,
            "reason": "difficulty < 2, report only",
        }
        summary = f"Report only: {len(issues)} vulnerabilities (difficulty {ctx.difficulty})"

    report_path = write_report(ctx, "dependency-audit-latest.json", report)

    return FixResult(
        success=True,
        actions=[{"report": str(report_path)}],
        changes=[],
        summary=summary,
    )
