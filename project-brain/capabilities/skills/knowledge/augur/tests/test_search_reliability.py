"""
Tests for memory search reliability: circuit breaker, LLM retry, error classification.

Covers edge cases found across 16 self-heal fix commits:
- Circuit breaker trips after N consecutive failures
- Circuit breaker resets after cooldown or on success
- max_retries=0 raises RuntimeError (not a crash)
- max_retries=1 single attempt with no retry
- Retryable vs non-retryable error classification
- HTTP status code extraction (429 retryable, 401/403 non-retryable)
- Graceful fallback when LLM is completely unavailable
- _rank_results with invalid/out-of-bounds indices from LLM
- _evaluate_results with empty results shortcircuits (no LLM call)
- _iterative_search fallback when circuit breaker is open
"""
# TODO_CLEANUP: This file is 810 lines — consider splitting into smaller modules

import time
from unittest.mock import MagicMock, patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temporary data directory structure for memory tests."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True)
    daily_dir = memory_dir / "daily"
    daily_dir.mkdir()
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(parents=True)
    config = {
        "version": "1.0",
        "core": {"markdown_indexing": True, "ripgrep_search": True},
        "indexing": {"incremental": True, "auto_rebuild_hours": 24},
        "advanced": {
            "vector_search": {"enabled": False},
            "iterative_search": {
                "enabled": True,
                "max_rounds": 3,
                "fallback_to_static": True,
            },
        },
    }
    (knowledge_dir / "config.yaml").write_text(yaml.dump(config))
    return tmp_path


@pytest.fixture
def mock_data_base(tmp_data_dir):
    """Patch get_memory_dir in all knowledge submodules."""
    memory_dir = tmp_data_dir / "memory"
    targets = [
        "src.lib.knowledge.memory_store.get_memory_dir",
        "src.lib.knowledge.search.get_memory_dir",
        "src.lib.knowledge.curator.get_memory_dir",
        "src.lib.knowledge.daily_logger.get_memory_dir",
        "src.lib.knowledge.unified_search.get_memory_dir",
    ]
    patches = [patch(t, return_value=memory_dir) for t in targets]
    for p in patches:
        p.start()
    yield memory_dir
    for p in patches:
        p.stop()


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """Reset the class-level circuit breaker state before each test."""
    from src.lib.knowledge.search import MemorySearcher

    MemorySearcher._cb_failure_count = 0
    MemorySearcher._cb_open_since = None
    yield
    MemorySearcher._cb_failure_count = 0
    MemorySearcher._cb_open_since = None


# ===========================================================================
# Circuit Breaker Tests
# ===========================================================================


class TestCircuitBreaker:
    """Test circuit breaker behavior for sustained LLM API outages."""

    def test_circuit_breaker_closed_by_default(self, mock_data_base):
        """Circuit breaker starts in closed state (LLM calls allowed)."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        assert not searcher._circuit_breaker_is_open()
        assert searcher._cb_failure_count == 0
        assert searcher._cb_open_since is None

    def test_circuit_breaker_stays_closed_below_threshold(self, mock_data_base):
        """Fewer failures than threshold keep the circuit closed."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        # Record failures below threshold (default: 3)
        searcher._circuit_breaker_record_failure()
        searcher._circuit_breaker_record_failure()
        assert MemorySearcher._cb_failure_count == 2
        assert not searcher._circuit_breaker_is_open()

    def test_circuit_breaker_opens_at_threshold(self, mock_data_base):
        """Circuit breaker opens after exactly _CIRCUIT_BREAKER_THRESHOLD failures."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        threshold = MemorySearcher._CIRCUIT_BREAKER_THRESHOLD

        for _ in range(threshold):
            searcher._circuit_breaker_record_failure()

        assert MemorySearcher._cb_failure_count == threshold
        assert searcher._circuit_breaker_is_open()
        assert MemorySearcher._cb_open_since is not None

    def test_circuit_breaker_resets_on_success(self, mock_data_base):
        """A successful LLM call resets the circuit breaker to closed."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        # Accumulate some failures
        searcher._circuit_breaker_record_failure()
        searcher._circuit_breaker_record_failure()
        assert MemorySearcher._cb_failure_count == 2

        # Success resets
        searcher._circuit_breaker_record_success()
        assert MemorySearcher._cb_failure_count == 0
        assert MemorySearcher._cb_open_since is None
        assert not searcher._circuit_breaker_is_open()

    def test_circuit_breaker_resets_after_cooldown(self, mock_data_base):
        """Circuit breaker resets to closed after cooldown period expires."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        threshold = MemorySearcher._CIRCUIT_BREAKER_THRESHOLD

        # Trip the breaker
        for _ in range(threshold):
            searcher._circuit_breaker_record_failure()
        assert searcher._circuit_breaker_is_open()

        # Simulate cooldown expiry by backdating _cb_open_since
        MemorySearcher._cb_open_since = (
            time.monotonic() - MemorySearcher._CIRCUIT_BREAKER_COOLDOWN - 1
        )

        # Should now be closed (allows probe call)
        assert not searcher._circuit_breaker_is_open()
        assert MemorySearcher._cb_failure_count == 0
        assert MemorySearcher._cb_open_since is None

    def test_circuit_breaker_shared_across_instances(self, mock_data_base):
        """Circuit breaker state is class-level, shared across MemorySearcher instances."""
        from src.lib.knowledge.search import MemorySearcher

        s1 = MemorySearcher()
        s2 = MemorySearcher()

        s1._circuit_breaker_record_failure()
        assert MemorySearcher._cb_failure_count == 1
        assert s2._cb_failure_count == 1  # Shared state

        s2._circuit_breaker_record_failure()
        s2._circuit_breaker_record_failure()
        assert s1._circuit_breaker_is_open()  # s1 sees s2's failures

    def test_circuit_breaker_blocks_call_llm_with_retry(self, mock_data_base):
        """_call_llm_with_retry raises RuntimeError when circuit is open."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        # Trip the breaker
        for _ in range(MemorySearcher._CIRCUIT_BREAKER_THRESHOLD):
            searcher._circuit_breaker_record_failure()

        mock_client = MagicMock()

        with pytest.raises(RuntimeError, match="circuit breaker is open"):
            searcher._call_llm_with_retry(mock_client, "sys", "prompt")

        # Client should never be called
        mock_client.generate_json.assert_not_called()

    def test_circuit_breaker_opens_after_retries_exhausted(self, mock_data_base):
        """When all retries fail with transient errors, circuit breaker records the failure."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        mock_client = MagicMock()
        mock_client.generate_json.side_effect = RuntimeError("Connection timeout")

        with patch("src.lib.knowledge._iterative.time.sleep"):
            # Run _call_llm_with_retry N times until circuit trips
            for _ in range(MemorySearcher._CIRCUIT_BREAKER_THRESHOLD):
                with pytest.raises(RuntimeError, match="Connection timeout"):
                    searcher._call_llm_with_retry(mock_client, "sys", "prompt", max_retries=1)

        assert searcher._circuit_breaker_is_open()


# ===========================================================================
# LLM Retry Logic Tests
# ===========================================================================


class TestLLMRetryLogic:
    """Test _call_llm_with_retry edge cases."""

    def test_max_retries_zero_raises_immediately(self, mock_data_base):
        """max_retries=0 raises RuntimeError without calling the client."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        mock_client = MagicMock()

        with pytest.raises(RuntimeError, match="max_retries=0"):
            searcher._call_llm_with_retry(mock_client, "sys", "prompt", max_retries=0)

        mock_client.generate_json.assert_not_called()

    def test_max_retries_negative_raises_immediately(self, mock_data_base):
        """Negative max_retries raises RuntimeError."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        mock_client = MagicMock()

        with pytest.raises(RuntimeError, match="max_retries=0"):
            searcher._call_llm_with_retry(mock_client, "sys", "prompt", max_retries=-1)

        mock_client.generate_json.assert_not_called()

    def test_max_retries_one_single_attempt(self, mock_data_base):
        """max_retries=1 makes exactly one attempt with no retry."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        mock_client = MagicMock()
        mock_client.generate_json.side_effect = RuntimeError("Server error 500")

        with patch("src.lib.knowledge._iterative.time.sleep") as mock_sleep:
            with pytest.raises(RuntimeError, match="Server error 500"):
                searcher._call_llm_with_retry(mock_client, "sys", "prompt", max_retries=1)

        assert mock_client.generate_json.call_count == 1
        mock_sleep.assert_not_called()  # No backoff for single attempt

    def test_retries_exhaust_all_attempts(self, mock_data_base):
        """All max_retries attempts are made before raising."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        mock_client = MagicMock()
        mock_client.generate_json.side_effect = RuntimeError("timeout")

        with patch("src.lib.knowledge._iterative.time.sleep"):
            with pytest.raises(RuntimeError, match="timeout"):
                searcher._call_llm_with_retry(mock_client, "sys", "prompt", max_retries=3)

        assert mock_client.generate_json.call_count == 3

    def test_success_on_second_attempt(self, mock_data_base):
        """Recovery on second attempt returns the successful result."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        mock_client = MagicMock()
        mock_client.generate_json.side_effect = [
            RuntimeError("transient 500"),
            {"sufficient": True, "refined_query": "", "reasoning": "OK"},
        ]

        with patch("src.lib.knowledge._iterative.time.sleep"):
            result = searcher._call_llm_with_retry(mock_client, "sys", "prompt", max_retries=3)

        assert result["sufficient"] is True
        assert mock_client.generate_json.call_count == 2

    def test_non_retryable_error_stops_immediately(self, mock_data_base):
        """Non-retryable errors (auth, quota) stop retries immediately."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        mock_client = MagicMock()
        mock_client.generate_json.side_effect = RuntimeError("authentication error: invalid_api_key")

        with pytest.raises(RuntimeError, match="invalid_api_key"):
            searcher._call_llm_with_retry(mock_client, "sys", "prompt", max_retries=5)

        # Should stop after first attempt (non-retryable)
        assert mock_client.generate_json.call_count == 1

    def test_exponential_backoff_timing(self, mock_data_base):
        """Backoff increases exponentially: 2, 4, 8, 16, capped at 30."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        mock_client = MagicMock()
        mock_client.generate_json.side_effect = RuntimeError("transient")

        sleep_calls = []

        with patch(
            "src.lib.knowledge._iterative.time.sleep",
            side_effect=lambda s: sleep_calls.append(s),
        ):
            with pytest.raises(RuntimeError):
                searcher._call_llm_with_retry(mock_client, "sys", "prompt", max_retries=5)

        # 4 sleeps between 5 attempts (no sleep after last)
        assert len(sleep_calls) == 4
        assert sleep_calls[0] == 2
        assert sleep_calls[1] == 4
        assert sleep_calls[2] == 8
        assert sleep_calls[3] == 16

    def test_backoff_cap_at_30_seconds(self, mock_data_base):
        """Backoff is capped at 30 seconds for high retry counts."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        mock_client = MagicMock()
        mock_client.generate_json.side_effect = RuntimeError("transient")

        sleep_calls = []

        with patch(
            "src.lib.knowledge._iterative.time.sleep",
            side_effect=lambda s: sleep_calls.append(s),
        ):
            with pytest.raises(RuntimeError):
                searcher._call_llm_with_retry(mock_client, "sys", "prompt", max_retries=7)

        # 2, 4, 8, 16, 30, 30
        assert all(s <= 30 for s in sleep_calls)
        assert sleep_calls[-1] == 30

    def test_success_resets_circuit_breaker(self, mock_data_base):
        """Successful LLM call inside retry resets the circuit breaker."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        # Simulate some prior failures
        MemorySearcher._cb_failure_count = 2

        mock_client = MagicMock()
        mock_client.generate_json.return_value = {"result": "ok"}

        result = searcher._call_llm_with_retry(mock_client, "sys", "prompt")
        assert result == {"result": "ok"}
        assert MemorySearcher._cb_failure_count == 0


# ===========================================================================
# Error Classification Tests
# ===========================================================================


class TestErrorClassification:
    """Test _is_non_retryable_error for various error patterns."""

    def test_authentication_errors_non_retryable(self, mock_data_base):
        """Auth-related keywords are classified as non-retryable."""
        from src.lib.knowledge.search import MemorySearcher

        assert MemorySearcher._is_non_retryable_error(
            RuntimeError("authentication failed")
        )
        assert MemorySearcher._is_non_retryable_error(
            RuntimeError("unauthorized request")
        )
        assert MemorySearcher._is_non_retryable_error(
            RuntimeError("forbidden: access denied")
        )
        assert MemorySearcher._is_non_retryable_error(
            RuntimeError("invalid_api_key provided")
        )

    def test_quota_errors_non_retryable(self, mock_data_base):
        """Quota/billing errors are classified as non-retryable."""
        from src.lib.knowledge.search import MemorySearcher

        assert MemorySearcher._is_non_retryable_error(
            RuntimeError("quota exceeded for this billing period")
        )

    def test_config_errors_non_retryable(self, mock_data_base):
        """Configuration errors are classified as non-retryable."""
        from src.lib.knowledge.search import MemorySearcher

        assert MemorySearcher._is_non_retryable_error(
            RuntimeError("missing model configuration")
        )
        assert MemorySearcher._is_non_retryable_error(
            RuntimeError("empty command received")
        )

    def test_http_4xx_non_retryable(self, mock_data_base):
        """HTTP 4xx codes (except 429) are non-retryable."""
        from src.lib.knowledge.search import MemorySearcher

        assert MemorySearcher._is_non_retryable_error(
            RuntimeError("LLM request failed (400): bad request")
        )
        assert MemorySearcher._is_non_retryable_error(
            RuntimeError("LLM request failed (401): unauthorized")
        )
        assert MemorySearcher._is_non_retryable_error(
            RuntimeError("LLM request failed (403): forbidden")
        )
        assert MemorySearcher._is_non_retryable_error(
            RuntimeError("LLM request failed (404): not found")
        )
        assert MemorySearcher._is_non_retryable_error(
            RuntimeError("LLM request failed (422): unprocessable")
        )

    def test_http_429_retryable(self, mock_data_base):
        """HTTP 429 (rate limit) is retryable, not non-retryable."""
        from src.lib.knowledge.search import MemorySearcher

        assert not MemorySearcher._is_non_retryable_error(
            RuntimeError("LLM request failed (429): rate limited")
        )

    def test_http_5xx_retryable(self, mock_data_base):
        """HTTP 5xx server errors are retryable."""
        from src.lib.knowledge.search import MemorySearcher

        assert not MemorySearcher._is_non_retryable_error(
            RuntimeError("LLM request failed (500): internal server error")
        )
        assert not MemorySearcher._is_non_retryable_error(
            RuntimeError("LLM request failed (502): bad gateway")
        )
        assert not MemorySearcher._is_non_retryable_error(
            RuntimeError("LLM request failed (503): service unavailable")
        )

    def test_generic_errors_retryable(self, mock_data_base):
        """Generic errors without keywords are retryable."""
        from src.lib.knowledge.search import MemorySearcher

        assert not MemorySearcher._is_non_retryable_error(
            RuntimeError("Connection timeout")
        )
        assert not MemorySearcher._is_non_retryable_error(
            RuntimeError("Network unreachable")
        )
        assert not MemorySearcher._is_non_retryable_error(
            OSError("socket error")
        )

    def test_api_error_without_code_retryable(self, mock_data_base):
        """'api error' in message (without HTTP code) is retryable.

        Fix commit 094988f1 removed 'api error' from non-retryable keywords
        because it was too broad and blocked retry on transient 5xx errors.
        """
        from src.lib.knowledge.search import MemorySearcher

        assert not MemorySearcher._is_non_retryable_error(
            RuntimeError("api error: service unavailable")
        )

    def test_cli_exit_code_not_matched_as_http(self, mock_data_base):
        """CLI exit codes in 'LLM command failed (EXIT_CODE)' do not trigger HTTP parsing."""
        from src.lib.knowledge.search import MemorySearcher

        # CLI exit code 1 should not match the HTTP code pattern
        # Pattern is "llm request failed (NNN)" not "llm command failed (N)"
        assert not MemorySearcher._is_non_retryable_error(
            RuntimeError("LLM command failed (1): process exited")
        )


# ===========================================================================
# Evaluate/Rank Fallback Tests
# ===========================================================================


class TestEvaluateAndRankFallbacks:
    """Test graceful fallback in _evaluate_results and _rank_results."""

    def test_evaluate_results_empty_returns_insufficient(self, mock_data_base):
        """_evaluate_results with empty result list returns insufficient without LLM call."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        mock_client = MagicMock()

        evaluation = searcher._evaluate_results(mock_client, "test query", [])

        assert not evaluation.sufficient
        assert evaluation.refined_query == "test query"
        mock_client.generate_json.assert_not_called()

    def test_rank_results_empty_returns_empty(self, mock_data_base):
        """_rank_results with empty results returns empty list without LLM call."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        mock_client = MagicMock()

        ranked = searcher._rank_results(mock_client, "test", [], top_k=5)

        assert ranked == []
        mock_client.generate_json.assert_not_called()

    def test_rank_results_top_k_zero_guarded(self, mock_data_base):
        """_rank_results with top_k=0 is guarded to max(1, top_k)."""
        from src.lib.knowledge.search import (
            MemorySearcher,
            SearchResult,
        )

        searcher = MemorySearcher()
        mock_client = MagicMock()
        mock_client.generate_json.return_value = {"ranked_indices": [0]}

        results = [
            SearchResult(
                content="test",
                source="daily",
                category="event",
                date="",
                relevance=0.5,
            )
        ]

        # top_k=0 should be guarded to 1
        ranked = searcher._rank_results(mock_client, "test", results, top_k=0)
        assert len(ranked) <= 1

    def test_rank_results_invalid_indices_ignored(self, mock_data_base):
        """Out-of-bounds or non-integer indices from LLM are silently skipped."""
        from src.lib.knowledge.search import (
            MemorySearcher,
            SearchResult,
        )

        searcher = MemorySearcher()
        mock_client = MagicMock()
        # LLM returns mix of valid, invalid, and out-of-bounds indices
        mock_client.generate_json.return_value = {
            "ranked_indices": [0, 99, -1, "invalid", 1, None]
        }

        results = [
            SearchResult(
                content="first", source="daily", category="event", date="", relevance=0.5
            ),
            SearchResult(
                content="second", source="daily", category="event", date="", relevance=0.3
            ),
        ]

        ranked = searcher._rank_results(mock_client, "test", results, top_k=5)

        # Only indices 0 and 1 are valid
        assert len(ranked) == 2
        assert ranked[0].content == "first"
        assert ranked[1].content == "second"

    def test_rank_results_missing_ranked_indices_key(self, mock_data_base):
        """If LLM response lacks 'ranked_indices', defaults to sequential order."""
        from src.lib.knowledge.search import (
            MemorySearcher,
            SearchResult,
        )

        searcher = MemorySearcher()
        mock_client = MagicMock()
        mock_client.generate_json.return_value = {"reasoning": "no indices here"}

        results = [
            SearchResult(
                content="a", source="daily", category="event", date="", relevance=0.5
            ),
            SearchResult(
                content="b", source="daily", category="event", date="", relevance=0.3
            ),
        ]

        ranked = searcher._rank_results(mock_client, "test", results, top_k=5)

        # Falls back to default range(min(top_k, len(results)))
        assert len(ranked) == 2


# ===========================================================================
# Iterative Search Integration Tests
# ===========================================================================


class TestIterativeSearchReliability:
    """Test _iterative_search graceful degradation under failure conditions."""

    def test_iterative_search_llm_unavailable_falls_back(self, mock_data_base):
        """When _get_llm_client returns None, falls back to HYBRID search."""
        from src.lib.knowledge.search import (
            MemorySearcher,
            SearchMode,
        )

        searcher = MemorySearcher()

        with patch.object(searcher, "_get_llm_client", return_value=None):
            with patch.object(searcher, "search", wraps=searcher.search) as mock_search:
                searcher._iterative_search("test", top_k=5)

        mock_search.assert_called_once_with("test", mode=SearchMode.HYBRID, top_k=5)

    def test_iterative_search_circuit_breaker_open_falls_back(self, mock_data_base):
        """When circuit breaker is open, _iterative_search falls back gracefully."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()

        # Trip the circuit breaker
        for _ in range(MemorySearcher._CIRCUIT_BREAKER_THRESHOLD):
            MemorySearcher._circuit_breaker_record_failure()

        mock_client = MagicMock()
        dummy_rg = [
            {"path": "/test.md", "line_number": 1, "content": "result", "submatches": []}
        ]

        with patch.object(searcher, "_get_llm_client", return_value=mock_client):
            with patch.object(searcher, "_ripgrep_search", return_value=dummy_rg):
                with patch("src.lib.knowledge._iterative.time.sleep"):
                    results = searcher._iterative_search("test", top_k=5)

        # Should still get results (from ripgrep), just without LLM ranking
        assert isinstance(results, list)

    def test_iterative_search_evaluation_failure_skips_ranking(self, mock_data_base):
        """When LLM evaluation fails, LLM ranking is skipped and static sort is used."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        mock_client = MagicMock()
        mock_client.generate_json.side_effect = RuntimeError("API error: service down")

        dummy_rg = [
            {"path": "/test.md", "line_number": 1, "content": "result A", "submatches": []},
            {"path": "/test.md", "line_number": 2, "content": "result B", "submatches": []},
        ]

        with patch.object(searcher, "_get_llm_client", return_value=mock_client):
            with patch.object(searcher, "_ripgrep_search", return_value=dummy_rg):
                with patch("src.lib.knowledge._iterative.time.sleep"):
                    results = searcher._iterative_search("test", top_k=5)

        # Results should be returned (fallback to static relevance)
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_iterative_search_ranking_failure_returns_static_sort(self, mock_data_base):
        """When evaluation succeeds but ranking fails, results use static relevance."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        mock_client = MagicMock()

        # First call (evaluation) succeeds, second call (ranking) fails
        mock_client.generate_json.side_effect = [
            {"sufficient": True, "refined_query": "", "reasoning": "Good"},
            RuntimeError("API died during ranking"),
        ]

        dummy_rg = [
            {"path": "/a.md", "line_number": 1, "content": "result A", "submatches": []},
        ]

        with patch.object(searcher, "_get_llm_client", return_value=mock_client):
            with patch.object(searcher, "_ripgrep_search", return_value=dummy_rg):
                with patch("src.lib.knowledge._iterative.time.sleep"):
                    results = searcher._iterative_search("test", top_k=5)

        assert isinstance(results, list)
        assert len(results) >= 1

    def test_iterative_search_max_rounds_zero(self, mock_data_base):
        """max_rounds=0 skips all rounds but still deduplicates and returns results."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        mock_client = MagicMock()

        with patch.object(searcher, "_get_llm_client", return_value=mock_client):
            with patch.object(searcher, "_ripgrep_search") as mock_rg:
                results = searcher._iterative_search("test", max_rounds=0, top_k=5)

        # No ripgrep calls (0 rounds), ranking on empty list
        mock_rg.assert_not_called()
        assert results == []

    def test_iterative_search_all_rounds_insufficient(self, mock_data_base):
        """All rounds returning insufficient still produces results from accumulated ripgrep."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        mock_client = MagicMock()

        # LLM always says insufficient, provides refined queries
        mock_client.generate_json.side_effect = [
            {"sufficient": False, "refined_query": "q1", "reasoning": "need more"},
            {"sufficient": False, "refined_query": "q2", "reasoning": "still need more"},
            {"sufficient": False, "refined_query": "q3", "reasoning": "not enough"},
            # Final ranking after all rounds
            {"ranked_indices": [0]},
        ]

        dummy_rg = [
            {"path": "/test.md", "line_number": 1, "content": "found", "submatches": []}
        ]

        with patch.object(searcher, "_get_llm_client", return_value=mock_client):
            with patch.object(searcher, "_ripgrep_search", return_value=dummy_rg):
                results = searcher._iterative_search("test", max_rounds=3, top_k=5)

        assert isinstance(results, list)

    def test_iterative_search_config_disabled_falls_back(self, mock_data_base):
        """When iterative search is disabled in config, falls back to HYBRID."""
        from src.lib.knowledge.search import (
            MemorySearcher,
            SearchMode,
        )

        searcher = MemorySearcher()
        # Override config to disable iterative search
        searcher._config = {
            "advanced": {
                "iterative_search": {
                    "enabled": False,
                    "fallback_to_static": True,
                }
            }
        }

        with patch.object(searcher, "search", wraps=searcher.search) as mock_search:
            searcher._iterative_search("test", top_k=5)

        mock_search.assert_called_once_with("test", mode=SearchMode.HYBRID, top_k=5)

    def test_iterative_search_config_disabled_no_fallback_returns_empty(self, mock_data_base):
        """When disabled with fallback_to_static=False, returns empty list."""
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        searcher._config = {
            "advanced": {
                "iterative_search": {
                    "enabled": False,
                    "fallback_to_static": False,
                }
            }
        }

        results = searcher._iterative_search("test", top_k=5)
        assert results == []


# ===========================================================================
# Path Normalization Edge Cases
# ===========================================================================


class TestPathNormalizationEdgeCases:
    """Test _normalize_path with unusual inputs."""

    def test_normalize_none_returns_none(self, mock_data_base):
        """None file path returns None."""
        from src.lib.knowledge.search import _normalize_path

        assert _normalize_path(None) is None

    def test_normalize_empty_string(self, mock_data_base):
        """Empty string normalizes to current directory resolved path."""
        from src.lib.knowledge.search import _normalize_path

        result = _normalize_path("")
        # Empty string resolves to cwd
        assert result is not None
        assert len(result) > 0

    def test_normalize_invalid_path_returns_original(self, mock_data_base):
        """Paths that cause OSError return the original string."""
        from src.lib.knowledge.search import _normalize_path

        # On most systems, paths with null bytes cause OSError
        result = _normalize_path("\x00invalid")
        # Should return the original rather than crash
        assert result == "\x00invalid"
