"""auto-tidy: Scan, review, and clean up TODO_ markers in the codebase.

Marker types (from SKILL.md):
  TODO_BUG, TODO_SECURITY, TODO_WORKAROUND, TODO_MISPLACED,
  TODO_OUTDATED, TODO_CLEANUP, TODO_REFACTOR, TODO_IMPROVE, TODO_IDEA, TODO_NEWSKILL

Difficulty levels:
  d0: Surface — count markers per type and report
  d1: Content — auto-remove comment-only TODO_CLEANUP and TODO_OUTDATED lines
  d2: Deep — flag stale markers (>90 days unchanged), prioritize by severity
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
import subprocess
from pathlib import Path

from src.config.paths import get_project_root
from src.lib.ops_protocol import (
    DifficultySpec,
    FixResult,
    OpsContext,
    ScanResult,
    evolution_gap,
    make_issue,
)

name = "auto-tidy"

DIFFICULTY_SPEC: DifficultySpec = {
    0: "Surface — count markers per type and report",
    1: "Content — auto-remove comment-only TODO_CLEANUP and TODO_OUTDATED lines",
    2: "Deep — flag stale markers (>90 days unchanged), prioritize by severity",
}

logger = logging.getLogger(__name__)

# Markers ordered by priority (high to low)
MARKER_PRIORITY: dict[str, str] = {
    "TODO_BUG": "high",
    "TODO_SECURITY": "high",
    "TODO_WORKAROUND": "medium",
    "TODO_MISPLACED": "medium",
    "TODO_OUTDATED": "low",
    "TODO_CLEANUP": "low",
    "TODO_REFACTOR": "low",
    "TODO_IMPROVE": "low",
    "TODO_IDEA": "low",
    "TODO_NEWSKILL": "low",
}

MARKER_PATTERN = re.compile(
    r"\b(TODO_BUG|TODO_SECURITY|TODO_WORKAROUND|TODO_MISPLACED"
    r"|TODO_OUTDATED|TODO_CLEANUP|TODO_REFACTOR|TODO_IMPROVE"
    r"|TODO_IDEA|TODO_NEWSKILL)\b"
)

# Extensions to scan
SCAN_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}

# Directories to scan (relative to project root)
SCAN_DIRS = ["skills", "src", "apps"]

# Comment-only line patterns (Python and TypeScript)
_COMMENT_ONLY_PY = re.compile(r"^\s*#.*$")
_COMMENT_ONLY_TS = re.compile(r"^\s*//.*$")


def _is_comment_only(line: str, ext: str) -> bool:
    """Check if a line is a comment-only line."""
    if ext == ".py":
        return bool(_COMMENT_ONLY_PY.match(line))
    return bool(_COMMENT_ONLY_TS.match(line))


def _scan_file(path: Path, project_root: Path) -> list[dict]:
    """Scan a single file for TODO_ markers."""
    hits: list[dict] = []
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return hits
    rel = str(path.relative_to(project_root))
    for lineno, line in enumerate(content.splitlines(), 1):
        for m in MARKER_PATTERN.finditer(line):
            marker = m.group(1)
            hits.append({
                "marker": marker,
                "path": rel,
                "line": lineno,
                "text": line.strip(),
                "priority": MARKER_PRIORITY.get(marker, "low"),
                "is_comment_only": _is_comment_only(line, path.suffix),
            })
    return hits


def _get_file_last_modified_days(path: Path, project_root: Path) -> int | None:
    """Get days since last git modification of a file."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%at", "--", str(path)],
            cwd=str(project_root),
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            import time
            ts = int(result.stdout.strip())
            return int((time.time() - ts) / 86400)
    except Exception:
        pass
    return None


def scan(ctx: OpsContext) -> ScanResult:
    """Scan codebase for TODO_ markers."""
    project_root = get_project_root()
    issues: list[dict] = []
    all_hits: list[dict] = []
    items_scanned = 0

    # Collect all files to scan
    for scan_dir_name in SCAN_DIRS:
        scan_dir = project_root / scan_dir_name
        if not scan_dir.is_dir():
            continue
        for path in scan_dir.rglob("*"):
            if not path.is_file() or path.suffix not in SCAN_EXTENSIONS:
                continue
            if any(part.startswith(".") or part == "node_modules" for part in path.parts):
                continue
            items_scanned += 1
            hits = _scan_file(path, project_root)
            all_hits.extend(hits)

    # --- d0: Report marker counts ---
    if not all_hits:
        if ctx.difficulty >= 2:
            issues.append(evolution_gap(
                "No TODO_ markers found in codebase. "
                "Consider adding: check for bare TODO/FIXME without TODO_ prefix "
                "(non-standard markers), check for stale BACKLOG.md items. "
                "Next: scan for non-standard TODO patterns.",
                category="tidy",
            ))
        return ScanResult(
            issues=issues,
            summary="No TODO_ markers found",
            severity="info",
            health="verified",
            items_scanned=items_scanned,
        )

    # Group by marker type for summary
    by_type: dict[str, int] = {}
    for hit in all_hits:
        by_type[hit["marker"]] = by_type.get(hit["marker"], 0) + 1

    # Create issues for each marker hit
    for hit in all_hits:
        priority = hit["priority"]
        severity: str = "warning" if priority in ("high", "medium") else "info"
        # d0 is observational. Comment-only markers are safe maintenance
        # items, and embedded high/medium markers only become actionable once
        # the loop is running at a difficulty that has a fix/review path.
        if ctx.difficulty < 1:
            kind = "maintenance"
        elif hit["is_comment_only"]:
            kind = "maintenance"
        else:
            kind = "actionable" if priority in ("high", "medium") else "maintenance"

        issues.append(make_issue(
            category="tidy",
            detail=f"{hit['marker']} at line {hit['line']}: {hit['text'][:120]}",
            path=hit["path"],
            kind=kind,
            root_cause_type="manual_debt",
            fixability="auto" if hit["marker"] in ("TODO_CLEANUP", "TODO_OUTDATED") and hit["is_comment_only"] else "manual",
            marker=hit["marker"],
            line=hit["line"],
            priority=priority,
            is_comment_only=hit["is_comment_only"],
        ))

    # --- d2: Flag stale markers (>90 days unchanged) ---
    if ctx.difficulty >= 2:
        stale_files: set[str] = set()
        for hit in all_hits:
            if hit["path"] in stale_files:
                continue
            days = _get_file_last_modified_days(
                project_root / hit["path"], project_root
            )
            if days is not None and days > 90:
                stale_files.add(hit["path"])
                issues.append(make_issue(
                    category="tidy",
                    detail=f"File has markers untouched for {days} days — review for staleness",
                    path=hit["path"],
                    kind="maintenance",
                    root_cause_type="manual_debt",
                    fixability="manual",
                    stale_days=days,
                ))

    # --- d2 evolution gap if everything is low priority ---
    if ctx.difficulty >= 2 and all(h["priority"] == "low" for h in all_hits):
        issues.append(evolution_gap(
            "All markers are low-priority. Consider: check marker age distribution, "
            "detect markers in generated files that should not have manual TODOs, "
            "verify markers reference valid ADRs. Next: add age-based escalation.",
            category="tidy",
        ))

    severity = "warning" if any(i.get("priority") in ("high", "medium") for i in issues if "priority" in i) else "info"
    health = "degraded" if severity == "warning" else "verified"

    type_summary = ", ".join(f"{k}={v}" for k, v in sorted(by_type.items()))
    return ScanResult(
        issues=issues,
        summary=f"{len(all_hits)} markers ({type_summary})",
        severity=severity,
        health=health,
        items_scanned=items_scanned,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix TODO_ marker issues.

    d0: Report only.
    d1+: Auto-remove comment-only TODO_CLEANUP and TODO_OUTDATED lines.
    """
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} marker issues found")

    if not issues:
        return FixResult(success=True, summary="No marker issues to fix")

    # d0: report only
    if ctx.difficulty < 1:
        return FixResult(
            success=True,
            summary=f"{len(issues)} markers found (report only at d0)",
            fix_type="report",
        )

    # d1+: auto-remove safe comment-only lines
    project_root = get_project_root()
    actions: list[dict] = []
    changes: list[str] = []

    # Group auto-fixable issues by file
    auto_fixable: dict[str, list[int]] = {}
    for issue in issues:
        marker = issue.get("marker", "")
        if marker not in ("TODO_CLEANUP", "TODO_OUTDATED"):
            continue
        if not issue.get("is_comment_only", False):
            continue
        if issue.get("fixability") != "auto":
            continue
        path = issue.get("path", "")
        line = issue.get("line")
        if path and line:
            auto_fixable.setdefault(path, []).append(line)

    for rel_path, lines_to_remove in auto_fixable.items():
        full_path = project_root / rel_path
        if not full_path.is_file():
            continue
        try:
            file_lines = full_path.read_text(encoding="utf-8").splitlines(keepends=True)
            # Remove lines in reverse order to preserve line numbers
            remove_set = set(lines_to_remove)
            new_lines = [
                line for i, line in enumerate(file_lines, 1)
                if i not in remove_set
            ]
            full_path.write_text("".join(new_lines), encoding="utf-8")
            actions.append({
                "action": "remove_markers",
                "file": rel_path,
                "lines_removed": sorted(lines_to_remove),
            })
            changes.append(f"Removed {len(lines_to_remove)} comment-only marker(s) from {rel_path}")
        except OSError as e:
            logger.warning("Failed to fix %s: %s", rel_path, e)

    manual_count = len(issues) - sum(len(v) for v in auto_fixable.values())
    summary_parts = []
    if actions:
        summary_parts.append(f"Removed markers from {len(actions)} file(s)")
    if manual_count > 0:
        summary_parts.append(f"{manual_count} marker(s) require manual review")
    summary = "; ".join(summary_parts) if summary_parts else "No auto-fixable markers"

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=summary,
        fix_type="code-fix" if actions else "report",
    )
