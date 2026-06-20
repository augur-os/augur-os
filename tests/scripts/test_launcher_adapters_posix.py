from __future__ import annotations

from pathlib import Path

from tests.scripts.launcher_test_utils import run_bash_script

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_posix_adapters_delegate_to_python_core_not_ai_launch_sh() -> None:
    for script in ["xa-launch.sh", "ca-launch.sh", "ga-launch.sh", "gca-launch.sh"]:
        text = (PROJECT_ROOT / "scripts" / script).read_text(encoding="utf-8")
        assert "src.scripts.agent_launch" in text
        assert "ai-launch.sh" not in text
        assert "worktree-launch.sh" not in text


def test_posix_xa_help_still_works() -> None:
    result = run_bash_script(PROJECT_ROOT / "scripts" / "xa-launch.sh", "--help", cwd=PROJECT_ROOT)

    assert result.returncode == 0, result.stderr
    assert "codex" in result.stdout.lower()
    assert "worktree" in result.stdout
    assert "desktop" in result.stdout


def test_posix_missing_python_error_lists_attempted_runtimes() -> None:
    for script in ["xa-launch.sh", "ca-launch.sh", "ga-launch.sh", "gca-launch.sh"]:
        text = (PROJECT_ROOT / "scripts" / script).read_text(encoding="utf-8")
        assert "Attempted:" in text
        assert ".venv/bin/python" in text
        assert ".venv/Scripts/python.exe" in text
        assert "uv run python" in text
