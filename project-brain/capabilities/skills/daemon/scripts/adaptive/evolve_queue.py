"""Evolve queue: persist and retrieve auto-remediation suggestions.

ADR-458: After generate_evolve_analysis() identifies report-only scanners,
this module persists the findings to a JSON queue file for later remediation.
Each entry is classified by fix difficulty:
  - reclassify: change issue `kind` fields (trivial, safe to auto-apply)
  - filter: fix scanner logic to stop false positives (medium)
  - upgrade-fix: make fix() actually resolve issues (hard, needs LLM agent)
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
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import get_state_dir


def _queue_path() -> Path:
    return get_state_dir() / "adaptive" / "evolve_queue.json"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

# Fix difficulty classification
FIX_RECLASSIFY = "reclassify"
FIX_FILTER = "filter"
FIX_UPGRADE = "upgrade-fix"


@dataclass
class EvolveEntry:
    """A single evolve suggestion queued for remediation."""

    category: str
    loop_name: str
    issue_count: int
    outcome: str  # "report-only", "broken", etc.
    fix_type: str  # FIX_RECLASSIFY, FIX_FILTER, FIX_UPGRADE
    suggestion: str  # Human-readable improvement suggestion
    scanner_path: str = ""  # Absolute path to scanner module
    created_at: str = ""
    applied: bool = False
    applied_at: str = ""
    result: str = ""  # "improved", "no-change", "reverted"

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class EvolveQueue:
    """The full queue of evolve suggestions."""

    entries: list[EvolveEntry] = field(default_factory=list)
    last_updated: str = ""

    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Fix type classification
# ---------------------------------------------------------------------------

# Categories whose issues are mostly false positives that should be reclassified
# from "actionable" to "maintenance" or "scanner-defect"
_RECLASSIFY_SIGNALS = {
    "report-only",  # scan works, fix() just writes reports
}

# Categories whose scanners produce too many false positives
_FILTER_SIGNALS = {
    "broken",  # fix() failed, scanner logic likely wrong
}


def classify_fix_type(outcome: str, issue_count: int) -> str:
    """Classify the appropriate fix type for a wasted category.

    Heuristic:
    - report-only with high issue count → likely false positives → reclassify
    - report-only with low issue count → scanner needs filter logic
    - broken → scanner logic needs debugging → filter
    - anything else with many issues → upgrade-fix (needs LLM)
    """
    if outcome in _RECLASSIFY_SIGNALS and issue_count > 10:
        return FIX_RECLASSIFY
    if outcome in _FILTER_SIGNALS:
        return FIX_FILTER
    if outcome in _RECLASSIFY_SIGNALS:
        return FIX_FILTER
    return FIX_UPGRADE


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def read_queue() -> EvolveQueue:
    """Read the evolve queue from disk. Returns empty queue if not found."""
    path = _queue_path()
    if not path.exists():
        return EvolveQueue()
    try:
        data = json.loads(path.read_text())
        entries = [EvolveEntry(**e) for e in data.get("entries", [])]
        return EvolveQueue(
            entries=entries,
            last_updated=data.get("last_updated", ""),
        )
    except (json.JSONDecodeError, OSError, TypeError):
        return EvolveQueue()


def write_queue(queue: EvolveQueue) -> Path:
    """Write the evolve queue to disk. Returns the queue file path."""
    path = _queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    queue.last_updated = datetime.now(timezone.utc).isoformat()
    data = {
        "entries": [asdict(e) for e in queue.entries],
        "last_updated": queue.last_updated,
    }
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path


def clear_queue() -> None:
    """Remove all entries from the queue."""
    path = _queue_path()
    if path.exists():
        path.unlink()


def pending_entries(queue: EvolveQueue | None = None) -> list[EvolveEntry]:
    """Return entries that haven't been applied yet."""
    if queue is None:
        queue = read_queue()
    return [e for e in queue.entries if not e.applied]


# ---------------------------------------------------------------------------
# Persist evolve analysis results
# ---------------------------------------------------------------------------

def persist_suggestions(
    reports: list,
    project_root: Path,
    auto_commands: dict | None = None,
) -> list[EvolveEntry]:
    """Extract wasted categories from cycle reports and persist to queue.

    Args:
        reports: List of CycleReport objects from the engine run.
        project_root: Project root for scanner path resolution.
        auto_commands: Engine's auto_commands registry for module path lookup.

    Returns:
        List of new EvolveEntry objects added to the queue.
    """
    from .run_inspection import _suggest_improvement

    # Find categories that found automatable issues but produced no code fixes.
    # Purely manual/reporting scanners belong in loop reports, not the evolve queue.
    wasted = []
    reported_loops = {r.loop_name for r in reports}
    for r in reports:
        for cat in r.categories:
            issue_count = int(getattr(cat, "issue_count", 0) or 0)
            actionable_count = int(getattr(cat, "actionable_count", 0) or 0)
            scanner_defect_count = int(getattr(cat, "scanner_defect_count", 0) or 0)
            broken_count = int(getattr(cat, "broken_count", 0) or 0)
            automatable_issue_count = actionable_count + scanner_defect_count + broken_count
            if issue_count <= 0:
                continue
            if cat.outcome in {"auto-fixed", "clean"}:
                continue
            if automatable_issue_count <= 0:
                continue

            if issue_count > 0:
                wasted.append({
                    "name": cat.name,
                    "loop": r.loop_name,
                    "issues": cat.issue_count,
                    "outcome": cat.outcome,
                    "summary": cat.action_summary,
                })

    # Build module path lookup from auto_commands registry
    module_paths: dict[str, str] = {}
    if auto_commands:
        for loop_name, entries in auto_commands.items():
            for entry in entries:
                if hasattr(entry, "module") and hasattr(entry.module, "__file__"):
                    module_paths[entry.name] = str(entry.module.__file__)

    # Load existing queue and build lookup of pending entries by category
    queue = read_queue()
    pending_by_category: dict[str, EvolveEntry] = {
        e.category: e for e in queue.entries if not e.applied
    }
    # Track categories that were already resolved as "already-implemented" or
    # "fixed-manually" to prevent the same false-positive suggestion from being
    # re-queued every cycle.
    suppressed_categories: set[str] = {
        e.category
        for e in queue.entries
        if e.applied and e.result in ("already-implemented", "fixed-manually", "not-applicable")
    }

    new_entries = []
    wasted_keys = {(w["loop"], w["name"]) for w in wasted}

    # Close out pending entries for loops included in this evolve run when the
    # category is no longer showing up as wasted. This prevents stale queue
    # items from lingering after a scanner or UX fix lands.
    resolved_at = datetime.now(timezone.utc).isoformat()
    for entry in queue.entries:
        if entry.applied:
            continue
        if entry.loop_name not in reported_loops:
            continue
        if (entry.loop_name, entry.category) in wasted_keys:
            continue
        entry.applied = True
        entry.applied_at = resolved_at
        entry.result = "resolved-in-run"

    for w in wasted:
        name = w["name"]
        if name in pending_by_category:
            pending_by_category[name].issue_count = w["issues"]
            pending_by_category[name].outcome = w["outcome"]
            continue
        if name in suppressed_categories:
            continue

        fix_type = classify_fix_type(w["outcome"], w["issues"])
        suggestion = _suggest_improvement(name, w["outcome"])
        if not suggestion:
            suggestion = f"Upgrade {name} from {w['outcome']} to producing code fixes"

        entry = EvolveEntry(
            category=name,
            loop_name=w["loop"],
            issue_count=w["issues"],
            outcome=w["outcome"],
            fix_type=fix_type,
            suggestion=suggestion,
            scanner_path=module_paths.get(name, ""),
        )
        queue.entries.append(entry)
        new_entries.append(entry)

    if not wasted and not reported_loops:
        return []

    write_queue(queue)
    return new_entries


def format_pending_report() -> str:
    """Format a human-readable report of pending evolve suggestions."""
    queue = read_queue()
    pending = pending_entries(queue)

    if not pending:
        return "  No pending evolve suggestions."

    lines = [
        "",
        "─── Evolve Queue: Pending Improvements ───",
        "",
    ]

    # Group by fix type
    by_type: dict[str, list[EvolveEntry]] = {}
    for e in pending:
        by_type.setdefault(e.fix_type, []).append(e)

    type_labels = {
        FIX_RECLASSIFY: "Reclassify (auto-apply at d2+)",
        FIX_FILTER: "Filter (scanner logic fix)",
        FIX_UPGRADE: "Upgrade fix() (needs LLM agent at d4)",
    }

    for fix_type in [FIX_RECLASSIFY, FIX_FILTER, FIX_UPGRADE]:
        entries = by_type.get(fix_type, [])
        if not entries:
            continue
        total_issues = sum(e.issue_count for e in entries)
        lines.append(f"  {type_labels[fix_type]} — {len(entries)} scanners, {total_issues} issues")
        for e in sorted(entries, key=lambda x: x.issue_count, reverse=True):
            age = _age_str(e.created_at)
            lines.append(f"    {e.category}: {e.issue_count} issues ({age})")
            lines.append(f"      → {e.suggestion}")
        lines.append("")

    lines.append(f"  Total: {len(pending)} pending improvements")
    lines.append("")
    return "\n".join(lines)


def _age_str(iso_timestamp: str) -> str:
    """Format age of an entry as human-readable string."""
    try:
        created = datetime.fromisoformat(iso_timestamp)
        now = datetime.now(timezone.utc)
        delta = now - created
        if delta.days > 0:
            return f"{delta.days}d ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours}h ago"
        return "just now"
    except (ValueError, TypeError):
        return "unknown"
