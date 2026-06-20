---
status: Implemented
date: 2026-04-15
deciders:
  - Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
---

# ADR-588: Canonical Document Understanding Install

## Context

Augur has three different document-extraction stories scattered across the repo: `skills/document-extractor/scripts/extractor.py` (active in ambient import via `unified_indexer`, MarkItDown-first with Tesseract/LLM fallback), `skills/rag/scripts/ocr_extractor.py` (richer PDF-aware routing with `pymupdf` and OCR cache, but not in the active path), and `skills/ingest/scripts/pipeline.py` (older manual ingest with an `opendataloader` PDF branch). Fresh-machine behavior is unreliable as a result.

The install contract is also split. Unix uses `scripts/install.sh` with `uv sync`; Windows uses `scripts/install.ps1` and installs from a `requirements.txt` that the repo does not actually ship. At the dependency level, `markitdown[all]` and `markitdown-ocr` are baseline but `pymupdf` and `mlx-vlm` are optional extras — so the richer PDF path is not guaranteed on a fresh machine even though the code already exists.

The wiki compiler downstream sees only raw body strings and produces shallow generic pages from imported documents because no structured document understanding is persisted on RAG entries.

## Decision

Adopt a single canonical document-understanding path used by ambient import, RAG indexing, and wiki compilation, plus one install contract that guarantees the baseline extraction stack on macOS and Windows:

1. **Canonical router**: introduce `skills/rag/scripts/document_understanding.py` as the only application-facing extraction/understanding entry point. It returns a normalized shape (`body`, `title`, `format`, `extraction_method`, `ocr_applied`, `document_kind`, `summary`, `key_insights`, `section_hints`, `visual_structure_used`, `understanding_version`, `error`). PDF prefers `pymupdf` first, then falls back to document-extractor; other formats route through document-extractor / MarkItDown.
2. **RAG persistence**: `unified_indexer._extract_document()` delegates to the router and persists structured metadata (`document_title`, `document_kind`, `document_summary`, `document_key_insights`, `document_sections`, `document_extraction_method`, `document_visual_structure_used`, `document_understanding_version`) on RAG entries.
3. **Wiki writes from understanding**: `wiki_compiler` and `wiki_page_writer` prefer the persisted `document_summary` / `document_key_insights` over thin raw excerpts for source-summary and topic pages.
4. **Baseline dependency contract**: move `pymupdf` into baseline `pyproject.toml` dependencies; keep `mlx-vlm` optional under `[project.optional-dependencies] ocr`. Align `scripts/install.ps1` with `uv sync` (no `requirements.txt`). Both installers verify baseline document capability after install.
5. **Status surface**: extend `get_extraction_status_impl()` to report `baseline_document_contract` (`markitdown`, `pymupdf`, `text_pdf_extraction`, `ocr_enhancement`). Onboarding (default and full modes) calls this surface to verify document capability.

## Consequences

### Positive
- One canonical extraction path used everywhere — no path drift between ambient import and RAG
- Fresh macOS and Windows machines have a guaranteed baseline (text PDF, office docs, MarkItDown formats) without optional installs
- Wiki compiler writes meaningfully better imported-document pages from persisted understanding
- Onboarding verification is honest about what works now versus what needs optional OCR system tools

### Negative
- Baseline dependency footprint grows by `pymupdf`
- Windows install no longer matches a non-existent `requirements.txt` flow; users on outdated install scripts must re-run

### Neutral
- `mlx-vlm` and other heavy/Apple-oriented vision stacks remain optional
- System OCR (`tesseract`, `poppler`, `ghostscript`) remains recommended for scanned-doc enhancement, not required for baseline

## Alternatives Considered

### Alternative 1: Make the existing `ocr_extractor.py` the canonical entry point
Rejected because it is framed as a low-level OCR helper, not as the application-facing document-understanding contract; the new router can reuse it internally while presenting a stable richer result shape.

### Alternative 2: Keep `pymupdf` optional and rely on capability reporting alone
Rejected because reliable text PDF extraction is the most common pain and must work on a fresh machine without extras.

### Alternative 3: Per-page deep multimodal vision in v1
Rejected as too heavy and Apple-oriented for the cross-platform baseline; deferred behind optional `ocr` extras.

## References
- Plan: docs/superpowers/plans/2026-04-15-canonical-document-understanding-install.md
- Spec: docs/superpowers/specs/2026-04-15-canonical-document-understanding-install-design.md
