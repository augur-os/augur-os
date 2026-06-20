from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def powershell_exe() -> str:
    found = shutil.which("powershell.exe") or shutil.which("powershell")
    if not found:
        pytest.skip("Windows PowerShell is not available on this host")
    return found


def run_ps(script: str, *args: str, input_text: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            powershell_exe(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PROJECT_ROOT / script),
            *args,
        ],
        cwd=PROJECT_ROOT,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )


def test_xa_help_runs_without_bash() -> None:
    result = run_ps("scripts/xa-launch.ps1", "--help")

    assert result.returncode == 0, result.stderr
    assert "codex" in result.stdout.lower()
    assert "main" in result.stdout
    assert "worktree" in result.stdout
    assert "desktop" in result.stdout


def test_xa_dry_run_main_uses_python_core() -> None:
    result = run_ps("scripts/xa-launch.ps1", "--dry-run", input_text="1\n")

    assert result.returncode == 0, result.stderr
    assert "mode=main" in result.stdout
    assert "codex --dangerously-bypass-approvals-and-sandbox" in result.stdout


def test_xa_desktop_dry_run_opens_codex_desktop_without_prompt() -> None:
    result = run_ps("scripts/xa-launch.ps1", "--desktop", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "mode=desktop" in result.stdout
    assert "codex app" in result.stdout


def test_ca_and_ga_help_run_without_bash() -> None:
    for script, client in [
        ("scripts/ca-launch.ps1", "claude"),
        ("scripts/ga-launch.ps1", "gemini"),
        ("scripts/gca-launch.ps1", "copilot"),
    ]:
        result = run_ps(script, "--help")
        assert result.returncode == 0, result.stderr
        assert client in result.stdout.lower()


def test_powershell_adapters_do_not_call_bash_or_sh() -> None:
    for script in ["xa-launch.ps1", "ca-launch.ps1", "ga-launch.ps1", "gca-launch.ps1"]:
        text = (PROJECT_ROOT / "scripts" / script).read_text(encoding="utf-8")
        lowered = text.lower()
        assert "bash" not in lowered
        assert ".sh" not in lowered


def test_powershell_adapters_run_python_from_repo_root() -> None:
    for script in ["xa-launch.ps1", "ca-launch.ps1", "ga-launch.ps1", "gca-launch.ps1"]:
        text = (PROJECT_ROOT / "scripts" / script).read_text(encoding="utf-8")
        assert "Push-Location $RepoRoot" in text
        assert "Pop-Location" in text


def test_powershell_missing_python_error_lists_attempted_runtimes() -> None:
    for script in ["xa-launch.ps1", "ca-launch.ps1", "ga-launch.ps1", "gca-launch.ps1"]:
        text = (PROJECT_ROOT / "scripts" / script).read_text(encoding="utf-8")
        assert "Attempted:" in text
        assert ".venv\\Scripts\\python.exe" in text
        assert "uv run python" in text


def test_powershell_adapters_have_directory_transition_logic() -> None:
    for script in ["xa-launch.ps1", "ca-launch.ps1", "ga-launch.ps1", "gca-launch.ps1"]:
        text = (PROJECT_ROOT / "scripts" / script).read_text(encoding="utf-8")
        assert "AUGUR_LAST_WORKTREE_FILE" in text
        assert "GetTempFileName()" in text
        assert "Set-Location" in text
        assert "Remove-Item $TempFile" in text
