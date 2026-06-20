# Contextual Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance Augur's RAG with contextual chunk enrichment (Ollama/Qwen 3.5), BM25 scoring, and hybrid retrieval to reduce retrieval failures by 49-67%.

**Architecture:** New modules slot into the existing nightly indexing pipeline. After category scanners produce raw entries, three new phases run: chunking (all categories), contextual enrichment (Ollama), and BM25 index build. At query time, BM25 runs alongside ripgrep, results merge via Reciprocal Rank Fusion, then the existing LLM reranker produces final results.

**Tech Stack:** Python 3.11+, `rank_bm25` (BM25 scoring), `httpx` (Ollama API, already a dependency), `mlx-vlm` (Apple MLX OCR), existing `src.lib.frontmatter_utils`

---

## File Structure

**New files:**

| File | Responsibility |
|------|---------------|
| `skills/rag/scripts/chunker.py` | Content-aware chunking strategies: markdown heading-aware, code boundary, paragraph sliding window |
| `skills/rag/scripts/contextualizer.py` | Ollama client wrapper, prompt template, batch contextualization with checksum caching |
| `skills/rag/scripts/bm25_index.py` | Build, serialize, load, and query BM25 index over enriched chunks |
| `skills/rag/scripts/retrieval.py` | Hybrid retrieval: parallel ripgrep + BM25, RRF fusion, deduplication |
| `skills/rag/scripts/ocr_extractor.py` | Apple MLX OCR pipeline with pymupdf fallback for text PDFs |
| `skills/rag/augur/tests/test_chunker.py` | Tests for all chunking strategies |
| `skills/rag/augur/tests/test_contextualizer.py` | Tests for Ollama contextualization (mocked) |
| `skills/rag/augur/tests/test_bm25_index.py` | Tests for BM25 build, serialize, load, query |
| `skills/rag/augur/tests/test_retrieval.py` | Tests for hybrid retrieval and RRF fusion |
| `skills/rag/augur/tests/test_ocr_extractor.py` | Tests for OCR pipeline detection and fallback |
| `skills/rag/assets/seeds/quality_baseline.yaml` | 20 test queries for before/after comparison |

**Modified files:**

| File | Change |
|------|--------|
| `skills/rag/scripts/unified_indexer.py` | Add chunking + contextualization + BM25 build phases after category scans |
| `skills/rag/scripts/search_engine.py` | Accept BM25 results alongside ripgrep, add RRF merge before LLM rerank |
| `skills/rag/scripts/mcp/rag_tools.py` | Wire hybrid retrieval into `search-skill-knowledge`, add BM25 stats to `rag-status` |
| `config/defaults/config/system/preferences.yaml` | Add `rag:` configuration section |
| `pyproject.toml` | Add `rank_bm25` dependency |

---

### Task 1: Add `rank_bm25` dependency

**Files:**
- Modify: `pyproject.toml:22-34`

- [ ] **Step 1: Add rank_bm25 to dependencies**

In `pyproject.toml`, add `rank_bm25` to the dependencies list:

```python
# In the dependencies array, after "markitdown-ocr>=0.1.0",
"rank-bm25>=0.2.2",
```

Also add `mlx-vlm` as an optional dependency for Apple Silicon OCR. In the `[project.optional-dependencies]` section, add:

```toml
ocr = [
    "mlx-vlm>=0.1.0",
    "pymupdf>=1.24.0",
]
```

- [ ] **Step 2: Add RAG config to preferences**

In `config/defaults/config/system/preferences.yaml`, add the `rag:` section after the existing `airplane_mode:` block:

```yaml
rag:
  chunk_size: 1500
  chunk_overlap: 200
  document_chunk_size: 1000
  code_chunk_size: 2000
  code_chunk_overlap: 100
  small_file_threshold: 500
  bm25_top_k: 50
  rrf_k: 60
  final_top_k: 10
  contextualization:
    enabled: true
    model: qwen3.5:9b
    max_context_tokens: 100
    ollama_url: "http://localhost:11434"
  ocr:
    enabled: true
    backend: mlx
```

- [ ] **Step 3: Install and verify**

Run: `cd ~/Projects/Augur && uv sync`
Expected: rank_bm25 installs successfully

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml config/defaults/config/system/preferences.yaml
git commit -m "feat(rag): add rank_bm25 dependency and RAG config defaults"
```

---

### Task 2: Chunker module

**Files:**
- Create: `skills/rag/scripts/chunker.py`
- Test: `skills/rag/augur/tests/test_chunker.py`

- [ ] **Step 1: Write failing tests for markdown chunking**

Create `skills/rag/augur/tests/test_chunker.py`:

```python
"""Tests for content-aware chunking strategies."""

import pytest


class TestMarkdownChunker:
    """Heading-aware sliding window for markdown content."""

    def test_small_file_returns_single_chunk(self):
        from plugins.ai.skills.rag.scripts.chunker import chunk_markdown

        text = "# Title\n\nShort content."
        chunks = chunk_markdown(text, chunk_size=1500, overlap=200)
        assert len(chunks) == 1
        assert chunks[0]["text"] == text
        assert chunks[0]["chunk_index"] == 0
        assert chunks[0]["total_chunks"] == 1

    def test_splits_at_heading_boundaries(self):
        from plugins.ai.skills.rag.scripts.chunker import chunk_markdown

        text = "# Title\n\nIntro paragraph.\n\n## Section A\n\n" + ("A content. " * 200) + "\n\n## Section B\n\n" + ("B content. " * 200)
        chunks = chunk_markdown(text, chunk_size=500, overlap=100)
        assert len(chunks) >= 3
        # Each chunk should carry heading metadata
        assert chunks[0]["section_heading"] == "Title"

    def test_long_section_uses_sliding_window(self):
        from plugins.ai.skills.rag.scripts.chunker import chunk_markdown

        # One heading, very long body — must split within section
        text = "# Only Section\n\n" + ("Word " * 1000)
        chunks = chunk_markdown(text, chunk_size=500, overlap=100)
        assert len(chunks) > 1
        # Verify overlap: end of chunk N overlaps with start of chunk N+1
        if len(chunks) >= 2:
            end_of_first = chunks[0]["text"][-100:]
            assert end_of_first in chunks[1]["text"]

    def test_overlap_content_present(self):
        from plugins.ai.skills.rag.scripts.chunker import chunk_markdown

        text = "# Head\n\n" + ("The quick brown fox jumps. " * 100)
        chunks = chunk_markdown(text, chunk_size=300, overlap=50)
        if len(chunks) >= 2:
            # Last 50 chars of chunk 0 should appear in chunk 1
            tail = chunks[0]["text"][-50:]
            assert tail in chunks[1]["text"]

    def test_parent_heading_tracked(self):
        from plugins.ai.skills.rag.scripts.chunker import chunk_markdown

        text = "# Top\n\n## Sub\n\nContent here.\n\n### SubSub\n\nDeep content."
        chunks = chunk_markdown(text, chunk_size=5000, overlap=0)
        # Find the chunk containing "Deep content"
        deep_chunk = [c for c in chunks if "Deep content" in c["text"]]
        assert len(deep_chunk) == 1
        assert deep_chunk[0]["parent_heading"] == "Sub"

    def test_metadata_fields_present(self):
        from plugins.ai.skills.rag.scripts.chunker import chunk_markdown

        text = "# Title\n\nBody text."
        chunks = chunk_markdown(text, chunk_size=5000, overlap=0)
        chunk = chunks[0]
        assert "text" in chunk
        assert "chunk_index" in chunk
        assert "total_chunks" in chunk
        assert "section_heading" in chunk
        assert "parent_heading" in chunk


class TestCodeChunker:
    """Function/class boundary detection for code files."""

    def test_splits_python_at_function_boundaries(self):
        from plugins.ai.skills.rag.scripts.chunker import chunk_code

        code = (
            "import os\n\n"
            "def function_a():\n    " + "\n    ".join(f"x = {i}" for i in range(60)) + "\n\n"
            "def function_b():\n    " + "\n    ".join(f"y = {i}" for i in range(60)) + "\n"
        )
        chunks = chunk_code(code, chunk_size=500, overlap=100)
        assert len(chunks) >= 2

    def test_small_code_file_single_chunk(self):
        from plugins.ai.skills.rag.scripts.chunker import chunk_code

        code = "def hello():\n    return 'world'\n"
        chunks = chunk_code(code, chunk_size=2000, overlap=100)
        assert len(chunks) == 1

    def test_typescript_class_boundaries(self):
        from plugins.ai.skills.rag.scripts.chunker import chunk_code

        code = (
            "export class Foo {\n" + "  method() { " + "x = 1;\n" * 80 + "}\n}\n\n"
            "export class Bar {\n" + "  method() { " + "y = 1;\n" * 80 + "}\n}\n"
        )
        chunks = chunk_code(code, chunk_size=500, overlap=100)
        assert len(chunks) >= 2


class TestParagraphChunker:
    """Paragraph-based sliding window for extracted documents."""

    def test_splits_on_paragraph_boundaries(self):
        from plugins.ai.skills.rag.scripts.chunker import chunk_paragraphs

        paragraphs = "\n\n".join(f"Paragraph {i}. " + "Content. " * 30 for i in range(10))
        chunks = chunk_paragraphs(paragraphs, chunk_size=500, overlap=100)
        assert len(chunks) >= 3

    def test_single_paragraph_single_chunk(self):
        from plugins.ai.skills.rag.scripts.chunker import chunk_paragraphs

        text = "Short paragraph."
        chunks = chunk_paragraphs(text, chunk_size=1000, overlap=200)
        assert len(chunks) == 1

    def test_overlap_between_paragraph_chunks(self):
        from plugins.ai.skills.rag.scripts.chunker import chunk_paragraphs

        paragraphs = "\n\n".join(f"Paragraph {i} with enough text to matter. " * 10 for i in range(5))
        chunks = chunk_paragraphs(paragraphs, chunk_size=300, overlap=80)
        if len(chunks) >= 2:
            tail = chunks[0]["text"][-80:]
            assert tail in chunks[1]["text"]


class TestAutoChunk:
    """Dispatcher that selects strategy based on content type."""

    def test_markdown_file_uses_markdown_strategy(self):
        from plugins.ai.skills.rag.scripts.chunker import auto_chunk

        text = "# Heading\n\nContent."
        chunks = auto_chunk(text, content_type="markdown")
        assert len(chunks) >= 1

    def test_code_file_uses_code_strategy(self):
        from plugins.ai.skills.rag.scripts.chunker import auto_chunk

        text = "def foo():\n    pass\n"
        chunks = auto_chunk(text, content_type="code")
        assert len(chunks) >= 1

    def test_document_uses_paragraph_strategy(self):
        from plugins.ai.skills.rag.scripts.chunker import auto_chunk

        text = "First paragraph.\n\nSecond paragraph."
        chunks = auto_chunk(text, content_type="document")
        assert len(chunks) >= 1

    def test_small_file_no_chunking(self):
        from plugins.ai.skills.rag.scripts.chunker import auto_chunk

        text = "Tiny."
        chunks = auto_chunk(text, content_type="markdown", small_file_threshold=500)
        assert len(chunks) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/test_chunker.py -v --no-header 2>&1 | head -40`
Expected: All tests FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement chunker.py**

Create `skills/rag/scripts/chunker.py`:

```python
"""Content-aware chunking strategies for RAG indexing.

Three strategies:
  - chunk_markdown: heading-aware sliding window for .md files
  - chunk_code: function/class boundary detection for .py/.ts files
  - chunk_paragraphs: paragraph-based sliding window for extracted documents
  - auto_chunk: dispatcher that selects strategy based on content_type
"""

from __future__ import annotations

import re


def _sliding_window(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping windows of approximately chunk_size chars."""
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            chunks.append(text[start:])
            break

        # Try to break at a sentence boundary near the end
        search_start = max(end - 100, start)
        last_period = text.rfind(". ", search_start, end)
        last_newline = text.rfind("\n", search_start, end)
        break_at = max(last_period + 2 if last_period > 0 else -1,
                       last_newline + 1 if last_newline > 0 else -1)
        if break_at > start:
            end = break_at

        chunks.append(text[start:end])
        start = end - overlap

    return chunks


def _parse_heading_level(line: str) -> int:
    """Return heading level (1-6) or 0 if not a heading."""
    m = re.match(r"^(#{1,6})\s", line)
    return len(m.group(1)) if m else 0


def chunk_markdown(
    text: str,
    chunk_size: int = 1500,
    overlap: int = 200,
) -> list[dict]:
    """Split markdown text using heading-aware sliding window.

    Prefers to break at heading boundaries. Falls back to sliding window
    for long sections without subheadings. Each chunk carries metadata:
    text, chunk_index, total_chunks, section_heading, parent_heading.
    """
    if len(text) <= chunk_size:
        heading = ""
        for line in text.split("\n"):
            if _parse_heading_level(line):
                heading = line.lstrip("#").strip()
                break
        return [{
            "text": text,
            "chunk_index": 0,
            "total_chunks": 1,
            "section_heading": heading or "preamble",
            "parent_heading": "",
        }]

    # Parse into sections by heading
    lines = text.split("\n")
    sections: list[dict] = []
    current_lines: list[str] = []
    current_heading = "preamble"
    heading_stack: list[tuple[int, str]] = []  # (level, name)

    for line in lines:
        level = _parse_heading_level(line)
        if level > 0:
            # Flush current section
            if current_lines:
                parent = heading_stack[-1][1] if heading_stack else ""
                sections.append({
                    "heading": current_heading,
                    "parent": parent,
                    "text": "\n".join(current_lines),
                })

            heading_name = line.lstrip("#").strip()
            # Update heading stack
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            parent = heading_stack[-1][1] if heading_stack else ""
            heading_stack.append((level, heading_name))
            current_heading = heading_name
            current_lines = [line]
        else:
            current_lines.append(line)

    # Flush last section
    if current_lines:
        parent = heading_stack[-1][1] if len(heading_stack) > 1 else (heading_stack[0][1] if heading_stack else "")
        # Parent should be the heading above current, not current itself
        parent_for_last = ""
        if len(heading_stack) >= 2:
            parent_for_last = heading_stack[-2][1]
        elif heading_stack:
            parent_for_last = ""
        sections.append({
            "heading": current_heading,
            "parent": parent_for_last,
            "text": "\n".join(current_lines),
        })

    # Now chunk each section, splitting long ones with sliding window
    raw_chunks: list[dict] = []
    for section in sections:
        section_text = section["text"].strip()
        if not section_text:
            continue

        if len(section_text) <= chunk_size:
            raw_chunks.append({
                "text": section_text,
                "section_heading": section["heading"],
                "parent_heading": section["parent"],
            })
        else:
            windows = _sliding_window(section_text, chunk_size, overlap)
            for window in windows:
                raw_chunks.append({
                    "text": window,
                    "section_heading": section["heading"],
                    "parent_heading": section["parent"],
                })

    # Add index metadata
    total = len(raw_chunks)
    for i, chunk in enumerate(raw_chunks):
        chunk["chunk_index"] = i
        chunk["total_chunks"] = total

    return raw_chunks if raw_chunks else [{
        "text": text,
        "chunk_index": 0,
        "total_chunks": 1,
        "section_heading": "preamble",
        "parent_heading": "",
    }]


# Patterns for code boundary detection
_PY_BOUNDARY = re.compile(r"^(?:def |class |async def )", re.MULTILINE)
_TS_BOUNDARY = re.compile(
    r"^(?:export\s+)?(?:function |class |const \w+ = |async function |export default )",
    re.MULTILINE,
)


def chunk_code(
    text: str,
    chunk_size: int = 2000,
    overlap: int = 100,
) -> list[dict]:
    """Split code at function/class boundaries with overlap fallback."""
    if len(text) <= chunk_size:
        return [{
            "text": text,
            "chunk_index": 0,
            "total_chunks": 1,
            "section_heading": "full_file",
            "parent_heading": "",
        }]

    # Try Python boundaries first, then TypeScript
    boundaries = [m.start() for m in _PY_BOUNDARY.finditer(text)]
    if not boundaries:
        boundaries = [m.start() for m in _TS_BOUNDARY.finditer(text)]

    if not boundaries:
        # No recognizable boundaries — fall back to sliding window
        windows = _sliding_window(text, chunk_size, overlap)
        return [{
            "text": w,
            "chunk_index": i,
            "total_chunks": len(windows),
            "section_heading": f"segment_{i}",
            "parent_heading": "",
        } for i, w in enumerate(windows)]

    # Always include start of file
    if boundaries[0] != 0:
        boundaries.insert(0, 0)

    raw_chunks: list[dict] = []
    for idx in range(len(boundaries)):
        start = boundaries[idx]
        end = boundaries[idx + 1] if idx + 1 < len(boundaries) else len(text)
        segment = text[start:end].rstrip()

        if not segment.strip():
            continue

        if len(segment) <= chunk_size:
            raw_chunks.append({
                "text": segment,
                "section_heading": segment.split("\n")[0].strip()[:80],
                "parent_heading": "",
            })
        else:
            windows = _sliding_window(segment, chunk_size, overlap)
            for w in windows:
                raw_chunks.append({
                    "text": w,
                    "section_heading": segment.split("\n")[0].strip()[:80],
                    "parent_heading": "",
                })

    total = len(raw_chunks)
    for i, chunk in enumerate(raw_chunks):
        chunk["chunk_index"] = i
        chunk["total_chunks"] = total

    return raw_chunks


def chunk_paragraphs(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200,
) -> list[dict]:
    """Split text at paragraph boundaries (double newlines) with overlap."""
    if len(text) <= chunk_size:
        return [{
            "text": text,
            "chunk_index": 0,
            "total_chunks": 1,
            "section_heading": "document",
            "parent_heading": "",
        }]

    paragraphs = re.split(r"\n\n+", text)
    raw_chunks: list[dict] = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        candidate = (current_chunk + "\n\n" + para).strip() if current_chunk else para

        if len(candidate) <= chunk_size:
            current_chunk = candidate
        else:
            if current_chunk:
                raw_chunks.append({"text": current_chunk})
            # If single paragraph exceeds chunk_size, split it
            if len(para) > chunk_size:
                windows = _sliding_window(para, chunk_size, overlap)
                for w in windows:
                    raw_chunks.append({"text": w})
                current_chunk = ""
            else:
                current_chunk = para

    if current_chunk:
        raw_chunks.append({"text": current_chunk})

    # Add overlap between paragraph chunks
    if overlap > 0 and len(raw_chunks) > 1:
        overlapped: list[dict] = [raw_chunks[0]]
        for i in range(1, len(raw_chunks)):
            prev_text = raw_chunks[i - 1]["text"]
            overlap_text = prev_text[-overlap:] if len(prev_text) > overlap else prev_text
            overlapped.append({"text": overlap_text + raw_chunks[i]["text"]})
        raw_chunks = overlapped

    total = len(raw_chunks)
    for i, chunk in enumerate(raw_chunks):
        chunk["chunk_index"] = i
        chunk["total_chunks"] = total
        chunk["section_heading"] = "document"
        chunk["parent_heading"] = ""

    return raw_chunks


def auto_chunk(
    text: str,
    content_type: str = "markdown",
    chunk_size: int | None = None,
    overlap: int | None = None,
    small_file_threshold: int = 500,
) -> list[dict]:
    """Dispatch to the appropriate chunking strategy.

    Args:
        text: Content to chunk.
        content_type: One of "markdown", "code", "document".
        chunk_size: Override default chunk size for the content type.
        overlap: Override default overlap for the content type.
        small_file_threshold: Files smaller than this are returned as a single chunk.
    """
    if len(text) <= small_file_threshold:
        return [{
            "text": text,
            "chunk_index": 0,
            "total_chunks": 1,
            "section_heading": "full_file",
            "parent_heading": "",
        }]

    if content_type == "markdown":
        return chunk_markdown(text, chunk_size=chunk_size or 1500, overlap=overlap or 200)
    elif content_type == "code":
        return chunk_code(text, chunk_size=chunk_size or 2000, overlap=overlap or 100)
    elif content_type == "document":
        return chunk_paragraphs(text, chunk_size=chunk_size or 1000, overlap=overlap or 200)
    else:
        return chunk_markdown(text, chunk_size=chunk_size or 1500, overlap=overlap or 200)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/test_chunker.py -v --no-header 2>&1 | tail -25`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/rag/scripts/chunker.py skills/rag/augur/tests/test_chunker.py
git commit -m "feat(rag): add content-aware chunking strategies"
```

---

### Task 3: Contextualizer module

**Files:**
- Create: `skills/rag/scripts/contextualizer.py`
- Test: `skills/rag/augur/tests/test_contextualizer.py`

- [ ] **Step 1: Write failing tests**

Create `skills/rag/augur/tests/test_contextualizer.py`:

```python
"""Tests for Ollama-powered contextual enrichment."""

from unittest.mock import MagicMock, patch
import json
import pytest


class TestContextualizer:
    """Tests for the Contextualizer class."""

    def test_generate_context_returns_string(self):
        from plugins.ai.skills.rag.scripts.contextualizer import Contextualizer

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "This chunk describes the RAG configuration."}

        with patch("httpx.post", return_value=mock_response):
            ctx = Contextualizer(model="qwen3.5:9b", ollama_url="http://localhost:11434")
            result = ctx.generate_context(
                document_text="# RAG Skill\n\nThe RAG skill provides search.",
                chunk_text="- Circuit breaker: 3 failures",
            )
            assert isinstance(result, str)
            assert len(result) > 0

    def test_ollama_down_returns_empty(self):
        from plugins.ai.skills.rag.scripts.contextualizer import Contextualizer

        with patch("httpx.post", side_effect=Exception("Connection refused")):
            ctx = Contextualizer(model="qwen3.5:9b", ollama_url="http://localhost:11434")
            result = ctx.generate_context(
                document_text="# Doc",
                chunk_text="Content",
            )
            assert result == ""

    def test_circuit_breaker_opens_after_failures(self):
        from plugins.ai.skills.rag.scripts.contextualizer import Contextualizer

        with patch("httpx.post", side_effect=Exception("Connection refused")):
            ctx = Contextualizer(model="qwen3.5:9b", ollama_url="http://localhost:11434")
            # Trigger 3 failures
            for _ in range(3):
                ctx.generate_context(document_text="# Doc", chunk_text="Content")
            assert ctx._circuit_open


class TestBatchContextualizer:
    """Tests for batch processing of chunks."""

    def test_batch_enriches_chunks(self):
        from plugins.ai.skills.rag.scripts.contextualizer import Contextualizer

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Context sentence."}

        with patch("httpx.post", return_value=mock_response):
            ctx = Contextualizer(model="qwen3.5:9b", ollama_url="http://localhost:11434")
            chunks = [
                {"text": "Chunk A content", "section_heading": "A", "parent_heading": ""},
                {"text": "Chunk B content", "section_heading": "B", "parent_heading": ""},
            ]
            enriched = ctx.enrich_chunks(
                document_text="# Full Document\n\nContent.",
                chunks=chunks,
            )
            assert len(enriched) == 2
            assert "context" in enriched[0]
            assert enriched[0]["context"] == "Context sentence."

    def test_checksum_cache_skips_unchanged(self):
        from plugins.ai.skills.rag.scripts.contextualizer import Contextualizer

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Generated context."}

        with patch("httpx.post", return_value=mock_response) as mock_post:
            ctx = Contextualizer(model="qwen3.5:9b", ollama_url="http://localhost:11434")
            chunks = [{"text": "Same content", "section_heading": "A", "parent_heading": ""}]

            # First call generates context
            enriched1 = ctx.enrich_chunks(document_text="# Doc", chunks=chunks)
            call_count_after_first = mock_post.call_count

            # Second call with same content should use cache
            enriched2 = ctx.enrich_chunks(document_text="# Doc", chunks=chunks)
            assert mock_post.call_count == call_count_after_first
            assert enriched2[0]["context"] == enriched1[0]["context"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/test_contextualizer.py -v --no-header 2>&1 | head -20`
Expected: All tests FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement contextualizer.py**

Create `skills/rag/scripts/contextualizer.py`:

```python
"""Ollama-powered contextual enrichment for RAG chunks.

For each chunk, generates a 1-2 sentence context that situates it within
its source document using the local Ollama LLM (Qwen 3.5 9B by default).
"""

from __future__ import annotations

import hashlib
import logging
import time

import httpx

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
<document>
{document_text}
</document>

Here is a chunk from that document:
<chunk>
{chunk_text}
</chunk>

Write a short (1-2 sentence) context that situates this chunk within the document.
Include: what document/skill this is from, what section, and what the chunk specifically covers.
Do not repeat the chunk content. Only provide the context sentence(s)."""

_CIRCUIT_BREAKER_THRESHOLD = 3
_CIRCUIT_BREAKER_COOLDOWN = 300  # seconds


class Contextualizer:
    """Generate contextual prefixes for RAG chunks via Ollama."""

    def __init__(
        self,
        model: str = "qwen3.5:9b",
        ollama_url: str = "http://localhost:11434",
        max_doc_chars: int = 3000,
        max_context_tokens: int = 100,
    ):
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")
        self.max_doc_chars = max_doc_chars
        self.max_context_tokens = max_context_tokens
        self._cache: dict[str, str] = {}
        self._failure_count = 0
        self._circuit_open = False
        self._circuit_opened_at: float | None = None

    def _check_circuit(self) -> bool:
        """Return True if circuit breaker is open (should skip calls)."""
        if not self._circuit_open:
            return False
        if self._circuit_opened_at and (time.monotonic() - self._circuit_opened_at) >= _CIRCUIT_BREAKER_COOLDOWN:
            self._circuit_open = False
            self._failure_count = 0
            self._circuit_opened_at = None
            return False
        return True

    def _record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= _CIRCUIT_BREAKER_THRESHOLD:
            self._circuit_open = True
            self._circuit_opened_at = time.monotonic()
            logger.warning("Contextualizer circuit breaker opened after %d failures", self._failure_count)

    def _record_success(self) -> None:
        self._failure_count = 0
        self._circuit_open = False
        self._circuit_opened_at = None

    def _chunk_hash(self, chunk_text: str) -> str:
        return hashlib.md5(chunk_text.encode(), usedforsecurity=False).hexdigest()

    def generate_context(self, document_text: str, chunk_text: str) -> str:
        """Generate a contextual prefix for a single chunk.

        Returns empty string on failure (circuit open, Ollama down, etc.).
        """
        if self._check_circuit():
            return ""

        # Check cache
        cache_key = self._chunk_hash(chunk_text)
        if cache_key in self._cache:
            return self._cache[cache_key]

        prompt = _PROMPT_TEMPLATE.format(
            document_text=document_text[: self.max_doc_chars],
            chunk_text=chunk_text,
        )

        try:
            response = httpx.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": self.max_context_tokens,
                        "temperature": 0.3,
                    },
                },
                timeout=60.0,
            )
            response.raise_for_status()
            context = response.json().get("response", "").strip()
            self._record_success()
            self._cache[cache_key] = context
            return context
        except Exception as e:
            logger.warning("Ollama contextualization failed: %s", e)
            self._record_failure()
            return ""

    def enrich_chunks(
        self,
        document_text: str,
        chunks: list[dict],
    ) -> list[dict]:
        """Enrich a list of chunks with contextual prefixes.

        Modifies chunks in-place, adding a 'context' field.
        Returns the same list for chaining.
        """
        for chunk in chunks:
            cache_key = self._chunk_hash(chunk["text"])
            if cache_key in self._cache:
                chunk["context"] = self._cache[cache_key]
                continue

            context = self.generate_context(document_text, chunk["text"])
            chunk["context"] = context

        return chunks

    def save_cache(self, path: "str | None" = None) -> None:
        """Persist the context cache to disk."""
        import json
        from pathlib import Path
        from src.config.paths import get_runtime_dir

        cache_path = Path(path) if path else get_runtime_dir() / "adaptive" / "rag_context_cache.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(self._cache), encoding="utf-8")

    def load_cache(self, path: "str | None" = None) -> None:
        """Load a previously saved context cache."""
        import json
        from pathlib import Path
        from src.config.paths import get_runtime_dir

        cache_path = Path(path) if path else get_runtime_dir() / "adaptive" / "rag_context_cache.json"
        if cache_path.exists():
            try:
                self._cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._cache = {}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/test_contextualizer.py -v --no-header 2>&1 | tail -15`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/rag/scripts/contextualizer.py skills/rag/augur/tests/test_contextualizer.py
git commit -m "feat(rag): add Ollama-powered contextual enrichment"
```

---

### Task 4: BM25 index module

**Files:**
- Create: `skills/rag/scripts/bm25_index.py`
- Test: `skills/rag/augur/tests/test_bm25_index.py`

- [ ] **Step 1: Write failing tests**

Create `skills/rag/augur/tests/test_bm25_index.py`:

```python
"""Tests for BM25 index build, serialize, load, and query."""

import json
import pytest
from pathlib import Path


class TestBM25Index:
    """Core BM25 index operations."""

    def test_build_from_chunks(self):
        from plugins.ai.skills.rag.scripts.bm25_index import BM25Index

        chunks = [
            {"path": "chunks/a.md", "text": "circuit breaker configuration for retry logic", "meta": {"skill": "rag"}},
            {"path": "chunks/b.md", "text": "notification settings and channel preferences", "meta": {"skill": "channels"}},
            {"path": "chunks/c.md", "text": "interview preparation and career pipeline", "meta": {"skill": "career"}},
        ]
        index = BM25Index.build(chunks)
        assert index.size() == 3

    def test_query_returns_ranked_results(self):
        from plugins.ai.skills.rag.scripts.bm25_index import BM25Index

        chunks = [
            {"path": "chunks/a.md", "text": "circuit breaker configuration for retry logic and error handling", "meta": {}},
            {"path": "chunks/b.md", "text": "notification settings and channel preferences for alerts", "meta": {}},
            {"path": "chunks/c.md", "text": "interview preparation and career pipeline management", "meta": {}},
        ]
        index = BM25Index.build(chunks)
        results = index.query("circuit breaker retry", top_k=2)
        assert len(results) <= 2
        # The circuit breaker chunk should rank highest
        assert results[0]["path"] == "chunks/a.md"

    def test_query_partial_match(self):
        from plugins.ai.skills.rag.scripts.bm25_index import BM25Index

        chunks = [
            {"path": "a.md", "text": "configure notification settings for email and slack channels", "meta": {}},
            {"path": "b.md", "text": "database migration scripts for postgresql", "meta": {}},
        ]
        index = BM25Index.build(chunks)
        results = index.query("notification channel", top_k=5)
        assert len(results) >= 1
        assert results[0]["path"] == "a.md"

    def test_empty_query_returns_empty(self):
        from plugins.ai.skills.rag.scripts.bm25_index import BM25Index

        chunks = [{"path": "a.md", "text": "some content", "meta": {}}]
        index = BM25Index.build(chunks)
        results = index.query("", top_k=5)
        assert results == []

    def test_empty_index_returns_empty(self):
        from plugins.ai.skills.rag.scripts.bm25_index import BM25Index

        index = BM25Index.build([])
        results = index.query("anything", top_k=5)
        assert results == []


class TestBM25Serialization:
    """Serialize and load BM25 index to/from disk."""

    def test_save_and_load_roundtrip(self, tmp_path):
        from plugins.ai.skills.rag.scripts.bm25_index import BM25Index

        chunks = [
            {"path": "a.md", "text": "circuit breaker configuration", "meta": {"skill": "rag"}},
            {"path": "b.md", "text": "notification settings", "meta": {"skill": "channels"}},
        ]
        original = BM25Index.build(chunks)
        original.save(tmp_path)

        loaded = BM25Index.load(tmp_path)
        assert loaded.size() == 2

        # Query should produce same results
        orig_results = original.query("circuit breaker", top_k=1)
        loaded_results = loaded.query("circuit breaker", top_k=1)
        assert orig_results[0]["path"] == loaded_results[0]["path"]

    def test_save_creates_expected_files(self, tmp_path):
        from plugins.ai.skills.rag.scripts.bm25_index import BM25Index

        chunks = [{"path": "a.md", "text": "test content", "meta": {}}]
        index = BM25Index.build(chunks)
        index.save(tmp_path)

        assert (tmp_path / "bm25_index.json").exists()
        assert (tmp_path / "bm25_chunk_map.json").exists()

    def test_load_missing_files_returns_empty(self, tmp_path):
        from plugins.ai.skills.rag.scripts.bm25_index import BM25Index

        index = BM25Index.load(tmp_path)
        assert index.size() == 0


class TestBM25Tokenization:
    """Tokenization and stopword handling."""

    def test_stopwords_removed(self):
        from plugins.ai.skills.rag.scripts.bm25_index import BM25Index

        chunks = [
            {"path": "a.md", "text": "the quick brown fox jumps over the lazy dog", "meta": {}},
        ]
        index = BM25Index.build(chunks)
        # "the" and "over" should be removed as stopwords
        results = index.query("quick fox", top_k=1)
        assert len(results) == 1

    def test_case_insensitive(self):
        from plugins.ai.skills.rag.scripts.bm25_index import BM25Index

        chunks = [{"path": "a.md", "text": "Circuit Breaker Configuration", "meta": {}}]
        index = BM25Index.build(chunks)
        results = index.query("circuit breaker", top_k=1)
        assert len(results) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/test_bm25_index.py -v --no-header 2>&1 | head -20`
Expected: All tests FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement bm25_index.py**

Create `skills/rag/scripts/bm25_index.py`:

```python
"""BM25 index for RAG retrieval.

Build, serialize, load, and query a BM25 index over enriched chunks.
Uses rank_bm25.BM25Okapi for scoring (k1=1.5, b=0.75).
"""

from __future__ import annotations

import json
import logging
import re
import string
from pathlib import Path

logger = logging.getLogger(__name__)

# Common English stopwords
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "as", "be", "was", "were",
    "been", "are", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "this", "that",
    "these", "those", "not", "no", "so", "if", "then", "than", "when",
    "where", "which", "who", "whom", "how", "what", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such",
    "only", "own", "same", "too", "very", "just", "about", "above",
    "after", "before", "between", "into", "through", "during", "over",
    "under", "again", "further", "once", "here", "there", "up", "out",
})


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split whitespace, remove stopwords."""
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    tokens = text.split()
    return [t for t in tokens if t and t not in _STOPWORDS]


class BM25Index:
    """BM25 index over a corpus of text chunks."""

    def __init__(self, bm25: "object | None", chunk_map: list[dict]):
        self._bm25 = bm25
        self._chunk_map = chunk_map

    @classmethod
    def build(cls, chunks: list[dict]) -> BM25Index:
        """Build a BM25 index from a list of chunk dicts.

        Each chunk must have 'path', 'text', and 'meta' keys.
        """
        if not chunks:
            return cls(bm25=None, chunk_map=[])

        from rank_bm25 import BM25Okapi

        corpus = [_tokenize(c["text"]) for c in chunks]
        chunk_map = [{"path": c["path"], "meta": c.get("meta", {})} for c in chunks]
        bm25 = BM25Okapi(corpus, k1=1.5, b=0.75)

        return cls(bm25=bm25, chunk_map=chunk_map)

    def size(self) -> int:
        return len(self._chunk_map)

    def query(self, query: str, top_k: int = 50) -> list[dict]:
        """Query the index. Returns list of {path, score, meta} dicts."""
        if not query.strip() or self._bm25 is None:
            return []

        tokens = _tokenize(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        results = []
        for idx in ranked_indices[:top_k]:
            if scores[idx] <= 0:
                break
            results.append({
                "path": self._chunk_map[idx]["path"],
                "score": float(scores[idx]),
                "meta": self._chunk_map[idx]["meta"],
            })
        return results

    def save(self, directory: Path) -> None:
        """Serialize index corpus and chunk map to JSON files."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        # Save tokenized corpus for rebuilding BM25 on load
        if self._bm25 is not None:
            # Re-tokenize from chunk_map is not possible without text,
            # so we store the corpus directly
            corpus = []
            if hasattr(self._bm25, "corpus"):
                corpus = self._bm25.corpus
            elif hasattr(self._bm25, "doc_freqs"):
                # rank_bm25 stores corpus as list of token lists
                corpus = getattr(self._bm25, "corpus", [])

            (directory / "bm25_index.json").write_text(
                json.dumps(corpus, ensure_ascii=False),
                encoding="utf-8",
            )
        else:
            (directory / "bm25_index.json").write_text("[]", encoding="utf-8")

        (directory / "bm25_chunk_map.json").write_text(
            json.dumps(self._chunk_map, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path) -> BM25Index:
        """Load a serialized BM25 index from disk."""
        directory = Path(directory)
        index_path = directory / "bm25_index.json"
        map_path = directory / "bm25_chunk_map.json"

        if not index_path.exists() or not map_path.exists():
            return cls(bm25=None, chunk_map=[])

        try:
            corpus = json.loads(index_path.read_text(encoding="utf-8"))
            chunk_map = json.loads(map_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load BM25 index: %s", e)
            return cls(bm25=None, chunk_map=[])

        if not corpus:
            return cls(bm25=None, chunk_map=chunk_map)

        from rank_bm25 import BM25Okapi

        bm25 = BM25Okapi(corpus, k1=1.5, b=0.75)
        return cls(bm25=bm25, chunk_map=chunk_map)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/test_bm25_index.py -v --no-header 2>&1 | tail -20`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/rag/scripts/bm25_index.py skills/rag/augur/tests/test_bm25_index.py
git commit -m "feat(rag): add BM25 index build, serialize, load, query"
```

---

### Task 5: Hybrid retrieval module

**Files:**
- Create: `skills/rag/scripts/retrieval.py`
- Test: `skills/rag/augur/tests/test_retrieval.py`

- [ ] **Step 1: Write failing tests**

Create `skills/rag/augur/tests/test_retrieval.py`:

```python
"""Tests for hybrid retrieval: ripgrep + BM25, RRF fusion, dedup."""

import pytest


class TestRRFFusion:
    """Reciprocal Rank Fusion merging."""

    def test_rrf_combines_two_ranked_lists(self):
        from plugins.ai.skills.rag.scripts.retrieval import rrf_merge

        ripgrep_results = [
            {"path": "a.md", "content": "match a"},
            {"path": "b.md", "content": "match b"},
            {"path": "c.md", "content": "match c"},
        ]
        bm25_results = [
            {"path": "b.md", "score": 5.0, "meta": {}},
            {"path": "d.md", "score": 3.0, "meta": {}},
            {"path": "a.md", "score": 1.0, "meta": {}},
        ]
        merged = rrf_merge(ripgrep_results, bm25_results, k=60)
        # Both a.md and b.md appear in both lists, should have highest scores
        paths = [r["path"] for r in merged]
        assert "a.md" in paths
        assert "b.md" in paths
        # b.md ranks #1 in ripgrep (idx 1) and #1 in bm25, should be near top
        assert paths.index("b.md") <= 1

    def test_rrf_deduplicates(self):
        from plugins.ai.skills.rag.scripts.retrieval import rrf_merge

        ripgrep = [{"path": "a.md", "content": "x"}]
        bm25 = [{"path": "a.md", "score": 1.0, "meta": {}}]
        merged = rrf_merge(ripgrep, bm25, k=60)
        assert len(merged) == 1

    def test_rrf_empty_inputs(self):
        from plugins.ai.skills.rag.scripts.retrieval import rrf_merge

        assert rrf_merge([], [], k=60) == []

    def test_rrf_one_source_empty(self):
        from plugins.ai.skills.rag.scripts.retrieval import rrf_merge

        ripgrep = [{"path": "a.md", "content": "x"}]
        merged = rrf_merge(ripgrep, [], k=60)
        assert len(merged) == 1
        assert merged[0]["path"] == "a.md"


class TestHybridRetrieval:
    """End-to-end hybrid retrieval pipeline."""

    def test_hybrid_search_returns_results(self):
        from plugins.ai.skills.rag.scripts.retrieval import hybrid_search
        from plugins.ai.skills.rag.scripts.bm25_index import BM25Index

        bm25_chunks = [
            {"path": "a.md", "text": "circuit breaker configuration", "meta": {}},
            {"path": "b.md", "text": "notification settings", "meta": {}},
        ]
        bm25 = BM25Index.build(bm25_chunks)

        def mock_ripgrep(query):
            return [{"path": "a.md", "content": "circuit breaker config"}]

        results = hybrid_search(
            query="circuit breaker",
            ripgrep_func=mock_ripgrep,
            bm25_index=bm25,
            top_k=10,
        )
        assert len(results) >= 1
        assert results[0]["path"] == "a.md"

    def test_bm25_none_falls_back_to_ripgrep(self):
        from plugins.ai.skills.rag.scripts.retrieval import hybrid_search

        def mock_ripgrep(query):
            return [{"path": "a.md", "content": "match"}]

        results = hybrid_search(
            query="test",
            ripgrep_func=mock_ripgrep,
            bm25_index=None,
            top_k=10,
        )
        assert len(results) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/test_retrieval.py -v --no-header 2>&1 | head -20`
Expected: All tests FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement retrieval.py**

Create `skills/rag/scripts/retrieval.py`:

```python
"""Hybrid retrieval: ripgrep + BM25 with Reciprocal Rank Fusion.

Runs both retrieval methods in parallel (conceptually — sequential in practice),
merges results via RRF, deduplicates, and returns a ranked list.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


def rrf_merge(
    ripgrep_results: list[dict],
    bm25_results: list[dict],
    k: int = 60,
) -> list[dict]:
    """Merge two ranked lists using Reciprocal Rank Fusion.

    RRF_score(doc) = SUM(1 / (k + rank_in_source))

    Args:
        ripgrep_results: List of dicts with 'path' key, ordered by ripgrep return order.
        bm25_results: List of dicts with 'path' key, already ranked by BM25 score.
        k: RRF constant (default 60).

    Returns:
        Merged, deduplicated list sorted by RRF score descending.
    """
    scores: dict[str, float] = {}
    entries: dict[str, dict] = {}

    for rank, result in enumerate(ripgrep_results):
        path = result.get("path") or result.get("file", "")
        if not path:
            continue
        scores[path] = scores.get(path, 0) + 1.0 / (k + rank + 1)
        if path not in entries:
            entries[path] = {"path": path, "source": "ripgrep"}

    for rank, result in enumerate(bm25_results):
        path = result.get("path", "")
        if not path:
            continue
        scores[path] = scores.get(path, 0) + 1.0 / (k + rank + 1)
        if path not in entries:
            entries[path] = {"path": path, "source": "bm25"}
        else:
            entries[path]["source"] = "both"

    ranked = sorted(entries.values(), key=lambda e: scores.get(e["path"], 0), reverse=True)
    for entry in ranked:
        entry["rrf_score"] = scores.get(entry["path"], 0)

    return ranked


def hybrid_search(
    query: str,
    ripgrep_func: Callable[[str], list[dict]],
    bm25_index: Any | None,
    top_k: int = 10,
    rrf_k: int = 60,
    bm25_top_k: int = 50,
) -> list[dict]:
    """Run hybrid retrieval: ripgrep + BM25, merge via RRF.

    Args:
        query: Search query string.
        ripgrep_func: Callable that takes a query and returns ripgrep hit dicts.
        bm25_index: BM25Index instance (or None to skip BM25).
        top_k: Number of final results to return.
        rrf_k: RRF constant.
        bm25_top_k: Number of BM25 candidates before RRF.

    Returns:
        List of result dicts sorted by RRF score.
    """
    # Ripgrep results
    ripgrep_results = ripgrep_func(query)
    # Flatten hit groups from ripgrep (which returns [{"type": ..., "hits": [...]}])
    flat_ripgrep: list[dict] = []
    for item in ripgrep_results:
        if isinstance(item, dict) and "hits" in item:
            for hit in item["hits"]:
                path = hit.get("file", "")
                if path:
                    flat_ripgrep.append({"path": path, "content": hit.get("content", "")})
        elif isinstance(item, dict) and "path" in item:
            flat_ripgrep.append(item)

    # BM25 results
    bm25_results: list[dict] = []
    if bm25_index is not None:
        try:
            bm25_results = bm25_index.query(query, top_k=bm25_top_k)
        except Exception as e:
            logger.warning("BM25 query failed: %s", e)

    # If no BM25, return ripgrep results as-is
    if not bm25_results:
        return flat_ripgrep[:top_k]

    merged = rrf_merge(flat_ripgrep, bm25_results, k=rrf_k)
    return merged[:top_k]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/test_retrieval.py -v --no-header 2>&1 | tail -15`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/rag/scripts/retrieval.py skills/rag/augur/tests/test_retrieval.py
git commit -m "feat(rag): add hybrid retrieval with RRF fusion"
```

---

### Task 6: OCR extractor module

**Files:**
- Create: `skills/rag/scripts/ocr_extractor.py`
- Test: `skills/rag/augur/tests/test_ocr_extractor.py`

- [ ] **Step 1: Write failing tests**

Create `skills/rag/augur/tests/test_ocr_extractor.py`:

```python
"""Tests for OCR extraction pipeline."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestDocTypeDetection:
    """Detect document type and route to correct extractor."""

    def test_text_pdf_detected(self, tmp_path):
        from plugins.ai.skills.rag.scripts.ocr_extractor import detect_doc_type

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 text content")
        assert detect_doc_type(pdf) in ("text_pdf", "scanned_pdf", "unknown")

    def test_image_detected(self, tmp_path):
        from plugins.ai.skills.rag.scripts.ocr_extractor import detect_doc_type

        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n")
        assert detect_doc_type(img) == "image"

    def test_office_detected(self, tmp_path):
        from plugins.ai.skills.rag.scripts.ocr_extractor import detect_doc_type

        doc = tmp_path / "test.docx"
        doc.write_bytes(b"PK\x03\x04")
        assert detect_doc_type(doc) == "office"

    def test_html_detected(self, tmp_path):
        from plugins.ai.skills.rag.scripts.ocr_extractor import detect_doc_type

        html = tmp_path / "test.html"
        html.write_text("<html><body>Hello</body></html>")
        assert detect_doc_type(html) == "html"


class TestExtractText:
    """Text extraction from various sources."""

    def test_extract_plain_text(self, tmp_path):
        from plugins.ai.skills.rag.scripts.ocr_extractor import extract_text

        txt = tmp_path / "readme.txt"
        txt.write_text("Hello world content")
        result = extract_text(txt)
        assert "Hello world content" in result["text"]
        assert result["method"] == "plaintext"

    def test_extract_markdown(self, tmp_path):
        from plugins.ai.skills.rag.scripts.ocr_extractor import extract_text

        md = tmp_path / "doc.md"
        md.write_text("# Title\n\nParagraph content.")
        result = extract_text(md)
        assert "Paragraph content" in result["text"]
        assert result["method"] == "plaintext"

    def test_extract_unknown_returns_empty(self, tmp_path):
        from plugins.ai.skills.rag.scripts.ocr_extractor import extract_text

        binary = tmp_path / "mystery.bin"
        binary.write_bytes(bytes(range(256)))
        result = extract_text(binary)
        assert result["method"] in ("plaintext", "failed")


class TestCachedExtraction:
    """Checksum-based extraction caching."""

    def test_cached_result_skips_extraction(self, tmp_path):
        from plugins.ai.skills.rag.scripts.ocr_extractor import extract_with_cache

        txt = tmp_path / "doc.txt"
        txt.write_text("Content here")
        cache_dir = tmp_path / "cache"

        # First extraction
        result1 = extract_with_cache(txt, cache_dir)
        assert result1["text"] == "Content here"

        # Second extraction should use cache
        result2 = extract_with_cache(txt, cache_dir)
        assert result2["text"] == "Content here"
        assert result2.get("cached", False)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/test_ocr_extractor.py -v --no-header 2>&1 | head -20`
Expected: All tests FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement ocr_extractor.py**

Create `skills/rag/scripts/ocr_extractor.py`:

```python
"""OCR extraction pipeline for RAG document indexing.

Routes documents to the appropriate extraction method:
- Text PDFs → pymupdf text extraction
- Scanned PDFs → page images → MLX OCR
- Images → MLX OCR
- Office/HTML → existing document-extractor skill
- Plain text/markdown → direct read

Uses checksum-based caching to avoid re-extraction of unchanged files.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp"}
_OFFICE_EXTENSIONS = {".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".odt", ".ods", ".odp"}
_TEXT_EXTENSIONS = {".txt", ".md", ".rst", ".csv", ".tsv", ".log", ".yaml", ".yml", ".json", ".xml"}


def detect_doc_type(path: Path) -> str:
    """Detect document type for extraction routing.

    Returns one of: text_pdf, scanned_pdf, image, office, html, plaintext, unknown
    """
    ext = path.suffix.lower()

    if ext in _IMAGE_EXTENSIONS:
        return "image"
    if ext in _OFFICE_EXTENSIONS:
        return "office"
    if ext in _TEXT_EXTENSIONS:
        return "plaintext"
    if ext in (".html", ".htm"):
        return "html"
    if ext == ".pdf":
        return _classify_pdf(path)
    return "unknown"


def _classify_pdf(path: Path) -> str:
    """Classify a PDF as text-based or scanned."""
    try:
        import pymupdf
        doc = pymupdf.open(str(path))
        text_chars = 0
        for page_num in range(min(3, len(doc))):
            page = doc[page_num]
            text_chars += len(page.get_text().strip())
        doc.close()
        # If first 3 pages have substantial text, it's text-based
        return "text_pdf" if text_chars > 100 else "scanned_pdf"
    except ImportError:
        logger.debug("pymupdf not available, treating PDF as scanned")
        return "scanned_pdf"
    except Exception as e:
        logger.warning("PDF classification failed for %s: %s", path, e)
        return "unknown"


def extract_text(path: Path) -> dict:
    """Extract text from a document.

    Returns dict with 'text', 'method', and optionally 'pages', 'error'.
    """
    doc_type = detect_doc_type(path)

    if doc_type == "plaintext":
        return _extract_plaintext(path)
    if doc_type == "text_pdf":
        return _extract_text_pdf(path)
    if doc_type == "scanned_pdf":
        return _extract_scanned_pdf(path)
    if doc_type == "image":
        return _extract_image_ocr(path)
    if doc_type in ("office", "html"):
        return _extract_via_document_extractor(path)
    if doc_type == "unknown":
        # Try plaintext as fallback
        return _extract_plaintext(path)

    return {"text": "", "method": "failed", "error": f"Unknown doc type: {doc_type}"}


def _extract_plaintext(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return {"text": text, "method": "plaintext"}
    except Exception as e:
        return {"text": "", "method": "failed", "error": str(e)}


def _extract_text_pdf(path: Path) -> dict:
    try:
        import pymupdf
        doc = pymupdf.open(str(path))
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return {"text": "\n\n".join(pages), "method": "pymupdf", "pages": len(pages)}
    except ImportError:
        return _extract_via_document_extractor(path)
    except Exception as e:
        return {"text": "", "method": "failed", "error": str(e)}


def _extract_scanned_pdf(path: Path) -> dict:
    """Extract from scanned PDF using MLX OCR or fallback."""
    try:
        # Try MLX vision model
        return _extract_mlx_ocr_pdf(path)
    except ImportError:
        logger.debug("mlx-vlm not available, falling back to document-extractor")
        return _extract_via_document_extractor(path)
    except Exception as e:
        logger.warning("MLX OCR failed for %s: %s", path, e)
        return _extract_via_document_extractor(path)


def _extract_mlx_ocr_pdf(path: Path) -> dict:
    """Extract text from scanned PDF pages using MLX vision model."""
    import pymupdf

    doc = pymupdf.open(str(path))
    pages_text = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        text = _ocr_image_bytes(img_bytes)
        pages_text.append(text)
    doc.close()
    return {"text": "\n\n".join(pages_text), "method": "mlx_ocr", "pages": len(pages_text)}


def _extract_image_ocr(path: Path) -> dict:
    """Extract text from an image file using MLX OCR."""
    try:
        img_bytes = path.read_bytes()
        text = _ocr_image_bytes(img_bytes)
        return {"text": text, "method": "mlx_ocr"}
    except ImportError:
        return {"text": "", "method": "failed", "error": "mlx-vlm not installed"}
    except Exception as e:
        return {"text": "", "method": "failed", "error": str(e)}


def _ocr_image_bytes(img_bytes: bytes) -> str:
    """Run MLX vision model OCR on raw image bytes."""
    from mlx_vlm import load, generate
    from mlx_vlm.utils import load_image_from_bytes

    model, processor = load("mlx-community/nanoLLaVA-1.5-4bit")
    image = load_image_from_bytes(img_bytes)
    prompt = "Extract all text from this image. Return only the text content."
    output = generate(model, processor, image, prompt, max_tokens=2000)
    return output.strip()


def _extract_via_document_extractor(path: Path) -> dict:
    """Fallback: use the existing document-extractor skill."""
    try:
        import sys
        from src.config.paths import get_skills_dir

        de_scripts = str(get_skills_dir() / "document-extractor" / "scripts")
        if de_scripts not in sys.path:
            sys.path.insert(0, de_scripts)
        from extractor import extract

        result = extract(str(path), max_tier=0)
        return {
            "text": result.markdown if result.success else "",
            "method": "document_extractor",
            "error": result.error if not result.success else None,
        }
    except Exception as e:
        return {"text": "", "method": "failed", "error": str(e)}


def _file_checksum(path: Path) -> str:
    return hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()


def extract_with_cache(path: Path, cache_dir: Path) -> dict:
    """Extract text with checksum-based caching.

    Checks if a cached extraction exists with the same file checksum.
    If so, returns the cached result. Otherwise, extracts and caches.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    checksum = _file_checksum(path)
    cache_file = cache_dir / f"{path.stem}_{checksum}.json"

    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            cached["cached"] = True
            return cached
        except (json.JSONDecodeError, OSError):
            pass

    result = extract_text(path)
    # Cache the result
    try:
        cache_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        logger.warning("Failed to cache extraction for %s: %s", path, e)

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/test_ocr_extractor.py -v --no-header 2>&1 | tail -15`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/rag/scripts/ocr_extractor.py skills/rag/augur/tests/test_ocr_extractor.py
git commit -m "feat(rag): add OCR extraction pipeline with MLX and pymupdf"
```

---

### Task 7: Wire chunking + contextualization into unified_indexer.py

**Files:**
- Modify: `skills/rag/scripts/unified_indexer.py:310-427` (the `reindex_all` function and `_chunk_skills` function)
- Modify: `skills/rag/augur/tests/test_unified_indexer.py`

- [ ] **Step 1: Write failing test for new pipeline phases**

Append to `skills/rag/augur/tests/test_unified_indexer.py`:

```python
# ---------------------------------------------------------------------------
# New pipeline phase tests (Contextual Retrieval)
# ---------------------------------------------------------------------------


def test_reindex_all_runs_chunking_phase(tmp_path):
    """reindex_all should produce chunk files for all categories."""
    from plugins.ai.skills.rag.scripts.unified_indexer import reindex_all

    skill_dir = tmp_path / "plugins" / "ai" / "skills" / "rag"
    skill_dir.mkdir(parents=True)
    # Large enough SKILL.md to trigger chunking
    (skill_dir / "SKILL.md").write_text(
        "---\nname: rag\ndescription: RAG\nx-augur-hub: ai\n---\n"
        "# RAG Skill\n\n" + ("Content paragraph. " * 200) + "\n\n"
        "## Configuration\n\n" + ("Config detail. " * 200)
    )

    rag_dir = tmp_path / "rag"
    stats = reindex_all(tmp_path, rag_dir, vault_dir=None)

    assert stats["chunks"] > 0
    chunk_files = list((rag_dir / "chunks").rglob("*.md"))
    assert len(chunk_files) > 0
    # Chunks should have chunk_index in frontmatter
    content = chunk_files[0].read_text()
    assert "chunk_index:" in content


def test_reindex_all_builds_bm25_index(tmp_path):
    """reindex_all should create BM25 index files in _meta/."""
    from plugins.ai.skills.rag.scripts.unified_indexer import reindex_all

    skill_dir = tmp_path / "plugins" / "ai" / "skills" / "rag"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: rag\ndescription: RAG search\n---\n# RAG\nContent.\n"
    )

    rag_dir = tmp_path / "rag"
    reindex_all(tmp_path, rag_dir, vault_dir=None)

    assert (rag_dir / "_meta" / "bm25_index.json").exists()
    assert (rag_dir / "_meta" / "bm25_chunk_map.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/test_unified_indexer.py::test_reindex_all_runs_chunking_phase skills/rag/augur/tests/test_unified_indexer.py::test_reindex_all_builds_bm25_index -v --no-header 2>&1`
Expected: FAIL because new chunking phase doesn't produce `chunk_index` in frontmatter and BM25 index files don't exist

- [ ] **Step 3: Replace _chunk_skills with new chunking pipeline**

In `skills/rag/scripts/unified_indexer.py`, replace the `_chunk_skills` function (lines 435-485) with:

```python
def _chunk_all(rag_dir: Path, root: Path) -> int:
    """Chunk all indexed content using content-aware strategies.

    Replaces the old _chunk_skills() heading-only splitter.
    Reads source files from all categories and produces enriched chunks
    in rag_dir/chunks/{hub}/{skill}/{heading}.md.
    """
    try:
        from .chunker import auto_chunk
    except ImportError:
        from chunker import auto_chunk

    from src.lib.frontmatter_utils import write_frontmatter

    chunks_dir = rag_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    skills_dir = root / "skills"

    if not skills_dir.is_dir():
        return 0

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue

        content = skill_md.read_text(errors="replace")
        hub = "uncategorized"
        if content.startswith("---"):
            try:
                _, fm, _ = content.split("---", 2)
                data = yaml.safe_load(fm)
                hub = (data or {}).get("x-augur-hub", "uncategorized")
            except Exception:
                pass

        chunks = auto_chunk(content, content_type="markdown")
        out_dir = chunks_dir / hub / skill_dir.name
        out_dir.mkdir(parents=True, exist_ok=True)

        for chunk in chunks:
            safe_heading = chunk["section_heading"].replace("/", "-").replace(" ", "-")[:60]
            chunk_name = f"{safe_heading}_{chunk['chunk_index']}"
            output_path = out_dir / f"{chunk_name}.md"

            meta = {
                "source": skill_dir.name,
                "source_path": str(skill_md),
                "heading": chunk["section_heading"],
                "parent_heading": chunk["parent_heading"],
                "chunk_index": chunk["chunk_index"],
                "total_chunks": chunk["total_chunks"],
            }
            write_frontmatter(output_path, meta, chunk["text"])
            count += 1

    return count
```

- [ ] **Step 4: Add BM25 build phase to reindex_all**

In `skills/rag/scripts/unified_indexer.py`, in the `reindex_all` function, replace the chunk + enrich + manifest section (after `stats["documents"]`) with:

```python
    # Phase 2: Chunk all content using content-aware strategies
    chunk_count = _chunk_all(rag_dir, root)
    stats["chunks"] = chunk_count

    # Phase 3: Contextual enrichment (Ollama, if available)
    try:
        from .contextualizer import Contextualizer
    except ImportError:
        try:
            from contextualizer import Contextualizer
        except ImportError:
            Contextualizer = None

    if Contextualizer is not None:
        try:
            ctx = Contextualizer()
            ctx.load_cache()
            chunks_dir = rag_dir / "chunks"
            _contextualize_chunks(ctx, chunks_dir, root)
            ctx.save_cache()
        except Exception as e:
            print(f"  Warning: contextualization skipped: {e}")

    # Phase 4: Build BM25 index over all chunks
    try:
        from .bm25_index import BM25Index
    except ImportError:
        try:
            from bm25_index import BM25Index
        except ImportError:
            BM25Index = None

    if BM25Index is not None:
        _build_bm25(rag_dir, BM25Index)

    # Post-processing: enrich empty/stub descriptions from source files
    try:
        from .enrich_descriptions import enrich_all as _enrich_all
    except ImportError:
        try:
            from enrich_descriptions import enrich_all as _enrich_all
        except ImportError:
            _enrich_all = None
    if _enrich_all is not None:
        try:
            enrich_stats = _enrich_all(rag_dir, root)
            enriched_total = sum(enrich_stats.values())
            if enriched_total > 0:
                print(f"  Enriched {enriched_total} descriptions across {sum(1 for v in enrich_stats.values() if v)} categories")
        except Exception as e:
            print(f"  Warning: description enrichment failed: {e}")
```

- [ ] **Step 5: Add helper functions for contextualization and BM25 build**

Add these functions before `reindex_all` in `unified_indexer.py`:

```python
def _contextualize_chunks(ctx: "Any", chunks_dir: Path, root: Path) -> int:
    """Run contextual enrichment over all chunk files."""
    from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter

    count = 0
    for chunk_file in sorted(chunks_dir.rglob("*.md")):
        meta, body = parse_frontmatter(chunk_file)
        if not meta or meta.get("context"):
            continue  # Already enriched

        source_path = meta.get("source_path", "")
        if source_path:
            try:
                doc_text = Path(source_path).read_text(errors="replace")[:3000]
            except Exception:
                doc_text = ""
        else:
            doc_text = ""

        context = ctx.generate_context(document_text=doc_text, chunk_text=body)
        if context:
            meta["context"] = context
            enriched_body = context + "\n\n" + body
            write_frontmatter(chunk_file, meta, enriched_body)
            count += 1

    return count


def _build_bm25(rag_dir: Path, BM25Index: type) -> None:
    """Build BM25 index over all chunk files and save to _meta/."""
    from src.lib.frontmatter_utils import parse_frontmatter

    chunks_dir = rag_dir / "chunks"
    if not chunks_dir.exists():
        return

    bm25_chunks: list[dict] = []
    for chunk_file in sorted(chunks_dir.rglob("*.md")):
        meta, body = parse_frontmatter(chunk_file)
        if not body.strip():
            continue
        bm25_chunks.append({
            "path": str(chunk_file.relative_to(rag_dir)),
            "text": body,
            "meta": {
                "source": meta.get("source", ""),
                "heading": meta.get("heading", ""),
                "hub": str(chunk_file.relative_to(chunks_dir)).split("/")[0] if "/" in str(chunk_file.relative_to(chunks_dir)) else "",
            },
        })

    if bm25_chunks:
        index = BM25Index.build(bm25_chunks)
        meta_dir = rag_dir / "_meta"
        index.save(meta_dir)
        print(f"  BM25 index built: {index.size()} chunks")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/test_unified_indexer.py -v --no-header 2>&1 | tail -25`
Expected: All tests PASS (including new ones)

- [ ] **Step 7: Commit**

```bash
git add skills/rag/scripts/unified_indexer.py skills/rag/augur/tests/test_unified_indexer.py
git commit -m "feat(rag): wire chunking, contextualization, and BM25 into indexing pipeline"
```

---

### Task 8: Wire hybrid retrieval into search_engine.py and MCP tools

**Files:**
- Modify: `skills/rag/scripts/search_engine.py`
- Modify: `skills/rag/scripts/mcp/rag_tools.py`
- Modify: `skills/rag/augur/tests/test_search_engine.py`

- [ ] **Step 1: Write failing test for hybrid search integration**

Append to `skills/rag/augur/tests/test_search_engine.py`:

```python
# ---------------------------------------------------------------------------
# Hybrid retrieval integration
# ---------------------------------------------------------------------------


class TestHybridIntegration:
    """Tests for RAGSearchEngine with BM25 integration."""

    def test_engine_accepts_bm25_index(self):
        from plugins.ai.skills.rag.scripts.search_engine import RAGSearchEngine
        from plugins.ai.skills.rag.scripts.bm25_index import BM25Index

        bm25 = BM25Index.build([
            {"path": "a.md", "text": "circuit breaker config", "meta": {}},
        ])
        mock_search = MagicMock(return_value=[])
        engine = RAGSearchEngine(search_func=mock_search, bm25_index=bm25)
        assert engine._bm25_index is not None

    def test_iterative_search_uses_bm25_when_available(self):
        from plugins.ai.skills.rag.scripts.search_engine import RAGSearchEngine
        from plugins.ai.skills.rag.scripts.bm25_index import BM25Index

        bm25 = BM25Index.build([
            {"path": "a.md", "text": "circuit breaker configuration for retry logic", "meta": {}},
            {"path": "b.md", "text": "notification settings and preferences", "meta": {}},
        ])

        ripgrep_results = [{"type": "fulltext", "hits": [
            {"file": "a.md", "content": "circuit breaker"},
        ]}]
        mock_search = MagicMock(return_value=ripgrep_results)
        engine = RAGSearchEngine(search_func=mock_search, bm25_index=bm25)

        results = engine.iterative_search("circuit breaker", top_k=5)
        assert isinstance(results, list)
        assert len(results) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/test_search_engine.py::TestHybridIntegration -v --no-header 2>&1`
Expected: FAIL because `RAGSearchEngine.__init__` doesn't accept `bm25_index`

- [ ] **Step 3: Update RAGSearchEngine to support hybrid retrieval**

In `skills/rag/scripts/search_engine.py`, modify the `__init__` and `iterative_search` methods:

```python
class RAGSearchEngine:
    """
    Consolidated RAG search engine implementing:
    - Layer 1: Ripgrep (exact matches)
    - Layer 1b: BM25 (term relevance) — NEW
    - Layer 2: LLM Evaluation and Reranking
    """
    _CIRCUIT_BREAKER_THRESHOLD = 3
    _CIRCUIT_BREAKER_COOLDOWN = 300

    _cb_failure_count: int = 0
    _cb_open_since: Optional[float] = None

    def __init__(self, search_func, llm_client: Any = None, bm25_index: Any = None):
        self.search_func = search_func
        self._injected_client = llm_client
        self._bm25_index = bm25_index
```

Then update `iterative_search` to use hybrid retrieval when BM25 is available:

```python
    def iterative_search(self, query: str, max_rounds: int = 3, top_k: int = 10) -> list:
        client = self._get_llm_client()

        # If BM25 is available, use hybrid retrieval
        if self._bm25_index is not None:
            from .retrieval import hybrid_search

            def ripgrep_wrapper(q):
                return self.search_func(q)

            hybrid_results = hybrid_search(
                query=query,
                ripgrep_func=ripgrep_wrapper,
                bm25_index=self._bm25_index,
                top_k=top_k * 2,  # Get extra candidates for LLM reranking
            )

            if client is None:
                return hybrid_results[:top_k]

            # LLM rerank the hybrid results
            try:
                return self._rank_results(client, query, hybrid_results, top_k)
            except Exception as e:
                logger.warning(f"LLM ranking failed: {e}")
                return hybrid_results[:top_k]

        # Original ripgrep-only path (fallback)
        if client is None:
            raw = self.search_func(query)
            for group in raw:
                if isinstance(group, dict) and "hits" in group:
                    group["hits"] = group["hits"][:top_k]
            return raw

        all_results = []
        current_query = query
        llm_client_failed = False

        for _ in range(max_rounds):
            round_results = self.search_func(current_query)
            all_results.extend(round_results)

            try:
                evaluation = self._evaluate_results(client, query, round_results)
            except Exception as e:
                logger.warning(f"LLM eval failed: {e}")
                llm_client_failed = True
                break

            if evaluation.sufficient:
                break

            refined = evaluation.refined_query or query
            current_query = refined[:200]

        seen = set()
        deduped = []
        for r in all_results:
            key = json.dumps(r, sort_keys=True)
            if key not in seen:
                seen.add(key)
                deduped.append(r)

        if llm_client_failed:
            return deduped[:top_k]

        try:
            return self._rank_results(client, query, deduped, top_k)
        except Exception as e:
            logger.warning(f"LLM ranking failed: {e}")
            return deduped[:top_k]
```

- [ ] **Step 4: Update MCP rag_tools.py to load BM25 at search time**

In `skills/rag/scripts/mcp/rag_tools.py`, update the `iterative_search` function and `rag_status` tool:

In the `iterative_search` function (line 169-173), add BM25 loading:

```python
def iterative_search(query: str, source_dirs: list[Path], priority_dirs: list[Path], rag_dirs: list[Path]) -> list[dict]:
    from ..search_engine import RAGSearchEngine

    # Try to load BM25 index
    bm25_index = None
    try:
        from ..bm25_index import BM25Index
        for rag_dir in rag_dirs:
            meta_dir = rag_dir / "_meta" if rag_dir.name != "_meta" else rag_dir
            candidate = BM25Index.load(meta_dir)
            if candidate.size() > 0:
                bm25_index = candidate
                break
    except ImportError:
        pass

    engine = RAGSearchEngine(
        search_func=lambda q: _raw_iterative_search(q, source_dirs, priority_dirs, rag_dirs),
        bm25_index=bm25_index,
    )
    return engine.iterative_search(query)
```

In the `_count_status` function (line 176-195), add BM25 stats:

```python
def _count_status(rag_dirs: list[Path]) -> dict:
    chunks = 0
    symbols = 0
    indices = 0
    bm25_size = 0
    existing_dirs: list[str] = []

    for rag_dir in rag_dirs:
        if not rag_dir.exists():
            continue
        existing_dirs.append(str(rag_dir))
        chunks += sum(1 for _ in rag_dir.rglob("index/chunks/*.md"))
        indices += sum(1 for _ in rag_dir.rglob("*_index.md"))
        symbols += sum(1 for _ in rag_dir.rglob("symbols.yaml"))

        # BM25 stats
        bm25_path = rag_dir / "_meta" / "bm25_index.json"
        if bm25_path.exists():
            bm25_size = bm25_path.stat().st_size

    return {
        "chunks": chunks,
        "symbols": symbols,
        "indices": indices,
        "bm25_index_bytes": bm25_size,
        "rag_paths": existing_dirs,
    }
```

- [ ] **Step 5: Run all tests to verify**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/test_search_engine.py skills/rag/augur/tests/test_unified_indexer.py -v --no-header 2>&1 | tail -30`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add skills/rag/scripts/search_engine.py skills/rag/scripts/mcp/rag_tools.py skills/rag/augur/tests/test_search_engine.py
git commit -m "feat(rag): wire hybrid BM25+ripgrep retrieval into search engine and MCP tools"
```

---

### Task 9: Quality baseline and search metrics

**Files:**
- Create: `skills/rag/assets/seeds/quality_baseline.yaml`
- Modify: `skills/rag/scripts/mcp/rag_tools.py` (add metrics logging)

- [ ] **Step 1: Create quality baseline test queries**

Create `skills/rag/assets/seeds/quality_baseline.yaml`:

```yaml
# Quality baseline for Contextual Retrieval evaluation
# Run before and after to measure improvement
# Each query has an expected result and acceptable rank position

queries:
  - query: "how do I configure notifications"
    expected_in_top_10:
      - "channels"
      - "attention"
    category: natural_language

  - query: "circuit breaker configuration"
    expected_in_top_10:
      - "rag"
    category: exact_match

  - query: "set up job tracking"
    expected_in_top_10:
      - "career"
    category: natural_language

  - query: "MCP tool registration"
    expected_in_top_10:
      - "mcp-sdk-patterns"
    category: technical

  - query: "dashboard page rendering"
    expected_in_top_10:
      - "dashboard"
      - "renderer"
    category: technical

  - query: "how to add a new skill"
    expected_in_top_10:
      - "skill-setup"
      - "evolve"
    category: natural_language

  - query: "test coverage analysis"
    expected_in_top_10:
      - "test-coverage"
    category: exact_match

  - query: "file organization and sorting"
    expected_in_top_10:
      - "file-manager"
    category: natural_language

  - query: "schedule recurring tasks"
    expected_in_top_10:
      - "schedule"
      - "daemon"
    category: natural_language

  - query: "git commit workflow"
    expected_in_top_10:
      - "dev-merge"
      - "git-guidelines"
    category: technical

  - query: "health tracking wearables"
    expected_in_top_10:
      - "wearables"
      - "health"
    category: natural_language

  - query: "PDF document extraction"
    expected_in_top_10:
      - "document-extractor"
    category: technical

  - query: "investment portfolio"
    expected_in_top_10:
      - "wealth"
      - "finance"
    category: natural_language

  - query: "obsidian vault integration"
    expected_in_top_10:
      - "obsidian"
    category: exact_match

  - query: "interview preparation tips"
    expected_in_top_10:
      - "coach"
      - "interview-coach"
    category: natural_language

  - query: "memory persistence across sessions"
    expected_in_top_10:
      - "knowledge"
    category: technical

  - query: "API route debugging"
    expected_in_top_10:
      - "dev-debug"
      - "runbook-dashboard"
    category: technical

  - query: "plugin architecture design"
    expected_in_top_10:
      - "dashboard"
    category: technical

  - query: "LinkedIn post creation"
    expected_in_top_10:
      - "linkedin-writer"
      - "content"
    category: exact_match

  - query: "reading list management"
    expected_in_top_10:
      - "reading-list"
    category: exact_match
```

- [ ] **Step 2: Add search metrics logging to rag_tools.py**

In `skills/rag/scripts/mcp/rag_tools.py`, add a metrics logging function and call it from `search_skill_knowledge`:

```python
def _log_search_metrics(query: str, ripgrep_hits: int, bm25_hits: int, merged: int, deduped: int, llm_reranked: bool, latency_ms: float) -> None:
    """Append search metrics to the JSONL log."""
    import json
    from datetime import datetime, timezone

    rag_dir = get_rag_dir()
    metrics_path = rag_dir / "_meta" / "search_metrics.jsonl"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "query": query,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "ripgrep_hits": ripgrep_hits,
        "bm25_hits": bm25_hits,
        "merged_candidates": merged,
        "deduplicated": deduped,
        "llm_reranked": llm_reranked,
        "latency_ms": round(latency_ms, 1),
    }

    with open(metrics_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
```

- [ ] **Step 3: Commit**

```bash
git add skills/rag/assets/seeds/quality_baseline.yaml skills/rag/scripts/mcp/rag_tools.py
git commit -m "feat(rag): add quality baseline queries and search metrics logging"
```

---

### Task 10: Run full test suite and verify integration

**Files:**
- All test files in `skills/rag/augur/tests/`

- [ ] **Step 1: Run the complete RAG test suite**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/ -v --no-header 2>&1 | tail -40`
Expected: All tests PASS

- [ ] **Step 2: Verify existing tests still pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/rag/augur/tests/test_unified_indexer.py skills/rag/augur/tests/test_search_engine.py skills/rag/augur/tests/test_rag_tools.py -v --no-header 2>&1 | tail -30`
Expected: All existing tests PASS (no regressions)

- [ ] **Step 3: Verify imports work end-to-end**

Run: `cd ~/Projects/Augur && python -c "from plugins.ai.skills.rag.scripts.chunker import auto_chunk; from plugins.ai.skills.rag.scripts.contextualizer import Contextualizer; from plugins.ai.skills.rag.scripts.bm25_index import BM25Index; from plugins.ai.skills.rag.scripts.retrieval import hybrid_search; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 4: Run a small manual integration test**

Run: `cd ~/Projects/Augur && python -c "
from plugins.ai.skills.rag.scripts.chunker import auto_chunk
from plugins.ai.skills.rag.scripts.bm25_index import BM25Index

# Chunk a real SKILL.md
text = open('skills/rag/SKILL.md').read()
chunks = auto_chunk(text, content_type='markdown')
print(f'Produced {len(chunks)} chunks from SKILL.md')

# Build BM25 index
bm25_chunks = [{'path': f'chunk_{i}.md', 'text': c['text'], 'meta': {}} for i, c in enumerate(chunks)]
index = BM25Index.build(bm25_chunks)
print(f'BM25 index has {index.size()} entries')

# Query
results = index.query('search configuration', top_k=3)
for r in results:
    print(f'  Score {r[\"score\"]:.2f}: {r[\"path\"]}')
print('Integration test PASSED')
"`
Expected: Outputs chunk count, BM25 size, and ranked results

- [ ] **Step 5: Commit**

```bash
git commit --allow-empty -m "test(rag): verify contextual retrieval integration passes"
```
