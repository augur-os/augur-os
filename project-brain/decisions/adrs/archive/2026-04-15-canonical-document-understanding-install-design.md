# Canonical Document Understanding And Install Contract Design

**Date:** 2026-04-15
**Status:** Draft
**Scope:** Unify binary document extraction for ambient import and RAG, guarantee the cross-platform dependency contract on fresh machines, and define the first structured document-understanding layer that wiki compilation can trust

## Summary

Augur currently has the pieces needed for richer imported-document understanding, but they are split across multiple code paths and inconsistent install contracts.

Today there are three different extraction stories in the repo:

- `skills/document-extractor/scripts/extractor.py`
  - active in the live ambient-import path through `skills/rag/scripts/unified_indexer.py`
  - uses MarkItDown first, with Tesseract/LLM-style OCR fallback
- `skills/rag/scripts/ocr_extractor.py`
  - richer PDF-aware routing with `pymupdf`, OCR routing, and cache support
  - not the active path for the current ambient wiki import flow
- `skills/ingest/scripts/pipeline.py`
  - older/manual ingest path with an `opendataloader` branch for PDFs
  - not the active path for the current ambient wiki import flow

This makes fresh-machine behavior unreliable. A new machine may have the base extractor but miss the richer PDF path, may have optional OCR dependencies absent, and on Windows may not even install Python dependencies through the same mechanism as the Unix installer.

This spec defines the fix:

1. **One canonical document-understanding path** for file-backed document import and RAG indexing
2. **One install contract** that guarantees the baseline extraction stack on new macOS and Windows machines
3. **One status/verification surface** that onboarding can call to confirm document capability
4. **Structured document understanding metadata** persisted on RAG entries so wiki compilation can write from real document substance instead of thin excerpts

The immediate user-visible outcome should be:

- a fresh machine behaves predictably for imported PDFs and other binary docs
- the ambient import path uses the same trusted extractor every time
- the wiki compiler can write better pages from imported documents without rediscovering their structure from scratch on every run

## Problem

### Current behavioral mismatch

The live ambient import path currently looks like this:

1. detect file
2. `index_documents(...)` in `skills/rag/scripts/unified_indexer.py`
3. `_extract_document(...)`
4. delegate to `skills/document-extractor/scripts/extractor.py`
5. write a RAG entry body
6. compile wiki pages from thin source-body handling

This is already enough for basic extraction, but it is not enough for richer document understanding. The wiki compiler mostly sees a raw body string and still produces shallow topic/source-summary pages.

### Install mismatch

The install story is also split:

- Unix installer: `scripts/install.sh`
  - runs `uv sync`
  - installs some OCR system dependencies on macOS/Linux
- Windows installer: `scripts/install.ps1`
  - creates a venv
  - installs from `requirements.txt`
  - but the repo currently does not ship `requirements.txt`
  - treats OCR dependencies as optional/manual guidance

At the Python dependency level:

- `markitdown[all]` and `markitdown-ocr` are in base dependencies
- `pymupdf` and `mlx-vlm` are in optional extras

That means the richer PDF path is not actually guaranteed on a fresh machine, even though it already exists in the codebase.

### Why this matters

The user experience is inconsistent in exactly the place that should feel magical:

- import a PDF
- let Augur understand it
- compile it into meaningful wiki pages

Instead, current behavior depends on which extractor path is active, which optional packages happened to be installed, and which platform the user is on.

## Design Principles

1. **One canonical extraction path**
   Ambient import, RAG indexing, and wiki compilation should build on the same document-understanding entry point.

2. **Cross-platform baseline first**
   The default install should guarantee a solid text-document/PDF path on macOS and Windows before optional advanced OCR paths are layered on.

3. **Advanced vision is enhancement, not the baseline**
   Apple-only or heavier OCR/vision stacks should stay optional. The core import experience must not depend on them.

4. **Document understanding is broader than PDF**
   PDF is the first pain point and the first implementation priority, but the architecture should apply to other binary/visual docs as well.

5. **Reuse existing status surfaces**
   Onboarding should verify document capability through the existing `document-extractor` status surface instead of inventing a parallel checker.

6. **Persist understanding once**
   RAG entries should store structured document understanding so the wiki compiler can reuse it instead of rediscovering the document every time.

## Scope

### In scope

- File-backed document understanding used by:
  - `documents`
  - ambient import
  - RAG document indexing
  - wiki compilation from imported docs
- Cross-platform install guarantees for the baseline extraction stack
- Onboarding/install verification for document capability
- Structured metadata persisted onto RAG entries for imported documents

### Out of scope

- Email or other connector-backed import
- Full page-by-page multimodal vision summarization for every binary format
- Making Apple-specific OCR/vision mandatory everywhere
- General wiki quality improvements unrelated to document import

## Canonical Runtime Path

### New canonical entry point

Introduce a single canonical document-understanding router in `skills/rag/scripts/document_understanding.py`.

This router becomes the only extraction/understanding path that the ambient import + RAG document flow calls directly.

In the first slice, it should support:

- **Plain text / markdown / structured text**
  - direct read or MarkItDown-backed extraction
- **Office / HTML / rich document formats**
  - document-extractor / MarkItDown path
- **Text-layer PDF**
  - `pymupdf` first
  - fallback to document-extractor when needed
- **Scanned PDF / images**
  - document-extractor OCR path
  - optional advanced vision/OCR path when available

### Canonical return shape

The router should return a normalized result object with:

- `body`
- `title`
- `format`
- `extraction_method`
- `ocr_applied`
- `document_kind`
- `section_hints`
- `summary`
- `key_insights`
- `visual_structure_used`
- `understanding_version`
- `error`

Not every format needs every field in v1, but the contract should exist now.

### Why a new router instead of direct `ocr_extractor.py`

`ocr_extractor.py` already contains valuable logic, especially for `pymupdf` and OCR routing, but it is framed as a low-level OCR helper rather than as the canonical application-facing understanding contract.

The new router should be free to reuse `ocr_extractor.py` internally while presenting one stable, richer result shape to RAG and wiki code.

## Format Strategy

### Baseline formats

The canonical path should support these as baseline on fresh machines:

- `.pdf`
- `.doc`, `.docx`
- `.ppt`, `.pptx`
- `.xls`, `.xlsx`
- `.html`, `.htm`
- `.md`, `.markdown`, `.txt`, `.rst`
- `.csv`, `.tsv`, `.json`, `.yaml`, `.yml`, `.xml`
- `.png`, `.jpg`, `.jpeg`, `.gif` through image/scanned-doc handling where possible

### Priority order

1. **PDF**
   Highest priority because current user pain is here and visual structure matters most
2. **Office formats**
   Important because they are common imported docs and should follow the same route
3. **Images/screenshots**
   Important for later multimodal compounding

### PDF-specific first-slice behavior

For PDF, v1 of the understanding layer should capture:

- real title if inferable
- whether the document is text PDF vs scanned PDF
- cover/title-page clues
- contents / chapter structure when available
- summary
- key insights
- section hints

This is enough to make imported PDF wiki pages meaningfully better without requiring full page-by-page deep vision on every document.

## Dependency Contract

### Baseline Python dependencies

The default install should guarantee:

- `markitdown[all]`
- `markitdown-ocr`
- `pymupdf`

These should be treated as part of the baseline document capability, not optional extras.

### Optional enhancement dependencies

Keep optional:

- `mlx-vlm`

Reason:

- it is not the right cross-platform baseline
- it is heavier
- it is especially Apple-oriented
- baseline imported-document understanding must work without it

### System dependencies

System OCR dependencies remain useful and should still be installed or recommended:

- `tesseract`
- `poppler`
- `ghostscript`
- related PDF/OCR helpers

But the product promise should be:

- **baseline text PDF and rich document extraction works after install**
- **scanned/OCR-heavy import improves when system OCR is present**

## Installer And Onboarding Contract

### Unix installer

`scripts/install.sh` is already closer to the correct path because it uses `uv sync`. It should continue to install system OCR dependencies where possible and should verify document capability after dependency installation.

### Windows installer

`scripts/install.ps1` currently drifts from the repo dependency contract because it installs from `requirements.txt`, which the repo does not ship. This must be corrected.

Windows should align with the same source of truth as Unix:

- install the repo-defined Python dependencies from `pyproject.toml`/lock via `uv`
- verify baseline document capability after install
- keep system OCR tools optional but clearly surfaced

### Onboarding verification

Onboarding should call the existing `document-extractor` status tool (`get-extraction-status`) and extend it as needed so it reports the baseline capability contract clearly.

The install/onboarding verification result should explicitly surface:

- `document parsing`
- `text pdf extraction`
- `scanned/image OCR`
- `advanced vision enhancement`
- platform-specific notes

The user should be able to see, on a fresh machine, what will work now and what is optional.

## RAG Persistence Contract

RAG document entries should continue to store the extracted body, but they should also persist the structured understanding output.

### Required new metadata

- `document_title`
- `document_kind`
- `document_summary`
- `document_key_insights`
- `document_sections`
- `document_extraction_method`
- `document_visual_structure_used`
- `document_understanding_version`

This should live on the existing RAG entry files. No second registry is needed.

### Why this matters

This lets the wiki compiler do better work without reopening the binary file or rerunning full understanding each time.

## Wiki Compilation Contract

The wiki compiler should prefer structured document understanding over:

- raw file path names
- a single first non-empty line excerpt
- shallow body scanning

For imported documents, source-summary and topic pages should build from:

- `document_summary`
- `document_key_insights`
- `document_sections`
- `document_title`

This is the minimal contract needed to stop imported documents from landing as thin generic wiki pages.

## User Experience On A New Machine

### Desired macOS behavior

After a standard install:

- imported text PDFs work
- imported office docs work
- many scanned/image docs work when OCR system tools are present
- advanced Apple-native vision enhancement is optional

### Desired Windows behavior

After a standard install:

- imported text PDFs work
- imported office docs work
- imported scanned/image docs can improve when OCR system tools are installed
- the install/onboarding flow reports clearly whether OCR enhancement is available

### Non-goal

Do not promise identical OCR richness on every platform in v1. Promise a reliable baseline and an explicit capability report.

## Migration Strategy

1. Add the canonical router
2. Switch `unified_indexer._extract_document()` to use it
3. Keep existing lower-level helpers as internal implementation details during transition
4. Remove ambient-import dependence on the legacy `opendataloader` branch as part of the canonicalization work
5. Align Windows install with the same Python dependency source as Unix
6. Update onboarding to verify real document capability
7. Update wiki compilation to use persisted document understanding fields

## Risks

### Risk: too much platform-specific complexity in one slice

Mitigation:
- make `pymupdf` baseline
- keep `mlx-vlm` optional
- use capability reporting instead of pretending everything is identical everywhere

### Risk: another parallel path survives

Mitigation:
- define one canonical document-understanding entry point
- make ambient import and RAG call it directly

### Risk: richer metadata exists but compiler ignores it

Mitigation:
- explicitly wire source-summary and topic compilation to use the new document fields

## Recommendation

Implement this in two linked slices:

### Slice 1: Canonical extraction and install contract

- canonical document-understanding router
- `pymupdf` moved into guaranteed install
- Windows installer aligned with the repo dependency source of truth
- onboarding verification via `get-extraction-status`

### Slice 2: Structured wiki writing from document understanding

- persist document understanding on RAG entries
- make wiki compiler write source/topic pages from those fields

Slice 1 is the prerequisite for making fresh-machine behavior predictable. Slice 2 is the step that turns that reliable extraction into reliably better wiki pages.
