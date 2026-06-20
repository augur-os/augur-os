"""auto-format: Run Prettier to auto-format source files.

Extracted from CodeQualityLoop scan (prettier --check) and
_run_format (prettier --write) (ADR-200).
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
import shutil
import subprocess
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

name = "auto-format"

DIFFICULTY_SPEC = {
    0: "Surface check — verify Prettier is available",
    1: "Content check — run prettier --check on src/",
    2: "Deep check — same as d1 (full Prettier scan)",
    3: "Exhaustive — same as d1 (full Prettier scan)",
    4: "Expert — same as d1 (full Prettier scan)",
}


def _node_bin(name: str) -> str:
    """Resolve Node shims correctly on Windows."""
    candidates = [f"{name}.cmd", name] if os.name == "nt" else [name]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return name


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


def scan(ctx: OpsContext) -> ScanResult:
    """Check for formatting issues using Prettier."""
    # d0: surface check — just verify Prettier is available
    if ctx.difficulty < 1:
        if _node_bin("npx") != "npx":
            return ScanResult(
                issues=[],
                summary="Prettier available",
                severity="info",
                health="verified",
            )
        return ScanResult(
            issues=[],
            summary="npx not found",
            severity="info",
            health="broken",
        )

    try:
        result = subprocess.run(
            [_node_bin("npx"), "--yes", "prettier", "--check", "src/"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(ctx.project_root),
        )
        if result.returncode != 0:
            return ScanResult(
                issues=[{
                    "action": "auto-format",
                    "files": ["src/"],
                    "detail": result.stdout[:500],
                }],
                summary="Formatting issues detected",
                severity="warning",
            )
        return ScanResult(
            issues=[],
            summary="No formatting issues",
            severity="info",
        )
    except (subprocess.TimeoutExpired, OSError):
        return ScanResult(
            issues=[],
            summary="Prettier not available or timed out",
            severity="warning",
            health="broken",
        )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Run Prettier to auto-format source files."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary="Dry run: would run prettier --write src/",
        )
    try:
        result = subprocess.run(
            [_node_bin("npx"), "--yes", "prettier", "--write", "src/"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(ctx.project_root),
        )
        if result.returncode == 0:
            commit = _commit_files(
                ctx.project_root,
                "style(adaptive): auto-format src/",
                paths=["src/"],
            )
            return FixResult(
                success=True,
                actions=[{"commit": commit}] if commit else [],
                changes=["src/"],
                summary="Formatted source files",
            )
        return FixResult(
            success=False,
            summary=f"Prettier failed: {result.stderr[:500]}",
        )
    except subprocess.TimeoutExpired:
        return FixResult(
            success=False,
            summary="Prettier timed out",
        )
    except OSError as exc:
        return FixResult(
            success=False,
            summary=f"Prettier unavailable: {exc}",
        )
