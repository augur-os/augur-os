"""Unit tests for browse index_common value helpers and constants.

Targets the pure helpers in
``src.mcp.augur_framework.tools.infrastructure.browse.index_common``:
- ``_as_string_list`` — list/tuple/comma-string/other coercion with empty pruning
- ``_metadata_text`` — None/list/tuple/bool/scalar rendering
plus the shared constant tables those modules export.

Run with:
    pytest tests/test_browse_index_common.py -v
"""

from src.mcp.augur_framework.tools.infrastructure.browse.index_common import (
    _AI_ARTIFACT_PROBLEM_IDS,
    _ARCHIVE_SEARCH_METADATA_KEYS,
    _BROWSE_LIMIT,
    _FILESYSTEM_BACKED_CATEGORIES,
    _VAULT_JOURNEY_ROOTS,
    _as_string_list,
    _metadata_text,
)


class TestAsStringList:
    def test_list_input_stringifies_and_drops_empty_strings(self):
        # Only items whose str() is empty ("") are dropped; None -> "None" stays.
        assert _as_string_list(["a", 1, ""]) == ["a", "1"]

    def test_tuple_input(self):
        assert _as_string_list(("x", "y")) == ["x", "y"]

    def test_comma_string_splits_and_strips(self):
        assert _as_string_list("a, b ,c") == ["a", "b", "c"]

    def test_empty_string_returns_empty_list(self):
        assert _as_string_list("") == []

    def test_comma_string_drops_blank_segments(self):
        assert _as_string_list("a,,  ,b") == ["a", "b"]

    def test_non_sequence_returns_empty_list(self):
        assert _as_string_list(42) == []
        assert _as_string_list(None) == []
        assert _as_string_list({"k": "v"}) == []


class TestMetadataText:
    def test_none_returns_empty(self):
        assert _metadata_text(None) == ""

    def test_list_joins_with_commas_and_strips(self):
        assert _metadata_text([" a ", "b", ""]) == "a,b"

    def test_tuple_joins_with_commas(self):
        assert _metadata_text(("x", "y")) == "x,y"

    def test_bool_renders_lowercase_words(self):
        assert _metadata_text(True) == "true"
        assert _metadata_text(False) == "false"

    def test_scalar_stringifies(self):
        assert _metadata_text(7) == "7"
        assert _metadata_text("hello") == "hello"


class TestConstants:
    def test_browse_limit_is_positive_int(self):
        assert isinstance(_BROWSE_LIMIT, int)
        assert _BROWSE_LIMIT == 1500

    def test_filesystem_backed_categories_membership(self):
        assert "documents" in _FILESYSTEM_BACKED_CATEGORIES
        assert "skills" in _FILESYSTEM_BACKED_CATEGORIES
        assert "inbox" not in _FILESYSTEM_BACKED_CATEGORIES

    def test_ai_artifact_problem_ids_contains_known_ids(self):
        assert "duplicate" in _AI_ARTIFACT_PROBLEM_IDS
        assert "permission_denied" in _AI_ARTIFACT_PROBLEM_IDS

    def test_vault_journey_roots_identity_mapping(self):
        # Every value maps a journey root onto itself.
        for key, value in _VAULT_JOURNEY_ROOTS.items():
            assert key == value
        assert _VAULT_JOURNEY_ROOTS["notes"] == "notes"

    def test_archive_search_metadata_keys_include_source_path(self):
        assert "source_path" in _ARCHIVE_SEARCH_METADATA_KEYS
        assert "journey_category" in _ARCHIVE_SEARCH_METADATA_KEYS
