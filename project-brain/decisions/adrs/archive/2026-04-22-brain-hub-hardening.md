# Brain Hub Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Brain hub buttons and displayed data trustworthy, then promote only staged Brain surfaces that pass the survival gate.

**Architecture:** Backend MCP tools expose explicit source/freshness/success data. Dashboard Brain pages consume those contracts through shared helpers and visible operation state. Staged Agent Control Center and Brain Harness are promoted as flat Brain pages only after wiring, tests, registry generation, and browser verification.

**Tech Stack:** Python 3.11 MCP tools, Next.js/React dashboard, React Query MCP hooks, Jest/jsdom, Playwright visual checks, pnpm, uv, dashboard lifecycle gate.

---

## File Structure

Backend contracts:

- Modify `skills/knowledge/scripts/mcp/tools_memory_dashboard.py`
  - Add reusable source metadata helpers.
  - Include source/freshness fields in `knowledge-memory-read`, `knowledge-memory-daily-logs`, and `knowledge-memory-daily-logs-read`.
- Modify `skills/knowledge/scripts/mcp/tools_memory_profile.py`
  - Accept structured dashboard profile updates.
  - Write `HUMAN_API.md` with frontmatter via `write_frontmatter()`.
- Modify `skills/knowledge/augur/tests/test_tools_memory_dashboard.py`
  - Add module-level tests for source metadata and daily log payloads.
- Modify `skills/knowledge/augur/tests/test_tools_memory_profile.py`
  - Add tests for structured profile writes and readback.

Dashboard shared contracts:

- Create `apps/dashboard/features/pages/brain/memory/contracts.ts`
  - Normalize MCP success/failure payloads.
  - Format source/freshness labels.
  - Build user-facing operation notices.
- Modify `apps/dashboard/features/pages/brain/memory/types.ts`
  - Add source/freshness and operation notice types.
- Modify `apps/dashboard/features/pages/brain/memory/hooks.ts`
  - Remove fallback data for primary Brain calls.
  - Add action success/error state to memory, profile, workspace, daily logs, and search hooks.
- Create `tests/dashboard/features/pages/brain/memory/contracts.test.ts`
  - Cover failure detection and freshness formatting.
- Create `tests/dashboard/features/pages/brain/memory/hooks.test.tsx`
  - Cover success/error behavior for profile, workspace, daily logs, and search hooks.

Live page UX:

- Modify `apps/dashboard/features/pages/brain/memory/page.tsx`
- Modify `apps/dashboard/features/pages/brain/search/page.tsx`
- Modify `apps/dashboard/features/pages/brain/daily-logs/page.tsx`
- Modify `apps/dashboard/features/pages/brain/profile/page.tsx`
- Modify `apps/dashboard/features/pages/brain/workspace/page.tsx`
- Modify `apps/dashboard/features/pages/brain/memory/components/MemorySearchWidget.tsx`
- Modify `apps/dashboard/features/pages/brain/memory/components/DailyLogsCalendar.tsx`
- Modify `apps/dashboard/features/pages/brain/memory/components/HumanApiProfile.tsx`
- Modify `apps/dashboard/features/pages/brain/memory/components/HumanReportPreview.tsx`
- Modify `apps/dashboard/features/pages/brain/memory/components/MemoryWorkspacePanel.tsx`
- Modify `apps/dashboard/features/pages/brain/memory/components/WikiMaintenancePanel.tsx`
- Add focused tests under `tests/dashboard/features/pages/brain/memory/components/`.

Staged survival and promotion:

- Create `apps/dashboard/features/pages/brain/agents/page.tsx`
- Create `apps/dashboard/features/pages/brain/agents/control-state.ts`
- Create `apps/dashboard/features/pages/brain/harness/page.tsx`
- Copy and adapt tests from:
  - `staging/r3/pages/tests/dashboard/features/pages/brain/ai/agents/control-state.test.ts`
  - `staging/r3/pages/tests/dashboard/features/pages/brain/harness-page.test.tsx`
- Modify `skills/ai/SKILL.md`
  - Add `/brain/agents` dashboard page and page contribution.
- Modify `skills/knowledge/SKILL.md`
  - Add `/brain/harness` dashboard page and page contribution.
- Modify tab and registry tests that assert Brain routes:
  - `tests/dashboard/lib/generate-tab-registry.test.ts`
  - `tests/dashboard/scripts/generate-registry.test.ts`
  - `tests/unit/test_staged_skill_catalog.py`
- Create `docs/references/brain-hub-staged-surface-audit.md`
  - Record promote/rework/do-not-promote decisions for staged Brain surfaces.

Verification:

- Run Python unit tests for memory MCP tools.
- Run focused dashboard Jest tests.
- Run `pnpm --dir apps/dashboard run mount-plugins`.
- Run `pnpm --dir apps/dashboard run generate-tabs`.
- Use `/dev-build` for production build verification.
- Use `skills/daemon/scripts/dashboard_lifecycle.py request-action` before browser verification.
- Browser-check `/brain/memory`, `/brain/search`, `/brain/daily-logs`, `/brain/profile`, `/brain/workspace`, `/brain/agents`, and `/brain/harness` on the actual worktree-owned dashboard port.

---

### Task 1: Backend MCP Data Contracts

**Files:**

- Modify: `skills/knowledge/scripts/mcp/tools_memory_dashboard.py`
- Modify: `skills/knowledge/scripts/mcp/tools_memory_profile.py`
- Test: `skills/knowledge/augur/tests/test_tools_memory_dashboard.py`
- Test: `skills/knowledge/augur/tests/test_tools_memory_profile.py`

- [ ] **Step 1: Add failing tests for memory source metadata**

Append to `skills/knowledge/augur/tests/test_tools_memory_dashboard.py`:

```python
def test_build_source_metadata_for_existing_file(tmp_path):
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")
    source = tmp_path / "MEMORY.md"
    source.write_text("| Date | Client | Type | Name | Description |\n", encoding="utf-8")

    metadata = mod._build_source_metadata(source, label="Curated memory", kind="file")

    assert metadata["label"] == "Curated memory"
    assert metadata["kind"] == "file"
    assert metadata["exists"] is True
    assert metadata["path"] == str(source)
    assert metadata["modifiedAt"]
    assert metadata["sizeBytes"] > 0


def test_build_source_metadata_for_missing_file(tmp_path):
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")
    source = tmp_path / "missing.md"

    metadata = mod._build_source_metadata(source, label="Missing source", kind="file")

    assert metadata == {
        "label": "Missing source",
        "kind": "file",
        "path": str(source),
        "exists": False,
        "modifiedAt": None,
        "sizeBytes": None,
    }
```

- [ ] **Step 2: Run the memory dashboard test and verify failure**

Run:

```bash
uv run pytest skills/knowledge/augur/tests/test_tools_memory_dashboard.py -q
```

Expected: FAIL with `AttributeError: module 'skills.knowledge.scripts.mcp.tools_memory_dashboard' has no attribute '_build_source_metadata'`.

- [ ] **Step 3: Implement source metadata helpers**

Add near the top of `skills/knowledge/scripts/mcp/tools_memory_dashboard.py`, after `_CATEGORY_META`:

```python
def _iso_mtime(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _path_size(path: Path) -> int | None:
    if not path.exists():
        return None
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
    return None


def _build_source_metadata(path: Path, *, label: str, kind: str) -> dict[str, Any]:
    return {
        "label": label,
        "kind": kind,
        "path": str(path),
        "exists": path.exists(),
        "modifiedAt": _iso_mtime(path),
        "sizeBytes": _path_size(path),
    }
```

- [ ] **Step 4: Add source fields to memory read payloads**

In `knowledge_memory_read_tool()`, create these paths after `runtime_mem_dir` is assigned:

```python
memory_file = mem_dir / "MEMORY.md"
index_file = mem_dir / "index.yaml"
daily_dir = runtime_mem_dir / "daily"
profile_file = runtime_mem_dir / "HUMAN_API.md"
```

Replace the local `memory_file = mem_dir / "MEMORY.md"` assignment inside the stats block with the existing `memory_file` variable.

Add this helper inside `knowledge_memory_read_tool()` after `_get_report()`:

```python
def _get_sources() -> dict[str, Any]:
    return {
        "memory": _build_source_metadata(memory_file, label="Curated memory", kind="file"),
        "index": _build_source_metadata(index_file, label="Memory index", kind="file"),
        "daily": _build_source_metadata(daily_dir, label="Daily logs", kind="directory"),
        "profile": _build_source_metadata(profile_file, label="Human API profile", kind="file"),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
```

Update mode returns:

```python
if mode == "stats":
    return json.dumps({"stats": _get_stats(), "sources": _get_sources()}, default=str)
if mode == "categories":
    return json.dumps({"categories": _build_categories(type_counts), "sources": _get_sources()}, default=str)
if mode == "workspace":
    return json.dumps({"workspace": _get_workspace(), "sources": _get_sources()}, default=str)
if mode == "report":
    return json.dumps({"report": _get_report(), "sources": _get_sources()}, default=str)
```

Update bootstrap return:

```python
return json.dumps({
    "stats": stats,
    "categories": _build_categories(type_counts),
    "workspace": _get_workspace(),
    "report": _get_report(),
    "sources": _get_sources(),
}, default=str)
```

- [ ] **Step 5: Add source fields to daily log tools**

In `knowledge_memory_daily_logs_tool()`, after `logs = await asyncio.to_thread(_list_daily_logs)`, return:

```python
return json.dumps(
    {
        "logs": logs,
        "source": {
            "label": "Git commit history",
            "kind": "git-log",
            "path": str(project_root),
            "exists": project_root.exists(),
            "modifiedAt": datetime.now(timezone.utc).isoformat(),
        },
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    },
    indent=2,
    default=str,
)
```

In `knowledge_memory_daily_logs_read_tool()`, after `result = await asyncio.to_thread(_read_daily_log, date)`, add:

```python
result["source"] = {
    "label": "Git commit history",
    "kind": "git-log",
    "path": str(project_root),
    "exists": project_root.exists(),
    "modifiedAt": datetime.now(timezone.utc).isoformat(),
}
result["generatedAt"] = datetime.now(timezone.utc).isoformat()
return json.dumps(result, indent=2, default=str)
```

- [ ] **Step 6: Add failing tests for structured profile writes**

Append to `skills/knowledge/augur/tests/test_tools_memory_profile.py`:

```python
def test_profile_payload_to_markdown_preserves_frontmatter_shape():
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_profile")
    content = mod._profile_payload_to_markdown({
        "role": "Engineer",
        "expertise": ["Python", "TypeScript"],
        "communicationStyle": "Direct",
        "successCriteria": ["Verified changes"],
        "contextGaps": ["Ask about deployment"],
    })

    assert content.startswith("---\n")
    assert "role: Engineer" in content
    assert "expertise:" in content
    assert "communicationStyle: Direct" in content
    assert "# Human API Profile" in content
    assert "- Verified changes" in content
```

- [ ] **Step 7: Run the profile test and verify failure**

Run:

```bash
uv run pytest skills/knowledge/augur/tests/test_tools_memory_profile.py -q
```

Expected: FAIL with `AttributeError` for `_profile_payload_to_markdown`.

- [ ] **Step 8: Implement structured profile serialization**

In `skills/knowledge/scripts/mcp/tools_memory_profile.py`, add imports:

```python
from src.lib.frontmatter_utils import write_frontmatter
```

Add this helper near the module logger:

```python
def _profile_payload_to_markdown(payload: dict[str, Any]) -> str:
    metadata = {
        "role": str(payload.get("role") or ""),
        "expertise": list(payload.get("expertise") or []),
        "communicationStyle": str(payload.get("communicationStyle") or ""),
        "successCriteria": list(payload.get("successCriteria") or []),
        "contextGaps": list(payload.get("contextGaps") or []),
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
    }
    body_lines = [
        "# Human API Profile",
        "",
        "## Role",
        metadata["role"] or "Not specified",
        "",
        "## Expertise",
        *(f"- {item}" for item in metadata["expertise"]),
        "",
        "## Communication Style",
        metadata["communicationStyle"] or "Not specified",
        "",
        "## Success Criteria",
        *(f"- {item}" for item in metadata["successCriteria"]),
        "",
        "## Context Gaps",
        *(f"- {item}" for item in metadata["contextGaps"]),
    ]
    yaml_str = yaml.dump(metadata, allow_unicode=True, sort_keys=False, default_flow_style=False).rstrip("\n")
    return "---\n" + yaml_str + "\n---\n\n" + "\n".join(body_lines).rstrip() + "\n"
```

Then change `knowledge_memory_profile_tool()` signature to accept dashboard fields:

```python
async def knowledge_memory_profile_tool(
    action: str = "read",
    content: str | None = None,
    profile: dict | str | None = None,
    role: str | None = None,
    expertise: list[str] | None = None,
    communicationStyle: str | None = None,
    successCriteria: list[str] | None = None,
    contextGaps: list[str] | None = None,
) -> str:
```

Before `metrics.track_tool(...)`, add:

```python
structured_profile = {
    "role": role,
    "expertise": expertise,
    "communicationStyle": communicationStyle,
    "successCriteria": successCriteria,
    "contextGaps": contextGaps,
}
if content is None and any(value is not None for value in structured_profile.values()):
    content = _profile_payload_to_markdown(structured_profile)
```

In `_handle_profile()`, replace `profile_path.write_text(new_content, encoding="utf-8")` with:

```python
if new_content.startswith("---"):
    profile_path.write_text(new_content, encoding="utf-8")
else:
    write_frontmatter(profile_path, {"lastUpdated": datetime.now(timezone.utc).isoformat()}, new_content)
```

- [ ] **Step 9: Run backend tests**

Run:

```bash
uv run pytest \
  skills/knowledge/augur/tests/test_tools_memory_dashboard.py \
  skills/knowledge/augur/tests/test_tools_memory_profile.py \
  skills/knowledge/augur/tests/test_tools_memory_core.py \
  -q
```

Expected: PASS.

- [ ] **Step 10: Commit backend contracts**

Run:

```bash
git add \
  skills/knowledge/scripts/mcp/tools_memory_dashboard.py \
  skills/knowledge/scripts/mcp/tools_memory_profile.py \
  skills/knowledge/augur/tests/test_tools_memory_dashboard.py \
  skills/knowledge/augur/tests/test_tools_memory_profile.py
git commit -m "fix(brain): expose memory source contracts"
```

Expected: commit succeeds.

---

### Task 2: Dashboard Brain Contract Utilities And Hooks

**Files:**

- Create: `apps/dashboard/features/pages/brain/memory/contracts.ts`
- Modify: `apps/dashboard/features/pages/brain/memory/types.ts`
- Modify: `apps/dashboard/features/pages/brain/memory/hooks.ts`
- Test: `tests/dashboard/features/pages/brain/memory/contracts.test.ts`
- Test: `tests/dashboard/features/pages/brain/memory/hooks.test.tsx`

- [ ] **Step 1: Write failing tests for contract utilities**

Create `tests/dashboard/features/pages/brain/memory/contracts.test.ts`:

```typescript
import {
  assertMcpSuccess,
  formatFreshness,
  formatOperationError,
  getPrimarySourceLabel,
} from '@/features/pages/brain/memory/contracts';

describe('Brain memory contracts', () => {
  it('throws on explicit MCP failure payloads', () => {
    expect(() => assertMcpSuccess({ success: false, error: 'not found' }, 'Open file')).toThrow('Open file failed: not found');
  });

  it('allows non-failure payloads', () => {
    expect(assertMcpSuccess({ success: true, message: 'ok' }, 'Refresh')).toEqual({ success: true, message: 'ok' });
    expect(assertMcpSuccess({ stats: { totalDecisions: 1 } }, 'Refresh')).toEqual({ stats: { totalDecisions: 1 } });
  });

  it('formats freshness labels', () => {
    const label = formatFreshness('2026-04-22T10:15:00Z');
    expect(label).toContain('Updated');
  });

  it('selects a primary source label', () => {
    expect(getPrimarySourceLabel({ memory: { label: 'Curated memory', exists: true } })).toBe('Curated memory');
  });

  it('normalizes unknown operation errors', () => {
    expect(formatOperationError('Search', 'bad input')).toBe('Search failed: bad input');
  });
});
```

- [ ] **Step 2: Run contract tests and verify failure**

Run:

```bash
pnpm --dir apps/dashboard test -- --runTestsByPath ../../tests/dashboard/features/pages/brain/memory/contracts.test.ts
```

Expected: FAIL because `contracts.ts` does not exist.

- [ ] **Step 3: Add shared contract utilities**

Create `apps/dashboard/features/pages/brain/memory/contracts.ts`:

```typescript
import type { BrainDataSources, BrainOperationNotice } from './types';

export function assertMcpSuccess<T>(payload: T, actionLabel: string): T {
  if (payload && typeof payload === 'object' && 'success' in payload && (payload as { success?: unknown }).success === false) {
    const error = (payload as { error?: unknown; details?: unknown }).error ?? (payload as { details?: unknown }).details;
    throw new Error(`${actionLabel} failed: ${String(error || 'unknown MCP error')}`);
  }
  return payload;
}

export function formatOperationError(actionLabel: string, error: unknown): string {
  const message = error instanceof Error ? error.message : String(error || 'unknown error');
  return message.startsWith(`${actionLabel} failed:`) ? message : `${actionLabel} failed: ${message}`;
}

export function makeNotice(type: BrainOperationNotice['type'], message: string): BrainOperationNotice {
  return { type, message, timestamp: new Date().toISOString() };
}

export function formatFreshness(value: string | null | undefined): string {
  if (!value) return 'No freshness timestamp';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return `Updated ${value}`;
  return `Updated ${date.toLocaleString()}`;
}

export function getPrimarySourceLabel(sources: BrainDataSources | null | undefined): string {
  if (!sources) return 'Unknown source';
  if (sources.memory?.exists) return sources.memory.label;
  if (sources.daily?.exists) return sources.daily.label;
  if (sources.profile?.exists) return sources.profile.label;
  if (sources.index?.exists) return sources.index.label;
  return 'Source unavailable';
}
```

- [ ] **Step 4: Extend Brain memory types**

Add to `apps/dashboard/features/pages/brain/memory/types.ts` after `DailyLogInfo`:

```typescript
export interface BrainDataSource {
  label: string;
  kind?: string;
  path?: string;
  exists?: boolean;
  modifiedAt?: string | null;
  sizeBytes?: number | null;
}

export interface BrainDataSources {
  memory?: BrainDataSource;
  index?: BrainDataSource;
  daily?: BrainDataSource;
  profile?: BrainDataSource;
  generatedAt?: string;
}

export interface BrainOperationNotice {
  type: 'success' | 'error' | 'info';
  message: string;
  timestamp: string;
}

export interface DailyLogsPayload {
  logs: DailyLogInfo[];
  source?: BrainDataSource;
  generatedAt?: string;
}

export interface DailyLogContentPayload {
  content: string;
  source?: BrainDataSource;
  generatedAt?: string;
  error?: string;
}
```

Add `sources?: BrainDataSources;` to `MemoryBootstrapPayload`.

- [ ] **Step 5: Harden hooks around MCP success and operation notices**

Modify imports in `apps/dashboard/features/pages/brain/memory/hooks.ts`:

```typescript
import { assertMcpSuccess, formatOperationError, makeNotice } from './contracts';
import type {
  BrainDataSources,
  BrainOperationNotice,
  DailyLogContentPayload,
  DailyLogsPayload,
  HumanApiProfile,
  MemoryBootstrapPayload,
  MemoryStats,
  PluginCategory,
  DailyLogInfo,
  MemorySearchResult,
  MemoryWorkspace,
  MemoryReport,
  WikiMaintenanceSummary,
  WikiRewriteCandidate,
} from './types';
```

In `toBootstrapPayload()`, return `sources: payload.sources`.

In `useMemoryDashboardData()`, add state:

```typescript
const [sources, setSources] = useState<BrainDataSources | null>(null);
const [notice, setNotice] = useState<BrainOperationNotice | null>(null);
```

In `applyBootstrap()`, add:

```typescript
setSources(payload.sources ?? null);
```

In `refreshAll()`, wrap the payload:

```typescript
const data = assertMcpSuccess(await mcpCall<unknown>('knowledge-memory-read', { mode: 'bootstrap' }), 'Load memory dashboard');
```

In `refreshStats()`, read new wrapped shapes:

```typescript
const [statsRaw, categoriesRaw] = await Promise.all([
  mcpCall<any>('knowledge-memory-read', { mode: 'stats' }),
  mcpCall<any>('knowledge-memory-read', { mode: 'categories' }),
]);
const statsData = assertMcpSuccess(statsRaw, 'Refresh memory stats');
const categoriesData = assertMcpSuccess(categoriesRaw, 'Refresh memory categories');
const nextStats = statsData.stats ?? statsData;
setStats(nextStats);
setSources(statsData.sources ?? categoriesData.sources ?? sources);
```

In `refreshWorkspace()`, wrap workspace/report calls with `assertMcpSuccess()` and update `sources`.

Return `sources` and `notice` from the hook.

In `useProfile()`, add:

```typescript
const [notice, setNotice] = useState<BrainOperationNotice | null>(null);
const [error, setError] = useState<string | null>(null);
```

Wrap profile reads/writes/regeneration with `assertMcpSuccess()`, set success notices on save/regenerate, and set error messages with `formatOperationError()`.

In `useMemoryWorkspace()`, remove `{ fallback: {} }` from both `knowledge-memory-read` calls, add `notice` and `error` state, wrap open calls with `assertMcpSuccess()`, and set notices such as `Opened ${fileId}`.

In `useDailyLogs()`, use `DailyLogsPayload` and `DailyLogContentPayload`, expose `source`, `generatedAt`, `logError`, and `isLogLoading`.

In `useMemorySearch()`, after the MCP call:

```typescript
const data = assertMcpSuccess(
  await mcpCall<{ results?: MemorySearchResult[]; error?: string }>('memory-search', { query, mode: 'hybrid', top_k: 10 }),
  'Search memory',
);
if (data.error) throw new Error(data.error);
setSearchResults(data.results || []);
```

- [ ] **Step 6: Add hook tests for visible failures**

Create `tests/dashboard/features/pages/brain/memory/hooks.test.tsx`:

```typescript
/**
 * @jest-environment jsdom
 */
import { renderHook, act, waitFor } from '@testing-library/react';
import { useMemorySearch } from '@/features/pages/brain/memory/hooks';
import { mcpCall } from '@/lib/mcp/client';

jest.mock('@/lib/mcp/client', () => ({
  mcpCall: jest.fn(),
}));

describe('Brain memory hooks', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows search errors from explicit MCP failures', async () => {
    (mcpCall as jest.Mock).mockResolvedValueOnce({ success: false, error: 'index unavailable' });

    const { result } = renderHook(() => useMemorySearch());

    await act(async () => {
      await result.current.handleSearch('architecture decision');
    });

    await waitFor(() => {
      expect(result.current.searchError).toContain('Search memory failed: index unavailable');
    });
  });

  it('stores successful search results', async () => {
    (mcpCall as jest.Mock).mockResolvedValueOnce({
      success: true,
      results: [{ content: 'Keep Brain flat', source: 'curated', category: 'decision', date: '2026-04-20', relevance: 0.9 }],
    });

    const { result } = renderHook(() => useMemorySearch());

    await act(async () => {
      await result.current.handleSearch('Brain flat routes');
    });

    expect(result.current.searchResults).toHaveLength(1);
    expect(result.current.searchResults[0]?.content).toBe('Keep Brain flat');
  });
});
```

- [ ] **Step 7: Run dashboard contract and hook tests**

Run:

```bash
pnpm --dir apps/dashboard test -- --runTestsByPath \
  ../../tests/dashboard/features/pages/brain/memory/contracts.test.ts \
  ../../tests/dashboard/features/pages/brain/memory/hooks.test.tsx
```

Expected: PASS.

- [ ] **Step 8: Commit dashboard contracts and hooks**

Run:

```bash
git add \
  apps/dashboard/features/pages/brain/memory/contracts.ts \
  apps/dashboard/features/pages/brain/memory/types.ts \
  apps/dashboard/features/pages/brain/memory/hooks.ts \
  tests/dashboard/features/pages/brain/memory/contracts.test.ts \
  tests/dashboard/features/pages/brain/memory/hooks.test.tsx
git commit -m "fix(brain): add visible data and action contracts"
```

Expected: commit succeeds.

---

### Task 3: Live Brain Page UX Hardening

**Files:**

- Modify: `apps/dashboard/features/pages/brain/memory/page.tsx`
- Modify: `apps/dashboard/features/pages/brain/search/page.tsx`
- Modify: `apps/dashboard/features/pages/brain/daily-logs/page.tsx`
- Modify: `apps/dashboard/features/pages/brain/profile/page.tsx`
- Modify: `apps/dashboard/features/pages/brain/workspace/page.tsx`
- Modify: `apps/dashboard/features/pages/brain/memory/components/MemorySearchWidget.tsx`
- Modify: `apps/dashboard/features/pages/brain/memory/components/DailyLogsCalendar.tsx`
- Modify: `apps/dashboard/features/pages/brain/memory/components/HumanApiProfile.tsx`
- Modify: `apps/dashboard/features/pages/brain/memory/components/HumanReportPreview.tsx`
- Modify: `apps/dashboard/features/pages/brain/memory/components/MemoryWorkspacePanel.tsx`
- Modify: `apps/dashboard/features/pages/brain/memory/components/WikiMaintenancePanel.tsx`
- Test: `tests/dashboard/features/pages/brain/memory/components/MemorySearchWidget.test.tsx`
- Test: `tests/dashboard/features/pages/brain/memory/components/DailyLogsCalendar.test.tsx`
- Test: `tests/dashboard/features/pages/brain/memory/components/HumanApiProfile.test.tsx`
- Test: `tests/dashboard/features/pages/brain/memory/components/MemoryWorkspacePanel.test.tsx`

- [ ] **Step 1: Write failing component tests for visible action outcomes**

Create `tests/dashboard/features/pages/brain/memory/components/MemorySearchWidget.test.tsx`:

```typescript
/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemorySearchWidget } from '@/features/pages/brain/memory/components/MemorySearchWidget';

const baseProps = {
  searchQuery: '',
  setSearchQuery: jest.fn(),
  isSearching: false,
  searchResults: [],
  hasSearched: false,
  searchError: null,
  onSearch: jest.fn(),
  categories: [],
};

describe('MemorySearchWidget', () => {
  it('shows the source freshness label when provided', () => {
    render(<MemorySearchWidget {...baseProps} sourceLabel="Curated memory" freshnessLabel="Updated 4/22/2026, 10:15:00 AM" />);
    expect(screen.getByText('Curated memory')).toBeInTheDocument();
    expect(screen.getByText('Updated 4/22/2026, 10:15:00 AM')).toBeInTheDocument();
  });

  it('offers curation as a next action when search has no results', () => {
    render(<MemorySearchWidget {...baseProps} hasSearched />);
    expect(screen.getByText(/Curate memory if the source looks stale/i)).toBeInTheDocument();
  });
});
```

Create `tests/dashboard/features/pages/brain/memory/components/DailyLogsCalendar.test.tsx`:

```typescript
/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { DailyLogsCalendar } from '@/features/pages/brain/memory/components/DailyLogsCalendar';
import { mcpCall } from '@/lib/mcp/client';

jest.mock('@/lib/mcp/client', () => ({ mcpCall: jest.fn() }));

describe('DailyLogsCalendar', () => {
  const props = {
    calendarMonth: new Date('2026-04-01T00:00:00Z'),
    setCalendarMonth: jest.fn(),
    selectedLog: '2026-04-22',
    logContent: '# Changes',
    lastCurated: '2026-04-22T10:00:00Z',
    onSelectDate: jest.fn(),
    onClearSelection: jest.fn(),
    hasLogForDate: () => true,
    getLogEntryCount: () => 3,
    getCalendarDays: () => [new Date('2026-04-22T00:00:00Z')],
    sourceLabel: 'Git commit history',
    generatedAt: '2026-04-22T10:15:00Z',
    logError: null,
    isLogLoading: false,
  };

  it('shows open failures from MCP', async () => {
    (mcpCall as jest.Mock).mockResolvedValueOnce({ success: false, error: 'Log not found' });
    render(<DailyLogsCalendar {...props} />);
    fireEvent.click(screen.getByRole('button', { name: /open in editor/i }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Log not found'));
  });
});
```

- [ ] **Step 2: Run component tests and verify failure**

Run:

```bash
pnpm --dir apps/dashboard test -- --runTestsByPath \
  ../../tests/dashboard/features/pages/brain/memory/components/MemorySearchWidget.test.tsx \
  ../../tests/dashboard/features/pages/brain/memory/components/DailyLogsCalendar.test.tsx
```

Expected: FAIL because the new props and visible text are not implemented.

- [ ] **Step 3: Add source and freshness props to search widget**

In `MemorySearchWidgetProps`, add:

```typescript
sourceLabel?: string;
freshnessLabel?: string;
```

Render this block below the description:

```tsx
{(sourceLabel || freshnessLabel) && (
  <div className="mb-4 flex flex-wrap gap-2 text-xs text-[var(--text-muted)]">
    {sourceLabel && <span className="rounded-full border border-[var(--border-color)] px-2 py-1">{sourceLabel}</span>}
    {freshnessLabel && <span className="rounded-full border border-[var(--border-color)] px-2 py-1">{freshnessLabel}</span>}
  </div>
)}
```

Change the no-results helper text to:

```tsx
Try a narrower topic, a concrete date, or a phrase from the original decision. Curate memory if the source looks stale.
```

- [ ] **Step 4: Add daily log source/error props**

In `DailyLogsCalendarProps`, add:

```typescript
sourceLabel?: string;
generatedAt?: string | null;
logError?: string | null;
isLogLoading?: boolean;
```

Render source/freshness in the header:

```tsx
<div className="flex flex-col items-end gap-1 text-xs text-[var(--text-muted)]">
  <div className="flex items-center gap-2">
    <Clock className="w-3 h-3" aria-hidden="true" />
    <span>Last curated: {lastCurated || 'Never'}</span>
  </div>
  {sourceLabel && <span>Source: {sourceLabel}</span>}
  {generatedAt && <span>Generated: {new Date(generatedAt).toLocaleString()}</span>}
</div>
```

In `handleOpenInEditor()`, change the success check:

```typescript
const result = await mcpCall<{ success?: boolean; error?: string }>('knowledge-memory-daily-logs-open', { date: selectedLog });
if (result?.success === false) {
  throw new Error(result.error || 'Daily log was not opened');
}
```

Replace the log content block with:

```tsx
{logError ? (
  <p className="text-xs text-[var(--accent-danger)]" role="alert">{logError}</p>
) : isLogLoading ? (
  <p className="text-xs text-[var(--text-muted)]">Loading log content...</p>
) : (
  <pre className="text-xs text-[var(--text-secondary)] whitespace-pre-wrap max-h-64 overflow-y-auto font-mono">
    {logContent || 'No content returned for this date.'}
  </pre>
)}
```

- [ ] **Step 5: Pass source/freshness through live pages**

In `memory/page.tsx`, import:

```typescript
import { formatFreshness, getPrimarySourceLabel } from './contracts';
```

After hooks:

```typescript
const sourceLabel = getPrimarySourceLabel(sources);
const freshnessLabel = formatFreshness(sources?.generatedAt ?? stats?.lastCurated);
```

Pass `sourceLabel` and `freshnessLabel` into `MemorySearchWidget`.

In `search/page.tsx`, use the same helper imports from `../memory/contracts`, pull `sources` from `useMemoryDashboardData()`, and pass labels into `MemorySearchWidget`.

In `DailyLogsSection.tsx`, pass `sourceLabel`, `generatedAt`, `logError`, and `isLogLoading` from `useDailyLogs()`.

- [ ] **Step 6: Add operation notices on profile and workspace pages**

In `HumanApiProfileSection.tsx`, pass `profileHook.notice` and `profileHook.error` into `HumanApiProfile`.

In `HumanApiProfile.tsx`, add props:

```typescript
notice?: { type: 'success' | 'error' | 'info'; message: string } | null;
error?: string | null;
```

Render above the profile body:

```tsx
{notice && (
  <div role="status" className="mb-4 rounded-lg border border-[var(--accent-success)]/25 bg-[var(--accent-success)]/10 p-3 text-sm text-[var(--accent-success)]">
    {notice.message}
  </div>
)}
{error && (
  <div role="alert" className="mb-4 rounded-lg border border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 p-3 text-sm text-[var(--accent-danger)]">
    {error}
  </div>
)}
```

In `workspace/page.tsx`, pass workspace hook `notice` and `error` into `MemoryWorkspacePanel` and `HumanReportPreview`.

In `MemoryWorkspacePanel.tsx`, add visible `role="status"` and `role="alert"` blocks before the file list.

In `HumanReportPreview.tsx`, ensure `onOpenReport` errors bubble through the workspace hook and render in the panel.

- [ ] **Step 7: Harden Wiki Maintenance action feedback**

Modify `WikiMaintenancePanel.tsx` so it uses `result` from `useActionRunner()` and renders:

```tsx
{result?.type === 'success' && lastActionId === 'wiki-update' && (
  <div role="status" className="rounded-xl border border-[var(--accent-success)]/25 bg-[var(--accent-success)]/10 p-3 text-sm text-[var(--accent-success)]">
    {result.message || 'Wiki update launched.'}
  </div>
)}
{result?.type === 'error' && lastActionId === 'wiki-update' && (
  <div role="alert" className="rounded-xl border border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 p-3 text-sm text-[var(--accent-danger)]">
    {result.message || 'Wiki update failed to launch.'}
  </div>
)}
```

Update `tests/dashboard/features/pages/brain/memory/components/WikiMaintenancePanel.test.tsx` to assert success/error messages when `mockUseActionRunner` returns those states.

- [ ] **Step 8: Run focused live-page tests**

Run:

```bash
pnpm --dir apps/dashboard test -- --runTestsByPath \
  ../../tests/dashboard/features/pages/brain/memory/components/WikiMaintenancePanel.test.tsx \
  ../../tests/dashboard/features/pages/brain/memory/components/MemorySearchWidget.test.tsx \
  ../../tests/dashboard/features/pages/brain/memory/components/DailyLogsCalendar.test.tsx \
  ../../tests/dashboard/features/pages/brain/memory/hooks.test.tsx \
  ../../tests/dashboard/features/pages/brain/memory/contracts.test.ts
```

Expected: PASS.

- [ ] **Step 9: Commit live Brain UX hardening**

Run:

```bash
git add \
  apps/dashboard/features/pages/brain/memory/page.tsx \
  apps/dashboard/features/pages/brain/search/page.tsx \
  apps/dashboard/features/pages/brain/daily-logs/page.tsx \
  apps/dashboard/features/pages/brain/profile/page.tsx \
  apps/dashboard/features/pages/brain/workspace/page.tsx \
  apps/dashboard/features/pages/brain/memory/components/MemorySearchWidget.tsx \
  apps/dashboard/features/pages/brain/memory/components/DailyLogsCalendar.tsx \
  apps/dashboard/features/pages/brain/memory/components/HumanApiProfile.tsx \
  apps/dashboard/features/pages/brain/memory/components/HumanApiProfileSection.tsx \
  apps/dashboard/features/pages/brain/memory/components/HumanReportPreview.tsx \
  apps/dashboard/features/pages/brain/memory/components/MemoryWorkspacePanel.tsx \
  apps/dashboard/features/pages/brain/memory/components/WikiMaintenancePanel.tsx \
  tests/dashboard/features/pages/brain/memory/components \
  tests/dashboard/features/pages/brain/memory/hooks.test.tsx \
  tests/dashboard/features/pages/brain/memory/contracts.test.ts
git commit -m "fix(brain): show live page action outcomes"
```

Expected: commit succeeds.

---

### Task 4: Promote Agent Control Center And Brain Harness

**Files:**

- Create: `apps/dashboard/features/pages/brain/agents/page.tsx`
- Create: `apps/dashboard/features/pages/brain/agents/control-state.ts`
- Create: `apps/dashboard/features/pages/brain/harness/page.tsx`
- Modify: `skills/ai/SKILL.md`
- Modify: `skills/knowledge/SKILL.md`
- Test: `tests/dashboard/features/pages/brain/agents/control-state.test.ts`
- Test: `tests/dashboard/features/pages/brain/harness-page.test.tsx`
- Modify: `tests/dashboard/lib/generate-tab-registry.test.ts`
- Modify: `tests/dashboard/scripts/generate-registry.test.ts`
- Modify: `tests/unit/test_staged_skill_catalog.py`

- [ ] **Step 1: Copy staged Agent Control Center source**

Run:

```bash
mkdir -p apps/dashboard/features/pages/brain/agents
cp staging/r3/pages/apps/dashboard/features/pages/brain/ai/agents/page.tsx apps/dashboard/features/pages/brain/agents/page.tsx
cp staging/r3/pages/apps/dashboard/features/pages/brain/ai/agents/control-state.ts apps/dashboard/features/pages/brain/agents/control-state.ts
```

Then edit `apps/dashboard/features/pages/brain/agents/page.tsx`:

- Keep `router.push('/settings/providers')` for provider configuration.
- Keep the "Browse owns the full agent inventory" copy.
- Change any `page: '/brain/ai/agents'` action context to `page: '/brain/agents'` if present.

- [ ] **Step 2: Copy staged Agent Control Center tests**

Run:

```bash
mkdir -p tests/dashboard/features/pages/brain/agents
cp staging/r3/pages/tests/dashboard/features/pages/brain/ai/agents/control-state.test.ts tests/dashboard/features/pages/brain/agents/control-state.test.ts
```

Run:

```bash
pnpm --dir apps/dashboard test -- --runTestsByPath ../../tests/dashboard/features/pages/brain/agents/control-state.test.ts
```

Expected: PASS.

- [ ] **Step 3: Copy staged Brain Harness page and tests**

Run:

```bash
mkdir -p apps/dashboard/features/pages/brain/harness
cp staging/r3/pages/apps/dashboard/features/pages/brain/harness/page.tsx apps/dashboard/features/pages/brain/harness/page.tsx
cp staging/r3/pages/tests/dashboard/features/pages/brain/harness-page.test.tsx tests/dashboard/features/pages/brain/harness-page.test.tsx
```

Run:

```bash
pnpm --dir apps/dashboard test -- --runTestsByPath ../../tests/dashboard/features/pages/brain/harness-page.test.tsx
```

Expected: PASS after updating import paths in the copied test if it references staging paths.

- [ ] **Step 4: Add Brain page contributions to owning skills**

In `skills/ai/SKILL.md`, change `x-augur-dashboard-pages: []` to:

```yaml
x-augur-dashboard-pages:
- /brain/agents
```

Under `x-augur-config.contributions`, add:

```yaml
    pages:
    - id: agents
      title: Agents
      icon: Bot
      order: 15
      purpose: Inspect execution routing, client sync health, provider readiness, and dispatch consequences.
      keywords:
      - agents
      - execution
      - dispatch
      - clients
```

In `skills/knowledge/SKILL.md`, add `/brain/harness` to `x-augur-dashboard-pages` after `/brain/workspace`.

Under `x-augur-config.contributions.pages`, add:

```yaml
    - id: harness
      title: Harness
      icon: Activity
      order: 16
      purpose: Inspect Brain capability wiring, diagnostics, provenance, and repair actions.
      keywords:
      - harness
      - diagnostics
      - wiring
      - brain
```

- [ ] **Step 5: Update route registry tests**

Update Brain route expectations in:

- `tests/dashboard/lib/generate-tab-registry.test.ts`
- `tests/dashboard/scripts/generate-registry.test.ts`
- `tests/unit/test_staged_skill_catalog.py`

Add `/brain/agents` and `/brain/harness` to expected route arrays. Keep existing flat routes intact.

Run:

```bash
pnpm --dir apps/dashboard test -- --runTestsByPath \
  ../../tests/dashboard/lib/generate-tab-registry.test.ts \
  ../../tests/dashboard/scripts/generate-registry.test.ts
uv run pytest tests/unit/test_staged_skill_catalog.py -q
```

Expected: PASS.

- [ ] **Step 6: Run mount and tab generation checks**

Run:

```bash
pnpm --dir apps/dashboard run build:scripts
pnpm --dir apps/dashboard run mount-plugins
pnpm --dir apps/dashboard run generate-tabs
```

Expected:

- `mount-plugins` completes without orphan pages.
- `generate-tabs` includes `/brain/agents` and `/brain/harness`.
- `apps/dashboard/app/brain/[[...slug]]/registry.ts` includes `agents` and `harness`.
- `apps/dashboard/lib/tabs/generated-registry.ts` includes the new flat Brain tabs.

- [ ] **Step 7: Commit promoted Brain surfaces**

Run:

```bash
git add \
  apps/dashboard/features/pages/brain/agents \
  apps/dashboard/features/pages/brain/harness \
  apps/dashboard/app/brain/[[...slug]]/registry.ts \
  apps/dashboard/lib/tabs/generated-registry.ts \
  skills/ai/SKILL.md \
  skills/knowledge/SKILL.md \
  tests/dashboard/features/pages/brain/agents/control-state.test.ts \
  tests/dashboard/features/pages/brain/harness-page.test.tsx \
  tests/dashboard/lib/generate-tab-registry.test.ts \
  tests/dashboard/scripts/generate-registry.test.ts \
  tests/unit/test_staged_skill_catalog.py
git commit -m "feat(brain): promote agents and harness pages"
```

Expected: commit succeeds.

---

### Task 5: Record Staged Surface Audit

**Files:**

- Create: `docs/references/brain-hub-staged-surface-audit.md`

- [ ] **Step 1: Write staged audit document**

Create `docs/references/brain-hub-staged-surface-audit.md`:

```markdown
---
title: Brain Hub Staged Surface Audit
date: 2026-04-22
status: implemented
---

# Brain Hub Staged Surface Audit

## Summary

Brain staged surfaces were evaluated against the Brain hardening survival gate: distinct user value, exact MCP wiring, real data, visible action outcomes, clear ownership, tests, and browser verification.

## Decisions

| Surface | Decision | Reason |
| --- | --- | --- |
| Agent Control Center | Promoted to `/brain/agents` | Distinct Brain value: execution routing, client sync health, provider readiness, dispatch behavior, and setup attention queue. Uses MCP-backed reads and mutations with existing focused tests. |
| Brain Harness | Promoted to `/brain/harness` | Distinct Brain value: capability wiring diagnostics, provenance, and repair workflow. Uses `get-brain-harness-snapshot` and `refresh-brain-harness-snapshot`. |
| RAG memory/search/projects/settings pages | Rework before promotion | Several surfaces overlap live `/brain/search`, `/brain/workspace`, Browse inventory, or Settings configuration. They need a narrower Brain job and freshness model before becoming live routes. |
| Schedule surfaces | Rework before promotion | The staged schedule controls need ownership, mutation outcomes, and a clear Brain-specific user job before becoming a route. |
| OCR/import | Not promoted | The staged import page uses `/api/brain/knowledge/ocr` and beta preview text. Brain hardening requires MCP-backed real extraction and no fake output. |

## Follow-Up Rules

- Future staged Brain pages must pass the survival gate before route registration.
- Provider configuration remains in Settings.
- Generic inventory remains in Browse.
- Brain routes remain flat siblings under `/brain`.
```

- [ ] **Step 2: Check frontmatter and wording**

Run:

```bash
sed -n '1,220p' docs/references/brain-hub-staged-surface-audit.md
python3 - <<'PY'
from pathlib import Path
text = Path("docs/references/brain-hub-staged-surface-audit.md").read_text(encoding="utf-8")
assert text.startswith("---\n")
assert "Agent Control Center" in text
assert "Brain Harness" in text
assert "OCR/import" in text
PY
```

Expected:

- The file starts with `---`.
- The Python assertions pass.

- [ ] **Step 3: Commit staged audit document**

Run:

```bash
git add docs/references/brain-hub-staged-surface-audit.md
git commit -m "docs(brain): record staged surface audit"
```

Expected: commit succeeds.

---

### Task 6: Full Verification And Browser Evidence

**Files:**

- No source file edits expected.
- Generated files may change if `mount-plugins` or `generate-tabs` was not committed in Task 4.

- [ ] **Step 1: Run focused Python tests**

Run:

```bash
uv run pytest \
  skills/knowledge/augur/tests/test_tools_memory_dashboard.py \
  skills/knowledge/augur/tests/test_tools_memory_profile.py \
  skills/knowledge/augur/tests/test_tools_memory_core.py \
  tests/unit/test_staged_skill_catalog.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run focused dashboard tests**

Run:

```bash
pnpm --dir apps/dashboard test -- --runTestsByPath \
  ../../tests/dashboard/features/pages/brain/memory/contracts.test.ts \
  ../../tests/dashboard/features/pages/brain/memory/hooks.test.tsx \
  ../../tests/dashboard/features/pages/brain/memory/components/WikiMaintenancePanel.test.tsx \
  ../../tests/dashboard/features/pages/brain/memory/components/MemorySearchWidget.test.tsx \
  ../../tests/dashboard/features/pages/brain/memory/components/DailyLogsCalendar.test.tsx \
  ../../tests/dashboard/features/pages/brain/agents/control-state.test.ts \
  ../../tests/dashboard/features/pages/brain/harness-page.test.tsx \
  ../../tests/dashboard/lib/generate-tab-registry.test.ts \
  ../../tests/dashboard/scripts/generate-registry.test.ts
```

Expected: PASS.

- [ ] **Step 3: Run registry generation checks**

Run:

```bash
pnpm --dir apps/dashboard run mount-plugins
pnpm --dir apps/dashboard run generate-tabs
git diff -- apps/dashboard/app/brain/[[...slug]]/registry.ts apps/dashboard/lib/tabs/generated-registry.ts
```

Expected:

- Commands pass.
- Diff is empty if generated files were already committed, or contains only the expected Brain route additions.

- [ ] **Step 4: Run production build through the lifecycle-safe command**

Use the project slash command:

```text
/dev-build
```

Expected: production dashboard build passes. Do not run `npm run build` directly.

- [ ] **Step 5: Request dashboard verification gate**

Run:

```bash
python3 skills/daemon/scripts/dashboard_lifecycle.py request-action \
  --actor brain-hub-hardening \
  --action verify-dashboard \
  --reason "verify Brain hub hardening pages"
```

Expected: JSON response permits verification or reports the current dashboard owner. If blocked, follow the returned owner/coordination guidance instead of killing processes.

- [ ] **Step 6: Identify the dashboard port and owning checkout**

Run:

```bash
lsof -nP -iTCP -sTCP:LISTEN | rg "node|next" || true
```

For the candidate dashboard PID, run:

```bash
pwdx <PID> 2>/dev/null || lsof -p <PID> | rg cwd
```

Expected: the listening dashboard process cwd is `&lt;active worktree path&gt;` or verification is deferred until the correct worktree dashboard is running through the lifecycle gate.

- [ ] **Step 7: Browser-verify live Brain pages**

Open each route on the verified worktree dashboard:

- `/brain/memory`
- `/brain/search`
- `/brain/daily-logs`
- `/brain/profile`
- `/brain/workspace`
- `/brain/agents`
- `/brain/harness`

For each route, wait at least 6 seconds and verify:

- At least one real data value appears.
- At least one meaningful action can be clicked or is disabled with a clear reason.
- Loading/error states do not collapse into blank content.
- No page uses beta/mock text as a successful result.
- Browser console has no new page-level errors.

- [ ] **Step 8: Record browser verification results in the final implementation handoff**

Use this concise evidence format in the final response:

```text
Browser verified on http://localhost:<port> from &lt;active worktree path&gt;:
- /brain/memory: real stats + Curate/Refresh outcome visible
- /brain/search: real search result or visible empty-state next action
- /brain/daily-logs: real date/source + open error/success visible
- /brain/profile: profile read + save/regenerate outcome visible
- /brain/workspace: file/report metadata + open/refresh outcome visible
- /brain/agents: execution summary + run/refresh/configure action visible
- /brain/harness: snapshot/diagnostics + refresh/repair action visible
```

- [ ] **Step 9: Final status check**

Run:

```bash
git status --short --branch
git log --oneline -6
```

Expected:

- Worktree has only intentional changes.
- Recent commits match the task checkpoints.
