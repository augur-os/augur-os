---
title: Block Data Runtime Design
date: 2026-03-10
---

# Block Data Runtime Design

**Date:** 2026-03-10
**Status:** Approved
**Scope:** Data fetching, caching, mutations, error handling, and cross-block workflows for the block system (ADR-406)

---

## Vision

Define how blocks fetch data, write mutations, share cached results, handle errors, and orchestrate cross-plugin workflows — using existing infrastructure (React Query, useActionRunner, MCP tools, SKILL.md) with minimal new code.

## Architectural Principles

| Principle | How This Design Respects It |
|---|---|
| Plugin decentralization | Blocks fetch independently, no central data provider. Workflows live in owning plugin. |
| MCP/skills standard compliance | All data flows through MCP tools. Workflows are SKILL.md files per Agent Skills open standard. |
| Cross-block workflows | SKILL.md files that chain MCP tools from any plugin. Run from CLI, AI client, or dashboard identically. |

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Caching layer | React Query (already in package.json) | Free deduplication, stale-while-revalidate, retry with backoff |
| Batch loading | Simple parallel fetches | React Query deduplicates same tool+params across blocks |
| Data refresh | Stale-while-revalidate with per-type overrides | 5min default, 1min calendar, 30s activity-feed, 10min stats |
| Cross-block sharing | Query key convention | `['block-data', toolName, params]` — same key = shared cache |
| Write path | Direct MCP via useActionRunner + cache invalidation | Localhost MCP <50ms, optimistic updates not worth complexity |
| Error resilience | Stale data + badge (fetch) + ErrorBoundary (crash) | Two failure modes, two handlers. One broken block doesn't kill view |
| Cross-block workflows | SKILL.md markdown files | Agent Skills open standard, runs from CLI/AI/dashboard, no new engine |
| Workflow location | Owning plugin + central discovery page | Decentralized ownership, centralized visibility |

## Architecture

### useBlockData Hook

The single new primitive. Wraps React Query around MCP-backed API routes.

```typescript
// src/dashboard/hooks/useBlockData.ts

import { useQuery, useQueryClient } from '@tanstack/react-query';

interface BlockDataSource {
  mcpTool: string;
  params?: Record<string, unknown>;
  apiRoute?: string;
}

interface UseBlockDataResult<T> {
  data: T | undefined;
  loading: boolean;
  error: Error | null;
  refetch: () => void;
  invalidate: () => void;
}

const STALE_TIMES: Record<string, number> = {
  'calendar': 60_000,
  'activity-feed': 30_000,
  'stat-card': 600_000,
  'stat-grid': 600_000,
  'notes': Infinity,
  'ops-board': 120_000,
  // default: 300_000 (5 min)
};

function useBlockData<T>(
  blockType: string,
  dataSource: BlockDataSource,
  config?: Record<string, unknown>
): UseBlockDataResult<T> {
  const queryClient = useQueryClient();
  const queryKey = ['block-data', dataSource.mcpTool, dataSource.params, config];
  const staleTime = STALE_TIMES[blockType] ?? 300_000;

  const { data, isLoading, error, refetch } = useQuery<T>({
    queryKey,
    queryFn: () => fetchFromMCP(dataSource, config),
    staleTime,
    keepPreviousData: true,
  });

  return {
    data,
    loading: isLoading,
    error: error as Error | null,
    refetch,
    invalidate: () => queryClient.invalidateQueries(['block-data', dataSource.mcpTool]),
  };
}
```

### Data Fetch Function

```typescript
async function fetchFromMCP(
  dataSource: BlockDataSource,
  config?: Record<string, unknown>
): Promise<unknown> {
  const route = dataSource.apiRoute ?? `/api/mcp/${dataSource.mcpTool}`;
  const params = { ...dataSource.params, ...config };

  const res = await fetch(route, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });

  if (!res.ok) throw new Error(`MCP fetch failed: ${res.status}`);
  return res.json();
}
```

### Write Path

No new code — uses existing `useActionRunner`.

```typescript
// Single mutation
await runAction({
  dispatch: 'fire',
  tool: 'lifestyle:update-recipe',
  args: { id: recipeId, favorite: true },
});
queryClient.invalidateQueries(['block-data', 'list-recipes']);

// Multi-step workflow
await runAction({
  dispatch: 'ide',
  skill: 'scrape-and-save-idea',
  args: { url },
});
queryClient.invalidateQueries(['block-data', 'list-ideas']);
```

Pattern: `dispatch: 'fire'` for single MCP mutations, `dispatch: 'ide'` for SKILL.md workflows.

### Error Resilience

Two failure modes, two handlers:

| Failure | Handler | User Sees |
|---|---|---|
| MCP fetch error | `keepPreviousData: true` + `StaleDataBadge` | Last good data + amber warning dot |
| First load, MCP down | Empty state | Retry button |
| Component crash | `BlockErrorBoundary` per instance | "Block failed to render" + Reload button |
| Retry exhaustion | React Query stops after 3 retries | Stale data stays, no retry storm |

```typescript
// Block component pattern
function DataListBlock({ instanceId, config, dataSource }: BlockProps) {
  const { data, loading, error } = useBlockData('data-list', dataSource, config);

  return (
    <BlockErrorBoundary instanceId={instanceId}>
      <div className="relative">
        {error && <StaleDataBadge error={error} />}
        {loading && !data ? (
          <BlockSkeleton type="data-list" />
        ) : (
          <DataList items={data?.items ?? []} />
        )}
      </div>
    </BlockErrorBoundary>
  );
}
```

### Cross-Block Workflows

Workflows are SKILL.md files per the Agent Skills open standard. They live in the plugin that owns the outcome.

**Location:**
```
plugins/{bundle}/skills/{skill}/
  skills/
    {workflow-name}/
      SKILL.md    # the entire workflow definition
```

**Example SKILL.md:**
```markdown
---
name: scrape-and-save-idea
description: Scrape a URL, summarize content, save as lifestyle idea
---

# Scrape and Save Idea

## Step 1: Fetch the page
Call `scraper:fetch-url` with the provided URL.
Extract the page title and main content.

## Step 2: Summarize
Call `ai-bridge:summarize` with the page content from Step 1.
Keep the summary under 200 words.

## Step 3: Save as idea
Call `lifestyle:save-idea` with:
- title: the page's title
- body: the summary from Step 2
- source_url: the original URL

## Step 4: Confirm
Tell the user the idea was saved and show the title.
```

**Execution surfaces:**

| Surface | Mechanism |
|---|---|
| CLI | `/scrape-and-save-idea https://example.com` |
| AI client | Agent loads SKILL.md, follows steps |
| Dashboard action-bar | `useActionRunner({ dispatch: 'ide', skill: 'scrape-and-save-idea' })` |
| Auto loop | `trigger: manual` in augur.yaml |

**Central discovery page** (`plugins/admin/skills/workflows/`):
- Scans all `plugins/*/skills/*/skills/*/SKILL.md`
- Parses MCP tool references from markdown
- Verifies each referenced tool exists in MCP server
- Shows health status per workflow

### React Query Setup

One-time wiring — React Query is in package.json but unused.

```typescript
// src/dashboard/app/providers.tsx

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 300_000,
      retry: 3,
      keepPreviousData: true,
      refetchOnWindowFocus: false,
    },
  },
});
```

`refetchOnWindowFocus: false` because Augur is local-first — MCP data doesn't change while user is in another tab.

## Data Flow Summary

```
┌─────────────────────────────────────────────────────┐
│                    View Canvas                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ stat-card│ │data-list │ │action-bar│            │
│  │useBlock  │ │useBlock  │ │useAction │            │
│  │Data()    │ │Data()    │ │Runner()  │            │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘            │
└───────┼─────────────┼────────────┼───────────────────┘
        │             │            │
   ┌────▼─────────────▼────┐  ┌────▼──────────────┐
   │   React Query Cache   │  │  useActionRunner  │
   │ key: ['block-data',   │  │ 'fire' → MCP tool │
   │   toolName, params]   │  │ 'ide'  → SKILL.md │
   └────────┬──────────────┘  └────────┬──────────┘
            │    ┌─────────────────┐   │
            └───►│  /api/mcp/*     │◄──┘
                 │  createAPIRoute │
                 └────────┬───────┘
                 ┌────────▼───────┐
                 │   MCP Server   │
                 │  (localhost)   │
                 └────────────────┘
```

## New Code Inventory

| Component | Lines | Status |
|---|---|---|
| `useBlockData` hook | ~60 | New |
| `fetchFromMCP` function | ~15 | New |
| `BlockErrorBoundary` | ~30 | New |
| `StaleDataBadge` | ~15 | New |
| `BlockSkeleton` | ~20 | New |
| `QueryClientProvider` wiring | ~15 | New (one-time) |
| `useActionRunner` | existing | No changes |
| `createAPIRoute` | existing | No changes |
| MCP server | existing | No changes |
| **Total new runtime** | **~155 lines** | |

## Scope Exclusions

- No optimistic updates (MCP is localhost, <50ms)
- No offline support (MCP server is local)
- No real-time subscriptions / WebSockets (single user)
- No client-side workflow engine (agent follows SKILL.md)
- No data bus / pub-sub (React Query handles sharing)
- No command queue for writes (no network failures to retry)
