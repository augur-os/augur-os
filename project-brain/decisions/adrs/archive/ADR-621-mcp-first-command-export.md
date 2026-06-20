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

# ADR-621: MCP-First Command Export

## Decision summary

Adopt **MCP-first, command-opt-in** export: capabilities live behind MCP, not duplicated as client-local skill copies. Stop bulk skill export to normal client surfaces. `_sync_skill_stubs()` becomes cleanup-first: it removes previously generated managed copies via existing manifests while...
