"""
adr_utils._archive — ADR archive operations.

archive_eligible_adrs, rebuild_archive_index, extract_archived_adr.
Internal use by the adr_utils package; do not import directly from outside.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.lib.adr_utils._index import (
    ARCHIVABLE_STATUSES,
    AdrArchiveResult,
    _extract_number,
    get_adrs_index_path,
    get_archive_dir,
    load_adrs_index,
    write_adrs_index,
)
from src.lib.adr_utils._parse import (
    _materialize_live_md,
    _merge_live_file_record_with_index,
    _plain_member_for_record,
    _record_from_adr_file,
    parse_adr_number,
)


def archive_eligible_adrs(
    decisions_dir: Path,
    *,
    range_size: int = 100,  # kept for signature compat, unused in plain model
    dry_run: bool = False,
    adr_numbers: Iterable[int | str] | None = None,
) -> AdrArchiveResult:
    """Flip live ADR entries with archivable status to ``state=archived``.

    ADR-811 plain-file model: for each archivable live ``ADR-*.md`` in
    ``decisions_dir`` (status in ``ARCHIVABLE_STATUSES``):
      1. Move the file into ``archive/`` via ``Path.replace``.
      2. Update the central ``adrs-index.json`` entry: ``state="archived"``,
         ``archive_member=<filename>``; drop zip_path/zip_member keys.
      3. For index-only live entries (no on-disk .md), record them as archived
         without writing a body (body is already in the JSON index).

    Companion files (spec_file/plan_file) are not moved at archive time under
    the plain model — they remain in their docs/ locations and are referenced
    by the index.
    """
    decisions_dir = Path(decisions_dir)
    target_numbers = _normalize_adr_number_filter(adr_numbers)

    archived_numbers: list[int] = []
    skipped_numbers: list[int] = []
    archive_paths: set[Path] = set()

    records = load_adrs_index(decisions_dir)
    by_number: dict[str, dict] = {r["adr_number"]: r for r in records if r.get("adr_number")}

    archive_dir = get_archive_dir(decisions_dir)

    # ----- Path 1: on-disk live ADR-*.md files -----
    for adr_path in sorted(decisions_dir.glob("ADR-*.md")):
        record = _record_from_adr_file(adr_path)
        if not record:
            continue
        number = _extract_number(record["adr_number"]) or 0
        if target_numbers is not None and number not in target_numbers:
            continue

        existing_record = by_number.get(record["adr_number"])

        # Already archived — ensure the file is moved into archive/ if stray.
        if existing_record and existing_record.get("state") == "archived":
            archive_member = str(
                existing_record.get("archive_member") or existing_record.get("zip_member") or adr_path.name
            )
            archived_numbers.append(number)
            dest_file = archive_dir / archive_member
            archive_paths.add(dest_file)
            if dry_run:
                continue
            archive_dir.mkdir(parents=True, exist_ok=True)
            if not dest_file.exists():
                adr_path.replace(dest_file)
            else:
                adr_path.unlink()
            # Ensure index has archive_member set.
            if not existing_record.get("archive_member"):
                repaired = dict(existing_record)
                repaired["archive_member"] = archive_member
                repaired.pop("zip_path", None)
                repaired.pop("zip_member", None)
                by_number[record["adr_number"]] = repaired
            else:
                # Just remove the stray live file; index already correct.
                pass
            continue

        archive_source = (
            _merge_live_file_record_with_index(record, existing_record)
            if existing_record and existing_record.get("state") == "live"
            else record
        )
        if archive_source["status"] not in ARCHIVABLE_STATUSES:
            skipped_numbers.append(number)
            continue

        archive_member = adr_path.name
        archived_numbers.append(number)
        dest_file = archive_dir / archive_member
        archive_paths.add(dest_file)

        if dry_run:
            continue

        archive_dir.mkdir(parents=True, exist_ok=True)
        adr_path.replace(dest_file)

        archived_record = dict(archive_source)
        archived_record["state"] = "archived"
        archived_record["archive_member"] = archive_member
        archived_record["spec_member"] = None
        archived_record["plan_member"] = None
        archived_record.pop("zip_path", None)
        archived_record.pop("zip_member", None)
        by_number[record["adr_number"]] = archived_record

    # ----- Path 2: live entries already in the central JSON index (no .md file) -----
    for adr_key, record in list(by_number.items()):
        if record.get("state") != "live":
            continue
        status = record.get("status") or ""
        number = _extract_number(record.get("adr_number")) or 0
        if target_numbers is not None and number not in target_numbers:
            continue
        if status not in ARCHIVABLE_STATUSES:
            skipped_numbers.append(number)
            continue

        # Derive archive_member from title slug (same convention as old zip model).
        archive_member = _plain_member_for_record(record)
        archived_numbers.append(number)
        dest_file = archive_dir / archive_member
        archive_paths.add(dest_file)

        if dry_run:
            continue

        # Write body from JSON index so the plain file exists in archive/.
        archive_dir.mkdir(parents=True, exist_ok=True)
        dest_file.write_bytes(_materialize_live_md(record))

        new_record = dict(record)
        new_record["state"] = "archived"
        new_record["archive_member"] = archive_member
        new_record["spec_member"] = None
        new_record["plan_member"] = None
        new_record.pop("zip_path", None)
        new_record.pop("zip_member", None)
        by_number[adr_key] = new_record

    if dry_run:
        return AdrArchiveResult(
            archived_numbers=sorted(set(archived_numbers)),
            skipped_numbers=sorted(set(skipped_numbers)),
            index_path=get_adrs_index_path(decisions_dir),
            archive_paths=sorted(archive_paths),
            dry_run=True,
        )

    index_path = write_adrs_index(decisions_dir, list(by_number.values()))

    return AdrArchiveResult(
        archived_numbers=sorted(set(archived_numbers)),
        skipped_numbers=sorted(set(skipped_numbers)),
        index_path=index_path,
        archive_paths=sorted(archive_paths),
        dry_run=False,
    )


def _normalize_adr_number_filter(values: Iterable[int | str] | None) -> set[int] | None:
    """Normalize an optional ADR number filter used by archive operations."""
    if values is None:
        return None
    numbers: set[int] = set()
    for value in values:
        if isinstance(value, int):
            number = value
        else:
            cleaned = str(value).strip().upper().removeprefix("ADR-").removeprefix("ADR")
            if not cleaned:
                continue
            number = int(cleaned)
        if number <= 0:
            raise ValueError(f"Invalid ADR number: {value}")
        numbers.add(number)
    return numbers


def rebuild_archive_index(decisions_dir: Path) -> Path:
    """Regenerate archived entries in ``adrs-index.json`` by walking ``archive/ADR-*.md``.

    ADR-811 plain-file model: live entries are preserved; archived entries are
    regenerated by parsing each plain markdown file in the archive directory.
    """
    decisions_dir = Path(decisions_dir)
    archive_dir = get_archive_dir(decisions_dir)

    existing = load_adrs_index(decisions_dir)
    live_records = [r for r in existing if r.get("state") == "live"]

    if not archive_dir.is_dir():
        return write_adrs_index(decisions_dir, live_records)

    records_by_number: dict[int, dict] = {}
    for adr_file in sorted(archive_dir.glob("ADR-*.md")):
        number = parse_adr_number(adr_file.name)
        if number is None:
            continue
        record = _record_from_adr_file(adr_file)
        if record is None:
            continue
        record["state"] = "archived"
        record["archive_member"] = adr_file.name
        record.pop("zip_path", None)
        record.pop("zip_member", None)
        records_by_number[number] = record

    archived_records = list(records_by_number.values())
    return write_adrs_index(decisions_dir, live_records + archived_records)


def extract_archived_adr(
    decisions_dir: Path,
    number: int,
    *,
    destination_dir: Path | None = None,
) -> Path:
    """Copy one archived ADR (and companions) to a destination directory.

    ADR-811 plain-file model: members are plain files inside ``archive/``.
    Member names are read from the index keys ``archive_member``,
    ``spec_member``, and ``plan_member`` (treated as filenames inside the
    archive directory).  Unsafe paths (absolute or containing ``..``) are
    rejected.  Raises ``FileNotFoundError`` if the record is missing or not
    archived, or if the primary file is absent.  Raises ``ValueError`` when no
    member keys are set.
    """
    target = f"ADR-{int(number):03d}"
    record = next(
        (r for r in load_adrs_index(decisions_dir) if r.get("adr_number") == target),
        None,
    )
    if not record or record.get("state") != "archived":
        raise FileNotFoundError(f"Archived {target} not found in central index")

    # Resolve member names — prefer plain archive_member; fall back to legacy
    # zip_member for records that haven't been migrated yet.
    member = str(record.get("archive_member") or record.get("zip_member") or "").strip()
    spec_member = str(record.get("spec_member") or "").strip()
    plan_member = str(record.get("plan_member") or "").strip()

    # Validate any member paths that ARE set.
    for candidate in (member, spec_member, plan_member):
        if candidate and (Path(candidate).is_absolute() or ".." in Path(candidate).parts):
            raise ValueError(f"Unsafe archived ADR member: {candidate}")
    if not (member or spec_member or plan_member):
        raise ValueError(f"No extractable members on {target}")

    archive_dir = get_archive_dir(decisions_dir)

    if destination_dir is None:
        from src.config.paths import get_runtime_dir

        destination_dir = get_runtime_dir() / "adr-extracts" / target
    destination_dir.mkdir(parents=True, exist_ok=True)

    primary_path: Path | None = None

    # Primary member
    if member:
        src_file = archive_dir / member
        if not src_file.exists():
            raise FileNotFoundError(f"Archived file not found: {src_file}")
        dest_file = destination_dir / Path(member).name
        dest_file.write_bytes(src_file.read_bytes())
        primary_path = dest_file

    # Companion members (spec + plan)
    for companion_name in (spec_member, plan_member):
        if not companion_name:
            continue
        src_file = archive_dir / companion_name
        if not src_file.exists():
            continue
        companion_dest = destination_dir / Path(companion_name).name
        companion_dest.write_bytes(src_file.read_bytes())
        if primary_path is None:
            primary_path = companion_dest

    if primary_path is None:
        raise FileNotFoundError(f"No extractable content for {target} in {archive_dir}")
    return primary_path
