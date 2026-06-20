"""Tests for memory_sync.py utility functions.

Tests: noise filtering, dedup normalization, entry parsing.
Legacy pipeline tests (archive_expired_entries, merge_native_entries,
update_memory_file) removed — that code now lives in the assembler.
"""

import sys
from datetime import datetime
from pathlib import Path

# Add scripts dir to path so we can import memory_sync
SCRIPTS_DIR = Path(__file__).parent.parent.parent / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import memory_sync

# ---------------------------------------------------------------------------
# normalize_entry
# ---------------------------------------------------------------------------


class TestNormalizeEntry:
    def test_strips_commit_hash_and_file_count(self):
        text = "fix(dashboard): remove stale routes (29273cf4, 22 files)"
        assert memory_sync.normalize_entry(text) == "fix(dashboard): remove stale routes"

    def test_strips_hash_with_single_file(self):
        text = "docs(adr): mark ADR-155 as Implemented (a3f1f3e3, 1 file)"
        assert memory_sync.normalize_entry(text) == "docs(adr): mark ADR-155 as Implemented"

    def test_collapses_whitespace(self):
        text = "fix(auth):   secure  cookie   flag"
        assert memory_sync.normalize_entry(text) == "fix(auth): secure cookie flag"

    def test_preserves_normal_text(self):
        text = "Architectural insight about X"
        assert memory_sync.normalize_entry(text) == "Architectural insight about X"


# ---------------------------------------------------------------------------
# _is_noise
# ---------------------------------------------------------------------------


class TestIsNoise:
    def test_chore_sync_regenerate(self):
        assert memory_sync._is_noise("chore(sync): regenerate IDE configs after ADR-159") is True

    def test_chore_sync_update_generated(self):
        assert memory_sync._is_noise("chore(sync): update generated timestamps") is True

    def test_chore_sync_case_insensitive(self):
        assert memory_sync._is_noise("Chore(sync): Regenerate IDE configs") is True

    def test_non_noise(self):
        assert memory_sync._is_noise("feat(adr-162): Focus Strip ambient context") is False

    def test_fix_is_not_noise(self):
        assert memory_sync._is_noise("fix(dashboard): remove stale routes") is False

    def test_session_checkpoint_is_noise(self):
        assert (
            memory_sync._is_noise("Session checkpoint created at ~70% context — completed full 3-stage pipeline")
            is True
        )

    def test_commit_only_is_noise(self):
        assert memory_sync._is_noise("fix(dashboard): remove stale routes (29273cf4, 22 files)") is True

    def test_commit_only_single_file(self):
        assert memory_sync._is_noise("docs(adr): mark ADR-155 as Implemented (a3f1f3e3, 1 file)") is True

    def test_commit_only_no_scope(self):
        assert memory_sync._is_noise("feat: refactor consulting hub routing (3f7227a4, 58 files)") is True

    def test_commit_only_chore_no_scope(self):
        assert memory_sync._is_noise("chore: sync generated files and update daily memory (53007037, 6 files)") is True

    def test_commit_with_insight_is_not_noise(self):
        assert (
            memory_sync._is_noise(
                "fix(audit): dashboard hardening audit must scan all skills in a bundle, not just the hub owner"
            )
            is False
        )

    def test_feat_with_description_is_not_noise(self):
        assert memory_sync._is_noise("feat(adr-162): Focus Strip ambient context, enriched focus state") is False

    def test_architectural_insight_is_not_noise(self):
        assert memory_sync._is_noise("Plugin decentralization established as Critical Rule #1") is False


# ---------------------------------------------------------------------------
# _classify_entry
# ---------------------------------------------------------------------------


class TestClassifyEntry:
    def test_chore(self):
        assert memory_sync._classify_entry("chore(cleanup): remove legacy files") == "chore"

    def test_fix(self):
        assert memory_sync._classify_entry("fix(auth): secure cookie") == "fix"

    def test_feat(self):
        assert memory_sync._classify_entry("feat(adr-162): Focus Strip") == "feat"

    def test_docs(self):
        assert memory_sync._classify_entry("docs(adr): add ADR-160") == "docs"

    def test_architectural_insight(self):
        assert memory_sync._classify_entry("Plugin decentralization is the #1 principle") is None

    def test_session_checkpoint(self):
        assert memory_sync._classify_entry("Session checkpoint created at ~70% context") is None


# ---------------------------------------------------------------------------
# _parse_entry_date / _entry_text
# ---------------------------------------------------------------------------


class TestEntryParsing:
    def test_parse_date(self):
        d = memory_sync._parse_entry_date("- [2026-02-25] fix(auth): something")
        assert d == datetime(2026, 2, 25)

    def test_parse_date_none(self):
        assert memory_sync._parse_entry_date("Not a dated entry") is None

    def test_entry_text(self):
        text = memory_sync._entry_text("- [2026-02-25] fix(auth): something")
        assert text == "fix(auth): something"


# ---------------------------------------------------------------------------
# _extract_entry_lines
# ---------------------------------------------------------------------------


class TestExtractEntryLines:
    def test_extracts_entries(self):
        content = "# Header\n\n- [2026-02-25] entry one\nsome text\n- [2026-02-26] entry two\n"
        lines = memory_sync._extract_entry_lines(content)
        assert len(lines) == 2
        assert "entry one" in lines[0]
        assert "entry two" in lines[1]


# ---------------------------------------------------------------------------
# _is_curated_index
# ---------------------------------------------------------------------------


class TestIsCuratedIndex:
    def test_curated_format_detected(self):
        content = "# Memory\n\n- [verify-page-wiring](feedback_verify_page_wiring.md) -- Always verify\n"
        assert memory_sync._is_curated_index(content) is True

    def test_flat_format_not_curated(self):
        content = "# Memory\n\n- [2026-02-25] fix(auth): something\n"
        assert memory_sync._is_curated_index(content) is False
