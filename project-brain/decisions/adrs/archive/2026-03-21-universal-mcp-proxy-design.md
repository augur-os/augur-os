# Universal MCP Proxy — Dashboard Route Consolidation

**Date:** 2026-03-21
**Status:** Draft
**Scope:** Dashboard API routing, MCP tool param validation, mount-plugins, client migration

## Problem

The dashboard has 461 API route files. 420 are MCP proxy boilerplate (378 using `createAPIRoute` + 42 hand-written `callMCPTool` wrappers) — each hardcodes a tool name and forwards params. This causes:

1. **Turbopack cache bloat** — 590 entry points (461 routes + 129 pages) produce a 600MB+ dev cache that triggers a restart thrashing loop
2. **mount-plugins overhead** — copies 253 auto-generated route files from `.claude/skills/*/augur/api/` on every build
3. **Duplicated param validation** — 285 route files contain `extractParams` logic that belongs in the MCP tools
4. **Duplicated response shaping** — 267 route files contain `transformResponse` functions that reshape MCP output
5. **Stale wiring** — route files reference 301 unique MCP tool names with no build-time validation

## Design

### Core: Extend Existing Universal MCP Proxy

An MCP proxy already exists at `app/api/mcp/tool/route.ts` (79 lines). It accepts `{ tool, args }`, calls `callMCPTool`, handles the `params` envelope retry, and returns JSON. This route becomes the single API entry point for all MCP tool calls.

Extend it to also handle GET:

```
POST /api/mcp/tool  { "tool": "get-career-job-counts", "args": { "limit": 10 } }
GET  /api/mcp/tool?tool=get-career-job-counts&limit=10
```

- POST: tool name + args from JSON body (existing behavior, including `params` envelope retry)
- GET: tool name from `?tool=`, remaining query params forwarded as args
- No `transformResponse`, no `gracefulFallback`, no `extractParams`
- The MCP server is the single source of truth

### Response Shaping Migration

267 routes currently transform MCP responses via `transformResponse`. These transforms move to:

1. **MCP tool side** (preferred) — the tool returns the final shape directly. For transforms that normalize tool output (wrapping in envelopes, renaming fields, filtering arrays).
2. **Client side** — the `mcpCall` consumer reshapes the response. For UI-specific transforms (extracting a single field for display).

The universal proxy returns raw MCP tool output. No dashboard-side transforms.

### Fallback Strategy

193 routes use `gracefulFallback` to return structured empty data when MCP tools fail. This prevents error screens when plugins are not installed.

Fallback moves to the client helper:

```typescript
const data = await mcpCall("finance-balance-sheet", {}, {
  fallback: { data: null }  // returned on MCP error instead of throwing
});
```

Components that need graceful degradation specify their fallback inline. Components that should show errors omit the fallback.

### Client Helper

One function in `lib/mcp/client.ts` (~40 lines):

```typescript
const data = await mcpCall("get-career-job-counts", { limit: 10 });
const data = await mcpCall("finance-balance-sheet", {}, { fallback: { data: null } });
const data = await mcpCall("search", { query: "test" }, { signal: controller.signal });
```

- Wraps `fetch('/api/mcp/tool', { method: 'POST', body: { tool, args } })`
- Returns parsed `data` on success, throws on error unless `fallback` provided
- Optional `signal` for AbortController
- 137 client files migrate from ad-hoc `fetch('/api/...')` to `mcpCall(toolName, args)`

### MCP Tool Param Migration

All `extractParams` logic moves from dashboard into MCP tools. 301 unique tool names are referenced across 420 proxy routes:

- Query string parsing → MCP tool receives args dict directly, validates
- Body parsing → MCP tool receives body as args, validates
- Tools validate strictly with clear error messages
- `params` envelope wrapping stays in the universal proxy's retry logic (already implemented)
- MCP protocol `inputSchema` provides schema-level validation for free

### Mount-Plugins Changes

mount-plugins stops copying API route files entirely:

- **Before:** copies every `route.ts` from plugin `augur/api/` into `app/api/{hub}/{skill}/`
- **After:** only mounts `dashboard/` (pages) and `lib/` (shared code)
- Plugin `augur/api/` directories become dead code and are deleted

### Complete Route Classification (461 routes)

**Consolidate into universal proxy (420 routes):**

| Category | Count | Action |
|----------|-------|--------|
| `createAPIRoute` proxies | 378 | Delete — use `mcpCall()` |
| Hand-written `callMCPTool` wrappers | 42 | Delete — use `mcpCall()` |

**Move to MCP tools (19 routes):**

| Category | Count | Routes | New MCP tool |
|----------|-------|--------|-------------|
| Views CRUD | 4 | `api/views/*` | `views-crud` |
| Page builder | 4 | `api/blocks/catalog`, `studio/page-builder/*`, `skill-meta/*/decompose` | `page-builder-*`, `list-block-catalog` |
| Health stubs | 4 | `brain/knowledge/health`, `life/finance/health`, `studio/*/health` | Delete — MCP reports health |
| Re-exports | 2 | `command/observe/health`, `command/observe/logs` | Delete — aliases |
| Action discovery | 1 | `api/actions` | `list-actions` |
| Skill readme | 1 | `api/skills/[skill]` | `get-skill-readme` |
| Screenshot serving | 1 | `apple/screenshots/image` | `serve-binary-file` (base64) |
| Home automation stubs | 3 | `home-automation/climate,routines,security` | Move to existing HA MCP tools |

**Delete (no replacement needed, 2 routes):**

| Route | Reason |
|-------|--------|
| `command/observe/health` | Re-export of `metrics/system` |
| `command/observe/logs` | Re-export of `logs` |

**Keep as individual route files (~22 routes):**

| Category | Count | Routes | Reason |
|----------|-------|--------|--------|
| Auth | 4 | login, logout, session, csrf | JWT/cookie handling |
| SSE/streaming | 1 | apple notes events | Different transport |
| LLM proxy | 2 | `api/llm`, `api/agents/available` | Multi-provider routing + streaming |
| Remote auth | 1 | `auth/start/[provider]` | OAuth flow |
| MCP capabilities | 1 | `mcp/capabilities` | Server introspection |
| Terminal execute | 1 | `terminal-automation/execute` | Process spawning |
| Agents wizard | 2 | `wizard/create`, `onboarding/validate` | Complex UI orchestration |
| Pulse/layout | 1 | `settings/layout/pulse` | Complex mode switching |
| Dev sync | 2 | `dev-sync/sync-status`, `client-skills` | IDE config introspection |
| Content pipelines | 3 | `linkedin-writer/posts`, `smb/posts`, `smb/refine-instructions` | Complex content logic |
| Knowledge OCR | 1 | `brain/knowledge/ocr` | Binary processing |
| File auth | 1 | `files/git-status` | Scope enforcement |
| Google install | 1 | `google-workspace/install` | SSE streaming |

**Verification: 420 + 19 + 22 = 461** (all routes accounted for)

## Migration Strategy

Big-bang. No phased rollout.

1. Extend existing `api/mcp/tool/route.ts` with GET support
2. Create `lib/mcp/client.ts` with `mcpCall()` helper (includes fallback support)
3. Move `extractParams` logic into MCP tools (audit all 301 referenced tool names)
4. Move `transformResponse` logic into MCP tools or client consumers
5. Migrate 137 client files from `fetch('/api/...')` to `mcpCall(toolName, args)`
6. Create new MCP tools for views, block catalog, actions, skills, page-builder
7. Delete all proxy route files from plugin sources and `app/api/`
8. Update mount-plugins to skip API route mounting
9. Delete `createAPIRoute.ts`, `createCRUDRoutes`, and related helpers

**Rollback:** Single commit. Revert the commit to restore all previous route files. No compatibility shims.

**Verification gate:** Before merging, run `auto-test-api` and `auto-test-pages` to confirm all dashboard pages render and all MCP tools respond correctly through the universal proxy.

## Impact

| Metric | Before | After |
|--------|--------|-------|
| API route files | 461 | ~22 |
| Turbopack entry points | 590 | ~151 |
| Dev cache size | 600MB+ | ~150MB (est.) |
| mount-plugins route copies | ~253 | 0 |
| Client API pattern | Ad-hoc `fetch()` across 137 files | `mcpCall(toolName, args)` |
| Param validation | Split across dashboard + MCP | MCP tools only |
| Response shaping | Dashboard `transformResponse` (267) | MCP tools + client consumers |
| Fallback handling | Dashboard `gracefulFallback` (193) | Client `mcpCall({ fallback })` |
| Source of truth | Dashboard route files + MCP tools | MCP tools only |

## Files to Create

- `apps/dashboard/lib/mcp/client.ts` — client helper (~40 lines)
- New MCP tools for views CRUD, block catalog, actions, skills, page-builder

## Files to Delete

- `apps/dashboard/lib/mcp/createAPIRoute.ts` (454 lines)
- `apps/dashboard/lib/mcp/plugin-tool-sources.ts` (if only used by createAPIRoute)
- ~439 `route.ts` files across `app/api/` and plugin `augur/api/` sources
- All plugin `augur/api/` directories in `.claude/skills/`

## Files to Modify

- `apps/dashboard/app/api/mcp/tool/route.ts` — add GET handler
- `apps/dashboard/scripts/mount-plugins.ts` — remove API route mounting logic
- 137 client files — migrate `fetch()` calls to `mcpCall()`
- MCP tool handlers — add param validation for 301 referenced tool names
- `apps/dashboard/lib/mcp/connection.ts` — already fixed: `--force` on reconnect
- `apps/dashboard/lib/mcp/diagnostics.ts` — already fixed: lock contention not permanent

## Risks

1. **MCP tool param validation gaps** — some tools may silently accept bad params today because the dashboard validated first. Mitigation: audit each tool's param handling during migration.
2. **Response shape changes** — removing `transformResponse` means clients receive raw MCP output. Mitigation: verify each of the 267 transform consumers receives the expected shape.
3. **Fallback behavior changes** — components must opt into fallbacks explicitly via `mcpCall({ fallback })`. Missing a fallback shows errors where empty states appeared before. Mitigation: grep all 193 `gracefulFallback` usages and port to client-side fallbacks.
4. **Custom route misidentification** — a route classified as "proxy" may have subtle custom logic. Mitigation: manual review of each route before deletion.
5. **Big-bang scope** — 461 route deletions + 137 client migrations + 301 tool updates in one commit. Mitigation: comprehensive verification gate; revert is one git command.
6. **Non-JSON routes** — binary/streaming routes must stay as individual files. Mitigation: explicit classification above (16 non-JSON identified, all in "keep" list).
7. **Tool name drift** — 301 referenced tool names vs actual registered tools may not match. Mitigation: audit tool names against `@mcp.tool(name=...)` registrations before migration.

## Non-Goals

- Changing the MCP protocol or transport
- Consolidating the 129 page files (separate concern)
- Adding API authentication beyond existing auth routes
- Backwards-compatible URL aliases for old routes
