from __future__ import annotations

import json
from pathlib import Path

from src.lib.frontmatter_utils import write_frontmatter
from src.mcp.augur_framework.tools.infrastructure.browse import browse_index_impl


def _write_project_source_config(project_root: Path, extra_fields: str = "") -> None:
    config = project_root / "config" / "documents" / "sources.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "sources:\n"
        "  - id: project-y-drive\n"
        "    name: Project Y Drive\n"
        "    provider: google-drive\n"
        "    remote_id: folders/abc123\n"
        f"{extra_fields}",
        encoding="utf-8",
    )


def _patch_document_browse_paths(tmp_path: Path, monkeypatch) -> tuple[Path, Path, Path]:
    project_root = tmp_path / "project"
    documents_dir = tmp_path / "Au-docs"
    cache_root = tmp_path / "cache"
    documents_dir.mkdir()

    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse.index_metadata.get_project_root",
        lambda: project_root,
    )
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse.index_metadata.get_documents_dir",
        lambda: documents_dir,
    )
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse.index_metadata.get_cache_dir",
        lambda: cache_root,
        raising=False,
    )
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse.index.inventory_browse_entries_for_category",
        lambda _category: [],
    )
    monkeypatch.setattr(
        "src.lib.index.document_source_config.read_project_brain_id",
        lambda _root: "project-y",
    )
    monkeypatch.setattr(
        "src.config.paths.get_rag_category_dir",
        lambda category: tmp_path / "rag" / category,
    )
    return project_root, documents_dir, cache_root


def test_browse_documents_emits_configured_project_source_card_when_not_indexed(tmp_path, monkeypatch):
    project_root, _documents_dir, cache_root = _patch_document_browse_paths(tmp_path, monkeypatch)
    _write_project_source_config(
        project_root,
        "    attached_brain_ids:\n" "      - project-y\n" "    catalog_summary: Shared project docs summary.\n",
    )
    (cache_root / "document-sources" / "project-y-drive").mkdir(parents=True)

    payload = json.loads(browse_index_impl(category="documents", limit=20))

    assert payload["count"] == 1
    item = payload["items"][0]
    assert item["id"] == "document-source:project-y-drive"
    assert item["title"] == "Project Y Drive"
    assert item["description"] == "Shared project docs summary."
    assert item["type"] == "document-source"
    assert item["metadata"]["attachedBrainIds"] == "project-y"
    assert item["metadata"]["indexStatus"] == "not_indexed"
    assert item["metadata"]["catalogSummary"] == "Shared project docs summary."
    assert item["metadata"]["provider"] == "google-drive"


def test_browse_documents_marks_missing_shared_cache_as_needs_access(tmp_path, monkeypatch):
    project_root, _documents_dir, _cache_root = _patch_document_browse_paths(tmp_path, monkeypatch)
    _write_project_source_config(project_root)

    payload = json.loads(browse_index_impl(category="documents", limit=20))

    assert payload["items"][0]["id"] == "document-source:project-y-drive"
    assert payload["items"][0]["metadata"]["indexStatus"] == "needs_access"


def test_browse_documents_surfaces_invalid_project_source_config(tmp_path, monkeypatch):
    project_root, _documents_dir, _cache_root = _patch_document_browse_paths(tmp_path, monkeypatch)
    config = project_root / "config" / "documents" / "sources.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "sources:\n"
        "  - id: local-project\n"
        "    name: Local Project\n"
        "    provider: filesystem\n"
        "    remote_id: folders/abc123\n",
        encoding="utf-8",
    )

    payload = json.loads(browse_index_impl(category="documents", limit=20))

    assert payload["count"] == 1
    item = payload["items"][0]
    assert item["id"] == "document-source-config:error"
    assert item["title"] == "Document source config error"
    assert item["type"] == "document-source-error"
    assert item["source_path"].endswith("config/documents/sources.yaml")
    assert "must use a shared provider" in item["description"]
    assert item["metadata"]["indexStatus"] == "config_error"
    assert "must use a shared provider" in item["metadata"]["error"]


def test_browse_documents_does_not_duplicate_configured_source_with_indexed_entries(tmp_path, monkeypatch):
    project_root, _documents_dir, cache_root = _patch_document_browse_paths(tmp_path, monkeypatch)
    _write_project_source_config(project_root)
    shared_cache = cache_root / "document-sources" / "project-y-drive"
    shared_cache.mkdir(parents=True)
    source_file = shared_cache / "architecture.md"
    source_file.write_text("architecture", encoding="utf-8")

    write_frontmatter(
        tmp_path / "rag" / "documents" / "_sources" / "project-y-drive" / "architecture.md",
        {
            "id": "architecture",
            "name": "architecture",
            "title": "Architecture Overview",
            "type": "document",
            "hub": "project-y-drive",
            "source_path": str(source_file),
            "metadata": {"source_id": "project-y-drive"},
        },
        "Body",
    )

    payload = json.loads(browse_index_impl(category="documents", limit=20))

    assert payload["count"] == 1
    assert payload["items"][0]["id"] == "architecture"
