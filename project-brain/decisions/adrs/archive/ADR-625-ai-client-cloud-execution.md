---
status: Implemented
date: '2026-05-10'
deciders:
- Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
---

# ADR-625: AI Client Cloud Execution

## Decision summary

Adopt **Review-First Cloud Execution**: every client defaults to read/review/plan modes; `fix`, `commit`, and `pr` require explicit opt-in. Define a shared **cloud execution profile** schema describing local surfaces, cloud surfaces, generated files, supported modes, default mode, mutation...

## Status notes

 | Flipped to Implemented per code-evidence triage 2026-05-10 — work already shipped.
