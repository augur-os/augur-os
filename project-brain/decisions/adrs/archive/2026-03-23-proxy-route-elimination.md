# Proxy Route Elimination Implementation Plan

**ADR:** ADR-494

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the 5,800-line hand-maintained proxy route layer (`_routes-{a,b,c}.ts`) by migrating all dashboard pages from `useCachedFetch`/`useCachedMutation`/`useAction`/`useCachedPoll` to direct MCP tool calls via `useMcpQuery`/`useMcpMutation`/`useMcpPoll`.

**Architecture:** The catch-all proxy at `apps/dashboard/app/api/[...proxy]/` maps 367 REST-style URLs to MCP tool names + params + transforms. Pages already split 50/50 between the modern `useMcpQuery` pattern (56 files, calls `/api/mcp/tool` directly by tool name) and the legacy `useCachedFetch` pattern (61 files, calls `/api/{hub}/{skill}/{action}` which the proxy translates). We complete the migration to the modern pattern, then delete the proxy layer entirely. The `/api/mcp/tool` passthrough route and `/api/blocks/data` route remain — they're the actual MCP transport, not the translation layer.

**Tech Stack:** TypeScript, React Query, Next.js App Router, Python MCP tools (read-only — no Python changes)

---

## File Structure

### New files to create

| File | Responsibility |
|------|---------------|
| `apps/dashboard/lib/mcp/useMcpMutation.ts` | React hook for MCP tool mutations (replaces `useCachedMutation`/`useAction`) |
| `apps/dashboard/lib/mcp/useMcpPoll.ts` | React hook for MCP tool polling (replaces `useCachedPoll`) |
| `apps/dashboard/lib/mcp/pluginFallback.ts` | Shared fallback detection utility (extracts `PLUGIN_TOOL_SOURCES` + `isFallbackResponse` logic from `_handler.ts`) |
| `apps/dashboard/lib/mcp/route-map.json` | Generated JSON mapping of every proxy route URL → `{ tool, args, hasTransform, hasExtract }` — used as migration reference, deleted when done |
| `scripts/generate_route_map.py` | One-time script: parses `_routes-{a,b,c}.ts` via regex and emits `route-map.json` |
| `tests/dashboard/lib/mcp/useMcpMutation.test.ts` | Tests for `useMcpMutation` |
| `tests/dashboard/lib/mcp/useMcpPoll.test.ts` | Tests for `useMcpPoll` |
| `tests/dashboard/lib/mcp/pluginFallback.test.ts` | Tests for `pluginFallback` |

### Files to modify (per-hub migration — each hub is one task)

Each migrated page replaces:
- `import { useCachedFetch } from "@/lib/hooks/useCachedFetch"` → `import { useMcpQuery } from "@/lib/mcp/useMcpQuery"`
- `import { useCachedMutation, useAction } from "@/lib/hooks/useCachedFetch"` → `import { useMcpMutation } from "@/lib/mcp/useMcpMutation"`
- `import { useCachedPoll } from "@/lib/hooks/useCachedFetch"` → `import { useMcpPoll } from "@/lib/mcp/useMcpPoll"`
- URL strings → tool name strings + explicit args

### Files to delete (after all hubs migrated)

| File | Lines | Why |
|------|-------|-----|
| `apps/dashboard/app/api/[...proxy]/_routes-a.ts` | ~1,600 | URL→tool map, no longer needed |
| `apps/dashboard/app/api/[...proxy]/_routes-b.ts` | ~2,000 | URL→tool map, no longer needed |
| `apps/dashboard/app/api/[...proxy]/_routes-c.ts` | ~2,200 | URL→tool map, no longer needed |
| `apps/dashboard/app/api/[...proxy]/_handler.ts` | ~320 | Proxy dispatch logic, no longer needed |
| `apps/dashboard/app/api/[...proxy]/_helpers.ts` | ~400 | Shared extractors/transforms, moved to components |
| `apps/dashboard/app/api/[...proxy]/_dynamic.ts` | ~49 | Dynamic route patterns, no longer needed |
| `apps/dashboard/app/api/[...proxy]/_types.ts` | ~23 | Route config types, no longer needed |
| `apps/dashboard/app/api/[...proxy]/route.ts` | ~71 | Catch-all entry point, no longer needed |

Total: ~6,700 lines deleted.

`apps/dashboard/lib/hooks/useCachedFetch.ts` (~360 lines) is deleted after all consumers are migrated (includes `useCachedFetch`, `useCachedPoll`, `useCachedMutation`, `useAction`, and `useCachedSearch` — verify zero consumers of each before deletion).

---

## Migration Pattern Reference

### Pattern A: Simple read (Tier 1-2)

Before:
```tsx
// Page calls /api/brain/rag/overview via proxy
// Proxy route: { toolName: "manage-rag", staticArgs: { action: "overview" } }
const { data, loading, error } = useCachedFetch<RagOverview>(
  "knowledge-rag-overview",
  "/api/brain/rag/overview",
  "live",
);
```

After:
```tsx
const { data, loading, error } = useMcpQuery<RagOverview>(
  "knowledge-rag-overview",
  "manage-rag",
  "live",
  { args: { action: "overview" } },
);
```

### Pattern B: Read with response transform (Tier 3)

Before:
```tsx
// Proxy route has transformResponse: (data) => ({ chains: data.skills.filter(...).map(...) })
const { data } = useCachedFetch<{ chains: Chain[] }>(
  "agent-chains",
  "/api/agents/chain",
  "config",
);
```

After:
```tsx
const { data } = useMcpQuery<{ chains: Chain[] }>(
  "agent-chains",
  "list-skills",
  "config",
  {
    select: (data: any) => ({
      chains: (data?.skills ?? [])
        .filter((s: any) => s.id === "executor" || s.capabilities?.includes("chain"))
        .map((s: any) => ({ name: s.id, description: s.description || s.id })),
    }),
  },
);
```

### Pattern C: Mutation (replacing useAction/useCachedMutation)

Before:
```tsx
// Proxy route: { toolName: "update-agent-weights", staticArgs: { save: true } }
const { run, loading } = useAction("/api/agents/recalculate");
// called as: run({})
```

After:
```tsx
const { mutate, loading } = useMcpMutation("update-agent-weights", {
  invalidates: ["agent-weights"],
});
// called as: mutate({ save: true })
```

### Pattern D: Polling (replacing useCachedPoll)

Before:
```tsx
const { data } = useCachedPoll<Light[]>(
  ["home", "lights"],
  "/api/life/home-automation/lights",
  10_000,
  { preset: "device", select: (r: any) => r.lights ?? [] },
);
```

After:
```tsx
const { data } = useMcpPoll<Light[]>(
  ["home", "lights"],
  "manage-hue-lights",
  10_000,
  { args: { action: "list" }, preset: "device", select: (r: any) => r.lights ?? [] },
);
```

### Pattern E: Fallback (plugin tools)

Before:
```tsx
// Proxy route: { toolName: "get-attention-items", fallback: { items: [], total: 0 } }
const { data } = useCachedFetch("/api/adaptive/attention", "live");
```

After:
```tsx
const { data } = useMcpQuery(
  "attention-items",
  "get-attention-items",
  "live",
  { fallback: { items: [], total: 0 } },
);
```

### Pattern F: extractParams with dynamic route segments

Before:
```tsx
// Dynamic route: /api/life/eisenhower/[id]
// extractParams reads context.params.id
const { data } = useCachedFetch(`/api/life/eisenhower/${id}`, "user-data");
```

After:
```tsx
const { data } = useMcpQuery(
  ["eisenhower-task", id],
  "manage-eisenhower-tasks",
  "user-data",
  { args: { action: "get", id } },
);
```

### Pattern G: Conditional tool selection (2 Google Workspace routes)

Two routes use `_toolOverride` in `extractParams` to dispatch to different MCP tools based on the request body. Note: `_handler.ts` never actually consumes `_toolOverride` — it passes through as a param. These routes are effectively broken in the proxy. Migration fixes this by calling the correct tool directly.

Before:
```tsx
// POST /api/life/google-workspace/sheets
// extractParams returns _toolOverride: 'google-sheets-create' when action === 'create'
const { run } = useAction("/api/life/google-workspace/sheets");
run({ action: "create", title: "New Sheet" });
```

After:
```tsx
const { mutate: createSheet } = useMcpMutation("google-sheets-create");
const { mutate: appendSheet } = useMcpMutation("google-sheets-append");

// Component decides which tool to call:
if (action === "create") {
  createSheet({ title });
} else {
  appendSheet({ spreadsheetId, range, values });
}
```

The same pattern applies to `google-tasks-create` / `google-tasks-complete`.

---

## Task 1: Create `useMcpMutation` hook

**Files:**
- Create: `apps/dashboard/lib/mcp/useMcpMutation.ts`
- Create: `tests/dashboard/lib/mcp/useMcpMutation.test.ts`
- Reference: `apps/dashboard/lib/hooks/useCachedFetch.ts:159-297` (existing `useCachedMutation` + `useAction`)
- Reference: `apps/dashboard/lib/mcp/client.ts` (mcpCall)
- Reference: `apps/dashboard/lib/mcp/useMcpQuery.ts` (pattern to follow)

- [ ] **Step 1: Write the failing test**

```typescript
// tests/dashboard/lib/mcp/useMcpMutation.test.ts
import { renderHook, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

// Mock mcpCall
jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn(),
}));

import { mcpCall } from "@/lib/mcp/client";
import { useMcpMutation } from "@/lib/mcp/useMcpMutation";

const mockedMcpCall = mcpCall as jest.MockedFunction<typeof mcpCall>;

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: queryClient },
      children,
    );
  };
}

describe("useMcpMutation", () => {
  beforeEach(() => {
    mockedMcpCall.mockReset();
  });

  it("calls mcpCall with tool name and body", async () => {
    mockedMcpCall.mockResolvedValue({ success: true });
    const { result } = renderHook(
      () => useMcpMutation("update-agent-weights"),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      await result.current.mutate({ save: true });
    });

    expect(mockedMcpCall).toHaveBeenCalledWith(
      "update-agent-weights",
      { save: true },
      {},
    );
  });

  it("merges staticArgs into the call", async () => {
    mockedMcpCall.mockResolvedValue({ success: true });
    const { result } = renderHook(
      () => useMcpMutation("set-config", { staticArgs: { scope: "onboarding" } }),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      await result.current.mutate({ value: "done" });
    });

    expect(mockedMcpCall).toHaveBeenCalledWith(
      "set-config",
      { value: "done", scope: "onboarding" },
      {},
    );
  });

  it("invalidates query keys after success", async () => {
    mockedMcpCall.mockResolvedValue({ ok: true });
    const queryClient = new QueryClient();
    const spy = jest.spyOn(queryClient, "invalidateQueries");

    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children);

    const { result } = renderHook(
      () => useMcpMutation("some-tool", { invalidates: ["list-key"] }),
      { wrapper },
    );

    await act(async () => {
      await result.current.mutate({});
    });

    expect(spy).toHaveBeenCalledWith({ queryKey: ["list-key"] });
  });

  it("applies select to the response", async () => {
    mockedMcpCall.mockResolvedValue({ data: { id: 1 }, success: true });
    const { result } = renderHook(
      () =>
        useMcpMutation<Record<string, unknown>, number>("some-tool", {
          select: (raw: unknown) => (raw as any).data.id,
        }),
      { wrapper: createWrapper() },
    );

    let res: number | undefined;
    await act(async () => {
      res = await result.current.mutate({});
    });

    expect(res).toBe(1);
  });

  it("sets error state on failure", async () => {
    mockedMcpCall.mockRejectedValue(new Error("Tool failed"));
    const { result } = renderHook(
      () => useMcpMutation("bad-tool"),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      try {
        await result.current.mutate({});
      } catch {
        // expected
      }
    });

    expect(result.current.error).toBe("Tool failed");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && npx jest tests/dashboard/lib/mcp/useMcpMutation.test.ts --no-coverage 2>&1 | tail -5`
Expected: FAIL — module `@/lib/mcp/useMcpMutation` not found

- [ ] **Step 3: Implement useMcpMutation**

```typescript
// apps/dashboard/lib/mcp/useMcpMutation.ts
"use client";

/**
 * React hook for MCP tool mutations.
 *
 * Replaces useCachedMutation/useAction for routes that map to MCP tools.
 * Uses mcpCall() directly — no proxy route translation needed.
 */

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { mcpCall } from "./client";

export interface McpMutationOpts<TResult> {
  /** Fixed args merged into every call (takes precedence over body args) */
  staticArgs?: Record<string, unknown>;
  /** Query keys to invalidate after successful mutation */
  invalidates?: string[];
  /** Transform the raw MCP response */
  select?: (raw: unknown) => TResult;
  /** Callback after successful mutation */
  onSuccess?: (result: TResult) => void;
}

export interface McpMutationResult<TBody, TResult> {
  mutate: (body?: TBody) => Promise<TResult>;
  loading: boolean;
  error: string | null;
}

export function useMcpMutation<TBody = Record<string, unknown>, TResult = unknown>(
  tool: string,
  opts?: McpMutationOpts<TResult>,
): McpMutationResult<TBody, TResult> {
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutate = useCallback(
    async (body?: TBody): Promise<TResult> => {
      setLoading(true);
      setError(null);
      try {
        const args = {
          ...(body as Record<string, unknown> ?? {}),
          ...(opts?.staticArgs ?? {}),
        };

        const raw = await mcpCall(tool, args, {});
        const result = opts?.select ? opts.select(raw) : (raw as TResult);

        if (opts?.invalidates) {
          for (const key of opts.invalidates) {
            queryClient.invalidateQueries({ queryKey: [key] });
          }
        }

        opts?.onSuccess?.(result);
        return result;
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [tool, opts?.staticArgs, opts?.invalidates, opts?.select, opts?.onSuccess, queryClient],
  );

  return { mutate, loading, error };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dashboard && npx jest tests/dashboard/lib/mcp/useMcpMutation.test.ts --no-coverage 2>&1 | tail -10`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/mcp/useMcpMutation.ts tests/dashboard/lib/mcp/useMcpMutation.test.ts
git commit -m "feat(mcp): add useMcpMutation hook for direct MCP tool mutations"
```

---

## Task 2: Create `useMcpPoll` hook

**Files:**
- Create: `apps/dashboard/lib/mcp/useMcpPoll.ts`
- Create: `tests/dashboard/lib/mcp/useMcpPoll.test.ts`
- Reference: `apps/dashboard/lib/hooks/useCachedFetch.ts:117-157` (existing `useCachedPoll`)
- Reference: `apps/dashboard/lib/mcp/useMcpQuery.ts` (pattern to follow)

- [ ] **Step 1: Write the failing test**

```typescript
// tests/dashboard/lib/mcp/useMcpPoll.test.ts
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn(),
}));

import { mcpCall } from "@/lib/mcp/client";
import { useMcpPoll } from "@/lib/mcp/useMcpPoll";

const mockedMcpCall = mcpCall as jest.MockedFunction<typeof mcpCall>;

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: queryClient },
      children,
    );
  };
}

describe("useMcpPoll", () => {
  beforeEach(() => {
    mockedMcpCall.mockReset();
  });

  it("calls mcpCall with tool and args", async () => {
    mockedMcpCall.mockResolvedValue({ lights: [{ id: 1 }] });
    const { result } = renderHook(
      () =>
        useMcpPoll(["home", "lights"], "manage-hue-lights", 10_000, {
          args: { action: "list" },
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.data).not.toBeNull());

    expect(mockedMcpCall).toHaveBeenCalledWith(
      "manage-hue-lights",
      { action: "list" },
      expect.objectContaining({}),
    );
  });

  it("applies select transform", async () => {
    mockedMcpCall.mockResolvedValue({ lights: [{ id: 1 }, { id: 2 }] });
    const { result } = renderHook(
      () =>
        useMcpPoll(["home", "lights"], "manage-hue-lights", 10_000, {
          select: (r: any) => r.lights ?? [],
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.data).toHaveLength(2));
  });

  it("returns loading and error states", async () => {
    mockedMcpCall.mockRejectedValue(new Error("Connection lost"));
    const { result } = renderHook(
      () => useMcpPoll("poll-key", "bad-tool", 5_000),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.error).toBe("Connection lost"));
    expect(result.current.data).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && npx jest tests/dashboard/lib/mcp/useMcpPoll.test.ts --no-coverage 2>&1 | tail -5`
Expected: FAIL — module `@/lib/mcp/useMcpPoll` not found

- [ ] **Step 3: Implement useMcpPoll**

```typescript
// apps/dashboard/lib/mcp/useMcpPoll.ts
"use client";

/**
 * React hook for polling MCP tools at a fixed interval.
 *
 * Replaces useCachedPoll for routes that map to MCP tools.
 * Uses mcpCall() directly — no proxy route translation needed.
 */

import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { mcpCall } from "./client";
import type { PresetName } from "./useMcpQuery";

// Re-use presets from useMcpQuery
const PRESETS: Record<PresetName, { staleTime: number; refetchOnWindowFocus: boolean }> = {
  device: { staleTime: 10_000, refetchOnWindowFocus: true },
  realtime: { staleTime: 30_000, refetchOnWindowFocus: true },
  live: { staleTime: 120_000, refetchOnWindowFocus: false },
  "user-data": { staleTime: 300_000, refetchOnWindowFocus: false },
  config: { staleTime: 600_000, refetchOnWindowFocus: false },
  static: { staleTime: Infinity, refetchOnWindowFocus: false },
};

export interface McpPollOpts<T> {
  args?: Record<string, unknown>;
  preset?: PresetName;
  select?: (raw: unknown) => T;
  enabled?: boolean;
}

export interface McpPollResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function useMcpPoll<T = unknown>(
  key: string | string[],
  tool: string,
  intervalMs: number,
  opts?: McpPollOpts<T>,
): McpPollResult<T> {
  const preset = opts?.preset ?? "device";
  const presetConfig = PRESETS[preset];
  const queryKey: unknown[] = [...(Array.isArray(key) ? key : [key]), tool];

  if (opts?.args && Object.keys(opts.args).length > 0) {
    queryKey.push(opts.args);
  }

  const { data, isLoading, error } = useQuery<unknown, Error, T>({
    queryKey,
    queryFn: () => mcpCall<T>(tool, opts?.args ?? {}, {}),
    staleTime: presetConfig.staleTime,
    refetchOnWindowFocus: presetConfig.refetchOnWindowFocus,
    refetchInterval: intervalMs,
    enabled: opts?.enabled !== false,
    placeholderData: keepPreviousData,
    select: opts?.select,
  });

  return {
    data: data ?? null,
    loading: isLoading,
    error: error ? error.message : null,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dashboard && npx jest tests/dashboard/lib/mcp/useMcpPoll.test.ts --no-coverage 2>&1 | tail -10`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/mcp/useMcpPoll.ts tests/dashboard/lib/mcp/useMcpPoll.test.ts
git commit -m "feat(mcp): add useMcpPoll hook for polling MCP tools at intervals"
```

---

## Task 3: Create `pluginFallback` utility

**Files:**
- Create: `apps/dashboard/lib/mcp/pluginFallback.ts`
- Create: `tests/dashboard/lib/mcp/pluginFallback.test.ts`
- Reference: `apps/dashboard/app/api/[...proxy]/_handler.ts:16-42` (PLUGIN_TOOL_SOURCES map)
- Reference: `apps/dashboard/lib/mcp/types.ts:41-55` (isFallbackResponse)

- [ ] **Step 1: Write the failing test**

```typescript
// tests/dashboard/lib/mcp/pluginFallback.test.ts
import { pluginForTool, isPluginTool, isFallbackResponse } from "@/lib/mcp/pluginFallback";

describe("pluginFallback", () => {
  describe("pluginForTool", () => {
    it("returns plugin name for known plugin tools", () => {
      expect(pluginForTool("get-attention-items")).toBe("attention");
      expect(pluginForTool("get-daemon-status")).toBe("daemon");
      expect(pluginForTool("unified-search")).toBe("knowledge");
    });

    it("returns null for non-plugin tools", () => {
      expect(pluginForTool("list-skills")).toBeNull();
      expect(pluginForTool("file-read")).toBeNull();
    });
  });

  describe("isPluginTool", () => {
    it("returns true for plugin tools", () => {
      expect(isPluginTool("get-attention-items")).toBe(true);
    });

    it("returns false for core tools", () => {
      expect(isPluginTool("list-skills")).toBe(false);
    });
  });

  describe("isFallbackResponse", () => {
    it("detects fallback responses", () => {
      expect(
        isFallbackResponse({ _fallback: true, _reason: "tool_error", _plugin: null }),
      ).toBe(true);
    });

    it("rejects normal responses", () => {
      expect(isFallbackResponse({ data: [] })).toBe(false);
      expect(isFallbackResponse(null)).toBe(false);
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && npx jest tests/dashboard/lib/mcp/pluginFallback.test.ts --no-coverage 2>&1 | tail -5`
Expected: FAIL — module not found

- [ ] **Step 3: Implement pluginFallback**

```typescript
// apps/dashboard/lib/mcp/pluginFallback.ts

/**
 * Plugin tool detection and fallback utilities.
 *
 * Extracted from the proxy handler's PLUGIN_TOOL_SOURCES map.
 * Used by components that call plugin tools directly via mcpCall
 * to detect when a plugin is not installed and show appropriate UI.
 */

/** Maps MCP tool names to their owning plugin bundle. */
const PLUGIN_TOOL_SOURCES: Record<string, string> = {
  "get-attention-items": "attention",
  "get-attention-summary": "attention",
  "get-agent-telemetry": "advisor",
  "get-agent-weights": "advisor",
  "update-agent-weights": "advisor",
  "get-skill-health": "advisor",
  "verify-changes": "advisor",
  "get-daemon-status": "daemon",
  "insights-pending": "daemon",
  "plugin-events-list": "daemon",
  "plugin-events-acknowledge": "daemon",
  "scan-file-organizer": "organizer",
  "get-context-files": "file-manager",
  "manage-cli-agents": "ai_bridge",
  "manage-tools-catalog": "ai_bridge",
  "run-adaptive-growth": "devops",
  "generate-ide-instructions": "mcp-app-factory",
  "validate-agent-wizard": "mcp-app-factory",
  "unified-search": "knowledge",
  "knowledge-project-index-rebuild": "knowledge",
  "knowledge-summarize-url": "knowledge",
  "knowledge-summarize-file": "knowledge",
  "start-rag-indexing": "knowledge",
  "search-skill-knowledge": "rag",
  "check-system-permissions": "system-cleanup",
};

/** Returns the plugin name for a tool, or null if it's a core tool. */
export function pluginForTool(toolName: string): string | null {
  return PLUGIN_TOOL_SOURCES[toolName] ?? null;
}

/** Returns true if the tool belongs to an optional plugin. */
export function isPluginTool(toolName: string): boolean {
  return toolName in PLUGIN_TOOL_SOURCES;
}

/**
 * Type guard for fallback responses from mcpCall.
 * Note: this replaces the identical function in types.ts — remove it from
 * types.ts and re-export from here to avoid duplication.
 */
export function isFallbackResponse(
  data: unknown,
): data is {
  _fallback: true;
  _reason: string;
  _plugin: string | null;
  _error?: string;
} {
  return (
    typeof data === "object" &&
    data !== null &&
    "_fallback" in data &&
    (data as Record<string, unknown>)._fallback === true
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dashboard && npx jest tests/dashboard/lib/mcp/pluginFallback.test.ts --no-coverage 2>&1 | tail -10`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/mcp/pluginFallback.ts tests/dashboard/lib/mcp/pluginFallback.test.ts
git commit -m "feat(mcp): add pluginFallback utility for plugin tool detection"
```

---

## Task 4: Generate route migration map

**Files:**
- Create: `scripts/generate-route-map.ts`
- Create: `apps/dashboard/lib/mcp/route-map.json` (generated output)
- Reference: `apps/dashboard/app/api/[...proxy]/_routes-a.ts`, `_routes-b.ts`, `_routes-c.ts`

This task produces a JSON reference file that maps every proxy URL to its tool config. It is a migration aid — not production code. It will be deleted after all pages are migrated.

- [ ] **Step 1: Write the generation script**

The script uses regex extraction (not runtime imports) because the route files use Next.js `@/` path aliases that `tsx` can't resolve outside the Next.js build.

```python
#!/usr/bin/env python3
# scripts/generate_route_map.py
"""
One-time migration helper: parses _routes-{a,b,c}.ts via regex and emits a JSON map
of every proxy URL → { tool, staticArgs (if simple), hasTransform, hasExtract, hasFallback }.

Run: python3 scripts/generate_route_map.py
Output: apps/dashboard/lib/mcp/route-map.json
"""

import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
PROXY_DIR = PROJECT / "apps/dashboard/app/api/[...proxy]"

def extract_routes(content: str) -> dict:
    """Extract route entries from a _routes-*.ts file using regex."""
    routes = {}
    # Match top-level route keys: "some/url/path": {
    route_pattern = re.compile(r'"([^"]+)":\s*\{')
    # Match method blocks: GET: { or POST: {
    method_pattern = re.compile(r'(GET|POST|PUT|PATCH|DELETE):\s*\{')
    # Match toolName
    tool_pattern = re.compile(r'toolName:\s*"([^"]+)"')
    # Match staticArgs (simple cases: { key: "value" } or { key: true/false })
    static_args_pattern = re.compile(r'staticArgs:\s*\{([^}]+)\}')
    # Match feature flags
    has_transform = re.compile(r'transformResponse:')
    has_extract = re.compile(r'extractParams:')
    has_fallback = re.compile(r'fallback:')
    has_wrap = re.compile(r'wrapSuccess:\s*true')
    has_wrap_check = re.compile(r'wrapSuccessCheck:\s*true')

    # Split into route blocks by finding top-level keys
    # We use a state machine approach: track brace depth
    lines = content.split('\n')
    current_route = None
    current_method = None
    brace_depth = 0
    route_start_depth = 0
    method_block = []

    for line in lines:
        # Track route key
        route_match = route_pattern.search(line)
        if route_match and brace_depth <= 1:
            current_route = route_match.group(1)
            if current_route not in routes:
                routes[current_route] = {}

        # Track method
        method_match = method_pattern.search(line)
        if method_match and current_route:
            current_method = method_match.group(1)
            method_block = [line]
            route_start_depth = brace_depth

        if current_method:
            method_block.append(line)

        # Track brace depth
        brace_depth += line.count('{') - line.count('}')

        # When method block closes
        if current_method and brace_depth <= route_start_depth + 1 and '}' in line:
            block = '\n'.join(method_block)
            tool_match = tool_pattern.search(block)
            if tool_match and current_route:
                entry = {
                    "tool": tool_match.group(1),
                    "hasTransform": bool(has_transform.search(block)),
                    "hasExtract": bool(has_extract.search(block)),
                    "hasFallback": bool(has_fallback.search(block)),
                }
                if has_wrap.search(block):
                    entry["wrapSuccess"] = True
                if has_wrap_check.search(block):
                    entry["wrapSuccessCheck"] = True

                # Try to extract simple staticArgs
                static_match = static_args_pattern.search(block)
                if static_match:
                    args_str = static_match.group(1).strip()
                    # Parse simple key: "value" or key: true/false pairs
                    args = {}
                    for pair in re.finditer(r'(\w+):\s*(?:"([^"]+)"|(\btrue\b|\bfalse\b))', args_str):
                        key = pair.group(1)
                        args[key] = pair.group(2) if pair.group(2) else (pair.group(3) == "true")
                    if args:
                        entry["staticArgs"] = args

                routes[current_route][current_method] = entry
            current_method = None
            method_block = []

    return routes

def main():
    all_routes = {}
    for suffix in ("a", "b", "c"):
        path = PROXY_DIR / f"_routes-{suffix}.ts"
        content = path.read_text()
        routes = extract_routes(content)
        all_routes.update(routes)

    out_path = PROJECT / "apps/dashboard/lib/mcp/route-map.json"
    out_path.write_text(json.dumps(all_routes, indent=2))
    print(f"Wrote {len(all_routes)} routes to {out_path}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script**

Run: `python3 scripts/generate_route_map.py`
Expected: "Wrote 367 routes to apps/dashboard/lib/mcp/route-map.json"

- [ ] **Step 3: Verify the output contains expected entries**

Run: `python3 -c "import json; d=json.load(open('apps/dashboard/lib/mcp/route-map.json')); print(f'{len(d)} routes'); print(json.dumps(d.get('agents/recalculate',{}), indent=2))"`
Expected: Shows `{ "POST": { "tool": "update-agent-weights", "staticArgs": { "save": true }, ... } }`

- [ ] **Step 4: Commit**

```bash
git add scripts/generate_route_map.py apps/dashboard/lib/mcp/route-map.json
git commit -m "chore: generate route migration map from proxy config (temporary)"
```

---

## Task 5: Export PRESETS from useMcpQuery and deduplicate

**Files:**
- Modify: `apps/dashboard/lib/mcp/useMcpQuery.ts` — export the `PRESETS` constant
- Modify: `apps/dashboard/lib/mcp/useMcpPoll.ts` — import `PRESETS` instead of duplicating

`PresetName` is already exported from `useMcpQuery.ts` (line 19). But the `PRESETS` constant is not, and `useMcpPoll` (Task 2) duplicates it. Fix the duplication.

- [ ] **Step 1: Export PRESETS from useMcpQuery.ts**

Add `export` before the `const PRESETS` declaration in `useMcpQuery.ts` (line 32).

- [ ] **Step 2: Update useMcpPoll to import PRESETS**

Replace the duplicated `PRESETS` constant in `useMcpPoll.ts` with:
```typescript
import { PRESETS, type PresetName } from "./useMcpQuery";
```

Remove the local `PRESETS` declaration.

- [ ] **Step 3: Run tests for both hooks**

Run: `cd apps/dashboard && npx jest tests/dashboard/lib/mcp/ --no-coverage 2>&1 | tail -10`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/lib/mcp/useMcpQuery.ts apps/dashboard/lib/mcp/useMcpPoll.ts
git commit -m "refactor(mcp): export PRESETS from useMcpQuery, deduplicate in useMcpPoll"
```

---

## Task 6: Migrate life hub pages (template hub — 14 files)

**Files:**
- Modify: All `skills/dashboard/pages/life/**/*.tsx` files that import `useCachedFetch`, `useCachedPoll`, `useCachedMutation`, or `useAction`
- Reference: `apps/dashboard/lib/mcp/route-map.json` — look up each URL to find the tool name and args

This is the template hub migration. The pattern established here is repeated for all other hubs. The life hub is chosen because it has the most diverse patterns: polling (home-automation), mutations (eisenhower, finance), reads (recipes, lifestyle), and Google Workspace routes with `extractParams`.

**Pre-migration checklist:**

For each page file:
1. Find all `useCachedFetch(key, "/api/life/...", preset, opts)` calls
2. Look up the URL in `route-map.json` to find `{ tool, staticArgs?, hasTransform, ... }`
3. Replace with `useMcpQuery(key, tool, preset, { args: staticArgs, select: ... })`
4. For `useAction`/`useCachedMutation` calls: replace with `useMcpMutation(tool, { staticArgs, invalidates, select })`
5. For `useCachedPoll` calls: replace with `useMcpPoll(key, tool, intervalMs, { args, select, preset })`
6. If the route has `transformResponse`, move the transform body into the `select` option
7. If the route has `extractParams` with validation logic, move validation into the component (before calling `mutate`)
8. Update imports: remove `useCachedFetch` imports, add `useMcpQuery`/`useMcpMutation`/`useMcpPoll`

- [ ] **Step 1: List all life hub consumers**

Run: `grep -rl "useCachedFetch\|useCachedPoll\|useCachedMutation\|useAction" skills/dashboard/pages/life/ --include="*.tsx" | sort`

Record the list — each file gets migrated.

- [ ] **Step 2: Migrate each file**

For each file in the list, apply the migration patterns A-F from the reference section above. Use `route-map.json` to look up the tool name and args for each URL.

Example — `skills/dashboard/pages/life/home-automation/page.tsx`:
```tsx
// BEFORE
const { data: polledLights } = useCachedPoll<Light[]>(
  ["home", "lights"], "/api/life/home-automation/lights", 10_000,
  { preset: "device", select: (r: any) => r.lights ?? [] },
);

// AFTER
const { data: polledLights } = useMcpPoll<Light[]>(
  ["home", "lights"], "manage-hue-lights", 10_000,
  { args: { action: "list" }, preset: "device", select: (r: any) => r.lights ?? [] },
);
```

- [ ] **Step 3: Run dashboard build to verify no type errors**

Run: `cd apps/dashboard && npx next build 2>&1 | tail -20`
Expected: Build succeeds with no errors in life hub pages.

- [ ] **Step 4: Run existing dashboard tests**

Run: `cd apps/dashboard && npx jest --no-coverage 2>&1 | tail -10`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/dashboard/pages/life/
git commit -m "refactor(life): migrate life hub pages from useCachedFetch to useMcpQuery/useMcpMutation/useMcpPoll"
```

---

## Task 7: Migrate brain hub pages (~15 files)

**Files:**
- Modify: All `skills/dashboard/pages/brain/**/*.tsx` files using legacy hooks
- Reference: `apps/dashboard/lib/mcp/route-map.json`

Same pattern as Task 6. Brain hub includes RAG, knowledge, reading-list, scraper, and AI bridge pages.

- [ ] **Step 1: List brain hub consumers**

Run: `grep -rl "useCachedFetch\|useCachedPoll\|useCachedMutation\|useAction" skills/dashboard/pages/brain/ --include="*.tsx" | sort`

- [ ] **Step 2: Migrate each file using patterns A-F and route-map.json**

- [ ] **Step 3: Build verification**

Run: `cd apps/dashboard && npx next build 2>&1 | tail -20`

- [ ] **Step 4: Test verification**

Run: `cd apps/dashboard && npx jest --no-coverage 2>&1 | tail -10`

- [ ] **Step 5: Commit**

```bash
git add skills/dashboard/pages/brain/
git commit -m "refactor(brain): migrate brain hub pages from useCachedFetch to useMcpQuery/useMcpMutation"
```

---

## Task 8: Migrate career hub pages (~12 files)

**Files:**
- Modify: All `skills/dashboard/pages/career/**/*.tsx` files using legacy hooks
- Reference: `apps/dashboard/lib/mcp/route-map.json`

Career hub includes resume, venture, GTM, interview, learning, and SMB pages.

- [ ] **Step 1: List career hub consumers**

Run: `grep -rl "useCachedFetch\|useCachedPoll\|useCachedMutation\|useAction" skills/dashboard/pages/career/ --include="*.tsx" | sort`

- [ ] **Step 2: Migrate each file**

- [ ] **Step 3: Build verification**

- [ ] **Step 4: Test verification**

- [ ] **Step 5: Commit**

```bash
git add skills/dashboard/pages/career/
git commit -m "refactor(career): migrate career hub pages from useCachedFetch to useMcpQuery/useMcpMutation"
```

---

## Task 9: Migrate command hub pages (~12 files)

**Files:**
- Modify: All `skills/dashboard/pages/command/**/*.tsx` files using legacy hooks
- Reference: `apps/dashboard/lib/mcp/route-map.json`

Command hub includes daemon, updater, import, system-cleanup, and workflow pages.

- [ ] **Step 1: List command hub consumers**

Run: `grep -rl "useCachedFetch\|useCachedPoll\|useCachedMutation\|useAction" skills/dashboard/pages/command/ --include="*.tsx" | sort`

- [ ] **Step 2: Migrate each file**

- [ ] **Step 3: Build verification**

- [ ] **Step 4: Test verification**

- [ ] **Step 5: Commit**

```bash
git add skills/dashboard/pages/command/
git commit -m "refactor(command): migrate command hub pages from useCachedFetch to useMcpQuery/useMcpMutation"
```

---

## Task 10: Migrate studio hub pages (~10 files)

**Files:**
- Modify: All `skills/dashboard/pages/studio/**/*.tsx` files using legacy hooks
- Reference: `apps/dashboard/lib/mcp/route-map.json`

Studio hub includes factory, workbench, terminal, page-builder, and design pages.

- [ ] **Step 1: List studio hub consumers**

Run: `grep -rl "useCachedFetch\|useCachedPoll\|useCachedMutation\|useAction" skills/dashboard/pages/studio/ --include="*.tsx" | sort`

- [ ] **Step 2: Migrate each file**

- [ ] **Step 3: Build verification**

- [ ] **Step 4: Test verification**

- [ ] **Step 5: Commit**

```bash
git add skills/dashboard/pages/studio/
git commit -m "refactor(studio): migrate studio hub pages from useCachedFetch to useMcpQuery/useMcpMutation"
```

---

## Task 11: Migrate adaptive hub pages and shared components

**Files:**
- Modify: All `skills/dashboard/pages/adaptive/**/*.tsx` files using legacy hooks
- Modify: All `skills/dashboard/components/**/*.tsx` files using legacy hooks (shared components like `ActionButton`, `HelpRequestModal`, `FileEditor`, etc.)
- Modify: All `skills/dashboard/lib/**/*.tsx` files using legacy hooks (StatCards, DataTable, ActionButtons blocks)
- Reference: `apps/dashboard/lib/mcp/route-map.json`

- [ ] **Step 1: List all remaining consumers**

Run: `grep -rl "useCachedFetch\|useCachedPoll\|useCachedMutation\|useAction" skills/dashboard/ --include="*.tsx" | grep -v "pages/life\|pages/brain\|pages/career\|pages/command\|pages/studio" | sort`

- [ ] **Step 2: Migrate each file**

- [ ] **Step 3: Build verification**

- [ ] **Step 4: Test verification**

- [ ] **Step 5: Commit**

```bash
git add skills/dashboard/
git commit -m "refactor(adaptive+shared): migrate remaining skill components from useCachedFetch to useMcpQuery"
```

---

## Task 12: Migrate framework-level consumers in apps/dashboard/

**Files:**
- Modify: All `apps/dashboard/components/**/*.tsx` and `apps/dashboard/app/**/*.tsx` files using legacy hooks
- Reference: `apps/dashboard/lib/mcp/route-map.json`

These are the framework-level components (settings tabs, coverage, bridge, HubLandingPage, etc.) that still use `useCachedFetch`.

- [ ] **Step 1: List all framework consumers**

Run: `grep -rl "useCachedFetch\|useCachedPoll\|useCachedMutation\|useAction" apps/dashboard/components/ apps/dashboard/app/ --include="*.tsx" --include="*.ts" | grep -v "useCachedFetch.ts$" | sort`

Note: Include both `.tsx` and `.ts` files. Exclude `apps/dashboard/lib/hooks/useCachedFetch.ts` itself.

- [ ] **Step 2: Migrate each file**

- [ ] **Step 3: Build verification**

- [ ] **Step 4: Test verification**

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/components/ apps/dashboard/app/
git commit -m "refactor(framework): migrate framework components from useCachedFetch to useMcpQuery"
```

---

## Task 13: Delete proxy route layer

**Files:**
- Delete: `apps/dashboard/app/api/[...proxy]/` (entire directory — `route.ts`, `_routes-{a,b,c}.ts`, `_handler.ts`, `_helpers.ts`, `_dynamic.ts`, `_types.ts`)
- Delete: `apps/dashboard/lib/hooks/useCachedFetch.ts`
- Delete: `scripts/generate_route_map.py`
- Delete: `apps/dashboard/lib/mcp/route-map.json`

- [ ] **Step 1: Verify zero remaining consumers of useCachedFetch**

Run: `grep -rl "useCachedFetch\|useCachedPoll\|useCachedMutation\|from.*useCachedFetch" apps/dashboard/ skills/dashboard/ --include="*.tsx" --include="*.ts" | grep -v "useCachedFetch.ts$" | grep -v "test" | grep -v "node_modules"`
Expected: No results (all consumers migrated).

- [ ] **Step 2: Delete all proxy route files (including the catch-all entry point)**

Per CLAUDE.md Rule 14: "Break compatibility, do cleanup — do not add backward-compatibility stubs." The catch-all `route.ts` is deleted entirely, not replaced with a 410 stub.

```bash
rm -r apps/dashboard/app/api/\[...proxy\]/
```

- [ ] **Step 3: Delete legacy hooks file**

First verify `useCachedSearch` has zero consumers:

Run: `grep -rl "useCachedSearch" apps/dashboard/ skills/dashboard/ --include="*.tsx" --include="*.ts" | grep -v "useCachedFetch.ts$"`
Expected: No results.

```bash
rm apps/dashboard/lib/hooks/useCachedFetch.ts
```

- [ ] **Step 4: Delete migration artifacts**

```bash
rm scripts/generate_route_map.py
rm apps/dashboard/lib/mcp/route-map.json
```

- [ ] **Step 5: Build verification**

Run: `cd apps/dashboard && npx next build 2>&1 | tail -20`
Expected: Build succeeds. No import errors.

- [ ] **Step 6: Test verification**

Run: `cd apps/dashboard && npx jest --no-coverage 2>&1 | tail -10`
Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(proxy): delete 6,700-line proxy route layer — all pages now use direct MCP calls"
```

---

## Task 14: Update documentation and CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` — remove any references to proxy route architecture, update Rule 11 if needed
- Modify: `docs/agent-topics/DASHBOARD.md` — update data fetching patterns documentation
- Modify: `docs/agent-topics/ARCHITECTURE.md` — update API architecture section

- [ ] **Step 1: Update CLAUDE.md**

Remove or update any references to `/api/[...proxy]`, `_routes-*.ts`, or the proxy handler. Rule 11 ("MCP-first API") still applies but the mechanism changed — API routes call MCP tools via `callMCPTool`, and pages call MCP tools via `mcpCall`/`useMcpQuery` directly.

- [ ] **Step 2: Update DASHBOARD.md data fetching section**

Document the three hooks:
- `useMcpQuery` — reads (GET-style data fetching)
- `useMcpMutation` — writes (mutations with cache invalidation)
- `useMcpPoll` — polling (interval-based refetch)

And the low-level `mcpCall` for imperative calls.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md docs/agent-topics/
git commit -m "docs: update data fetching docs to reflect proxy route elimination"
```
