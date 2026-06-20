---
status: Implemented
date: '2026-05-10'
deciders:
- gsannikov
related: []
hub: command
tags:
- dashboard
- onboarding
- sidebar
- mcp
- vault
- setup
superseded_by: null
spec_file: 2026-05-10-setup-completeness-widget-design.md
plan_file: 2026-05-10-setup-completeness-widget.md
---

# ADR-722: Setup Completeness Widget

## Decision summary

Ship a sidebar Setup widget that auto-detects 11 setup milestones across three phases (Foundation, Knowledge, Personalization) via existing MCP tools plus small additive tooling, rendering progressive-disclosure states (full card → compact bar → chip → alert) so the system stays motivating for new...

## Status notes

Accepted on 2026-05-10. Brainstormed via `superpowers:brainstorming`, design committed at `234999c81`, plan committed at `71ac221ca`. Status flips to Implemented when the four checkpoints (C1 prerequisites, C2 backend, C3 sidebar UI, C4 settings deep-dive) are merged with all auto-loops green and a real-browser screenshot pass on the four widget states (rule 28). Test gap audit (2026-05-13): rewrote test_foundation/personalization/state with importlib spec convention (27 behavior tests), added test_knowledge (9 tests), converted setup_aggregator/registry/mcp_tools to importlib (19 tests), removed redundant importability stubs. Dashboard widget verified in real browser at localhost:3000 — bar state at 64% renders, click opens flyout via portal with 3 phases + 7/11 fraction, no console errors. ItemRow.test.tsx covers all action/skip paths.
