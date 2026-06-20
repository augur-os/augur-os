"""Commit verification and regression guard for the adaptive engine.

Extracted from engine.py to keep each module under ~400 lines.
Provides VerificationMixin which AdaptiveLoopEngine inherits.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


def _normalize_tsc_error(line: str) -> str:
    """Strip line/column numbers from a tsc diagnostic so that errors
    which merely shifted position (due to formatting changes) are treated
    as the same error during baseline comparison.

    e.g. ``components/Foo.tsx(42,5): error TS2345: ...``
      -> ``components/Foo.tsx: error TS2345: ...``
    """
    return re.sub(r"\(\d+,\d+\)", "", line)


def _revert_commit(project_root: Path, commit_hash: str) -> bool:
    """Revert the verified commit without assuming it is still HEAD."""
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit_hash, "HEAD"],
        capture_output=True,
        cwd=str(project_root),
    )
    if ancestor.returncode != 0:
        return False

    result = subprocess.run(
        ["git", "revert", commit_hash, "--no-edit"],
        capture_output=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        return True

    subprocess.run(
        ["git", "revert", "--abort"],
        capture_output=True,
        cwd=str(project_root),
    )
    return False


class VerificationMixin:
    """Mixin providing verify_commit() and related helpers."""

    _TS_EXTENSIONS = frozenset((".ts", ".tsx", ".js", ".jsx", ".json"))
    # Categories whose commits are cosmetic-only (e.g. Prettier) and cannot
    # introduce TypeScript errors.  Skip tsc verify to avoid false positives
    # from cold-start cache differences.
    _SKIP_VERIFY_CATEGORIES = frozenset(("auto-format",))

    def _commit_touches_ts(self, commit_hash: str) -> bool:
        """Check if a commit modified any TypeScript-relevant files."""
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash],
            capture_output=True,
            text=True,
            cwd=str(self._project_root),
        )
        if result.returncode != 0:
            return True  # Assume TS on error (safe default)
        for line in result.stdout.strip().splitlines():
            suffix = Path(line).suffix
            if suffix in self._TS_EXTENSIONS:
                return True
        return False

    def capture_tsc_baseline(self) -> None:
        """Run tsc once and cache the baseline errors for the entire cycle.

        Call this at the start of each cycle so verify_commit() can compare
        against the cached baseline instead of running tsc twice per commit.
        """
        self._tsc_baseline_errors: set[str] | None = None
        if not self._verify_command:
            return
        try:
            result = subprocess.run(
                self._verify_command, shell=True, capture_output=True,  # nosec B602  # operator-supplied trusted config (SKILL.md frontmatter / engine verify config), not attacker-controllable input
                text=True,
                timeout=120,
                cwd=str(self._project_root),
            )
            self._tsc_baseline_errors = {
                _normalize_tsc_error(line)
                for line in result.stdout.strip().splitlines()
            } if result.returncode != 0 else set()
        except subprocess.TimeoutExpired:
            self._tsc_baseline_errors = None

    def verify_commit(self, commit_hash: str) -> bool:
        """Run verify command after a commit. Reverts on failure.

        Skips verification for commits that don't touch TypeScript-relevant
        files (e.g., RAG checksums, YAML data) to avoid false positives
        from transient tsc cold-start failures.

        Uses cached baseline from capture_tsc_baseline() when available.
        Without a cached baseline, a verify failure fails closed and reverts
        the auto-fix commit instead of mutating the worktree to reconstruct
        prior state.
        """
        if not self._verify_command:
            return True
        if not self._commit_touches_ts(commit_hash):
            return True
        try:
            # Run verify on the current state (with the commit)
            result = subprocess.run(
                self._verify_command, shell=True, capture_output=True,  # nosec B602  # operator-supplied trusted config (SKILL.md frontmatter / engine verify config), not attacker-controllable input
                text=True,
                timeout=120,
                cwd=str(self._project_root),
            )
            if result.returncode == 0:
                return True

            post_errors = {
                _normalize_tsc_error(line)
                for line in result.stdout.strip().splitlines()
            }

            # Use cached baseline if available (avoids 2nd tsc run)
            pre_errors = getattr(self, "_tsc_baseline_errors", None)
            if pre_errors is None:
                _revert_commit(self._project_root, commit_hash)
                return False

            # Only fail if the commit introduced NEW errors
            new_errors = post_errors - pre_errors
            if new_errors:
                _revert_commit(self._project_root, commit_hash)
                # Update cached baseline after revert
                self._tsc_baseline_errors = pre_errors
                return False
            # Pre-existing errors only -- commit is fine.
            # Update baseline to include current state for next verify.
            self._tsc_baseline_errors = post_errors
            return True
        except subprocess.TimeoutExpired:
            _revert_commit(self._project_root, commit_hash)
            return False
