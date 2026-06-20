"""
adr_utils._index — ADR index CRUD and archive infrastructure.

Central-index I/O (load/write/upsert/delete), path helpers, archive constants.
Internal use by the adr_utils package; do not import directly from outside.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Internal number extractor (used by parse/archive/scan layers)
# ---------------------------------------------------------------------------


def _extract_number(adr_number: object) -> int | None:
    if adr_number is None:
        return None
    if isinstance(adr_number, int):
        return adr_number
    if isinstance(adr_number, str):
        m = re.match(r"ADR-?(\d+)", adr_number, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                return None
    return None


# ---------------------------------------------------------------------------
# Archive constants and result type
# ---------------------------------------------------------------------------

# ADRs whose body content is worth keeping but whose status is no longer "live
# work in flight". Frozen, not dead — a Superseded ADR can resurrect if its
# successor is itself superseded, a Deprecated decision can be re-adopted,
# and a Cancelled feature may return.
ARCHIVABLE_STATUSES = frozenset({"Implemented", "Deprecated", "Superseded", "Cancelled"})


@dataclass(frozen=True)
class AdrArchiveResult:
    """Result of moving archivable ADR entries into the archive directory."""

    archived_numbers: list[int]
    skipped_numbers: list[int]
    index_path: Path
    archive_paths: list[Path]
    dry_run: bool = False


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def get_archive_dir(decisions_dir: Path) -> Path:
    """Return the directory that stores archived ADR plain markdown files."""
    return decisions_dir / "archive"


def get_archived_adr_path(decisions_dir: Path, number: int) -> Path | None:
    """Return the plain archived ADR markdown file for ``number``, if present."""
    archive_dir = get_archive_dir(decisions_dir)
    if not archive_dir.is_dir():
        return None
    matches = sorted(archive_dir.glob(f"ADR-{int(number):03d}-*.md"))
    if not matches:
        matches = sorted(archive_dir.glob(f"ADR-{int(number):03d}.md"))
    return matches[0] if matches else None


def get_adrs_index_path(decisions_dir: Path) -> Path:
    """Return the central JSON index for live + archived ADRs."""
    return Path(decisions_dir) / "adrs-index.json"


def get_archive_index_path(decisions_dir: Path) -> Path:  # pragma: no cover - compat shim
    """Deprecated: use ``get_adrs_index_path`` (ADR-642)."""
    return get_adrs_index_path(decisions_dir)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _empty_impact() -> dict:
    return {
        "paths_renamed": [],
        "apis_changed": [],
        "patterns_deprecated": [],
        "files_affected": [],
    }


# ---------------------------------------------------------------------------
# Index CRUD
# ---------------------------------------------------------------------------


def load_adrs_index(decisions_dir: Path) -> list[dict]:
    """Read the central ``adrs-index.json`` (returns an empty list when missing)."""
    index_path = get_adrs_index_path(decisions_dir)
    if not index_path.exists():
        return []
    try:
        text = index_path.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [record for record in data if isinstance(record, dict)]


def write_adrs_index(decisions_dir: Path, records: list[dict]) -> Path:
    """Persist ``records`` to the central JSON index, sorted by ADR number."""
    index_path = get_adrs_index_path(decisions_dir)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    payload = sorted(
        (dict(r) for r in records if isinstance(r, dict) and r.get("adr_number")),
        key=lambda r: str(r.get("adr_number", "")),
    )
    index_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return index_path


def upsert_adr_entry(decisions_dir: Path, record: dict) -> Path:
    """Insert or update one ADR entry in the central index."""
    if not record.get("adr_number"):
        raise ValueError("record must have adr_number")
    records = load_adrs_index(decisions_dir)
    target = str(record["adr_number"])
    by_number = {r["adr_number"]: r for r in records if r.get("adr_number")}
    by_number[target] = dict(record)
    return write_adrs_index(decisions_dir, list(by_number.values()))


def delete_adr_entry(decisions_dir: Path, adr_number: str | int) -> Path:
    """Remove a single ADR entry from the central index."""
    if isinstance(adr_number, int):
        adr_number = f"ADR-{adr_number:03d}"
    records = load_adrs_index(decisions_dir)
    keep = [r for r in records if r.get("adr_number") != adr_number]
    return write_adrs_index(decisions_dir, keep)


# ---------------------------------------------------------------------------
# Legacy/back-compat helpers
# ---------------------------------------------------------------------------


def get_archived_adr_ledger(decisions_dir: Path) -> list[dict]:
    """Return archived ADR entries projected into the legacy ledger shape.

    The central JSON index supersedes the old archived-only sidecar; this shim
    keeps callers that still expect ``number``/``archive_path``/``archive_member``
    fields working without rewriting them all at once.
    """
    out: list[dict] = []
    for record in load_adrs_index(decisions_dir):
        if record.get("state") != "archived":
            continue
        out.append(_legacy_ledger_record(record))
    return out


def _legacy_ledger_record(entry: dict) -> dict:
    record = dict(entry)
    raw_number = str(record.pop("adr_number", "")).removeprefix("ADR-").lstrip("0")
    if raw_number:
        try:
            record["number"] = int(raw_number)
        except ValueError:
            pass
    if "zip_path" in record:
        record["archive_path"] = record["zip_path"]
    if "zip_member" in record:
        record["archive_member"] = record["zip_member"]
    return record
