---
status: Implemented
date: '2026-05-10'
deciders:
- Gur Sannikov
related:
- ADR-592
hub: null
tags: []
superseded_by: null
---

# ADR-612: Brain Hub IA Refresh

## Decision summary

Move provider configuration to Settings: `/settings/providers` becomes the canonical provider page; `/brain/ai/providers` is retired (no compatibility alias). Settings owns settings navigation: remove the `Integrations` tab that points to Browse; add a first-class `Providers` tab. Reframe...

## Status notes

 | Flipped to Implemented per code-evidence triage 2026-05-10 — work already shipped.
