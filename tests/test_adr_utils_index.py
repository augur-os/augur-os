"""Unit tests for src.lib.adr_utils._index (index CRUD, path + archive helpers)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from src.lib.adr_utils._index import (
    ARCHIVABLE_STATUSES,
    AdrArchiveResult,
    _empty_impact,
    _extract_number,
    _legacy_ledger_record,
    delete_adr_entry,
    get_adrs_index_path,
    get_archive_dir,
    get_archive_index_path,
    get_archived_adr_ledger,
    get_archived_adr_path,
    load_adrs_index,
    upsert_adr_entry,
    write_adrs_index,
)


def test_extract_number_variants():
    assert _extract_number(42) == 42
    assert _extract_number("ADR-007") == 7
    assert _extract_number("adr-7") == 7
    assert _extract_number("ADR7") == 7
    assert _extract_number(None) is None
    assert _extract_number("not-an-adr") is None
    assert _extract_number(3.5) is None


def test_empty_impact_shape():
    impact = _empty_impact()
    assert impact == {
        "paths_renamed": [],
        "apis_changed": [],
        "patterns_deprecated": [],
        "files_affected": [],
    }
    # Independent instances (not a shared mutable default).
    impact["paths_renamed"].append("x")
    assert _empty_impact()["paths_renamed"] == []


def test_archivable_statuses_constant():
    assert ARCHIVABLE_STATUSES == frozenset({"Implemented", "Deprecated", "Superseded", "Cancelled"})
    assert "Accepted" not in ARCHIVABLE_STATUSES


def test_path_helpers(tmp_path):
    assert get_archive_dir(tmp_path) == tmp_path / "archive"
    assert get_adrs_index_path(tmp_path) == tmp_path / "adrs-index.json"
    # Compat shim points at the same central index.
    assert get_archive_index_path(tmp_path) == get_adrs_index_path(tmp_path)


def test_load_adrs_index_missing_returns_empty(tmp_path):
    assert load_adrs_index(tmp_path) == []


def test_load_adrs_index_malformed_json_returns_empty(tmp_path):
    get_adrs_index_path(tmp_path).write_text("{ not json", encoding="utf-8")
    assert load_adrs_index(tmp_path) == []


def test_load_adrs_index_non_list_returns_empty(tmp_path):
    get_adrs_index_path(tmp_path).write_text('{"adr_number": "ADR-001"}', encoding="utf-8")
    assert load_adrs_index(tmp_path) == []


def test_load_adrs_index_filters_non_dict_members(tmp_path):
    get_adrs_index_path(tmp_path).write_text(json.dumps([{"adr_number": "ADR-001"}, "garbage", 3]), encoding="utf-8")
    assert load_adrs_index(tmp_path) == [{"adr_number": "ADR-001"}]


def test_write_adrs_index_sorts_and_filters(tmp_path):
    records = [
        {"adr_number": "ADR-010", "title": "Ten"},
        {"adr_number": "ADR-002", "title": "Two"},
        {"title": "no number"},  # dropped — no adr_number
    ]
    index_path = write_adrs_index(tmp_path, records)
    assert index_path == get_adrs_index_path(tmp_path)
    loaded = load_adrs_index(tmp_path)
    assert [r["adr_number"] for r in loaded] == ["ADR-002", "ADR-010"]


def test_write_then_load_roundtrip(tmp_path):
    record = {"adr_number": "ADR-099", "title": "Round", "state": "live"}
    write_adrs_index(tmp_path, [record])
    loaded = load_adrs_index(tmp_path)
    assert loaded == [record]


def test_upsert_inserts_and_updates(tmp_path):
    upsert_adr_entry(tmp_path, {"adr_number": "ADR-005", "title": "Orig"})
    upsert_adr_entry(tmp_path, {"adr_number": "ADR-006", "title": "Six"})
    upsert_adr_entry(tmp_path, {"adr_number": "ADR-005", "title": "Updated"})

    loaded = {r["adr_number"]: r["title"] for r in load_adrs_index(tmp_path)}
    assert loaded == {"ADR-005": "Updated", "ADR-006": "Six"}


def test_upsert_requires_adr_number(tmp_path):
    with pytest.raises(ValueError):
        upsert_adr_entry(tmp_path, {"title": "no number"})


def test_delete_adr_entry_by_str_and_int(tmp_path):
    write_adrs_index(
        tmp_path,
        [
            {"adr_number": "ADR-001", "title": "One"},
            {"adr_number": "ADR-002", "title": "Two"},
            {"adr_number": "ADR-003", "title": "Three"},
        ],
    )
    delete_adr_entry(tmp_path, "ADR-002")
    delete_adr_entry(tmp_path, 3)  # int gets zero-padded
    remaining = [r["adr_number"] for r in load_adrs_index(tmp_path)]
    assert remaining == ["ADR-001"]


def test_get_archived_adr_path(tmp_path):
    # No archive dir yet.
    assert get_archived_adr_path(tmp_path, 12) is None

    archive = get_archive_dir(tmp_path)
    archive.mkdir()
    target = archive / "ADR-012-some-slug.md"
    target.write_text("body", encoding="utf-8")
    assert get_archived_adr_path(tmp_path, 12) == target

    # Bare-number filename also resolves.
    (archive / "ADR-013.md").write_text("body", encoding="utf-8")
    assert get_archived_adr_path(tmp_path, 13) == archive / "ADR-013.md"

    # Unknown number -> None.
    assert get_archived_adr_path(tmp_path, 999) is None


def test_get_archived_adr_ledger_projects_legacy_shape(tmp_path):
    write_adrs_index(
        tmp_path,
        [
            {"adr_number": "ADR-001", "state": "live", "title": "Live"},
            {
                "adr_number": "ADR-050",
                "state": "archived",
                "title": "Archived",
                "zip_path": "archive/legacy.zip",
                "zip_member": "ADR-050.md",
            },
        ],
    )
    ledger = get_archived_adr_ledger(tmp_path)
    assert len(ledger) == 1
    entry = ledger[0]
    assert entry["number"] == 50
    assert "adr_number" not in entry
    assert entry["archive_path"] == "archive/legacy.zip"
    assert entry["archive_member"] == "ADR-050.md"


def test_legacy_ledger_record_handles_bad_number():
    rec = _legacy_ledger_record({"adr_number": "ADR-not-a-number", "title": "X"})
    # Unparseable number simply leaves "number" unset; no crash.
    assert "number" not in rec
    assert rec["title"] == "X"


def test_adr_archive_result_is_frozen_dataclass(tmp_path):
    result = AdrArchiveResult(
        archived_numbers=[1],
        skipped_numbers=[2],
        index_path=get_adrs_index_path(tmp_path),
        archive_paths=[],
    )
    assert result.dry_run is False
    with pytest.raises(Exception):
        result.dry_run = True  # frozen
