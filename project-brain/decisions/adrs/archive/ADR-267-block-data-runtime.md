---
status: Implemented
date: '2026-03-10'
deciders:
- Guy
related: []
hub: null
tags:
- block
- data
- runtime
superseded_by: null
---

# ADR-267: Block Data Runtime

## Context

ADR-406 defines the block system UI — composable blocks on view canvases replacing hub overview pages. ADR-287 defines the MCP-first dashboard migration. Neither specifies how blocks actually fetch data, handle mutations, share cached results, manage errors, or orchestrate cross-plugin workflows.

Blocks need a data layer that:
1. Fetches data from MCP tools with caching and deduplication
2. Writes mutations back through existing `useActionRunner`
3. Shares data across blocks without coupling them
4. Handles MCP server failures gracefully
5. Supports cross-plugin workflows that run from CLI, AI client, or dashboard identically

The block system has 14 block types across 15 plugin hubs. Each block fetches from MCP tools, some blocks consume the same tool with different params. Blocks must be independent — one broken block must not kill the view.

## Decision

### 1. React Query as Caching Layer

Use `@tanstack/react-query` (already in package.json, currently unused) with a single `useBlockData` hook wrapping `useQuery`. Query keys follow `['block-data', mcpTool, params, config]` — same tool + same params = shared cache across blocks automatically.

### 2. Stale-While-Revalidate with Per-Type Overrides

Default 5-minute stale time. Overrides: calendar (1min), activity-feed (30s), stat-card/stat-grid (10min), notes (Infinity — local state). No polling, no WebSockets. Users refetch manually or data refreshes on next navigation.

### 3. Direct MCP Mutations via useActionRunner

Writes use existing `useActionRunner({ dispatch: 'fire' })` for single MCP tool calls. After mutation, invalidate the relevant React Query cache key. All blocks consuming that tool refetch automatically. No optimistic updates — MCP is localhost, <50ms round-trip.

### 4. Dual Error Handling

- **Fetch failures**: `keepPreviousData: true` shows last good data + amber `StaleDataBadge`. React Query retries 3x with exponential backoff.
- **Component crashes**: `BlockErrorBoundary` per block instance. One crash doesn't affect other blocks. User can reload the single block.

### 5. Cross-Block Workflows as SKILL.md Files

Workflows are markdown instruction files per the Agent Skills open standard. Each step calls MCP tools. The agent follows the instructions — no workflow engine, no event bus, no client-side chaining.

**Workflow location**: SKILL.md lives in the plugin that owns the primary outcome. A workflow calling `scraper:fetch-url` then `lifestyle:save-idea` lives in the lifestyle plugin.

**Workflow execution**: `useActionRunner({ dispatch: 'ide' })` spawns an agent that follows the SKILL.md. Same workflow runs from CLI (`/workflow-name`) or any AI client.

**Workflow discovery**: A central admin skill scans all `plugins/*/skills/*/skills/*/SKILL.md`, parses MCP tool references, verifies tool availability, and surfaces health status on a dashboard page.

### 6. React Query Setup

One `QueryClient` with `refetchOnWindowFocus: false` (local-first app), `retry: 3`, `staleTime: 300_000`. Wrapped at app root via `QueryClientProvider`.

## Consequences

### Positive

- ~155 lines of new runtime code — minimal surface area
- Zero new dependencies (React Query already installed)
- Zero new concepts — builds on useActionRunner, createAPIRoute, MCP tools, SKILL.md
- Blocks are fully independent — fetch, cache, error handle without coordination
- Cross-block workflows are portable — run from CLI, AI client, or dashboard
- Workflow SKILL.md files follow the Agent Skills open standard (30+ tool compatibility)

### Negative

- No optimistic updates — writes show results after MCP round-trip (~50ms perceived delay)
- `dispatch: 'ide'` for workflows spawns a full agent session (heavier than direct script call)
- Stale data on errors may confuse users if they don't notice the badge
- Manual cache invalidation after writes — developer must know which query keys to invalidate

### Neutral

- React Query DevTools available in development for debugging cache behavior
- Cache size bounded naturally (max 20 blocks × ~1KB = ~20KB)
- `refetchOnWindowFocus: false` means switching tabs won't trigger refetches

## Alternatives Considered

### Alternative 1: View Data Provider

A `<ViewDataProvider>` context wraps each view canvas, pre-fetches all block data sources, blocks read from context.

Rejected: Provider becomes a central coordinator that must know all blocks' data sources upfront. Adding/removing blocks dynamically requires provider re-orchestration. Violates plugin decentralization — provider is a bottleneck.

### Alternative 2: Data Bus + Event System

Zustand store + pub/sub for block-to-block communication. Central store holds all block data, blocks subscribe to slices, mutations publish events.

Rejected: ~800+ lines of new code. Reinvents what React Query already does (caching, deduplication). Creates invisible coupling between blocks. Client-side workflow orchestration violates MCP-first principle and doesn't work from CLI.

### Alternative 3: Declarative YAML Workflow Pipelines

Cross-block workflows defined as YAML pipelines in augur.yaml with `callable:` Python scripts and `input:`/`output:` step dependencies.

Rejected: Invents a new format locked to Augur's runtime. Not portable across AI clients. The Agent Skills open standard (SKILL.md) is simpler, more flexible, and supported by 30+ tools. Agents are smart enough to follow markdown instructions — rigid declarative pipelines are unnecessary.

## References

- ADR-406: Block System UI
- ADR-287: MCP-First Dashboard
- ADR-163: Plugin Decentralization
- Agent Skills Open Standard: agentskills.io
- Design doc: `docs/plans/2026-03-10-block-data-runtime-design.md`

## Impact Manifest

```yaml
impact:
  apis_changed:
    - function: useBlockData
      module: src/dashboard/hooks/useBlockData.ts
      breaking: false
  files_affected:
    - glob: "src/dashboard/app/providers.tsx"
    - glob: "src/dashboard/hooks/useBlockData.ts"
    - glob: "src/dashboard/components/blocks/BlockErrorBoundary.tsx"
    - glob: "src/dashboard/components/blocks/StaleDataBadge.tsx"
    - glob: "src/dashboard/components/blocks/BlockSkeleton.tsx"
    - glob: "plugins/admin/skills/workflows/**"
```

## Implementation Prompt

**Team name**: `adr-267-block-data-runtime`

### Phase 1: Core Data Hook
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Wire QueryClientProvider at app root | `src/dashboard/app/providers.tsx` |
| 1.2 | developer | medium | Implement useBlockData hook with fetchFromMCP | `src/dashboard/hooks/useBlockData.ts` |
| 1.3 | developer | low | Create BlockErrorBoundary component | `src/dashboard/components/blocks/BlockErrorBoundary.tsx` |
| 1.4 | developer | low | Create StaleDataBadge component | `src/dashboard/components/blocks/StaleDataBadge.tsx` |
| 1.5 | developer | low | Create BlockSkeleton component | `src/dashboard/components/blocks/BlockSkeleton.tsx` |

### Phase 2: Workflow Discovery
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create workflow scanner script | `plugins/admin/skills/workflows/scripts/scan_workflows.py` |
| 2.2 | frontend | medium | Create workflow discovery dashboard page | `plugins/admin/skills/workflows/augur/dashboard/page.tsx` |
| 2.3 | developer | low | Register workflows skill in augur.yaml | `plugins/admin/skills/workflows/augur.yaml` |

### Phase 3: Integration
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Wire useBlockData into block type components from ADR-406 | `src/dashboard/components/blocks/types/*.tsx` |
| 3.2 | developer | low | Add cache invalidation to existing useActionRunner write patterns | Block components with mutations |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass
- [ ] useBlockData fetches from MCP tools with React Query caching
- [ ] Two blocks consuming same MCP tool share one fetch
- [ ] StaleDataBadge shows on fetch error with stale data visible
- [ ] BlockErrorBoundary catches component crashes per-block
- [ ] Workflow scanner discovers SKILL.md files across plugins
- [ ] No orphaned files or broken references
- [ ] ADR status updated to Accepted/Implemented
