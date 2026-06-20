"""
Tests for server-level caching and metrics tracking (server_cache.py).

Validates SkillCache TTL behavior, MetricsTracker tool/error tracking,
session counting, and persistence resilience.

Run with: pytest tests/packages/augur-mcp/test_server_cache.py -v
"""

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.mcp.augur_shared.server_cache import MetricsTracker, SkillCache

# =============================================================================
# SkillCache Tests
# =============================================================================


class TestSkillCache:
    """Tests for in-memory TTL cache."""

    def test_set_and_get(self):
        """Basic set and get returns the stored value."""
        cache = SkillCache(ttl=300)
        cache.set("skill:careers", {"data": "test"})
        assert cache.get("skill:careers") == {"data": "test"}

    def test_get_missing_key_returns_none(self):
        """Getting a key that was never set returns None."""
        cache = SkillCache(ttl=300)
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self):
        """Expired entries are evicted and return None."""
        cache = SkillCache(ttl=1)
        cache.set("key", "value")
        assert cache.get("key") == "value"

        # Simulate TTL expiration by patching time
        with patch("src.mcp.augur_shared.server_cache.time.time", return_value=time.time() + 2):
            assert cache.get("key") is None

    def test_expired_entry_removed_from_cache(self):
        """Accessing an expired key removes it from internal storage."""
        cache = SkillCache(ttl=1)
        cache.set("key", "value")

        with patch("src.mcp.augur_shared.server_cache.time.time", return_value=time.time() + 2):
            cache.get("key")

        assert cache.stats()["entries"] == 0

    def test_invalidate_all(self):
        """Invalidate with no pattern clears all entries."""
        cache = SkillCache(ttl=300)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)

        cache.invalidate()
        assert cache.stats()["entries"] == 0

    def test_invalidate_with_pattern(self):
        """Invalidate with pattern clears only matching entries."""
        cache = SkillCache(ttl=300)
        cache.set("skill:careers", 1)
        cache.set("skill:dev", 2)
        cache.set("other:stuff", 3)

        cache.invalidate("skill:")
        assert cache.stats()["entries"] == 1
        assert cache.get("other:stuff") == 3

    def test_invalidate_pattern_no_matches(self):
        """Invalidate with non-matching pattern leaves cache untouched."""
        cache = SkillCache(ttl=300)
        cache.set("a", 1)
        cache.set("b", 2)

        cache.invalidate("xyz")
        assert cache.stats()["entries"] == 2

    def test_stats_reports_entries_and_keys(self):
        """Stats returns entry count and key list."""
        cache = SkillCache(ttl=300)
        cache.set("x", 1)
        cache.set("y", 2)

        stats = cache.stats()
        assert stats["entries"] == 2
        assert sorted(stats["keys"]) == ["x", "y"]

    def test_overwrite_existing_key(self):
        """Setting a key again overwrites the old value and resets TTL."""
        cache = SkillCache(ttl=300)
        cache.set("key", "old")
        cache.set("key", "new")
        assert cache.get("key") == "new"
        assert cache.stats()["entries"] == 1

    def test_different_value_types(self):
        """Cache supports various value types: str, dict, list, None."""
        cache = SkillCache(ttl=300)
        cache.set("str", "hello")
        cache.set("dict", {"a": 1})
        cache.set("list", [1, 2, 3])
        cache.set("none", None)

        assert cache.get("str") == "hello"
        assert cache.get("dict") == {"a": 1}
        assert cache.get("list") == [1, 2, 3]
        assert cache.get("none") is None  # Indistinguishable from miss by return value


# =============================================================================
# MetricsTracker Tests
# =============================================================================


class TestMetricsTracker:
    """Tests for tool usage metrics tracking."""

    @pytest.fixture
    def metrics_file(self, tmp_path: Path) -> Path:
        """Return a temporary metrics file path."""
        return tmp_path / "metrics" / "metrics.json"

    @pytest.fixture
    def tracker(self, metrics_file: Path) -> MetricsTracker:
        """Create a fresh MetricsTracker instance."""
        return MetricsTracker(metrics_file)

    def test_initial_state(self, tracker: MetricsTracker):
        """New tracker starts with empty counters."""
        stats = tracker.get_stats()
        assert stats["tool_calls"] == {}
        assert stats["skill_usage"] == {}
        assert stats["errors"] == []
        assert stats["sessions"] == 0
        assert "session_start" in stats

    def test_track_tool_increments_count(self, tracker: MetricsTracker):
        """track_tool increments the tool call counter."""
        tracker.track_tool("list_skills")
        tracker.track_tool("list_skills")
        tracker.track_tool("get_skill")

        stats = tracker.get_stats()
        assert stats["tool_calls"]["list_skills"] == 2
        assert stats["tool_calls"]["get_skill"] == 1

    def test_track_tool_with_skill(self, tracker: MetricsTracker):
        """track_tool with skill parameter tracks skill usage."""
        tracker.track_tool("get_skill", skill="careers")
        tracker.track_tool("get_skill", skill="careers")
        tracker.track_tool("get_skill", skill="developer")

        stats = tracker.get_stats()
        assert stats["skill_usage"]["careers"] == 2
        assert stats["skill_usage"]["developer"] == 1

    def test_track_tool_with_module(self, tracker: MetricsTracker):
        """track_tool with module parameter tracks module usage."""
        tracker.track_tool("load_module", skill="careers", module="sync")

        stats = tracker.get_stats()
        assert stats["module_usage"]["careers/sync"] == 1

    def test_track_tool_module_without_skill(self, tracker: MetricsTracker):
        """Module without skill uses just the module name as key."""
        tracker.track_tool("some_tool", module="utils")

        stats = tracker.get_stats()
        assert stats["module_usage"]["utils"] == 1

    def test_track_tool_with_chain_as_skill(self, tracker: MetricsTracker):
        """chain kwarg is used as skill if skill is not provided."""
        tracker.track_tool("run_chain", chain="onboarding")

        stats = tracker.get_stats()
        assert stats["skill_usage"]["onboarding"] == 1

    def test_track_error(self, tracker: MetricsTracker):
        """track_error appends error with timestamp and tool name."""
        with patch("src.mcp.augur_shared.server_cache.report_bug", None):
            tracker.track_error("get_skill", "Skill not found: xyz")

        stats = tracker.get_stats()
        assert len(stats["errors"]) == 1
        assert stats["errors"][0]["tool"] == "get_skill"
        assert stats["errors"][0]["error"] == "Skill not found: xyz"
        assert "timestamp" in stats["errors"][0]

    def test_track_error_truncates_long_messages(self, tracker: MetricsTracker):
        """Error messages are truncated to 200 chars."""
        long_error = "x" * 500
        with patch("src.mcp.augur_shared.server_cache.report_bug", None):
            tracker.track_error("test", long_error)

        stats = tracker.get_stats()
        assert len(stats["errors"][0]["error"]) == 200

    def test_track_error_keeps_last_100(self, tracker: MetricsTracker):
        """Only the last 100 errors are kept."""
        with patch("src.mcp.augur_shared.server_cache.report_bug", None):
            for i in range(110):
                tracker.track_error("tool", f"error-{i}")

        stats = tracker.get_stats()
        assert len(stats["errors"]) == 100
        # Oldest errors should be trimmed
        assert stats["errors"][0]["error"] == "error-10"

    def test_increment_sessions(self, tracker: MetricsTracker):
        """increment_sessions bumps the session counter."""
        tracker.increment_sessions()
        tracker.increment_sessions()

        stats = tracker.get_stats()
        assert stats["sessions"] == 2

    def test_get_stats_with_cache(self, tracker: MetricsTracker):
        """get_stats includes cache_stats when skill_cache is provided."""
        cache = SkillCache(ttl=300)
        cache.set("test", "value")

        stats = tracker.get_stats(skill_cache=cache)
        assert "cache_stats" in stats
        assert stats["cache_stats"]["entries"] == 1

    def test_persistence_roundtrip(self, metrics_file: Path):
        """Metrics survive re-creation of the tracker (loaded from disk)."""
        tracker1 = MetricsTracker(metrics_file)
        tracker1.track_tool("list_skills")
        tracker1.increment_sessions()

        # Create new tracker reading from same file
        tracker2 = MetricsTracker(metrics_file)
        stats = tracker2.get_stats()
        assert stats["tool_calls"]["list_skills"] == 1
        assert stats["sessions"] == 1

    def test_corrupted_metrics_file_handled(self, metrics_file: Path):
        """Corrupted metrics file is handled gracefully (starts fresh)."""
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        metrics_file.write_text("not valid json {{{")

        tracker = MetricsTracker(metrics_file)
        stats = tracker.get_stats()
        assert stats["tool_calls"] == {}
        assert stats["sessions"] == 0

    def test_save_failure_does_not_raise(self, tracker: MetricsTracker):
        """Metrics save failure is silently swallowed (never breaks tool calls)."""
        with patch.object(tracker, "_metrics_file", Path("/nonexistent/read-only/metrics.json")):
            # Should not raise even though path is invalid
            tracker.track_tool("test")
            tracker.increment_sessions()
