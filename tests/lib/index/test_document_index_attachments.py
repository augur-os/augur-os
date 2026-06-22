from __future__ import annotations

import json
from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.index import unified_indexer
from src.lib.index.document_sources import DocumentSource
from src.lib.index.unified_indexer import (
    index_document_sources,
    reindex_all,
    reindex_category,
)


def _patch_document_extraction(monkeypatch) -> None:
    def fake_extract(path: Path) -> dict[str, object]:
        body = path.read_text(encoding="utf-8")
        return {
            "format": path.suffix.lower().lstrip(".") or "md",
            "size_bytes": path.stat().st_size,
            "created": "2026-06-07T08:00:00+00:00",
            "body": body,
            "document_title": path.stem.replace("-", " ").title(),
            "document_kind": "document",
            "document_summary": body.strip().splitlines()[-1],
            "document_key_insights": [],
            "document_sections": [],
            "document_extraction_method": "test",
            "document_visual_structure_used": False,
            "document_understanding_version": "v3",
            "document_action_candidates": [],
            "document_extraction_confidence": "high",
            "document_low_signal_warnings": [],
            "document_llm_assisted": False,
        }

    monkeypatch.setattr(unified_indexer, "_extract_document", fake_extract)
    monkeypatch.setattr(unified_indexer, "_load_mtime_cache", lambda: {})
    monkeypatch.setattr(unified_indexer, "_save_mtime_cache", lambda _cache: None)


def test_index_document_source_writes_attachment_metadata(tmp_path, monkeypatch):
    _patch_document_extraction(monkeypatch)
    source_root = tmp_path / "Downloads"
    source_root.mkdir()
    report = source_root / "report.md"
    report.write_text(
        "# Report\n\nThis document has enough words for extraction.",
        encoding="utf-8",
    )

    rag_dir = tmp_path / "rag"
    source = DocumentSource(
        id="downloads",
        name="Downloads",
        path=source_root,
        attached_brain_ids=("personal",),
    )

    count = index_document_sources([source], rag_dir)

    assert count == 1
    output = rag_dir / "documents" / "_sources" / "downloads" / "report.md"
    metadata, body = parse_frontmatter(output)
    assert metadata["canonical_document_id"] == f"filesystem:{report.resolve(strict=False)}"
    assert metadata["attached_brain_ids"] == ["personal"]
    assert metadata["brain_id"] == "personal"
    assert metadata["source_id"] == "downloads"
    assert metadata["source_type"] == "local"
    assert metadata["provider"] == "filesystem"
    assert metadata["index_status"] == "synced"
    assert "This document" in body


def test_index_document_source_uses_catalog_summary_and_revision(
    tmp_path,
    monkeypatch,
):
    _patch_document_extraction(monkeypatch)
    source_root = tmp_path / "shared-cache"
    source_root.mkdir()
    deck = source_root / "deck.md"
    deck.write_text("# Deck\n\nProject Y investor deck body.", encoding="utf-8")

    project_root = tmp_path / "project"
    catalog_entry = project_root / "project-brain" / "knowledge" / "documents" / "project-y-drive" / "deck.md"
    catalog_entry.parent.mkdir(parents=True)
    catalog_entry.write_text(
        "---\n"
        "remote_id: google-drive:file:deck\n"
        "source_id: project-y-drive\n"
        "source_relative_path: deck.md\n"
        "provider: google-drive\n"
        "attached_brain_ids:\n"
        "  - project-y\n"
        "title: Investor Deck\n"
        "summary_status: auto\n"
        "summary_generated_from_revision: drive-revision-41\n"
        "remote_revision: drive-revision-42\n"
        "remote_modified_at: 2026-06-07T08:00:00Z\n"
        "---\n"
        "Catalog summary used on cards.\n",
        encoding="utf-8",
    )

    rag_dir = tmp_path / "rag"
    source = DocumentSource(
        id="project-y-drive",
        name="Project Y Drive",
        path=source_root,
        source_type="shared",
        provider="google-drive",
        attached_brain_ids=("project-y",),
        source_remote_id="folder:abc123",
        remote_revision="drive-revision-42",
        remote_modified_at="2026-06-07T08:00:00Z",
    )

    index_document_sources([source], rag_dir, project_root=project_root)

    metadata, _body = parse_frontmatter(rag_dir / "documents" / "_sources" / "project-y-drive" / "deck.md")
    assert metadata["title"] == "Investor Deck"
    assert metadata["document_title"] == "Investor Deck"
    assert metadata["description"] == "Catalog summary used on cards."
    assert metadata["catalog_summary"] == "Catalog summary used on cards."
    assert metadata["document_summary"] == "Catalog summary used on cards."
    assert metadata["index_status"] == "summary_stale"
    assert metadata["remote_id"] == "google-drive:file:deck"
    assert metadata["remote_revision"] == "drive-revision-42"
    assert metadata["remote_modified_at"] == "2026-06-07T08:00:00Z"
    assert metadata["indexed_revision"] == "drive-revision-42"
    assert metadata["summary_generated_from_revision"] == "drive-revision-41"
    assert metadata["catalog_entry_path"] == ("project-brain/knowledge/documents/project-y-drive/deck.md")


def test_index_document_source_uses_source_catalog_summary_without_catalog_entry(
    tmp_path,
    monkeypatch,
):
    _patch_document_extraction(monkeypatch)
    source_root = tmp_path / "shared-cache"
    source_root.mkdir()
    brief = source_root / "brief.md"
    brief.write_text("# Brief\n\nProject Y brief body.", encoding="utf-8")

    rag_dir = tmp_path / "rag"
    source = DocumentSource(
        id="project-y-drive",
        name="Project Y Drive",
        path=source_root,
        source_type="shared",
        provider="google-drive",
        attached_brain_ids=("project-y",),
        source_remote_id="folder:abc123",
        remote_revision="drive-revision-42",
        remote_modified_at="2026-06-07T08:00:00Z",
        catalog_title="Project Y Reference Folder",
        catalog_summary="Shared project documents used by Browse cards.",
        summary_status="human",
        summary_generated_from_revision="drive-revision-41",
    )

    index_document_sources([source], rag_dir)

    metadata, _body = parse_frontmatter(rag_dir / "documents" / "_sources" / "project-y-drive" / "brief.md")
    assert metadata["title"] == "Project Y Reference Folder"
    assert metadata["description"] == "Shared project documents used by Browse cards."
    assert metadata["catalog_title"] == "Project Y Reference Folder"
    assert metadata["catalog_summary"] == "Shared project documents used by Browse cards."
    assert metadata["summary_status"] == "human"
    assert metadata["summary_generated_from_revision"] == "drive-revision-41"
    assert metadata["index_status"] == "summary_stale"


def test_cached_document_refreshes_catalog_metadata_without_reextracting(
    tmp_path,
    monkeypatch,
):
    _patch_document_extraction(monkeypatch)
    source_root = tmp_path / "shared-cache"
    source_root.mkdir()
    deck = source_root / "deck.md"
    deck.write_text("# Deck\n\nProject Y investor deck body.", encoding="utf-8")
    indexed_mtime = deck.stat().st_mtime

    project_root = tmp_path / "project"
    catalog_entry = project_root / "project-brain" / "knowledge" / "documents" / "project-y-drive" / "deck.md"
    catalog_entry.parent.mkdir(parents=True)
    catalog_entry.write_text(
        "---\n"
        "remote_id: google-drive:file:deck\n"
        "source_id: project-y-drive\n"
        "source_relative_path: deck.md\n"
        "provider: google-drive\n"
        "attached_brain_ids:\n"
        "  - project-y\n"
        "title: Investor Deck\n"
        "summary_generated_from_revision: drive-revision-42\n"
        "remote_revision: drive-revision-42\n"
        "---\n"
        "Initial catalog summary.\n",
        encoding="utf-8",
    )
    rag_dir = tmp_path / "rag"
    source = DocumentSource(
        id="project-y-drive",
        name="Project Y Drive",
        path=source_root,
        source_type="shared",
        provider="google-drive",
        attached_brain_ids=("project-y",),
        source_remote_id="folder:abc123",
        remote_revision="drive-revision-42",
    )

    index_document_sources([source], rag_dir, project_root=project_root)
    catalog_entry.write_text(
        "---\n"
        "remote_id: google-drive:file:deck\n"
        "source_id: project-y-drive\n"
        "source_relative_path: deck.md\n"
        "provider: google-drive\n"
        "attached_brain_ids:\n"
        "  - project-y\n"
        "title: Investor Deck Updated\n"
        "summary_generated_from_revision: drive-revision-42\n"
        "remote_revision: drive-revision-42\n"
        "---\n"
        "Updated catalog summary.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        unified_indexer,
        "_load_mtime_cache",
        lambda: {str(deck.resolve()): indexed_mtime},
    )

    def fail_extract(path: Path) -> dict[str, object]:
        raise AssertionError(f"unexpected re-extraction for cached document {path}")

    monkeypatch.setattr(unified_indexer, "_extract_document", fail_extract)

    index_document_sources([source], rag_dir, project_root=project_root)

    metadata, body = parse_frontmatter(rag_dir / "documents" / "_sources" / "project-y-drive" / "deck.md")
    assert metadata["document_title"] == "Investor Deck Updated"
    assert metadata["document_summary"] == "Updated catalog summary."
    assert metadata["index_status"] == "synced"
    assert "Project Y investor deck body" in body


def test_shared_document_source_requires_remote_revision_freshness(
    tmp_path,
    monkeypatch,
):
    _patch_document_extraction(monkeypatch)
    source_root = tmp_path / "shared-cache"
    source_root.mkdir()
    source_doc = source_root / "proposal.md"
    source_doc.write_text("# Proposal\n\nProject Y proposal body.", encoding="utf-8")

    project_root = tmp_path / "project"
    catalog_entry = project_root / "project-brain" / "knowledge" / "documents" / "project-y-drive" / "proposal.md"
    catalog_entry.parent.mkdir(parents=True)
    catalog_entry.write_text(
        "---\n"
        "remote_id: google-drive:file:proposal\n"
        "source_id: project-y-drive\n"
        "source_relative_path: proposal.md\n"
        "provider: google-drive\n"
        "attached_brain_ids:\n"
        "  - project-y\n"
        "title: Proposal\n"
        "---\n"
        "Proposal catalog summary.\n",
        encoding="utf-8",
    )

    index_document_sources(
        [
            DocumentSource(
                id="project-y-drive",
                name="Project Y Drive",
                path=source_root,
                source_type="shared",
                provider="google-drive",
                attached_brain_ids=("project-y",),
                source_remote_id="folder:abc123",
            )
        ],
        tmp_path / "rag",
        project_root=project_root,
    )

    metadata, _body = parse_frontmatter(tmp_path / "rag" / "documents" / "_sources" / "project-y-drive" / "proposal.md")
    assert metadata["index_status"] == "source_changed"
    assert metadata["remote_revision"] == ""
    assert metadata["indexed_revision"] == ""


def test_shared_document_source_marks_cache_revision_mismatch_changed(
    tmp_path,
    monkeypatch,
):
    _patch_document_extraction(monkeypatch)
    source_root = tmp_path / "shared-cache"
    source_root.mkdir()
    source_doc = source_root / "roadmap.md"
    source_doc.write_text("# Roadmap\n\nProject Y roadmap body.", encoding="utf-8")

    project_root = tmp_path / "project"
    catalog_entry = project_root / "project-brain" / "knowledge" / "documents" / "project-y-drive" / "roadmap.md"
    catalog_entry.parent.mkdir(parents=True)
    catalog_entry.write_text(
        "---\n"
        "remote_id: google-drive:file:roadmap\n"
        "source_id: project-y-drive\n"
        "source_relative_path: roadmap.md\n"
        "provider: google-drive\n"
        "remote_revision: drive-revision-42\n"
        "---\n"
        "Roadmap catalog summary.\n",
        encoding="utf-8",
    )

    index_document_sources(
        [
            DocumentSource(
                id="project-y-drive",
                name="Project Y Drive",
                path=source_root,
                source_type="shared",
                provider="google-drive",
                attached_brain_ids=("project-y",),
                source_remote_id="folder:abc123",
                remote_revision="drive-revision-41",
            )
        ],
        tmp_path / "rag",
        project_root=project_root,
    )

    metadata, _body = parse_frontmatter(tmp_path / "rag" / "documents" / "_sources" / "project-y-drive" / "roadmap.md")
    assert metadata["index_status"] == "source_changed"
    assert metadata["remote_revision"] == "drive-revision-42"
    assert metadata["indexed_revision"] == "drive-revision-41"


def test_reindex_category_documents_loads_configured_sources(
    tmp_path,
    monkeypatch,
):
    _patch_document_extraction(monkeypatch)
    project_root = tmp_path / "project"
    brain_manifest = project_root / "project-brain" / "BRAIN.yaml"
    brain_manifest.parent.mkdir(parents=True)
    brain_manifest.write_text(
        "schema_version: 1\n" "id: project-y\n" "type: project\n" "root: .\n",
        encoding="utf-8",
    )
    sources_config = project_root / "config" / "documents" / "sources.yaml"
    sources_config.parent.mkdir(parents=True)
    sources_config.write_text(
        "sources:\n"
        "  - id: project-y-drive\n"
        "    provider: google-drive\n"
        "    remote_id: folder:abc123\n"
        "    attached_brain_ids:\n"
        "      - project-y\n"
        "    remote_revision: drive-revision-42\n",
        encoding="utf-8",
    )
    cache_dir = tmp_path / "cache"
    shared_cache = cache_dir / "document-sources" / "project-y-drive"
    shared_cache.mkdir(parents=True)
    (shared_cache / "deck.md").write_text(
        "# Deck\n\nConfigured shared source body.",
        encoding="utf-8",
    )
    catalog_entry = project_root / "project-brain" / "knowledge" / "documents" / "project-y-drive" / "deck.md"
    catalog_entry.parent.mkdir(parents=True)
    catalog_entry.write_text(
        "---\n"
        "remote_id: google-drive:file:deck\n"
        "source_id: project-y-drive\n"
        "source_relative_path: deck.md\n"
        "provider: google-drive\n"
        "attached_brain_ids:\n"
        "  - project-y\n"
        "remote_revision: drive-revision-42\n"
        "---\n"
        "Configured catalog summary.\n",
        encoding="utf-8",
    )
    documents_dir = tmp_path / "Au-docs"
    documents_dir.mkdir()
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setattr(
        "src.lib.index.document_source_config.get_cache_dir",
        lambda: cache_dir,
    )
    monkeypatch.setattr(Path, "home", lambda: home_dir)

    count = reindex_category(
        "documents",
        project_root,
        tmp_path / "rag",
        documents_dir=documents_dir,
    )

    assert count == 1
    metadata, _body = parse_frontmatter(tmp_path / "rag" / "documents" / "_sources" / "project-y-drive" / "deck.md")
    assert metadata["source_id"] == "project-y-drive"
    assert metadata["source_type"] == "shared"
    assert metadata["provider"] == "google-drive"
    assert metadata["remote_id"] == "google-drive:file:deck"
    assert metadata["index_status"] == "synced"


def test_chunks_and_bm25_carry_document_attachment_metadata(
    tmp_path,
    monkeypatch,
):
    _patch_document_extraction(monkeypatch)
    source_root = tmp_path / "shared-cache"
    source_root.mkdir()
    long_doc = source_root / "architecture.md"
    long_doc.write_text(
        "# Architecture\n\n" + ("Project document content. " * 80),
        encoding="utf-8",
    )
    project_root = tmp_path / "project"
    catalog_entry = project_root / "project-brain" / "knowledge" / "documents" / "project-y-drive" / "architecture.md"
    catalog_entry.parent.mkdir(parents=True)
    catalog_entry.write_text(
        "---\n"
        "remote_id: google-drive:file:architecture\n"
        "source_id: project-y-drive\n"
        "source_relative_path: architecture.md\n"
        "provider: google-drive\n"
        "attached_brain_ids:\n"
        "  - project-y\n"
        "remote_revision: drive-revision-42\n"
        "---\n"
        "Architecture summary.\n",
        encoding="utf-8",
    )
    rag_dir = tmp_path / "rag"

    reindex_all(
        project_root,
        rag_dir,
        document_sources=[
            DocumentSource(
                id="project-y-drive",
                name="Project Y Drive",
                path=source_root,
                source_type="shared",
                provider="google-drive",
                attached_brain_ids=("project-y",),
                source_remote_id="folder:abc123",
                remote_revision="drive-revision-42",
            )
        ],
    )

    chunks = list((rag_dir / "chunks" / "documents").rglob("*.md"))
    assert chunks
    metadata, _body = parse_frontmatter(chunks[0])
    assert metadata["attached_brain_ids"] == ["project-y"]
    assert metadata["brain_id"] == "project-y"
    assert metadata["remote_id"] == "google-drive:file:architecture"
    assert metadata["index_status"] == "synced"
    assert metadata["remote_revision"] == "drive-revision-42"
    assert "catalog_title" not in metadata
    assert "catalog_summary" not in metadata

    bm25_map = json.loads((rag_dir / "_meta" / "bm25_chunk_map.json").read_text(encoding="utf-8"))
    bm25_metadata = bm25_map[0]["meta"]
    assert bm25_metadata["attached_brain_ids"] == ["project-y"]
    assert bm25_metadata["brain_id"] == "project-y"
    assert bm25_metadata["remote_id"] == "google-drive:file:architecture"
    assert bm25_metadata["index_status"] == "synced"
    assert "catalog_title" not in bm25_metadata
    assert "catalog_summary" not in bm25_metadata
