---
status: Superseded
date: 2026-03-21
deciders:
  - Gur Sannikov
related:
  - ADR-266
  - ADR-453
  - ADR-494
hub: null
tags:
  - dashboard
  - api-routes
  - mcp
  - turbopack
  - performance
superseded_by: ADR-494
---

# ADR-465: Universal MCP Proxy — Dashboard Route Consolidation

## Context

The dashboard had 461 API route files. 420 were MCP proxy boilerplate — each hardcoded a tool name and forwarded params via `createAPIRoute()`. This caused:

1. **Turbopack cache bloat** — 590 entry points (461 routes + 129 pages) produced 600MB+ dev cache triggering a restart thrashing loop
2. **mount-plugins overhead** — copied 253 auto-generated route files from `.claude/skills/*/augur/api/` on every build
3. **Duplicated param validation** — 285 route files contained `extractParams` logic that belonged in MCP tools
4. **Duplicated response shaping** — 267 route files contained `transformResponse` functions reshaping MCP output
5. **Stale wiring** — route files referenced 301 unique MCP tool names with no build-time validation

The existing universal proxy at `api/mcp/tool/route.ts` handled POST requests but had no GET support and no client helper.

## Decision

### 1. Catch-all Proxy Route

Consolidate all 437 proxy route files into a single Next.js catch-all route at `app/api/[...proxy]/route.ts`. The catch-all preserves all existing behavior (extractParams, transformResponse, gracefulFallback) in a modular file structure:

| File | Responsibility |
|------|---------------|
| `route.ts` | Exports GET/POST/PUT/PATCH/DELETE, merges route maps |
| `_types.ts` | MethodConfig with `wrapSuccess`, `staticArgs` fields |
| `_handler.ts` | Core request handling, params envelope retry, fallback logic |
| `_helpers.ts` | Shared helper functions used by route configs |
| `_routes-a.ts` | Route map: actions through brain (74 routes) |
| `_routes-b.ts` | Route map: bridge through insights (125 routes) |
| `_routes-c.ts` | Route map: life through workflows (168 routes) |
| `_dynamic.ts` | 39 regex patterns for `[param]` route segments |

This approach was chosen over full client migration because it achieves the same Turbopack reduction with zero client breakage.

### 2. mcpCall Client Helper

Created `lib/mcp/client.ts` with `mcpCall<T>(tool, args, options)`:
- POST to `/api/mcp/tool` with `{ tool, args }`
- Optional `fallback` value returned on error instead of throwing
- Optional `signal` for AbortController cancellation

67 client files migrated from `fetch('/api/...')` to `mcpCall()`.

### 3. GET Handler on Universal Proxy

Extended `api/mcp/tool/route.ts` with GET support: `?tool=X&param1=Y&param2=Z`. Used by `useCachedFetch` consumers that need React Query integration.

### 4. Handler Optimizations

Added two proxy-level features to reduce route config verbosity:
- **`wrapSuccess: true`** — handler wraps MCP response in `{ success: true, data }` (replaced 17 transforms)
- **`staticArgs: { key: value }`** — handler merges static args with dynamic params (replaced 30 extractParams)

### 5. MCP Tool Updates

Updated 69 Python MCP tools to:
- Accept camelCase param aliases via `or` fallback (e.g., `params.get("project_id") or params.get("projectId")`)
- Return final response shapes with defaults (eliminating dashboard-side null coalescing)

This removed ~70 extractParams/transformResponse from the catch-all while keeping existing CLI/agent callers working.

### 6. Cleanup

- Deleted `createAPIRoute.ts` (454 lines) and its test
- Deleted 256 plugin API source files from `.claude/skills/*/augur/api/`
- Disabled API route mounting in `mount-plugins/copier.ts`
- 3 page-colocated routes rewritten to use `callMCPTool` directly

### 22 Routes That Stay as Individual Files

| Category | Count | Reason |
|----------|-------|--------|
| Auth (login, logout, session, csrf) | 4 | JWT/cookie handling |
| LLM proxy + agents/available | 2 | Multi-provider routing + streaming |
| SSE/streaming (apple notes, google install) | 2 | Different transport |
| Remote auth | 1 | OAuth flow |
| MCP (tool, capabilities) | 2 | Universal proxy + introspection |
| Terminal execute | 1 | Process spawning |
| Agents wizard/onboarding | 2 | Complex UI orchestration |
| Dev sync | 2 | IDE config introspection |
| Content pipelines | 3 | Complex content logic |
| Knowledge OCR | 1 | Binary processing |
| Files git-status | 1 | Scope enforcement |
| Settings layout/pulse | 1 | Complex mode switching |

## Consequences

### Positive

- Turbopack entry points reduced from 590 to 156 (73% reduction)
- Dev cache size expected to drop from 600MB+ to ~150MB
- mount-plugins no longer copies route files (253 fewer file operations per build)
- `createAPIRoute.ts` eliminated (454 lines of duplicated wrapping logic)
- Single entry point for all MCP tool calls (`mcpCall()` or catch-all)
- MCP tools becoming self-validating (accept dashboard params directly)

### Negative

- Catch-all route files total 7,746 lines — complexity relocated, not fully eliminated
- 281 extractParams + 217 transformResponse still embedded in catch-all (incremental work)
- `useCachedFetch` URL rewrites to `/api/mcp/tool?tool=X` bypass catch-all transforms — potential shape mismatches
- 81 client files still use direct `fetch('/api/...')` instead of `mcpCall()`

### Neutral

- `plugin-tool-sources.ts` still exists (used by catch-all handler for fallback metadata)
- Dynamic route matching via regex adds ~5ms overhead per request vs direct route matching
- 203 gracefulFallback configs remain server-side (spec wanted client-side)

## Implementation Order

### Phase 1: Foundation (DONE)
1. Add GET handler to `api/mcp/tool/route.ts`
2. Create `mcpCall()` client helper at `lib/mcp/client.ts`

### Phase 2: Catch-all Proxy (DONE)
3. Extract route configs from 437 route files
4. Generate catch-all at `api/[...proxy]/route.ts`
5. Split into modular files (`_routes-a/b/c.ts`, `_handler.ts`, etc.)
6. Delete 437 route files + 256 plugin API sources
7. Update mount-plugins to skip API route mounting

### Phase 3: Client Migration (DONE — partial)
8. Migrate 67 client files from `fetch('/api/...')` to `mcpCall()`
9. Delete `createAPIRoute.ts`

### Phase 4: MCP Tool Updates (DONE — partial)
10. Add `wrapSuccess` + `staticArgs` handler features (47 functions removed)
11. Strip trivial extractParams/transformResponse (36 functions removed)
12. Update 69 Python MCP tools (~70 functions removed)

### Phase 5: Remaining Work (INCREMENTAL)
13. Migrate remaining 81 client files to `mcpCall()`
14. Move remaining 281 extractParams into MCP tool `inputSchema`
15. Move remaining 217 transformResponse into MCP tool output
16. Move 203 fallback configs to client-side `mcpCall({ fallback })`
17. Delete `plugin-tool-sources.ts`
18. Shrink catch-all toward eventual deletion

## Alternatives Considered

### A: Full Client Migration (Original Plan)

Modify all 175 client files from `fetch('/api/...')` to `mcpCall()`, then delete all route files. No catch-all proxy.

**Rejected because:** Too high risk for a single migration. 175 files touching every hub, with response shape changes. The catch-all approach achieves the same Turbopack benefit with zero client breakage, and client migration happens incrementally.

### B: Next.js Middleware Redirect

Create a Next.js middleware that intercepts `/api/*` requests and redirects to the universal proxy. No catch-all route, no client changes.

**Rejected because:** Middleware runs on every request including static assets. Can't preserve extractParams/transformResponse logic. Would require all MCP tools to accept raw params immediately (massive Python-side effort upfront).

### C: Dynamic Import Catch-all

Create a catch-all that dynamically `import()`s the original route configs. Route files stay on disk but aren't Turbopack entry points.

**Rejected because:** Dynamic imports defeat Turbopack tree-shaking. Route files would still be bundled, just lazily. No meaningful cache reduction.

## References

- Spec: `docs/superpowers/specs/2026-03-21-universal-mcp-proxy-design.md`
- Plan: `docs/superpowers/plans/2026-03-21-universal-mcp-proxy.md`
- Related: ADR-266 (MCP-first API pattern), ADR-453 (vault decoupling)
- CLAUDE.md Rule 11: "MCP-first API — Dashboard API routes call MCP tools as backend"

## Impact Manifest

```yaml
patterns_deprecated:
  - createAPIRoute: "Deleted. Use catch-all route config or mcpCall() directly"
  - createCRUDRoutes: "Deleted. Use catch-all route config"
  - "fetch('/api/hub/skill/endpoint')": "Migrate to mcpCall('tool-name', args)"

apis_changed:
  - "GET /api/mcp/tool?tool=X&params": "New — universal proxy GET handler"
  - "POST /api/mcp/tool { tool, args }": "Existing — now primary client entry point"

files_affected:
  deleted:
    - "apps/dashboard/lib/mcp/createAPIRoute.ts"
    - "apps/dashboard/__tests__/api/refactored-routes.test.ts"
    - "437 route.ts files under apps/dashboard/app/api/"
    - "256 route.ts files under .claude/skills/*/augur/api/"
  created:
    - "apps/dashboard/app/api/[...proxy]/ (8 files)"
    - "apps/dashboard/lib/mcp/client.ts"
  modified:
    - "apps/dashboard/scripts/mount/copier.ts (skip API mounting)"
    - "69 Python MCP tool handlers (param aliases + response shapes)"
    - "67 client files (fetch → mcpCall)"
```
