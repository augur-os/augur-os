---
title: AI PC Brain Inbox Design
date: 2026-05-07
status: approved-for-planning
scope: design
---

# AI PC Brain Inbox Design

## Purpose

Build a local-first Brain Inbox demo that shows Augur using this Windows AI PC to turn messy Desktop files into organized, searchable brain knowledge.

The core demo:

1. User configures Desktop as an inbox folder.
2. User drops mixed files there: text PDFs, scanned PDFs or photos, Office files, and MP3 meeting recordings.
3. User clicks **Consume** in Brain Inbox.
4. Augur extracts or transcribes locally first, classifies and renames files, routes them to the right vault or document location, writes RAG source descriptions, indexes them, and shows what changed.
5. Only when local capability is not enough, and policy allows it, Augur escalates to a cloud vision or audio model.

The product promise is: local files become organized knowledge, searchable context, and useful next actions, with clear evidence of what ran locally and what needed escalation.

## Current State

The current codebase already has several useful pieces:

- `document-extractor` skill with MarkItDown-based extraction and an MCP surface.
- PyMuPDF and MarkItDown installed in the Augur venv, which are good enough for text PDFs and common Office-like inputs.
- Tesseract support in code, but Tesseract is not installed on this machine.
- Audio extraction module exists, but it is mostly a MarkItDown/stub path and is not a real local transcript pipeline yet.
- Dashboard pages for `/brain/inbox` and `/brain/insights` exist, but backend MCP tools such as `inbox-folders`, `inbox-consume-folder`, and `brain-insights` are not implemented in the current runtime.
- RAG index artifacts exist and include vault content, so the demo can build on the current RAG layer rather than inventing a new search system.
- Ollama is installed with local models including `qwen3.5:latest` and `gemma4:latest`; both report vision capability through `ollama show`.

The main gaps are backend workflow implementation, real local OCR/transcription setup, local hardware capability detection, and policy-controlled escalation.

## Goals

- Provide a complete click-to-consume Desktop inbox workflow.
- Use local extraction, OCR, transcription, and local Ollama agents before cloud escalation.
- Make airplane mode a hard local-only policy gate.
- Use this AI PC's CPU, Intel Graphics, shared memory, and Intel AI Boost NPU where the backend supports it.
- Generate useful RAG source cards, not only raw OCR or transcript text.
- Show file-level status and capability evidence in Brain Inbox and Brain Insights.
- Keep safety and auditability visible: every move, rename, skip, escalation, failure, and index result is recorded.

## Non-Goals

- Fully autonomous background watching in the first pass. Manual **Consume** is the trusted demo path.
- Perfect document understanding for every possible format.
- Permanent deletion or destructive cleanup.
- Hand-writing compiled wiki pages. Wiki compounding remains concept-first and tool-driven.
- Assuming NPU acceleration for every model. Backend choice must be measured and recorded.

## Recommended Approach

Use a **local-first pipeline with a visible capability ladder**.

The backend should treat extraction as a staged decision tree:

1. Try deterministic local parsing.
2. Try local OCR or local transcription.
3. Try accelerated local backends when installed and beneficial.
4. Try local Ollama vision/audio-capable agents for hard interpretation.
5. If airplane mode is off and policy allows it, escalate low-confidence cases to cloud.
6. If confidence is still low or cloud is blocked, mark the item for review instead of pretending success.

This approach gives the strongest product story: the user sees a real demo, the laptop's local capabilities matter, and cloud remains a fallback instead of the main path.

## Architecture

### 1. Inbox Workflow Layer

The inbox workflow owns:

- folder registry for Desktop, Downloads, and custom folders
- scan previews and file stability checks
- consume runs
- run history and per-file results
- user-visible status for completed, partial, failed, skipped, escalated, and review-needed items

The workflow stores runtime records under `get_runtime_dir()`, not in the repo or vault source content.

### 2. Local Understanding Layer

The local understanding layer provides one stable API for:

- text extraction
- scanned document OCR
- image/photo OCR and description
- audio transcription
- transcript summarization
- extraction confidence scoring
- local/cloud backend metadata

The layer should reuse the existing `src.lib.extraction` and `src.lib.index.document_understanding` entry points, then extend them where needed.

### 3. Brain Routing Layer

The routing layer turns extracted content into a decision:

- content kind
- title
- summary
- destination folder
- normalized filename
- tags
- route reason
- confidence
- source card path
- review reason, if ambiguous

Classification should prefer deterministic rules where they are clear, then use local LLM or cloud LLM only when needed and allowed.

### 4. RAG And Insight Layer

The RAG layer receives high-quality source cards and extracted Markdown or transcripts.

Each consumed file should produce a concise Markdown source card with YAML frontmatter. The card links to the original file and extracted/transcribed text, summarizes content, records route and confidence, and lists any action items.

Brain Insights should show the payoff:

- imported file summaries
- meeting summaries
- action items
- review-needed files
- RAG indexing state
- pending wiki compounding state

## Capability Ladder

### Documents And Images

1. **Native text extraction**
   - Use PyMuPDF and MarkItDown for text PDFs, Office docs, HTML, CSV, TXT, and Markdown.
   - This path is fast, deterministic, and should be the first source of truth.

2. **Local OCR**
   - Use local OCR for scanned PDFs and photos.
   - The first implementation should add the missing runtime pieces: PDF page rendering, image preprocessing, and an OCR backend.
   - OpenVINO is the preferred AI PC acceleration target.
   - Tesseract remains a simple fallback where exact text OCR is sufficient.

3. **Local vision agent**
   - Use local Ollama vision models for hard visual interpretation, classification, document type detection, and layout/context understanding.
   - Do not treat local vision as automatically better than OCR. For exact numbers, dates, totals, IDs, and tables, deterministic OCR remains the source of truth unless benchmarking proves otherwise.

4. **Cloud escalation**
   - Escalate only when local confidence is low and policy allows it.
   - Escalation reasons include empty output, bad symbol ratio, missing key fields, handwriting, table/layout failure, form complexity, or user-selected high-accuracy mode.

### Audio

1. **Local transcription**
   - Add a real local Whisper-style transcription pipeline.
   - Use `ffmpeg` for MP3 decoding.
   - Prefer OpenVINO-backed inference so CPU, GPU, or NPU can be selected where supported.
   - Output transcript text, timestamps, language, duration, backend, and confidence where available.

2. **Meeting understanding**
   - Generate a source card with summary, topics, decisions, action items, people or organizations when detected, and follow-up questions.
   - Keep the original MP3 linked from the source card.

3. **Cloud escalation**
   - Escalate only for low-confidence transcription, poor audio, complex speaker separation, or high-accuracy mode.
   - If airplane mode is on, do not cloud-escalate.

## Airplane Mode Policy

Airplane mode is a hard cloud policy gate.

When airplane mode is enabled:

- no cloud vision, audio, text, or classification calls are allowed
- escalation can only move to stronger local backends
- local Ollama agents are allowed
- local OpenVINO, Tesseract, Whisper, PyMuPDF, and MarkItDown are allowed
- unresolved files become `needs_review` or `local_low_confidence`

When airplane mode is disabled:

- local-first ordering still applies
- cloud escalation remains policy-driven, not automatic for every file
- every cloud use must have an explicit escalation reason in the run record

## Local Benchmark And Calibration

The implementation should include a small local demo benchmark set:

- text PDF
- scanned invoice or receipt
- Hebrew/English form
- photo of a document
- screenshot
- MP3 meeting sample

Each backend should be scored for:

- text coverage
- numeric/date accuracy
- title/vendor/person detection
- route correctness
- action-item extraction
- runtime
- whether the output is good enough without cloud

The default local ladder should be selected from measured results on this laptop, not from assumptions about NPU, GPU, or local vision quality.

## Demo Workflow

1. User opens `/brain/inbox`.
2. User adds Desktop using the existing Desktop preset.
3. User drops mixed demo files onto Desktop.
4. User clicks **Consume**.
5. Augur scans stable files only.
6. Each file runs through the capability ladder.
7. Augur classifies destination and normalized filename.
8. Augur writes a source card and extracted/transcribed content.
9. Augur moves or copies the source file according to the workflow's safety policy.
10. Augur indexes the generated source material into RAG.
11. `/brain/inbox` shows per-file results.
12. `/brain/insights` shows summaries, imported meeting actions, review-needed items, and index/wiki state.

The first implementation should use manual Consume. Background watching can be added after the manual workflow is reliable.

## Data Contracts

### Consume Run Record

```json
{
  "id": "run_20260507_001",
  "folder_id": "desktop",
  "started_at": "2026-05-07T12:00:00+00:00",
  "completed_at": "2026-05-07T12:02:00+00:00",
  "status": "partial_success",
  "airplane_mode": true,
  "files_seen": 5,
  "files_moved": 3,
  "files_indexed": 4,
  "files_skipped": 1,
  "files_failed": 0,
  "files_needing_review": 1,
  "cloud_calls": 0,
  "local_agent_calls": 1,
  "wiki_update_marked": true
}
```

### File Result

```json
{
  "source_path": "C:/Users/example/Desktop/scan.pdf",
  "final_path": "C:/Users/example/Projects/Au-vault/finance/2026-05-07-bank-statement-april.pdf",
  "source_card_path": "C:/Users/example/Projects/Au-vault/sources/files/2026-05-07-bank-statement-april.md",
  "content_type": "pdf",
  "document_kind": "bank_statement",
  "extraction_method": "openvino-ocr",
  "hardware_backend": "NPU",
  "local_agent_used": false,
  "cloud_used": false,
  "confidence": "high",
  "route": "finance",
  "route_reason": "Detected bank statement title, date, and account summary.",
  "renamed_to": "2026-05-07-bank-statement-april.pdf",
  "rag_indexed": true,
  "status": "success"
}
```

### Source Card

Source cards are user-facing vault Markdown and must start with YAML frontmatter. They should include:

- title
- source type
- original path
- final path
- extracted/transcript path
- content hash
- extraction method
- hardware backend
- confidence
- route
- tags
- summary
- action items
- escalation or review reason when present

## Safety Rules

- Never permanently delete files.
- Skip active downloads, temp files, directories, and recently modified files.
- Do not move files when extraction fails completely.
- Move ambiguous files to a review folder or keep them in place with `needs_review`.
- Keep original binary files linked to generated Markdown.
- Record all moves, renames, skips, local agent calls, cloud calls, and index results.
- A failed file does not fail the whole consume run.
- RAG indexing failure does not roll back file movement; it marks the run partial and exposes retry.
- Wiki compounding failure does not roll back file organization or RAG indexing.

## MCP Surface

Implement or harden these MCP tools:

- `inbox-folders`: list, add, update, pause, remove inbox folders
- `inbox-scan-folder`: scan preview and counts
- `inbox-consume-folder`: run the full consume workflow
- `inbox-run-history`: list recent runs
- `inbox-run-detail`: inspect one run and its file results
- `brain-insights`: summarize recent imports, meeting actions, review-needed files, RAG/wiki state
- `get-extraction-status`: include OCR, transcription, Ollama, OpenVINO, NPU/GPU/CPU, and airplane/cloud policy status

Dashboard code must call these through the existing MCP client path and `POST /api/mcp/tool`; it must not directly run local scripts or file operations.

## Dashboard Experience

### `/brain/inbox`

The page should show:

- Desktop and Downloads presets
- configured inbox folders
- scan counts
- primary Consume action
- per-run status
- file-level result list
- review-needed files
- backend evidence such as `local OCR`, `OpenVINO`, `Ollama local agent`, `cloud skipped: airplane mode`

### `/brain/insights`

The page should show:

- latest consume run summary
- meeting summary and action items
- imported file summaries
- review-needed items
- RAG indexing status
- pending wiki compounding state
- main action to reindex or run wiki update when appropriate

UI must not claim full success when files failed, were skipped, or need review.

## Testing And Acceptance

### Backend Acceptance

- `get-extraction-status` accurately reports local parsing, OCR, transcription, Ollama, OpenVINO, and policy state.
- Text PDF extracts without OCR.
- Scanned/photo PDF uses local OCR first.
- Low-confidence OCR can call local Ollama vision.
- In airplane mode, no cloud call happens.
- MP3 meeting creates transcript plus source card.
- Every consumed file has a file result and source card or explicit skip/review record.
- RAG index updates after consume.
- Failed or low-confidence items are visible review items.

### Dashboard Acceptance

- `/brain/inbox` can add Desktop, show counts, run Consume, and show run status.
- `/brain/insights` shows imported meeting summary, file mapping results, action items, and indexing state.
- Browser verification proves affected pages load to interactive state.
- Visual review checks alignment, spacing, hierarchy, mobile behavior, button consistency, and text overflow.

### Demo Acceptance

- User can drop a small mixed batch on Desktop.
- One click processes local-first.
- Files are moved or routed into meaningful destinations.
- Generated source cards are searchable through RAG.
- Airplane mode visibly prevents cloud use while still allowing local Ollama escalation.

## Implementation Phases

1. **Capability inventory and policy**
   - Harden `get-extraction-status`.
   - Detect OpenVINO/NPU/GPU/CPU, Ollama vision models, transcription dependencies, and airplane mode.

2. **Local extraction and transcription**
   - Add missing local OCR and PDF rendering pieces.
   - Add local Whisper/OpenVINO transcript path.
   - Calibrate local backends on the demo pack.

3. **Inbox backend**
   - Implement folder registry, scan, consume, run records, file results, source cards, and RAG indexing.

4. **Dashboard payoff**
   - Wire `/brain/inbox` and `/brain/insights` to real MCP data.
   - Show per-file backend evidence and review-needed items.

5. **Verification and demo pack**
   - Add backend tests, dashboard tests, browser verification, and a small local demo fixture set.

## References

- Intel Core Ultra 7 255U product specification: <https://www.intel.com/content/www/us/en/products/sku/241860/intel-core-ultra-7-processor-255u-12m-cache-up-to-5-20-ghz/specifications.html>
- OpenVINO NPU device documentation: <https://docs.openvino.ai/2025/openvino-workflow/running-inference/inference-devices-and-modes/npu-device.html>
- OpenVINO GenAI on NPU documentation: <https://docs.openvino.ai/2025/openvino-workflow-generative/inference-with-genai/inference-with-genai-on-npu.html>
- Windows ML supported execution providers: <https://learn.microsoft.com/windows/ai/new-windows-ml/supported-execution-providers>
