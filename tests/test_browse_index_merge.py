"""Unit tests for browse index_merge external/inventory merge helpers.

Targets the helpers in
``src.mcp.augur_framework.tools.infrastructure.browse.index_merge``:
- ``_external_integration_entries`` — best-effort, always returns a list
- ``_merge_external_integration_entries`` — id-deduped append
- ``_source_path_dedupe_key`` — resolved-path / URL / empty dedupe key
- ``_filter_missing_inventory_entries`` — drop entries whose file is missing
- ``_merge_inventory_entries`` — dedupe-by-path merge with metadata fold-in
- ``_merge_inventory_metadata`` — problem_* metadata + problem-tag reconciliation

Real-filesystem checks use ``tmp_path`` absolute paths only; the real vault and
repo are never read.

Run with:
    pytest tests/test_browse_index_merge.py -v
"""

from pathlib import Path

from src.mcp.augur_framework.tools.infrastructure.browse.index_merge import (
    _external_integration_entries,
    _filter_missing_inventory_entries,
    _merge_external_integration_entries,
    _merge_inventory_entries,
    _merge_inventory_metadata,
    _source_path_dedupe_key,
)


class TestExternalIntegrationEntries:
    def test_returns_a_list(self):
        # Best-effort: real external-services may or may not be configured, but
        # the contract is "never raise, always a list".
        result = _external_integration_entries()
        assert isinstance(result, list)


class TestMergeExternalIntegrationEntries:
    def test_empty_external_returns_original(self):
        base = [{"id": "a"}]
        assert _merge_external_integration_entries(base, []) == base

    def test_appends_new_ids(self):
        base = [{"id": "a"}]
        merged = _merge_external_integration_entries(base, [{"id": "b"}])
        ids = [e["id"] for e in merged]
        assert ids == ["a", "b"]

    def test_skips_duplicate_ids(self):
        base = [{"id": "a"}]
        merged = _merge_external_integration_entries(base, [{"id": "a"}, {"id": "c"}])
        ids = [e["id"] for e in merged]
        assert ids == ["a", "c"]

    def test_does_not_mutate_input_list(self):
        base = [{"id": "a"}]
        _merge_external_integration_entries(base, [{"id": "b"}])
        assert len(base) == 1


class TestSourcePathDedupeKey:
    def test_absolute_path_resolves(self, tmp_path: Path):
        f = tmp_path / "doc.md"
        f.write_text("x")
        key = _source_path_dedupe_key({"source_path": str(f)})
        assert key == str(f.resolve())

    def test_url_source_path_passes_through_as_string(self):
        # URLs aren't local paths -> _resolve_local_source_path returns None.
        key = _source_path_dedupe_key({"source_path": "https://example.com/x"})
        assert key == "https://example.com/x"

    def test_missing_source_path_returns_empty(self):
        assert _source_path_dedupe_key({}) == ""

    def test_two_spellings_of_same_file_share_key(self, tmp_path: Path):
        d = tmp_path / "sub"
        d.mkdir()
        f = d / "doc.md"
        f.write_text("x")
        direct = _source_path_dedupe_key({"source_path": str(f)})
        dotted = _source_path_dedupe_key({"source_path": str(d / "." / "doc.md")})
        assert direct == dotted


class TestFilterMissingInventoryEntries:
    def test_empty_input(self):
        filtered, missing = _filter_missing_inventory_entries([])
        assert filtered == []
        assert missing == 0

    def test_existing_kept_missing_counted(self, tmp_path: Path):
        present = tmp_path / "here.md"
        present.write_text("x")
        entries = [
            {"id": "present", "source_path": str(present)},
            {"id": "gone", "source_path": str(tmp_path / "ghost.md")},
        ]
        filtered, missing = _filter_missing_inventory_entries(entries)
        assert [e["id"] for e in filtered] == ["present"]
        assert missing == 1

    def test_entry_without_source_path_is_kept(self):
        # No resolvable path -> treated as "exists" (not a filesystem entry).
        filtered, missing = _filter_missing_inventory_entries([{"id": "virtual"}])
        assert [e["id"] for e in filtered] == ["virtual"]
        assert missing == 0


class TestMergeInventoryEntries:
    def test_empty_inventory_returns_original(self):
        base = [{"id": "a"}]
        merged, added = _merge_inventory_entries(base, [])
        assert merged == base
        assert added == 0

    def test_new_path_is_appended(self, tmp_path: Path):
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("x")
        b.write_text("y")
        base = [{"id": "a", "source_path": str(a)}]
        inv = [{"id": "b", "source_path": str(b)}]
        merged, added = _merge_inventory_entries(base, inv)
        assert added == 1
        assert {e["id"] for e in merged} == {"a", "b"}

    def test_matching_path_folds_metadata_instead_of_appending(self, tmp_path: Path):
        f = tmp_path / "shared.md"
        f.write_text("x")
        base = [{"id": "base", "source_path": str(f), "metadata": {}}]
        inv = [{"id": "inv", "source_path": str(f), "metadata": {"problem_duplicate": "1"}}]
        merged, added = _merge_inventory_entries(base, inv)
        assert added == 0
        assert len(merged) == 1
        # Inventory metadata folded into the existing entry.
        assert merged[0]["metadata"]["problem_duplicate"] == "1"


class TestMergeInventoryMetadata:
    def test_problem_metadata_and_tags_added(self):
        existing = {"metadata": {}, "tags": ["normal"]}
        inventory = {
            "metadata": {"problem_tags": "duplicate,stale_generated", "problem_duplicate": "yes"},
        }
        _merge_inventory_metadata(existing, inventory)
        assert existing["metadata"]["problem_duplicate"] == "yes"
        assert "duplicate" in existing["tags"]
        assert "stale_generated" in existing["tags"]
        assert "normal" in existing["tags"]

    def test_stale_problem_tags_replaced_with_fresh(self):
        # Existing carries a stale problem tag that the fresh inventory drops.
        existing = {
            "metadata": {"problem_tags": "permission_denied", "problem_old": "1"},
            "tags": ["permission_denied", "keepme"],
        }
        inventory = {"metadata": {"problem_tags": "duplicate"}}
        _merge_inventory_metadata(existing, inventory)
        # Stale AI-artifact problem tag removed, fresh one added, non-problem kept.
        assert "permission_denied" not in existing["tags"]
        assert "duplicate" in existing["tags"]
        assert "keepme" in existing["tags"]
        # Stale problem_* metadata keys are stripped.
        assert "problem_old" not in existing["metadata"]

    def test_inventory_source_propagated(self):
        existing = {"metadata": {}}
        inventory = {"metadata": {}, "inventory_source": "capability-scan"}
        _merge_inventory_metadata(existing, inventory)
        assert existing["metadata"]["inventory_source"] == "capability-scan"
        assert existing["inventory_source"] == "capability-scan"

    def test_handles_non_dict_existing_metadata(self):
        existing = {"metadata": None, "tags": "not-a-list"}
        inventory = {"metadata": {"problem_tags": "duplicate"}}
        _merge_inventory_metadata(existing, inventory)
        assert isinstance(existing["metadata"], dict)
        assert existing["tags"] == ["duplicate"]
