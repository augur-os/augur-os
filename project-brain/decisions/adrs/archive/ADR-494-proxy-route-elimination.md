---
status: Implemented
date: 2026-03-23
deciders:
  - Gur Sannikov
related:
  - ADR-465
hub: null
tags:
  - architecture
  - dashboard
  - mcp
superseded_by: null
---

# ADR-494: Proxy Route Elimination — Direct MCP Tool Calls from Dashboard

## Context

The dashboard's data fetching architecture routed all page requests through a catch-all proxy at `apps/dashboard/app/api/[...proxy]/`. This proxy maintained 367 REST-style route entries across three hand-maintained files (`_routes-a.ts`, `_routes-b.ts`, `_routes-c.ts` — 5,834 lines combined) that mapped URLs to MCP tool names with optional `staticArgs`, `extractParams`, `transformResponse`, and `fallback` configs.

**Problems with the proxy layer:**

1. **Staleness**: Hub renames left 113 pages with stale URL prefixes (7 old hub names). Hand-maintained routes silently drifted from reality.
2. **Unnecessary indirection**: Pages called `fetch('/api/hub/skill/action')` → proxy → URL→tool lookup → `callMCPTool()`. But the page already knew (or could know) the tool name.
3. **Centralized config**: The route files were centralized registries — violating ADR-163's decentralization principle.
4. **Developer friction**: Adding a new page required editing a centralized route file in addition to the page component.
5. **Shadowing bugs**: The catch-all `[...proxy]` route shadowed the `/api/mcp/tool` passthrough, causing 404s for all `mcpCall()` users.

Meanwhile, 56 files already used `useMcpQuery`/`mcpCall` to call MCP tools directly via `POST /api/mcp/tool`, proving the pattern worked.

## Decision

Eliminate the proxy route layer entirely. Migrate all dashboard pages from URL-based hooks (`useCachedFetch`, `useCachedMutation`, `useAction`, `useCachedPoll`) to direct MCP tool call hooks (`useMcpQuery`, `useMcpMutation`, `useMcpPoll`).

### New hooks created

| Hook | Purpose | Replaces |
|------|---------|----------|
| `useMcpMutation(tool, opts?)` | Mutations with cache invalidation | `useCachedMutation`, `useAction` |
| `useMcpPoll(key, tool, interval, opts?)` | Interval-based polling | `useCachedPoll` |
| `pluginFallback` utilities | Plugin tool detection | `PLUGIN_TOOL_SOURCES` in `_handler.ts` |

`useMcpQuery` already existed; `useMcpMutation` and `useMcpPoll` are new.

### Migration approach

1. Generated a route migration map (Python regex parser → JSON) mapping all 390 proxy URLs to their MCP tool configs
2. Migrated hub-by-hub: life → brain → career → command → studio → adaptive+shared → framework
3. ~70 page/component files converted
4. Deleted the entire `[...proxy]/` directory, `useCachedFetch.ts`, and migration artifacts

### What remains

- `/api/mcp/tool` — the universal MCP transport (POST with `{ tool, args }`)
- `/api/blocks/data` — block data fetching (already MCP-direct)
- `/api/skill-meta/[skillId]` — standalone route aggregating 11+ MCP tools server-side
- A few non-MCP routes (auth, views, logs) converted to raw React Query

## Consequences

### Positive

- 6,980 lines of centralized config deleted
- No more stale route bugs — pages declare the tool name they need
- Adding a new page no longer requires editing centralized route files
- All data fetching goes through one transport (`POST /api/mcp/tool`)
- Consistent API surface: three hooks cover all patterns (read, write, poll)

### Negative

- Pages now need to know MCP tool names (previously hidden behind URLs)
- `staticArgs` and `transformResponse` logic moved into components (more code per page, but explicit)
- Two Google Workspace routes had `_toolOverride` pattern — now components handle conditional tool dispatch explicitly

### Neutral

- The `/api/mcp/tool` route and `MCPBridge` stdio transport are unchanged
- Block system was already MCP-direct, unaffected
- `useActionRunner` (IDE dispatch) is unrelated, unaffected

## Alternatives Considered

### Alternative 1: Auto-generate routes from MCP tool discovery

Use `tools/list` at build time to generate the route map automatically. Rejected because it fixes staleness but keeps the unnecessary indirection layer. Pages still wouldn't know tool names.

### Alternative 2: Hybrid — new pages use mcpCall, existing pages keep proxy

Keep the proxy for existing pages, only use direct calls for new pages. Rejected per CLAUDE.md Rule 14 ("break compatibility, do cleanup") — maintaining both patterns indefinitely adds cognitive overhead.

## References

- ADR-465: Universal MCP Proxy (the original proxy consolidation — this ADR supersedes the route layer it created)
- Plan: `docs/superpowers/plans/2026-03-23-proxy-route-elimination.md`
- MCP health audit session that identified the root causes

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - removed: "/api/[...proxy]/ catch-all (367 routes)"
      replacement: "POST /api/mcp/tool with { tool, args }"
  patterns_deprecated:
    - pattern: "useCachedFetch, useCachedPoll, useCachedMutation, useAction, useCachedSearch"
      replacement: "useMcpQuery, useMcpMutation, useMcpPoll"
    - pattern: "_routes-{a,b,c}.ts route config entries"
      replacement: "Direct tool name in component via useMcpQuery/useMcpMutation"
  files_affected:
    - "apps/dashboard/app/api/[...proxy]/ (deleted)"
    - "apps/dashboard/lib/hooks/useCachedFetch.ts (deleted)"
    - "~70 page/component files migrated"
```

### Completion Criteria
- [x] All phases executed
- [x] Dashboard builds successfully
- [x] All tests pass
- [x] Zero remaining useCachedFetch consumers
- [x] Proxy route directory deleted
- [x] Documentation updated (CLAUDE.md, DASHBOARD.md, ARCHITECTURE.md)
- [x] ADR status: Implemented
