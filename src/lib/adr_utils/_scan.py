"""
adr_utils._scan — ADR scanning, cleanup, and renaming helpers.

scan_adrs, find_duplicate_adrs, find_gaps, detect_stale_status, rename_adr.
Internal use by the adr_utils package; do not import directly from outside.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from src.lib.adr_utils._index import (
    _extract_number,
    load_adrs_index,
)
from src.lib.adr_utils._parse import (
    CANONICAL_STATUSES,
    _record_from_adr_file,
    normalize_adr_status,
    parse_adr_number,
)


def scan_adrs(decisions_dir: Path, *, include_archived: bool = True) -> list[dict]:
    """Return ADR metadata records from the central JSON index.

    Each record has:
      - number, title, status, raw_status, date, hub, tags, related, deciders
      - filename (synthetic for live entries; archive_member for archived)
      - path ("" for live entries — they live only in the JSON; the archive
              path or "" for archived)
      - description (decision_summary projection)
      - archived (bool)
      - archive_path / archive_member (when archived)

    Falls back to scanning legacy ADR-*.md files if any still exist on disk
    (helps tests and migration tooling).
    """
    decisions_dir = Path(decisions_dir)
    adrs: list[dict] = []
    seen_numbers: set[int] = set()

    for record in load_adrs_index(decisions_dir):
        number = _extract_number(record.get("adr_number"))
        if number is None:
            continue
        state = record.get("state", "live")
        if state == "archived" and not include_archived:
            continue
        seen_numbers.add(number)

        archived = state == "archived"
        # Prefer plain archive_member; fall back to legacy zip_member for
        # records that pre-date the ADR-811 migration.
        member = record.get("archive_member") or record.get("zip_member") or f"ADR-{number:03d}.md"
        filename = member
        # archive_path: prefer "archive/<member>"; fall back to legacy zip_path.
        if archived:
            if record.get("archive_member"):
                archive_path = "archive/" + record["archive_member"]
            elif record.get("zip_path"):
                archive_path = record["zip_path"]
            else:
                archive_path = ""
        else:
            archive_path = ""
        adrs.append(
            {
                "number": number,
                "title": record.get("title") or "",
                "raw_status": record.get("status") or "",
                "status": normalize_adr_status(record.get("status") or ""),
                "date": str(record.get("date", "")),
                "filename": filename,
                "path": "",
                "archived": archived,
                "archive_path": archive_path,
                "archive_member": member if archived else "",
                "hub": record.get("hub"),
                "tags": list(record.get("tags") or []),
                "related": list(record.get("related") or []),
                "deciders": list(record.get("deciders") or []),
                "superseded_by": record.get("superseded_by"),
                "spec_file": record.get("spec_file"),
                "plan_file": record.get("plan_file"),
                "description": record.get("decision_summary") or record.get("title") or "",
            }
        )

    # Fallback: scan stray .md files (legacy / pre-migration environments).
    if decisions_dir.is_dir():
        for adr_path in sorted(decisions_dir.glob("ADR-*.md")):
            number = parse_adr_number(adr_path.name)
            if number is None or number in seen_numbers:
                continue
            record = _record_from_adr_file(adr_path)
            if not record:
                continue
            adrs.append(
                {
                    "number": number,
                    "title": record["title"],
                    "raw_status": record["status"],
                    "status": normalize_adr_status(record["status"]),
                    "date": record["date"],
                    "filename": adr_path.name,
                    "path": str(adr_path),
                    "archived": False,
                    "hub": record.get("hub"),
                    "tags": list(record.get("tags") or []),
                    "related": list(record.get("related") or []),
                    "deciders": list(record.get("deciders") or []),
                    "superseded_by": record.get("superseded_by"),
                    "spec_file": record.get("spec_file"),
                    "plan_file": record.get("plan_file"),
                    "description": record.get("decision_summary") or record["title"],
                }
            )

    adrs.sort(key=lambda r: int(r.get("number", 0)))
    return adrs


def find_duplicate_adrs(decisions_dir: Path) -> dict[int, list[Path]]:
    """Find ADR numbers that have multiple on-disk files.

    Post-migration, this should always return ``{}`` because live ADRs no
    longer exist as files. Kept for environments that still have stray
    ``ADR-*.md`` files.
    """
    by_number: dict[int, list[Path]] = defaultdict(list)
    decisions_dir = Path(decisions_dir)
    if decisions_dir.is_dir():
        for f in sorted(decisions_dir.glob("ADR-*.md")):
            num = parse_adr_number(f.name)
            if num is not None:
                by_number[num].append(f)
    return {num: paths for num, paths in by_number.items() if len(paths) > 1}


def find_gaps(decisions_dir: Path) -> list[int]:
    """Find gaps in the ADR numbering sequence using the central index."""
    numbers: set[int] = set()
    for record in load_adrs_index(decisions_dir):
        number = _extract_number(record.get("adr_number"))
        if number is not None:
            numbers.add(number)
    decisions_dir = Path(decisions_dir)
    if decisions_dir.is_dir():
        for f in decisions_dir.glob("ADR-*.md"):
            num = parse_adr_number(f.name)
            if num is not None:
                numbers.add(num)
    if not numbers:
        return []
    return sorted(set(range(min(numbers), max(numbers) + 1)) - numbers)


def detect_stale_status(
    adrs: list[dict],
    days: int = 60,
    decisions_dir: Path | None = None,
) -> list[dict]:
    """Detect ADRs with stale or non-canonical status values.

    Mtime-based checks (``stale_proposed``) are skipped post-migration because
    live ADRs no longer have a file mtime. Non-canonical detection still works
    against ``raw_status``.
    """
    issues: list[dict] = []
    for adr in adrs:
        raw = adr.get("raw_status", "")
        canonical = adr.get("status", "")
        number = adr["number"]
        filename = adr.get("filename", f"ADR-{number:03d}.md")

        if raw and raw != canonical and raw not in CANONICAL_STATUSES:
            issues.append(
                {
                    "number": number,
                    "filename": filename,
                    "issue": "non_canonical",
                    "current": raw,
                    "suggested": canonical,
                }
            )
    return issues


def rename_adr(
    old_path: Path,
    new_number: int,
    decisions_dir: Path,
) -> Path:
    """Rename a stray ADR ``.md`` file (legacy/back-compat).

    Production ADR-renumbering should update the central index entry directly
    via ``upsert_adr_entry`` + ``delete_adr_entry``. This helper is only used
    by tests and migration tools that still write a one-off ``.md`` file.
    """
    if not old_path.exists():
        raise FileNotFoundError(f"ADR file not found: {old_path}")

    old_number = parse_adr_number(old_path.name)
    if old_number is None:
        raise ValueError(f"Cannot parse ADR number from: {old_path.name}")

    old_prefix = f"ADR-{old_number:03d}"
    new_prefix = f"ADR-{new_number:03d}"

    new_name = old_path.name.replace(old_prefix, new_prefix, 1)
    if new_name == old_path.name:
        new_name = old_path.name.replace(f"ADR-{old_number}", f"ADR-{new_number:03d}", 1)
    new_path = old_path.parent / new_name

    content = old_path.read_text(encoding="utf-8")
    content = _replace_adr_ref(content, old_number, new_number)
    old_path.write_text(content, encoding="utf-8")

    old_path.rename(new_path)

    decisions_dir = Path(decisions_dir)
    if decisions_dir.is_dir():
        for adr_file in sorted(decisions_dir.glob("ADR-*.md")):
            if adr_file == new_path:
                continue
            try:
                text = adr_file.read_text(encoding="utf-8")
            except OSError:
                continue
            updated = _replace_adr_ref(text, old_number, new_number)
            if updated != text:
                adr_file.write_text(updated, encoding="utf-8")

    return new_path


def _replace_adr_ref(text: str, old_number: int, new_number: int) -> str:
    """Replace all occurrences of an ADR number reference in text."""
    old_padded = f"ADR-{old_number:03d}"
    new_padded = f"ADR-{new_number:03d}"

    text = text.replace(old_padded, new_padded)

    old_unpadded = f"ADR-{old_number}"
    if old_unpadded != old_padded:
        text = re.sub(
            rf"\bADR-{old_number}\b",
            new_padded,
            text,
        )

    return text
