"""Tests for documents-category hygiene: SKILL.md and media-file exclusions.

Spec (2026-06-11-content-cleanup, Task 3):
- SKILL.md (case-insensitive) under a document source dir must NOT be indexed.
- Media files (image/audio/video extensions) must produce NO documents-category
  entry — the exclusion lives at the documents INDEXER, not in the shared
  should_index_source_file() helper, because the ingest-discovery LISTING tool
  (list_knowledge_hub_files_impl) shares that helper and must keep showing media.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.lib.index import unified_indexer
from src.lib.index.document_sources import (
    DocumentSource,
    should_index_source_file,
)
from src.lib.index.unified_indexer import index_document_sources


def _source(root: Path) -> DocumentSource:
    return DocumentSource(id="docs", name="Au-docs", path=root)


def _patch_document_extraction(monkeypatch) -> None:
    """Mirror the harness in test_document_index_attachments.py."""

    def fake_extract(path: Path) -> dict[str, object]:
        body = path.read_text(encoding="utf-8", errors="ignore")
        return {
            "format": path.suffix.lower().lstrip(".") or "md",
            "size_bytes": path.stat().st_size,
            "created": "2026-06-11T08:00:00+00:00",
            "body": body,
            "document_title": path.stem.replace("-", " ").title(),
            "document_kind": "document",
            "document_summary": "test summary",
            "document_key_insights": [],
            "document_sections": [],
            "document_extraction_method": "test",
            "document_visual_structure_used": False,
            "document_understanding_version": "v2",
            "document_action_candidates": [],
            "document_extraction_confidence": "high",
            "document_low_signal_warnings": [],
            "document_llm_assisted": False,
        }

    monkeypatch.setattr(unified_indexer, "_extract_document", fake_extract)
    monkeypatch.setattr(unified_indexer, "_load_mtime_cache", lambda: {})
    monkeypatch.setattr(unified_indexer, "_save_mtime_cache", lambda _cache: None)


def _indexed_stems(rag_dir: Path) -> set[str]:
    return {path.stem for path in (rag_dir / "documents").rglob("*.md")}


# ---------------------------------------------------------------------------
# SKILL.md exclusion (helper-level: SKILL.md is not a source document for
# listings either, so the guard lives in should_index_source_file)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filename", ["SKILL.md", "skill.md", "Skill.md"])
def test_skill_md_not_indexed_case_insensitive(tmp_path: Path, filename: str) -> None:
    root = tmp_path / "Au-docs"
    root.mkdir()
    skill_file = root / filename
    skill_file.write_text("name: test\n---\n# Skill\n", encoding="utf-8")

    assert should_index_source_file(skill_file, _source(root)) is False


def test_skill_md_in_subdir_not_indexed(tmp_path: Path) -> None:
    root = tmp_path / "Au-docs"
    subdir = root / "my-skill"
    subdir.mkdir(parents=True)
    skill_file = subdir / "SKILL.md"
    skill_file.write_text("name: test\n---\n# Skill\n", encoding="utf-8")

    assert should_index_source_file(skill_file, _source(root)) is False


def test_regular_md_in_same_dir_still_indexed(tmp_path: Path) -> None:
    """SKILL.md exclusion must not block regular .md files."""
    root = tmp_path / "Au-docs"
    root.mkdir()
    doc = root / "README.md"
    doc.write_text("# Readme\n", encoding="utf-8")

    assert should_index_source_file(doc, _source(root)) is True


def test_skill_md_produces_no_documents_entry(tmp_path: Path, monkeypatch) -> None:
    """Scanner-level: SKILL.md never reaches the documents index."""
    _patch_document_extraction(monkeypatch)
    root = tmp_path / "Au-docs"
    sub = root / "video"
    sub.mkdir(parents=True)
    (sub / "SKILL.md").write_text("name: video\n---\n# Video skill\n", encoding="utf-8")
    (root / "report.md").write_text("# Report\n\nReal document body.", encoding="utf-8")
    rag_dir = tmp_path / "rag"

    count = index_document_sources([_source(root)], rag_dir)

    stems = _indexed_stems(rag_dir)
    assert count == 1
    assert "report" in stems
    assert "skill" not in {s.lower() for s in stems}


# ---------------------------------------------------------------------------
# Media-file exclusion — INDEXER-level. The shared listing helper must keep
# showing media; only the documents-category index drops them.
# ---------------------------------------------------------------------------

MEDIA_FILES = [
    ("photo.png", "image"),
    ("scan.jpg", "image"),
    ("snapshot.jpeg", "image"),
    ("icon.gif", "image"),
    ("hero.webp", "image"),
    ("portrait.heic", "image"),
    ("voice.m4a", "audio"),
    ("podcast.mp3", "audio"),
    ("recording.wav", "audio"),
    ("clip.flac", "audio"),
    ("track.aac", "audio"),
    ("meeting.mp4", "video"),
    ("screen.mov", "video"),
    ("demo.webm", "video"),
    ("lesson.m4v", "video"),
]


def test_media_files_produce_no_documents_entries(tmp_path: Path, monkeypatch) -> None:
    """Scanner-level: media files yield NO documents-category entry (no media-stub)."""
    _patch_document_extraction(monkeypatch)
    root = tmp_path / "Au-docs"
    root.mkdir()
    for filename, _kind in MEDIA_FILES:
        (root / filename).write_bytes(b"\x00\x01\x02\x03")
    (root / "report.md").write_text("# Report\n\nReal document body.", encoding="utf-8")
    (root / "notes.txt").write_text("Some notes\n", encoding="utf-8")
    rag_dir = tmp_path / "rag"

    count = index_document_sources([_source(root)], rag_dir)

    stems = _indexed_stems(rag_dir)
    assert count == 2, f"only the two real documents should be indexed, got {count}: {stems}"
    assert stems == {"report", "notes"}
    media_stems = {Path(filename).stem for filename, _ in MEDIA_FILES}
    assert not (stems & media_stems)
    # And no media-stub bodies anywhere in the output
    for entry in (rag_dir / "documents").rglob("*.md"):
        assert "media-stub" not in entry.read_text(encoding="utf-8", errors="ignore")


@pytest.mark.parametrize("filename,ext_kind", MEDIA_FILES)
def test_media_files_stay_visible_to_source_listing(tmp_path: Path, filename: str, ext_kind: str) -> None:
    """The shared listing helper keeps media files (ingest discovery depends on it)."""
    root = tmp_path / "Au-docs"
    root.mkdir()
    media_file = root / filename
    media_file.write_bytes(b"\x00\x01\x02\x03")

    result = should_index_source_file(media_file, _source(root))
    assert result is True, (
        f"{filename} ({ext_kind}) must stay visible to source-file listings: "
        f"should_index_source_file returned {result}"
    )


def test_pdf_still_indexed(tmp_path: Path, monkeypatch) -> None:
    """Ensure media exclusion doesn't block document types at the indexer."""
    _patch_document_extraction(monkeypatch)
    root = tmp_path / "Au-docs"
    root.mkdir()
    (root / "report.pdf").write_bytes(b"%PDF-1.4 ...")
    rag_dir = tmp_path / "rag"

    count = index_document_sources([_source(root)], rag_dir)

    assert count == 1
    assert "report" in _indexed_stems(rag_dir)
