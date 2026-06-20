"""auto-test-onboarding-probes: fixture-backed setup-completeness probe tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from src.lib.ops_protocol import OpsContext, ScanResult, report_only_fix


name = "auto-test-onboarding-probes"

TEST_PATHS = [
    "project-brain/capabilities/skills/onboard/augur/tests/test_setup_registry.py",
    "project-brain/capabilities/skills/onboard/augur/tests/test_setup_aggregator.py",
    "project-brain/capabilities/skills/onboard/augur/tests/test_setup_mcp_tools.py",
]


def _python(project_root: Path) -> str:
    venv = project_root / ".venv" / "bin" / "python3"
    if venv.exists():
        return str(venv)
    return sys.executable or "python3"


def scan(ctx: OpsContext) -> ScanResult:
    missing = [path for path in TEST_PATHS if not (ctx.project_root / path).exists()]
    if missing:
        return ScanResult(
            issues=[{"missing": missing}],
            summary="Onboarding probe test files are missing",
            severity="error",
        )

    pythonpath = ":".join(
        [
            str(ctx.project_root),
            str(ctx.project_root / "project-brain"),
            str(ctx.project_root / "project-brain" / "capabilities" / "skills" / "onboard" / "scripts"),
            str(ctx.project_root / "project-brain" / "capabilities" / "skills" / "onboard" / "scripts" / "mcp"),
        ]
    )
    cmd = [_python(ctx.project_root), "-m", "pytest", *TEST_PATHS, "-q"]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(ctx.project_root),
            capture_output=True,
            text=True,
            timeout=int(ctx.config.get("timeout", 120)),
            env={**os.environ, "PYTHONPATH": pythonpath},
        )
    except subprocess.TimeoutExpired:
        return ScanResult(
            issues=[{"error": "onboarding probe tests timed out"}],
            summary="Onboarding probe tests timed out",
            severity="error",
        )

    if result.returncode == 0:
        return ScanResult(
            issues=[],
            summary=f"Onboarding probe tests passed: {result.stdout.strip()[-120:]}",
            severity="info",
            health="verified",
        )
    return ScanResult(
        issues=[{"exit_code": result.returncode, "stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:]}],
        summary=f"Onboarding probe tests failed (exit {result.returncode})",
        severity="error",
    )


def fix(ctx: OpsContext, issues: list[dict]):
    return report_only_fix(ctx, "auto-test-onboarding-probes.json", issues, noun="onboarding probe failure")
