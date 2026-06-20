---
id: ADR-518
title: Universal Document Extraction with LLM-Assisted MCP Pattern
status: Implemented
date: 2026-03-26
tags: [document-extractor, markitdown, ocr, llm-assisted-mcp, architecture]
related: [ADR-517, ADR-086, ADR-085]
---

# ADR-518: Universal Document Extraction with LLM-Assisted MCP Pattern

## Status

Accepted

## Context

Augur's content extraction is fragmented across multiple format-specific implementations:

- `binary_extractor.py` in RAG skill: handles PDF (pdfplumber), Excel (openpyxl), missing Word/PowerPoint deps
- `file_metadata_extractor.py` in knowledge skill: metadata only, no content
- `scan-folder` in file-manager: plain text sampling only
- Knowledge skill OCR: labeled "beta", Tesseract-based, not production-ready

This fragmentation means:
- New format support requires changes in multiple places
- No OCR for scanned PDFs or images
- File-manager triage can't read 50%+ of Desktop files (PDFs, Office docs, images)
- RAG indexing misses content from formats without dedicated extractors

Meanwhile, Microsoft's MarkItDown library provides unified document-to-Markdown conversion for PDF, DOCX, PPTX, XLSX, images, audio, HTML, and more — with an optional OCR plugin using LLM Vision.

## Decision

### 1. New `document-extractor` skill

A new infrastructure skill in the command hub that wraps MarkItDown and exposes universal document extraction via MCP tools. Replaces `binary_extractor.py` as the single extraction layer.

### 2. LLM-Assisted MCP pattern

Introduces a new architecture pattern (documented in `docs/references/llm-assisted-mcp-pattern.md`) for MCP tools that need LLM intelligence on a subset of inputs:

- **Inside AI client** (Claude Code, Codex, Ollama CLI): Tool returns image/page data to the calling agent. The agent IS the LLM — it processes and calls back with results.
- **Outside AI client** (dashboard, daemon, cron): Tool spawns a configured CLI agent session. That session calls the same tool — now inside an AI client. Same behavior, same interface.

This pattern complies with rule 10 (no direct LLM API calls) while enabling LLM-powered OCR from any context.

### 3. Tiered extraction

| Tier | When | Capability | Cost |
|------|------|-----------|------|
| 0 | Always | Text-based PDF, Office, HTML, text → Markdown | None |
| 1 | AI client available | Above + OCR for images and scanned PDFs via calling agent | Per LLM session |

Tier 0 uses MarkItDown's pure Python parsers — works offline, no LLM, no network. Tier 1 adds LLM Vision for OCR via the LLM-Assisted MCP pattern.

### 4. Replace binary_extractor.py

RAG indexing migrates from `binary_extractor.py` to `extract-document` MCP tool calls. `binary_extractor.py` is deleted. One extraction path, no divergence.

### 5. CLI agent configuration

Users configure their preferred CLI agent for LLM-assisted processing:

```yaml
llm_cli:
  preferred: claude
  fallback: ollama
  ollama_model: llava
  timeout: 120
```

Priority: Claude Code CLI → Ollama CLI with vision model → graceful degradation (tier 0 only).

### 6. Dashboard integration

The skill contributes a page to the integrations/browse tab showing:
- Extraction capabilities (which formats available)
- LLM status (Claude CLI available? Ollama running? Vision model installed?)
- Ollama/LLaVA integration health

## Consequences

- `binary_extractor.py` in RAG skill is deleted — single extraction path via MCP
- `file_metadata_extractor.py` in knowledge skill becomes redundant (extract-document returns richer data)
- `markitdown[all]` and `markitdown-ocr` added as Python dependencies
- File-manager's `scan-folder` gains content extraction for all supported formats
- RAG indexing quality improves (structured Markdown vs. plain text)
- LLM-Assisted MCP pattern is available for future skills that need selective LLM intelligence
- Ollama with vision models becomes a first-class local LLM integration

## Consumers

| Consumer | Current | After |
|----------|---------|-------|
| `scan-folder` (file-manager) | Plain text only | All formats via `extract-document` |
| RAG indexing | `binary_extractor.py` | `extract-document` MCP tool |
| `knowledge-summarize-file` | Delegates to binary_extractor | `extract-document` MCP tool |
| Dashboard file viewer | Metadata only | Full content preview |
