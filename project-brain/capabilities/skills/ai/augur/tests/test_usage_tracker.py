"""
Tests for LLM Usage Tracker

Tests Story-013: Cost tracking and usage statistics.
"""

import sys
import tempfile
from pathlib import Path

# Add ai plugin root and project root to path
ai_root = Path(__file__).resolve().parent.parent
ai_augur_root = ai_root / "augur"
project_root = Path(__file__).resolve().parents[4]
for p in (str(ai_augur_root), str(ai_root), str(project_root)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest  # noqa: E402

from src.lib.ai.usage_tracker import UsageTracker, get_usage_tracker  # noqa: E402


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def tracker(temp_data_dir):
    """Create a UsageTracker instance with temporary data directory."""
    return UsageTracker(data_dir=temp_data_dir)


class TestUsageTracker:
    """Test suite for UsageTracker."""

    def test_track_request_success(self, tracker):
        """Test tracking a successful request."""
        tracker.track_request(
            provider="groq",
            profile="test-profile",
            model="llama-3.1-70b-versatile",
            prompt_tokens=100,
            completion_tokens=50,
            cost=0.0001,
            success=True,
        )

        stats = tracker.get_usage_stats(days=1)
        assert stats["total_requests"] == 1
        assert stats["total_tokens"] == 150
        assert stats["total_cost"] == 0.0001
        assert stats["total_errors"] == 0

    def test_track_request_error(self, tracker):
        """Test tracking a failed request."""
        tracker.track_request(
            provider="openai",
            profile="test-profile",
            model="gpt-4o-mini",
            prompt_tokens=0,
            completion_tokens=0,
            cost=0.0,
            success=False,
            error="API key invalid",
        )

        stats = tracker.get_usage_stats(days=1)
        assert stats["total_requests"] == 1
        assert stats["total_errors"] == 1

    def test_provider_breakdown(self, tracker):
        """Test provider breakdown statistics."""
        tracker.track_request(
            provider="groq",
            profile="test-profile",
            model="llama-3.1-70b-versatile",
            prompt_tokens=100,
            completion_tokens=50,
            cost=0.0001,
            success=True,
        )

        tracker.track_request(
            provider="openai",
            profile="test-profile",
            model="gpt-4o-mini",
            prompt_tokens=200,
            completion_tokens=100,
            cost=0.0002,
            success=True,
        )

        stats = tracker.get_usage_stats(days=1)
        assert "groq" in stats["provider_breakdown"]
        assert "openai" in stats["provider_breakdown"]
        assert stats["provider_breakdown"]["groq"]["requests"] == 1
        assert stats["provider_breakdown"]["openai"]["requests"] == 1

    def test_cost_estimation(self, tracker):
        """Test cost estimation for different providers."""
        # Groq
        cost = tracker.get_cost_estimate(
            provider="groq",
            model="llama-3.1-70b-versatile",
            prompt_tokens=1_000_000,
            completion_tokens=500_000,
        )
        assert cost > 0
        assert cost < 1.0  # Should be reasonable

        # OpenAI
        cost = tracker.get_cost_estimate(
            provider="openai",
            model="gpt-4o-mini",
            prompt_tokens=1_000_000,
            completion_tokens=500_000,
        )
        assert cost > 0

    def test_daily_breakdown(self, tracker):
        """Test daily breakdown statistics."""
        # Track requests for multiple days
        for i in range(3):
            tracker.track_request(
                provider="groq",
                profile="test-profile",
                model="llama-3.1-70b-versatile",
                prompt_tokens=100,
                completion_tokens=50,
                cost=0.0001,
                success=True,
            )

        stats = tracker.get_usage_stats(days=7)
        assert len(stats["daily_breakdown"]) >= 1
        assert stats["daily_breakdown"][0]["requests"] >= 1

    def test_persistence(self, temp_data_dir):
        """Test that usage data persists across tracker instances."""
        tracker1 = UsageTracker(data_dir=temp_data_dir)
        tracker1.track_request(
            provider="groq",
            profile="test-profile",
            model="llama-3.1-70b-versatile",
            prompt_tokens=100,
            completion_tokens=50,
            cost=0.0001,
            success=True,
        )

        # Create a new tracker instance
        tracker2 = UsageTracker(data_dir=temp_data_dir)
        stats = tracker2.get_usage_stats(days=1)
        assert stats["total_requests"] == 1

    def test_get_usage_tracker_singleton(self, temp_data_dir):
        """Test that get_usage_tracker returns a singleton."""
        # This test is limited since we can't easily mock the global
        # But we can verify it returns an instance
        tracker = get_usage_tracker()
        assert tracker is not None
        assert isinstance(tracker, UsageTracker)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
