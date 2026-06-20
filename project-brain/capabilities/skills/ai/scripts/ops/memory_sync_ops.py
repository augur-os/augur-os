"""auto-memory-sync: Detect uncurated daily logs and sync memory to all agents.
Extracted from /ops-memory (ADR-200).

Scan: checks the vault-backed memory daily log directory for entries that
haven't been curated to MEMORY.md.
Fix: runs memory_sync.py --sync to curate and distribute to all agent targets.
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
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.config.paths import get_memory_dir, get_python_executable
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult


name = "auto-memory-sync"


def _find_memory_script(project_root: Path) -> Path | None:
    candidate = project_root / ".github" / "scripts" / "memory_sync.py"
    return candidate if candidate.exists() else None


def _memory_tracked_paths(project_root: Path) -> list[str]:
    memory_dir = get_memory_dir()
    candidates = [
        memory_dir / "MEMORY.md",
        memory_dir / "decisions.md",
        memory_dir / "patterns.md",
        memory_dir / "preferences.md",
    ]
    tracked: list[str] = []
    for path in candidates:
        try:
            tracked.append(str(path.relative_to(project_root)))
        except ValueError:
            continue
    return tracked


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
    daily_dir = get_memory_dir() / "daily"
    if not daily_dir.is_dir():
        return ScanResult(issues=[], summary="No daily log directory found", severity="info")

    # Check for recent daily logs (last 7 days)
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=7)
    recent_logs: list[Path] = []
    for md_file in sorted(daily_dir.glob("*.md"), reverse=True):
        try:
            date_str = md_file.stem  # e.g. 2026-03-03
            file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if file_date >= cutoff:
                recent_logs.append(md_file)
        except ValueError:
            continue

    if not recent_logs:
        return ScanResult(issues=[], summary="No recent daily logs to curate", severity="info")

    # Check if MEMORY.md was updated after the most recent daily log
    memory_file = get_memory_dir() / "MEMORY.md"
    if memory_file.exists():
        memory_mtime = memory_file.stat().st_mtime
        newest_log_mtime = max(f.stat().st_mtime for f in recent_logs)
        if memory_mtime >= newest_log_mtime:
            return ScanResult(
                issues=[],
                summary=f"MEMORY.md is up to date ({len(recent_logs)} recent logs already curated)",
                severity="info",
            )

    return ScanResult(
        issues=[{
            "action": "sync-memory",
            "uncurated_logs": [str(f.name) for f in recent_logs],
            "count": len(recent_logs),
        }],
        summary=f"{len(recent_logs)} daily logs may need curation",
        severity="warning",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if ctx.dry_run:
        count = issues[0].get("count", 0) if issues else 0
        return FixResult(success=True, summary=f"Dry run: would curate {count} daily logs")

    script = _find_memory_script(ctx.project_root)
    if script is None:
        return FixResult(success=False, summary="memory_sync.py not found")

    result = subprocess.run(
        [str(get_python_executable()), str(script), "--sync"],
        capture_output=True,
        text=True,
        cwd=str(ctx.project_root),
    )

    if result.returncode != 0:
        return FixResult(success=False, summary=f"memory_sync failed: {result.stderr[:300]}")

    memory_paths = _memory_tracked_paths(ctx.project_root)
    sha = None
    if memory_paths:
        sha = _commit_files(
            ctx.project_root,
            "chore(adaptive): sync curated memory to all agents",
            memory_paths,
        )
    summary = (
        f"Memory synced (commit {sha})"
        if sha
        else "Memory synced (external vault changes are not committed in the core repo)"
    )
    return FixResult(success=True, summary=summary, fix_type="sync")
