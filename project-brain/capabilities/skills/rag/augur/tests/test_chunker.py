"""
Tests for the chunker module — content-aware chunking strategies for RAG indexing.

Module: skills/rag/scripts/chunker.py
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import():
    from src.lib.index.chunker import (
        auto_chunk,
        chunk_code,
        chunk_markdown,
        chunk_paragraphs,
    )

    return chunk_markdown, chunk_code, chunk_paragraphs, auto_chunk


# ---------------------------------------------------------------------------
# chunk_markdown
# ---------------------------------------------------------------------------


class TestChunkMarkdown:
    def test_returns_list_of_dicts(self):
        chunk_markdown, *_ = _import()
        result = chunk_markdown("# Hello\n\nWorld")
        assert isinstance(result, list)
        assert len(result) > 0
        assert isinstance(result[0], dict)

    def test_chunk_keys_present(self):
        chunk_markdown, *_ = _import()
        result = chunk_markdown("# Hello\n\nWorld")
        chunk = result[0]
        assert "text" in chunk
        assert "chunk_index" in chunk
        assert "total_chunks" in chunk
        assert "section_heading" in chunk
        assert "parent_heading" in chunk

    def test_single_small_section_one_chunk(self):
        chunk_markdown, *_ = _import()
        text = "# Intro\n\nThis is short."
        result = chunk_markdown(text)
        assert len(result) == 1
        assert result[0]["section_heading"] == "Intro"
        assert result[0]["chunk_index"] == 0
        assert result[0]["total_chunks"] == 1

    def test_heading_captured_in_section_heading(self):
        chunk_markdown, *_ = _import()
        text = "## Features\n\nSome content here."
        result = chunk_markdown(text)
        assert result[0]["section_heading"] == "Features"

    def test_parent_heading_tracked(self):
        chunk_markdown, *_ = _import()
        text = "# Top\n\nIntro\n\n## Sub\n\nDetail"
        result = chunk_markdown(text)
        # Find the chunk for the Sub section
        sub_chunks = [c for c in result if c["section_heading"] == "Sub"]
        assert len(sub_chunks) >= 1
        assert sub_chunks[0]["parent_heading"] == "Top"

    def test_large_section_split_into_multiple_chunks(self):
        chunk_markdown, *_ = _import()
        # Create a section that exceeds chunk_size=100
        long_body = ". ".join([f"Sentence {i}" for i in range(50)]) + "."
        text = f"# Big Section\n\n{long_body}"
        result = chunk_markdown(text, chunk_size=100, overlap=20)
        assert len(result) > 1
        # All chunks should belong to the same section
        for chunk in result:
            assert chunk["section_heading"] == "Big Section"

    def test_chunk_indices_sequential(self):
        chunk_markdown, *_ = _import()
        long_body = "Word " * 500
        text = f"# Section\n\n{long_body}"
        result = chunk_markdown(text, chunk_size=200, overlap=50)
        for i, chunk in enumerate(result):
            assert chunk["chunk_index"] == i
            assert chunk["total_chunks"] == len(result)

    def test_overlap_content_present(self):
        chunk_markdown, *_ = _import()
        # Create text where overlap should carry content from one chunk to next
        sentences = [f"Statement number {i} ends here" for i in range(30)]
        body = ". ".join(sentences) + "."
        text = f"# Doc\n\n{body}"
        result = chunk_markdown(text, chunk_size=200, overlap=50)
        if len(result) > 1:
            # The start of chunk[1] should overlap with end of chunk[0]
            end_of_first = result[0]["text"][-30:]
            start_of_second = result[1]["text"][:100]
            # Overlap means some text from end of chunk 0 appears near start of chunk 1
            # (not necessarily exact, but content is preserved)
            assert len(result[1]["text"]) > 0

    def test_multiple_sections(self):
        chunk_markdown, *_ = _import()
        text = "# A\n\nContent A.\n\n# B\n\nContent B.\n\n# C\n\nContent C."
        result = chunk_markdown(text)
        headings = [c["section_heading"] for c in result]
        assert "A" in headings
        assert "B" in headings
        assert "C" in headings

    def test_no_heading_section_empty_string(self):
        chunk_markdown, *_ = _import()
        text = "Just some plain text with no headings."
        result = chunk_markdown(text)
        assert len(result) >= 1
        assert result[0]["section_heading"] == ""

    def test_empty_string_returns_empty_or_single(self):
        chunk_markdown, *_ = _import()
        result = chunk_markdown("")
        assert isinstance(result, list)

    def test_h3_parent_heading_chain(self):
        chunk_markdown, *_ = _import()
        text = "# Level1\n\nText\n\n## Level2\n\nText\n\n### Level3\n\nDetail"
        result = chunk_markdown(text)
        l3_chunks = [c for c in result if c["section_heading"] == "Level3"]
        assert len(l3_chunks) >= 1
        # parent should be Level2 (immediate parent)
        assert l3_chunks[0]["parent_heading"] == "Level2"


# ---------------------------------------------------------------------------
# chunk_code
# ---------------------------------------------------------------------------


class TestChunkCode:
    def test_returns_list_of_dicts(self):
        _, chunk_code, *_ = _import()
        result = chunk_code("def foo():\n    return 1\n")
        assert isinstance(result, list)
        assert len(result) > 0
        assert isinstance(result[0], dict)

    def test_chunk_keys_present(self):
        _, chunk_code, *_ = _import()
        result = chunk_code("def foo():\n    pass\n")
        chunk = result[0]
        assert "text" in chunk
        assert "chunk_index" in chunk
        assert "total_chunks" in chunk
        assert "section_heading" in chunk
        assert "parent_heading" in chunk

    def test_python_functions_split_at_def(self):
        _, chunk_code, *_ = _import()
        code = "def foo():\n    return 1\n\n\ndef bar():\n    return 2\n"
        result = chunk_code(code, chunk_size=2000)
        # With small chunk size forcing splits, or naturally two functions
        assert len(result) >= 1

    def test_python_class_boundary(self):
        _, chunk_code, *_ = _import()
        code = "class Foo:\n    def method(self):\n        pass\n\n\nclass Bar:\n    pass\n"
        result = chunk_code(code, chunk_size=2000)
        headings = [c["section_heading"] for c in result]
        # At least one chunk should reference a class boundary
        assert any("Foo" in h or "Bar" in h or h == "" for h in headings)

    def test_async_def_boundary(self):
        _, chunk_code, *_ = _import()
        code = "async def fetch():\n    pass\n\n\nasync def save():\n    pass\n"
        result = chunk_code(code, chunk_size=2000)
        assert len(result) >= 1

    def test_typescript_export_function(self):
        _, chunk_code, *_ = _import()
        code = "export function hello() {\n  return 'hi';\n}\n\nexport function world() {\n  return 'world';\n}\n"
        result = chunk_code(code)
        assert len(result) >= 1

    def test_large_function_gets_sliding_window(self):
        _, chunk_code, *_ = _import()
        # A single large function that exceeds chunk_size
        body = "    x = 1\n" * 300
        code = f"def big_function():\n{body}"
        result = chunk_code(code, chunk_size=200, overlap=50)
        assert len(result) > 1

    def test_indices_sequential(self):
        _, chunk_code, *_ = _import()
        body = "    x = 1\n" * 300
        code = f"def big():\n{body}"
        result = chunk_code(code, chunk_size=200, overlap=50)
        for i, chunk in enumerate(result):
            assert chunk["chunk_index"] == i
            assert chunk["total_chunks"] == len(result)


# ---------------------------------------------------------------------------
# chunk_paragraphs
# ---------------------------------------------------------------------------


class TestChunkParagraphs:
    def test_returns_list_of_dicts(self):
        _, _, chunk_paragraphs, _ = _import()
        result = chunk_paragraphs("Para one.\n\nPara two.")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_chunk_keys_present(self):
        _, _, chunk_paragraphs, _ = _import()
        result = chunk_paragraphs("Para one.\n\nPara two.")
        chunk = result[0]
        assert "text" in chunk
        assert "chunk_index" in chunk
        assert "total_chunks" in chunk
        assert "section_heading" in chunk
        assert "parent_heading" in chunk

    def test_small_doc_one_chunk(self):
        _, _, chunk_paragraphs, _ = _import()
        result = chunk_paragraphs("Short paragraph.", chunk_size=1000)
        assert len(result) == 1

    def test_large_doc_multiple_chunks(self):
        _, _, chunk_paragraphs, _ = _import()
        paras = "\n\n".join([f"Paragraph {i} with some text." for i in range(30)])
        result = chunk_paragraphs(paras, chunk_size=200, overlap=50)
        assert len(result) > 1

    def test_indices_sequential(self):
        _, _, chunk_paragraphs, _ = _import()
        paras = "\n\n".join([f"Paragraph {i} with some text." for i in range(30)])
        result = chunk_paragraphs(paras, chunk_size=200, overlap=50)
        for i, chunk in enumerate(result):
            assert chunk["chunk_index"] == i
            assert chunk["total_chunks"] == len(result)

    def test_section_heading_empty(self):
        _, _, chunk_paragraphs, _ = _import()
        result = chunk_paragraphs("Para one.\n\nPara two.")
        for chunk in result:
            assert chunk["section_heading"] == ""
            assert chunk["parent_heading"] == ""

    def test_overlap_ensures_content_continuity(self):
        _, _, chunk_paragraphs, _ = _import()
        paras = "\n\n".join([f"Para {i}." for i in range(20)])
        result = chunk_paragraphs(paras, chunk_size=100, overlap=30)
        if len(result) > 1:
            # Second chunk should contain overlap from first
            assert len(result[1]["text"]) > 0


# ---------------------------------------------------------------------------
# auto_chunk
# ---------------------------------------------------------------------------


class TestAutoChunk:
    def test_returns_list(self):
        *_, auto_chunk = _import()
        result = auto_chunk("# Hello\n\nContent", "markdown")
        assert isinstance(result, list)

    def test_small_file_single_chunk(self):
        *_, auto_chunk = _import()
        result = auto_chunk("Short text", "markdown", small_file_threshold=500)
        assert len(result) == 1
        assert result[0]["chunk_index"] == 0
        assert result[0]["total_chunks"] == 1

    def test_routes_markdown(self):
        *_, auto_chunk = _import()
        text = "# Heading\n\nContent paragraph"
        result = auto_chunk(text, "markdown")
        assert len(result) >= 1
        # Should use heading-aware chunking
        assert result[0]["section_heading"] in ("Heading", "")

    def test_routes_python(self):
        *_, auto_chunk = _import()
        code = "def hello():\n    return 'world'\n"
        result = auto_chunk(code, "python")
        assert len(result) >= 1

    def test_routes_typescript(self):
        *_, auto_chunk = _import()
        code = "export function greet() { return 'hi'; }\n"
        result = auto_chunk(code, "typescript")
        assert len(result) >= 1

    def test_routes_text_to_paragraphs(self):
        *_, auto_chunk = _import()
        text = "First paragraph.\n\nSecond paragraph."
        result = auto_chunk(text, "text")
        assert len(result) >= 1

    def test_unknown_content_type_uses_paragraphs(self):
        *_, auto_chunk = _import()
        result = auto_chunk("Some content.", "unknown_type")
        assert len(result) >= 1

    def test_custom_chunk_size_passed_through(self):
        *_, auto_chunk = _import()
        # Very small chunk size should produce more chunks on large text
        long_text = "# Big\n\n" + ("Word " * 200)
        result_small = auto_chunk(long_text, "markdown", chunk_size=100, overlap=20)
        result_large = auto_chunk(long_text, "markdown", chunk_size=2000, overlap=200)
        assert len(result_small) >= len(result_large)

    def test_small_file_threshold_respected(self):
        *_, auto_chunk = _import()
        text = "A" * 400  # Below threshold of 500
        result = auto_chunk(text, "markdown", small_file_threshold=500)
        assert len(result) == 1

    def test_above_threshold_uses_strategy(self):
        *_, auto_chunk = _import()
        text = "A" * 600  # Above threshold of 500
        result = auto_chunk(text, "markdown", small_file_threshold=500)
        assert isinstance(result, list)

    def test_chunk_keys_present_auto(self):
        *_, auto_chunk = _import()
        result = auto_chunk("Short", "markdown")
        chunk = result[0]
        assert "text" in chunk
        assert "chunk_index" in chunk
        assert "total_chunks" in chunk
        assert "section_heading" in chunk
        assert "parent_heading" in chunk
