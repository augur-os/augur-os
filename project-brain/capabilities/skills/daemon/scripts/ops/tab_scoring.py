"""auto-tab-scoring: Score page maturity and reorder hub tabs.
Extracted from /ops-tabs (ADR-200).

Scan: runs tab_scorer.py --dry-run to evaluate page maturity scores.
Fix: applies tab reordering based on maturity scores.
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

from src.config.paths import get_all_client_skill_dirs, get_python_executable
from src.lib.staged_skill_catalog import find_skill_file
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult


name = "auto-tab-scoring"


def _find_tab_scorer(project_root: Path) -> Path | None:
    return find_skill_file(project_root, "system-cleanup", "scripts", "tab_scorer.py")


def _commit_files(project_root: Path, message: str, paths: list[str]) -> str | None:
    for p in paths:
        subprocess.run(["git", "add", p], capture_output=True, cwd=str(project_root))
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


def scan(ctx: OpsContext) -> ScanResult:
    scorer = _find_tab_scorer(ctx.project_root)
    if scorer is None:
        return ScanResult(issues=[], summary="tab_scorer.py not found", severity="info")

    result = subprocess.run(
        [str(get_python_executable()), str(scorer), "--dry-run"],
        capture_output=True,
        text=True,
        cwd=str(ctx.project_root),
    )

    if result.returncode != 0:
        return ScanResult(
            issues=[],
            summary=f"Tab scorer failed: {result.stderr[:200]}",
            severity="error",
        )

    output = result.stdout.strip()
    if not output or "no changes" in output.lower():
        return ScanResult(issues=[], summary="Tab ordering is current", severity="info")

    return ScanResult(
        issues=[{"action": "reorder-tabs", "preview": output[:500]}],
        summary="Tab reordering available based on maturity scores",
        severity="info",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if ctx.dry_run:
        return FixResult(success=True, summary="Dry run: would reorder tabs based on maturity scores")

    scorer = _find_tab_scorer(ctx.project_root)
    if scorer is None:
        return FixResult(success=False, summary="tab_scorer.py not found")

    result = subprocess.run(
        [str(get_python_executable()), str(scorer)],
        capture_output=True,
        text=True,
        cwd=str(ctx.project_root),
    )

    if result.returncode != 0:
        return FixResult(success=False, summary=f"Tab scoring failed: {result.stderr[:300]}")

    # Stage any modified skill metadata files
    metadata_files = []
    for client_skills_dir in get_all_client_skill_dirs(ctx.project_root):
        if not client_skills_dir.resolve().is_relative_to(ctx.project_root.resolve()):
            continue
        for skill_dir in client_skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            for candidate in (skill_dir / "SKILL.md", skill_dir / "config.yaml"):
                if candidate.exists():
                    metadata_files.append(candidate)
    sha = _commit_files(
        ctx.project_root,
        "chore(adaptive): reorder tabs by maturity score",
        [str(f.relative_to(ctx.project_root)) for f in metadata_files],
    )

    summary = f"Tabs reordered (commit {sha})" if sha else "Tabs reordered (no changes to commit)"
    return FixResult(success=True, summary=summary)
