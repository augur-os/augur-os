"""Unit tests for src.lib.adr_utils._archive (archive, rebuild, extract)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from src.lib.adr_utils._archive import (
    _normalize_adr_number_filter,
    archive_eligible_adrs,
    extract_archived_adr,
    rebuild_archive_index,
)
from src.lib.adr_utils._index import (
    get_archive_dir,
    load_adrs_index,
    write_adrs_index,
)
from src.lib.frontmatter_utils import write_frontmatter


def _write_adr(path: Path, number: int, status: str, title: str, body: str = "Decision body.") -> Path:
    adr_path = path / f"ADR-{number:03d}-{title.lower().replace(' ', '-')}.md"
    write_frontmatter(
        adr_path,
        {"status": status, "date": "2026-04-19", "hub": "workspace", "tags": ["t"]},
        f"# ADR-{number:03d}: {title}\n\n{body}\n",
    )
    return adr_path


def test_normalize_adr_number_filter():
    assert _normalize_adr_number_filter(None) is None
    assert _normalize_adr_number_filter([1, "ADR-007", "12"]) == {1, 7, 12}
    assert _normalize_adr_number_filter(["adr-005"]) == {5}
    # Empty/blank entries are skipped.
    assert _normalize_adr_number_filter(["", "ADR-"]) == set()


def test_normalize_adr_number_filter_rejects_non_positive():
    with pytest.raises(ValueError):
        _normalize_adr_number_filter([0])
    with pytest.raises(ValueError):
        _normalize_adr_number_filter([-3])


def test_archive_eligible_adrs_moves_files(tmp_path):
    _write_adr(tmp_path, 7, "Implemented", "First Archived")
    _write_adr(tmp_path, 19, "Superseded", "Second Archived")
    _write_adr(tmp_path, 23, "Accepted", "Still Active")  # not archivable

    result = archive_eligible_adrs(tmp_path)
    assert result.dry_run is False
    assert result.archived_numbers == [7, 19]
    assert result.skipped_numbers == [23]

    archive_dir = get_archive_dir(tmp_path)
    assert (archive_dir / "ADR-007-first-archived.md").exists()
    assert (archive_dir / "ADR-019-second-archived.md").exists()
    # Archived live files removed from the top-level dir.
    assert not (tmp_path / "ADR-007-first-archived.md").exists()
    # Active ADR stays put.
    assert (tmp_path / "ADR-023-still-active.md").exists()

    # Index reflects archived state.
    by_number = {r["adr_number"]: r for r in load_adrs_index(tmp_path)}
    assert by_number["ADR-007"]["state"] == "archived"
    assert by_number["ADR-007"]["archive_member"] == "ADR-007-first-archived.md"


def test_archive_eligible_adrs_dry_run(tmp_path):
    _write_adr(tmp_path, 7, "Implemented", "Dry Run Adr")
    result = archive_eligible_adrs(tmp_path, dry_run=True)
    assert result.dry_run is True
    assert result.archived_numbers == [7]
    # No file moved, no archive dir created.
    assert (tmp_path / "ADR-007-dry-run-adr.md").exists()
    assert not get_archive_dir(tmp_path).exists()


def test_archive_eligible_adrs_number_filter(tmp_path):
    _write_adr(tmp_path, 7, "Implemented", "Targeted")
    _write_adr(tmp_path, 8, "Implemented", "Untouched")
    result = archive_eligible_adrs(tmp_path, adr_numbers=[7])
    assert result.archived_numbers == [7]
    assert (get_archive_dir(tmp_path) / "ADR-007-targeted.md").exists()
    # Number 8 not in filter -> left alone on disk.
    assert (tmp_path / "ADR-008-untouched.md").exists()


def test_archive_eligible_adrs_index_only_entry(tmp_path):
    # A live entry that exists only in the JSON index (no .md on disk).
    write_adrs_index(
        tmp_path,
        [
            {
                "adr_number": "ADR-050",
                "title": "Index Only",
                "status": "Implemented",
                "state": "live",
                "decision_summary": "Body in JSON.",
            }
        ],
    )
    result = archive_eligible_adrs(tmp_path)
    assert result.archived_numbers == [50]
    member = get_archive_dir(tmp_path) / "ADR-050-index-only.md"
    assert member.exists()
    assert "Body in JSON." in member.read_text(encoding="utf-8")


def test_rebuild_archive_index(tmp_path):
    # Seed a live entry in the index and an archived plain file on disk.
    write_adrs_index(
        tmp_path,
        [{"adr_number": "ADR-001", "title": "Live", "status": "Accepted", "state": "live"}],
    )
    archive_dir = get_archive_dir(tmp_path)
    archive_dir.mkdir()
    write_frontmatter(
        archive_dir / "ADR-060-archived-file.md",
        {"status": "Implemented", "date": "2026-02-02"},
        "# ADR-060: Archived File\n\nArchived body.\n",
    )

    rebuild_archive_index(tmp_path)
    by_number = {r["adr_number"]: r for r in load_adrs_index(tmp_path)}
    # Live entry preserved.
    assert by_number["ADR-001"]["state"] == "live"
    # Archived entry regenerated from disk.
    assert by_number["ADR-060"]["state"] == "archived"
    assert by_number["ADR-060"]["archive_member"] == "ADR-060-archived-file.md"


def test_rebuild_archive_index_no_archive_dir(tmp_path):
    write_adrs_index(
        tmp_path,
        [{"adr_number": "ADR-001", "title": "Live", "status": "Accepted", "state": "live"}],
    )
    rebuild_archive_index(tmp_path)
    records = load_adrs_index(tmp_path)
    assert [r["adr_number"] for r in records] == ["ADR-001"]


def test_extract_archived_adr(tmp_path):
    archive_dir = get_archive_dir(tmp_path)
    archive_dir.mkdir()
    (archive_dir / "ADR-070-extractable.md").write_text("primary body", encoding="utf-8")
    (archive_dir / "ADR-070-spec.md").write_text("spec body", encoding="utf-8")
    write_adrs_index(
        tmp_path,
        [
            {
                "adr_number": "ADR-070",
                "state": "archived",
                "archive_member": "ADR-070-extractable.md",
                "spec_member": "ADR-070-spec.md",
            }
        ],
    )
    dest = tmp_path / "out"
    primary = extract_archived_adr(tmp_path, 70, destination_dir=dest)
    assert primary == dest / "ADR-070-extractable.md"
    assert primary.read_text(encoding="utf-8") == "primary body"
    assert (dest / "ADR-070-spec.md").read_text(encoding="utf-8") == "spec body"


def test_extract_archived_adr_missing_record(tmp_path):
    write_adrs_index(tmp_path, [{"adr_number": "ADR-001", "state": "live"}])
    with pytest.raises(FileNotFoundError):
        extract_archived_adr(tmp_path, 999, destination_dir=tmp_path / "out")


def test_extract_archived_adr_rejects_unsafe_member(tmp_path):
    write_adrs_index(
        tmp_path,
        [
            {
                "adr_number": "ADR-080",
                "state": "archived",
                "archive_member": "../escape.md",
            }
        ],
    )
    with pytest.raises(ValueError):
        extract_archived_adr(tmp_path, 80, destination_dir=tmp_path / "out")


def test_extract_archived_adr_no_members(tmp_path):
    write_adrs_index(
        tmp_path,
        [{"adr_number": "ADR-081", "state": "archived"}],
    )
    with pytest.raises(ValueError):
        extract_archived_adr(tmp_path, 81, destination_dir=tmp_path / "out")
