---
status: Implemented
date: '2026-02-22'
deciders:
- Project team
related:
- ADR-028 (Two-Layer Memory)
- ADR-124 (Focus Button / Contextual Discovery)
- ADR-130 (Action Button Dispatch Modes)
hub: null
tags:
- activity
- summary
- panel
- replace
- empty
superseded_by: null
---

# ADR-139: Activity Summary Panel — Replace Empty Activity Box with Runtime-Driven Operation Summary

## Context

The home page "Latest Activity" panel (`ActivityList.tsx`) currently shows a near-empty box with "No recent activity" for most sessions because `getActivityFeed()` only aggregates from three static data sources (jobs, ideas, recipes). Meanwhile, the system already tracks rich operational data in `runtime/`:

1. **Page visits** — `runtime/daemon/usage_stats.yaml` tracks every dashboard page view with 7d/30d counts, last visit timestamps, and action click counts. Currently ~40+ pages tracked.
2. **IDE prompt history** — `runtime/logs/ide_history.json` records every slash command and prompt dispatched to CLI agents with timestamps and success status.
3. **Focus state** — `runtime/focus_state.json` tracks the last focused page/skill/bundle.
4. **Search queries** — The RAG search API (`/api/ai/knowledge/search`) processes queries but doesn't persist them.

None of this runtime data feeds the activity panel. The result is a prominent UI element that almost always shows "No recent activity" — wasting prime dashboard real estate.

The user wants the activity box enlarged to show an **operation summary** with:
- Last files searched (from RAG search history)
- Latest dashboards worked on (from usage_stats)
- Latest workflows run (from IDE history)
- Operations filtered to the bottom section
- 1-2 lines for dev activities (git commits, build status)

## Decision

Replace the static `getActivityFeed()` with a new `getActivitySummary()` API that aggregates runtime data into a structured summary panel. The panel is divided into user-facing activity sections (top) and dev/operations activity (bottom).

### 1. New API Route: `/api/activity/summary`

**File**: `plugins/admin/skills/renderer/augur/api/activity/summary/route.ts`
**Mounted at**: `src/dashboard/app/api/activity/summary/route.ts`

**GET** returns:

```typescript
interface ActivitySummary {
  dashboards: DashboardVisit[];   // Top pages by recency
  searches: SearchEntry[];         // Recent RAG search queries
  workflows: WorkflowEntry[];      // Recent IDE/CLI commands
  dev: DevActivity;                // Git + build summary (1-2 lines)
  operations: OperationStats;      // Task counts (existing)
}

interface DashboardVisit {
  page: string;           // e.g. "/career"
  label: string;          // e.g. "Career"
  views_7d: number;
  last_visit: string;     // ISO timestamp
}

interface SearchEntry {
  query: string;
  project?: string;       // RAG project filter
  timestamp: string;
}

interface WorkflowEntry {
  prompt: string;         // Slash command or prompt summary
  ide: string;
  timestamp: string;
  success: boolean;
}

interface DevActivity {
  last_commit: string;    // One-line summary
  branch: string;
  build_status: 'ok' | 'error' | 'unknown';
}

interface OperationStats {
  ready: number;
  in_progress: number;
  completed: number;
}
```

**Data source mapping:**

| Field | Source | How |
|-------|--------|-----|
| `dashboards` | `runtime/daemon/usage_stats.yaml` | Parse YAML, sort by `last_visit` desc, take top 5 |
| `searches` | `runtime/daemon/search_history.json` (NEW) | Append-only JSON log, take last 5 |
| `workflows` | `runtime/logs/ide_history.json` | Read existing file, take last 5 |
| `dev.last_commit` | `git log --oneline -1` | Shell exec |
| `dev.branch` | `git branch --show-current` | Shell exec |
| `dev.build_status` | Check if `.next/BUILD_ID` exists | fs.stat |
| `operations` | `getAgentBacklogSummary()` (existing) | Reuse existing function |

### 2. Search History Persistence

**File**: `plugins/ai/skills/knowledge/augur/api/search/route.ts`

Add a side-effect to the search handler: after a successful search, append a `{query, project, timestamp}` entry to `runtime/daemon/search_history.json`. Cap at 50 entries (FIFO).

```typescript
async function logSearchQuery(query: string, project: string | null): Promise<void> {
  const historyPath = join(AUGUR_RUNTIME_DIR, 'daemon', 'search_history.json');
  let entries = [];
  try { entries = JSON.parse(await readFile(historyPath, 'utf-8')); } catch {}
  entries.unshift({ query, project, timestamp: new Date().toISOString() });
  if (entries.length > 50) entries.length = 50;
  await writeFile(historyPath, JSON.stringify(entries, null, 2));
}
```

### 3. New Component: `ActivitySummaryPanel.tsx`

**File**: `src/dashboard/components/ActivitySummaryPanel.tsx`

Replaces `ActivityList` on the home page. Client component that fetches from `/api/activity/summary` on mount. Layout:

```
┌─────────────────────────────────────────────────┐
│  📊  Your Activity                    View All →│
├─────────────────────────────────────────────────┤
│                                                 │
│  DASHBOARDS           (top 5, sorted by recency)│
│  ● Career              24 views   2 min ago     │
│  ● Consulting           29 views  3h ago        │
│  ● AI Hub               19 views  3h ago        │
│                                                 │
│  SEARCHES              (last 3 queries)         │
│  🔍 "nvidia"           career     14 min ago    │
│  🔍 "pitch deck"       global     1h ago        │
│                                                 │
│  WORKFLOWS             (last 3 commands)        │
│  ▶ /app-dd ... translate           12h ago ✓    │
│  ▶ /app-dd ... tailor              12h ago ✓    │
│  ▶ /rag search find my post        2d ago  ✓    │
│                                                 │
├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┤
│  DEV                                            │
│  🔨 main · bfda2d1d feat(search)... · build ok │
│                                                 │
│  OPERATIONS                        View Ops →   │
│  Ready: 3  |  In Progress: 1  |  Completed: 12 │
└─────────────────────────────────────────────────┘
```

**Design rules:**
- Uses `glass-panel` + `bg-[var(--bg-card)]` consistent with existing dashboard cards
- Sections separated by subtle dividers, not heavy borders
- Relative timestamps via existing `RelativeTime` component
- Dashboard links are clickable (navigate to the page)
- Search entries are clickable (re-run the search in the hub search bar)
- Operations section is a compact 1-line summary with link to `/operations`
- Dev section is always exactly 1-2 lines: branch, last commit hash + message, build status indicator

### 4. Home Page Integration

**File**: `src/dashboard/app/page.tsx`

Replace:
```tsx
<Suspense fallback={<ActivitySkeleton />}>
  <ActivitySection />
</Suspense>
```

With:
```tsx
<Suspense fallback={<ActivitySkeleton />}>
  <ActivitySummaryPanel />
</Suspense>
```

Remove the `ActivitySection` function, `getActivityFeed` import, and `groupActivities` helper. Keep `ActivityList.tsx` as-is for the `/activity` detail page if it exists.

The `OperationsSection` and `OperationsSectionGate` at the bottom of the page are **removed** — operations data is now part of the summary panel's bottom section.

### 5. Usage Stats GET Endpoint

**File**: `src/dashboard/app/api/usage/track/route.ts`

Add a `GET` handler that returns the top N pages sorted by `last_visit` descending:

```typescript
export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const limit = parseInt(searchParams.get('limit') || '10', 10);
  const stats = await readUsageStats();
  const sorted = Object.entries(stats.pages)
    .filter(([page]) => page !== '/')
    .sort(([, a], [, b]) => new Date(b.last_visit).getTime() - new Date(a.last_visit).getTime())
    .slice(0, limit)
    .map(([page, stats]) => ({ page, ...stats }));
  return NextResponse.json({ pages: sorted });
}
```

## Consequences

**Positive:**
- Home page activity panel shows real, useful data instead of "No recent activity"
- Users see their actual workflow at a glance: what they searched, where they navigated, what commands they ran
- Operations section consolidates into the activity panel, reducing vertical scroll
- Search history enables "recent searches" UX patterns
- All data is local-first (runtime/ files), no external services

**Negative:**
- Search history persistence adds a small write to every search query (~1ms)
- Git commands in the API route add ~50ms latency (cached after first call)
- `ActivityList.tsx` is no longer used on the home page (but preserved for detail page)

**Neutral:**
- The `usage_stats.yaml` file grows with page visits but is already pruned at 30 days
- Search history is capped at 50 entries (~5KB)

## Implementation Order

```
Phase 1: Backend — Data Endpoints
├── Step 1: Add GET handler to /api/usage/track (read usage_stats.yaml)
├── Step 2: Add search history logging to knowledge search route
└── Step 3: Create /api/activity/summary route aggregating all sources

Phase 2: Frontend — Activity Summary Panel (depends on Phase 1)
├── Step 4: Create ActivitySummaryPanel.tsx component
└── Step 5: Wire into page.tsx, remove old ActivitySection + OperationsSection

Phase 3: Verification (depends on Phase 2)
├── Step 6: Verify build, type-check, no regressions
└── Step 7: Visual check — panel renders with real data from runtime/
```

## Alternatives Considered

### A. Extend `getActivityFeed()` with runtime data (server-side only)

Read runtime files directly in the server component. Rejected because:
- Mixes concerns (data aggregation in a rendering function)
- No reusable API endpoint for other consumers (MCP, mobile)
- Can't add search history without an API-level side-effect anyway

### B. Use a SQLite database for activity tracking

Replace YAML/JSON files with a local SQLite database. Rejected because:
- Adds a dependency for minimal benefit at current scale
- YAML/JSON files are human-readable and git-debuggable
- The current file-based approach handles ~50 pages and ~50 searches fine

### C. Real-time WebSocket activity stream

Push activity events via WebSocket for live updates. Rejected because:
- Over-engineered for a summary panel that refreshes on page load
- Adds infrastructure complexity (WebSocket server, connection management)
- The 5-minute debounce on usage tracking means data changes slowly

## References

- ADR-028: Two-Layer Memory Architecture (runtime data patterns)
- ADR-124: Focus Button / Contextual Discovery (runtime focus_state.json)
- `src/dashboard/components/ActivityList.tsx` — current activity component
- `src/dashboard/lib/services/system.ts` — current `getActivityFeed()`
- `src/dashboard/app/api/usage/track/route.ts` — usage stats tracking
- `runtime/daemon/usage_stats.yaml` — page visit data
- `runtime/logs/ide_history.json` — IDE prompt history

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-139: Activity Summary Panel**.

Read the full ADR: `docs/decisions/ADR-139-activity-summary-panel.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-139-activity-panel", description="Implementing ADR-139: Activity Summary Panel")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-139-activity-panel", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-139 team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-139-activity-panel`

#### Phase 1: Backend — Data Endpoints
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Add GET handler to `/api/usage/track/route.ts` that reads `usage_stats.yaml` and returns top N pages sorted by `last_visit` desc | `src/dashboard/app/api/usage/track/route.ts` |
| 1.2 | developer | medium | Add search history logging to knowledge search route — append `{query, project, timestamp}` to `runtime/daemon/search_history.json` after successful search, cap 50 entries | `plugins/ai/skills/knowledge/augur/api/search/route.ts`, `src/dashboard/app/api/ai/knowledge/search/route.ts` |
| 1.3 | developer | medium | Create `/api/activity/summary` route that aggregates: usage_stats (top 5 pages), search_history (last 5), ide_history (last 5 workflows), git info (last commit + branch), operations (existing `getAgentBacklogSummary`) | `src/dashboard/app/api/activity/summary/route.ts` |

#### Phase 2: Frontend — Activity Summary Panel
**Strategy**: PIPELINE (depends on Phase 1)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create `ActivitySummaryPanel.tsx` — client component fetching `/api/activity/summary`, rendering Dashboards / Searches / Workflows sections (top) and Dev + Operations sections (bottom). Use glass-panel styling, RelativeTime, clickable links. See ADR wireframe for layout. | `src/dashboard/components/ActivitySummaryPanel.tsx` |
| 2.2 | developer | low | Wire `ActivitySummaryPanel` into `page.tsx` — replace `ActivitySection` + remove `OperationsSection`/`OperationsSectionGate`. Remove unused `getActivityFeed` import and `groupActivities` helper. | `src/dashboard/app/page.tsx` |

#### Phase 3: Verification
**Strategy**: PIPELINE (depends on Phase 2)

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 3.1 | validator | low | Run `npx tsc --noEmit` in `src/dashboard/`, verify zero type errors |
| 3.2 | validator | low | Run `npm run build` in `src/dashboard/`, verify production build succeeds |
| 3.3 | validator | low | Verify `GET /api/activity/summary` returns valid JSON with all sections populated from runtime data |

### Completion Criteria
- [ ] All phases executed
- [ ] `GET /api/activity/summary` returns dashboards, searches, workflows, dev, operations
- [ ] Search queries are persisted to `runtime/daemon/search_history.json`
- [ ] `ActivitySummaryPanel` renders on home page with real runtime data
- [ ] Old `ActivitySection` and `OperationsSectionGate` removed from `page.tsx`
- [ ] TypeScript build passes (`npx tsc --noEmit`)
- [ ] Production build passes (`npm run build`)
- [ ] ADR status updated to "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-139-activity-summary-panel.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
