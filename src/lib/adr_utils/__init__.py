"""
src/lib/adr_utils — Canonical ADR utility package.

Shared helpers for scanning, parsing, and normalising Architecture Decision
Records (ADRs).  All other scripts that work with ADR data should import from
here instead of reimplementing these routines.

Storage layout (ADR-811, supersedes ADR-642 zip model):
    <adr_dir>/ADR-*.md              -- live ADR bodies (plain markdown).
    <adr_dir>/adrs-index.json       -- generated metadata index.
    <adr_dir>/archive/ADR-*.md      -- archived ADR bodies (plain markdown).
    <adr_dir>/TEMPLATE.md           -- template.

Public API
----------
find_next_adr_number(decisions_dir)  — highest existing live/archived ADR number + 1
parse_adr_number(name)               — extract ADR number from a filename/stem
parse_adr_slug(name)                 — extract slug from an ADR filename
normalize_adr_status(raw)            — normalise free-form status strings
scan_adrs(decisions_dir)             — return all ADR records (live + archived)
load_adrs_index(decisions_dir)       — read the central JSON index
write_adrs_index(decisions_dir, recs) — persist the central JSON index
upsert_adr_entry(decisions_dir, rec) — insert or update one entry
delete_adr_entry(decisions_dir, num) — remove one entry from the index
archive_eligible_adrs(decisions_dir) — flip live→archived and move bodies to archive/
extract_archived_adr(decisions_dir, number) — extract one historical ADR to temp
find_duplicate_adrs(decisions_dir)   — find ADR numbers with multiple entries
find_gaps(decisions_dir)             — find gaps in the ADR numbering sequence
detect_stale_status(adrs, days)      — find ADRs with stale or non-canonical status
"""

from __future__ import annotations

from pathlib import Path

from src.config.paths import get_vault_dir  # noqa: F401  (kept for compat)

# ---------------------------------------------------------------------------
# Default ADR directory
# ---------------------------------------------------------------------------


def get_adr_dir() -> Path:
    """Return the canonical ADR directory in the project repo.

    ADRs live at ``project-brain/decisions/adrs/`` per ADR-811 — they are
    technical project docs, not personal vault knowledge.
    """
    from src.config.paths import get_adr_dir as _get_adr_dir

    return _get_adr_dir()


# ---------------------------------------------------------------------------
# Re-exports from sub-modules (stable public interface)
# ---------------------------------------------------------------------------

from src.lib.adr_utils._index import (  # noqa: E402
    ARCHIVABLE_STATUSES,
    AdrArchiveResult,
    delete_adr_entry,
    get_archive_dir,
    get_archive_index_path,
    get_archived_adr_ledger,
    get_archived_adr_path,
    get_adrs_index_path,
    load_adrs_index,
    upsert_adr_entry,
    write_adrs_index,
)

from src.lib.adr_utils._parse import (  # noqa: E402
    CANONICAL_STATUSES,
    find_next_adr_number,
    normalize_adr_status,
    parse_adr_number,
    parse_adr_slug,
)

from src.lib.adr_utils._archive import (  # noqa: E402
    archive_eligible_adrs,
    extract_archived_adr,
    rebuild_archive_index,
)

from src.lib.adr_utils._scan import (  # noqa: E402
    detect_stale_status,
    find_duplicate_adrs,
    find_gaps,
    rename_adr,
    scan_adrs,
)

__all__ = [
    # Path helpers
    "get_adr_dir",
    "get_adrs_index_path",
    "get_archive_dir",
    "get_archive_index_path",
    "get_archived_adr_path",
    # Numbering / parsing
    "find_next_adr_number",
    "parse_adr_number",
    "parse_adr_slug",
    # Status
    "normalize_adr_status",
    "CANONICAL_STATUSES",
    # Archive constants and types
    "ARCHIVABLE_STATUSES",
    "AdrArchiveResult",
    # Index CRUD
    "load_adrs_index",
    "write_adrs_index",
    "upsert_adr_entry",
    "delete_adr_entry",
    # Legacy shims
    "get_archived_adr_ledger",
    # Archive operations
    "archive_eligible_adrs",
    "rebuild_archive_index",
    "extract_archived_adr",
    # Scanning
    "scan_adrs",
    "find_duplicate_adrs",
    "find_gaps",
    "detect_stale_status",
    "rename_adr",
]
