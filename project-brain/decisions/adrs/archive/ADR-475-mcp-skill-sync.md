---
status: Implemented
date: 2026-03-22
deciders:
  - Gur Sannikov
related: []
hub: null
tags:
  - mcp
  - skill-sync
  - cross-client
  - adapters
superseded_by: null
---

# ADR-475: MCP-Based Skill Sync

## Context

Cross-client skill distribution uses a file-copy adapter pattern where each client adapter has a `sync_skill()` method that copies adapted skill files. This causes deduplication confusion (adapted copies look like real skills to scanners), breaks cross-client resource access (copied files lack the original's MCP tool context), and requires 11 separate adapter implementations to maintain.

## Decision

Replace file-copy adapters with MCP-based stub generation:

1. **Adapted-copy detection**: Add `_is_adapted_copy()` helper that detects marker comments (`AUGUR-ADAPTED-COPY`, `AUGUR-STUB`, `AUTO-GENERATED FILE`) to distinguish copies from master originals
2. **Dedup site filters**: Add exclusion filters at 3 dedup sites (skill registry, browse, scorer) to skip adapted copies
3. **Stub generation MCP tool**: New `render-skill-file` tool generates thin discovery stubs per client format -- stubs contain only the skill name, description, and an MCP reference for full content retrieval
4. **Thin sync script**: Replace 11 adapter `sync_skill()` methods with a single sync script that calls `render-skill-file` for each target client
5. **Adapter preservation**: Adapter classes remain for rules/config/memory sync (non-skill concerns)

Stubs use a marker comment (`<!-- AUGUR-STUB -- full content via MCP get-skill -->`) so they are always detectable as non-master copies.

## Consequences

### Positive
- Eliminates deduplication confusion from adapted copies
- Cross-client skill access works through MCP rather than stale file copies
- Reduces 11 `sync_skill()` implementations to 1 thin sync script

### Negative
- Stubs require MCP server running for full skill content access
- Clients without MCP support see only the stub, not the full skill

### Neutral
- Legacy `AUTO-GENERATED FILE` markers are supported for backward compatibility detection
- Adapter classes are preserved for non-skill sync concerns

## Alternatives Considered

### Alternative 1: Improve file-copy adapters with better dedup markers
Add dedup-friendly markers to adapted copies while keeping the file-copy pattern. Rejected because the fundamental issue is that file copies go stale and lack MCP context.

## References
- Plan: `docs/superpowers/plans/2026-03-20-mcp-skill-sync.md`
- Spec: `docs/superpowers/specs/2026-03-20-mcp-skill-sync-design.md`
