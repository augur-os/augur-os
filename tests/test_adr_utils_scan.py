"""Unit tests for src.lib.adr_utils._scan (scan, gaps, duplicates, rename)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.lib.adr_utils._index import write_adrs_index
from src.lib.adr_utils._scan import (
    _replace_adr_ref,
    detect_stale_status,
    find_duplicate_adrs,
    find_gaps,
    rename_adr,
    scan_adrs,
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


def test_scan_adrs_from_index(tmp_path):
    write_adrs_index(
        tmp_path,
        [
            {
                "adr_number": "ADR-001",
                "title": "Live One",
                "status": "Accepted",
                "state": "live",
                "date": "2026-01-01",
                "tags": ["a"],
                "decision_summary": "Summary one.",
            },
            {
                "adr_number": "ADR-002",
                "title": "Archived Two",
                "status": "Implemented",
                "state": "archived",
                "archive_member": "ADR-002-archived-two.md",
            },
        ],
    )
    records = scan_adrs(tmp_path)
    assert [r["number"] for r in records] == [1, 2]

    live = records[0]
    assert live["title"] == "Live One"
    assert live["status"] == "Accepted"
    assert live["archived"] is False
    assert live["description"] == "Summary one."

    archived = records[1]
    assert archived["archived"] is True
    assert archived["archive_member"] == "ADR-002-archived-two.md"
    assert archived["archive_path"] == "archive/ADR-002-archived-two.md"


def test_scan_adrs_exclude_archived(tmp_path):
    write_adrs_index(
        tmp_path,
        [
            {"adr_number": "ADR-001", "title": "L", "status": "Accepted", "state": "live"},
            {"adr_number": "ADR-002", "title": "A", "status": "Implemented", "state": "archived"},
        ],
    )
    numbers = [r["number"] for r in scan_adrs(tmp_path, include_archived=False)]
    assert numbers == [1]


def test_scan_adrs_md_fallback(tmp_path):
    # No JSON index; stray .md file should be picked up.
    _write_adr(tmp_path, 9, "Accepted", "Stray File", "Body for stray.")
    records = scan_adrs(tmp_path)
    assert len(records) == 1
    rec = records[0]
    assert rec["number"] == 9
    assert rec["title"] == "Stray File"
    assert rec["path"].endswith("ADR-009-stray-file.md")
    assert rec["archived"] is False


def test_scan_adrs_index_wins_over_md(tmp_path):
    write_adrs_index(
        tmp_path,
        [{"adr_number": "ADR-009", "title": "Indexed", "status": "Accepted", "state": "live"}],
    )
    _write_adr(tmp_path, 9, "Accepted", "On Disk")  # duplicate number — should be skipped
    records = scan_adrs(tmp_path)
    assert len(records) == 1
    assert records[0]["title"] == "Indexed"


def test_find_duplicate_adrs(tmp_path):
    _write_adr(tmp_path, 5, "Accepted", "First")
    # A second file with the same number but different slug.
    dup = tmp_path / "ADR-005-second.md"
    write_frontmatter(dup, {"status": "Accepted"}, "# ADR-005: Second\n")
    _write_adr(tmp_path, 6, "Accepted", "Unique")

    dups = find_duplicate_adrs(tmp_path)
    assert set(dups.keys()) == {5}
    assert len(dups[5]) == 2


def test_find_duplicate_adrs_none(tmp_path):
    _write_adr(tmp_path, 1, "Accepted", "Only")
    assert find_duplicate_adrs(tmp_path) == {}


def test_find_gaps(tmp_path):
    write_adrs_index(
        tmp_path,
        [
            {"adr_number": "ADR-001"},
            {"adr_number": "ADR-002"},
            {"adr_number": "ADR-005"},
        ],
    )
    assert find_gaps(tmp_path) == [3, 4]


def test_find_gaps_empty(tmp_path):
    assert find_gaps(tmp_path) == []


def test_detect_stale_status_non_canonical():
    adrs = [
        {"number": 1, "raw_status": "Wishlist", "status": "Other", "filename": "ADR-001.md"},
        {"number": 2, "raw_status": "Accepted", "status": "Accepted", "filename": "ADR-002.md"},
        {"number": 3, "raw_status": "Implemented", "status": "Implemented", "filename": "ADR-003.md"},
    ]
    issues = detect_stale_status(adrs)
    assert len(issues) == 1
    issue = issues[0]
    assert issue["number"] == 1
    assert issue["issue"] == "non_canonical"
    assert issue["current"] == "Wishlist"
    assert issue["suggested"] == "Other"


def test_replace_adr_ref():
    text = "See ADR-001 and ADR-1 for details."
    out = _replace_adr_ref(text, 1, 42)
    # Padded form replaced as a substring; bare ADR-1 replaced via word-boundary regex.
    assert out == "See ADR-042 and ADR-042 for details."
    assert "ADR-001" not in out


def test_replace_adr_ref_word_boundary_protects_other_numbers():
    # The bare-number regex uses \b so ADR-10 is not matched when renaming ADR-1.
    text = "ADR-1 references ADR-10."
    out = _replace_adr_ref(text, 1, 42)
    assert "ADR-042 references ADR-10." == out


def test_rename_adr(tmp_path):
    adr = _write_adr(tmp_path, 10, "Accepted", "Renamable", "Body references ADR-010 here.")
    # A second ADR referencing the renamed one.
    other = _write_adr(tmp_path, 11, "Accepted", "Other", "Relates to ADR-010 strongly.")

    new_path = rename_adr(adr, 99, tmp_path)
    assert new_path.exists()
    assert not adr.exists()
    assert "ADR-099" in new_path.name

    # Body of the renamed file updated.
    assert "ADR-099" in new_path.read_text(encoding="utf-8")
    assert "ADR-010" not in new_path.read_text(encoding="utf-8")

    # Cross-references in sibling ADRs updated too.
    other_text = other.read_text(encoding="utf-8")
    assert "ADR-099" in other_text
    assert "ADR-010" not in other_text


def test_rename_adr_missing_file(tmp_path):
    import pytest

    with pytest.raises(FileNotFoundError):
        rename_adr(tmp_path / "ADR-001-nope.md", 2, tmp_path)
