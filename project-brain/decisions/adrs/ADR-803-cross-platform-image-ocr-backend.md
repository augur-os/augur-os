---
status: Implemented
date: 2026-06-07
deciders:
  - gsannikov
related: []
hub: null
tags:
  - file-manager
  - ocr
  - ingest
  - cross-platform
superseded_by: null
spec_file: 2026-06-07-image-ocr-backend-design.md
plan_file: null
---

# ADR-803: Cross-Platform Image OCR + EXIF Backend for Desktop Ingest

> **ADR-803 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Add image text (OCR) + EXIF signals to the Desktop ingest classifier via a **pluggable OCR backend** with local per-OS defaults — **Apple Vision** on macOS and **EasyOCR-on-OpenVINO** on Windows/Linux (Hebrew-capable) — with **cloud OCR strictly opt-in** (gated by the extraction policy's `cloud_escalation_allowed`), and **EXIF via Pillow** cross-platform; OCR is an enhancement that degrades gracefully to filename-only when no backend is installed.

## Spec (canonical)

- [`docs/superpowers/specs/2026-06-07-image-ocr-backend-design.md`](../superpowers/specs/2026-06-07-image-ocr-backend-design.md)

## Plan (canonical, drives `/adr implement`)

- Not yet written. Run `/superpowers:writing-plans` against the spec before `/project adr implement ADR-803`.

## Status notes

**Implemented (2026-06-07) — full backend scope built; verified per platform.**
The pluggable `ocr/` package shipped in `file-manager-augur` with all three
adapters real (no stubs) behind one `image_ocr()` interface, plus Pillow EXIF and
the ingest integration (`_extract_content` OCRs images; the scan attaches
`exif_date`). 174 tests pass (1 conditional skip).

Per-backend verification (honest, rule 34):
- **macOS → Apple Vision** (compiles a bundled Swift helper, native Hebrew):
  **real-data verified** — a BBC-article screenshot OCRs to its content and scores
  `reading` 0.46 (was ~0 on filename alone); a generated text image reads back.
- **Windows/Linux → EasyOCR** (Hebrew-capable; the dispatcher key is `openvino`,
  the engine is EasyOCR — chosen over PaddleOCR for Hebrew): **implemented** with
  Reader caching + graceful fallback; logic mock-tested and a conditional
  real-OCR test that runs wherever `easyocr` is installed (skipped here — torch is
  a multi-GB optional dep, `pip install easyocr` / `augur[ocr]`). True OpenVINO
  IR acceleration remains a documented future optimization (`TODO_CLEANUP`).
- **Cloud → Google Cloud Vision** (stdlib REST, `DOCUMENT_TEXT_DETECTION`):
  **implemented**, opt-in only (gated by `allow_cloud` + policy
  `cloud_escalation_allowed`), env key `GOOGLE_CLOUD_VISION_API_KEY`; gating +
  response parsing mock-tested. A real cloud call needs the user's API key (by
  design — privacy-gated).

All backends degrade to filename-only when their dep/credentials are absent, so a
fresh clone behaves as before. The optional dependency extra `augur[ocr]`
(`easyocr`) is declared in `pyproject.toml`.

## Related

- Builds on the `file-manager-augur` Desktop ingest workflow (spec `2026-06-07-desktop-downloads-ingest-workflow-design.md`, closeout `2026-06-07-desktop-downloads-ingest-CLOSEOUT.md`).
- Honors rule 30 (cross-OS: shell-neutral engine + thin per-OS adapters) and the local-first/privacy posture.

## Impact Manifest

> New, additive capability — no path renames, API changes, or pattern deprecations. Files are created under the skill on implementation; none are changed by this decision record.

```yaml
impact:
  paths_renamed: []
  apis_changed: []
  patterns_deprecated: []
  files_affected: []
```
