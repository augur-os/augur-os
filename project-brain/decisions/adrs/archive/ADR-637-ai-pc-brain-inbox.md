---
status: Implemented
date: '2026-05-10'
deciders:
- Gur Sannikov
related:
- ADR-564
- ADR-640
hub: null
tags: []
superseded_by: null
spec_file: 2026-05-07-ai-pc-brain-inbox-design.md
plan_file: 2026-05-07-ai-pc-brain-inbox.md
---

# ADR-637: AI PC Brain Inbox

## Decision summary

Build a local-first pipeline with a visible capability ladder: deterministic local parsing → local OCR/transcription → accelerated local backends → local Ollama vision/audio agents → policy-gated cloud escalation → review queue for unresolved low-confidence files. Treat airplane mode as a hard...

## Status notes

 | Flipped to Implemented per code-evidence triage 2026-05-10 — work already shipped.
