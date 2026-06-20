---
status: Implemented
date: '2026-05-10'
deciders:
- Gur Sannikov
related:
- ADR-596
- ADR-597
- ADR-598
- ADR-599
- ADR-568
- ADR-570
hub: null
tags: []
superseded_by: null
spec_file: 2026-04-29-track2-vault-server-split-design.md
plan_file: 2026-04-29-track2-vault-server-split.md
---

# ADR-631: Track 2 Vault Server Split

## Decision summary

**Per-bundle entry point**: a generic launcher `python -m augur_mcp.bundle_server <bundle-name>`. Bundles continue exporting `scripts/mcp/__init__.py:register_tools(mcp, interceptor, metrics)`; the launcher loads one bundle and runs its FastMCP stdio loop. **Transition strategy**: hybrid. PR 1...

## Status notes

 | Flipped to Implemented per code-evidence triage 2026-05-10 — work already shipped.
