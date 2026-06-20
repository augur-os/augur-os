"""
Tests for file_metadata_extractor — extract file metadata as JSON for RAG indexing.

Module: skills/knowledge/scripts/file_metadata_extractor.py
"""

import json

import pytest


# ---------------------------------------------------------------------------
# Core extract_metadata tests
# ---------------------------------------------------------------------------


class TestExtractMetadata:
    """Tests for the extract_metadata function."""

    def test_basic_fields_always_present(self, tmp_path):
        from skills.knowledge.scripts.file_metadata_extractor import extract_metadata

        f = tmp_path / "test.txt"
        f.write_text("Hello world")
        meta = extract_metadata(str(f))
        assert meta["name"] == "test.txt"
        assert meta["type"] == "txt"
        assert meta["size_bytes"] == f.stat().st_size

    def test_unknown_extension(self, tmp_path):
        from skills.knowledge.scripts.file_metadata_extractor import extract_metadata

        f = tmp_path / "data.xyz"
        f.write_bytes(b"\x00\x01\x02")
        meta = extract_metadata(str(f))
        assert meta["type"] == "xyz"
        assert "extracted" not in meta  # No extractor for .xyz

    def test_no_extension(self, tmp_path):
        from skills.knowledge.scripts.file_metadata_extractor import extract_metadata

        f = tmp_path / "Makefile"
        f.write_text("all: build")
        meta = extract_metadata(str(f))
        assert meta["type"] == "unknown"


# ---------------------------------------------------------------------------
# Type-specific extractors
# ---------------------------------------------------------------------------


class TestTextExtractor:
    """Tests for markdown/text metadata extraction."""

    def test_text_word_and_line_count(self, tmp_path):
        from skills.knowledge.scripts.file_metadata_extractor import extract_metadata

        f = tmp_path / "readme.md"
        f.write_text("one two three\nfour five six\n")
        meta = extract_metadata(str(f))
        assert "extracted" in meta
        assert meta["extracted"]["line_count"] == 2
        assert meta["extracted"]["word_count"] == 6

    def test_empty_text_file(self, tmp_path):
        from skills.knowledge.scripts.file_metadata_extractor import extract_metadata

        f = tmp_path / "empty.txt"
        f.write_text("")
        meta = extract_metadata(str(f))
        assert meta["size_bytes"] == 0
        # Extractor may return counts of 0
        if "extracted" in meta:
            assert meta["extracted"]["word_count"] == 0


class TestCsvExtractor:
    """Tests for CSV row count extraction."""

    def test_csv_row_count(self, tmp_path):
        from skills.knowledge.scripts.file_metadata_extractor import extract_metadata

        f = tmp_path / "data.csv"
        f.write_text("name,age\nAlice,30\nBob,25\n")
        meta = extract_metadata(str(f))
        assert "extracted" in meta
        # 3 lines total, minus 1 header = 2 data rows
        assert meta["extracted"]["row_count"] == 2

    def test_csv_header_only(self, tmp_path):
        from skills.knowledge.scripts.file_metadata_extractor import extract_metadata

        f = tmp_path / "headers.csv"
        f.write_text("col1,col2\n")
        meta = extract_metadata(str(f))
        if "extracted" in meta:
            assert meta["extracted"]["row_count"] == 0


class TestJsonExtractor:
    """Tests for JSON top-level key extraction."""

    def test_json_top_level_keys(self, tmp_path):
        from skills.knowledge.scripts.file_metadata_extractor import extract_metadata

        f = tmp_path / "config.json"
        f.write_text(json.dumps({"name": "test", "version": "1.0", "items": []}))
        meta = extract_metadata(str(f))
        assert "extracted" in meta
        assert set(meta["extracted"]["keys"]) == {"name", "version", "items"}

    def test_json_array_no_keys(self, tmp_path):
        from skills.knowledge.scripts.file_metadata_extractor import extract_metadata

        f = tmp_path / "list.json"
        f.write_text(json.dumps([1, 2, 3]))
        meta = extract_metadata(str(f))
        # Array top-level returns empty extracted or no extracted key
        assert "extracted" not in meta or meta.get("extracted") == {}


class TestYamlExtractor:
    """Tests for YAML top-level key extraction."""

    def test_yaml_top_level_keys(self, tmp_path):
        from skills.knowledge.scripts.file_metadata_extractor import extract_metadata

        f = tmp_path / "config.yaml"
        f.write_text("name: test\nversion: 1.0\n")
        meta = extract_metadata(str(f))
        assert "extracted" in meta
        assert "name" in meta["extracted"]["keys"]
        assert "version" in meta["extracted"]["keys"]
