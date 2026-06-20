from __future__ import annotations

import os
import subprocess
from pathlib import Path

from tests.scripts.launcher_test_utils import run_bash_script

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "ai-launch.sh"


def run_script(*args: str, input_text: str = "", env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
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


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def configure_repo(repo: Path) -> None:
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test User")


def init_main_repo_pair(tmp_path: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin.git"
    seed = tmp_path / "seed"
    local = tmp_path / "local"
    upstream = tmp_path / "upstream"

    git(tmp_path, "init", "--bare", str(origin))
    git(tmp_path, "clone", str(origin), str(seed))
    configure_repo(seed)
    git(seed, "checkout", "-b", "main")
    (seed / "tracked.txt").write_text("base\n", encoding="utf-8")
    git(seed, "add", "tracked.txt")
    git(seed, "commit", "-m", "base")
    git(seed, "push", "-u", "origin", "main")
    git(origin, "symbolic-ref", "HEAD", "refs/heads/main")

    git(tmp_path, "clone", str(origin), str(local))
    configure_repo(local)
    git(local, "checkout", "main")

    git(tmp_path, "clone", str(origin), str(upstream))
    configure_repo(upstream)
    git(upstream, "checkout", "main")

    return local, upstream


def test_help_mentions_main_mode_and_worktree_mode() -> None:
    result = run_script("--help")

    assert result.returncode == 0
    assert "main" in result.stdout
    assert "new worktree" in result.stdout
    assert "origin/main" in result.stdout


def test_invalid_choice_reprompts_until_valid_worktree_selection() -> None:
    result = run_script("--dry-run", "--", "codex", "--dangerously-bypass-approvals-and-sandbox", input_text="wat\n2\n")

    assert result.returncode == 0
    assert "Invalid choice" in result.stdout
    assert "mode=worktree" in result.stdout
    assert "worktree-launch.sh create -- codex" in result.stdout


def test_legacy_alias_choose_main_selects_main_without_prompt_or_forwarding_words() -> None:
    result = run_script(
        "--dry-run",
        "--",
        "codex",
        "--dangerously-bypass-approvals-and-sandbox",
        "choose",
        "main",
    )

    assert result.returncode == 0, result.stderr
    assert "mode=main" in result.stdout
    assert "command=codex --dangerously-bypass-approvals-and-sandbox\n" in result.stdout
    assert "choose main" not in result.stdout


def test_main_mode_fast_forwards_and_restores_dirty_changes(tmp_path: Path) -> None:
    local, upstream = init_main_repo_pair(tmp_path)

    (upstream / "remote.txt").write_text("remote change\n", encoding="utf-8")
    git(upstream, "add", "remote.txt")
    git(upstream, "commit", "-m", "remote change")
    git(upstream, "push", "origin", "main")

    (local / "tracked.txt").write_text("base\nlocal dirty\n", encoding="utf-8")
    (local / "untracked.txt").write_text("keep me\n", encoding="utf-8")

    result = run_script(
        "--",
        "true",
        input_text="1\n",
        env={"AI_PROJECT_ROOT": str(local), "AI_NO_EXEC": "1"},
    )

    assert result.returncode == 0, result.stderr
    assert "mode=main" in result.stdout
    assert git(local, "rev-parse", "HEAD") == git(local, "rev-parse", "origin/main")
    assert "local dirty" in (local / "tracked.txt").read_text(encoding="utf-8")
    assert (local / "untracked.txt").read_text(encoding="utf-8") == "keep me\n"
    assert (local / "remote.txt").read_text(encoding="utf-8") == "remote change\n"


def test_main_mode_switches_to_main_when_on_other_branch(tmp_path: Path) -> None:
    local, _ = init_main_repo_pair(tmp_path)

    git(local, "checkout", "-b", "feature-branch")

    result = run_script(
        "--",
        "true",
        input_text="1\n",
        env={"AI_PROJECT_ROOT": str(local), "AI_NO_EXEC": "1"},
    )

    assert result.returncode == 0, result.stderr
    assert "mode=main" in result.stdout
    assert git(local, "rev-parse", "--abbrev-ref", "HEAD") == "main"


def test_main_mode_prompts_before_syncing_local_main_that_is_ahead(tmp_path: Path) -> None:
    local, _ = init_main_repo_pair(tmp_path)

    (local / "local-only.txt").write_text("ahead\n", encoding="utf-8")
    git(local, "add", "local-only.txt")
    git(local, "commit", "-m", "ahead")

    result = run_script(
        "--",
        "true",
        input_text="1\nn\n",
        env={"AI_PROJECT_ROOT": str(local), "AI_NO_EXEC": "1"},
    )

    assert result.returncode != 0
    assert "Run safe sync now" in result.stdout
    assert "safe sync declined" in result.stderr


def test_main_mode_safe_syncs_diverged_main_and_preserves_dirty_changes(tmp_path: Path) -> None:
    local, upstream = init_main_repo_pair(tmp_path)

    (local / "local-only.txt").write_text("ahead\n", encoding="utf-8")
    git(local, "add", "local-only.txt")
    git(local, "commit", "-m", "ahead")

    (upstream / "remote.txt").write_text("remote change\n", encoding="utf-8")
    git(upstream, "add", "remote.txt")
    git(upstream, "commit", "-m", "remote change")
    git(upstream, "push", "origin", "main")

    (local / "tracked.txt").write_text("base\nlocal dirty\n", encoding="utf-8")
    git(local, "add", "tracked.txt")
    (local / "untracked.txt").write_text("keep me\n", encoding="utf-8")

    result = run_script(
        "--",
        "true",
        input_text="1\ny\n",
        env={"AI_PROJECT_ROOT": str(local), "AI_NO_EXEC": "1"},
    )

    assert result.returncode == 0, result.stderr
    assert "Run safe sync now" in result.stdout
    assert git(local, "rev-parse", "HEAD") == git(local, "rev-parse", "origin/main")
    assert (local / "local-only.txt").read_text(encoding="utf-8") == "ahead\n"
    assert (local / "remote.txt").read_text(encoding="utf-8") == "remote change\n"
    assert "local dirty" in (local / "tracked.txt").read_text(encoding="utf-8")
    assert (local / "untracked.txt").read_text(encoding="utf-8") == "keep me\n"
    assert "M  tracked.txt" in git(local, "status", "--short")
    assert len(git(local, "show", "-s", "--pretty=%P").split()) == 1


def test_main_mode_safe_sync_avoids_merge_commit_hooks_when_main_diverged(tmp_path: Path) -> None:
    local, upstream = init_main_repo_pair(tmp_path)

    (local / "local-only.txt").write_text("ahead\n", encoding="utf-8")
    git(local, "add", "local-only.txt")
    git(local, "commit", "-m", "ahead")

    hook = local / ".git" / "hooks" / "commit-msg"
    hook.write_text(
        "#!/bin/sh\n"
        "if grep -q '^Merge' \"$1\"; then\n"
        "  echo 'merge commit blocked by test hook' >&2\n"
        "  exit 1\n"
        "fi\n",
        encoding="utf-8",
    )

    (upstream / "remote.txt").write_text("remote change\n", encoding="utf-8")
    git(upstream, "add", "remote.txt")
    git(upstream, "commit", "-m", "remote change")
    git(upstream, "push", "origin", "main")

    result = run_script(
        "--",
        "true",
        input_text="1\ny\n",
        env={"AI_PROJECT_ROOT": str(local), "AI_NO_EXEC": "1"},
    )

    assert result.returncode == 0, result.stderr
    assert "mode=main" in result.stdout
    assert git(local, "rev-parse", "HEAD") == git(local, "rev-parse", "origin/main")
    assert len(git(local, "show", "-s", "--pretty=%P").split()) == 1
