"""Tests for the simplified RAGSearchEngine."""

from unittest.mock import MagicMock

def _make_engine(search_results=None, bm25_index=None):
    """Helper to create a RAGSearchEngine with a mock search function."""
    from src.lib.index.search_engine import RAGSearchEngine

    mock_search = MagicMock(return_value=search_results or [])
    return RAGSearchEngine(search_func=mock_search, bm25_index=bm25_index), mock_search


class TestIterativeSearch:
    """Tests for iterative_search in the three-tier simplified flow."""

    def test_returns_raw_results_without_llm(self):
        raw = [{"type": "fulltext", "hits": [{"file": "a.md", "content": "match"}]}]
        engine, mock_search = _make_engine(search_results=raw)

        results = engine.iterative_search("test query")
        mock_search.assert_called_once_with("test query")
        assert len(results) == 1
        assert results[0]["type"] == "fulltext"

    def test_applies_top_k_to_hit_groups(self):
        hits = [{"file": f"f{i}.md", "content": "match"} for i in range(20)]
        raw = [{"type": "fulltext", "hits": hits}]
        engine, _ = _make_engine(search_results=raw)

        results = engine.iterative_search("test", top_k=5)
        assert len(results[0]["hits"]) == 5

    def test_empty_search_returns_empty(self):
        engine, _ = _make_engine(search_results=[])
        results = engine.iterative_search("nothing")
        assert results == []

    def test_engine_accepts_bm25_index(self):
        from src.lib.index.search_engine import RAGSearchEngine

        bm25 = object()
        mock_search = MagicMock(return_value=[])
        engine = RAGSearchEngine(search_func=mock_search, bm25_index=bm25)
        assert engine._bm25_index is not None

    def test_iterative_search_appends_document_hits_when_bm25_available(self):
        from src.lib.index.search_engine import RAGSearchEngine

        bm25 = MagicMock()
        bm25.query.return_value = [
            {
                "path": "chunks/documents/payroll-policy/introduction_0.md",
                "score": 1.5,
                "meta": {"category": "documents", "source": "payroll-policy", "hub": "brain"},
            },
            {
                "path": "chunks/documents/benefits/intro_0.md",
                "score": 0.5,
                "meta": {"category": "documents", "source": "benefits", "hub": "brain"},
            },
        ]

        ripgrep_results = [{"type": "fulltext", "hits": [
            {"file": "skills/finance/SKILL.md", "content": "invoice handling"},
        ]}]
        mock_search = MagicMock(return_value=ripgrep_results)
        engine = RAGSearchEngine(search_func=mock_search, bm25_index=bm25)

        results = engine.iterative_search("invoice", top_k=5)
        assert len(results) == 2
        assert results[0]["type"] == "fulltext"
        assert results[1]["type"] == "documents"
        assert results[1]["hits"][0]["file"] == "chunks/documents/payroll-policy/introduction_0.md"
        assert results[1]["hits"][0]["source"] == "payroll-policy"

    def test_iterative_search_limits_document_hits_to_top_k(self):
        from src.lib.index.search_engine import RAGSearchEngine

        bm25 = MagicMock()
        bm25.query.return_value = [
            {"path": f"chunks/documents/doc-{i}/intro_0.md", "score": 5 - i, "meta": {"category": "documents", "source": f"doc-{i}"}}
            for i in range(4)
        ]
        engine = RAGSearchEngine(search_func=MagicMock(return_value=[]), bm25_index=bm25)

        results = engine.iterative_search("invoice", top_k=2)
        assert results == [{
            "type": "documents",
            "hits": results[0]["hits"],
        }]
        assert len(results[0]["hits"]) == 2
