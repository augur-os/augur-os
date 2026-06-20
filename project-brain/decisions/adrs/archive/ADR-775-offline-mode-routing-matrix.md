---
status: Implemented
date: 2026-05-22
deciders:
  - gsannikov
related: [ADR-640]
hub: null
tags: [offline, routing, extraction, ocr, transcription, ollama, openvino, gemini, airplane]
superseded_by: null
spec_file: 2026-05-22-offline-mode-routing-simplification-design.md
plan_file: 2026-05-22-offline-mode-routing-simplification.md
---

# ADR-775: Offline-Mode Routing Matrix

> **ADR-775 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Offline-mode engine selection is governed by a single declarative `(activity × mode × OS) → engine` routing matrix in `src/lib/routing/`, replacing the scattered OCR escalation ladder and the Ollama agent/model smoke-probe layer; regular-mode transcript falls back to local Whisper when Gemini is absent (D1) and the Hebrew OCR special-case is dropped (D2).

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-22-offline-mode-routing-simplification-design.md`](../superpowers/specs/2026-05-22-offline-mode-routing-simplification-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-22-offline-mode-routing-simplification.md`](../superpowers/plans/2026-05-22-offline-mode-routing-simplification.md)

## Status notes

Implemented 2026-05-22. The three activities (chat, OCR, transcript) each resolve their engine from one place: regular mode routes to the agent (active AI client / passive-agent vision; Gemini passive-agent for audio), offline mode routes to local engines (Ollama GLM-OCR for OCR on both OSes; Ollama-backed `ollama launch` for chat; OpenVINO Whisper for transcript on Windows/Linux, faster-whisper on macOS). Tasks 1–8 of the plan landed on branch `offline-routing-simplification` with unit/integration tests green (150 passing) and a net reduction of ~330 lines of production logic. Task 9 closed in merge commit `5176be995` (`Merge offline-routing-simplification into main`), whose message records Windows real-data verification for GLM-OCR, OpenVINO GPU transcript, Gemini transcript, and offline chat, plus the merge to `main`.

## Related

- ADR-640: OpenVINO and Ollama Offline Mode (archived) — **partially superseded**. The offline capability and the engine choices (GLM-OCR, OpenVINO/faster-whisper, Ollama-backed agent chat) are retained; what is removed is the multi-tier OCR escalation ladder and the agent/model smoke-turn probe machinery, both replaced by the declarative matrix plus lightweight per-engine availability checks.

## Impact Manifest

```yaml
paths_renamed: []
apis_changed:
  - "new src/lib/routing public API: engine_id_for / detect_mode / resolve_mode / run_ocr / transcribe / resolve_chat"
  - "get-airplane-launch-overrides MCP tool: granular probe `reason` values collapsed to `ollama_not_ready` + actionable `setup_hint`"
  - "get-local-backend-status MCP tool: additive `routing` section mapping (activity, mode) -> {engine, available}"
  - "extractor.extract(): OCR and audio now routed via src.lib.routing; allow_cloud=False forces local offline OCR"
  - "TranscriptResult: added `note` field to carry the D1 local-fallback notice"
patterns_deprecated:
  - "tiered OCR escalation ladder in extractor._request_llm_ocr"
  - "agent/model smoke-turn probe layer in local_backends.py (~900 -> ~695 lines)"
  - "Hebrew OCR offline->cloud special-case (D2)"
files_affected:
  - "src/lib/routing/__init__.py"
  - "src/lib/routing/matrix.py"
  - "src/lib/routing/engines.py"
  - "src/lib/routing/resolver.py"
  - "src/lib/extraction/extractor.py"
  - "src/lib/extraction/transcription.py"
  - "src/lib/extraction/audio_extractor.py"
  - "src/mcp/augur_framework/tools/infrastructure/local_backends.py"
  - "docs/adrs/ADR-775-offline-mode-routing-matrix.md"
  - "docs/superpowers/specs/2026-05-22-offline-mode-routing-simplification-design.md"
  - "docs/superpowers/plans/2026-05-22-offline-mode-routing-simplification.md"
```
