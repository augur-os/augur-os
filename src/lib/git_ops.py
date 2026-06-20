"""Shared git helpers for autoloop commit operations.

Consolidates the 24+ private _commit_files / _commit copies scattered
across skills/*/scripts/ops/*.py into a single canonical implementation.

Also provides is_diff_significant() for semantic diff gating — rejects
commits that only contain whitespace or blank-line changes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def is_diff_significant(project_root: Path) -> bool:
    """Check if the staged diff contains meaningful changes (not just whitespace).

    Returns False if the diff only contains blank line or whitespace changes,
    or if the git command fails (safer to skip than commit unknown content).
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "-U0", "--ignore-all-space", "--ignore-blank-lines"],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    if result.returncode != 0:
        return False  # Don't commit on unknown git state

    diff_lines = [
        line
        for line in result.stdout.splitlines()
        if (line.startswith("+") or line.startswith("-")) and not line.startswith("+++") and not line.startswith("---")
    ]
    return len(diff_lines) > 0


def commit_files(
    project_root: Path,
    message: str,
    paths: list[str] | None = None,
    *,
    significance_check: bool = True,
) -> str | None:
    """Stage paths and commit. Returns short commit hash or None.

    Args:
        project_root: Repository root.
        message: Commit message.
        paths: Files/directories to stage. When None, stages all tracked changes.
        significance_check: When True, skips commits that are whitespace-only.

    Returns:
        Short commit hash on success, None if nothing to commit or commit failed.
    """
    if paths:
        for p in paths:
            subprocess.run(["git", "add", p], capture_output=True, cwd=str(project_root))
    else:
        subprocess.run(["git", "add", "-u"], capture_output=True, cwd=str(project_root))

    # Check if anything was staged
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        return None  # Nothing staged

    # Semantic diff gate
    if significance_check and not is_diff_significant(project_root):
        subprocess.run(["git", "reset", "HEAD"], capture_output=True, cwd=str(project_root))
        return None

    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        rev = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        return rev.stdout.strip() if rev.returncode == 0 else None
    return None
