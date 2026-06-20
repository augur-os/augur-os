# Document Extractor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `document-extractor` skill that provides universal document-to-Markdown extraction via MarkItDown, with tiered LLM-assisted OCR using the LLM-Assisted MCP pattern.

**Architecture:** MarkItDown wraps all format-specific parsing into a single `extract()` call. Tier 0 (pure parsing, always works) covers text-based PDFs, Office docs, HTML, text. Tier 1 adds LLM Vision for OCR via the calling AI agent or local Ollama. The skill exposes 4 MCP tools and replaces `binary_extractor.py` as the single extraction layer.

**Tech Stack:** Python 3.11+, MarkItDown (`markitdown[all]`, `markitdown-ocr`), FastMCP, OpenAI client (for Ollama compat), Swift (macOS audio helper)

**Spec:** `docs/superpowers/specs/2026-03-26-document-extractor-design.md`
**ADR:** ADR-518
**Pattern:** `docs/references/llm-assisted-mcp-pattern.md`

---

## File Structure

```
skills/document-extractor/
├── SKILL.md                           # Skill metadata, x-augur-mcp-tools
├── config.yaml                        # Dashboard page contributions
├── scripts/
│   ├── extractor.py                   # Core: MarkItDown wrapper, tier detection, extract()
│   ├── ollama_client.py               # Ollama health check, OpenAI-compat wrapper
│   ├── audio_extractor.py             # macOS native + cross-platform audio
│   └── mcp/
│       ├── __init__.py                # Tool registration entry point
│       ├── _shared.py                 # Shared helpers (tool_annotations, etc.)
│       └── tools_extract.py           # MCP tool impls + registration
├── augur/
│   ├── dashboard/
│   │   └── page.tsx                   # Integrations status page
│   └── tests/
│       ├── conftest.py                # sys.path bootstrap
│       ├── test_extractor.py          # Core extractor tests
│       ├── test_ollama_client.py      # Ollama client tests
│       └── test_tools_extract.py      # MCP tool tests
├── assets/
│   └── seeds/
│       └── .gitkeep
└── evals/
    └── .gitkeep
```

**Modified files:**
- `pyproject.toml` — add `markitdown[all]`, `markitdown-ocr` dependencies
- `skills/file-manager/scripts/mcp/tools_organize.py:109-119` — replace text-only content sampling
- `skills/rag/scripts/unified_indexer.py:148-161` — replace binary_extractor import
- `skills/rag/scripts/binary_extractor.py` — deleted after migration

---

## Phase 1: Scaffold & Core

### Task 1: Scaffold skill directory and add dependencies

**Files:**
- Create: `skills/document-extractor/SKILL.md`
- Create: `skills/document-extractor/config.yaml`
- Create: `skills/document-extractor/assets/seeds/.gitkeep`
- Create: `skills/document-extractor/evals/.gitkeep`
- Create: `skills/document-extractor/augur/tests/conftest.py`
- Create: `skills/document-extractor/scripts/mcp/_shared.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Create skill directory structure**

```bash
mkdir -p skills/document-extractor/{scripts/mcp,augur/{tests,dashboard},assets/seeds,evals}
touch skills/document-extractor/assets/seeds/.gitkeep
touch skills/document-extractor/evals/.gitkeep
```

- [ ] **Step 2: Create SKILL.md**

```markdown
---
name: document-extractor
description: >-
  Universal document-to-Markdown extraction service. Converts PDF, Office docs,
  images, audio, and HTML to structured Markdown. Supports offline extraction
  (tier 0) and LLM-assisted OCR via the LLM-Assisted MCP pattern.
x-augur-type: domain
x-augur-hub: command
x-augur-tab: home
x-augur-requires-platform: true
x-augur-mcp-tools:
  - extract-document
  - submit-extract-document-result
  - extract-document-batch
  - get-extraction-status
x-augur-dashboard-pages:
  - /command/document-extractor
x-augur-dependencies:
  python: ["markitdown[all]", "markitdown-ocr"]
x-augur-config-file: config.yaml
---

# Document Extractor

Universal document-to-Markdown extraction powered by MarkItDown.

## Tiers

- **Tier 0** — Pure parsing, always available offline. Handles text-based PDF, DOCX, PPTX, XLSX, HTML, CSV, JSON, plain text.
- **Tier 1** — LLM-assisted OCR for scanned PDFs and images. Uses the LLM-Assisted MCP pattern: when called by an AI client, the agent processes images directly; when called from daemon/dashboard, spawns a CLI agent session.

## Architecture Pattern

See `docs/references/llm-assisted-mcp-pattern.md`.
```

- [ ] **Step 3: Create config.yaml**

```yaml
contributions:
  pages:
    - id: document-extractor
      label: Extraction
      icon: FileText
      order: 1
```

- [ ] **Step 4: Create conftest.py**

```python
"""Shared test fixtures and path bootstrap for document-extractor tests."""
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_scripts_dir = str(Path(__file__).resolve().parents[2] / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
```

- [ ] **Step 5: Create _shared.py**

Read `skills/file-manager/scripts/mcp/_shared.py` for reference, then create a minimal version:

```python
"""Shared helpers for document-extractor MCP tools."""
import logging

logger = logging.getLogger("document-extractor")


def tool_annotations(hints: dict) -> dict:
    """Build MCP tool annotation hints."""
    return {"annotations": {"hints": hints}}
```

- [ ] **Step 6: Add markitdown dependencies to pyproject.toml**

In `pyproject.toml`, add to `[project.dependencies]`:

```toml
"markitdown[all]>=0.1.0",
"markitdown-ocr>=0.1.0",
```

- [ ] **Step 7: Install dependencies**

```bash
uv sync
```

Verify markitdown is importable:

```bash
python -c "from markitdown import MarkItDown; print('MarkItDown OK')"
```

- [ ] **Step 8: Commit**

```bash
git add skills/document-extractor/ pyproject.toml uv.lock
git commit -m "feat(document-extractor): scaffold skill directory and add markitdown dependencies"
```

### Task 2: Core extractor — ExtractionResult and tier 0 extraction

**Files:**
- Create: `skills/document-extractor/scripts/extractor.py`
- Create: `skills/document-extractor/augur/tests/test_extractor.py`

- [ ] **Step 1: Write failing tests**

```python
# skills/document-extractor/augur/tests/test_extractor.py
"""Tests for the document extractor core."""
from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

import pytest

from extractor import ExtractionResult, extract, detect_available_tier


class TestExtractionResult:
    def test_create_success_result(self):
        result = ExtractionResult(
            success=True,
            markdown="# Hello",
            title="Hello",
            tier_used=0,
            format="md",
            size_bytes=7,
            extraction_time=0.01,
            ocr_applied=False,
        )
        assert result.success is True
        assert result.markdown == "# Hello"
        assert result.needs_llm is False

    def test_needs_llm_result(self):
        result = ExtractionResult(
            success=True,
            markdown="",
            title=None,
            tier_used=0,
            format="png",
            size_bytes=1000,
            extraction_time=0.01,
            ocr_applied=False,
            needs_llm=True,
            llm_requests=[{"id": "ocr-1", "type": "image_ocr"}],
        )
        assert result.needs_llm is True
        assert len(result.llm_requests) == 1


class TestExtractTier0:
    def test_extract_plain_text(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("Hello, world!")
        result = extract(str(f), max_tier=0)
        assert result.success is True
        assert "Hello, world!" in result.markdown
        assert result.tier_used == 0
        assert result.format == "txt"

    def test_extract_markdown(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text("# Title\n\nParagraph text.")
        result = extract(str(f), max_tier=0)
        assert result.success is True
        assert "Title" in result.markdown

    def test_extract_csv(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("name,age\nAlice,30\nBob,25")
        result = extract(str(f), max_tier=0)
        assert result.success is True
        assert "Alice" in result.markdown

    def test_extract_nonexistent_file(self):
        result = extract("/nonexistent/file.pdf", max_tier=0)
        assert result.success is False

    def test_extract_returns_size_and_time(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("content")
        result = extract(str(f), max_tier=0)
        assert result.size_bytes > 0
        assert result.extraction_time >= 0

    def test_extract_html(self, tmp_path):
        f = tmp_path / "page.html"
        f.write_text("<html><body><h1>Title</h1><p>Text</p></body></html>")
        result = extract(str(f), max_tier=0)
        assert result.success is True
        assert "Title" in result.markdown

    def test_extract_image_tier0_no_content(self, tmp_path):
        """Images at tier 0 return metadata only, no content."""
        f = tmp_path / "photo.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        result = extract(str(f), max_tier=0)
        assert result.success is True
        assert result.needs_llm is False  # tier 0 doesn't request LLM
        # Markdown may be empty or contain just EXIF metadata

    def test_extract_image_tier1_returns_llm_request(self, tmp_path):
        """Images at tier 1 (without LLM available) return needs_llm."""
        f = tmp_path / "photo.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        result = extract(str(f), max_tier=1)
        # Without an actual LLM client available, should either:
        # - Return needs_llm=True with llm_requests (if AI client detected)
        # - Return tier 0 result (if no AI client and no Ollama)
        assert result.success is True


class TestMergeLlmResults:
    def test_merge_replaces_placeholder(self):
        from extractor import merge_llm_results
        partial = "# Page 1\n\n[Image: page requires OCR]\n\n# Page 2\n\nReal text."
        results = {"ocr-1": "Extracted OCR text from page 1"}
        merged = merge_llm_results(partial, results)
        assert "Extracted OCR text from page 1" in merged
        assert "[Image: page requires OCR]" not in merged

    def test_merge_with_no_results(self):
        from extractor import merge_llm_results
        partial = "# Just text"
        merged = merge_llm_results(partial, {})
        assert merged == "# Just text"


class TestDetectAvailableTier:
    def test_tier0_always_available(self):
        tier = detect_available_tier()
        assert tier >= 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest skills/document-extractor/augur/tests/test_extractor.py -v 2>&1 | head -20
```

Expected: ImportError — `extractor` module doesn't exist.

- [ ] **Step 3: Implement extractor.py**

```python
# skills/document-extractor/scripts/extractor.py
"""Core document extraction — MarkItDown wrapper with tiered LLM support.

Tier 0: Pure parsing, always available offline.
Tier 1: LLM-assisted OCR via calling agent or local Ollama.
"""
from __future__ import annotations

import base64
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Path bootstrap
_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from src.logging import get_entity_logger

logger = get_entity_logger("document-extractor")

# Env vars indicating an AI client is calling
AI_CLIENT_ENV_VARS = [
    "CLAUDE_CODE_ENTRY_POINT",
    "CODEX_SESSION",
    "GEMINI_SESSION",
    "AUGUR_AGENT_SESSION",
]

# Image extensions that need LLM for content extraction
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp", ".heic", ".heif", ".svg"}


@dataclass
class ExtractionResult:
    """Result of document extraction."""
    success: bool
    markdown: str
    title: str | None
    tier_used: int
    format: str
    size_bytes: int
    extraction_time: float
    ocr_applied: bool
    needs_llm: bool = False
    llm_requests: list[dict[str, Any]] | None = None
    partial_markdown: str | None = None
    error: str | None = None


def is_ai_client_context() -> bool:
    """Check if an AI client is in the calling context."""
    return any(os.environ.get(v) for v in AI_CLIENT_ENV_VARS)


def detect_available_tier() -> int:
    """Detect the highest available extraction tier.

    Returns:
        0 = offline only (always available)
        1 = LLM-assisted (Ollama or AI client present)
    """
    # Check for AI client
    if is_ai_client_context():
        return 1

    # Check for local Ollama
    try:
        from ollama_client import is_ollama_running
        if is_ollama_running():
            return 1
    except ImportError:
        pass

    return 0


def extract(path: str, max_tier: int = 1) -> ExtractionResult:
    """Extract document content as Markdown.

    Args:
        path: File path to extract.
        max_tier: Maximum tier to use (0=offline only, 1=with LLM).

    Returns:
        ExtractionResult with markdown content or LLM request.
    """
    file_path = Path(path).expanduser().resolve()

    if not file_path.exists():
        return ExtractionResult(
            success=False, markdown="", title=None, tier_used=0,
            format="", size_bytes=0, extraction_time=0, ocr_applied=False,
            error=f"File not found: {path}",
        )

    size = file_path.stat().st_size
    ext = file_path.suffix.lower()
    fmt = ext.lstrip(".")
    start = time.monotonic()

    # Tier 0: MarkItDown pure parsing
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(str(file_path))
        elapsed = time.monotonic() - start

        markdown = result.markdown or ""
        title = result.title if hasattr(result, "title") else None

        # If we got meaningful content, return it
        if markdown.strip():
            return ExtractionResult(
                success=True, markdown=markdown, title=title, tier_used=0,
                format=fmt, size_bytes=size, extraction_time=elapsed,
                ocr_applied=False,
            )

        # Empty result for image — check if LLM can help
        if ext in IMAGE_EXTENSIONS and max_tier >= 1:
            return _request_llm_ocr(file_path, fmt, size, elapsed, markdown)

        # Empty result but not an image — return what we have
        return ExtractionResult(
            success=True, markdown=markdown or f"[No text content extracted from {ext} file]",
            title=title, tier_used=0, format=fmt, size_bytes=size,
            extraction_time=elapsed, ocr_applied=False,
        )

    except Exception as e:
        elapsed = time.monotonic() - start
        logger.warning("MarkItDown extraction failed for %s: %s", path, e)
        return ExtractionResult(
            success=False, markdown="", title=None, tier_used=0,
            format=fmt, size_bytes=size, extraction_time=elapsed,
            ocr_applied=False, error=str(e),
        )


def _request_llm_ocr(
    file_path: Path, fmt: str, size: int, elapsed: float, partial: str
) -> ExtractionResult:
    """Build an LLM OCR request for images/scanned content."""
    # Try Ollama first (local, direct)
    try:
        from ollama_client import get_ollama_client
        client_info = get_ollama_client()
        if client_info:
            client, model = client_info
            from markitdown import MarkItDown
            md = MarkItDown(enable_plugins=True, llm_client=client, llm_model=model)
            result = md.convert(str(file_path))
            return ExtractionResult(
                success=True, markdown=result.markdown or "",
                title=result.title if hasattr(result, "title") else None,
                tier_used=1, format=fmt, size_bytes=size,
                extraction_time=time.monotonic() - (time.monotonic() - elapsed),
                ocr_applied=True,
            )
    except (ImportError, Exception) as e:
        logger.debug("Ollama OCR not available: %s", e)

    # No local LLM — check if we're in an AI client context
    if is_ai_client_context():
        # Return image data for the calling AI agent to process
        try:
            image_data = base64.b64encode(file_path.read_bytes()).decode("utf-8")
            return ExtractionResult(
                success=True, markdown="", title=None, tier_used=0,
                format=fmt, size_bytes=size, extraction_time=elapsed,
                ocr_applied=False, needs_llm=True,
                partial_markdown=partial,
                llm_requests=[{
                    "id": f"ocr-{file_path.stem}",
                    "type": "image_ocr",
                    "image_base64": image_data,
                    "filename": file_path.name,
                    "prompt": "Extract all text from this image, preserving structure. If it's a document, maintain headings, lists, and tables.",
                }],
            )
        except Exception as e:
            logger.warning("Failed to encode image %s: %s", file_path, e)

    # No LLM available — return tier 0 result
    return ExtractionResult(
        success=True, markdown=partial or f"[Image: {file_path.name} — OCR unavailable]",
        title=None, tier_used=0, format=fmt, size_bytes=size,
        extraction_time=elapsed, ocr_applied=False,
    )


def merge_llm_results(partial_markdown: str, results: dict[str, str]) -> str:
    """Merge LLM OCR results into partial markdown.

    Args:
        partial_markdown: Markdown with [Image: ...] placeholders.
        results: Dict of request_id → extracted text.

    Returns:
        Merged markdown with OCR text replacing placeholders.
    """
    merged = partial_markdown
    for request_id, text in results.items():
        # Replace placeholder patterns
        merged = merged.replace(f"[Image: page requires OCR]", text, 1)
    return merged
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest skills/document-extractor/augur/tests/test_extractor.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/document-extractor/scripts/extractor.py skills/document-extractor/augur/tests/test_extractor.py
git commit -m "feat(document-extractor): core extractor with tier 0 MarkItDown extraction"
```

### Task 3: Ollama client

**Files:**
- Create: `skills/document-extractor/scripts/ollama_client.py`
- Create: `skills/document-extractor/augur/tests/test_ollama_client.py`

- [ ] **Step 1: Write failing tests**

```python
# skills/document-extractor/augur/tests/test_ollama_client.py
"""Tests for Ollama client wrapper."""
from __future__ import annotations

from unittest.mock import patch, MagicMock
import json

import pytest

from ollama_client import is_ollama_running, get_default_vision_model, get_ollama_client


class TestIsOllamaRunning:
    def test_returns_true_when_ollama_responds(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}
        with patch("ollama_client.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            assert is_ollama_running() is True

    def test_returns_false_on_connection_error(self):
        with patch("ollama_client.httpx") as mock_httpx:
            mock_httpx.get.side_effect = Exception("Connection refused")
            assert is_ollama_running() is False


class TestGetDefaultVisionModel:
    def test_finds_llava_model(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3:latest"},
                {"name": "llava:latest"},
            ]
        }
        with patch("ollama_client.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            model = get_default_vision_model()
            assert model == "llava:latest"

    def test_returns_none_when_no_vision_model(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama3:latest"}]
        }
        with patch("ollama_client.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            model = get_default_vision_model()
            assert model is None


class TestGetOllamaClient:
    def test_returns_none_when_ollama_not_running(self):
        with patch("ollama_client.is_ollama_running", return_value=False):
            assert get_ollama_client() is None

    def test_returns_client_when_vision_model_available(self):
        with patch("ollama_client.is_ollama_running", return_value=True), \
             patch("ollama_client.get_default_vision_model", return_value="llava:latest"):
            result = get_ollama_client()
            assert result is not None
            client, model = result
            assert model == "llava:latest"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest skills/document-extractor/augur/tests/test_ollama_client.py -v
```

- [ ] **Step 3: Implement ollama_client.py**

```python
# skills/document-extractor/scripts/ollama_client.py
"""Ollama client wrapper — OpenAI-compatible interface for local LLM."""
from __future__ import annotations

from typing import Any

import httpx

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_TIMEOUT = 3.0  # seconds for health checks

# Vision-capable models to look for (in priority order)
VISION_MODELS = ["llava", "llava-llama3", "bakllava", "moondream"]


def is_ollama_running() -> bool:
    """Check if Ollama server is responding."""
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=OLLAMA_TIMEOUT)
        return resp.status_code == 200
    except Exception:
        return False


def get_default_vision_model() -> str | None:
    """Find a vision-capable model in Ollama's installed models."""
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=OLLAMA_TIMEOUT)
        if resp.status_code != 200:
            return None
        models = resp.json().get("models", [])
        model_names = [m.get("name", "") for m in models]

        for vision_model in VISION_MODELS:
            for name in model_names:
                if name.startswith(vision_model):
                    return name
        return None
    except Exception:
        return None


def get_ollama_client(model: str | None = None) -> tuple[Any, str] | None:
    """Return OpenAI-compatible client pointing at local Ollama.

    Args:
        model: Specific model name. If None, auto-detects a vision model.

    Returns:
        Tuple of (OpenAI client, model name) or None if unavailable.
    """
    if not is_ollama_running():
        return None

    model = model or get_default_vision_model()
    if not model:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(base_url=f"{OLLAMA_BASE_URL}/v1", api_key="ollama")
        return client, model
    except ImportError:
        return None
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest skills/document-extractor/augur/tests/test_ollama_client.py -v
```

- [ ] **Step 5: Commit**

```bash
git add skills/document-extractor/scripts/ollama_client.py skills/document-extractor/augur/tests/test_ollama_client.py
git commit -m "feat(document-extractor): add Ollama client with vision model detection"
```

### Task 3b: Audio extractor (macOS native + fallback)

**Files:**
- Create: `skills/document-extractor/scripts/audio_extractor.py`

- [ ] **Step 1: Implement audio_extractor.py**

```python
# skills/document-extractor/scripts/audio_extractor.py
"""Audio transcription — macOS native via Swift helper, cross-platform via MarkItDown."""
from __future__ import annotations

import platform
import subprocess
import tempfile
from pathlib import Path

AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"}


def can_extract_audio() -> bool:
    """Check if audio extraction is available on this platform."""
    if platform.system() == "Darwin":
        return True  # macOS has SFSpeechRecognizer
    # Cross-platform: check if speech_recognition is available
    try:
        import speech_recognition
        return True
    except ImportError:
        return False


def extract_audio(path: str) -> str | None:
    """Extract text from audio file.

    Tries macOS native first, falls back to MarkItDown speech_recognition.

    Returns:
        Transcription text, or None if extraction unavailable.
    """
    if platform.system() == "Darwin":
        result = _extract_audio_macos(path)
        if result:
            return result

    # Cross-platform fallback via MarkItDown
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(path)
        if result.markdown and result.markdown.strip():
            return result.markdown
    except Exception:
        pass

    return None


def _extract_audio_macos(path: str) -> str | None:
    """Use macOS speech recognition via osascript/NSSpeechRecognizer."""
    # For now, delegate to MarkItDown which handles audio formats.
    # A dedicated Swift helper for SFSpeechRecognizer can be added later
    # when offline transcription is a priority (requires user authorization
    # and model download).
    return None  # Fall through to cross-platform path
```

Note: The macOS Swift helper is deferred — MarkItDown's cross-platform audio support covers the initial use case. The `_extract_audio_macos` stub is ready for a future Swift helper when offline transcription becomes a priority.

- [ ] **Step 2: Commit**

```bash
git add skills/document-extractor/scripts/audio_extractor.py
git commit -m "feat(document-extractor): add audio extractor with macOS stub and MarkItDown fallback"
```

---

## Phase 2: MCP Tools

### Task 4: Implement MCP tools (extract-document, submit, batch, status)

**Files:**
- Create: `skills/document-extractor/scripts/mcp/tools_extract.py`
- Create: `skills/document-extractor/scripts/mcp/__init__.py`
- Create: `skills/document-extractor/augur/tests/test_tools_extract.py`

- [ ] **Step 1: Write failing tests**

```python
# skills/document-extractor/augur/tests/test_tools_extract.py
"""Tests for document-extractor MCP tools."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from mcp.tools_extract import (
    extract_document_impl,
    submit_result_impl,
    extract_batch_impl,
    get_extraction_status_impl,
)


class TestExtractDocument:
    def test_extract_text_file(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("Hello, world!")
        result = json.loads(extract_document_impl(str(f), max_tier=0))
        assert result["success"] is True
        assert "Hello" in result["markdown"]
        assert result["tier_used"] == 0

    def test_extract_nonexistent(self):
        result = json.loads(extract_document_impl("/no/such/file.pdf", max_tier=0))
        assert result["success"] is False
        assert "error" in result

    def test_extract_csv(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b\n1,2\n3,4")
        result = json.loads(extract_document_impl(str(f), max_tier=0))
        assert result["success"] is True
        assert result["format"] == "csv"

    def test_includes_metadata(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        result = json.loads(extract_document_impl(str(f), include_metadata=True))
        assert "size_bytes" in result
        assert "extraction_time" in result


class TestSubmitResult:
    def test_submit_returns_merged_text(self):
        result = json.loads(submit_result_impl(
            request_id="ocr-1",
            result_text="Extracted text",
            source_path="/tmp/test.png",
        ))
        assert result["success"] is True
        assert result["request_id"] == "ocr-1"


class TestExtractBatch:
    def test_batch_multiple_files(self, tmp_path):
        (tmp_path / "a.txt").write_text("Alpha")
        (tmp_path / "b.txt").write_text("Beta")
        paths = json.dumps([str(tmp_path / "a.txt"), str(tmp_path / "b.txt")])
        result = json.loads(extract_batch_impl(paths, max_tier=0))
        assert result["success"] is True
        assert result["summary"]["total"] == 2
        assert result["summary"]["completed"] == 2

    def test_batch_with_missing_file(self, tmp_path):
        (tmp_path / "a.txt").write_text("Alpha")
        paths = json.dumps([str(tmp_path / "a.txt"), "/no/such/file.txt"])
        result = json.loads(extract_batch_impl(paths, max_tier=0))
        assert result["summary"]["total"] == 2
        # One succeeds, one fails
        successes = [r for r in result["results"] if r["success"]]
        assert len(successes) >= 1


class TestGetExtractionStatus:
    def test_returns_format_info(self):
        result = json.loads(get_extraction_status_impl())
        assert result["success"] is True
        assert "formats" in result
        assert "pdf_text" in result["formats"]
        assert "llm_integrations" in result
        assert "tier_available" in result

    def test_markitdown_version_present(self):
        result = json.loads(get_extraction_status_impl())
        assert "markitdown_version" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest skills/document-extractor/augur/tests/test_tools_extract.py -v
```

- [ ] **Step 3: Implement tools_extract.py**

```python
# skills/document-extractor/scripts/mcp/tools_extract.py
"""Document extraction MCP tools."""
from __future__ import annotations

import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_scripts_dir = Path(__file__).resolve().parents[1]
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from dataclasses import asdict
from extractor import extract, detect_available_tier, merge_llm_results, ExtractionResult
from ollama_client import is_ollama_running, get_default_vision_model
from src.logging import get_entity_logger

logger = get_entity_logger("document-extractor.tools")


def _result_to_json(result: ExtractionResult) -> dict[str, Any]:
    """Convert ExtractionResult to JSON-safe dict."""
    d = asdict(result)
    # Remove None fields for cleaner output
    return {k: v for k, v in d.items() if v is not None}


# ---------------------------------------------------------------------------
# extract-document
# ---------------------------------------------------------------------------

def extract_document_impl(
    path: str,
    max_tier: int = 1,
    include_metadata: bool = True,
) -> str:
    """Extract a document to Markdown."""
    result = extract(path, max_tier=max_tier)
    d = _result_to_json(result)
    if not include_metadata:
        for key in ("size_bytes", "extraction_time"):
            d.pop(key, None)
    return json.dumps(d)


# ---------------------------------------------------------------------------
# submit-extract-document-result
# ---------------------------------------------------------------------------

# In-memory store for pending LLM results (per-process)
_pending_results: dict[str, dict] = {}


def submit_result_impl(
    request_id: str,
    result_text: str,
    source_path: str,
) -> str:
    """Accept LLM OCR result and merge into extraction output."""
    key = source_path
    if key not in _pending_results:
        _pending_results[key] = {"partial": "", "results": {}, "meta": {}}

    _pending_results[key]["results"][request_id] = result_text

    # Check if all results are in
    pending = _pending_results[key]
    merged = merge_llm_results(
        pending.get("partial", ""),
        pending["results"],
    )

    return json.dumps({
        "success": True,
        "markdown": merged,
        "request_id": request_id,
        "total_results": len(pending["results"]),
    })


# ---------------------------------------------------------------------------
# extract-document-batch
# ---------------------------------------------------------------------------

def extract_batch_impl(paths_json: str, max_tier: int = 1) -> str:
    """Extract multiple documents to Markdown."""
    try:
        paths = json.loads(paths_json)
    except json.JSONDecodeError as e:
        return json.dumps({"success": False, "error": f"Invalid JSON: {e}"})

    if not isinstance(paths, list):
        return json.dumps({"success": False, "error": "Expected JSON array of paths"})

    results = []
    all_llm_requests = []
    completed = 0
    needs_llm = 0

    for i, path in enumerate(paths):
        result = extract(path, max_tier=max_tier)
        d = _result_to_json(result)
        d["path"] = path
        results.append(d)

        if result.needs_llm and result.llm_requests:
            # Prefix request IDs with batch index
            for req in result.llm_requests:
                req["id"] = f"batch-{i}-{req['id']}"
                req["source_path"] = path
                all_llm_requests.append(req)
            needs_llm += 1
        elif result.success:
            completed += 1

    response: dict[str, Any] = {
        "success": True,
        "results": results,
        "summary": {
            "total": len(paths),
            "completed": completed,
            "needs_llm": needs_llm,
            "failed": len(paths) - completed - needs_llm,
        },
    }
    if all_llm_requests:
        response["llm_requests"] = all_llm_requests

    return json.dumps(response)


# ---------------------------------------------------------------------------
# get-extraction-status
# ---------------------------------------------------------------------------

def get_extraction_status_impl() -> str:
    """Report extraction capabilities and LLM integration status."""
    # Check MarkItDown
    try:
        import markitdown
        md_version = getattr(markitdown, "__version__", "unknown")
    except ImportError:
        md_version = "not installed"

    # Check format support
    formats = {
        "pdf_text": {"available": md_version != "not installed", "engine": "pdfminer"},
        "pdf_scanned": {"available": False, "requires": "llm_tier_1"},
        "docx": {"available": _check_import("docx"), "engine": "python-docx"},
        "pptx": {"available": _check_import("pptx"), "engine": "python-pptx"},
        "xlsx": {"available": _check_import("openpyxl"), "engine": "openpyxl"},
        "images": {"available": False, "requires": "llm_tier_1"},
        "html": {"available": md_version != "not installed", "engine": "markitdown"},
        "audio": {"available": platform.system() == "Darwin", "engine": "apple_speech" if platform.system() == "Darwin" else "speech_recognition"},
        "csv": {"available": True, "engine": "markitdown"},
        "json": {"available": True, "engine": "markitdown"},
        "text": {"available": True, "engine": "direct"},
    }

    # Check LLM integrations
    claude_cli = shutil.which("claude")
    ollama_running = is_ollama_running()
    vision_model = get_default_vision_model() if ollama_running else None

    llm_integrations = {
        "claude_cli": {"installed": claude_cli is not None, "path": claude_cli or "not found"},
        "ollama": {"running": ollama_running, "url": "http://localhost:11434"},
        "ollama_vision_model": {"installed": vision_model is not None, "model": vision_model or "none"},
        "preferred_cli": "claude" if claude_cli else ("ollama" if ollama_running else "none"),
    }

    # Update scanned PDF and image availability based on LLM
    if ollama_running and vision_model:
        formats["pdf_scanned"]["available"] = True
        formats["pdf_scanned"]["engine"] = f"markitdown-ocr + {vision_model}"
        formats["images"]["available"] = True
        formats["images"]["engine"] = f"llm_vision + {vision_model}"

    tier = detect_available_tier()

    return json.dumps({
        "success": True,
        "formats": formats,
        "llm_integrations": llm_integrations,
        "tier_available": tier,
        "markitdown_version": md_version,
        "platform": platform.system().lower(),
    })


def _check_import(module: str) -> bool:
    """Check if a Python module is importable."""
    try:
        __import__(module)
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# MCP registration
# ---------------------------------------------------------------------------

def register_extract_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable,
    metrics: Any = None,
) -> None:
    """Register document extraction MCP tools."""
    from ._shared import tool_annotations

    @mcp.tool(
        name="extract-document",
        annotations=tool_annotations({
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        }),
    )
    @mcp_tool_interceptor
    async def extract_document_tool(
        path: str,
        max_tier: int = 1,
        include_metadata: bool = True,
    ) -> str:
        """Extract any document to Markdown. Supports PDF, DOCX, PPTX, XLSX, HTML, images, audio, text.

        Args:
            path: File path to extract.
            max_tier: Max extraction tier (0=offline, 1=with LLM if available).
            include_metadata: Include size, format, timing in response.

        Returns:
            JSON with markdown content. May include needs_llm=true with llm_requests
            if the document needs OCR and an AI client is calling.
        """
        return extract_document_impl(path, max_tier, include_metadata)

    @mcp.tool(
        name="submit-extract-document-result",
        annotations=tool_annotations({
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def submit_result_tool(
        request_id: str,
        result_text: str,
        source_path: str,
    ) -> str:
        """Submit LLM OCR/description result for a pending extraction request.

        Called by AI clients after processing llm_requests from extract-document.

        Args:
            request_id: The request ID from llm_requests[].id.
            result_text: The LLM's extracted text or description.
            source_path: Original file path (for merging context).
        """
        return submit_result_impl(request_id, result_text, source_path)

    @mcp.tool(
        name="extract-document-batch",
        annotations=tool_annotations({
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        }),
    )
    @mcp_tool_interceptor
    async def extract_batch_tool(
        paths: str,
        max_tier: int = 1,
    ) -> str:
        """Extract multiple documents to Markdown in batch.

        Args:
            paths: JSON array of file paths.
            max_tier: Max extraction tier (0=offline, 1=with LLM).

        Returns:
            JSON with per-file results, aggregated llm_requests, and summary counts.
        """
        return extract_batch_impl(paths, max_tier)

    @mcp.tool(
        name="get-extraction-status",
        annotations=tool_annotations({
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def get_extraction_status_tool() -> str:
        """Report extraction capabilities, supported formats, and LLM integration status.

        Returns installed format support, Ollama status, Claude CLI availability,
        and the current maximum extraction tier.
        """
        return get_extraction_status_impl()
```

- [ ] **Step 4: Create __init__.py**

```python
# skills/document-extractor/scripts/mcp/__init__.py
"""Document extractor MCP tool registration."""
from .tools_extract import register_extract_tools


def register_tools(mcp, mcp_tool_interceptor, metrics=None):
    register_extract_tools(mcp, mcp_tool_interceptor, metrics)
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest skills/document-extractor/augur/tests/test_tools_extract.py -v
```

- [ ] **Step 6: Commit**

```bash
git add skills/document-extractor/scripts/mcp/ skills/document-extractor/augur/tests/test_tools_extract.py
git commit -m "feat(document-extractor): add extract-document, batch, submit, and status MCP tools"
```

---

## Phase 3: Consumer Migration

### Task 5: Migrate file-manager scan-folder to use document-extractor

**Files:**
- Modify: `skills/file-manager/scripts/mcp/tools_organize.py:109-119`

- [ ] **Step 1: Read the current content_sample logic**

Read `skills/file-manager/scripts/mcp/tools_organize.py` lines 95-125.

- [ ] **Step 2: Replace text-only sampling with universal extraction**

Find the content_sample block in `_file_entry()` that checks `TEXT_EXTENSIONS` and replace it:

```python
# Before (text-only):
if include_content and path.suffix.lower() in TEXT_EXTENSIONS and size < 50_000:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        entry["content_sample"] = content[:CONTENT_SAMPLE_MAX]
    except OSError:
        pass

# After (universal via document-extractor):
if include_content and size < 50_000:
    try:
        from src.config.paths import get_skills_dir
        _de_scripts = get_skills_dir() / "document-extractor" / "scripts"
        if str(_de_scripts) not in sys.path:
            sys.path.insert(0, str(_de_scripts))
        from extractor import extract
        ext_result = extract(str(path), max_tier=0)  # Tier 0 for speed
        if ext_result.success and ext_result.markdown:
            entry["content_sample"] = ext_result.markdown[:CONTENT_SAMPLE_MAX]
    except Exception as e:
        logger.debug("Content extraction failed for %s: %s", path, e)
```

No fallback — if document-extractor fails, the file gets no content_sample. Per rule 5, fix the root cause rather than papering over with a fallback.

- [ ] **Step 3: Run file-manager tests**

```bash
python -m pytest skills/file-manager/augur/tests/ -v
```

- [ ] **Step 4: Commit**

```bash
git add skills/file-manager/scripts/mcp/tools_organize.py
git commit -m "feat(file-manager): use document-extractor for content sampling in scan-folder"
```

### Task 6: Migrate RAG unified_indexer to use document-extractor

**Files:**
- Modify: `skills/rag/scripts/unified_indexer.py:148-161`

- [ ] **Step 1: Read the current binary_extractor import**

Read `skills/rag/scripts/unified_indexer.py` lines 145-165.

- [ ] **Step 2: Modify binary_extractor.extract_binary to delegate to document-extractor**

In `skills/rag/scripts/binary_extractor.py`:
1. Rename the current `extract_binary` function to `_legacy_extract_binary`
2. Create a new `extract_binary` that delegates to document-extractor:

```python
def extract_binary(path: Path) -> dict[str, Any]:
    """Extract text from a binary document.

    Delegates to document-extractor skill for actual extraction.
    """
    from src.config.paths import get_skills_dir
    _de_scripts = str(get_skills_dir() / "document-extractor" / "scripts")
    if _de_scripts not in sys.path:
        sys.path.insert(0, _de_scripts)
    from extractor import extract

    result = extract(str(path), max_tier=0)
    return {
        "format": result.format,
        "size_bytes": result.size_bytes,
        "created": datetime.now(timezone.utc).isoformat(),
        "body": result.markdown if result.success else "",
        "extraction_error": result.error,
    }
```

No fallback to legacy — per rule 5, if document-extractor is broken, fix it.

- [ ] **Step 3: Run RAG tests**

```bash
python -m pytest skills/rag/augur/tests/ -v 2>&1 | tail -20
```

- [ ] **Step 4: Commit**

```bash
git add skills/rag/scripts/binary_extractor.py
git commit -m "feat(rag): delegate binary extraction to document-extractor skill"
```

---

## Phase 4: Dashboard

### Task 7: Create integrations status dashboard page

**Files:**
- Create: `skills/document-extractor/augur/dashboard/page.tsx`

- [ ] **Step 1: Read existing dashboard patterns**

Read `docs/agent-topics/DASHBOARD.md` and an existing command hub page for patterns. Check how `useMcpQuery` is used.

- [ ] **Step 2: Create the page**

The page shows three sections from `get-extraction-status` MCP tool:

1. **Extraction Capabilities** — table of formats with green/yellow/red status
2. **LLM Integration Status** — cards for Claude CLI, Ollama, vision model
3. **Quick Actions** — test extraction button

Use `useMcpQuery` with `get-extraction-status` tool. Use shadcn/ui Card, Table, Badge components.

- [ ] **Step 3: Verify compilation**

```bash
pnpm --filter dashboard typecheck 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
git add skills/document-extractor/augur/dashboard/
git commit -m "feat(document-extractor): add integrations status dashboard page"
```

---

## Phase 5: Verification

### Task 8: End-to-end verification

- [ ] **Step 1: Run all document-extractor tests**

```bash
python -m pytest skills/document-extractor/augur/tests/ -v
```

- [ ] **Step 2: Run file-manager tests**

```bash
python -m pytest skills/file-manager/augur/tests/ -v
```

- [ ] **Step 3: Verify MCP tools register**

```bash
python -c "
import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'skills/document-extractor/scripts')
from mcp.tools_extract import get_extraction_status_impl
import json
status = json.loads(get_extraction_status_impl())
print(f'Tier available: {status[\"tier_available\"]}')
print(f'Formats: {list(status[\"formats\"].keys())}')
print(f'MarkItDown: {status[\"markitdown_version\"]}')
print(f'Ollama: {status[\"llm_integrations\"][\"ollama\"]}')
"
```

- [ ] **Step 4: Test extraction on real Desktop files**

```bash
python -c "
import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'skills/document-extractor/scripts')
from extractor import extract
import json

# Test text PDF
result = extract('~/Desktop/PaySlip2026-02.pdf', max_tier=0)
print(f'PDF: success={result.success}, {len(result.markdown)} chars, tier={result.tier_used}')

# Test image
result = extract('~/Desktop/Screenshot 2026-03-25 at 15.44.10.png', max_tier=0)
print(f'Image (tier 0): success={result.success}, needs_llm={result.needs_llm}')
"
```

- [ ] **Step 5: Test scan-folder with improved content sampling**

```bash
python -c "
import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'skills/file-manager/scripts')
import json
from mcp.tools_organize import scan_folder_impl

result = json.loads(scan_folder_impl('~/Desktop', include_content_sample=True))
files_with_content = [f for f in result['files'] if f.get('content_sample')]
files_without = [f for f in result['files'] if not f.get('content_sample')]
print(f'Files with content sample: {len(files_with_content)}')
print(f'Files without: {len(files_without)}')
for f in files_with_content[:5]:
    print(f'  {f[\"name\"]}: {f[\"content_sample\"][:60]}...')
"
```

Expected: More files now have content samples (PDFs, DOCX) compared to the text-only baseline.

- [ ] **Step 6: Verify organizer references cleaned up**

```bash
rg "binary_extractor" skills/ --type py -l
```

Should show only `skills/rag/scripts/binary_extractor.py` (the file itself) and `skills/rag/scripts/unified_indexer.py` (imports it).
