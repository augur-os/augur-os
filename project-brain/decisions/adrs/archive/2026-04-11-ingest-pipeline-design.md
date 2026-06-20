# Ingest Pipeline Design — Phase 1 of LLM Wiki

**Date:** 2026-04-11
**Status:** Draft
**Phase:** 1 of 2 (Phase 2: LLM Wiki Maintenance)
**Inspired by:** [Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

## Summary

A unified content ingest pipeline that accepts any content type — files, folders, URLs, text, YouTube links, GitHub repos, Notion exports, skills — processes it through extraction, classification, renaming, and summarization, then routes it to the correct vault location and indexes it in RAG immediately.

Two entry points feed the same pipeline:
- **Real-time:** Drop zone on the browse page + `/ingest` CLI command
- **Nightly:** Daemon scans tracked folders for changes

This is Phase 1 — it builds the ingest infrastructure. Phase 2 adds continuous LLM-driven wiki page maintenance on top of this pipeline.

## Architecture

### Pipeline Flow

```
Stage → Detect → Extract → Classify → Rename → Summarize → Route → Index
```

1. **Stage** — content arrives (file upload, URL, text) and is stored in staging directory with a job record
2. **Detect** — content type identified by extension, URL pattern, or magic bytes
3. **Extract** — format-specific conversion to markdown (opendataloader-pdf, MarkItDown, scraper, transcription)
4. **Classify** — auto-determine destination in vault (configurable: heuristic, Ollama, IDE dispatch)
5. **Rename** — normalize filename to `YYYY-MM-DD-slug.ext` pattern
6. **Summarize** — for URLs/articles, generate a markdown summary (optional, configurable)
7. **Route** — move processed content to classified vault location
8. **Index** — add to RAG index immediately

### Processing Model

AI client session execution model (see `docs/references/ai-client-execution-model.md`):

All execution happens inside an AI client session. The agent (LLM) is the orchestrator. MCP tools are stateless hands that perform atomic operations. There is no separate executor, no daemon-owned job queue, no background threads.

**Three trigger sources, same result:**

| Trigger | How it starts | What happens inside |
|---------|--------------|---------------------|
| CLI | User types `/ingest file1.pdf file2.pdf` | Agent calls MCP tools, decides parallelism |
| Web (Dashboard) | Drop zone dispatches via `useActionRunner({dispatch:'ide'})` | Same agent, same MCP tools. Dashboard opened the session. |
| Nightly | Daemon triggers scheduled AI client session | Same agent scans tracked folders, calls same MCP tools |

**MCP tools for ingest** (stateless, atomic):

- `ingest-process` — accepts batch of items, processes each through extract/rename/route/index pipeline. Returns results.
- `ingest-status` — reads job records, returns current state
- `ingest-config` — reads/writes ingest configuration

**Agent responsibilities** (intelligence, orchestration):

- Decides parallelism (batch command, parallel tool calls)
- Handles classification — determines vault destination using LLM capability
- Handles summarization — generates markdown summaries for URLs/articles
- Calls `ingest-process` for mechanical work (extraction, renaming, routing, indexing)

### Content Types

| Input | Detection | Extraction Handler |
|-------|-----------|-------------------|
| PDF | `.pdf` extension | opendataloader-pdf (external) with MarkItDown fallback |
| Office docs | `.docx`, `.pptx`, `.xlsx` | MarkItDown |
| Images | `.png`, `.jpg`, `.gif`, `.bmp`, `.tiff`, `.webp`, `.heic` | MarkItDown + OCR (configurable) |
| Markdown | `.md` extension | Direct read |
| URL / article | `http(s)://` pattern | Scraper skill → markdown + auto-summarize |
| YouTube | `youtube.com`, `youtu.be` | Existing `knowledge-summarize-youtube` |
| GitHub repo | `github.com` repo URL | Existing `install-skill` |
| Notion export | `.zip` with Notion structure | Existing `import-notion` |
| Folder | Directory input | Recursive — each file enters pipeline individually |
| Skill package | Contains `SKILL.md` | Existing `install-skill` |
| Raw text | Clipboard / typed input | Save as markdown note |

### PDF Extraction: Hybrid Strategy

opendataloader-pdf is treated as an **external dependency** — not bundled into Augur. The pipeline detects if it's installed and routes PDFs there when available, falling back to MarkItDown if not.

**Why opendataloader-pdf for PDFs:**
- Bounding box preservation for RAG source citations
- 0.907 overall accuracy (#1 benchmarked), 0.928 table accuracy
- Reading order analysis (XY-Cut++ algorithm)
- Prompt injection filtering for AI safety
- LaTeX formula extraction

**Why keep MarkItDown for everything else:**
- Handles 8+ non-PDF formats (DOCX, PPTX, XLSX, HTML, CSV, images)
- Already integrated, pure Python, no Java runtime
- LLM OCR tier already built for images

## Drop Zone UI

### Placement: Full-Page Drop Target + FAB

- Entire browse page is a drag target — no visible drop zone until user starts dragging
- On drag-enter: full-page overlay with dashed border, icon, and accepted types hint
- On drop: overlay closes, items enter the processing queue, FAB badge shows count
- FAB button (bottom-right corner): click opens input modal

### FAB Input Modal (tabs)

| Tab | Input | Behavior |
|-----|-------|----------|
| Files | File picker (multi-select) | Upload via API, each file becomes a job |
| URL | Text input | URL string passed to MCP, scraped + summarized |
| Text | Textarea | Content saved as markdown note in staging |
| Folder | Folder picker | Recursive — each file uploaded individually |

### Processing Queue Panel

Clicking the FAB badge expands a panel showing all active/recent jobs:

- Status icon: pending (circle), processing (spinner), completed (check), failed (x)
- Normalized filename or URL
- Current pipeline stage (extracting, classifying, routing...)
- Destination path (shown after classification)

### Dashboard Components

| Component | Source Location | Purpose |
|-----------|----------------|---------|
| `IngestDropZone` | `skills/ingest/augur/dashboard/IngestDropZone.tsx` | Full-page drag overlay + drop handler |
| `IngestFAB` | `skills/ingest/augur/dashboard/IngestFAB.tsx` | Floating action button + queue panel |
| `IngestModal` | `skills/ingest/augur/dashboard/IngestModal.tsx` | URL/text/file/folder input tabs |
| `IngestQueueItem` | `skills/ingest/augur/dashboard/IngestQueueItem.tsx` | Single item in processing queue |

Components are mounted to `apps/dashboard/features/pages/` at build time via the standard plugin mount system.

Data hooks:
- `useMcpMutation('ingest-process')` — submit content for processing
- `useMcpPoll('ingest-status')` — poll queue state for FAB badge and queue panel

## CLI Ingest

The `/ingest` command calls the same `ingest-process` MCP tool. Same pipeline, same job queue, same processing. The only difference: CLI passes filesystem paths directly (no upload API needed).

```bash
# Files
/ingest path/to/document.pdf
/ingest path/to/folder/

# URLs
/ingest https://arxiv.org/abs/2401.12345
/ingest https://youtube.com/watch?v=...

# Text (stdin)
echo "Meeting notes: discussed Q3 roadmap..." | /ingest --text

# Batch
/ingest file1.pdf file2.docx https://article.com/post

# Explicit destination override
/ingest document.pdf --to vault/finance/reports/
```

## Upload & Staging

### Browser → Server Flow

Files from the browser (drag or picker) upload via `POST /api/ingest/upload` (multipart form data). The API route:

1. Writes file to `{runtime}/ingest/staging/{job-id}/`
2. Calls `ingest-process` MCP tool with the staged path
3. Returns job ID to the client

URLs and text don't need upload — they're passed directly to the MCP tool as string arguments.

### CLI Flow

CLI passes local filesystem paths directly to `ingest-process`. No upload API involved. For folders, the CLI enumerates files and submits each one.

### Staging Directory

```
{runtime}/ingest/
├── staging/          # temporary files awaiting processing
│   ├── {job-id}/     # one dir per job
│   │   └── original-file.pdf
│   └── ...
├── jobs/             # job records (YAML)
│   ├── {job-id}.yaml
│   └── ...
└── scan-state.yaml   # nightly scan mtime tracker
```

Staging files are cleaned up after successful routing to the vault destination.

## Job Queue

Filesystem-based job queue in `{runtime}/ingest/jobs/`.

### Job Record Schema

```yaml
id: "a1b2c3d4"
status: pending          # pending → processing → completed | failed
type: pdf                # pdf, url, text, youtube, github, notion, skill, folder, image, document, markdown
source: "/staging/a1b2c3d4/invoice.pdf"
original_name: "Invoice_2024 (copy).PDF"
stage: null              # current stage: detect | extract | classify | rename | summarize | route | index
classified_to: null      # vault destination, filled after classification
renamed_to: null         # new filename, filled after rename
summary_path: null       # path to summary markdown, filled after summarize
error: null              # error message if failed
created_at: "2026-04-11T10:30:00Z"
updated_at: "2026-04-11T10:30:00Z"
completed_at: null
```

### Job Lifecycle

```
pending → processing (stage cycles through: detect → extract → classify → rename → summarize → route → index) → completed
                                                                                                              → failed (retryable)
```

Failed jobs retain their state and can be retried via `ingest-retry`, resuming from the failed stage.

## MCP Tools

New tools owned by an `ingest` skill. All are stateless, atomic operations — the agent orchestrates the pipeline.

| Tool | Type | Args | Returns |
|------|------|------|---------|
| `ingest-process` | mutation | `{items: [{source, type?, destination?}]}` | `{results: [{source, status, destination, renamed_to, error?}]}` |
| `ingest-extract` | mutation | `{source, type?}` | `{markdown, title, format, metadata}` |
| `ingest-rename` | mutation | `{path, title?}` | `{original, renamed_to}` |
| `ingest-route` | mutation | `{source, destination}` | `{routed_to, indexed}` |
| `ingest-status` | read | `{job_id?}` (omit for all) | `{jobs: [...], queue_size}` |
| `ingest-history` | read | `{limit?, since?}` | `{items: [{source, destination, type, created_at}]}` |
| `ingest-config` | read/write | `{key?, value?}` | Current config or updated config |

`ingest-process` is the high-level tool — it runs extract → rename → route → index for each item in the batch. The agent calls this for mechanical work and handles classification/summarization itself using its LLM. Individual tools (`ingest-extract`, `ingest-rename`, `ingest-route`) are available for granular control when the agent needs it.

## File Naming Convention

Pattern: `{date}-{slug}.{ext}`

- **Date:** ingest date (`YYYY-MM-DD`)
- **Slug:** derived from extracted content title, not original filename. Lowercase, hyphens, no special characters
- **Extension:** binary files keep original extension, text content becomes `.md`
- **Collisions:** append `-2`, `-3` suffix

| Original | Renamed |
|----------|---------|
| `Invoice_2024 (copy).PDF` | `2026-04-11-invoice-2024.pdf` |
| `IMG_20240101_123456.jpg` | `2026-04-11-photo-january.jpg` |
| `résumé final v3 (2).docx` | `2026-04-11-resume-final.docx` |
| URL article about ML | `2026-04-11-machine-learning-transformers.md` |
| Raw text note | `2026-04-11-meeting-notes-q3-roadmap.md` |

## Configuration

Stored in the existing Augur settings infrastructure. Accessible via `ingest-config` MCP tool and dashboard settings.

```yaml
ingest:
  classification:
    method: "heuristic"        # heuristic | ollama | ide
    model: "gemma2:2b"         # for ollama method
    fallback: "heuristic"      # if primary method unavailable
  extraction:
    pdf: "opendataloader-pdf"  # opendataloader-pdf | markitdown
    ocr: "tesseract"           # tesseract | ollama | disabled
  naming:
    pattern: "{date}-{slug}"
    date_format: "YYYY-MM-DD"
  summarize:
    enabled: true              # auto-summarize URLs/articles on ingest
    max_length: 2000           # summary word limit
  tracked_folders:             # for nightly daemon scan
    - "~/Documents"
    - "~/Downloads/papers"
  auto_index: true             # RAG index immediately after routing
```

## Nightly Tracked Folder Scan

The Augur daemon scans tracked folders on a configurable schedule (default: nightly).

**Mechanism:**
- Compare file mtimes against last scan timestamp in `{runtime}/ingest/scan-state.yaml`
- New or modified files enter the same pipeline (extract → classify → rename → route → index)
- Scan results logged to job queue records, queryable via `ingest-history`

**This is the bridge to Phase 2:** the nightly scan detects all changes across tracked folders and vault. Phase 2 will add an LLM wiki update step after indexing — the wiki pages get updated based on what changed since the last scan.

## Skill Structure

New `ingest` skill following the Agent Skills standard:

```
skills/ingest/
├── SKILL.md                    # skill metadata, x-augur-hub: brain
├── commands/
│   └── ingest.md               # /ingest CLI command
├── scripts/
│   ├── pipeline.py             # orchestrator: stage → detect → extract → classify → rename → summarize → route → index
│   ├── detector.py             # content type detection
│   ├── classifier.py           # auto-classification (heuristic + LLM)
│   ├── renamer.py              # filename normalization
│   └── job_queue.py            # filesystem-based job queue
├── augur/
│   ├── dashboard/
│   │   ├── IngestDropZone.tsx
│   │   ├── IngestFAB.tsx
│   │   ├── IngestModal.tsx
│   │   └── IngestQueueItem.tsx
│   └── data/
│       └── config-defaults.yaml
└── assets/
    └── seeds/
        └── classification-rules.yaml  # heuristic classification rules
```

## Dependencies

| Dependency | Type | Required | Purpose |
|------------|------|----------|---------|
| opendataloader-pdf | External (pip) | Optional | PDF extraction with bounding boxes |
| MarkItDown | Existing | Yes | Non-PDF document extraction |
| Scraper skill | Existing | Yes | URL → markdown conversion |
| Knowledge skill | Existing | Yes | Summarization tools |
| Import skill | Existing | Yes | GitHub/Notion/skill import |
| RAG skill | Existing | Yes | Indexing |
| Document extractor | Existing | Yes | OCR fallback |

## Phase 2 Preview

Phase 2 (LLM Wiki Maintenance) will add:
- Continuous wiki page updates after ingest and chat sessions
- Multi-page wiki writes per ingested document (Karpathy's "10-15 pages" pattern)
- Cross-reference and consistency maintenance
- Wiki linting for orphaned pages, stale claims, contradictions
- Chat session hooks that trigger wiki updates from conversation learnings

Phase 2 depends on Phase 1's pipeline being solid — the ingest infrastructure must work reliably before adding LLM-driven wiki maintenance on top.
