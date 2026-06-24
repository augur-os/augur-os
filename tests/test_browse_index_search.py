"""Unit tests for browse index_search match/score/scope/journey helpers.

Targets the pure helpers in
``src.mcp.augur_framework.tools.infrastructure.browse.index_search``:
- ``_entry_search_values`` — flattened searchable field list
- ``_entry_matches_search`` — case-insensitive substring match
- ``_entry_search_score`` — exact(3)/prefix(2)/substring(1)/none(0) ranking
- ``_entry_timestamp`` — ISO parsing across modified/indexed_at/created
- ``_entry_search_sort_key`` — composite (-score, -ts, label) ordering
- ``_entry_matches_scope`` — packet/shared/private/none scope filtering
- ``_entry_matches_vault_journey`` — journey_category / _index_path / source_path
- ``_latest_indexed_at`` — max indexed_at across entries

Any path math runs against ``tmp_path``-style fabricated paths only.

Run with:
    pytest tests/test_browse_index_search.py -v
"""

from pathlib import Path

from src.mcp.augur_framework.tools.infrastructure.browse.index_search import (
    _entry_matches_scope,
    _entry_matches_search,
    _entry_matches_vault_journey,
    _entry_search_score,
    _entry_search_sort_key,
    _entry_search_values,
    _entry_timestamp,
    _latest_indexed_at,
)


class TestSearchValues:
    def test_collects_core_fields(self):
        entry = {
            "id": "i1",
            "name": "n1",
            "title": "Title",
            "description": "desc",
            "source": "src",
        }
        values = _entry_search_values(entry)
        assert "Title" in values
        assert "desc" in values
        assert "i1" in values

    def test_joins_client_source_lists(self):
        entry = {"client_sources": ["claude", "codex"], "skill_clients": "a,b"}
        values = _entry_search_values(entry)
        assert "claude codex" in values
        assert "a b" in values


class TestMatchesSearch:
    def test_case_insensitive_substring(self):
        entry = {"title": "Quarterly Report"}
        assert _entry_matches_search(entry, "quarterly") is True
        assert _entry_matches_search(entry, "report") is True

    def test_no_match(self):
        assert _entry_matches_search({"title": "Report"}, "invoice") is False

    def test_matches_archive_metadata_key(self):
        entry = {"reason": "stale-generated cleanup"}
        assert _entry_matches_search(entry, "stale-generated") is True


class TestSearchScore:
    def test_exact_match_scores_three(self):
        assert _entry_search_score({"title": "report"}, "report") == 3

    def test_prefix_match_scores_two(self):
        assert _entry_search_score({"title": "reporting"}, "report") == 2

    def test_substring_match_scores_one(self):
        assert _entry_search_score({"title": "the report card"}, "report") == 1

    def test_no_match_scores_zero(self):
        assert _entry_search_score({"title": "ledger"}, "report") == 0

    def test_best_field_wins(self):
        # description is exact match (3) even though title only substring-matches.
        entry = {"title": "monthly reports", "description": "report"}
        assert _entry_search_score(entry, "report") == 3


class TestTimestamp:
    def test_parses_modified_iso(self):
        ts = _entry_timestamp({"modified": "2026-01-02T03:04:05"})
        assert ts > 0

    def test_handles_zulu_suffix(self):
        ts = _entry_timestamp({"indexed_at": "2026-01-02T03:04:05Z"})
        assert ts > 0

    def test_falls_back_through_keys(self):
        # modified is unparsable, created is valid -> uses created.
        ts = _entry_timestamp({"modified": "not-a-date", "created": "2026-06-01T00:00:00"})
        assert ts > 0

    def test_all_missing_or_bad_returns_zero(self):
        assert _entry_timestamp({}) == 0.0
        assert _entry_timestamp({"modified": "garbage"}) == 0.0

    def test_later_timestamp_is_greater(self):
        early = _entry_timestamp({"modified": "2026-01-01T00:00:00"})
        late = _entry_timestamp({"modified": "2026-12-31T00:00:00"})
        assert late > early


class TestSearchSortKey:
    def test_sorts_exact_before_partial_then_recency(self):
        exact = {"title": "report", "modified": "2026-01-01T00:00:00"}
        prefix_recent = {"title": "reporting", "modified": "2026-12-31T00:00:00"}
        prefix_old = {"title": "reporting", "modified": "2026-01-01T00:00:00"}
        ordered = sorted(
            [prefix_old, prefix_recent, exact],
            key=lambda e: _entry_search_sort_key(e, "report"),
        )
        # Exact (score 3) first; among prefix matches the more recent ranks higher.
        assert ordered[0] is exact
        assert ordered[1] is prefix_recent
        assert ordered[2] is prefix_old


class TestMatchesScope:
    def test_no_scope_always_true(self):
        assert _entry_matches_scope({}, None) is True
        assert _entry_matches_scope({}, "") is True

    def test_packet_requires_packet_promotion_state(self):
        assert _entry_matches_scope({"promotion_state": "packet"}, "packet") is True
        assert _entry_matches_scope({"promotion_state": "live"}, "packet") is False

    def test_shared_excludes_packets(self):
        entry = {"promotion_state": "packet", "vault_scope": "shared"}
        assert _entry_matches_scope(entry, "shared") is False

    def test_private_matches_vault_scope(self):
        assert _entry_matches_scope({"vault_scope": "private"}, "private") is True
        assert _entry_matches_scope({"vault_scope": "shared"}, "private") is False

    def test_unknown_scope_passthrough_true(self):
        assert _entry_matches_scope({"vault_scope": "shared"}, "other") is True


class TestMatchesVaultJourney:
    def test_explicit_journey_category_wins(self):
        entry = {"journey_category": "notes"}
        assert _entry_matches_vault_journey(entry, Path("/cat"), "notes") is True
        assert _entry_matches_vault_journey(entry, Path("/cat"), "inbox") is False

    def test_index_path_relative_to_category(self):
        category_dir = Path("/vault/.index")
        entry = {"_index_path": "/vault/.index/notes/entry.json"}
        assert _entry_matches_vault_journey(entry, category_dir, "notes") is True
        assert _entry_matches_vault_journey(entry, category_dir, "sources") is False

    def test_absolute_source_path_under_au_vault(self):
        entry = {"source_path": "/home/user/Au-vault/sources/doc.md"}
        assert _entry_matches_vault_journey(entry, Path("/cat"), "sources") is True
        assert _entry_matches_vault_journey(entry, Path("/cat"), "notes") is False

    def test_relative_source_path_first_part(self):
        entry = {"source_path": "drafts/idea.md"}
        assert _entry_matches_vault_journey(entry, Path("/cat"), "drafts") is True

    def test_no_signal_returns_false(self):
        assert _entry_matches_vault_journey({}, Path("/cat"), "notes") is False


class TestLatestIndexedAt:
    def test_returns_max_string_timestamp(self):
        entries = [
            {"indexed_at": "2026-01-01T00:00:00"},
            {"indexed_at": "2026-06-01T00:00:00"},
            {"indexed_at": "2026-03-01T00:00:00"},
        ]
        assert _latest_indexed_at(entries) == "2026-06-01T00:00:00"

    def test_ignores_entries_without_timestamp(self):
        entries = [{"id": "x"}, {"indexed_at": "2026-02-02T00:00:00"}]
        assert _latest_indexed_at(entries) == "2026-02-02T00:00:00"

    def test_empty_returns_none(self):
        assert _latest_indexed_at([]) is None
        assert _latest_indexed_at([{"id": "no-ts"}]) is None
