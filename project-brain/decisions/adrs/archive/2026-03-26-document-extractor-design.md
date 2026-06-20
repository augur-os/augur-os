# Universal Document Extraction — `document-extractor` Skill

**Date:** 2026-03-26
**Status:** Draft
**Scope:** New infrastructure skill, MarkItDown integration, LLM-Assisted MCP pattern, consumer migration, dashboard page
**ADR:** ADR-518
**Architecture Pattern:** `docs/references/llm-assisted-mcp-pattern.md`

## Problem

Augur's content extraction is fragmented: `binary_extractor.py` (RAG) handles some formats without OCR, `scan-folder` (file-manager) only samples plain text, knowledge skill's OCR is beta/non-functional. File-manager triage can't read 50%+ of Desktop files — PDFs, Office docs, images, Hebrew documents all go to "pending" because no content is available for routing.

## Design

### 1. New Skill: `document-extractor`

Infrastructure skill in the command hub. Wraps Microsoft's MarkItDown library and exposes universal document-to-Markdown extraction via MCP tools.

```
skills/document-extractor/
├── SKILL.md
├── config.yaml                    # Dashboard page contributions
├── scripts/
│   ├── extractor.py               # Core: MarkItDown wrapper + tier detection
│   ├── ollama_client.py           # OpenAI-compatible wrapper for local Ollama
│   ├── audio_extractor.py         # macOS-native + cross-platform audio transcription
│   └── mcp/
│       ├── __init__.py
│       └── tools_extract.py       # MCP tool registration + impl functions
├── augur/
│   ├── dashboard/
│   │   └── page.tsx               # Integrations status page
│   └── tests/
│       ├── conftest.py
│       ├── test_extractor.py
│       └── test_tools_extract.py
├── assets/
│   └── seeds/
└── evals/
```

**SKILL.md frontmatter:**
```yaml
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
---
```

**Python dependency:** Add `markitdown[all]` and `markitdown-ocr` to `pyproject.toml`.

### 2. Tiered Extraction

All extraction starts at tier 0 (pure parsing, no LLM). LLM-assisted processing is additive, only for inputs that need it.

**Tier 0 — Always available, offline, no LLM:**

| Format | Engine | Output |
|--------|--------|--------|
| PDF (text-based) | MarkItDown / pdfminer | Structured Markdown with headings, tables |
| DOCX | MarkItDown / python-docx | Markdown preserving document structure |
| PPTX | MarkItDown / python-pptx | Slide-by-slide Markdown |
| XLSX / XLS | MarkItDown / openpyxl | Tables as Markdown |
| HTML | MarkItDown parser | Clean Markdown |
| CSV, JSON, YAML, XML | MarkItDown | Formatted Markdown |
| Plain text (.txt, .md, .log, .py, .ts, etc.) | Direct read | As-is |
| Images | EXIF metadata only | Metadata block (no content) |
| Audio (macOS) | Apple Speech Recognition (`SFSpeechRecognizer`) | Transcription as Markdown |
| Audio (cross-platform) | MarkItDown `speech_recognition` dep | Transcription as Markdown |

**Tier 1 — LLM-assisted (requires AI client or local Ollama):**

| Format | Capability | How |
|--------|-----------|-----|
| Images (.png, .jpg, .heic, etc.) | Content description + OCR | LLM Vision via calling agent |
| Scanned PDFs (no text layer) | Full page OCR | LLM Vision via `markitdown-ocr` plugin or calling agent |
| Image-heavy Office docs | Embedded image text extraction | LLM Vision per image |

### 3. LLM-Assisted MCP Pattern Implementation

Per `docs/references/llm-assisted-mcp-pattern.md`:

**Context detection:**
```python
def is_ai_client_context() -> bool:
    return bool(
        os.environ.get("CLAUDE_CODE_ENTRY_POINT")
        or os.environ.get("CODEX_SESSION")
        or os.environ.get("GEMINI_SESSION")
        or os.environ.get("AUGUR_AGENT_SESSION")
    )
```

**Inside AI client:** Tool returns `{needs_llm: true, llm_requests: [...]}`. The calling AI agent processes each request and calls `submit-extract-document-result` with results.

**Outside AI client (daemon/dashboard):** Tool spawns a configured CLI agent session. CLI config stored in `get_skill_vault_dir("document-extractor")/config.yaml`:

```yaml
llm_cli:
  preferred: claude          # First choice: Claude Code CLI
  fallback: ollama           # Second choice: Ollama with vision model
  ollama_model: llava        # Vision-capable model
  timeout: 120               # Max seconds per CLI session
```

Resolution order: `claude` CLI → `ollama run <model>` → tier 0 only (graceful degradation).

**CLI spawning mechanism (Mode 2 detail):**

When `is_ai_client_context()` returns False and OCR is needed, the tool spawns a CLI session:

```python
def _spawn_cli_for_ocr(file_path: str, llm_requests: list[dict]) -> list[dict]:
    """Spawn a CLI agent to process OCR requests."""
    config = _load_cli_config()
    cli = config.get("preferred", "claude")

    # Build a focused prompt with the file and OCR requests serialized
    prompt = f"""Process these OCR requests using the extract-document MCP tool.
    File: {file_path}
    Call submit-extract-document-result for each with the extracted text.
    Requests: {json.dumps(llm_requests)}"""

    if cli == "claude":
        result = subprocess.run(
            ["claude", "--print", "--prompt", prompt],
            capture_output=True, text=True, timeout=config.get("timeout", 120),
            env={**os.environ, "AUGUR_AGENT_SESSION": "true"},
        )
    elif cli == "ollama":
        # For Ollama: MarkItDown handles OCR internally via the OpenAI-compatible client
        # No need to spawn a CLI — just re-run extraction with Ollama client
        client, model = get_ollama_client(config.get("ollama_model", "llava"))
        if client:
            md = MarkItDown(enable_plugins=True, llm_client=client, llm_model=model)
            result = md.convert(file_path)
            return [{"id": req["id"], "text": result.markdown} for req in llm_requests]

    # Parse CLI output for results
    return _parse_cli_results(result.stdout)
```

Note: The Ollama path is simpler — no CLI spawning needed. Since Ollama is a local service, MarkItDown can call it directly via the OpenAI-compatible API. Only the Claude CLI path requires subprocess spawning.

### 4. MCP Tools

#### `extract-document`

Main extraction tool. Returns Markdown for any supported file.

```python
async def extract_document(
    path: str,                     # File path to extract
    max_tier: int = 1,             # 0=offline only, 1=with LLM if available
    include_metadata: bool = True  # Include size, format, timestamps
) -> str:  # JSON
```

**Response — tier 0 success (no LLM needed):**
```json
{
  "success": true,
  "markdown": "# Document Title\n\nContent...",
  "title": "Document Title",
  "tier_used": 0,
  "format": "pdf",
  "size_bytes": 45800,
  "extraction_time": 0.34,
  "ocr_applied": false
}
```

**Response — needs LLM (AI client calling):**
```json
{
  "success": true,
  "needs_llm": true,
  "partial_markdown": "# Page 1\n\n[Image: page requires OCR]\n\n# Page 2\n\nSome text...",
  "llm_requests": [
    {"id": "ocr-1", "type": "image_ocr", "image_base64": "...", "page": 1, "prompt": "Extract all text from this document page, preserving structure."}
  ],
  "format": "pdf",
  "tier_used": 0,
  "instructions": "Process each llm_request image and call submit-extract-document-result with the text."
}
```

**Response — needs LLM but no AI client and max_tier=0:**
```json
{
  "success": true,
  "markdown": "[No text content — scanned PDF requires OCR]",
  "tier_used": 0,
  "format": "pdf",
  "ocr_available": false,
  "note": "Set max_tier=1 or run from an AI client for OCR extraction"
}
```

#### `submit-extract-document-result`

Companion tool for the LLM callback protocol.

```python
async def submit_extraction_result(
    request_id: str,     # From llm_requests[].id
    result_text: str,    # LLM's OCR/description output
    source_path: str     # Original file (for merging context)
) -> str:  # JSON — final merged markdown
```

The tool merges the LLM output into the partial markdown, replacing `[Image: page requires OCR]` placeholders with actual text.

#### `extract-document-batch`

Batch extraction for multiple files. Returns partial results — files that succeed at tier 0 return immediately, files needing LLM are flagged.

```python
async def extract_document_batch(
    paths: str,           # JSON array of file paths
    max_tier: int = 1
) -> str:  # JSON
```

**Response:**
```json
{
  "success": true,
  "results": [
    {"path": "/tmp/report.pdf", "success": true, "markdown": "...", "tier_used": 0},
    {"path": "/tmp/scan.pdf", "success": true, "needs_llm": true, "partial_markdown": "..."}
  ],
  "llm_requests": [
    {"id": "batch-0-ocr-1", "type": "image_ocr", "image_base64": "...", "source_path": "/tmp/scan.pdf", "page": 1}
  ],
  "summary": {"total": 2, "completed": 1, "needs_llm": 1}
}
```

Each `llm_request.id` encodes the file index (`batch-{file_idx}-ocr-{page}`) so the caller can associate results with files. The caller processes all requests and calls `submit-extract-document-result` once per request. Each submit call returns the updated state; the final submit returns the fully merged batch result.

#### `get-extraction-status`

Health and capability check.

```python
async def get_extraction_status() -> str:  # JSON
```

**Response:**
```json
{
  "success": true,
  "formats": {
    "pdf_text": {"available": true, "engine": "pdfminer"},
    "pdf_scanned": {"available": false, "requires": "llm_tier_1"},
    "docx": {"available": true, "engine": "python-docx"},
    "pptx": {"available": true, "engine": "python-pptx"},
    "xlsx": {"available": true, "engine": "openpyxl"},
    "images": {"available": false, "requires": "llm_tier_1"},
    "audio": {"available": true, "engine": "apple_speech"},
    "html": {"available": true, "engine": "markitdown"}
  },
  "llm_integrations": {
    "claude_cli": {"installed": true, "path": "/usr/local/bin/claude"},
    "ollama": {"running": true, "url": "http://localhost:11434"},
    "ollama_vision_model": {"installed": true, "model": "llava", "size": "4.7GB"},
    "preferred_cli": "claude"
  },
  "tier_available": 1,
  "markitdown_version": "0.1.x",
  "platform": "darwin"
}
```

### 5. Core Implementation: `extractor.py`

```python
@dataclass
class ExtractionResult:
    success: bool
    markdown: str
    title: str | None
    tier_used: int
    format: str
    size_bytes: int
    extraction_time: float
    ocr_applied: bool
    needs_llm: bool = False
    llm_requests: list[dict] | None = None
    partial_markdown: str | None = None
```

**Key functions:**

- `detect_available_tier() -> int` — checks env vars, Ollama, CLI availability
- `extract(path, max_tier=1) -> ExtractionResult` — main extraction entry point
- `merge_llm_results(partial_markdown, results: list[dict]) -> str` — merges OCR text into placeholders

**MarkItDown initialization:**
```python
def _get_markitdown(tier: int) -> MarkItDown:
    if tier == 0:
        return MarkItDown()
    if tier == 1:
        client, model = _get_llm_client()
        return MarkItDown(enable_plugins=True, llm_client=client, llm_model=model)
```

**LLM client resolution:**
```python
def _get_llm_client() -> tuple[OpenAI, str] | None:
    # Check Ollama first (local, no cost)
    if _ollama_running():
        model = _get_ollama_vision_model()
        if model:
            return OpenAI(base_url="http://localhost:11434/v1", api_key="ollama"), model
    return None  # No local LLM — will use LLM-Assisted MCP pattern instead
```

When `_get_llm_client()` returns a client (Ollama available), MarkItDown handles OCR internally at tier 1. When it returns None and OCR is needed, the tool falls back to the LLM-Assisted MCP callback pattern.

### 6. Audio Extraction: `audio_extractor.py`

**macOS native path (tier 0):**

Uses a compiled Swift helper script that calls `SFSpeechRecognizer` and outputs text to stdout. This avoids PyObjC complexity. The helper is a small Swift file compiled on first use via `swiftc` and cached.

Note: `SFSpeechRecognizer` requires one-time user authorization (macOS privacy prompt). On-device models must be downloaded for offline use. If authorization is denied or models unavailable, falls back to MarkItDown's cross-platform path.

```python
def extract_audio_macos(path: str) -> str | None:
    """Use Apple Speech Recognition via compiled Swift helper."""
    helper = _ensure_swift_helper_compiled()
    result = subprocess.run([helper, path], capture_output=True, text=True, timeout=120)
    if result.returncode == 0:
        return result.stdout
    return None  # Fall back to cross-platform
```

**Cross-platform fallback:**
MarkItDown's `speech_recognition` optional dependency. Primarily supports `.wav` format; other formats may require `ffmpeg` for conversion.

**Format support:** `.wav` (native), `.mp3`, `.m4a` (require `ffmpeg` for conversion to wav)

### 7. Ollama Client: `ollama_client.py`

Thin module — Ollama already exposes an OpenAI-compatible API:

```python
from openai import OpenAI

def get_ollama_client(model: str | None = None) -> tuple[OpenAI, str] | None:
    """Return OpenAI-compatible client pointing at local Ollama, or None."""
    if not _ollama_running():
        return None
    model = model or _get_default_vision_model()
    if not model:
        return None
    return OpenAI(base_url="http://localhost:11434/v1", api_key="ollama"), model

def _ollama_running() -> bool:
    """Check if Ollama server is responding."""
    # GET http://localhost:11434/api/tags with 2s timeout

def _get_default_vision_model() -> str | None:
    """Find a vision-capable model in Ollama's model list."""
    # Check for: llava, llava-llama3, bakllava, moondream
    # Return first found, or None
```

### 8. Consumer Migration

**Cross-skill import pattern:** Consumers import the extractor via `sys.path` manipulation, consistent with the project's existing cross-skill import pattern (see `skills/attention/scripts/mcp/tools_attention.py` for precedent):

```python
import sys
from pathlib import Path
from src.config.paths import get_skills_dir

_extractor_scripts = get_skills_dir() / "document-extractor" / "scripts"
if str(_extractor_scripts) not in sys.path:
    sys.path.insert(0, str(_extractor_scripts))

from extractor import extract
```

#### file-manager `scan-folder`

Replace text-only content sampling with universal extraction:

```python
# In tools_organize.py, _file_entry():
# Before:
if include_content and path.suffix.lower() in TEXT_EXTENSIONS and size < 50_000:
    content = path.read_text(...)[:CONTENT_SAMPLE_MAX]

# After:
if include_content and size < 50_000:
    result = extract(str(path), max_tier=0)  # Tier 0 for speed
    if result.success and result.markdown:
        entry["content_sample"] = result.markdown[:CONTENT_SAMPLE_MAX]
```

For files larger than 50KB or needing OCR, the AI client can call `extract-document` directly at tier 1.

#### RAG `unified_indexer.py`

Replace `binary_extractor.py` import:

```python
# Before:
from binary_extractor import extract_binary
body = extract_binary(path)["body"]

# After:
result = extract(str(path), max_tier=0)
body = result.markdown if result.success else ""
```

#### knowledge skill

`knowledge-summarize-file` uses CLIBridge, not binary_extractor — no migration needed. The knowledge skill's `file_metadata_extractor.py` becomes redundant but is not deleted immediately (deprecated, separate cleanup).

#### Delete `binary_extractor.py`

After RAG and file-manager consumers migrate: delete `skills/rag/scripts/binary_extractor.py`.

### 9. Dashboard: Integrations Status Page

One page at `/command/document-extractor` contributed to the command hub (or integration browse tab).

**Three sections:**

**Extraction Capabilities** — table from `get-extraction-status` showing each format, availability, and engine. Green/yellow/red status indicators.

**LLM Integration Status** — cards showing:
- Claude CLI: detected path, version
- Ollama: running/stopped/not installed, URL
- Ollama vision model: model name, size, installed status
- Preferred CLI: current config value

**Quick Actions:**
- "Pull LLaVA model" button → fires action that runs `ollama pull llava`
- "Test extraction" → fires action that runs `extract-document` on a sample file and shows result
- "Configure CLI preference" → edit config

All data via `useMcpQuery` with `get-extraction-status`. Actions via `useMcpMutation`.

### 10. SKILL.md `x-augur-file-intake` Note

`document-extractor` does NOT declare `x-augur-file-intake`. It's an infrastructure skill — it processes files on behalf of other skills, it doesn't accept file routing itself.

## Implementation Order

1. **Scaffold skill** — directory structure, SKILL.md, conftest.py, pyproject.toml dependency
2. **Core extractor** — `extractor.py` with MarkItDown wrapper, ExtractionResult, tier detection, extract()
3. **Ollama client** — `ollama_client.py` with health check, model detection, OpenAI wrapper
4. **Audio extractor** — `audio_extractor.py` with macOS native + cross-platform fallback
5. **MCP tools** — `extract-document`, `submit-extract-document-result`, `extract-document-batch`, `get-extraction-status`
6. **Consumer migration: scan-folder** — replace text-only sampling with extract()
7. **Consumer migration: RAG indexing** — replace binary_extractor with extract()
8. **Consumer migration: knowledge** — replace binary_extractor with extract()
9. **Delete binary_extractor.py**
10. **Dashboard page** — integrations status with format table, LLM status, quick actions
11. **Verification** — end-to-end test with Desktop folder scan showing improved triage

## Supersedes

- `skills/rag/scripts/binary_extractor.py` — deleted after migration
- `skills/knowledge/scripts/file_metadata_extractor.py` — made redundant (not deleted immediately, but deprecated)
- Knowledge skill OCR beta — replaced by LLM-Assisted MCP pattern
