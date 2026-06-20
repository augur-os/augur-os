"""
scripts._launch_git — Git helpers for the agent launcher.

Self-contained: only stdlib imports. No cross-sibling dependencies.

Split from src/scripts/agent_launch.py (WS5, behavior-preserving).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"git {' '.join(args)} failed"
        raise RuntimeError(message)
    return result


def git_stdout(repo: Path, *args: str) -> str:
    return run_git(repo, *args).stdout.strip()


def repo_is_dirty(repo: Path) -> bool:
    return bool(git_stdout(repo, "status", "--porcelain"))


def stash(repo: Path) -> bool:
    from datetime import datetime

    if not repo_is_dirty(repo):
        return False
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_git(repo, "stash", "push", "--include-untracked", "--message", f"ai-autostash-{stamp}")
    return True


def restore_stash(repo: Path) -> None:
    result = run_git(repo, "stash", "pop", "--index", check=False)
    if result.returncode != 0:
        raise RuntimeError("failed to restore stashed changes cleanly")


def rev_count(repo: Path, revision_range: str) -> int:
    return int(git_stdout(repo, "rev-list", "--count", revision_range) or "0")


def prompt_safe_sync(repo: Path) -> None:
    ahead = rev_count(repo, "origin/main..main")
    behind = rev_count(repo, "main..origin/main")
    print("Local main is ahead of or diverged from origin/main.")
    print(
        "Safe sync can rebase local-only commits onto origin/main, "
        f"push main normally, and preserve dirty work ({ahead} ahead, {behind} behind)."
    )
    print("Run safe sync now? [y/N]: ", end="", flush=True)

    choice = sys.stdin.readline()
    if choice == "":
        raise RuntimeError("safe sync cancelled")
    if choice.strip().lower() in {"y", "yes"}:
        return
    raise RuntimeError("safe sync declined; local main is ahead of or diverged from origin/main")


def abort_merge_if_active(repo: Path) -> None:
    result = run_git(repo, "rev-parse", "--verify", "--quiet", "MERGE_HEAD", check=False)
    if result.returncode == 0:
        run_git(repo, "merge", "--abort", check=False)


def abort_rebase_if_active(repo: Path) -> None:
    run_git(repo, "rebase", "--abort", check=False)


def safe_sync_main_checkout(repo: Path, remote_sha: str, base_sha: str) -> None:
    stashed = stash(repo)
    sync_error: Exception | None = None

    try:
        if remote_sha != base_sha:
            run_git(repo, "rebase", "origin/main")
        run_git(repo, "push", "origin", "main")
        run_git(repo, "fetch", "origin", "main")
        if git_stdout(repo, "rev-parse", "main") != git_stdout(repo, "rev-parse", "origin/main"):
            raise RuntimeError("safe sync did not leave main aligned with origin/main")
    except Exception as exc:  # noqa: BLE001 - preserve git failure text after cleanup.
        sync_error = exc
        abort_merge_if_active(repo)
        abort_rebase_if_active(repo)

    if stashed:
        try:
            restore_stash(repo)
        except Exception as exc:
            if sync_error is not None:
                raise RuntimeError(f"{sync_error}; additionally failed to restore stashed changes cleanly") from exc
            raise

    if sync_error is not None:
        raise sync_error


def sync_main_checkout(repo: Path) -> None:
    current_branch = git_stdout(repo, "rev-parse", "--abbrev-ref", "HEAD")

    if current_branch != "main":
        if repo_is_dirty(repo):
            raise RuntimeError(
                f"main mode requires a clean working tree before switching to main from {current_branch}"
            )
        checkout = run_git(repo, "checkout", "main", check=False)
        if checkout.returncode != 0:
            raise RuntimeError("main mode requires branch 'main'; checkout failed - resolve manually")

    run_git(repo, "fetch", "origin", "main")
    local_sha = git_stdout(repo, "rev-parse", "main")
    remote_sha = git_stdout(repo, "rev-parse", "origin/main")
    base_sha = git_stdout(repo, "merge-base", "main", "origin/main")

    if local_sha == remote_sha:
        return
    if local_sha != base_sha:
        prompt_safe_sync(repo)
        safe_sync_main_checkout(repo, remote_sha, base_sha)
        return

    stashed = stash(repo)
    run_git(repo, "merge", "--ff-only", "origin/main")
    if stashed:
        restore_stash(repo)
