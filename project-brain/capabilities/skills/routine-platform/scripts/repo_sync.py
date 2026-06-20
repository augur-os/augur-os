"""auto-repo-sync: Detect uncommitted changes and unpushed commits, optionally commit/push.

Scans the project repository for dirty working tree state (uncommitted changes)
and commits ahead of the upstream tracking branch.  Fix behavior escalates with
difficulty level:
  - difficulty 0: report only
  - difficulty 1: commit staged + safe untracked changes
  - difficulty 2+: commit staged changes and push to remote

See ADR-200 for the auto-command protocol.
"""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import subprocess
from pathlib import Path

from src.config.paths import get_configured_vault_dir
from src.lib.git_ops import is_diff_significant
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

name = "auto-repo-sync"

# Untracked file patterns safe to auto-add (config, generated docs, non-source)
_SAFE_UNTRACKED_PREFIXES = (
    "config/",
    "docs/generated/",
)
_SAFE_UNTRACKED_EXACT = {
    "config/preferences.yaml",
}


# ---------------------------------------------------------------------------
# Helpers (patchable in tests)
# ---------------------------------------------------------------------------

def _classify_untracked(status_output: str) -> tuple[list[str], list[str]]:
    """Split untracked files into (safe_to_add, unsafe).

    Safe: config files, generated docs, known non-source paths.
    Unsafe: everything else (source code, scripts, etc.).
    """
    safe, unsafe = [], []
    for line in status_output.splitlines():
        if not line.startswith("??"):
            continue
        path = line[3:].strip().strip('"')
        if path in _SAFE_UNTRACKED_EXACT or any(path.startswith(p) for p in _SAFE_UNTRACKED_PREFIXES):
            safe.append(path)
        else:
            unsafe.append(path)
    return safe, unsafe


def _has_tracked_changes(status_output: str) -> bool:
    """Return True if status output contains changes to tracked files.

    Untracked files ('??') are normal working state, not defects.
    Only modified, staged, conflicted, deleted, renamed files count.
    """
    for line in status_output.splitlines():
        if line and not line.startswith("??"):
            return True
    return False


def _git_status(project_root: Path) -> str:
    """Return `git status --porcelain` output."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    return result.stdout.strip()


def _git_unpushed(project_root: Path) -> str:
    """Return `git log --oneline @{u}..HEAD` output (commits ahead of upstream)."""
    result = subprocess.run(
        ["git", "log", "--oneline", "@{u}..HEAD"],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    return result.stdout.strip()


def _git_commit(project_root: Path, message: str) -> str:
    """Stage tracked changes and commit.

    Returns:
        "committed" if changes were staged and committed,
        "nothing_to_commit" if git add -u found no tracked changes to stage,
        "insignificant" if the staged diff is whitespace-only,
        "error" if the commit failed for another reason.
    """
    subprocess.run(["git", "add", "-u"], capture_output=True, cwd=str(project_root))
    # Check if anything was actually staged
    diff_result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
        cwd=str(project_root),
    )
    if diff_result.returncode == 0:
        # Nothing staged (only untracked files in working tree)
        return "nothing_to_commit"

    # Diff significance gate: abort if changes are whitespace-only
    if not is_diff_significant(project_root):
        subprocess.run(["git", "reset", "HEAD"], capture_output=True, cwd=str(project_root))
        return "insignificant"

    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    return "committed" if result.returncode == 0 else "error"


def _git_push(project_root: Path) -> bool:
    """Push to upstream. Returns True on success."""
    result = subprocess.run(
        ["git", "push"],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    return result.returncode == 0


def _git_has_upstream(project_root: Path) -> bool:
    """Return True when the current branch has an upstream tracking branch."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def _get_vault_path(project_root: Path | None = None) -> Path:
    """Read the configured vault path without private discovery fallback."""
    return get_configured_vault_dir(project_root)


# ---------------------------------------------------------------------------
# Protocol implementation
# ---------------------------------------------------------------------------

def scan(ctx: OpsContext) -> ScanResult:
    """Detect uncommitted changes and unpushed commits."""
    issues: list[dict] = []
    summary_parts: list[str] = []

    status_output = _git_status(ctx.project_root)
    if status_output:
        lines = status_output.splitlines()
        tracked_dirty = _has_tracked_changes(status_output)
        if tracked_dirty:
            summary_parts.append(f"working tree dirty ({len(lines)} paths)")
        else:
            summary_parts.append(f"untracked files only ({len(lines)} paths)")
        if ctx.difficulty >= 1:
            issues.append({
                "type": "uncommitted_changes",
                "count": len(lines),
                "detail": status_output,
                "kind": "actionable" if tracked_dirty else "maintenance",
            })

    unpushed_output = _git_unpushed(ctx.project_root)
    if unpushed_output:
        commits = unpushed_output.splitlines()
        summary_parts.append(f"{len(commits)} unpushed commit(s)")
        if ctx.difficulty >= 1:
            issues.append({
                "type": "unpushed_commits",
                "count": len(commits),
                "detail": unpushed_output,
                "kind": "manual",
            })

    # Scan vault repo if configured
    vault_path = _get_vault_path(ctx.project_root)
    if vault_path is None:
        pass
    elif not vault_path.exists():
        summary_parts.append(f"configured vault missing: {vault_path}")
        if ctx.difficulty >= 1:
            issues.append({
                "type": "configured_vault_missing",
                "path": str(vault_path),
                "repo": "vault",
                "kind": "maintenance",
                "detail": f"Configured vault path does not exist: {vault_path}",
            })
    elif (vault_path / ".git").exists():
        vault_status = _git_status(vault_path)
        if vault_status:
            lines = vault_status.splitlines()
            vault_tracked_dirty = _has_tracked_changes(vault_status)
            if vault_tracked_dirty:
                summary_parts.append(f"vault dirty ({len(lines)} paths)")
            else:
                summary_parts.append(f"vault untracked files only ({len(lines)} paths)")
            if ctx.difficulty >= 1:
                issues.append({
                    "type": "vault_uncommitted",
                    "count": len(lines),
                    "detail": vault_status,
                    "repo": "vault",
                    "kind": "actionable" if vault_tracked_dirty else "maintenance",
                })

        vault_unpushed = _git_unpushed(vault_path)
        if vault_unpushed:
            commits = vault_unpushed.splitlines()
            summary_parts.append(f"vault: {len(commits)} unpushed commit(s)")
            if ctx.difficulty >= 1:
                issues.append({
                    "type": "vault_unpushed",
                    "count": len(commits),
                    "detail": vault_unpushed,
                    "repo": "vault",
                    "kind": "manual",
                })

    actionable_count = sum(1 for i in issues if i.get("kind", "actionable") == "actionable")
    maintenance_count = sum(1 for i in issues if i.get("kind") == "maintenance")
    severity = "warning" if actionable_count else "info"
    if actionable_count:
        summary = f"Found {actionable_count} repo sync issue(s)"
        if maintenance_count:
            summary += f" + {maintenance_count} informational"
    elif maintenance_count:
        summary = f"Repository has {maintenance_count} informational finding(s)"
        if summary_parts:
            summary += f": {'; '.join(summary_parts)}"
    elif summary_parts:
        summary = "; ".join(summary_parts)
    else:
        summary = "Repository is clean and synced"
    return ScanResult(issues=issues, summary=summary, severity=severity)


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix repo sync issues based on difficulty level."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            actions=[{"action": "dry_run", "description": "Would fix repo sync issues"}],
            summary="Dry run — no changes made",
        )

    if not issues:
        return FixResult(
            success=True,
            actions=[{"action": "report", "description": "No issues to fix"}],
            summary="Repository is clean — nothing to fix",
            fix_type="sync",
        )

    if ctx.difficulty < 1:
        # Report only
        return FixResult(
            success=True,
            actions=[{"action": "report", "description": "Difficulty 0 — report only"}],
            summary=f"Report only (d0): {len(issues)} repo sync issue(s) detected",
            fix_type="report",
        )

    actions: list[dict] = []
    changes: list[str] = []
    errors: list[str] = []
    project_committed = False
    project_has_unpushed = any(i["type"] == "unpushed_commits" for i in issues)

    # difficulty 1+: commit staged + safe untracked changes
    uncommitted = [i for i in issues if i["type"] == "uncommitted_changes"]
    if uncommitted:
        # Also add safe untracked files before committing
        status_detail = uncommitted[0].get("detail", "")
        safe_untracked, _ = _classify_untracked(status_detail)
        for path in safe_untracked:
            subprocess.run(
                ["git", "add", path],
                capture_output=True, cwd=str(ctx.project_root),
            )

        commit_status = _git_commit(ctx.project_root, "chore(auto): repo-sync auto-commit")
        if commit_status == "committed":
            project_committed = True
            actions.append({"action": "commit", "success": True})
            changes.append("Committed staged changes")
            if safe_untracked:
                changes.append(f"Added {len(safe_untracked)} safe untracked file(s)")
        elif commit_status in ("nothing_to_commit", "insignificant"):
            actions.append({"action": "commit", "success": True, "skipped": True})
        else:
            actions.append({"action": "commit", "success": False})
            errors.append("git commit failed")

    # difficulty 2+: push to remote
    if ctx.difficulty >= 2 and (project_committed or project_has_unpushed):
        if _git_has_upstream(ctx.project_root):
            pushed = _git_push(ctx.project_root)
            if pushed:
                actions.append({"action": "push", "success": True})
                changes.append("Pushed to upstream")
            else:
                actions.append({"action": "push", "success": False})
                errors.append("git push failed")
        else:
            actions.append({"action": "push", "success": True, "skipped": True, "reason": "no_upstream"})

    # Fix vault issues
    vault_path = _get_vault_path(ctx.project_root)
    if vault_path is not None and vault_path.exists():
        vault_uncommitted = [i for i in issues if i.get("repo") == "vault" and i["type"] == "vault_uncommitted"]
        if vault_uncommitted:
            commit_status = _git_commit(vault_path, "chore(auto): vault-sync auto-commit")
            if commit_status == "committed":
                actions.append({"action": "vault_commit", "success": True})
                changes.append("Committed vault changes")
            elif commit_status in ("nothing_to_commit", "insignificant"):
                actions.append({"action": "vault_commit", "success": True, "skipped": True})
            else:
                actions.append({"action": "vault_commit", "success": False})
                errors.append("vault git commit failed")

        if ctx.difficulty >= 2:
            vault_unpushed = [i for i in issues if i.get("repo") == "vault" and i["type"] == "vault_unpushed"]
            if vault_unpushed or vault_uncommitted:
                if _git_has_upstream(vault_path):
                    pushed = _git_push(vault_path)
                    if pushed:
                        actions.append({"action": "vault_push", "success": True})
                        changes.append("Pushed vault to remote")
                    else:
                        actions.append({"action": "vault_push", "success": False})
                        errors.append("vault git push failed")
                else:
                    actions.append({"action": "vault_push", "success": True, "skipped": True, "reason": "no_upstream"})

    success = all(a.get("success", True) for a in actions)
    if not success or errors:
        summary = f"Fix failed: {'; '.join(errors) if errors else 'one or more repo sync actions failed'}"
    elif changes:
        summary = f"Applied {len(changes)} repo sync fix(es)"
    elif success:
        summary = "No actionable changes (untracked files only)"
    else:
        summary = f"Fix failed: {'; '.join(errors)}"

    return FixResult(
        success=success,
        actions=actions,
        changes=changes,
        summary=summary,
        fix_type="code-fix" if changes else "report",
    )
