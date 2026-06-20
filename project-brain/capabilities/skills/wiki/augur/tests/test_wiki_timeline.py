"""Tests for ADR-740 wiki timeline helpers."""
from __future__ import annotations

import pytest

from skills.wiki.scripts.wiki_timeline import (
    TimelineEntry,
    append_timeline_entries,
    extract_compiled_truth,
    extract_timeline,
    replace_compiled_truth,
    validate_timeline_entries,
)


BODY = """# Page

## Compiled truth

### Current Thesis

Keep this human text.

## Timeline

- _at: 2026-05-14T10:00:00Z  _source: vault://a.md
  Latest observation.
"""


def test_extracts_compiled_truth_and_timeline_zones() -> None:
    assert "Keep this human text." in extract_compiled_truth(BODY)
    assert "Latest observation." in extract_timeline(BODY)


def test_replace_compiled_truth_preserves_timeline() -> None:
    updated = replace_compiled_truth(BODY, "### Current Thesis\n\nApproved rewrite.")
    assert "Approved rewrite." in updated
    assert "Latest observation." in updated
    assert "Keep this human text." not in updated


def test_append_timeline_entries_newest_first_and_preserves_truth() -> None:
    updated = append_timeline_entries(
        BODY,
        [
            TimelineEntry(
                at="2026-05-15T08:00:00Z",
                source="graph://edge-1",
                observation="Newer observation.",
            )
        ],
    )
    assert updated.index("Newer observation.") < updated.index("Latest observation.")
    assert "Keep this human text." in updated


def test_append_timeline_entries_inserts_older_entries_after_existing_newer() -> None:
    updated = append_timeline_entries(
        BODY,
        [
            TimelineEntry(
                at="2026-05-13T08:00:00Z",
                source="vault://older.md",
                observation="Older observation.",
            )
        ],
    )
    assert updated.index("Latest observation.") < updated.index("Older observation.")


def test_append_timeline_entries_preserves_existing_block_order() -> None:
    body = """# Page

## Compiled truth

text

## Timeline

- _at: 2026-05-13T10:00:00Z  _source: vault://old.md
  Old listed first.

- _at: 2026-05-14T10:00:00Z  _source: vault://new.md
  New listed second.
"""
    updated = append_timeline_entries(
        body,
        [
            TimelineEntry(
                at="2026-05-12T10:00:00Z",
                source="vault://older.md",
                observation="Older appended observation.",
            )
        ],
    )
    assert updated.index("Old listed first.") < updated.index("New listed second.")
    assert updated.index("New listed second.") < updated.index("Older appended observation.")


def test_validate_rejects_missing_required_fields() -> None:
    with pytest.raises(ValueError, match="_source"):
        TimelineEntry(at="2026-05-15T08:00:00Z", source="", observation="bad")
    with pytest.raises(ValueError, match="_at"):
        TimelineEntry(at="", source="vault://a.md", observation="bad")
    with pytest.raises(ValueError, match="_at"):
        TimelineEntry(at="not-a-timestamp", source="vault://a.md", observation="bad")
    with pytest.raises(ValueError, match="_source"):
        TimelineEntry(at="2026-05-15T08:00:00Z", source="not-uri", observation="bad")


def test_validate_reports_missing_observation() -> None:
    body = """# Page

## Compiled truth

text

## Timeline

- _at: 2026-05-14T10:00:00Z  _source: vault://new.md
"""
    result = validate_timeline_entries(body)
    assert "timeline_entry_missing_observation" in result.errors


def test_validate_reports_out_of_order_warning() -> None:
    body = """# Page

## Compiled truth

text

## Timeline

- _at: 2026-05-13T10:00:00Z  _source: vault://old.md
  Old.
- _at: 2026-05-14T10:00:00Z  _source: vault://new.md
  New.
"""
    result = validate_timeline_entries(body)
    assert result.errors == []
    assert "timeline_out_of_order" in result.warnings
