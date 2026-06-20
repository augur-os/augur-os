# skills/rag/augur/tests/test_binary_extractor.py
# Tests for document extraction via unified_indexer (formerly binary_extractor).
# binary_extractor.py was deleted per ADR-518 — extraction now delegates to
# document-extractor skill via _extract_document() in unified_indexer.py.
from pathlib import Path
import pytest


def test_extract_document_for_unknown_format(tmp_path):
    """Unknown binary formats still get metadata and best-effort body."""
    from src.lib.index.unified_indexer import _extract_document

    binary = tmp_path / "file.xyz"
    binary.write_bytes(b"\x00\x01\x02")

    result = _extract_document(binary)
    assert result["format"] == "xyz"
    assert result["size_bytes"] == 3
    # MarkItDown does best-effort extraction; body may or may not be empty
    assert "body" in result


def test_extract_document_includes_timestamps(tmp_path):
    from src.lib.index.unified_indexer import _extract_document

    binary = tmp_path / "doc.pdf"
    binary.write_bytes(b"fake pdf content")

    result = _extract_document(binary)
    assert "created" in result
    assert result["format"] == "pdf"


def test_extract_text_file(tmp_path):
    """Plain text files get their content extracted."""
    from src.lib.index.unified_indexer import _extract_document

    text_file = tmp_path / "notes.txt"
    text_file.write_text("Some notes about career development")

    result = _extract_document(text_file)
    assert result["format"] == "txt"
    assert "career development" in result["body"]


def test_index_documents_creates_entries(tmp_path):
    """Integration: index a document directory into RAG."""
    from src.lib.index.unified_indexer import index_documents

    docs_dir = tmp_path / "documents" / "career" / "career"
    docs_dir.mkdir(parents=True)
    (docs_dir / "notes.txt").write_text("Some text notes about career")

    rag_dir = tmp_path / "rag"
    count = index_documents(tmp_path / "documents", rag_dir)
    assert count >= 1

    entries = list((rag_dir / "documents").rglob("*.md"))
    assert len(entries) >= 1


def test_index_documents_keeps_unreadable_media_stub(tmp_path, monkeypatch):
    """Unreadable media files should not abort the whole document reindex."""
    from src.lib.index import unified_indexer

    docs_dir = tmp_path / "documents"
    image = docs_dir / "photos" / "IMG_4688.heic"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"heic bytes")

    original_read_bytes = Path.read_bytes

    def read_bytes_or_deadlock(path: Path) -> bytes:
        if path == image:
            raise OSError(11, "Resource deadlock avoided")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes_or_deadlock)
    monkeypatch.setattr(unified_indexer, "_load_mtime_cache", lambda: {})
    monkeypatch.setattr(unified_indexer, "_save_mtime_cache", lambda _cache: None)

    rag_dir = tmp_path / "rag"
    # Media exclusion (01ff47b0e): media files produce NO documents-category
    # entry — readable or not. The property under test is that an unreadable
    # media file does not raise and does not abort the reindex.
    count = unified_indexer.index_documents(docs_dir, rag_dir)

    assert count == 0
    entry_path = rag_dir / "documents" / "photos" / "IMG_4688.md"
    assert not entry_path.exists()


def test_index_documents_prunes_orphaned_outputs_from_old_source_root(tmp_path, monkeypatch):
    """Stale rag/documents entries outside the live documents tree are removed."""
    from src.lib.index import unified_indexer

    docs_dir = tmp_path / "documents"
    live_dir = docs_dir / "brain"
    live_dir.mkdir(parents=True)
    live_file = live_dir / "notes.txt"
    live_file.write_text("Live notes", encoding="utf-8")

    rag_dir = tmp_path / "rag"
    stale_output = rag_dir / "documents" / "config" / "README.md"
    stale_output.parent.mkdir(parents=True, exist_ok=True)
    stale_output.write_text(
        "---\n"
        "type: document\n"
        "name: README\n"
        "source_path: /Users/example/Projects/Augur/config/README.md\n"
        "format: md\n"
        "---\n"
        "stale\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        unified_indexer,
        "_extract_document",
        lambda path: {
            "format": path.suffix.lstrip(".") or "txt",
            "size_bytes": path.stat().st_size,
            "created": "2026-01-01T00:00:00+00:00",
            "body": path.read_text(encoding="utf-8"),
            "extraction_error": None,
        },
    )
    monkeypatch.setattr(
        unified_indexer,
        "_load_mtime_cache",
        lambda: {
            "/Users/example/Projects/Augur/config/README.md": 1.0,
        },
    )
    monkeypatch.setattr(unified_indexer, "_save_mtime_cache", lambda _cache: None)

    count = unified_indexer.index_documents(docs_dir, rag_dir)

    assert count == 1
    assert not stale_output.exists()
    assert (rag_dir / "documents" / "brain" / "notes.md").exists()


def test_extract_document_includes_deep_understanding_fields(tmp_path, monkeypatch):
    from src.lib.index import document_understanding
    from src.lib.index.unified_indexer import _extract_document

    doc = tmp_path / "invoice.txt"
    doc.write_text("Invoice\n\nTotal due 1200 NIS\nSubmit reimbursement by Friday.", encoding="utf-8")

    result = _extract_document(doc)

    assert result["document_extraction_confidence"] in {"low", "medium", "high"}
    assert result["document_action_candidates"] == ["Submit reimbursement by Friday."]
    assert result["document_low_signal_warnings"] == []
    assert result["document_llm_assisted"] is False
    assert document_understanding.UNDERSTANDING_VERSION >= "v2"
