"""Tests for OCR extractor module.

Tests routing/caching logic only — actual OCR (pymupdf, mlx-vlm) is mocked.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

from src.lib.index.ocr_extractor import (
    detect_doc_type,
    extract_text,
    extract_with_cache,
)


# ---------------------------------------------------------------------------
# TestDocTypeDetection
# ---------------------------------------------------------------------------

class TestDocTypeDetection:
    def test_text_pdf_detected(self, tmp_path):
        """PDF files should return a valid doc type string."""
        pdf = tmp_path / "sample.pdf"
        # Minimal valid-looking PDF header; without pymupdf returns scanned_pdf
        pdf.write_bytes(b"%PDF-1.4 sample content")
        result = detect_doc_type(pdf)
        assert result in ("text_pdf", "scanned_pdf", "unknown")

    def test_image_detected(self, tmp_path):
        """PNG files should be detected as 'image'."""
        img = tmp_path / "photo.png"
        # Valid PNG header (8 magic bytes)
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
        assert detect_doc_type(img) == "image"

    def test_office_detected(self, tmp_path):
        """DOCX files (PK zip header) should be detected as 'office'."""
        docx = tmp_path / "report.docx"
        docx.write_bytes(b"PK\x03\x04" + b"\x00" * 20)
        assert detect_doc_type(docx) == "office"

    def test_html_detected(self, tmp_path):
        """HTML files should be detected as 'html'."""
        page = tmp_path / "index.html"
        page.write_text("<html><body>hello</body></html>")
        assert detect_doc_type(page) == "html"

    def test_plaintext_detected(self, tmp_path):
        """TXT files should be detected as 'plaintext'."""
        f = tmp_path / "notes.txt"
        f.write_text("hello world")
        assert detect_doc_type(f) == "plaintext"

    def test_markdown_detected(self, tmp_path):
        """.md files should be 'plaintext'."""
        f = tmp_path / "README.md"
        f.write_text("# Hello")
        assert detect_doc_type(f) == "plaintext"

    def test_unknown_extension(self, tmp_path):
        """Unrecognised extensions should return 'unknown'."""
        f = tmp_path / "file.xyz"
        f.write_bytes(b"\x00\x01\x02\x03")
        assert detect_doc_type(f) == "unknown"


# ---------------------------------------------------------------------------
# TestExtractText
# ---------------------------------------------------------------------------

class TestExtractText:
    def test_extract_plain_text(self, tmp_path):
        """Plain text extraction reads file content, method='plaintext'."""
        f = tmp_path / "note.txt"
        f.write_text("Hello, world!")
        result = extract_text(f)
        assert result["text"] == "Hello, world!"
        assert result["method"] == "plaintext"
        assert "error" not in result

    def test_extract_markdown(self, tmp_path):
        """Markdown files are extracted as plaintext."""
        f = tmp_path / "doc.md"
        f.write_text("# Title\n\nContent here.")
        result = extract_text(f)
        assert "Title" in result["text"]
        assert result["method"] == "plaintext"

    def test_extract_unknown_returns_empty(self, tmp_path):
        """Unknown binary files should return method 'plaintext' or 'failed', not crash."""
        f = tmp_path / "blob.bin"
        f.write_bytes(b"\x00\x01\x02\x03\xff\xfe")
        result = extract_text(f)
        assert result["method"] in ("plaintext", "failed", "unknown")
        # Should not raise; must always return a dict
        assert isinstance(result, dict)
        assert "text" in result


# ---------------------------------------------------------------------------
# TestCachedExtraction
# ---------------------------------------------------------------------------

class TestCachedExtraction:
    def test_cached_result_skips_extraction(self, tmp_path):
        """Second extraction of same file returns cached=True."""
        f = tmp_path / "note.txt"
        f.write_text("Cached content")
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        first = extract_with_cache(f, cache_dir)
        assert first.get("cached") is not True  # first call hits real extractor

        second = extract_with_cache(f, cache_dir)
        assert second.get("cached") is True
        assert second["text"] == first["text"]

    def test_cache_file_created(self, tmp_path):
        """Cache JSON file is written after first extraction."""
        f = tmp_path / "doc.txt"
        f.write_text("data")
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        extract_with_cache(f, cache_dir)
        cache_files = list(cache_dir.glob("*.json"))
        assert len(cache_files) == 1

    def test_cache_key_based_on_content(self, tmp_path):
        """Different file content → different cache entry."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        f1 = tmp_path / "a.txt"
        f1.write_text("content A")
        f2 = tmp_path / "b.txt"
        f2.write_text("content B")

        extract_with_cache(f1, cache_dir)
        extract_with_cache(f2, cache_dir)

        cache_files = list(cache_dir.glob("*.json"))
        assert len(cache_files) == 2
