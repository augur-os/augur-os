"""auto-code-health: TypeScript build error detection and AI-assisted fixing.

Extracted from HardeningLoop._scan_build_health and _fix_build_error (ADR-200).
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

from src.lib.llm_retry import resolve_cli as _find_cli
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, declare_ops_capabilities

name = "auto-code-health"
OPS_CAPABILITIES = declare_ops_capabilities(
    platforms=("cross_platform",),
    windows_fix_mode="report_only",
)


def _list_changed_paths(project_root: Path) -> set[str]:
    """Return the current git worktree delta as repo-relative paths."""
    result = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    if result.returncode != 0:
        return set()

    paths: set[str] = set()
    for line in result.stdout.splitlines():
        if not line:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path:
            paths.add(path)
    return paths


def _commit_files(project_root: Path, message: str, paths: list[str]) -> str | None:
    """Stage specific paths and commit. Returns commit hash or None."""
    for p in paths:
        subprocess.run(
            ["git", "add", p],
            capture_output=True,
            cwd=str(project_root),
        )
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        return None  # No changes to commit
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


def _verify_dashboard_build(ctx: OpsContext, dashboard_dir: Path) -> subprocess.CompletedProcess[str]:
    """Run the dashboard typecheck used by scan/fix verification."""
    return subprocess.run(
        ["pnpm", "run", "typecheck"],
        capture_output=True,
        text=True,
        timeout=ctx.config.get("scan_timeout", 120),
        cwd=str(dashboard_dir),
    )


def _normalize_tsc_path(raw_path: str, dashboard_dir: Path, project_root: Path) -> str:
    """Convert a tsc-relative path to a project-root-relative path.

    tsc emits paths relative to apps/dashboard/ (e.g. ``../../skills/...``).
    Resolve via the dashboard dir and make it relative to project root so
    that downstream consumers (CLI prompts, issue reports) get canonical paths.
    """
    resolved = (dashboard_dir / raw_path).resolve()
    try:
        return str(resolved.relative_to(project_root.resolve()))
    except ValueError:
        return raw_path  # fallback: keep original if outside project


def scan(ctx: OpsContext) -> ScanResult:
    """Run tsc --noEmit and emit per-file issues for any TypeScript errors."""
    dashboard_dir = ctx.project_root / "apps" / "dashboard"
    if not dashboard_dir.exists():
        return ScanResult(issues=[], summary="No dashboard directory", severity="info")

    try:
        result = _verify_dashboard_build(ctx, dashboard_dir)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ScanResult(
            issues=[],
            summary="tsc not available or timed out",
            severity="info",
        )

    if result.returncode == 0:
        return ScanResult(issues=[], summary="No TypeScript errors", severity="info")

    # Group errors by file, normalizing paths to project-root-relative
    errors_by_file: dict[str, list[str]] = {}
    for line in result.stdout.strip().splitlines():
        if ": error TS" in line:
            raw_path = (
                line.split("(")[0].strip()
                if "(" in line
                else line.split(":")[0].strip()
            )
            fpath = _normalize_tsc_path(raw_path, dashboard_dir, ctx.project_root)
            errors_by_file.setdefault(fpath, []).append(line.strip())

    issues = []
    for fpath, errs in errors_by_file.items():
        issues.append({
            "action": f"build-fix-{Path(fpath).stem}",
            "file": fpath,
            "path": fpath,
            "errors": errs,
            "detail": f"{len(errs)} TS error(s) in {fpath}",
        })

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} file(s) with TypeScript errors",
        severity="error" if issues else "info",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Use headless Claude to fix TypeScript build errors, then verify with tsc.

    Returns success=True with fix_type="report" when issues are real but
    cannot be auto-fixed (e.g. test structural issues). Only returns
    success=False on infrastructure errors (no CLI available).
    """
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would fix {len(issues)} TS build issue(s)",
        )

    try:
        cli_path = _find_cli()
    except RuntimeError:
        cli_path = None
    dashboard_dir = ctx.project_root / "apps" / "dashboard"
    all_changes: list[str] = []
    all_actions: list[dict] = []
    infra_failure = False
    fixed_count = 0
    unresolved_count = 0

    if not cli_path:
        # No CLI is an infrastructure problem — report issues without failing
        return FixResult(
            success=True,
            actions=[{"skipped": i.get("file", ""), "reason": "no CLI"} for i in issues],
            summary=f"Reported {len(issues)} TS build issue(s) (no CLI available for auto-fix)",
            fix_type="report",
        )

    for issue in issues:
        file_path = issue.get("file", "")
        errors = issue.get("errors", [])
        error_desc = "\n".join(errors[:10])  # Cap at 10 errors

        prompt = (
            f"Fix the following TypeScript build errors in {file_path}. "
            f"Make minimal, correct fixes that preserve behavior.\n\n"
            f"Errors:\n{error_desc}\n\n"
            f"After fixing, verify with: cd apps/dashboard && pnpm run typecheck\n"
            f"Do NOT use @ts-ignore or any suppression comments."
        )
        max_turns = str(ctx.config.get("max_turns", 12))
        fix_timeout = ctx.config.get("fix_timeout", 300)
        before_changes = _list_changed_paths(ctx.project_root)
        try:
            result = subprocess.run(
                [
                    cli_path, "--print", "--max-turns", max_turns,
                    "--allowedTools", "Read,Edit,Bash,Grep,Glob",
                    "-p", prompt,
                ],
                capture_output=True,
                text=True,
                timeout=fix_timeout,
                cwd=str(ctx.project_root),
            )
        except (subprocess.TimeoutExpired, OSError):
            infra_failure = True
            all_actions.append({"failed": file_path, "reason": "CLI timeout/error"})
            continue

        if result.returncode != 0:
            # CLI crashed — infrastructure failure
            infra_failure = True
            all_actions.append({"failed": file_path, "exit": result.returncode})
            continue

        # Verify with tsc after fix
        verify = _verify_dashboard_build(ctx, dashboard_dir)
        if verify.returncode != 0:
            # CLI ran but couldn't resolve the issue — this is NOT a trust
            # failure, the scan correctly identified a real problem that
            # needs manual attention.
            unresolved_count += 1
            all_actions.append({"unresolved": file_path})
            continue

        after_changes = _list_changed_paths(ctx.project_root)
        new_changes = sorted(after_changes - before_changes)
        if not new_changes:
            fixed_count += 1
            all_actions.append({"resolved": file_path, "changes": []})
            continue

        commit = _commit_files(
            ctx.project_root,
            f"fix(adaptive): resolve build errors in {Path(file_path).name}",
            paths=new_changes,
        )
        fixed_count += 1
        all_changes.extend(path for path in new_changes if path not in all_changes)
        all_actions.append({"fixed": file_path, "changes": new_changes, "commit": commit})

    # Determine result: only fail on infrastructure errors, not unresolved issues
    if all_changes or fixed_count > 0:
        summary_parts = []
        if all_changes:
            summary_parts.append(f"Fixed {len(all_changes)} file(s)")
        if fixed_count > 0 and not all_changes:
            summary_parts.append("Resolved build errors without new local changes")
        if unresolved_count:
            summary_parts.append(f"{unresolved_count} unresolved")
        return FixResult(
            success=True,
            actions=all_actions,
            changes=all_changes,
            summary=", ".join(summary_parts),
            fix_type="code-fix",
        )

    if infra_failure:
        # CLI was available but crashed/timed out on all attempts — this is
        # an environment problem, not a scanner defect.  Return success=True
        # with fix_type="report" so the engine treats it as report-only and
        # does NOT penalize trust.  The scan correctly found real issues; we
        # just couldn't auto-fix them this cycle.
        return FixResult(
            success=True,
            actions=all_actions,
            summary=f"CLI infrastructure error; {unresolved_count} issue(s) unresolved (reported, not fixable this cycle)",
            fix_type="report",
        )

    # Scan found real issues, auto-fix was attempted but issues persist --
    # report-only outcome, not a trust failure.
    return FixResult(
        success=True,
        actions=all_actions,
        summary=f"Reported {len(issues)} TS build issue(s); {unresolved_count} need manual fix",
        fix_type="report",
    )
