"""auto-markers: Scan runtime TODO/FIXME markers and write tech debt report.

Extracted from CodeQualityLoop._run_scan_markers (ADR-200).
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
import re
import sys
from pathlib import Path

from src.config.paths import get_logs_dir, get_runtime_dir, get_project_brain_skills_dir
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

_DAEMON_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "daemon" / "scripts"
if str(_DAEMON_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_DAEMON_SCRIPTS_DIR))

# Import scanner helper gracefully
try:
    from runtime_marker_scanner import (
        collect_log_positions as _collect_log_positions,
        compute_error_fingerprint as _compute_error_fingerprint,
        load_scan_state as _load_scan_state,
        scan_all_logs as _scan_all_logs,
        scan_and_update as _scan_and_update,
    )
except ImportError:
    _collect_log_positions = None
    _compute_error_fingerprint = None
    _load_scan_state = None
    _scan_all_logs = None
    _scan_and_update = None

# Module-level reference so tests can patch
collect_log_positions = _collect_log_positions
compute_error_fingerprint = _compute_error_fingerprint
load_scan_state = _load_scan_state
scan_all_logs = _scan_all_logs
scan_and_update = _scan_and_update

name = "auto-markers"

DIFFICULTY_SPEC = {
    0: "Surface check — verify runtime_marker_scanner is importable",
    1: "Content check — scan for TODO_BUG, TODO_CLEANUP, FIXME, HACK, XXX",
    2: "Deep check — add workaround, temporary, DEPRECATED patterns",
    3: "Exhaustive — same as d2 (all known patterns)",
    4: "Expert — same as d2 (all known patterns)",
}

# Marker patterns by difficulty level: each level adds patterns
_MARKER_PATTERNS_BY_DIFFICULTY = {
    0: ["TODO_BUG", "TODO_CLEANUP"],
    1: ["FIXME", "HACK", "XXX"],
    2: ["workaround", "temporary", "DEPRECATED"],
}


def _latest_log_mtime() -> float:
    latest = 0.0
    logs_dir = get_logs_dir()
    if not logs_dir.exists():
        return latest
    for path in logs_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            latest = max(latest, path.stat().st_mtime)
        except OSError:
            continue
    return latest


def scan(ctx: OpsContext) -> ScanResult:
    """Check if runtime marker scanner is available and can run."""
    if scan_and_update is None:
        return ScanResult(
            issues=[],
            summary="runtime_marker_scanner not importable",
            severity="info",
            health="broken",
        )

    # d0: surface check — just verify scanner is importable
    if ctx.difficulty < 1:
        return ScanResult(
            issues=[],
            summary="runtime_marker_scanner available",
            severity="info",
            health="verified",
        )

    report_path = get_runtime_dir() / "tech_debt.md"
    if (
        scan_all_logs is not None
        and compute_error_fingerprint is not None
        and load_scan_state is not None
        and collect_log_positions is not None
    ):
        state = load_scan_state()
        previous_positions = state.get("log_positions", {})
        current_positions = collect_log_positions()
        if current_positions == previous_positions:
            summary = (
                "No new runtime log activity"
            )
            return ScanResult(
                issues=[],
                summary=summary,
                severity="info",
                health="verified",
            )
        errors = scan_all_logs(previous_positions)
        current_fingerprint = compute_error_fingerprint(errors)
        previous_fingerprint = state.get("fingerprint")
        if not errors and previous_fingerprint == current_fingerprint:
            return ScanResult(
                issues=[],
                summary="No new runtime markers detected",
                severity="info",
                health="verified",
            )
    else:
        latest_log = _latest_log_mtime()
        if report_path.exists() and report_path.stat().st_mtime >= latest_log:
            return ScanResult(
                issues=[],
                summary="Runtime marker report is current",
                severity="info",
                health="verified",
            )

    # d1+: Trigger a scan only when the report is missing or older than the logs
    patterns = []
    for level in range(ctx.difficulty + 1):
        patterns.extend(_MARKER_PATTERNS_BY_DIFFICULTY.get(level, []))

    return ScanResult(
        issues=[{"action": "scan-runtime-markers", "patterns": patterns}],
        summary=f"Marker scan ready (difficulty={ctx.difficulty}, patterns={len(patterns)})",
        severity="info",
    )


def _prune_stale_auto_markers(project_root: Path) -> list[str]:
    """Remove TODO_ markers injected by auto-loop scanners that are now resolved.

    Only removes markers tagged with a scanner origin (e.g. auto-dead-api) to avoid
    touching hand-written markers. Conservative: only prunes markers where the
    parenthetical tag indicates an auto-loop scanner produced them.
    """
    # Pattern matches lines like:
    #   // TODO_CLEANUP(auto-dead-api): Orphan API route /api/foo — no consumer
    #   # TODO_CLEANUP(auto-dead-api): ...
    auto_marker_re = re.compile(
        r'^[#/]*\s*TODO_(?:BUG|CLEANUP|OUTDATED|IMPROVE)\(auto-[\w-]+\):.*$'
    )

    pruned: list[str] = []
    search_dirs = [
        project_root / "apps" / "dashboard",
        project_root / "src",
        get_project_brain_skills_dir(project_root),
    ]

    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue
        for ext in ("*.py", "*.ts", "*.tsx", "*.yaml", "*.yml"):
            for filepath in search_dir.rglob(ext):
                try:
                    content = filepath.read_text()
                except Exception:
                    continue

                lines = content.splitlines(keepends=True)
                new_lines = [line for line in lines if not auto_marker_re.match(line.rstrip())]

                if len(new_lines) < len(lines):
                    removed = len(lines) - len(new_lines)
                    filepath.write_text("".join(new_lines))
                    rel = str(filepath.relative_to(project_root))
                    pruned.append(f"{rel} ({removed} marker(s))")

    return pruned


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Run the runtime marker scanner and prune stale auto-injected markers.

    Two-phase fix:
    1. Run scan_and_update() to refresh the tech_debt.md report
    2. Prune TODO_ markers injected by auto-loop scanners (tagged with scanner
       origin) that are no longer valid — the underlying issue was resolved
    """
    if scan_and_update is None:
        return FixResult(
            success=False,
            summary="runtime_marker_scanner not importable",
        )
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary="Dry run: would scan runtime markers and prune stale auto-markers",
        )

    changes: list[str] = []
    parts: list[str] = []

    # Phase 1: update the tech_debt.md report
    try:
        summary = scan_and_update()
        if summary.get("changed"):
            parts.append("Runtime marker report updated")
        else:
            parts.append("Runtime marker findings unchanged")
    except Exception as e:
        return FixResult(
            success=False,
            summary=f"Marker scan failed: {e}",
        )

    # Phase 2: prune stale auto-injected markers from source files
    pruned = _prune_stale_auto_markers(ctx.project_root)
    if pruned:
        changes.extend(entry.split(" (")[0] for entry in pruned)
        parts.append(f"Pruned stale auto-markers from {len(pruned)} file(s)")

    return FixResult(
        success=True,
        changes=changes,
        summary=". ".join(parts),
        fix_type="code-fix" if changes else "report",
    )
