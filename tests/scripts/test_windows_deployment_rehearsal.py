from __future__ import annotations

from pathlib import Path

from scripts import windows_deployment_rehearsal as rehearsal


def test_rehearsal_plan_covers_windows_deployment_surfaces_without_windows_host(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    resolved_repo_root = repo_root.resolve()
    plan = rehearsal.build_plan(
        repo_root,
        powershell_executable=None,
        include_browser=False,
    )
    steps = {step.name: step for step in plan.steps}

    python_step = steps["python-windows-contracts"]
    python_command = " ".join(python_step.command)
    assert python_step.cwd == resolved_repo_root
    assert "tests/scripts/test_windows_one_click_bootstrap.py" in python_command
    assert "project-brain/capabilities/skills/onboard/augur/tests/test_windows_one_click.py" in python_command
    assert "project-brain/capabilities/skills/daemon/augur/tests/test_service_healer_registration.py" in python_command
    assert "tests/config/test_path_primitives.py" in python_command
    assert "tests/packages/augur-mcp/test_packaging.py" in python_command

    dashboard_step = steps["dashboard-windows-paths"]
    dashboard_command = " ".join(dashboard_step.command)
    assert dashboard_step.cwd == resolved_repo_root / "apps" / "dashboard"
    assert dashboard_step.command[:2] == ("pnpm", "jest")
    assert "../../tests/dashboard/api/cli-config.test.ts" in dashboard_command
    assert "../../tests/dashboard/lib/paths-discovery.test.ts" in dashboard_command
    assert "--runInBand" in dashboard_step.command

    assert "dashboard-browser-smoke" not in steps
    assert "PowerShell parser was not run" in plan.residual_risks


def test_rehearsal_plan_adds_powershell_parse_and_optional_browser_smoke(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    resolved_repo_root = repo_root.resolve()
    plan = rehearsal.build_plan(
        repo_root,
        powershell_executable="pwsh",
        include_browser=True,
    )
    steps = {step.name: step for step in plan.steps}

    powershell_step = steps["powershell-bootstrap-parser"]
    assert powershell_step.command[0] == "pwsh"
    assert "scriptblock" in " ".join(powershell_step.command).lower()
    assert "scripts/windows-one-click-bootstrap.ps1" in " ".join(powershell_step.command)

    browser_step = steps["dashboard-browser-smoke"]
    browser_command = " ".join(browser_step.command)
    assert browser_step.cwd == resolved_repo_root
    assert browser_step.command[:3] == ("uv", "run", "python")
    assert "verify_dashboard" in browser_command
    assert not plan.residual_risks


def test_rehearsal_exit_code_fails_only_on_required_failed_steps() -> None:
    results = [
        rehearsal.StepResult(name="python-windows-contracts", status="passed", duration_seconds=1.0),
        rehearsal.StepResult(
            name="dashboard-windows-paths",
            status="failed",
            duration_seconds=2.0,
            exit_code=1,
            output="failed",
        ),
        rehearsal.StepResult(name="powershell-bootstrap-parser", status="skipped", duration_seconds=0.0),
    ]

    assert rehearsal.exit_code_for_results(results) == 1
    assert rehearsal.exit_code_for_results(results[:1]) == 0
