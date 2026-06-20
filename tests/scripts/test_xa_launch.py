from __future__ import annotations

import os
import subprocess
from pathlib import Path

from tests.scripts.launcher_test_utils import run_bash_script

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "xa-launch.sh"


def run_script(
    *args: str,
    input_text: str = "",
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return run_bash_script(
        SCRIPT,
        *args,
        cwd=PROJECT_ROOT,
        input_text=input_text,
        env=merged_env,
    )


def test_help_mentions_codex_and_main_or_worktree() -> None:
    result = run_script("--help")

    assert result.returncode == 0, result.stderr
    assert "codex" in result.stdout.lower()
    assert "main" in result.stdout
    assert "worktree" in result.stdout
    assert "desktop" in result.stdout


def test_desktop_dry_run_opens_codex_desktop_without_prompt() -> None:
    result = run_script("--desktop", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "mode=desktop" in result.stdout
    assert "codex app" in result.stdout


def test_dry_run_main_mode_forwards_to_ai_launch_with_codex_flags() -> None:
    result = run_script("--dry-run", input_text="1\n")

    assert result.returncode == 0, result.stderr
    assert "mode=main" in result.stdout
    assert "codex --dangerously-bypass-approvals-and-sandbox" in result.stdout


def test_dry_run_worktree_mode_forwards_to_worktree_launch() -> None:
    result = run_script("--dry-run", input_text="2\n")

    assert result.returncode == 0, result.stderr
    assert "mode=worktree" in result.stdout
    assert "create-worktree -- codex" in result.stdout


def test_extra_args_after_dashdash_are_forwarded_to_codex() -> None:
    result = run_script("--dry-run", "--", "--resume", "abc123", input_text="1\n")

    assert result.returncode == 0, result.stderr
    assert "codex --dangerously-bypass-approvals-and-sandbox --resume abc123" in result.stdout


def test_client_flags_without_dashdash_are_forwarded_to_codex() -> None:
    result = run_script("--dry-run", "--version", input_text="1\n")

    assert result.returncode == 0, result.stderr
    assert "codex --dangerously-bypass-approvals-and-sandbox --version" in result.stdout


def test_choose_main_selects_main_without_prompt_or_forwarding_words() -> None:
    result = run_script("--dry-run", "choose", "main")

    assert result.returncode == 0, result.stderr
    assert "mode=main" in result.stdout
    assert "command=codex --dangerously-bypass-approvals-and-sandbox\n" in result.stdout
    assert "choose main" not in result.stdout


def test_worktree_mode_respects_project_root_and_forwards_codex(tmp_path: Path) -> None:
    from tests.scripts.test_ai_launch import init_main_repo_pair

    local, _ = init_main_repo_pair(tmp_path)

    result = run_script(
        "--dry-run",
        input_text="2\n",
        env={
            "AI_PROJECT_ROOT": str(local),
            "AI_NO_EXEC": "1",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "mode=worktree" in result.stdout
    assert "codex --dangerously-bypass-approvals-and-sandbox" in result.stdout
