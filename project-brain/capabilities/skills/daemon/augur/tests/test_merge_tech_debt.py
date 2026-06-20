"""Regression tests for merged marker payload compatibility."""

from __future__ import annotations

import json
from pathlib import Path

from skills.daemon.scripts import merge_tech_debt


def test_load_existing_merged_reads_markers_from_object_payload(tmp_path: Path, monkeypatch) -> None:
    merged_file = tmp_path / "merged_markers.json"
    payload = {
        "merged_at": "2026-02-05T12:00:00",
        "markers": [{"message": "Issue A", "count": 2}],
    }
    merged_file.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(merge_tech_debt, "get_merged_markers_file", lambda: merged_file)

    result = merge_tech_debt.load_existing_merged()

    assert result == payload["markers"]


def test_load_existing_merged_supports_legacy_list_payload(tmp_path: Path, monkeypatch) -> None:
    merged_file = tmp_path / "merged_markers.json"
    payload = [{"message": "Issue B", "count": 1}]
    merged_file.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(merge_tech_debt, "get_merged_markers_file", lambda: merged_file)

    result = merge_tech_debt.load_existing_merged()

    assert result == payload
