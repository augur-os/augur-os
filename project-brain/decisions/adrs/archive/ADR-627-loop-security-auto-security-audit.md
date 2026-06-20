---
status: Implemented
date: '2026-05-10'
deciders:
- Gur Sannikov
related:
- ADR-566
hub: null
tags: []
superseded_by: null
---

# ADR-627: Loop Security (Auto Security Audit)

## Decision summary

Introduce a `loop-security` skill exposing a single `auto-security-audit` scan-fix command that scans every discovered skill (core, private, external) using a 5-stage offline pipeline. Pipeline stages: **S1** prompt injection (regex patterns derived from ClawGuard/Tank heuristics), **S2** secret...
