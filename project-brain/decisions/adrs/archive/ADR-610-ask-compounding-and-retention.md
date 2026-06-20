---
status: Implemented
date: '2026-05-10'
deciders:
- Gur Sannikov
related:
- ADR-532
hub: null
tags: []
superseded_by: null
---

# ADR-610: Ask Compounding and Retention

## Decision summary

Keep `/ask` as the public command name; upgrade it from a reflective Q&A surface into a structured four-stage compounding pipeline: conversation → classification → retention → session-end compounding. Make retention automatic by default with a high threshold; expose `--retain`, `--no-retain`,...
