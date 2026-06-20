---
status: Implemented
date: '2026-05-10'
deciders:
- Gur Sannikov
related:
- ADR-576
- ADR-584
hub: null
tags: []
superseded_by: null
spec_file: 2026-05-03-windows-one-click-onboarding-design.md
plan_file: 2026-05-03-windows-one-click-onboarding.md
---

# ADR-634: Windows One-Click Onboarding

## Decision summary

Use a staged agent bootstrap: a short versioned `augur.run` prompt launches a rerunnable PowerShell bootstrapper, which hands off to Codex from the cloned repo root, which runs a repo-owned setup orchestrator. The bootstrapper installs Git, Python 3.11+, Node.js 20+, `uv`, and Codex CLI through...

## Status notes

 | Flipped to Implemented per code-evidence triage 2026-05-10 — work already shipped.
