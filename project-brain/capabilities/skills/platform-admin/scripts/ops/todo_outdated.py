"""auto-todo-outdated: Find and resolve TODO_OUTDATED markers.

Extracted from CodeQualityLoop._run_todo_fix for todo-outdated category (ADR-200).
Similar to todo_cleanup but targets TODO_OUTDATED markers at a higher tier.
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

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

name = "auto-todo-outdated"

# Markers this command handles
_MARKERS = ["TODO_OUTDATED"]


def scan(ctx: OpsContext) -> ScanResult:
    """Scan for TODO_OUTDATED markers in the codebase."""
    # Use comment-aware pattern to avoid false positives from code references
    # (e.g. _MARKERS list in this file, dictionary keys)
    _COMMENT_PATTERN = r"(#|//|/\*)\s*TODO_OUTDATED"
    try:
        result = subprocess.run(
            ["grep", "-r", "-E", "--include=*.py", "--include=*.ts", "--include=*.tsx",
             "--include=*.js", "--include=*.jsx", "-l", _COMMENT_PATTERN],
            capture_output=True,
            text=True,
            timeout=ctx.config.get("scan_timeout", 30),
            cwd=str(ctx.project_root),
        )
        if result.returncode == 0 and result.stdout.strip():
            files = result.stdout.strip().splitlines()
            issues = [
                {"action": "todo-outdated", "file": f, "marker": "TODO_OUTDATED"}
                for f in files[:20]  # Cap at 20 files per scan
            ]
            return ScanResult(
                issues=issues,
                summary=f"Found TODO_OUTDATED markers in {len(files)} files",
                severity="warning",
            )
        return ScanResult(
            issues=[],
            summary="No TODO_OUTDATED markers found",
            severity="info",
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ScanResult(
            issues=[],
            summary="grep not available or timed out",
            severity="info",
        )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Use headless Claude to resolve TODO_OUTDATED markers."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would fix {len(issues)} TODO_OUTDATED markers",
        )

    cli_path = _find_cli()
    if not cli_path:
        return FixResult(
            success=False,
            summary="No CLI path configured for TODO fix",
        )

    all_changes: list[str] = []
    all_actions: list[dict] = []

    for issue in issues:
        file_path = issue.get("file", "")
        prompt = (
            f"Find and fix the TODO_OUTDATED marker in: {file_path}. "
            "The code or comment is outdated and needs updating. "
            "Make the minimal change to resolve it. "
            "Commit with prefix fix(adaptive):"
        )
        max_turns = str(ctx.config.get("max_turns", 10))
        fix_timeout = ctx.config.get("fix_timeout", 300)
        result = subprocess.run(
            [cli_path, "--print", "--max-turns", max_turns,
             "--allowedTools", "Read,Edit,Bash,Grep,Glob",
             "-p", prompt],
            capture_output=True,
            text=True,
            timeout=fix_timeout,
            cwd=str(ctx.project_root),
        )
        commit = _get_latest_commit(ctx.project_root)
        if result.returncode == 0 and commit:
            all_changes.append(file_path)
            all_actions.append({"commit": commit})

    return FixResult(
        success=len(all_changes) > 0,
        actions=all_actions,
        changes=all_changes,
        summary=f"Fixed {len(all_changes)} TODO_OUTDATED markers",
    )


def _get_latest_commit(project_root: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    return result.stdout.strip() if result.returncode == 0 else None


from src.lib.llm_retry import resolve_cli as _find_cli
