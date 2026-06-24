"""Unit tests for src.lib.adr_utils._parse (numbering, parsing, normalisation)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.lib.adr_utils._index import write_adrs_index
from src.lib.adr_utils._parse import (
    CANONICAL_STATUSES,
    _first_prose_paragraph,
    _materialize_live_md,
    _merge_live_file_record_with_index,
    _normalize_related_field,
    _plain_member_for_record,
    _record_from_adr_file,
    _slug_from_title,
    find_next_adr_number,
    normalize_adr_status,
    parse_adr_number,
    parse_adr_slug,
)
from src.lib.frontmatter_utils import write_frontmatter


def test_parse_adr_number():
    assert parse_adr_number("ADR-042-foo.md") == 42
    assert parse_adr_number("adr-7.md") == 7
    assert parse_adr_number("ADR-100") == 100
    assert parse_adr_number("README.md") is None
    assert parse_adr_number("no-digits-ADR-x.md") is None


def test_parse_adr_slug():
    assert parse_adr_slug("ADR-001-some-decision.md") == "some-decision"
    assert parse_adr_slug("ADR-002-feature-hardening.md") == "feature"
    assert parse_adr_slug("ADR-003.md") is None
    assert parse_adr_slug("random.md") is None


def test_normalize_adr_status_canonical_passthrough():
    assert normalize_adr_status("Accepted") == "Accepted"
    assert normalize_adr_status("Proposed") == "Proposed"
    assert normalize_adr_status("Future") == "Future"


def test_normalize_adr_status_mappings():
    assert normalize_adr_status("in progress") == "Accepted"
    assert normalize_adr_status("Pending Execution") == "Accepted"
    assert normalize_adr_status("Partially Implemented (phase 1)") == "Accepted"
    assert normalize_adr_status("Accepted (phase 1 of 3)") == "Accepted"
    assert normalize_adr_status("Accepted (phases 1-2 implemented)") == "Implemented"
    assert normalize_adr_status("Accepted (implemented in 2026)") == "Implemented"
    assert normalize_adr_status("Superseded by ADR-900") == "Superseded"
    assert normalize_adr_status("Implemented") == "Implemented"


def test_normalize_adr_status_unknown_and_non_string():
    assert normalize_adr_status("Wishlist") == "Other"
    assert normalize_adr_status("") == "Other"
    assert normalize_adr_status(None) == "Other"
    assert normalize_adr_status(123) == "Other"


def test_canonical_statuses_constant():
    assert "Implemented" in CANONICAL_STATUSES
    assert "Other" not in CANONICAL_STATUSES


def test_first_prose_paragraph():
    body = "# Title\n\n| a | b |\n- bullet\n**bold**\n\nReal prose here.\nNext line."
    assert _first_prose_paragraph(body) == "Real prose here."
    # Nothing after a heading -> empty.
    assert _first_prose_paragraph("no heading at all\nplain") == ""


def test_normalize_related_field():
    assert _normalize_related_field([1, "ADR-2", "ADR-003", "7", "free-text"]) == [
        "ADR-001",
        "ADR-002",
        "ADR-003",
        "ADR-007",
        "free-text",
    ]
    assert _normalize_related_field(None) == []
    assert _normalize_related_field("not-a-list") == []
    assert _normalize_related_field([" ", ""]) == []


def test_slug_from_title():
    assert _slug_from_title("Hello, World!") == "hello-world"
    assert _slug_from_title("  Multiple   Spaces  ") == "multiple-spaces"
    assert _slug_from_title("") == "untitled"
    assert _slug_from_title("!!!") == "untitled"


def test_plain_member_for_record():
    assert (
        _plain_member_for_record({"adr_number": "ADR-042", "title": "My Decision"})
        == "ADR-042-my-decision.md"
    )
    # Existing archive_member wins (idempotency).
    assert (
        _plain_member_for_record(
            {"adr_number": "ADR-042", "title": "x", "archive_member": "ADR-042-frozen.md"}
        )
        == "ADR-042-frozen.md"
    )


def test_record_from_adr_file_parses_frontmatter(tmp_path):
    adr = tmp_path / "ADR-077-test-decision.md"
    write_frontmatter(
        adr,
        {
            "status": "Implemented",
            "date": "2026-01-02",
            "hub": "workspace",
            "tags": ["alpha"],
            "related": [1, "ADR-2"],
            "deciders": ["gur"],
        },
        "# ADR-077: Test Decision\n\nThis is the decision rationale.\n",
    )
    record = _record_from_adr_file(adr)
    assert record is not None
    assert record["adr_number"] == "ADR-077"
    assert record["title"] == "Test Decision"
    assert record["status"] == "Implemented"
    assert record["date"] == "2026-01-02"
    assert record["state"] == "live"
    assert record["related"] == ["ADR-001", "ADR-002"]
    assert record["deciders"] == ["gur"]
    assert record["decision_summary"] == "This is the decision rationale."
    assert record["_legacy_filename"] == "ADR-077-test-decision.md"


def test_record_from_adr_file_non_adr_returns_none(tmp_path):
    other = tmp_path / "notes.md"
    other.write_text("# notes\n", encoding="utf-8")
    assert _record_from_adr_file(other) is None


def test_materialize_live_md_roundtrip(tmp_path):
    record = {
        "adr_number": "ADR-200",
        "title": "Materialized",
        "status": "Implemented",
        "date": "2026-03-03",
        "decision_summary": "We decided to materialize.",
        "tags": ["t"],
        "related": ["ADR-001"],
    }
    data = _materialize_live_md(record)
    assert isinstance(data, bytes)
    text = data.decode("utf-8")
    assert text.startswith("---\n")
    assert "# ADR-200: Materialized" in text
    assert "We decided to materialize." in text

    # The materialized file is itself re-parseable.
    out = tmp_path / "ADR-200-materialized.md"
    out.write_bytes(data)
    reparsed = _record_from_adr_file(out)
    assert reparsed is not None
    assert reparsed["title"] == "Materialized"
    assert reparsed["status"] == "Implemented"


def test_merge_live_file_record_with_index():
    parsed = {"adr_number": "ADR-010", "title": "Parsed Title", "status": "Implemented", "related": []}
    indexed = {
        "adr_number": "ADR-010",
        "title": "Old Title",
        "status": "Accepted",
        "decision_summary": "Rich summary kept from index.",
        "tags": ["keep"],
    }
    merged = _merge_live_file_record_with_index(parsed, indexed)
    # Parsed non-empty fields override.
    assert merged["title"] == "Parsed Title"
    assert merged["status"] == "Implemented"
    # Index-only rich metadata preserved.
    assert merged["decision_summary"] == "Rich summary kept from index."
    assert merged["tags"] == ["keep"]

    # No index record -> parsed returned unchanged.
    assert _merge_live_file_record_with_index(parsed, None) is parsed


def test_find_next_adr_number_from_index(tmp_path):
    assert find_next_adr_number(tmp_path) == 1  # empty
    write_adrs_index(
        tmp_path,
        [{"adr_number": "ADR-005"}, {"adr_number": "ADR-012"}],
    )
    assert find_next_adr_number(tmp_path) == 13


def test_find_next_adr_number_md_fallback(tmp_path):
    write_adrs_index(tmp_path, [{"adr_number": "ADR-005"}])
    (tmp_path / "ADR-030-stray.md").write_text("# ADR-030\n", encoding="utf-8")
    assert find_next_adr_number(tmp_path) == 31
