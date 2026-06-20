"""Auto-generated importability test for tools_memory_core."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_tools_memory_core_importable():
    """Verify that tools_memory_core can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_core")
    assert mod is not None


def test_search_memory_results_uses_memory_searcher_payload(monkeypatch):
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_core")

    class FakeResult:
        def __init__(self, payload):
            self._payload = payload

        def to_dict(self):
            return self._payload

    class FakeSearcher:
        def search(self, **kwargs):
            assert kwargs["query"] == "workflow"
            assert kwargs["mode"].value == "hybrid"
            assert kwargs["top_k"] == 3
            return [
                FakeResult(
                    {
                        "content": "Workflow decisions captured in the April 21 daily log.",
                        "source": "daily",
                        "category": "decision",
                        "date": "2026-04-21",
                        "relevance": 0.92,
                        "file_path": "/tmp/2026-04-21.md",
                        "line_number": 8,
                    }
                )
            ]

    monkeypatch.setattr(mod, "MemorySearcher", lambda: FakeSearcher())

    results = mod._search_memory_results(query="workflow", mode="hybrid", top_k=3)

    assert results == [
        {
            "doc_id": "/tmp/2026-04-21.md:8",
            "content": "Workflow decisions captured in the April 21 daily log.",
            "source": "daily",
            "category": "decision",
            "date": "2026-04-21",
            "relevance": 0.92,
            "file_path": "/tmp/2026-04-21.md",
            "line_number": 8,
            "score": 0.016393,
            "budget": "balanced",
            "provenance": ["memory"],
        }
    ]


def test_search_memory_results_budget_sets_limit_and_shape(monkeypatch):
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_core")

    class FakeSearcher:
        def search(self, **kwargs):
            assert kwargs["top_k"] == 5
            return [
                {
                    "content": "short memory result",
                    "file_path": "/tmp/memory.md",
                    "line_number": 1,
                    "relevance": 0.7,
                }
            ]

    monkeypatch.setattr(mod, "MemorySearcher", lambda: FakeSearcher())

    results = mod._search_memory_results(query="short", budget="conservative")

    assert results[0]["budget"] == "conservative"
    assert results[0]["provenance"] == ["memory"]
    assert "score" in results[0]


def test_memory_profile_regenerate_calls_wiki_query_runner(monkeypatch):
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_core")
    called = {}

    class FakeResult:
        success = True
        query_id = "profile-human-api"
        error = None
        output_path = "vault/wiki/profile-human-api.md"
        tokens_used = 12
        sections_validated = ["Role"]
        truncated_sources = False

        def to_dict(self):
            return {
                "success": self.success,
                "query_id": self.query_id,
                "error": self.error,
                "output_path": self.output_path,
                "tokens_used": self.tokens_used,
                "sections_validated": self.sections_validated,
                "truncated_sources": self.truncated_sources,
            }

    def fake_run(query_id):
        called["id"] = query_id
        return FakeResult()

    monkeypatch.setattr(mod, "run_query", fake_run)

    result = mod._memory_profile_regenerate_impl()

    assert called["id"] == "profile-human-api"
    assert result["success"] is True
    assert result["details"]["output_path"] == "vault/wiki/profile-human-api.md"
