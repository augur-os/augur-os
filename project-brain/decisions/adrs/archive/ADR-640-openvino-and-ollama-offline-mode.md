---
status: Implemented
date: 2026-05-10
deciders:
  - gsannikov
related:
  - ADR-637
hub: null
tags:
  - offline
  - ocr
  - asr
  - openvino
  - ollama
  - cross-platform
  - windows-validated
superseded_by: null
spec_file: 2026-05-09-openvino-ollama-offline-design.md
plan_file: 2026-05-09-openvino-ollama-offline.md
---

# ADR-640: OpenVINO and Ollama Offline Mode

> **ADR-640 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Use one local OCR engine on both Windows and macOS: Ollama GLM-OCR (`model="glm-ocr"`), replacing Tesseract and the hardcoded `llava`. Use one ASR engine per OS: OpenVINO Whisper-large-v3 INT8 on Windows with explicit `["NPU", "GPU", "CPU"]` device probe replacing `device="AUTO"`; the same OpenVINO Whisper on macOS via CPU fallback only (macOS lacks NPU). All configuration flows through `config/system/llm.yaml` profiles (`local_ocr`, `local_asr`) and the existing `llm_retry.resolve_cli()` path so the rest of the codebase does not know which backend served a given call.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-09-openvino-ollama-offline-design.md`](../superpowers/specs/2026-05-09-openvino-ollama-offline-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-09-openvino-ollama-offline.md`](../superpowers/plans/2026-05-09-openvino-ollama-offline.md)

## Status notes

Index ADR reconstructed on 2026-05-12 from the existing spec + plan to align with the new thin-index ADR workflow (the original `/adr write` run that produced this ADR's spec and plan did not generate the markdown index file). No design content was changed in reconstruction.

Implemented 2026-05-12 in Windows session B1 after ADR-733 landed. Live validation installed GLM-OCR, OpenVINO GenAI, and the Whisper-large-v3 INT8 OpenVINO model; AI-client status reports OCR/ASR readiness and schema-validated `local_ocr` / `local_asr` profiles. Sample OCR succeeds through `ollama-glm-ocr`; sample ASR succeeds through the explicit `NPU` → `GPU` → `CPU` probe and selected `GPU` on this machine after `NPU` generation returned a Level Zero driver-not-initialized error.

Security follow-up 2026-05-12: removed the `transformers==4.52.*` / `optimum-intel` conversion stack from the Windows AI PC runtime extra and stopped shipping the legacy `mlx-vlm` OCR extra that transitively pinned `transformers` 4.x through `mlx-lm`. The shipped ASR path consumes the preconverted `OpenVINO/whisper-large-v3-int8-ov` model through `openvino-genai`, and OCR uses Ollama GLM-OCR, so retaining those conversion/legacy packages only reintroduced known `transformers` 4.x dependency alerts.

## Related

- ADR-637 — Local Backends Onboarding
