---
status: Implemented
date: 2026-03-17
deciders:
  - Gur Sannikov
related:
  - ADR-287
hub: dev
tags:
  - mcp
  - api-wiring
  - dashboard
  - data-quality
superseded_by: null
---

# ADR-428: Missing MCP Tools Implementation

## Context

288 dashboard API routes reference MCP tools that don't exist. When these routes are called, the MCP call fails and `gracefulFallback` silently returns empty data — making pages appear empty with no error. The `auto-api-wiring` autoloop detects these, but the tools need to be implemented.

## Decision

### Triage Strategy (C + seeds)

For each route with a missing `toolName`:

1. **Vault data exists** — implement the MCP tool to serve it
2. **No vault data, seeds exist** — seed the vault first, then implement the tool
3. **No data, no seeds** — collect into report for user review (no deletion)

### Agent Protocol

Each hub agent: inventory missing tools → triage each route → implement tools → report results. Agents only add Python MCP tool implementations + augur.yaml registrations. No dashboard file modifications.

### Rollout

- **Batch 1**: Career hub (~8 tools), Productivity hub (apple, eisenhower, reading-list gaps)
- **Batch 2**: Professional, observability, finance, health, dev, admin, AI, core

### Constraints

- Agents only add Python MCP tool implementations + augur.yaml registrations
- No dashboard component, route, or page modifications
- No file deletions
- All tools follow existing patterns in the skill's MCP module

## Consequences

### Positive

- Pages that show empty data will display real content
- `auto-api-wiring` scan count decreases after each batch
- Fixes the root cause (missing tools) not the symptom (empty pages)

### Negative

- Large scope — 288 routes across all hubs
- Some routes may have no data to serve (report-only)

### Neutral

- No TypeScript or dashboard changes needed

## References

- Design doc: `docs/superpowers/specs/2026-03-17-missing-mcp-tools-implementation-design.md`
- ADR-287: MCP-First Dashboard
