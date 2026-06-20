from __future__ import annotations

import json
from pathlib import Path

from src.lib.frontmatter_utils import write_frontmatter


def _write_adr(path: Path, number: int, status: str, title: str, body: str = "Decision body.") -> Path:
    adr_path = path / f"ADR-{number:03d}-{title.lower().replace(' ', '-')}.md"
    write_frontmatter(
        adr_path,
        {
            "status": status,
            "date": "2026-04-19",
            "hub": "workspace",
            "tags": ["archive"],
            "related": ["ADR-001"],
        },
        f"# ADR-{number:03d}: {title}\n\n## Context\n\n{body}\n",
    )
    return adr_path


def test_archive_eligible_adrs_writes_central_index(tmp_path):
    """ADR-811: archive_eligible_adrs writes the central adrs-index.json with archive_member."""
    from src.lib.adr_utils import archive_eligible_adrs, get_adrs_index_path

    _write_adr(tmp_path, 7, "Implemented", "First Archived", "First body.")
    _write_adr(tmp_path, 19, "Implemented", "Second Archived", "Second body.")
    _write_adr(tmp_path, 23, "Accepted", "Active", "Active body.")

    archive_eligible_adrs(tmp_path, range_size=100)

    index_path = get_adrs_index_path(tmp_path)
    assert index_path.exists(), "central JSON index must be written"

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    archived = [entry for entry in payload if entry.get("state") == "archived"]
    assert len(archived) == 2

    by_number = {entry["adr_number"]: entry for entry in archived}
    assert "ADR-007" in by_number
    assert "ADR-019" in by_number

    entry = by_number["ADR-007"]
    assert entry["title"] == "First Archived"
    assert entry["status"] == "Implemented"
    assert entry["date"] == "2026-04-19"
    assert entry["hub"] == "workspace"
    assert entry["tags"] == ["archive"]
    assert entry["archive_member"] == "ADR-007-first-archived.md"
    assert "zip_path" not in entry


def test_rebuild_archive_index_regenerates_from_existing_plain_files(tmp_path):
    """ADR-811: rebuild_archive_index walks archive/*.md and produces fresh archived rows."""
    from src.lib.adr_utils import (
        archive_eligible_adrs,
        get_adrs_index_path,
        rebuild_archive_index,
    )

    _write_adr(tmp_path, 42, "Implemented", "Existing Decision")
    archive_eligible_adrs(tmp_path, range_size=100)

    index_path = get_adrs_index_path(tmp_path)
    # Wipe the JSON to simulate a missing index
    index_path.unlink()
    assert not index_path.exists()

    returned_path = rebuild_archive_index(tmp_path)

    assert returned_path == index_path
    assert index_path.exists()
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    archived = [r for r in payload if r.get("state") == "archived"]
    assert len(archived) == 1
    assert archived[0]["adr_number"] == "ADR-042"
    assert archived[0]["title"] == "Existing Decision"


def test_rebuild_archive_index_writes_empty_array_when_no_archive(tmp_path):
    """ADR-811: rebuild on a clean directory produces an empty JSON array."""
    from src.lib.adr_utils import get_adrs_index_path, rebuild_archive_index

    index_path = rebuild_archive_index(tmp_path)
    assert index_path == get_adrs_index_path(tmp_path)
    assert index_path.exists()
    assert json.loads(index_path.read_text(encoding="utf-8")) == []


def test_archive_eligible_adrs_preserves_live_json_metadata_when_file_exists(tmp_path):
    """Central live JSON is richer than a thin ADR file and must win."""
    from src.lib.adr_utils import archive_eligible_adrs, get_adrs_index_path, upsert_adr_entry

    adr_path = _write_adr(
        tmp_path,
        736,
        "Implemented",
        "Sweep Interactive LLM Classification",
        "Thin wrapper text.",
    )
    upsert_adr_entry(
        tmp_path,
        {
            "adr_number": "ADR-736",
            "title": "Sweep Interactive LLM Classification",
            "state": "live",
            "status": "Implemented",
            "date": "2026-05-12",
            "deciders": ["gsannikov"],
            "related": ["ADR-732"],
            "hub": "adaptive",
            "tags": ["hygiene"],
            "decision_summary": "Rich central summary with implementation details.",
            "status_notes": "Rich status notes that should remain searchable.",
            "impact": {
                "paths_renamed": [],
                "apis_changed": ["hygiene-scan output schema"],
                "patterns_deprecated": [],
                "files_affected": ["project-brain/capabilities/skills/loop-hygiene/scripts/hygiene_scan.py"],
            },
            "spec_file": None,
            "plan_file": None,
            "superseded_by": None,
        },
    )

    archive_eligible_adrs(tmp_path, range_size=100)

    assert not adr_path.exists()
    payload = json.loads(get_adrs_index_path(tmp_path).read_text(encoding="utf-8"))
    archived = {record["adr_number"]: record for record in payload}
    record = archived["ADR-736"]
    assert record["state"] == "archived"
    assert record["decision_summary"] == "Rich central summary with implementation details."
    assert record["status_notes"] == "Rich status notes that should remain searchable."
    assert record["impact"]["apis_changed"] == ["hygiene-scan output schema"]


def test_archive_eligible_adrs_moves_bodies_to_flat_archive_and_writes_index(tmp_path):
    """ADR-811: archive layout is flat (archive/ADR-*.md); central JSON is single source."""
    from src.lib.adr_utils import archive_eligible_adrs, get_archived_adr_ledger

    implemented = _write_adr(tmp_path, 12, "Implemented", "Done Thing", "Done decision body.")
    accepted = _write_adr(tmp_path, 13, "Accepted", "Active Thing", "Active decision body.")

    result = archive_eligible_adrs(tmp_path, range_size=100)

    assert result.archived_numbers == [12]
    assert not implemented.exists()
    assert accepted.exists()

    archive_file = tmp_path / "archive" / "ADR-012-done-thing.md"
    assert archive_file.exists()
    assert "Done decision body." in archive_file.read_text(encoding="utf-8")
    assert not list((tmp_path / "archive").glob("*.zip"))

    legacy_ledger = tmp_path / "archive" / "implemented-adr-ledger.md"
    assert not legacy_ledger.exists()
    assert result.index_path == tmp_path / "adrs-index.json"
    assert result.index_path.exists()

    records = get_archived_adr_ledger(tmp_path)
    assert len(records) == 1
    assert records[0]["number"] == 12
    assert records[0]["archive_member"] == "ADR-012-done-thing.md"


def test_scan_and_numbering_include_archived_implemented_adrs(tmp_path):
    from src.lib.adr_utils import archive_eligible_adrs, find_next_adr_number, scan_adrs

    _write_adr(tmp_path, 98, "Implemented", "Archived Decision")
    _write_adr(tmp_path, 99, "Accepted", "Active Decision")

    archive_eligible_adrs(tmp_path, range_size=100)

    adrs = scan_adrs(tmp_path)
    by_number = {record["number"]: record for record in adrs}

    assert sorted(by_number) == [98, 99]
    assert by_number[98]["status"] == "Implemented"
    assert by_number[98]["archived"] is True
    assert by_number[98]["archive_member"] == "ADR-098-archived-decision.md"
    assert by_number[99].get("archived", False) is False
    assert find_next_adr_number(tmp_path) == 100


def test_find_gaps_counts_archived_implemented_adrs(tmp_path):
    from src.lib.adr_utils import archive_eligible_adrs, find_gaps

    _write_adr(tmp_path, 1, "Accepted", "First Decision")
    _write_adr(tmp_path, 2, "Implemented", "Archived Middle Decision")
    _write_adr(tmp_path, 3, "Accepted", "Third Decision")

    archive_eligible_adrs(tmp_path, range_size=100)

    assert find_gaps(tmp_path) == []


def test_extract_archived_adr_writes_requested_file_to_runtime_temp(tmp_path):
    from src.lib.adr_utils import archive_eligible_adrs, extract_archived_adr

    _write_adr(tmp_path, 7, "Implemented", "Extract Me", "Recoverable content.")
    archive_eligible_adrs(tmp_path, range_size=100)

    extracted = extract_archived_adr(tmp_path, 7, destination_dir=tmp_path / "runtime")

    assert extracted == tmp_path / "runtime" / "ADR-007-extract-me.md"
    assert "Recoverable content." in extracted.read_text(encoding="utf-8")


def test_archive_dry_run_does_not_modify_files(tmp_path):
    from src.lib.adr_utils import archive_eligible_adrs

    implemented = _write_adr(tmp_path, 1, "Implemented", "Dry Run")

    result = archive_eligible_adrs(tmp_path, dry_run=True)

    assert result.archived_numbers == [1]
    assert implemented.exists()
    assert not (tmp_path / "archive").exists()


def test_archive_eligible_adrs_can_scope_to_specific_adr(tmp_path):
    from src.lib.adr_utils import archive_eligible_adrs

    first = _write_adr(tmp_path, 1, "Implemented", "First Archived")
    second = _write_adr(tmp_path, 2, "Implemented", "Target Archived")

    result = archive_eligible_adrs(tmp_path, range_size=100, adr_numbers=["ADR-002"])

    assert result.archived_numbers == [2]
    assert first.exists()
    assert not second.exists()

    archive_dir = tmp_path / "archive"
    archived_files = sorted(p.name for p in archive_dir.glob("ADR-*.md"))
    assert archived_files == ["ADR-002-target-archived.md"]


def test_archive_eligible_adrs_scope_preserves_other_live_json_entries(tmp_path):
    from src.lib.adr_utils import archive_eligible_adrs, load_adrs_index, upsert_adr_entry

    for number in (100, 200):
        upsert_adr_entry(
            tmp_path,
            {
                "adr_number": f"ADR-{number:03d}",
                "title": f"Decision {number}",
                "state": "live",
                "status": "Implemented",
                "date": "2026-05-10",
                "deciders": [],
                "related": [],
                "hub": None,
                "tags": [],
                "decision_summary": "Decision body lives in JSON.",
                "status_notes": "",
                "impact": {
                    "paths_renamed": [],
                    "apis_changed": [],
                    "patterns_deprecated": [],
                    "files_affected": [],
                },
                "spec_file": None,
                "plan_file": None,
                "superseded_by": None,
            },
        )

    result = archive_eligible_adrs(tmp_path, range_size=100, adr_numbers=[200])

    assert result.archived_numbers == [200]
    records = {r["adr_number"]: r for r in load_adrs_index(tmp_path)}
    assert records["ADR-100"]["state"] == "live"
    assert records["ADR-200"]["state"] == "archived"


def test_archive_live_markdown_preserves_existing_index_metadata(tmp_path):
    from src.lib.adr_utils import archive_eligible_adrs, load_adrs_index, upsert_adr_entry

    _write_adr(tmp_path, 42, "Implemented", "Indexed Decision", "Thin index body.")
    upsert_adr_entry(
        tmp_path,
        {
            "adr_number": "ADR-042",
            "title": "Indexed Decision",
            "state": "live",
            "status": "Implemented",
            "date": "2026-05-10",
            "deciders": ["gsannikov"],
            "related": [],
            "hub": None,
            "tags": ["archive"],
            "decision_summary": "Rich summary from the central index.",
            "status_notes": "Important status note from the central index.",
            "impact": {
                "paths_renamed": [],
                "apis_changed": ["api.example"],
                "patterns_deprecated": [],
                "files_affected": [],
            },
            "spec_file": None,
            "plan_file": None,
            "superseded_by": None,
        },
    )

    archive_eligible_adrs(tmp_path, range_size=100, adr_numbers=[42])

    records = {r["adr_number"]: r for r in load_adrs_index(tmp_path)}
    archived = records["ADR-042"]
    assert archived["state"] == "archived"
    assert archived["decision_summary"] == "Rich summary from the central index."
    assert archived["status_notes"] == "Important status note from the central index."
    assert archived["impact"]["apis_changed"] == ["api.example"]


# ---------------------------------------------------------------------------
# ADR-811 — central index tests (supersede ADR-642 zip assertions)
# ---------------------------------------------------------------------------


def test_central_index_holds_live_and_archived(tmp_path):
    """ADR-811: a single adrs-index.json holds both live and archived rows."""
    from src.lib.adr_utils import (
        archive_eligible_adrs,
        get_adrs_index_path,
        upsert_adr_entry,
    )

    upsert_adr_entry(
        tmp_path,
        {
            "adr_number": "ADR-100",
            "title": "Live Decision",
            "state": "live",
            "status": "Proposed",
            "date": "2026-05-09",
            "deciders": ["User"],
            "related": [],
            "hub": "dev",
            "tags": ["live"],
            "decision_summary": "Keep this live.",
            "status_notes": "",
            "impact": {
                "paths_renamed": [],
                "apis_changed": [],
                "patterns_deprecated": [],
                "files_affected": [],
            },
            "spec_file": None,
            "plan_file": None,
            "superseded_by": None,
        },
    )

    _write_adr(tmp_path, 50, "Implemented", "Archived Decision", "Body.")
    archive_eligible_adrs(tmp_path, range_size=100)

    payload = json.loads(get_adrs_index_path(tmp_path).read_text(encoding="utf-8"))
    by_number = {entry["adr_number"]: entry for entry in payload}
    assert by_number["ADR-100"]["state"] == "live"
    assert by_number["ADR-050"]["state"] == "archived"
    assert by_number["ADR-050"]["archive_member"] == "ADR-050-archived-decision.md"
    assert "zip_path" not in by_number["ADR-050"]


def test_archive_eligible_adrs_transitions_live_json_entry(tmp_path):
    """ADR-811: archive sweep flips a live JSON entry to archived without an .md file."""
    from src.lib.adr_utils import (
        archive_eligible_adrs,
        load_adrs_index,
        upsert_adr_entry,
    )

    upsert_adr_entry(
        tmp_path,
        {
            "adr_number": "ADR-200",
            "title": "Promote To Archived",
            "state": "live",
            "status": "Implemented",
            "date": "2026-05-10",
            "deciders": ["User"],
            "related": [],
            "hub": "dev",
            "tags": [],
            "decision_summary": "Decision body lives in JSON.",
            "status_notes": "",
            "impact": {
                "paths_renamed": [],
                "apis_changed": [],
                "patterns_deprecated": [],
                "files_affected": [],
            },
            "spec_file": None,
            "plan_file": None,
            "superseded_by": None,
        },
    )

    result = archive_eligible_adrs(tmp_path, range_size=100)

    assert 200 in result.archived_numbers
    records = {r["adr_number"]: r for r in load_adrs_index(tmp_path)}
    assert records["ADR-200"]["state"] == "archived"
    assert records["ADR-200"]["archive_member"] == "ADR-200-promote-to-archived.md"
    assert "zip_path" not in records["ADR-200"]
    # Plain file written to archive/ from index body.
    archive_file = tmp_path / "archive" / "ADR-200-promote-to-archived.md"
    assert archive_file.exists()


def test_upsert_and_delete_adr_entry_round_trip(tmp_path):
    from src.lib.adr_utils import (
        delete_adr_entry,
        load_adrs_index,
        upsert_adr_entry,
    )

    upsert_adr_entry(
        tmp_path,
        {
            "adr_number": "ADR-300",
            "title": "Reversible",
            "state": "live",
            "status": "Proposed",
            "date": "2026-05-10",
            "deciders": [],
            "related": [],
            "hub": None,
            "tags": [],
            "decision_summary": "x",
            "status_notes": "",
            "impact": {
                "paths_renamed": [],
                "apis_changed": [],
                "patterns_deprecated": [],
                "files_affected": [],
            },
            "spec_file": None,
            "plan_file": None,
            "superseded_by": None,
        },
    )
    assert any(r["adr_number"] == "ADR-300" for r in load_adrs_index(tmp_path))
    delete_adr_entry(tmp_path, "ADR-300")
    assert all(r["adr_number"] != "ADR-300" for r in load_adrs_index(tmp_path))
