"""Evolve auto-remediation: apply queued fixes to scanners.

ADR-458 Phase 2: After the evolve queue identifies report-only scanners,
this module applies trivial fixes (reclassify) at d2+ and tracks outcomes.

Reclassify fixes work by writing a self-repair hint file that the scanner
reads on its next run to reclassify issues from "actionable" to the correct
kind (maintenance, scanner-defect, etc.). This is safe because:
  - It doesn't modify scanner source code directly
  - The hint is a data file, not code
  - If the scanner ignores it, nothing breaks
  - Re-running the scanner validates the improvement
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
import logging
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import get_state_dir

from .evolve_queue import (
    EvolveEntry,
    EvolveQueue,
    FIX_RECLASSIFY,
    read_queue,
    write_queue,
)

logger = logging.getLogger(__name__)


def _hints_dir() -> Path:
    return get_state_dir() / "adaptive" / "evolve_hints"


def _write_reclassify_hint(entry: EvolveEntry) -> Path | None:
    """Write a reclassify hint file for a scanner category.

    The hint tells the scanner that its high issue count is likely false
    positives, and suggests reclassifying bulk issues from "actionable" to
    "maintenance". Scanners that support evolve hints will read this file.

    Returns the hint path, or None if the entry is not suitable.
    """
    if entry.fix_type != FIX_RECLASSIFY:
        return None

    hints_dir = _hints_dir()
    hints_dir.mkdir(parents=True, exist_ok=True)
    hint_path = hints_dir / f"{entry.category}.json"

    hint = {
        "category": entry.category,
        "action": FIX_RECLASSIFY,
        "from_kind": "actionable",
        "to_kind": "maintenance",
        "reason": (
            f"Evolve analysis identified {entry.issue_count} issues as likely "
            f"false positives ({entry.outcome}). Reclassifying to maintenance."
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scanner_path": entry.scanner_path,
    }
    hint_path.write_text(json.dumps(hint, indent=2) + "\n")
    return hint_path


_hint_cache: dict[str, dict | None] = {}


def load_all_hints() -> None:
    """Pre-load all hint files into memory. Call once per cycle to avoid
    repeated file I/O in the hot scan path (engine_entry_runner)."""
    _hint_cache.clear()
    hints_dir = _hints_dir()
    if not hints_dir.exists():
        return
    for hint_path in hints_dir.glob("*.json"):
        try:
            _hint_cache[hint_path.stem] = json.loads(hint_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass


def get_reclassify_hint(category: str) -> dict | None:
    """Read a reclassify hint for a category, if one exists.

    Uses in-memory cache populated by load_all_hints(). Falls back to
    disk read if cache is empty (first call before load_all_hints).
    """
    if _hint_cache is not None and category in _hint_cache:
        return _hint_cache[category]
    # Fallback: direct disk read (e.g., standalone usage outside engine cycle)
    hint_path = _hints_dir() / f"{category}.json"
    if not hint_path.exists():
        return None
    try:
        hint = json.loads(hint_path.read_text())
        _hint_cache[category] = hint
        return hint
    except (json.JSONDecodeError, OSError):
        return None


def clear_hint(category: str) -> None:
    """Remove a reclassify hint after it's been applied or rejected."""
    _hint_cache.pop(category, None)
    hint_path = _hints_dir() / f"{category}.json"
    if hint_path.exists():
        hint_path.unlink()


def apply_reclassify(
    queue: EvolveQueue | None = None,
    dry_run: bool = False,
) -> list[dict]:
    """Apply reclassify fixes for all pending reclassify entries.

    For each reclassify entry:
    1. Write a hint file that the scanner will read on next run
    2. Mark the entry as applied
    3. Track the outcome for verification on next evolve cycle

    Args:
        queue: Optional queue to use (reads from disk if None).
        dry_run: If True, log what would happen without writing hints.

    Returns:
        List of result dicts with category, action, and outcome.
    """
    if queue is None:
        queue = read_queue()

    results = []
    reclassify_entries = [
        e for e in queue.entries
        if e.fix_type == FIX_RECLASSIFY and not e.applied
    ]

    if not reclassify_entries:
        return results

    for entry in reclassify_entries:
        result = {
            "category": entry.category,
            "action": "reclassify",
            "issue_count": entry.issue_count,
        }

        if dry_run:
            result["outcome"] = "dry-run"
            logger.info(
                "Would write reclassify hint for %s (%d issues)",
                entry.category, entry.issue_count,
            )
            results.append(result)
            continue

        hint_path = _write_reclassify_hint(entry)
        if hint_path:
            entry.applied = True
            entry.applied_at = datetime.now(timezone.utc).isoformat()
            entry.result = "hint-written"
            result["outcome"] = "hint-written"
            result["hint_path"] = str(hint_path)
            logger.info(
                "Wrote reclassify hint for %s → %s",
                entry.category, hint_path,
            )
        else:
            result["outcome"] = "skipped"

        results.append(result)

    if not dry_run:
        write_queue(queue)

    return results


def verify_reclassify(
    category: str,
    old_issue_count: int,
    new_issue_count: int,
) -> str:
    """Verify a reclassify fix improved the scanner's issue count.

    Called after re-running a scanner that had a reclassify hint applied.

    Returns:
        "improved" if actionable count decreased,
        "no-change" if unchanged,
        "reverted" if hint was removed due to no improvement.
    """
    if new_issue_count < old_issue_count:
        # Success — clear the hint (scanner internalized the reclassification)
        logger.info(
            "Reclassify verified for %s: %d → %d issues",
            category, old_issue_count, new_issue_count,
        )
        return "improved"

    if new_issue_count == old_issue_count:
        # Scanner didn't read the hint — revert
        clear_hint(category)
        logger.warning(
            "Reclassify had no effect on %s (%d issues), hint removed",
            category, old_issue_count,
        )
        return "no-change"

    # Issue count increased — definitely revert
    clear_hint(category)
    logger.warning(
        "Reclassify worsened %s: %d → %d issues, hint removed",
        category, old_issue_count, new_issue_count,
    )
    return "reverted"


def format_remediation_report(results: list[dict]) -> str:
    """Format auto-remediation results for terminal display."""
    if not results:
        return ""

    lines = [
        "",
        "  ── Auto-Remediation (ADR-458) ──",
        "",
    ]

    for r in results:
        outcome = r.get("outcome", "unknown")
        category = r.get("category", "unknown")
        issues = r.get("issue_count", 0)
        lines.append(f"    {category}: {outcome} ({issues} issues)")

    lines.append("")
    return "\n".join(lines)
