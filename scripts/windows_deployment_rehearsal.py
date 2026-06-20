#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


PYTHON_WINDOWS_CONTRACT_TESTS: tuple[str, ...] = (
    "tests/scripts/test_windows_one_click_bootstrap.py",
    "tests/scripts/test_onboard_install_prompt.py",
    "tests/scripts/test_windows_ci_workflow.py",
    "tests/config/test_path_primitives.py",
    "tests/src/test_paths.py",
    "tests/packages/augur-mcp/test_packaging.py",
    "tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py::TestConfigureMcpRuntimeArgs::test_codex_cli_config_uses_powershell_launcher_on_windows",
    "project-brain/capabilities/skills/onboard/augur/tests/test_windows_one_click.py",
    "project-brain/capabilities/skills/daemon/augur/tests/test_service_healer_registration.py",
)

DASHBOARD_WINDOWS_TESTS: tuple[str, ...] = (
    "../../tests/dashboard/api/cli-config.test.ts",
    "../../tests/dashboard/lib/paths-discovery.test.ts",
)

POWERSHELL_PARSE_COMMAND = (
    "$ErrorActionPreference = 'Stop'; "
    "$null = [scriptblock]::Create((Get-Content -Path "
    "'scripts/windows-one-click-bootstrap.ps1' -Raw)); "
    "'parser ok'"
)

DASHBOARD_BROWSER_SMOKE_COMMAND = (
    "import json, sys; "
    "from pathlib import Path; "
    "sys.path.insert(0, str((Path('project-brain') / 'capabilities').resolve())); "
    "from skills.onboard.scripts.windows_one_click import verify_dashboard; "
    "result = verify_dashboard(Path('.').resolve()); "
    "print(json.dumps(result, sort_keys=True)); "
    "sys.exit(0 if result.get('ok') else 1)"
)


@dataclass(frozen=True)
class CommandStep:
    name: str
    command: tuple[str, ...]
    cwd: Path
    timeout_seconds: int
    description: str


@dataclass(frozen=True)
class RehearsalPlan:
    repo_root: Path
    steps: tuple[CommandStep, ...]
    residual_risks: tuple[str, ...]


@dataclass(frozen=True)
class StepResult:
    name: str
    status: str
    duration_seconds: float
    exit_code: int | None = None
    output: str = ""


def find_powershell() -> str | None:
    for candidate in ("pwsh", "powershell"):
        if shutil.which(candidate):
            return candidate
    return None


def build_plan(
    repo_root: Path,
    *,
    powershell_executable: str | None,
    include_browser: bool,
) -> RehearsalPlan:
    repo_root = repo_root.resolve()
    steps: list[CommandStep] = []
    residual_risks: list[str] = []

    if powershell_executable:
        steps.append(
            CommandStep(
                name="powershell-bootstrap-parser",
                command=(
                    powershell_executable,
                    "-NoProfile",
                    "-Command",
                    POWERSHELL_PARSE_COMMAND,
                ),
                cwd=repo_root,
                timeout_seconds=60,
                description="Parse the Windows PowerShell bootstrap script without executing it.",
            )
        )
    else:
        residual_risks.append("PowerShell parser was not run")

    steps.append(
        CommandStep(
            name="python-windows-contracts",
            command=("uv", "run", "pytest", *PYTHON_WINDOWS_CONTRACT_TESTS, "-q"),
            cwd=repo_root,
            timeout_seconds=300,
            description=(
                "Run Windows path, onboarding, daemon, MCP packaging, "
                "and CI-reachability contract tests."
            ),
        )
    )

    steps.append(
        CommandStep(
            name="dashboard-windows-paths",
            command=("pnpm", "jest", *DASHBOARD_WINDOWS_TESTS, "--runInBand"),
            cwd=repo_root / "apps" / "dashboard",
            timeout_seconds=180,
            description="Run dashboard Windows PATH and CLI-discovery Jest tests.",
        )
    )

    if include_browser:
        steps.append(
            CommandStep(
                name="dashboard-browser-smoke",
                command=("uv", "run", "python", "-c", DASHBOARD_BROWSER_SMOKE_COMMAND),
                cwd=repo_root,
                timeout_seconds=240,
                description=(
                    "Run the Windows onboarding Playwright smoke through the "
                    "repo-owned orchestrator."
                ),
            )
        )

    return RehearsalPlan(
        repo_root=repo_root,
        steps=tuple(steps),
        residual_risks=tuple(residual_risks),
    )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part for part in (result.stdout, result.stderr) if part).strip()


def run_step(step: CommandStep) -> StepResult:
    start = time.monotonic()
    try:
        completed = subprocess.run(
            list(step.command),
            cwd=step.cwd,
            text=True,
            capture_output=True,
            timeout=step.timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        return StepResult(
            name=step.name,
            status="failed",
            duration_seconds=time.monotonic() - start,
            output=str(exc),
        )
    except subprocess.TimeoutExpired as exc:
        command = " ".join(str(part) for part in exc.cmd)
        return StepResult(
            name=step.name,
            status="failed",
            duration_seconds=time.monotonic() - start,
            output=f"timed out after {exc.timeout} seconds: {command}",
        )

    return StepResult(
        name=step.name,
        status="passed" if completed.returncode == 0 else "failed",
        duration_seconds=time.monotonic() - start,
        exit_code=completed.returncode,
        output=_combined_output(completed),
    )


def run_plan(plan: RehearsalPlan) -> list[StepResult]:
    return [run_step(step) for step in plan.steps]


def exit_code_for_results(results: Sequence[StepResult]) -> int:
    return 1 if any(result.status == "failed" for result in results) else 0


def _clip_output(output: str, limit: int = 1800) -> str:
    if len(output) <= limit:
        return output
    return output[:limit] + "\n... output clipped ..."


def render_text_report(plan: RehearsalPlan, results: Sequence[StepResult]) -> str:
    lines = [
        "Windows deployment rehearsal",
        f"repo_root: {plan.repo_root}",
        "",
    ]
    for result in results:
        exit_text = "" if result.exit_code is None else f" exit={result.exit_code}"
        lines.append(f"[{result.status}] {result.name} ({result.duration_seconds:.1f}s){exit_text}")
        if result.output:
            lines.append(_clip_output(result.output))
            lines.append("")

    if plan.residual_risks:
        lines.append("Residual risks")
        lines.extend(f"- {risk}" for risk in plan.residual_risks)
        lines.append(
            "- Task Scheduler execution and Windows ACL behavior still require a real Windows host."
        )

    return "\n".join(lines).rstrip() + "\n"


def _json_payload(plan: RehearsalPlan, results: Sequence[StepResult]) -> dict[str, object]:
    return {
        "repo_root": str(plan.repo_root),
        "steps": [
            {
                **asdict(step),
                "cwd": str(step.cwd),
                "command": list(step.command),
            }
            for step in plan.steps
        ],
        "results": [asdict(result) for result in results],
        "residual_risks": list(plan.residual_risks),
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the strongest Windows first-deployment checks available from "
            "this non-Windows checkout."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Augur repository root. Defaults to this script's repository.",
    )
    parser.add_argument(
        "--include-browser",
        action="store_true",
        help="Also run the Playwright Windows onboarding browser smoke.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of text.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    plan = build_plan(
        args.repo_root,
        powershell_executable=find_powershell(),
        include_browser=args.include_browser,
    )
    results = run_plan(plan)
    if args.json:
        print(json.dumps(_json_payload(plan, results), indent=2, sort_keys=True))
    else:
        print(render_text_report(plan, results), end="")
    return exit_code_for_results(results)


if __name__ == "__main__":
    raise SystemExit(main())
