"""auto-memory-consolidation: Detect and fix memory index bloat and staleness.

Scans linked client memory indexes for:
1. MEMORY.md size exceeding threshold (default 30k chars)
2. Superseded entries still in the index (body contains "SUPERSEDED by ...")
3. Oversized individual files (>8 KB feedback files that should be split)
4. Completed project memories (body contains "Completed" with a date)
5. Stale artifacts (.consolidate-lock, _consolidation_report.md)
6. Orphaned memory files not referenced by MEMORY.md

Difficulty escalation:
  - difficulty 0: report only (counts and sizes)
  - difficulty 1: remove superseded entries and stale artifacts
  - difficulty 2+: all of d1 + remove completed project files older than 30 days

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
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

from src.config.paths import get_claude_native_memory_dir
from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    evolution_gap,
    make_issue,
)

log = logging.getLogger(__name__)

name = "auto-memory-consolidation"

# Thresholds
MAX_INDEX_CHARS = 30_000
MAX_INDEX_ENTRIES = 50
MAX_FILE_SIZE_BYTES = 8_192  # 8 KB — feedback files above this need splitting

# Stale artifacts that should be cleaned up unconditionally
_STALE_ARTIFACTS = {".consolidate-lock", "_consolidation_report.md"}

_SUPERSEDED_RE = re.compile(r"SUPERSEDED\s+by\s+\S+", re.IGNORECASE)
_COMPLETED_RE = re.compile(
    r"Completed\s+(\d{4}-\d{2}-\d{2})", re.IGNORECASE
)


def resolve_default_client_memory_plan(*, project_root: Path) -> dict:
    skills_dir = Path(__file__).resolve().parents[3]
    ops_dir = skills_dir / "ai" / "scripts" / "ops"
    if str(ops_dir) not in _augur_sys.path:
        _augur_sys.path.insert(0, str(ops_dir))
    from memory_assembler import resolve_default_client_memory_plan as _resolve

    return _resolve(project_root=project_root)


def _find_memory_dir(project_root: Path) -> Path | None:
    """Locate the first linked client memory directory with a MEMORY.md index."""
    try:
        plan = resolve_default_client_memory_plan(project_root=project_root)
        for output in plan.get("outputs", []):
            if output.get("kind") != "linked_index":
                continue
            memory_dir = Path(output["dir"])
            if (memory_dir / "MEMORY.md").exists():
                return memory_dir
    except Exception:
        pass

    memory_dir = get_claude_native_memory_dir(project_root)
    if memory_dir is not None:
        return memory_dir
    candidate = project_root / ".claude" / "projects"
    if candidate.is_dir():
        for d in candidate.iterdir():
            mem = d / "memory"
            if mem.is_dir() and (mem / "MEMORY.md").exists():
                return mem
    return None


def _parse_index_entries(memory_dir: Path) -> list[str]:
    """Extract filenames referenced in MEMORY.md."""
    index_file = memory_dir / "MEMORY.md"
    if not index_file.exists():
        return []
    content = index_file.read_text()
    return re.findall(r"\]\(([^)]+\.md)\)", content)


def _read_file_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _is_superseded(content: str) -> bool:
    """Check if file content contains a SUPERSEDED marker."""
    return bool(_SUPERSEDED_RE.search(content))


def _completed_date(content: str) -> datetime | None:
    """Extract completion date from project memory content, or None."""
    m = _COMPLETED_RE.search(content)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d")
        except ValueError:
            pass
    return None


def _remove_index_entry(memory_dir: Path, filename: str) -> bool:
    """Remove a single entry line from MEMORY.md that links to filename."""
    index_file = memory_dir / "MEMORY.md"
    if not index_file.exists():
        return False
    lines = index_file.read_text(encoding="utf-8").splitlines(keepends=True)
    pattern = re.compile(re.escape(f"]({filename})"))
    new_lines = [ln for ln in lines if not pattern.search(ln)]
    if len(new_lines) == len(lines):
        return False
    index_file.write_text("".join(new_lines), encoding="utf-8")
    return True


def scan(ctx: OpsContext) -> ScanResult:
    """Detect memory index bloat, superseded entries, and stale artifacts."""
    memory_dir = _find_memory_dir(ctx.project_root)
    if not memory_dir:
        return ScanResult(
            issues=[], summary="No memory directory found",
            severity="info", items_scanned=0,
        )

    index_file = memory_dir / "MEMORY.md"
    if not index_file.exists():
        return ScanResult(
            issues=[], summary="No MEMORY.md found",
            severity="info", items_scanned=0,
        )

    content = index_file.read_text()
    char_count = len(content)
    indexed_files = _parse_index_entries(memory_dir)
    entry_count = len(indexed_files)
    all_md = [f for f in memory_dir.glob("*.md") if f.name != "MEMORY.md"]
    total_files = len(all_md)

    issues: list[dict] = []

    # --- Index size ---
    if char_count > MAX_INDEX_CHARS:
        issues.append(make_issue(
            category="memory-consolidation", kind="actionable",
            detail=f"MEMORY.md is {char_count:,} chars (limit: {MAX_INDEX_CHARS:,})",
            path=str(index_file), root_cause_type="manual_debt",
            fixability="auto" if ctx.difficulty >= 2 else "manual",
        ))

    # --- Entry count ---
    if entry_count > MAX_INDEX_ENTRIES:
        issues.append(make_issue(
            category="memory-consolidation", kind="actionable",
            detail=f"MEMORY.md has {entry_count} entries (limit: {MAX_INDEX_ENTRIES})",
            path=str(index_file), root_cause_type="manual_debt",
            fixability="manual",
        ))

    # --- Superseded entries ---
    superseded: list[str] = []
    for md_file in all_md:
        body = _read_file_safe(md_file)
        if _is_superseded(body):
            superseded.append(md_file.name)
    if superseded:
        issues.append(make_issue(
            category="memory-consolidation", kind="actionable",
            detail=f"{len(superseded)} superseded entries still present",
            root_cause_type="manual_debt", fixability="auto",
            files=superseded,
        ))

    # --- Oversized files ---
    oversized: list[dict] = []
    for md_file in all_md:
        size = md_file.stat().st_size
        if size > MAX_FILE_SIZE_BYTES:
            oversized.append({"file": md_file.name, "size": size})
    if oversized:
        names = [o["file"] for o in oversized]
        issues.append(make_issue(
            category="memory-consolidation", kind="maintenance",
            detail=f"{len(oversized)} files exceed {MAX_FILE_SIZE_BYTES // 1024} KB: {', '.join(names)}",
            root_cause_type="manual_debt", fixability="manual",
            files=oversized,
        ))

    # --- Completed project memories ---
    completed: list[dict] = []
    now = datetime.now()
    for md_file in all_md:
        if not md_file.name.startswith("project_"):
            continue
        body = _read_file_safe(md_file)
        done_date = _completed_date(body)
        if done_date and (now - done_date) > timedelta(days=30):
            completed.append({
                "file": md_file.name,
                "completed": done_date.strftime("%Y-%m-%d"),
                "age_days": (now - done_date).days,
            })
    if completed:
        issues.append(make_issue(
            category="memory-consolidation", kind="actionable",
            detail=f"{len(completed)} completed project memories older than 30 days",
            root_cause_type="manual_debt", fixability="auto",
            files=completed,
        ))

    # --- Stale artifacts ---
    stale_found: list[str] = []
    for artifact_name in _STALE_ARTIFACTS:
        artifact = memory_dir / artifact_name
        if artifact.exists():
            stale_found.append(artifact_name)
    if stale_found:
        issues.append(make_issue(
            category="memory-consolidation", kind="actionable",
            detail=f"Stale artifacts: {', '.join(stale_found)}",
            root_cause_type="generated_artifact", fixability="auto",
            files=stale_found,
        ))

    # --- Orphaned files ---
    indexed_set = set(indexed_files)
    orphans = [
        f.name for f in all_md
        if f.name not in indexed_set and f.name not in _STALE_ARTIFACTS
    ]
    if orphans:
        issues.append(make_issue(
            category="memory-consolidation", kind="maintenance",
            detail=f"{len(orphans)} memory files not in index",
            root_cause_type="manual_debt", fixability="manual",
            orphan_files=orphans,
        ))

    if not issues:
        issues.append(evolution_gap(
            "Memory is well-organized. Next: add per-file body quality checks "
            "(detect stale references to renamed files/functions)."
        ))

    severity = "warning" if any(
        i.get("kind") == "actionable" for i in issues
    ) else "info"
    health = "degraded" if char_count > MAX_INDEX_CHARS else "verified"

    return ScanResult(
        issues=issues,
        summary=(
            f"Memory: {char_count:,} chars, {entry_count} entries, "
            f"{len(superseded)} superseded, {len(oversized)} oversized, "
            f"{len(completed)} completed-stale, {len(orphans)} orphans"
        ),
        severity=severity, health=health, items_scanned=total_files,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix memory consolidation issues.

    d0: report only.
    d1: remove superseded entries + stale artifacts.
    d2+: all of d1 + remove completed project memories >30 days old.
    """
    if ctx.dry_run:
        return FixResult(
            success=True,
            actions=[{"action": "dry_run", "description": f"Would address {len(issues)} issue(s)"}],
            summary=f"Dry run: {len(issues)} issue(s) detected",
        )

    if ctx.difficulty < 1:
        return FixResult(
            success=True,
            actions=[{"action": "report", "description": "Difficulty 0 — report only"}],
            summary="Report only at difficulty 0",
            fix_type="report",
        )

    memory_dir = _find_memory_dir(ctx.project_root)
    if not memory_dir:
        return FixResult(success=False, summary="Memory directory not found")

    actions: list[dict] = []
    changes: list[str] = []

    # --- d1+: Remove stale artifacts ---
    for artifact_name in _STALE_ARTIFACTS:
        artifact = memory_dir / artifact_name
        if artifact.exists():
            artifact.unlink()
            actions.append({"action": "delete-artifact", "file": artifact_name})
            changes.append(f"Deleted stale artifact {artifact_name}")
            log.info("Deleted stale artifact: %s", artifact)

    # --- d1+: Remove superseded entries ---
    for issue in issues:
        if "files" not in issue:
            continue
        files = issue["files"]
        # Superseded entries: list of filename strings
        if issue.get("detail", "").startswith(("superseded", "Superseded")) or "superseded" in issue.get("detail", "").lower():
            for filename in files:
                # filename is a string for superseded issues
                if not isinstance(filename, str):
                    continue
                file_path = memory_dir / filename
                if file_path.exists():
                    file_path.unlink()
                    _remove_index_entry(memory_dir, filename)
                    actions.append({"action": "delete-superseded", "file": filename})
                    changes.append(f"Removed superseded entry {filename}")
                    log.info("Removed superseded: %s", filename)

    # --- d2+: Remove completed project memories >30 days old ---
    if ctx.difficulty >= 2:
        for issue in issues:
            if "completed project" not in issue.get("detail", "").lower():
                continue
            for entry in issue.get("files", []):
                if not isinstance(entry, dict):
                    continue
                filename = entry.get("file", "")
                file_path = memory_dir / filename
                if file_path.exists():
                    file_path.unlink()
                    _remove_index_entry(memory_dir, filename)
                    actions.append({
                        "action": "archive-completed",
                        "file": filename,
                        "completed": entry.get("completed"),
                    })
                    changes.append(
                        f"Removed completed project memory {filename} "
                        f"(completed {entry.get('completed')}, {entry.get('age_days')}d ago)"
                    )
                    log.info("Archived completed project memory: %s", filename)

    if not changes:
        return FixResult(
            success=True, actions=actions, changes=changes,
            summary="No auto-fixable issues at current difficulty",
            fix_type="report",
        )

    return FixResult(
        success=True, actions=actions, changes=changes,
        summary=f"Consolidated memory: {len(changes)} changes applied",
        fix_type="sync",
    )
