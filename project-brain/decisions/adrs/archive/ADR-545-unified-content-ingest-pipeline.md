---
status: Implemented
date: 2026-04-11
deciders:
  - gsannikov
related:
  - ADR-532
  - ADR-539
  - ADR-518
hub: brain
tags:
  - ingest
  - pipeline
  - rag
  - pdf
  - drop-zone
superseded_by: null
---

# ADR-545: Unified Content Ingest Pipeline

## Context

Augur had no single entry point for bringing external content into the vault. PDF extraction, URL scraping, Notion import, and GitHub skill install were separate skills with no shared pipeline, no unified CLI, and no RAG indexing on ingest. Users had to know which skill handled which content type. There was no drop zone UI on the dashboard. The document extractor (ADR-518) existed but was disconnected from the broader vault routing flow.

## Decision

New `skills/ingest/` skill implementing a unified 8-stage pipeline:

```
Stage → Detect → Extract → Classify → Rename → Summarize → Route → Index
```

**Three trigger sources, same pipeline:**

| Trigger | Entry point |
|---------|-------------|
| CLI | `/ingest file.pdf https://url.com` |
| Dashboard | Drop zone + FAB (dispatches via `useActionRunner({dispatch:'ide'})`) |
| Nightly daemon | Scans tracked folders for changes via `scan-state.yaml` |

**7 MCP tools** (stateless, atomic):

| Tool | Type | Purpose |
|------|------|---------|
| `ingest-process` | mutation | High-level: extract → rename → route → index for a batch of items |
| `ingest-extract` | mutation | Format-specific content extraction to markdown |
| `ingest-rename` | mutation | Normalize filename to `YYYY-MM-DD-slug.ext` |
| `ingest-route` | mutation | Move to classified vault location |
| `ingest-status` | read | Current job queue state |
| `ingest-history` | read | Past ingest records |
| `ingest-config` | read/write | Classification/extraction/naming settings |

The agent (LLM) handles classification and summarization; `ingest-process` handles mechanical extraction, renaming, routing, and indexing.

**PDF extraction strategy:** opendataloader-pdf as an optional external dependency (pip-installable, not bundled). When present, it provides bounding-box RAG citations, 0.907 accuracy, reading-order analysis (XY-Cut++), and LaTeX extraction. MarkItDown handles all other formats (DOCX, PPTX, XLSX, images) and serves as PDF fallback when opendataloader-pdf is absent.

**Classification** is configurable: `heuristic` (default), `ollama` (local LLM), or `ide` (agent-dispatched). All fall back to heuristic if unavailable.

**Job queue:** filesystem-based in `{runtime}/ingest/jobs/` as YAML records. Failed jobs are retryable from the stage they failed at.

**Drop zone UI:** full-page drag overlay on the browse page with a FAB button (bottom-right) that opens a modal with File / URL / Text / Folder input tabs and shows a live processing queue panel.

## Consequences

### Positive

- Single `/ingest` command handles any content type — users don't choose the handler
- RAG indexed immediately after routing — content is searchable as soon as ingested
- Nightly tracked folder scan automates continuous ingestion without user action
- opendataloader-pdf gives best-in-class PDF accuracy when installed; absence doesn't break flow
- Phase 2 (LLM wiki maintenance) can hook into the same pipeline post-route

### Negative

- opendataloader-pdf requires user to pip-install a Java-backed tool for premium PDF quality
- Classification accuracy depends on chosen method — heuristic misclassifies edge cases
- Browser uploads require a staging API route (`POST /api/ingest/upload`) outside the pure MCP pattern

### Neutral

- Existing skill import paths (GitHub repos, Notion, YouTube) are unchanged — ingest delegates to them
- All execution remains inside AI client sessions per the execution model; no daemon-owned threads
- 41 tests cover the pipeline stages and job queue

## Alternatives Considered

### Alternative 1: Extend each existing skill independently

Add drag-and-drop to the scraper skill, add CLI flags to document-extractor, etc. Rejected: no shared classification or job queue, users still need to know which skill to use, no unified RAG indexing trigger.

### Alternative 2: Bundle opendataloader-pdf into Augur

Ship it as a required dependency. Rejected: it requires a Java runtime (or large binary) making Augur's install significantly heavier. Optional external dependency gives the quality when the user wants it without penalizing everyone.

### Alternative 3: Daemon-owned async job processor

Background thread processes jobs without an AI session. Rejected: violates the AI client execution model (ADR reference: `docs/references/ai-client-execution-model.md`). The agent is the orchestrator; atomic MCP tools are the hands.

## References

- Source spec: `docs/superpowers/specs/2026-04-11-ingest-pipeline-design.md`
- ADR-532: Query Compounding and Content Index
- ADR-539: RAG Three-Tier Simplification
- ADR-518: Document Extractor (universal doc-to-Markdown)
- Phase 2 ADR: ADR-546 (LLM Wiki Maintenance)

## Implementation Prompt

> Already implemented. 41 tests, merged to main.

**Team name**: `adr-545-ingest-pipeline`

### Completion Criteria

- [x] All phases executed
- [x] 41 tests pass
- [x] Drop zone and FAB components mounted to dashboard
- [x] opendataloader-pdf optional detection implemented
- [x] Nightly scan-state mechanism wired to daemon config
- [x] ADR status updated to Implemented
