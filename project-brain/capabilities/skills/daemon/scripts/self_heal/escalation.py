"""Escalation — tracking recurring issues, dedup logic, TODO marker and critical item creation."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ai_self_healer import ErrorFinding, RegistryEntry


def deduplicate_findings(
    findings: list["ErrorFinding"],
    registry: dict[str, "RegistryEntry"],
    config: Optional[dict] = None,
) -> list["ErrorFinding"]:
    """Filter findings against registry, update counts, return only actionable ones.

    Escalation: recurring issues that recur past escalation_threshold are promoted:
    low -> medium, medium -> high.  Re-queued for immediate fix.
    """
    import ai_self_healer as _healer

    actionable: list["ErrorFinding"] = []
    now = datetime.now()
    fix_conf = (config or {}).get("fix", {})
    max_attempts = fix_conf.get("max_fix_attempts", 3)
    escalation_threshold = fix_conf.get("escalation_threshold", 3)
    recover_stuck_fixing = bool(fix_conf.get("recover_stuck_fixing", False))

    for finding in findings:
        key = finding.dedup_key

        if key not in registry:
            # Brand new issue
            registry[key] = _healer.RegistryEntry(
                dedup_key=key,
                message=finding.message,
                file=finding.file,
                status="new",
                first_seen=finding.timestamp,
                last_seen=finding.timestamp,
                occurrences=1,
                stack_trace=finding.stack_trace,
            )
            actionable.append(finding)
            continue

        entry = registry[key]
        entry.last_seen = finding.timestamp
        entry.occurrences += 1

        if entry.status == "fixing":
            if not recover_stuck_fixing:
                continue
            # Check if the fix lock is still held — if not, the fixer crashed
            # and we need to recover the entry from the stuck "fixing" state.
            if _healer.FIX_LOCK_FILE.exists():
                try:
                    lock_data = json.loads(_healer.FIX_LOCK_FILE.read_text())
                    if lock_data.get("issue_key") == key:
                        # Active fix in progress for this entry, skip
                        continue
                except Exception:
                    pass
            # No active lock for this entry — recover from stuck "fixing" state
            if entry.fix_attempts >= max_attempts:
                entry.status = "abandoned"
            else:
                entry.status = "failed"
                actionable.append(finding)
            continue

        if entry.status == "dismissed":
            # Transient/runtime issue — never re-queue
            continue

        if entry.status == "fixed":
            # Check for regression
            if entry.fix_result == "resolved":
                fixed_time = datetime.fromisoformat(entry.last_seen) if entry.last_seen else now
                if (now - fixed_time).total_seconds() < 3600:
                    # Regression within 1 hour
                    entry.status = "new"
                    entry.fix_result = "regression"
                    actionable.append(finding)
                # else: old issue reappearing, treat as noise
            continue

        if entry.status == "failed":
            if entry.fix_attempts < max_attempts:
                entry.status = "new"
                actionable.append(finding)
            else:
                entry.status = "abandoned"
            continue

        if entry.status in ("abandoned", "todo_created"):
            # Escalation: recurring low/medium issues jump straight to HIGH
            if entry.severity in ("low", "medium") and entry.occurrences >= escalation_threshold:
                old_sev = entry.severity
                entry.severity = "high"
                _healer.logger.info(
                    f"Escalating {key} from {old_sev} to high "
                    f"(seen {entry.occurrences}x, threshold={escalation_threshold})"
                )
                entry.status = "new"
                entry.fix_attempts = 0
                entry.fix_result = f"escalated_from_{old_sev}"
                actionable.append(finding)
            continue

        if entry.status == "awaiting_manual_fix":
            # Already triaged — critical item exists, user was notified.
            # Don't re-queue; occurrence count is already updated above.
            continue

        # Escalation: low/medium issues that keep recurring in backlog states.
        if entry.status in ("new", "unclassified", "classifying"):
            if entry.severity in ("low", "medium") and entry.occurrences >= escalation_threshold:
                old_sev = entry.severity
                if entry.severity != "high":
                    _healer.logger.info(
                        f"Escalating {key} from {old_sev} to high "
                        f"(seen {entry.occurrences}x, threshold={escalation_threshold})"
                    )
                    entry.severity = "high"
                    entry.status = "new"
                    entry.fix_attempts = 0
                    entry.fix_result = f"escalated_from_{old_sev}"
                    actionable.append(finding)
            # Already pending or below threshold, don't re-queue
            continue

    return actionable


# ═══════════════════════════════════════════════════════════════════════════════
# TODO MARKER CREATION
# ═══════════════════════════════════════════════════════════════════════════════


def create_todo_marker(entry: "RegistryEntry") -> None:
    """Append a TODO_ marker to tech_debt.md (with dedup)."""
    import ai_self_healer as _healer

    _healer.TECH_DEBT_FILE.parent.mkdir(parents=True, exist_ok=True)

    marker_line = _format_marker(entry)

    # Check for existing marker with same dedup key
    if _healer.TECH_DEBT_FILE.exists():
        existing = _healer.TECH_DEBT_FILE.read_text()
        if entry.dedup_key in existing:
            # Update occurrence count in-place
            updated = re.sub(
                rf"(<!-- key:{entry.dedup_key} count:)\d+(\s*-->)",
                rf"\g<1>{entry.occurrences}\2",
                existing,
            )
            _healer.TECH_DEBT_FILE.write_text(updated)
            return
    else:
        existing = ""

    # Append new marker
    block = (
        f"\n{marker_line}\n"
        f"<!-- key:{entry.dedup_key} count:{entry.occurrences} -->\n"
        f"<!-- file:{entry.file} -->\n"
    )

    with open(_healer.TECH_DEBT_FILE, "a") as f:
        f.write(block)


def _format_marker(entry: "RegistryEntry") -> str:
    """Format a TODO_ marker string."""
    sev = entry.severity.lower()
    cat = entry.category or "integration"
    msg = entry.message[:150]
    ts = entry.last_seen[:10] if entry.last_seen else "unknown"

    if sev in ("critical", "high", "error"):
        return f"# TODO_BUG({cat}/{sev}): {msg} (seen {entry.occurrences}x, last: {ts})"
    return f"# TODO_IMPROVE({cat}): {msg} (seen {entry.occurrences}x, last: {ts})"


# ═══════════════════════════════════════════════════════════════════════════════
# CRITICAL ITEM CREATION
# ═══════════════════════════════════════════════════════════════════════════════


def create_critical_item(entry: "RegistryEntry") -> Path:
    """Create a structured backlog item in state/self_heal/critical/.

    Contains full error context so the user can investigate and fix manually.
    Returns the path to the created file.
    """
    import ai_self_healer as _healer

    _healer.CRITICAL_DIR.mkdir(parents=True, exist_ok=True)

    item_path = _healer.CRITICAL_DIR / f"{entry.dedup_key}.md"
    now = datetime.now().isoformat()

    content = f"""# Critical Issue: {entry.dedup_key}

**Status**: awaiting_manual_fix
**Created**: {now}
**Severity**: {entry.severity}
**Category**: {entry.category}
**Occurrences**: {entry.occurrences}
**First seen**: {entry.first_seen}
**Last seen**: {entry.last_seen}

## Error

```
{entry.message}
```

## Source

File: `{entry.file}`

## Stack Trace

```
{entry.stack_trace or 'N/A'}
```

## Suggested Approach

{entry.suggested_approach or 'Investigate the error and apply minimal fix.'}

## Fix History

- Fix attempts: {entry.fix_attempts}
- Last result: {entry.fix_result or 'N/A'}
"""

    item_path.write_text(content)
    _healer.logger.info(f"Created critical item: {item_path}")
    return item_path


def format_fix_prompt(entry: "RegistryEntry") -> str:
    """Format a copy-to-clipboard prompt the user can paste into CLI.

    Contains error context and suggested approach for manual fixing.
    """
    lines = [
        f"[SELF-HEAL] {entry.severity.upper()} issue needs manual fix",
        f"Error: {entry.message}",
        f"File: {entry.file}",
    ]
    if entry.stack_trace:
        lines.append(f"Stack: {entry.stack_trace[:300]}")
    lines.append(f"Category: {entry.category}")
    lines.append(f"Occurrences: {entry.occurrences}")
    if entry.suggested_approach:
        lines.append(f"Approach: {entry.suggested_approach}")
    lines.append(f"Dedup key: {entry.dedup_key}")
    return "\n".join(lines)
