"""Shared code-review helper logic for adaptive/devops command surfaces."""
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
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, write_report

# Load lint_lib for eslint --fix delegation (auto-lint already owns this).
_LINT_LIB_MOD = "lint_lib"
if _LINT_LIB_MOD in sys.modules:
    _lint_lib = sys.modules[_LINT_LIB_MOD]
else:
    _lint_lib_path = Path(__file__).resolve().parent / "lint_lib.py"
    _lint_spec = importlib.util.spec_from_file_location(_LINT_LIB_MOD, str(_lint_lib_path))
    _lint_lib = importlib.util.module_from_spec(_lint_spec)
    sys.modules[_LINT_LIB_MOD] = _lint_lib
    _lint_spec.loader.exec_module(_lint_lib)


CODE_REVIEW_DIFFICULTY_SPEC = {
    0: "Surface check — classify dirty files only; defer lint and type checks",
    1: "Content check — inspect changed dashboard files with targeted lint/tsc",
    2: "Deep check — same as d1 with wider recent change window",
    3: "Exhaustive — same as d2",
    4: "Expert — same as d2",
}


def _git_diff_stat(project_root: Path, *, extended: bool = False) -> str:
    """Return ``git diff --stat`` output."""
    cmd = ["git", "diff", "--stat"]
    if extended:
        cmd = ["git", "diff", "--stat", "HEAD~3"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_changed_files(project_root: Path, *, extended: bool = False) -> list[str]:
    """Return changed file paths from git."""
    cmd = ["git", "diff", "--name-only"]
    if extended:
        cmd = ["git", "diff", "--name-only", "HEAD~3"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _run_tsc_check(dashboard_dir: Path, timeout: int = 120) -> list[dict]:
    """Run ``npx tsc --noEmit`` and return a list of diagnostic dicts."""
    try:
        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(dashboard_dir),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    if result.returncode == 0:
        return []

    diagnostics: list[dict] = []
    for line in (result.stdout or "").splitlines():
        if ": error " in line:
            diagnostics.append({"message": line.strip()[:300]})
    return diagnostics


_LINTABLE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
_TSC_RELEVANT_SUFFIXES = {".ts", ".tsx"}
_TSC_TRIGGER_FILES = {
    "package.json",
    "tsconfig.json",
    "tsconfig.base.json",
    "next-env.d.ts",
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
}


def _lint_targets(
    dashboard_dir: Path,
    changed_paths: set[str] | None,
) -> list[str]:
    """Return existing lintable dashboard-relative paths."""
    if not changed_paths:
        return []

    targets: list[str] = []
    for rel_path in sorted(changed_paths):
        path = Path(rel_path)
        if path.suffix not in _LINTABLE_SUFFIXES:
            continue
        full_path = dashboard_dir / path
        if full_path.is_file():
            targets.append(rel_path)
    return targets


def _needs_tsc_check(changed_paths: set[str] | None) -> bool:
    """Return whether the current dashboard diff can affect TypeScript health."""
    if not changed_paths:
        return False

    for rel_path in changed_paths:
        path = Path(rel_path)
        if path.suffix in _TSC_RELEVANT_SUFFIXES:
            return True
        if path.name in _TSC_TRIGGER_FILES:
            return True
    return False


def _snapshot_changed_files(ctx: OpsContext) -> list[str]:
    """Return shared dirty-file state when available for classify-only scans."""
    snapshot = ctx.shared_snapshot if isinstance(ctx.shared_snapshot, dict) else {}
    dirty_files = snapshot.get("git_dirty_files")
    if not isinstance(dirty_files, list):
        return []
    return [str(path).strip() for path in dirty_files if str(path).strip()]


def _run_lint_check(
    dashboard_dir: Path,
    changed_paths: set[str] | None = None,
    timeout: int = 120,
) -> list[dict]:
    """Run targeted ESLint and return error-level findings."""
    targets = _lint_targets(dashboard_dir, changed_paths)
    if not targets:
        return []

    try:
        result = subprocess.run(
            ["npx", "eslint", "--format", "json", *targets],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(dashboard_dir),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    if not result.stdout or not result.stdout.strip():
        return []

    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return []

    findings: list[dict] = []
    for entry in data:
        file_path = entry.get("filePath", "")
        try:
            rel_file = str(Path(file_path).resolve().relative_to(dashboard_dir.resolve()))
        except (ValueError, OSError):
            rel_file = ""
        if changed_paths is not None and rel_file and rel_file not in changed_paths:
            continue
        for msg in entry.get("messages", []):
            if msg.get("severity", 0) >= 2:
                findings.append({
                    "file": file_path,
                    "line": msg.get("line"),
                    "rule": msg.get("ruleId", ""),
                    "message": msg.get("message", "")[:200],
                })
    return findings


def scan_code_review(
    ctx: OpsContext,
    *,
    git_changed_files=_git_changed_files,
    git_diff_stat=_git_diff_stat,
    run_tsc_check=_run_tsc_check,
    run_lint_check=_run_lint_check,
    snapshot_changed_files=_snapshot_changed_files,
    needs_tsc_check=_needs_tsc_check,
) -> ScanResult:
    """Detect recent code changes and collect tsc/lint findings."""
    extended = ctx.difficulty >= 1
    changed_files = (
        snapshot_changed_files(ctx)
        if ctx.difficulty < 1
        else git_changed_files(ctx.project_root, extended=extended)
    )

    if not changed_files:
        return ScanResult(issues=[], summary="No changes detected", severity="info")

    if ctx.difficulty < 1:
        dashboard_changes = sum(1 for path in changed_files if path.startswith("apps/dashboard/"))
        return ScanResult(
            issues=[],
            summary=(
                f"{len(changed_files)} files changed"
                + (
                    f", {dashboard_changes} under apps/dashboard"
                    if dashboard_changes
                    else ""
                )
                + "; surface review only"
            ),
            severity="info",
        )

    dashboard_dir = ctx.project_root / "apps" / "dashboard"
    tsc_errors: list[dict] = []
    lint_errors: list[dict] = []

    if dashboard_dir.exists():
        changed_dashboard_paths = {
            path.removeprefix("apps/dashboard/")
            for path in changed_files
            if path.startswith("apps/dashboard/")
        }
        if needs_tsc_check(changed_dashboard_paths):
            tsc_errors = run_tsc_check(dashboard_dir)
        lint_errors = run_lint_check(dashboard_dir, changed_paths=changed_dashboard_paths)

    if not tsc_errors and not lint_errors:
        return ScanResult(
            issues=[],
            summary=f"{len(changed_files)} files changed, no tsc/lint findings",
            severity="info",
        )

    diff_output = git_diff_stat(ctx.project_root, extended=extended)

    issues = [{
        "action": "code-review",
        "changed_files": changed_files,
        "diff_stat": diff_output,
        "tsc_errors": tsc_errors,
        "lint_errors": lint_errors,
    }]

    return ScanResult(
        issues=issues,
        summary=f"{len(changed_files)} files changed, {len(tsc_errors)} tsc errors, {len(lint_errors)} lint errors",
        severity="warning",
    )


def fix_code_review(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix lint errors via eslint --fix (d>=1), then write a review report."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would report {len(issues)} code review issues",
        )

    payload = issues[0] if issues else {}
    lint_errors = payload.get("lint_errors", [])

    # ADR-417: delegate eslint --fix to auto-lint's implementation at d>=1
    autofix_applied = False
    autofix_actions: list[dict] = []
    autofix_changes: list[str] = []
    if ctx.difficulty >= 1 and lint_errors:
        dashboard_dir = ctx.project_root / "apps" / "dashboard"
        if dashboard_dir.exists():
            lint_result = _lint_lib._fix_eslint_auto(ctx, dashboard_dir)
            if lint_result.success and lint_result.changes:
                autofix_applied = True
                autofix_actions.extend(lint_result.actions)
                autofix_changes.extend(lint_result.changes)

    report = {
        "changed_files": payload.get("changed_files", []),
        "diff_stat": payload.get("diff_stat", ""),
        "tsc_errors": payload.get("tsc_errors", []),
        "lint_errors": lint_errors,
        "total_tsc": len(payload.get("tsc_errors", [])),
        "total_lint": len(lint_errors),
        "autofix_applied": autofix_applied,
    }
    report_path = write_report(ctx, "code-review-latest.json", report)

    all_actions = [{"report": str(report_path)}] + autofix_actions
    fix_type = "code-fix" if autofix_applied else "report"

    return FixResult(
        success=True,
        actions=all_actions,
        changes=autofix_changes,
        summary=(
            f"Report written: {report['total_tsc']} tsc errors, "
            f"{report['total_lint']} lint errors"
            + (f"; eslint --fix applied ({len(autofix_changes)} paths)" if autofix_applied else "")
        ),
        fix_type=fix_type,
    )
