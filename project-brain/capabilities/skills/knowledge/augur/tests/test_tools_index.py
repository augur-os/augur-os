"""Auto-generated importability test for tools_index."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.config.paths import get_project_root

PROJECT_ROOT = get_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "mcp"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_tools_index_importable():
    """Verify that tools_index can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_index")
    assert mod is not None


def test_unified_indexer_loader_uses_current_src_module():
    """The MCP index tools load the canonical src/lib indexer, not a retired skill path."""
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_index")

    loaded = mod._load_unified_indexer_module()

    assert hasattr(loaded, "reindex_all")
    assert Path(loaded.__file__).relative_to(PROJECT_ROOT).as_posix() == "src/lib/index/unified_indexer.py"


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name: str, annotations=None):
        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator


class _FakeMetrics:
    def track_tool(self, *_args, **_kwargs):
        return None


def _identity(fn):
    return fn


def test_index_tools_pass_external_roots_to_reindex_all():
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_index")
    fake_mcp = _FakeMCP()
    mod.register_index_tools(fake_mcp, _identity, _FakeMetrics())

    calls = []

    def fake_reindex_all(root, rag_dir, vault_dir=None, documents_dir=None, document_sources=None):
        calls.append((root, rag_dir, vault_dir, documents_dir, document_sources))
        return {"skills": 1}

    fake_module = SimpleNamespace(reindex_all=fake_reindex_all)

    async def run_tools():
        with (
            patch.object(mod, "_load_unified_indexer_module", return_value=fake_module),
            patch.object(mod, "PROJECT_ROOT", Path("/tmp/project")),
            patch.object(mod, "get_rag_dir", return_value=Path("/tmp/rag")),
            patch.object(mod, "_get_external_roots", return_value=(Path("/tmp/vault"), Path("/tmp/documents"))),
            patch("src.lib.index.document_source_config.configured_document_sources", return_value=[]),
        ):
            rebuild = fake_mcp.tools["knowledge-project-index-rebuild"]
            docs = fake_mcp.tools["index-documents"]
            await rebuild()
            await docs()

    asyncio.run(run_tools())

    assert calls == [
        (Path("/tmp/project"), Path("/tmp/rag"), Path("/tmp/vault"), Path("/tmp/documents"), []),
        (Path("/tmp/project"), Path("/tmp/rag"), Path("/tmp/vault"), Path("/tmp/documents"), []),
    ]


def test_index_tools_use_default_document_sources(monkeypatch, tmp_path):
    import importlib

    from src.lib.index.document_sources import DocumentSource

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_index")
    fake_mcp = _FakeMCP()
    mod.register_index_tools(fake_mcp, _identity, _FakeMetrics())
    calls = []
    docs = tmp_path / "Au-docs"
    docs.mkdir()
    sources = [DocumentSource("documents", "Au-docs", docs, preserve_legacy_output=True)]

    def fake_sources(*, project_root, documents_dir):
        calls.append(("sources", project_root, documents_dir))
        return sources

    def fake_reindex_all(root, rag_dir, vault_dir=None, documents_dir=None, document_sources=None):
        calls.append(("reindex", root, rag_dir, vault_dir, documents_dir, document_sources))
        return {"documents": len(document_sources or [])}

    fake_module = SimpleNamespace(reindex_all=fake_reindex_all)

    async def run_tools():
        with (
            patch.object(mod, "_load_unified_indexer_module", return_value=fake_module),
            patch.object(mod, "PROJECT_ROOT", tmp_path / "Augur"),
            patch.object(mod, "get_rag_dir", return_value=tmp_path / "rag"),
            patch.object(mod, "_get_external_roots", return_value=(tmp_path / "vault", docs)),
            patch("src.lib.index.document_source_config.configured_document_sources", side_effect=fake_sources),
        ):
            rebuild_result = json.loads(await fake_mcp.tools["knowledge-project-index-rebuild"]())
            docs_result = json.loads(await fake_mcp.tools["index-documents"]())
            return rebuild_result, docs_result

    rebuild_result, docs_result = asyncio.run(run_tools())

    assert calls == [
        ("sources", tmp_path / "Augur", docs),
        ("reindex", tmp_path / "Augur", tmp_path / "rag", tmp_path / "vault", docs, sources),
        ("sources", tmp_path / "Augur", docs),
        ("reindex", tmp_path / "Augur", tmp_path / "rag", tmp_path / "vault", docs, sources),
    ]
    expected_sources = [
        {
            "id": "documents",
            "name": "Au-docs",
            "path": str(docs.resolve(strict=False)),
            "provider": "filesystem",
            "source_type": "local",
            "attached_brain_ids": "personal",
        }
    ]
    assert docs_result["sources"] == expected_sources
    assert rebuild_result["sources"] == expected_sources


def test_index_tools_use_configured_document_sources(monkeypatch, tmp_path):
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_index")

    captured = {}

    class Source:
        id = "project-y-drive"
        name = "Project Y Drive"
        provider = "google-drive"
        source_type = "shared"
        attached_brain_ids = ("project-y",)

        @property
        def resolved_path(self):
            return Path("/tmp/project-y-drive-cache")

    def fake_configured_document_sources(*, project_root, documents_dir):
        captured["project_root"] = project_root
        captured["documents_dir"] = documents_dir
        return [Source()]

    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path / "Augur")
    monkeypatch.setattr(
        "src.lib.index.document_source_config.configured_document_sources",
        fake_configured_document_sources,
    )

    sources = mod._default_document_sources(tmp_path / "Au-docs")

    assert sources[0].id == "project-y-drive"
    assert mod._document_source_metadata(sources)[0] == {
        "id": "project-y-drive",
        "name": "Project Y Drive",
        "path": "/tmp/project-y-drive-cache",
        "provider": "google-drive",
        "source_type": "shared",
        "attached_brain_ids": "project-y",
    }
    assert captured == {
        "project_root": tmp_path / "Augur",
        "documents_dir": tmp_path / "Au-docs",
    }
