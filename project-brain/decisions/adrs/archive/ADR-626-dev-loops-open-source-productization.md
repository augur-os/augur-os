---
status: Implemented
date: '2026-05-10'
deciders:
- Gur Sannikov
related:
- ADR-582
hub: null
tags: []
superseded_by: null
---

# ADR-626: Dev Loops Open-Source Productization

## Decision summary

Treat repo `skills/` plus active vault user skills as the only canonical loop-source for adaptive discovery; generated client exports (`.gemini/skills`, `.opencode/skills`, `.codex/skills`) are consumer surfaces and must not be loaded as loop modules. Adopt a single source of truth for scheduler...

## Status notes

 | Flipped to Implemented per code-evidence triage 2026-05-10 — work already shipped.
