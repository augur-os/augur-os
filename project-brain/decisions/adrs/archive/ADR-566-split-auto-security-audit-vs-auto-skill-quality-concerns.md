---
status: Implemented
date: '2026-04-28'
deciders:
- gsannikov
related:
- ADR-200
hub: null
tags:
- security
- adaptive-loops
- signal-quality
superseded_by: null
---

# ADR-566: Split auto-security-audit vs auto-skill-quality concerns

## Decision summary

Move skill housekeeping checks out of `auto-security-audit` and into `auto-skill-quality` (or `auto-skill-md` / a new `auto-skill-metadata` category as appropriate).

## Status notes

 | Flipped to Implemented 2026-05-10 per pass-2 code-evidence triage.
