"""
Tests for BM25Index — BM25 sparse retrieval index for RAG pipeline.

Module: skills/rag/scripts/bm25_index.py
"""

import json

import pytest

from src.lib.index.bm25_index import BM25Index


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CHUNKS_DIVERSE = [
    {
        "path": "docs/resilience.md",
        "text": "circuit breaker pattern retry logic exponential backoff fault tolerance",
        "meta": {"source": "resilience"},
    },
    {
        "path": "docs/auth.md",
        "text": "authentication oauth token refresh JWT bearer header security",
        "meta": {"source": "auth"},
    },
    {
        "path": "docs/db.md",
        "text": "database connection pool query optimization index performance",
        "meta": {"source": "db"},
    },
]

CHUNKS_NOTIFICATIONS = [
    {
        "path": "docs/notif.md",
        "text": "configure notification settings for email and slack channel",
        "meta": {"source": "notif"},
    },
    {
        "path": "docs/logging.md",
        "text": "structured logging json format log level filtering",
        "meta": {"source": "logging"},
    },
    {
        "path": "docs/cache.md",
        "text": "cache eviction policy lru ttl memory storage",
        "meta": {"source": "cache"},
    },
]


# ---------------------------------------------------------------------------
# TestBM25Index
# ---------------------------------------------------------------------------


class TestBM25Index:
    def test_build_from_chunks(self):
        idx = BM25Index.build(CHUNKS_DIVERSE)
        assert idx.size() == 3

    def test_query_returns_ranked_results(self):
        idx = BM25Index.build(CHUNKS_DIVERSE)
        results = idx.query("circuit breaker retry", top_k=10)
        assert len(results) >= 1
        assert results[0]["path"] == "docs/resilience.md"
        # Scores should be descending
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_query_partial_match(self):
        idx = BM25Index.build(CHUNKS_NOTIFICATIONS)
        results = idx.query("notification channel", top_k=10)
        assert len(results) >= 1
        assert results[0]["path"] == "docs/notif.md"

    def test_empty_query_returns_empty(self):
        idx = BM25Index.build(CHUNKS_DIVERSE)
        results = idx.query("", top_k=10)
        assert results == []

    def test_empty_index_returns_empty(self):
        idx = BM25Index.build([])
        results = idx.query("circuit breaker", top_k=10)
        assert results == []


# ---------------------------------------------------------------------------
# TestBM25Serialization
# ---------------------------------------------------------------------------


class TestBM25Serialization:
    def test_save_and_load_roundtrip(self, tmp_path):
        idx = BM25Index.build(CHUNKS_DIVERSE)
        idx.save(tmp_path)

        loaded = BM25Index.load(tmp_path)
        assert loaded.size() == idx.size()

        original_results = idx.query("circuit breaker retry", top_k=5)
        loaded_results = loaded.query("circuit breaker retry", top_k=5)
        assert len(original_results) == len(loaded_results)
        assert original_results[0]["path"] == loaded_results[0]["path"]

    def test_save_creates_expected_files(self, tmp_path):
        idx = BM25Index.build(CHUNKS_DIVERSE)
        idx.save(tmp_path)

        assert (tmp_path / "bm25_index.json").exists()
        assert (tmp_path / "bm25_chunk_map.json").exists()

    def test_load_missing_files_returns_empty(self, tmp_path):
        idx = BM25Index.load(tmp_path)
        assert idx.size() == 0


# ---------------------------------------------------------------------------
# TestBM25Tokenization
# ---------------------------------------------------------------------------


class TestBM25Tokenization:
    def test_stopwords_removed(self):
        chunks = [
            {"path": "a.md", "text": "the quick brown fox", "meta": {}},
            {"path": "b.md", "text": "slow red tortoise", "meta": {}},
            {"path": "c.md", "text": "blue ocean wave surf", "meta": {}},
        ]
        idx = BM25Index.build(chunks)
        results = idx.query("quick fox", top_k=5)
        assert len(results) >= 1
        assert results[0]["path"] == "a.md"

    def test_case_insensitive(self):
        chunks = [
            {"path": "circuit.md", "text": "Circuit Breaker Pattern", "meta": {}},
            {"path": "other.md", "text": "Database Connection Pool", "meta": {}},
            {"path": "extra.md", "text": "cache eviction policy lru", "meta": {}},
        ]
        idx = BM25Index.build(chunks)
        results = idx.query("circuit breaker", top_k=5)
        assert len(results) >= 1
        assert results[0]["path"] == "circuit.md"
