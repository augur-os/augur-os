from __future__ import annotations

import os
import subprocess
from pathlib import Path

from tests.scripts.launcher_test_utils import run_bash_script

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "ca-launch.sh"


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


def test_help_mentions_claude() -> None:
    result = run_script("--help")

    assert result.returncode == 0
    assert "claude" in result.stdout.lower()


def test_dry_run_main_includes_claude_skip_permissions_flag() -> None:
    result = run_script("--dry-run", input_text="1\n")

    assert result.returncode == 0, result.stderr
    assert "claude --dangerously-skip-permissions" in result.stdout


def test_dry_run_worktree_routes_to_worktree_launch_with_claude() -> None:
    result = run_script("--dry-run", input_text="2\n")

    assert result.returncode == 0, result.stderr
    assert "create-worktree -- claude" in result.stdout
