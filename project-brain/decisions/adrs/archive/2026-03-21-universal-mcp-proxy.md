# Universal MCP Proxy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 461 individual API route files with a single universal MCP proxy, making the dashboard a dumb passthrough to MCP tools.

**Architecture:** Extend the existing `api/mcp/tool/route.ts` with GET support. Create a `mcpCall()` client helper that all components use instead of ad-hoc `fetch()`. Delete all proxy route files. MCP tools own param validation and response shaping.

**Tech Stack:** Next.js App Router, TypeScript, MCP protocol (stdio), Python MCP tools

**Spec:** `docs/superpowers/specs/2026-03-21-universal-mcp-proxy-design.md`

---

## File Structure

| File | Responsibility | Action |
|------|---------------|--------|
| `apps/dashboard/app/api/mcp/tool/route.ts` | Universal MCP proxy (POST + GET) | Modify |
| `apps/dashboard/lib/mcp/client.ts` | Client helper `mcpCall()` with fallback support | Create |
| `apps/dashboard/lib/mcp/createAPIRoute.ts` | Legacy route factory (454 lines) | Delete (phase 4) |
| `apps/dashboard/lib/mcp/plugin-tool-sources.ts` | Legacy tool source mapping | Delete (phase 4) |
| `apps/dashboard/scripts/mount-plugins.ts` | Plugin mounting — remove API route copying | Modify (phase 3) |
| `apps/dashboard/app/api/**/*.ts` | ~439 proxy route files | Delete (phase 3) |
| `.claude/skills/*/augur/api/**` | ~253 plugin API source files | Delete (phase 3) |
| `plugins/ui/pages/*/api/**` | ~3 plugin API source files | Delete (phase 3) |
| 137 client files | Migrate `fetch('/api/...')` to `mcpCall()` | Modify (phase 2) |

---

## Phase 1: Foundation (universal proxy + client helper)

### Task 1: Add GET handler to universal proxy

**Files:**
- Modify: `apps/dashboard/app/api/mcp/tool/route.ts`
- Test: `apps/dashboard/__tests__/api/mcp-tool-route.test.ts`

- [ ] **Step 1: Write failing test for GET handler**

```typescript
// apps/dashboard/__tests__/api/mcp-tool-route.test.ts
import { GET, POST } from "@/app/api/mcp/tool/route";

// Mock callMCPTool
jest.mock("@/lib/mcp/MCPBridge", () => ({
  callMCPTool: jest.fn().mockResolvedValue({
    isError: false,
    content: [{ type: "text", text: JSON.stringify({ count: 42 }) }],
  }),
  extractContextFromRequest: jest.fn().mockReturnValue({}),
  MCPBridge: {
    extractText: jest.fn((r) => r.content?.[0]?.text ?? ""),
  },
}));

describe("GET /api/mcp/tool", () => {
  it("calls MCP tool with query params", async () => {
    const { callMCPTool } = require("@/lib/mcp/MCPBridge");
    const req = new Request("http://localhost/api/mcp/tool?tool=get-count&limit=10");
    const res = await GET(req);
    const body = await res.json();

    expect(callMCPTool).toHaveBeenCalledWith("get-count", { limit: "10" }, {});
    expect(body.count).toBe(42);
  });

  it("returns 400 when tool param is missing", async () => {
    const req = new Request("http://localhost/api/mcp/tool?limit=10");
    const res = await GET(req);
    expect(res.status).toBe(400);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && npx jest __tests__/api/mcp-tool-route.test.ts --no-cache`
Expected: FAIL — `GET is not exported`

- [ ] **Step 3: Implement GET handler**

Add to `apps/dashboard/app/api/mcp/tool/route.ts`:

```typescript
export async function GET(req: Request) {
  try {
    const url = new URL(req.url);
    const tool = url.searchParams.get("tool");
    if (!tool || tool.trim().length === 0) {
      return NextResponse.json(
        { error: "`tool` query parameter is required" },
        { status: 400 },
      );
    }

    // Collect remaining params (exclude "tool")
    const args: Record<string, string> = {};
    for (const [key, value] of url.searchParams.entries()) {
      if (key !== "tool") args[key] = value;
    }

    const mcpContext = extractContextFromRequest(req);
    const result = await callMCPTool(tool.trim(), args, mcpContext);

    if (result.isError) {
      return NextResponse.json(
        { error: MCPBridge.extractText(result) || `MCP tool failed: ${tool}` },
        { status: 500 },
      );
    }

    const raw = MCPBridge.extractText(result).trim();
    if (!raw) return NextResponse.json({});

    try {
      return NextResponse.json(JSON.parse(raw));
    } catch {
      return NextResponse.json({ result: raw });
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to call MCP tool";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dashboard && npx jest __tests__/api/mcp-tool-route.test.ts --no-cache`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/app/api/mcp/tool/route.ts apps/dashboard/__tests__/api/mcp-tool-route.test.ts
git commit -m "feat(mcp-proxy): add GET handler to universal MCP tool route"
```

---

### Task 2: Create mcpCall client helper

**Files:**
- Create: `apps/dashboard/lib/mcp/client.ts`
- Test: `apps/dashboard/__tests__/lib/mcp-client.test.ts`

- [ ] **Step 1: Write failing test**

```typescript
// apps/dashboard/__tests__/lib/mcp-client.test.ts
import { mcpCall } from "@/lib/mcp/client";

// Mock global fetch
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("mcpCall", () => {
  beforeEach(() => mockFetch.mockReset());

  it("calls /api/mcp/tool with tool and args", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ count: 42 }),
    });

    const result = await mcpCall("get-count", { limit: 10 });
    expect(result).toEqual({ count: 42 });
    expect(mockFetch).toHaveBeenCalledWith("/api/mcp/tool", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tool: "get-count", args: { limit: 10 } }),
      signal: undefined,
    });
  });

  it("throws on error response when no fallback", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: "tool failed" }),
    });

    await expect(mcpCall("bad-tool")).rejects.toThrow("tool failed");
  });

  it("returns fallback on error when fallback provided", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: "tool failed" }),
    });

    const result = await mcpCall("bad-tool", {}, { fallback: { data: null } });
    expect(result).toEqual({ data: null });
  });

  it("passes abort signal", async () => {
    const controller = new AbortController();
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });

    await mcpCall("tool", {}, { signal: controller.signal });
    expect(mockFetch.mock.calls[0][1].signal).toBe(controller.signal);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && npx jest __tests__/lib/mcp-client.test.ts --no-cache`
Expected: FAIL — `Cannot find module '@/lib/mcp/client'`

- [ ] **Step 3: Implement mcpCall**

```typescript
// apps/dashboard/lib/mcp/client.ts

/**
 * Universal MCP tool caller for dashboard client code.
 *
 * Replaces all ad-hoc fetch('/api/...') calls with a single function
 * that routes through the universal MCP proxy at /api/mcp/tool.
 */

export interface McpCallOptions {
  /** Return this value instead of throwing on MCP errors */
  fallback?: unknown;
  /** AbortController signal for cancellation */
  signal?: AbortSignal;
}

/**
 * Call an MCP tool through the universal proxy.
 *
 * @param tool - MCP tool name (e.g., "get-career-job-counts")
 * @param args - Tool arguments (forwarded as-is to MCP)
 * @param options - Fallback and signal options
 * @returns Parsed JSON response from MCP tool
 * @throws Error with MCP error message (unless fallback is provided)
 */
export async function mcpCall<T = unknown>(
  tool: string,
  args: Record<string, unknown> = {},
  options: McpCallOptions = {},
): Promise<T> {
  const { fallback, signal } = options;

  const res = await fetch("/api/mcp/tool", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool, args }),
    signal,
  });

  if (!res.ok) {
    if (fallback !== undefined) return fallback as T;
    const body = await res.json().catch(() => ({ error: `MCP call failed (${res.status})` }));
    throw new Error(body.error || `MCP tool "${tool}" failed`);
  }

  return res.json() as Promise<T>;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dashboard && npx jest __tests__/lib/mcp-client.test.ts --no-cache`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/mcp/client.ts apps/dashboard/__tests__/lib/mcp-client.test.ts
git commit -m "feat(mcp-proxy): add mcpCall client helper with fallback support"
```

---

## Phase 2: Client Migration

### Task 3: Generate tool name mapping

Before migrating clients, build a mapping of old URL paths to MCP tool names. This is a one-time script, not committed — it generates the migration reference.

**Files:**
- Create (temp): `scripts/generate-route-tool-map.sh`

- [ ] **Step 1: Generate the mapping**

```bash
# Run from project root — extracts URL path → tool name from all createAPIRoute files
grep -rl "createAPIRoute\|callMCPTool" apps/dashboard/app --include="route.ts" | while read f; do
  rel="${f#apps/dashboard/app/}"
  path="/${rel%/route.ts}"
  tool=$(grep -oP "toolName:\s*'\"['\"]" "$f" | head -1 | grep -oP "'\"['\"]" | tr -d "'" | tr -d '"')
  [ -n "$tool" ] && echo "$path -> $tool"
done | sort > /tmp/route-tool-map.txt
```

- [ ] **Step 2: Review the mapping**

Run: `wc -l /tmp/route-tool-map.txt && head -20 /tmp/route-tool-map.txt`
Expected: ~420 lines, each showing `/api/path -> tool-name`

- [ ] **Step 3: No commit — this is a reference artifact**

---

### Task 4: Migrate client files (batch by hub)

This is the largest task. Migrate 137 client files from `fetch('/api/...')` to `mcpCall()`. Work hub-by-hub.

**Strategy for each file:**
1. Find every `fetch('/api/...')` call
2. Look up the tool name in `/tmp/route-tool-map.txt`
3. Replace with `mcpCall(toolName, args)` or `mcpCall(toolName, args, { fallback })` if the route had `gracefulFallback`
4. Add `import { mcpCall } from "@/lib/mcp/client"` at the top
5. If the file destructures the response differently than raw MCP output, adjust the destructuring

- [ ] **Step 1: Migrate adaptive hub clients**

Find: `grep -rl "fetch.*'/api/adaptive\|fetch.*\"/api/adaptive" apps/dashboard --include="*.ts" --include="*.tsx" | grep -v route.ts`

For each file: replace `fetch('/api/adaptive/...')` with `mcpCall('tool-name', args)`.

- [ ] **Step 2: Migrate brain hub clients**

Find: `grep -rl "fetch.*'/api/brain\|fetch.*\"/api/brain" apps/dashboard --include="*.ts" --include="*.tsx" | grep -v route.ts`

- [ ] **Step 3: Migrate career hub clients**

Find: `grep -rl "fetch.*'/api/career\|fetch.*\"/api/career" apps/dashboard --include="*.ts" --include="*.tsx" | grep -v route.ts`

- [ ] **Step 4: Migrate command hub clients**

Find: `grep -rl "fetch.*'/api/command\|fetch.*\"/api/command" apps/dashboard --include="*.ts" --include="*.tsx" | grep -v route.ts`

- [ ] **Step 5: Migrate life hub clients**

Find: `grep -rl "fetch.*'/api/life\|fetch.*\"/api/life" apps/dashboard --include="*.ts" --include="*.tsx" | grep -v route.ts`

- [ ] **Step 6: Migrate studio hub clients**

Find: `grep -rl "fetch.*'/api/studio\|fetch.*\"/api/studio" apps/dashboard --include="*.ts" --include="*.tsx" | grep -v route.ts`

- [ ] **Step 7: Migrate core/shared clients (api/mcp, api/settings, api/blocks, etc.)**

Find: `grep -rl "fetch.*'/api/\|fetch.*\"/api/" apps/dashboard --include="*.ts" --include="*.tsx" | grep -v route.ts | grep -v "api/auth\|api/csrf\|api/llm"` (exclude routes that stay)

- [ ] **Step 8: Skip files that call "keep" routes**

Do NOT migrate fetch calls to these routes (they stay as individual files):
- `/api/auth/*`, `/api/csrf/*` — auth routes
- `/api/llm` — LLM proxy
- `/api/mcp/tool` — the universal proxy itself
- Any route in the "Routes That Stay" list from the spec

- [ ] **Step 9: Verify no remaining proxy fetch calls**

```bash
# Should return only calls to "keep" routes (auth, llm, etc.)
grep -rn "fetch.*'/api/\|fetch.*\"/api/" apps/dashboard --include="*.ts" --include="*.tsx" | grep -v route.ts | grep -v node_modules | grep -v ".next" | grep -v "api/auth\|api/csrf\|api/llm\|api/mcp/tool"
```

Expected: Zero results (or only calls to routes in the "keep" list)

- [ ] **Step 10: Run dashboard build to verify no TypeScript errors**

Run: `cd apps/dashboard && npx next build 2>&1 | tail -20`
Expected: Build succeeds

- [ ] **Step 11: Commit**

```bash
git add -A apps/dashboard
git commit -m "refactor(mcp-proxy): migrate 137 client files from fetch to mcpCall"
```

---

## Phase 3: Route Deletion

### Task 5: Delete proxy route files from app/api/

**Files:**
- Delete: ~439 `route.ts` files (420 proxy + 19 moved-to-MCP)
- Keep: ~22 routes listed in spec "Routes That Stay"

- [ ] **Step 1: Build the keep-list**

```bash
# Routes that must NOT be deleted — copy this to /tmp/keep-routes.txt
cat > /tmp/keep-routes.txt << 'EOF'
api/auth/login/route.ts
api/auth/logout/route.ts
api/auth/session/route.ts
api/csrf/token/route.ts
api/files/git-status/route.ts
api/remote/auth/start/[provider]/route.ts
api/settings/layout/pulse/route.ts
api/studio/terminal-automation-template/terminal/execute/route.ts
api/life/apple/notes/events/route.ts
api/life/google-workspace/install/route.ts
api/llm/route.ts
api/agents/available/route.ts
api/agents/wizard/create/route.ts
api/agents/onboarding/validate/[step]/route.ts
api/mcp/tool/route.ts
api/mcp/capabilities/route.ts
api/brain/dev-sync/sync-status/route.ts
api/brain/dev-sync/client-skills/route.ts
api/brain/knowledge/ocr/route.ts
api/career/linkedin-writer/posts/route.ts
api/career/smb-client-template/content-pipeline/posts/route.ts
api/career/smb-client-template/content-pipeline/refine-instructions/route.ts
EOF
```

- [ ] **Step 2: Delete all route files NOT in the keep-list**

```bash
cd apps/dashboard/app
find . -name "route.ts" -path "*/api/*" | while read f; do
  rel="${f#./}"
  if ! grep -qF "$rel" /tmp/keep-routes.txt; then
    rm "$f"
    echo "Deleted: $rel"
  fi
done
```

- [ ] **Step 3: Clean up empty directories**

```bash
cd apps/dashboard/app
find api -type d -empty -delete
```

- [ ] **Step 4: Verify keep-list routes still exist**

```bash
cd apps/dashboard/app
while read route; do
  [ -f "$route" ] && echo "OK: $route" || echo "MISSING: $route"
done < /tmp/keep-routes.txt
```

Expected: All routes show "OK"

- [ ] **Step 5: Count remaining routes**

```bash
find apps/dashboard/app -name "route.ts" -path "*/api/*" | wc -l
```

Expected: ~22

- [ ] **Step 6: Commit**

```bash
git add -A apps/dashboard/app/api
git commit -m "refactor(mcp-proxy): delete 439 proxy route files"
```

---

### Task 6: Delete plugin API source files

**Files:**
- Delete: all `augur/api/` directories in `.claude/skills/`
- Delete: API route sources in `plugins/ui/pages/`

- [ ] **Step 1: Delete plugin API sources**

```bash
# Delete augur/api/ directories from all skills
find .claude/skills -type d -name "api" -path "*/augur/api" | while read d; do
  echo "Deleting: $d"
  rm -rf "$d"
done

# Delete API routes from plugins/ui/pages
find plugins/ui/pages -name "route.ts" -path "*/api/*" -delete
find plugins/ui/pages -type d -name "api" -empty -delete
```

- [ ] **Step 2: Verify no plugin API sources remain**

```bash
find .claude/skills -path "*/augur/api/*/route.ts" | wc -l
find plugins/ui/pages -name "route.ts" -path "*/api/*" | wc -l
```

Expected: 0 for both

- [ ] **Step 3: Commit**

```bash
git add -A .claude/skills plugins/ui
git commit -m "refactor(mcp-proxy): delete plugin API source files"
```

---

### Task 7: Update mount-plugins to skip API route mounting

**Files:**
- Modify: `apps/dashboard/scripts/mount-plugins.ts`

- [ ] **Step 1: Read mount-plugins.ts and find API route mounting logic**

Search for the section that copies `api/` directories. Look for `mountSinglePlugin`, `api` path references, and the copier logic.

- [ ] **Step 2: Remove or skip API route mounting**

In the mounting function, add a check to skip files under `api/` directories. The simplest approach: if the source path contains `/api/`, skip the copy.

- [ ] **Step 3: Run mount-plugins to verify it works**

```bash
cd apps/dashboard && node scripts/dist/mount-plugins.mjs
```

Expected: No API route files copied, page files still mounted correctly.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/scripts/mount-plugins.ts
git commit -m "refactor(mount-plugins): stop copying API route files from plugins"
```

---

## Phase 4: Cleanup

### Task 8: Delete createAPIRoute and related helpers

**Files:**
- Delete: `apps/dashboard/lib/mcp/createAPIRoute.ts`
- Delete: `apps/dashboard/lib/mcp/plugin-tool-sources.ts` (if unused after deletion)
- Modify: any remaining imports of these files

- [ ] **Step 1: Check for remaining imports**

```bash
grep -rl "createAPIRoute\|createCRUDRoutes\|plugin-tool-sources" apps/dashboard --include="*.ts" --include="*.tsx" | grep -v node_modules | grep -v ".next"
```

Expected: Zero results (all consumers deleted in phase 3)

- [ ] **Step 2: Delete the files**

```bash
rm apps/dashboard/lib/mcp/createAPIRoute.ts
rm apps/dashboard/lib/mcp/plugin-tool-sources.ts 2>/dev/null
```

- [ ] **Step 3: Run build to verify nothing breaks**

```bash
cd apps/dashboard && npx next build 2>&1 | tail -20
```

Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add -A apps/dashboard/lib/mcp
git commit -m "refactor(mcp-proxy): delete createAPIRoute and related helpers"
```

---

### Task 9: Final verification

- [ ] **Step 1: Count final route files**

```bash
find apps/dashboard/app -name "route.ts" -path "*/api/*" | wc -l
```

Expected: ~22

- [ ] **Step 2: Count Turbopack entry points**

```bash
echo "Routes:" && find apps/dashboard/app -name "route.ts" | wc -l
echo "Pages:" && find apps/dashboard/app -name "page.tsx" | wc -l
echo "Total entry points:" && echo $(( $(find apps/dashboard/app -name "route.ts" | wc -l) + $(find apps/dashboard/app -name "page.tsx" | wc -l) ))
```

Expected: ~151 total (22 routes + 129 pages)

- [ ] **Step 3: Start dashboard and verify health**

Run: `/dev-build`
Wait for healthy state, then:
```bash
curl -s http://localhost:3000/api/mcp/tool?tool=health | python3 -m json.tool
```

Expected: MCP health response with no errors

- [ ] **Step 4: Run auto-test-api**

Run: `/auto-test-api`
Expected: All remaining API routes respond correctly

- [ ] **Step 5: Run auto-test-pages**

Run: `/auto-test-pages`
Expected: All dashboard pages render without errors

- [ ] **Step 6: Check Turbopack cache size after clean build**

```bash
du -sh ~/Library/Caches/Augur/dashboard/next
```

Expected: Significantly smaller than 600MB (target: ~150MB)

- [ ] **Step 7: Final commit**

```bash
git commit --allow-empty -m "verify(mcp-proxy): universal MCP proxy migration complete — 461→22 routes"
```
