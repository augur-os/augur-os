---
status: Implemented
date: '2026-05-10'
deciders:
- Gur Sannikov
related:
- ADR-575
hub: null
tags: []
superseded_by: null
---

# ADR-622: Augur App Page Staging Cleanup

## Decision summary

Apply **dependency-aware page staging**: page surfaces and skill backends are separate decisions. Move only the page when the backend is still needed by active runtime; move both only when neither is required in the current stage. Verify backend dependency before moving any skill folder using MCP...

## Status notes

 | Flipped to Implemented per code-evidence triage 2026-05-10 — work already shipped.
