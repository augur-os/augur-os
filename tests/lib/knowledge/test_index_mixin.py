"""Unit tests for src.lib.knowledge._index.IndexMixin.

These exercise the index/staleness/parser logic of IndexMixin in true isolation
via a lightweight stub host, with all index files and fixtures under tmp_path.
They deliberately do NOT construct the full MemorySearcher (which depends on real
path helpers and sibling mixins) -- that integration surface is covered by the
skill-side tests in
project-brain/capabilities/skills/knowledge/augur/tests/test_search_hardening.py.

The focus here is on edge/error paths and parser correctness that those
integration tests do not assert: checksum error handling, every staleness
trigger (corrupt index, version mismatch, bad timestamp), force rebuild,
per-branch category detection, key/date extraction fallbacks, and tag capping.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml

from src.lib.knowledge._index import INDEX_VERSION, IndexMixin


class _StubHost(IndexMixin):
    """Minimal host satisfying the attributes IndexMixin documents it needs."""

    def __init__(self, base: Path, config: dict | None = None):
        self._memory_dir = base
        self._index_path = base / "index.yaml"
        self._daily_dir = base / "daily"
        self._memory_file = base / "MEMORY.md"
        self._config = config if config is not None else {}


@pytest.fixture
def host(tmp_path: Path) -> _StubHost:
    """A stub IndexMixin host with an empty daily dir under tmp_path."""
    (tmp_path / "daily").mkdir()
    return _StubHost(tmp_path)


# ---------------------------------------------------------------------------
# _compute_file_checksum
# ---------------------------------------------------------------------------


class TestComputeFileChecksum:
    def test_stable_and_prefixed(self, host: _StubHost, tmp_path: Path):
        f = tmp_path / "a.md"
        f.write_text("consistent content")
        cs1 = host._compute_file_checksum(f)
        cs2 = host._compute_file_checksum(f)
        assert cs1 == cs2
        assert cs1.startswith("sha256:")
        # 64 hex chars after the prefix
        assert len(cs1.split(":", 1)[1]) == 64

    def test_distinct_content_distinct_checksum(self, host: _StubHost, tmp_path: Path):
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("alpha")
        b.write_text("beta")
        assert host._compute_file_checksum(a) != host._compute_file_checksum(b)

    def test_missing_file_returns_error_sentinel(self, host: _StubHost, tmp_path: Path):
        """OSError (unreadable/nonexistent) is swallowed and returns the sentinel."""
        assert host._compute_file_checksum(tmp_path / "does-not-exist.md") == "sha256:error"

    def test_directory_path_returns_error_sentinel(self, host: _StubHost, tmp_path: Path):
        """Reading a directory raises OSError -> sentinel, not a crash."""
        assert host._compute_file_checksum(tmp_path / "daily") == "sha256:error"


# ---------------------------------------------------------------------------
# _get_source_files
# ---------------------------------------------------------------------------


class TestGetSourceFiles:
    def test_empty_when_nothing_exists(self, host: _StubHost):
        assert host._get_source_files() == []

    def test_daily_logs_sorted_then_memory_last(self, host: _StubHost):
        (host._daily_dir / "2026-01-16.md").write_text("b")
        (host._daily_dir / "2026-01-15.md").write_text("a")
        host._memory_file.write_text("## S\n- x\n")

        files = host._get_source_files()
        names = [f.name for f in files]
        # daily logs are globbed and sorted; MEMORY.md appended after.
        assert names == ["2026-01-15.md", "2026-01-16.md", "MEMORY.md"]

    def test_only_markdown_daily_files(self, host: _StubHost):
        (host._daily_dir / "2026-01-15.md").write_text("a")
        (host._daily_dir / "notes.txt").write_text("ignored")
        names = [f.name for f in host._get_source_files()]
        assert names == ["2026-01-15.md"]


# ---------------------------------------------------------------------------
# _is_index_stale
# ---------------------------------------------------------------------------


class TestIsIndexStale:
    def _seed(self, host: _StubHost) -> Path:
        daily = host._daily_dir / "2026-01-15.md"
        daily.write_text("## Test\nbody\n")
        host.build_index()
        return daily

    def test_missing_index_is_stale(self, host: _StubHost):
        assert host._is_index_stale() is True

    def test_fresh_index_not_stale(self, host: _StubHost):
        self._seed(host)
        assert host._is_index_stale() is False

    def test_corrupt_index_yaml_is_stale(self, host: _StubHost):
        self._seed(host)
        host._index_path.write_text("{: not valid yaml ::")
        assert host._is_index_stale() is True

    def test_version_mismatch_is_stale(self, host: _StubHost):
        self._seed(host)
        index = yaml.safe_load(host._index_path.read_text())
        index["version"] = "1.0"
        host._index_path.write_text(yaml.dump(index))
        assert host._is_index_stale() is True

    def test_new_file_is_stale(self, host: _StubHost):
        self._seed(host)
        assert host._is_index_stale() is False
        (host._daily_dir / "2026-01-16.md").write_text("## New\nmore\n")
        assert host._is_index_stale() is True

    def test_deleted_file_is_stale(self, host: _StubHost):
        daily = self._seed(host)
        daily.unlink()
        assert host._is_index_stale() is True

    def test_modified_file_is_stale(self, host: _StubHost):
        daily = self._seed(host)
        daily.write_text("## Test\nDIFFERENT body\n")
        assert host._is_index_stale() is True

    def test_old_index_exceeding_auto_rebuild_hours_is_stale(self, host: _StubHost):
        self._seed(host)
        index = yaml.safe_load(host._index_path.read_text())
        index["updated"] = (datetime.now() - timedelta(hours=25)).isoformat()
        host._index_path.write_text(yaml.dump(index))
        assert host._is_index_stale() is True

    def test_recent_index_within_threshold_not_stale(self, host: _StubHost):
        self._seed(host)
        index = yaml.safe_load(host._index_path.read_text())
        index["updated"] = (datetime.now() - timedelta(hours=1)).isoformat()
        host._index_path.write_text(yaml.dump(index))
        assert host._is_index_stale() is False

    def test_custom_auto_rebuild_hours_honored(self, tmp_path: Path):
        (tmp_path / "daily").mkdir()
        h = _StubHost(tmp_path, config={"indexing": {"auto_rebuild_hours": 1}})
        (h._daily_dir / "2026-01-15.md").write_text("## Test\nbody\n")
        h.build_index()
        index = yaml.safe_load(h._index_path.read_text())
        index["updated"] = (datetime.now() - timedelta(hours=2)).isoformat()
        h._index_path.write_text(yaml.dump(index))
        assert h._is_index_stale() is True

    def test_unparseable_updated_timestamp_is_stale(self, host: _StubHost):
        self._seed(host)
        index = yaml.safe_load(host._index_path.read_text())
        index["updated"] = "not-a-real-timestamp"
        host._index_path.write_text(yaml.dump(index))
        assert host._is_index_stale() is True


# ---------------------------------------------------------------------------
# build_index
# ---------------------------------------------------------------------------


class TestBuildIndex:
    def test_writes_v2_index_with_checksums(self, host: _StubHost):
        daily = host._daily_dir / "2026-01-15.md"
        daily.write_text("## 10:00 - Decision\n**Topic**: Test\n")
        count = host.build_index()

        assert count == 1
        index = yaml.safe_load(host._index_path.read_text())
        assert index["version"] == INDEX_VERSION
        assert index["entry_count"] == 1
        assert str(daily) in index["file_checksums"]
        assert index["file_checksums"][str(daily)].startswith("sha256:")
        # updated is an ISO timestamp we can round-trip.
        datetime.fromisoformat(index["updated"])

    def test_indexes_both_daily_and_memory(self, host: _StubHost):
        (host._daily_dir / "2026-01-15.md").write_text("## 10:00 - Event\nbody\n")
        host._memory_file.write_text("## Insights\n- something useful\n")
        count = host.build_index()

        assert count == 2
        index = yaml.safe_load(host._index_path.read_text())
        sources = {e["source"] for e in index["entries"]}
        assert sources == {"daily", "curated"}

    def test_empty_corpus_writes_zero_entry_index(self, host: _StubHost):
        count = host.build_index()
        assert count == 0
        index = yaml.safe_load(host._index_path.read_text())
        assert index["entry_count"] == 0
        assert index["entries"] == []
        assert index["file_checksums"] == {}

    def test_incremental_reuses_unchanged_entries(self, host: _StubHost):
        daily = host._daily_dir / "2026-01-15.md"
        daily.write_text("## 10:00 - Decision\n**Topic**: Test\n")
        first = host.build_index()
        idx1 = yaml.safe_load(host._index_path.read_text())

        # No change -> same count, same checksum.
        second = host.build_index()
        idx2 = yaml.safe_load(host._index_path.read_text())

        assert first == second
        assert idx1["file_checksums"] == idx2["file_checksums"]

    def test_incremental_only_reparses_changed_file(self, host: _StubHost):
        d1 = host._daily_dir / "2026-01-15.md"
        d2 = host._daily_dir / "2026-01-16.md"
        d1.write_text("## 10:00 - Decision\n**Topic**: Unchanged\n")
        d2.write_text("## 11:00 - Decision\n**Topic**: Original\n")
        host.build_index()
        idx1 = yaml.safe_load(host._index_path.read_text())

        d2.write_text("## 11:00 - Decision\n**Topic**: Modified\n")
        host.build_index()
        idx2 = yaml.safe_load(host._index_path.read_text())

        assert idx2["file_checksums"][str(d1)] == idx1["file_checksums"][str(d1)]
        assert idx2["file_checksums"][str(d2)] != idx1["file_checksums"][str(d2)]

    def test_force_rebuild_ignores_incremental(self, host: _StubHost):
        host._config = {"indexing": {"incremental": True}}
        daily = host._daily_dir / "2026-01-15.md"
        daily.write_text("## 10:00 - Decision\n**Topic**: Test\n")
        host.build_index()
        # force=True must still produce a valid full index of the same content.
        count = host.build_index(force=True)
        assert count == 1
        index = yaml.safe_load(host._index_path.read_text())
        assert index["version"] == INDEX_VERSION

    def test_incremental_disabled_full_rebuild(self, tmp_path: Path):
        (tmp_path / "daily").mkdir()
        h = _StubHost(tmp_path, config={"indexing": {"incremental": False}})
        (h._daily_dir / "2026-01-15.md").write_text("## 10:00 - Decision\n**Topic**: Test\n")
        assert h.build_index() == 1
        assert h.build_index() == 1  # rebuild still yields the same entries

    def test_corrupt_existing_index_falls_back_to_full_build(self, host: _StubHost):
        host._index_path.write_text("{: broken yaml ::")
        daily = host._daily_dir / "2026-01-15.md"
        daily.write_text("## 10:00 - Decision\n**Topic**: Recovered\n")
        # Must not raise; rebuilds from scratch.
        count = host.build_index()
        assert count == 1
        index = yaml.safe_load(host._index_path.read_text())
        assert index["version"] == INDEX_VERSION


# ---------------------------------------------------------------------------
# _parse_daily_log
# ---------------------------------------------------------------------------


class TestParseDailyLog:
    def test_category_detection_per_keyword(self, host: _StubHost):
        content = (
            "## 09:00 - Decision made\nd\n"
            "## 10:00 - Preference noted\np\n"
            "## 11:00 - Pattern observed\npa\n"
            "## 12:00 - Context switch happened\ncs\n"
            "## 13:00 - Tool run\nt\n"
            "## 14:00 - Error occurred\ne\n"
            "## 15:00 - Random heading\nr\n"
        )
        entries = host._parse_daily_log(content, "2026-01-15", "/d.md")
        cats = [e.category for e in entries]
        assert cats == [
            "decision",
            "preference",
            "pattern",
            "context_switch",
            "tool_execution",
            "error",
            "event",
        ]

    def test_key_extracted_after_dash(self, host: _StubHost):
        content = "## 09:00 - My event key\nbody\n"
        entries = host._parse_daily_log(content, "2026-01-15", "/d.md")
        assert len(entries) == 1
        assert entries[0].key == "My event key"
        assert entries[0].source == "daily"
        assert entries[0].date == "2026-01-15"
        assert entries[0].file_path == "/d.md"

    def test_key_falls_back_to_full_header_without_dash(self, host: _StubHost):
        content = "## Heading no dash\nbody\n"
        entries = host._parse_daily_log(content, "2026-01-15", "/d.md")
        assert len(entries) == 1
        # No "- " in the header -> the whole header line (with markers) is the key.
        assert entries[0].key == "## Heading no dash"

    def test_line_number_points_at_header(self, host: _StubHost):
        content = "## First\na\n## Second\nb\n"
        entries = host._parse_daily_log(content, "2026-01-15", "/d.md")
        assert [e.line_number for e in entries] == [1, 3]

    def test_last_event_is_flushed(self, host: _StubHost):
        """The final event (no trailing header) must still be captured."""
        content = "## Only event\nbody line\nmore body\n"
        entries = host._parse_daily_log(content, "2026-01-15", "/d.md")
        assert len(entries) == 1
        assert "body line" in entries[0].content
        assert "more body" in entries[0].content

    def test_blank_lines_skipped_in_body(self, host: _StubHost):
        content = "## Event\nfirst\n\n\nsecond\n"
        entries = host._parse_daily_log(content, "2026-01-15", "/d.md")
        assert entries[0].content == "## Event\nfirst\nsecond"

    def test_content_without_header_yields_nothing(self, host: _StubHost):
        entries = host._parse_daily_log("just\nsome\nlines\n", "2026-01-15", "/d.md")
        assert entries == []


# ---------------------------------------------------------------------------
# _parse_memory_md
# ---------------------------------------------------------------------------


class TestParseMemoryMd:
    def test_category_from_section(self, host: _StubHost):
        md = "## Decisions\n- a\n" "## Patterns\n- b\n" "## Preferences\n- c\n" "## Misc\n- d\n"
        entries = host._parse_memory_md(md, "/m.md")
        assert [e.category for e in entries] == [
            "decision",
            "pattern",
            "preference",
            "insight",
        ]

    def test_bold_key_and_date_extracted(self, host: _StubHost):
        md = "## Decisions\n### Routing\n- **Use mixin** for index (2026-01-15)\n"
        entries = host._parse_memory_md(md, "/m.md")
        assert len(entries) == 1
        e = entries[0]
        assert e.key == "Use mixin"
        assert e.date == "2026-01-15"
        assert e.content.startswith("Routing: ")
        assert e.line_number == 3

    def test_key_falls_back_to_subsection_without_bold(self, host: _StubHost):
        md = "## Insights\n### Routing\n- a plain bullet no bold\n"
        entries = host._parse_memory_md(md, "/m.md")
        assert entries[0].key == "Routing"
        assert entries[0].date == ""

    def test_subsection_tag_always_appended(self, host: _StubHost):
        md = "## Insights\n### Health\n- some bullet about Sleep\n"
        entries = host._parse_memory_md(md, "/m.md")
        # The subsection lowercased is always appended to the tag list.
        assert "health" in entries[0].tags

    def test_non_bullet_lines_ignored(self, host: _StubHost):
        md = "## Insights\nplain paragraph\n### Sub\nanother paragraph\n"
        assert host._parse_memory_md(md, "/m.md") == []


# ---------------------------------------------------------------------------
# _extract_tags
# ---------------------------------------------------------------------------


class TestExtractTags:
    def test_capitalized_words_capped_at_five(self, host: _StubHost):
        tags = host._extract_tags("Alpha Beta Gamma Delta Epsilon Zeta Eta")
        # Only the first five capitalized words are taken, lowercased.
        assert set(tags) == {"alpha", "beta", "gamma", "delta", "epsilon"}

    def test_quoted_strings_capped_at_three(self, host: _StubHost):
        tags = host._extract_tags('"one" "two" "three" "four"')
        assert "four" not in tags
        assert {"one", "two", "three"}.issubset(set(tags))

    def test_results_are_deduplicated(self, host: _StubHost):
        tags = host._extract_tags("Health Health Health")
        assert tags.count("health") == 1

    def test_lowercase_words_not_captured(self, host: _StubHost):
        # Words that aren't Capitalized-then-lowercase and aren't quoted are ignored.
        assert host._extract_tags("all lowercase words here no quotes") == []
