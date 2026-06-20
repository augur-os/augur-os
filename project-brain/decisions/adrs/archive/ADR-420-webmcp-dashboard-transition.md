---
status: Implemented
date: 2026-03-14
deciders:
  - Gur Sannikov
related:
  - ADR-287
  - ADR-406
hub: core
tags:
  - webmcp
  - dashboard
  - testing
  - agents
superseded_by: null
---

# ADR-420: WebMCP Dashboard Transition

## Context

Agent testing of the dashboard requires click → screenshot → vision parse, which is slow and fragile. The W3C WebMCP specification (`navigator.modelContext`) enables AI agents to interact with UI through typed tool calls with structured responses including UI state.

## Decision

Convert the Augur dashboard to expose structured tools via WebMCP in 9 phases:

1. **Phase 1: Block Tools** — WebMCPProvider, state registry, useWebMCPReport hook, 4 block tools (discover, read, configure, act), polyfill. Covers all 300+ blocks via BlockRenderer wrapper.
2. **Phase 2: Auto-Pages** — 2 page tools (discover, read)
3. **Phase 3: Views** — 2 view tools (manage, compose)
4. **Phase 4: Navigation** — 2 navigation tools (goto, state)
5. **Phase 5: Actions** — 3 action tools (discover, run, status)
6. **Phase 6: Search/Browse** — 2 catalog tools (search, preview)
7. **Phase 7: Forms/Settings** — 3 form tools (discover, fill, submit)
8. **Phase 8: Custom Pages** — Convention-based opt-in via useWebMCPPage hook
9. **Phase 9: Agent Bubbles** — 3 agent tools (list, read, interact)

### Key Design Decisions

- **Categorical tools (~21 total)** over per-block (300+) — agent tool selection degrades past ~30 tools
- **React context provider** architecture — agents need UI state
- **React Query cache** for mounted blocks, API fallback for unmounted — cache-consistent
- **Polyfill** with full consumer surface for testing without Chrome flag

## Consequences

### Positive

- Agent testing becomes deterministic and fast (no vision parsing)
- All 300+ blocks automatically WebMCP-enabled via BlockRenderer
- Incremental phased rollout — no big-bang migration

### Negative

- Polyfill maintenance until WebMCP spec stabilizes
- BlockRenderer refactor needed to own data-fetching lifecycle

### Neutral

- Existing click-based tests continue working alongside WebMCP tests

## Alternatives Considered

### Alternative 1: Per-Block Tool Registration

Register a separate tool for each block. Rejected because 300+ tools overwhelm agent tool selection.

## References

- Design doc: `docs/superpowers/specs/2026-03-14-webmcp-dashboard-transition-design.md`
- W3C WebMCP Draft: webmachinelearning.github.io/webmcp/
- ADR-287: MCP-First Dashboard
- ADR-406: Block System UI
