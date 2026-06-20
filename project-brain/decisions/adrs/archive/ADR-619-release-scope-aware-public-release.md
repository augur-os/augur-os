---
status: Implemented
date: '2026-05-10'
deciders:
- Gur Sannikov
related:
- ADR-557
hub: null
tags: []
superseded_by: null
---

# ADR-619: Release-Scope-Aware Public Release

## Decision summary

Introduce a canonical machine-readable release scope at `config/system/release_scope.yaml`, initialized to `scope: docs_only` and switchable to `scope: mvp` later. Make `/release` (and `scripts/release.sh`) read that state file, print the detected scope in preflight, and dispatch to a...

## Status notes

 | Flipped to Implemented per code-evidence triage 2026-05-10 — work already shipped.
