---
title: 'GitHub - opendataloader-project/opendataloader-pdf: PDF Parser for AI-ready
  data. Automate PDF accessibility. Open-source.'
x-augur-note-type: url
canonical_url: https://github.com/opendataloader-project/opendataloader-pdf?tab=contributing-ov-file
content_hash: sha256:e8c3306d7dea51cb5ae058e08290df27829fd0eab79bb8fe2d561f83756555ca
tags:
- pdf
- document-extraction
- ocr
- tool
- open-source
captured_at: '2026-06-08T06:07:01.001459Z'
_source_type: url
_relates_to:
- '[[document-extraction]]'
- '[[ocr]]'
- '[[open-source]]'
- '[[pdf]]'
- '[[tool]]'
_mentions:
- '[[ADR-803]]'
---



# GitHub - opendataloader-project/opendataloader-pdf: PDF Parser for AI-ready data. Automate PDF accessibility. Open-source.

> [!summary]
> OpenDataLoader PDF — open-source (Apache-2.0) PDF parser for AI-ready data:
> extracts Markdown / JSON (with bounding boxes) / HTML from any PDF, #1 in
> extraction benchmarks (0.907 overall, 0.928 tables). Built-in OCR for 80+
> languages (hybrid mode) for scanned PDFs, plus end-to-end PDF accessibility
> auto-tagging (untagged → Tagged PDF / PDF/UA). Python, Node.js, Java SDKs.

## Source

- URL: https://github.com/opendataloader-project/opendataloader-pdf?tab=contributing-ov-file
- Repo: https://github.com/opendataloader-project/opendataloader-pdf · Site: opendataloader.org
- License: Apache-2.0 (core) · SDKs: Python (`opendataloader-pdf`), Node.js (`@opendataloader/pdf`), Java (`org.opendataloader`) · Requires Java 11+
- Captured: 2026-06-08T06:07:01.001459Z
- Note: GitHub renders its README via JS, so the auto-capture fetched a boilerplate stub; this body was enriched from the raw README.

## Body

**OpenDataLoader PDF** turns any PDF into AI-ready structured data, and is also the
first open-source tool to auto-tag PDFs for accessibility end-to-end.

**Data extraction (for RAG/LLM pipelines):**
- Outputs **Markdown**, **JSON with bounding boxes** (source citations), **HTML**, and Tagged PDF.
- **#1 extraction accuracy** in benchmarks — 0.907 overall, 0.928 table accuracy across 200 real-world PDFs (multi-column, scientific papers); ~0.015s/page in deterministic local mode.
- **Built-in OCR, 80+ languages** via *hybrid mode* for scanned/poor-quality PDFs (300 DPI+); handles complex/borderless tables, LaTeX formulas, and AI-generated picture/chart descriptions.
- Deterministic **local mode** + optional AI **hybrid mode** for complex pages; AI safety filters; XY-Cut++ reading order.
- `pip install opendataloader-pdf` → 3-line `convert()` (batch files in one call — each call spawns a JVM). LangChain integration available.

**Accessibility:** layout analysis + auto-tagging (Apache-2.0) converts untagged PDFs to screen-reader-ready Tagged PDFs, built with the PDF Association + Dual Lab (veraPDF) per the Well-Tagged PDF spec; PDF/UA-1/2 export is an enterprise add-on.

**Why kept (relevance to Augur):** a strong candidate to **complement or replace MarkItDown** in the `file-manager-augur` ingest document extraction, and its **built-in multi-language OCR** is directly relevant to [[ADR-803]] (cross-platform image/PDF OCR) — especially Hebrew + scanned documents, where our current Apple Vision / EasyOCR path could be backed or compared against a benchmarked deterministic engine. Worth a proof-of-concept as an extraction/OCR backend.
