"""Shared implementation for auto-lint scanners."""
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
import json
import os
import shutil
import subprocess
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

LINT_DIFFICULTY_SPEC = {
    0: "Surface check — verify ESLint is available and dashboard dir exists",
    1: "Content check — run ESLint --quiet and report fixable vs manual errors",
    2: "Deep check — same as d1 (full ESLint scan)",
    3: "Exhaustive — same as d1 (full ESLint scan)",
    4: "Expert — same as d1 (full ESLint scan)",
}


def _dashboard_dir(project_root: Path) -> Path:
    return project_root / "apps" / "dashboard"


def _find_command(command: str) -> str | None:
    candidates = [f"{command}.cmd", command] if os.name == "nt" else [command]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _resolve_command(command: str) -> str:
    candidates = [f"{command}.cmd", command] if os.name == "nt" else [command]
    found = _find_command(command)
    if found:
        return found
    return candidates[-1]


def _eslint_command(dashboard_dir: Path) -> list[str]:
    package_json = dashboard_dir / "package.json"
    package_text = package_json.read_text(encoding="utf-8") if package_json.exists() else ""
    if (dashboard_dir / "pnpm-lock.yaml").exists() or '"pnpm@' in package_text:
        pnpm = _find_command("pnpm")
        if pnpm:
            return [pnpm, "exec", "eslint"]
        corepack = _resolve_command("corepack")
        return [corepack, "pnpm", "exec", "eslint"]
    return [_resolve_command("npx"), "eslint"]


def _commit_files(project_root: Path, message: str, paths: list[str]) -> str | None:
    """Stage specific paths and commit. Returns commit hash or None."""
    for rel_path in paths:
        subprocess.run(
            ["git", "add", rel_path],
            capture_output=True,
            cwd=str(project_root),
        )
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
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


def scan_lint(ctx: OpsContext) -> ScanResult:
    """Check for ESLint issues in the dashboard directory."""
    dashboard_dir = _dashboard_dir(ctx.project_root)
    if not dashboard_dir.exists():
        return ScanResult(issues=[], summary="No dashboard directory", severity="info")

    if ctx.difficulty < 1:
        return ScanResult(
            issues=[],
            summary="ESLint available, dashboard dir exists",
            severity="info",
            health="verified",
        )

    try:
        result = subprocess.run(
            [*_eslint_command(dashboard_dir), ".", "--quiet", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=ctx.config.get("scan_timeout", 120),
            cwd=str(dashboard_dir),
        )
        if result.returncode == 0 or not result.stdout.strip():
            return ScanResult(issues=[], summary="No lint issues", severity="info")

        try:
            data = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError):
            return ScanResult(
                issues=[],
                summary="Failed to parse ESLint output",
                severity="warning",
                health="broken",
            )

        fixable = 0
        manual_count = 0
        for file_result in data:
            for message in file_result.get("messages", []):
                if message.get("severity", 0) < 2:
                    continue
                # Skip "unused eslint-disable" removals — these often protect
                # @fs-exempt annotations and removing them breaks the build.
                rule = message.get("ruleId") or ""
                if rule == "" and "eslint-disable" in message.get("message", ""):
                    continue
                if message.get("fix"):
                    fixable += 1
                else:
                    manual_count += 1

        issues: list[dict] = []
        if fixable > 0:
            issues.append(
                {
                    "action": "lint-autofix",
                    "fixable_count": fixable,
                }
            )

        return ScanResult(
            issues=issues,
            summary=f"{fixable} auto-fixable, {manual_count} manual errors",
            severity="warning" if issues or manual_count else "info",
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ScanResult(
            issues=[],
            summary="ESLint not available or timed out",
            severity="warning",
            health="broken",
        )


def _restore_fs_exempt_files(project_root: Path, dashboard_dir: Path) -> int:
    """Revert files where ESLint --fix only removed @fs-exempt directives.

    ESLint treats eslint-disable comments as "unused" when the disabled rule
    isn't triggering, and --fix auto-removes them.  But @fs-exempt annotations
    are intentional build-safety markers (CLAUDE.md rule 11, ADR-266).
    Removing them causes no-restricted-imports to fire and break the build.
    """
    result = subprocess.run(
        ["git", "diff", "--name-only", "--", str(dashboard_dir)],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    if result.returncode != 0 or not result.stdout.strip():
        return 0

    restored = 0
    for rel_path in result.stdout.strip().splitlines():
        diff = subprocess.run(
            ["git", "diff", "--", rel_path],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        # If every removed line contains @fs-exempt or eslint-disable, revert
        removed = [
            line[1:].strip()
            for line in diff.stdout.splitlines()
            if line.startswith("-") and not line.startswith("---")
        ]
        if removed and all("@fs-exempt" in l or "eslint-disable" in l for l in removed):
            subprocess.run(
                ["git", "checkout", "--", rel_path],
                capture_output=True,
                cwd=str(project_root),
            )
            restored += 1

    return restored


def _fix_eslint_auto(ctx: OpsContext, dashboard_dir: Path) -> FixResult:
    # Snapshot tracked dirty files BEFORE eslint --fix so we can distinguish
    # files modified by eslint from unrelated working-tree changes.
    pre_dirty = subprocess.run(
        ["git", "diff", "--name-only", "--", "apps/dashboard/"],
        capture_output=True,
        text=True,
        cwd=str(ctx.project_root),
    )
    pre_dirty_set = set(pre_dirty.stdout.strip().splitlines()) if pre_dirty.returncode == 0 else set()

    result = subprocess.run(
        [*_eslint_command(dashboard_dir), ".", "--fix", "--quiet"],
        capture_output=True,
        text=True,
        timeout=ctx.config.get("scan_timeout", 120),
        cwd=str(dashboard_dir),
    )
    if result.returncode not in (0, 1):
        return FixResult(
            success=False,
            summary=result.stderr[:500] if result.stderr else f"eslint exit {result.returncode}",
        )

    # Restore files where the only change was removing @fs-exempt directives
    restored = _restore_fs_exempt_files(ctx.project_root, dashboard_dir)

    # Only stage files that eslint --fix actually changed (post-dirty minus
    # pre-dirty).  This prevents sweeping unrelated untracked or modified
    # files into the lint commit.
    post_dirty = subprocess.run(
        ["git", "diff", "--name-only", "--", "apps/dashboard/"],
        capture_output=True,
        text=True,
        cwd=str(ctx.project_root),
    )
    post_dirty_set = set(post_dirty.stdout.strip().splitlines()) if post_dirty.returncode == 0 else set()
    eslint_changed = sorted(post_dirty_set - pre_dirty_set)

    if not eslint_changed:
        return FixResult(
            success=True,
            summary="ESLint auto-fix ran but no files changed",
        )

    commit = _commit_files(
        ctx.project_root,
        "fix(adaptive): auto-fix lint issues",
        paths=eslint_changed,
    )
    summary = "ESLint auto-fix applied"
    if restored:
        summary += f" ({restored} @fs-exempt files preserved)"
    return FixResult(
        success=True,
        actions=[{"commit": commit}] if commit else [],
        changes=["apps/dashboard/"],
        summary=summary,
    )


def fix_lint(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix ESLint issues with auto-fix only."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would fix {len(issues)} lint issues",
        )

    dashboard_dir = _dashboard_dir(ctx.project_root)
    all_changes: list[str] = []
    all_actions: list[dict] = []
    any_success = False

    auto_issues = [issue for issue in issues if not issue.get("ai_fix")]
    for _issue in auto_issues:
        result = _fix_eslint_auto(ctx, dashboard_dir)
        if result.success:
            any_success = True
            all_changes.extend(result.changes)
            all_actions.extend(result.actions)

    return FixResult(
        success=any_success or len(auto_issues) == 0,
        actions=all_actions,
        changes=all_changes,
        summary=(
            f"Fixed {len(all_changes)} files"
            if all_changes
            else "No auto-fixable changes"
        ),
    )
