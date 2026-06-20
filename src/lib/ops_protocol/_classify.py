"""
ops_protocol._classify — Fix classification and intentional-skip guard.

FixClassification, DeletionInfo, ModificationInfo, classify_fix,
make_migration_incomplete_issue, check_intentional_skip.

Internal use by the ops_protocol package; do not import directly from outside.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

# Import make_issue directly from _core to avoid circular imports via __init__
from src.lib.ops_protocol._core import make_issue

_DELETION_WINDOW_DAYS = 7
_MODIFICATION_WINDOW_DAYS = 7
_ADR_PATTERN = re.compile(r"ADR-\d+", re.IGNORECASE)
# Commit prefixes used by autoloops — modifications from these are not "user intent"
_AUTOLOOP_PREFIXES = ("chore(auto):", "chore(auto-", "fix(auto-", "fix(adaptive)", "docs(adaptive)")


class FixClassification(Enum):
    """Classification of an auto-loop fix (ADR-443)."""

    SAFE = "safe"  # Formatting, lint, marker updates — always apply
    STRUCTURAL = "structural"  # Missing files, broken data sources — report at d0-1, apply at d2+
    REVERTING = "reverting"  # Recreating recently deleted file — always block + alert
    MODIFIED = "modified"  # File recently modified by user — block to avoid overwriting intent


@dataclass
class DeletionInfo:
    """Git history for a deleted file (ADR-443)."""

    deleted_date: datetime
    commit_hash: str
    commit_message: str
    adr_reference: str | None  # e.g. "ADR-430" or None


@dataclass
class ModificationInfo:
    """Git history for a recently modified file."""

    modified_date: datetime
    commit_hash: str
    commit_message: str
    is_user_change: bool  # True if commit is NOT from an autoloop


def _check_git_deletion_history(
    path: str,
    project_root: Path | None = None,
) -> DeletionInfo | None:
    """Check if a file was recently deleted in git history."""
    current_path = Path(project_root, path) if project_root else Path(path)
    if current_path.exists():
        return None

    cwd = str(project_root) if project_root else None
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--diff-filter=D",
                "--format=%H %aI %s",
                "-1",
                "--",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=cwd,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None

    output = result.stdout.strip()
    if not output or result.returncode != 0:
        return None

    parts = output.split(" ", 2)
    if len(parts) < 3:
        return None

    commit_hash = parts[0]
    try:
        deleted_date = datetime.fromisoformat(parts[1])
    except ValueError:
        return None
    commit_message = parts[2]

    adr_match = _ADR_PATTERN.search(commit_message)
    adr_reference = adr_match.group(0).upper() if adr_match else None

    return DeletionInfo(
        deleted_date=deleted_date,
        commit_hash=commit_hash,
        commit_message=commit_message,
        adr_reference=adr_reference,
    )


def _check_git_recent_modification(
    path: str,
    project_root: Path | None = None,
) -> ModificationInfo | None:
    """Check if a file was recently modified (not deleted) in git history."""
    cwd = str(project_root) if project_root else None
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--diff-filter=AMRC",
                "--format=%H %aI %s",
                "-1",
                "--",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=cwd,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None

    output = result.stdout.strip()
    if not output or result.returncode != 0:
        return None

    parts = output.split(" ", 2)
    if len(parts) < 3:
        return None

    commit_hash = parts[0]
    try:
        modified_date = datetime.fromisoformat(parts[1])
    except ValueError:
        return None
    commit_message = parts[2]

    is_user_change = not any(commit_message.startswith(prefix) for prefix in _AUTOLOOP_PREFIXES)

    return ModificationInfo(
        modified_date=modified_date,
        commit_hash=commit_hash,
        commit_message=commit_message,
        is_user_change=is_user_change,
    )


# Safe fix types that never touch file structure
_SAFE_FIX_TYPES = frozenset(
    {
        "formatting",
        "lint",
        "marker",
        "report",
        "sync",
    }
)


def classify_fix(
    fix_type: str,
    target_path: str,
    project_root: Path | None = None,
) -> tuple[FixClassification, DeletionInfo | ModificationInfo | None]:
    """Classify an auto-loop fix before application (ADR-443)."""
    if fix_type in _SAFE_FIX_TYPES:
        return FixClassification.SAFE, None

    # Check for recent user modifications FIRST — protects all change types
    modification = _check_git_recent_modification(target_path, project_root)
    if modification is not None and modification.is_user_change:
        now = datetime.now(timezone.utc)
        mod_utc = modification.modified_date.astimezone(timezone.utc)
        age = now - mod_utc
        if age <= timedelta(days=_MODIFICATION_WINDOW_DAYS):
            return FixClassification.MODIFIED, modification

    # Check if target was recently deleted (ADR-443 original gate)
    deletion = _check_git_deletion_history(target_path, project_root)
    if deletion is None:
        return FixClassification.STRUCTURAL, None

    now = datetime.now(timezone.utc)
    deleted_utc = deletion.deleted_date.astimezone(timezone.utc)
    age = now - deleted_utc

    if age <= timedelta(days=_DELETION_WINDOW_DAYS) and deletion.adr_reference:
        return FixClassification.REVERTING, deletion

    return FixClassification.STRUCTURAL, deletion


def make_migration_incomplete_issue(
    deletion: DeletionInfo,
    target_path: str,
    consumer: str = "",
    category: str = "fix-classification",
) -> dict:
    """Create a migration-incomplete issue for a blocked Reverting fix (ADR-443)."""
    adr = deletion.adr_reference or "unknown"
    detail = (
        f"File '{target_path}' was intentionally deleted by {adr}. " f"Consumer needs migration, not file restoration."
    )
    if consumer:
        detail += f" Affected consumer: {consumer}"
    return make_issue(
        category=category,
        detail=detail,
        path=target_path,
        kind="manual",
        root_cause_type="manual_debt",
        fixability="manual",
        adr=adr,
        deleted_commit=deletion.commit_hash,
    )


# ---------------------------------------------------------------------------
# INTENTIONAL_SKIP guard — ADR-269
# ---------------------------------------------------------------------------

_SKIP_MARKER = "INTENTIONAL_SKIP"


def check_intentional_skip(
    filepath: str | Path,
    line_number: int | None = None,
    window: int = 3,
) -> str | None:
    """Check if a source file has an INTENTIONAL_SKIP marker near a line."""
    path = Path(filepath)
    if not path.is_file():
        return None
    try:
        lines = path.read_text().splitlines()
    except (OSError, UnicodeDecodeError):
        return None

    if line_number is None:
        # Scan entire file
        for line in lines:
            if _SKIP_MARKER in line:
                return _extract_reason(line)
        return None

    # Scan window around the target line (1-indexed)
    start = max(0, line_number - 1 - window)
    end = min(len(lines), line_number + window)
    for line in lines[start:end]:
        if _SKIP_MARKER in line:
            return _extract_reason(line)
    return None


def _extract_reason(line: str) -> str:
    """Extract reason from '// INTENTIONAL_SKIP(adr-269): reason here'."""
    idx = line.find(_SKIP_MARKER)
    if idx < 0:
        return "intentionally skipped"
    rest = line[idx + len(_SKIP_MARKER) :].strip()
    # Strip parens like (adr-269) and colon
    if rest.startswith("("):
        close = rest.find(")")
        if close > 0:
            rest = rest[close + 1 :].strip()
    if rest.startswith(":"):
        rest = rest[1:].strip()
    return rest or "intentionally skipped"
