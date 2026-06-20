"""auto-git-health: Run git gc to keep repo size in check.

Wraps git_optimize.py as an auto-loop command for nightly execution.
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
import os
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

# Import git_optimize gracefully
try:
    from scripts.git_optimize import get_dir_size, run_git_gc
except ImportError:
    try:
        import importlib.util

        _spec = importlib.util.spec_from_file_location(
            "git_optimize",
            Path(__file__).resolve().parent / "git_optimize.py",
        )
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        get_dir_size = _mod.get_dir_size
        run_git_gc = _mod.run_git_gc
    except Exception:
        get_dir_size = None
        run_git_gc = None

name = "auto-git-health"

# Warn threshold in MB
SIZE_THRESHOLD_MB = 300


def scan(ctx: OpsContext) -> ScanResult:
    """Check .git directory size."""
    git_dir = ctx.project_root / ".git"
    if not git_dir.exists():
        return ScanResult(issues=[], summary="Not a git repo", severity="info")

    if get_dir_size is None:
        # A loop that cannot load its dependency must not report green.
        return ScanResult(
            issues=[],
            summary="git_optimize module not available — git health not checked",
            severity="warning",
            health="degraded",
        )

    size_mb = get_dir_size(git_dir)
    if size_mb > SIZE_THRESHOLD_MB:
        return ScanResult(
            issues=[{"action": "git-gc", "size_mb": round(size_mb, 1)}],
            summary=f".git is {size_mb:.0f} MB (threshold: {SIZE_THRESHOLD_MB} MB)",
            severity="warning",
        )

    return ScanResult(
        issues=[],
        summary=f".git is {size_mb:.0f} MB — healthy",
        severity="info",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Run git gc --prune=now."""
    if ctx.dry_run:
        size_mb = issues[0].get("size_mb", "?") if issues else "?"
        return FixResult(
            success=True,
            summary=f"Dry run: would run git gc (current size: {size_mb} MB)",
        )

    if run_git_gc is None:
        return FixResult(
            success=False,
            summary="git_optimize module not available",
        )

    git_dir = ctx.project_root / ".git"
    before = get_dir_size(git_dir) if get_dir_size else 0

    try:
        run_git_gc(ctx.project_root)
    except Exception as e:
        return FixResult(success=False, summary=f"git gc failed: {e}")

    after = get_dir_size(git_dir) if get_dir_size else 0
    saved = before - after

    return FixResult(
        success=True,
        summary=f"git gc complete: {before:.0f} → {after:.0f} MB (saved {saved:.1f} MB)",
    )
