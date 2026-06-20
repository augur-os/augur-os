import sys
import asyncio
import json
from pathlib import Path


def test_get_wiki_pages_uses_package_import_without_bare_script_path(monkeypatch, tmp_path):
    from skills.wiki.scripts.mcp import wiki_tools

    wiki_tools._wiki_pages = None
    script_dir = str(Path(wiki_tools.__file__).resolve().parents[1])
    monkeypatch.setattr(sys, "path", [entry for entry in sys.path if entry != script_dir])
    sys.modules.pop("wiki_pages", None)
    monkeypatch.setattr(wiki_tools, "get_compiled_wiki_dir", lambda *_args: tmp_path / "wiki")
    monkeypatch.setattr("src.config.paths.get_runtime_dir", lambda: tmp_path / "runtime")

    pages = wiki_tools._get_wiki_pages()

    assert pages._wiki_dir == tmp_path / "wiki"
    assert pages._runtime_dir == tmp_path / "runtime" / "wiki"


def test_ask_sync_tools_use_package_imports_after_plugin_path_cleanup(monkeypatch):
    from src.lib.ingest import ask_sync, ask_sync_clusters
    from skills.wiki.scripts.mcp import wiki_tools

    class FakeMcp:
        def __init__(self):
            self.tools = {}

        def tool(self, name, annotations=None):
            def decorator(func):
                self.tools[name] = func
                return func

            return decorator

    class Metrics:
        def track_tool(self, name, skill):
            return None

    sample_item = {
        "kind": "synthesis",
        "question": "What pattern is emerging in Augur wiki compounding?",
        "summary": "Augur should show evidence-backed compounding candidates.",
        "confidence": "high",
        "tags": ["ask", "demo", "wiki"],
        "created": "2026-06-01T00:00:00+00:00",
        "path": "/tmp/demo.md",
        "source_type": "synthesis",
    }
    monkeypatch.setattr(
        ask_sync,
        "load_recent_ask_outcomes",
        lambda *, days_back=7, limit=20: [sample_item],
    )
    monkeypatch.setattr(
        ask_sync_clusters,
        "cluster_ask_outcomes",
        lambda items: [{"label": "demo wiki", "items": items, "item_count": len(items)}],
    )
    monkeypatch.setattr(
        ask_sync_clusters,
        "suggest_page_targets",
        lambda clusters, tags: [{**clusters[0], "suggested_page_target": "brain/demo-wiki"}],
    )

    class Pages:
        def read_tags(self):
            return {}

    monkeypatch.setattr(wiki_tools, "_get_wiki_pages", lambda: Pages())

    mcp = FakeMcp()
    wiki_tools.register_wiki_tools(mcp, lambda func: func, Metrics())

    script_dir = str(Path(wiki_tools.__file__).resolve().parents[1])
    monkeypatch.setattr(sys, "path", [entry for entry in sys.path if entry != script_dir])
    sys.modules.pop("ask_sync", None)
    sys.modules.pop("ask_sync_clusters", None)

    data = json.loads(asyncio.run(mcp.tools["ask-sync-data"](days_back=90, limit=5)))
    clusters = json.loads(asyncio.run(mcp.tools["ask-sync-clusters"](days_back=90, limit=5)))

    assert data["success"] is True
    assert data["count"] == 1
    assert clusters["success"] is True
    assert clusters["count"] == 1
    assert clusters["clusters"][0]["suggested_page_target"] == "brain/demo-wiki"
