---
status: Implemented
date: '2026-03-09'
deciders:
- Gur Sannikov
related:
- ADR-406 (Block System)
- ADR-250 (MCP Tool Hygiene)
- ADR-107 (MCP Package Architecture)
- ADR-163 (Plugin Decentralization)
hub: null
tags:
- mcp
- first
- dashboard
- eliminate
- direct
superseded_by: null
---

# ADR-287: MCP-First Dashboard — Eliminate Direct Filesystem Access from UI Layer

**Supersedes**: None

## Context

The Augur dashboard has accumulated three incompatible data access patterns over time. An initial audit (2026-03-09) of 454 API routes showed only 26% MCP compliance. Since then, significant migration work has been completed.

### Current State (Audit: 2026-03-12)

| Data Access Pattern | Route Count | % of Total |
|---|---|---|
| `createAPIRoute` → MCP tool | 624 | 82% |
| Direct `import fs` → `readFile`/`writeFile` | 38 | 5% |
| `exec`/`spawn` → shell commands | 39 | 5% |
| `runPythonScript` → Python scripts | 6 | 1% |
| Other (internal, computed, external API) | 57 | 7% |
| **Total routes** | **764** | |

Additionally:
- **`@/lib/services/` directory** — deleted (was 17 files, all replaced by `createAPIRoute` routes)
- **`@/lib/api.ts` barrel** — deleted
- **`DATA_PATHS` proxy** — 1 remaining reference
- **Server-component pages** importing services — 0 remaining
- **Plugin pages** directly importing `fs` — to be verified

### Why This Is a Problem

1. **CLI/Dashboard divergence**: `aug list-recipes` calls the `list-recipes` MCP tool. The dashboard calls `getRecipes()` from `@/lib/services/recipes.ts` which reads the same YAML files through completely separate TypeScript code. Bug fixes, validation, sorting, or filtering added to the MCP tool are invisible to the dashboard.

2. **Agent parity violation**: IDE agents and the CLI use MCP tools. The dashboard uses a parallel filesystem layer. A user editing data via CLI sees different behavior than editing via dashboard if the two implementations drift.

3. **Block system blocked**: ADR-406 blocks declare `data_source: { mcp_tool: list-recipes }` in `augur.yaml`, but the rendering layer has no hook to call MCP tools. Blocks show placeholder content because the MCP-first path was never built.

4. **Service layer is technical debt**: 17 service files in `@/lib/services/` re-implement what MCP tools already do. The `DATA_PATHS` proxy in `paths.ts` creates a second discovery mechanism parallel to MCP tool registration. The barrel export `@/lib/api.ts` makes it trivially easy to bypass MCP.

5. **Security surface**: Direct `fs.readFile` in 224 routes means path traversal bugs must be caught in each route individually. MCP tools have a single enforcement point.

## Decision

**The dashboard is a consumer, not a data implementation.** Every data operation flows through MCP tools — the same tools that `aug` CLI and IDE agents use. If a capability is missing from MCP, add it to the CLI/MCP layer first, then wire the dashboard to consume it.

### Target Architecture

```
Dashboard (browser)
    │ fetch()
API Route (/api/hub/skill/resource)
    │ createAPIRoute({ toolName })
MCP Tool (Python, reads plugin augur/data/)
    │ fs read
Plugin Data (augur/data/*.yaml)
```

Four consumers, one implementation:
- **CLI**: `aug list-recipes` → MCP tool
- **Dashboard page**: `fetch('/api/lifestyle/recipes')` → `createAPIRoute` → MCP tool
- **Dashboard block**: `useBlockData({ mcpTool: 'list-recipes' })` → same API route → MCP tool
- **IDE agent**: `callMCPTool('list-recipes')` → MCP tool

### What Gets Eliminated

| Layer | Current | Target |
|---|---|---|
| `src/dashboard/lib/services/*.ts` (17 files) | Direct `fs.readFile` + `yaml.parse` | Deleted — replaced by `createAPIRoute` in API routes |
| `src/dashboard/lib/api.ts` (barrel) | Re-exports 17 service functions | Deleted — pages use `fetch('/api/...')` |
| `DATA_PATHS` proxy in `paths.ts` | Scans `augur.yaml` for `contributions.data_paths` | Deleted — MCP tools resolve their own paths |
| Server-component pages (15) | `async function Page()` calls services directly | Converted to client components calling API routes |
| `child_process.spawn` in pages (2) | Spawns `gog` CLI during SSR | Converted to `fetch('/api/...')` → MCP tool |
| Direct `fs` in API routes (224) | `fs.readFile` + `yaml.parse` inline | Replaced with `createAPIRoute({ toolName })` |
| `runPythonScript` in routes (12) | `runPythonScript('script.py')` | Replaced with MCP tool that wraps the same logic |
| `exec`/`spawn` in routes (79) | Shell commands for git, system metrics, etc. | Replaced with MCP tools or dedicated utility routes |

### Migration Pattern

**Before** (non-compliant route, ~224 routes follow this):
```typescript
import fs from 'fs/promises';
import yaml from 'yaml';
import { getSkillDataPath } from '@/lib/paths';

export async function GET() {
  const dataDir = getSkillDataPath('finance');
  const raw = await fs.readFile(`${dataDir}/transactions.yaml`, 'utf8');
  const { transactions } = yaml.parse(raw);
  return NextResponse.json({ success: true, data: transactions });
}
```

**After** (MCP-compliant, 4 lines):
```typescript
import { createAPIRoute } from '@/lib/mcp/createAPIRoute';

export const dynamic = 'force-dynamic';
export const { GET } = createAPIRoute({ toolName: 'finance-transactions' });
```

**Before** (non-compliant service + server page):
```typescript
// lib/services/recipes.ts
import fs from 'fs/promises';
import { DATA_PATHS } from '@/lib/paths';
export async function getRecipes() {
  const files = await glob(path.join(DATA_PATHS.recipes, '**/*.yaml'));
  return Promise.all(files.map(f => fs.readFile(f, 'utf8').then(yaml.parse)));
}

// plugins/lifestyle/.../page.tsx (server component)
import { getRecipes } from '@/lib/api';
export default async function Page() {
  const recipes = await getRecipes();
  return <RecipeGrid recipes={recipes} />;
}
```

**After** (MCP-compliant page + route):
```typescript
// plugins/lifestyle/.../page.tsx (client component)
'use client';
export default function Page() {
  const [recipes, setRecipes] = useState([]);
  useEffect(() => {
    fetch('/api/lifestyle/lifestyle/recipes').then(r => r.json()).then(d => setRecipes(d.data));
  }, []);
  return <RecipeGrid recipes={recipes} />;
}

// API route — already migrated to createAPIRoute
// lib/services/recipes.ts — DELETED
```

## Implementation Plan

### Phase A: Wire Blocks to MCP (ADR-406 scope)

**Goal**: Make all 14 block types fetch and display real data through MCP.
**Depends on**: Nothing — can start immediately.
**Strategy**: PIPELINE

| Step | Task | Files | Details |
|------|------|-------|---------|
| A.1 | Add `dataSource` to `BlockProps` | `lib/blocks/types.ts` | Add optional `dataSource?: DataSource` field |
| A.2 | Forward `dataSource` in `BlockRenderer` | `components/blocks/BlockRenderer.tsx` | Pass `manifest.dataSource` to block component |
| A.3 | Create `useBlockData` hook | `lib/blocks/useBlockData.ts` (new) | Generic fetcher: takes `DataSource` + config, returns `{ data, loading, error }`. Calls `fetch(apiRoute)` or `fetch('/api/mcp/call', { tool, args })` |
| A.4 | Create block data proxy route | `app/api/blocks/data/route.ts` (new) | Generic MCP proxy: receives `{ tool, args }`, calls `callMCPTool(tool, args)`, returns result. For blocks whose `dataSource` specifies `mcpTool` without an existing API route |
| A.5 | Wire `DataListBlock` | `components/blocks/types/DataListBlock.tsx` | Call `useBlockData`, render items as clickable list |
| A.6 | Wire `CardGridBlock` | `components/blocks/types/CardGridBlock.tsx` | Call `useBlockData`, render card tiles |
| A.7 | Wire `DataTableBlock` | `components/blocks/types/DataTableBlock.tsx` | Call `useBlockData`, render sortable table |
| A.8 | Wire `ChartBlock` | `components/blocks/types/ChartBlock.tsx` | Call `useBlockData`, render bar/line chart |
| A.9 | Wire `ActionBarBlock` | `components/blocks/types/ActionBarBlock.tsx` | Call `useBlockData`, wire buttons to `useActionRunner` |
| A.10 | Wire `ActivityFeedBlock` | `components/blocks/types/ActivityFeedBlock.tsx` | Call `useBlockData`, render timestamped entries |
| A.11 | Wire `StatCardBlock` | `components/blocks/types/StatCardBlock.tsx` | Call `useBlockData`, render live stat value |
| A.12 | Wire `StatGridBlock` | `components/blocks/types/StatGridBlock.tsx` | Call `useBlockData`, render stat grid |
| A.13 | Wire `ProgressBlock` | `components/blocks/types/ProgressBlock.tsx` | Call `useBlockData`, render live progress |
| A.14 | Wire `OpsBoardBlock` | `components/blocks/types/OpsBoardBlock.tsx` | Call `useBlockData`, render status indicators |
| A.15 | Wire `CalendarBlock` | `components/blocks/types/CalendarBlock.tsx` | Call `useBlockData`, render mini calendar |
| A.16 | Wire `MarkdownBlock` | `components/blocks/types/MarkdownBlock.tsx` | Call `useBlockData`, render markdown content |
| A.17 | Wire `NotesBlock` | `components/blocks/types/NotesBlock.tsx` | Fetch saved notes, persist on change |
| A.18 | Wire `EmbedBlock` | `components/blocks/types/EmbedBlock.tsx` | Render `config.url` in iframe |

**Verification**: Every block with a valid `dataSource` pointing to an existing MCP tool/API route shows real data. Blocks with missing tools show "Data source not available" empty state.

---

### Phase B: Fill MCP Tool Gaps

**Goal**: Create MCP tools for dashboard data needs that currently have no MCP backend.
**Depends on**: Nothing — can run in parallel with Phase A.
**Strategy**: PARALLEL (each tool is independent)

#### Audit: Services vs MCP Tools

| Service File | MCP Tool Exists? | Action |
|---|---|---|
| `recipes.ts` | `list-recipes` exists | Delete service (Phase D) |
| `movies.ts` | `list-movies` exists | Delete service (Phase D) |
| `ideas.ts` | `list-ideas` exists | Delete service (Phase D) |
| `shopping.ts` | `list-shopping-items` exists | Delete service (Phase D) |
| `travel.ts` | `list-trips` exists | Delete service (Phase D) |
| `reading.ts` | `list-reading-items` exists | Delete service (Phase D) |
| `jobs.ts` (800 lines) | `get-career-jobs` exists | Delete service (Phase D) |
| `voice-memos.ts` | `apple-list-voice-memos` exists | Delete service (Phase D) |
| `calendar.ts` | Already MCP-compliant | Keep (already calls `callMCPTool`) |
| `reviews.ts` | Already MCP-compliant | Keep (already calls `callMCPTool`) |
| `inbox.ts` | Already MCP-compliant | Keep (already calls `callMCPTool`) |
| `places.ts` | **No MCP tool** | Create tool → then delete service |
| `social-media.ts` | **No MCP tool** | Create tool → then delete service |
| `interview-projects.ts` | **No MCP tool** | Create tool → then delete service |
| `page-telemetry.ts` | **No MCP tool** | Create tool → then delete service |
| `system.ts` (aggregator) | **No MCP tool** | Create tool → then delete service |
| `agents.ts` | **No MCP tool** | Create tool → then delete service |
| `collateral.ts` | **No MCP tool** | Create tool → then delete service |
| `mcp.ts` (infra) | N/A | Keep (infrastructure bootstrap) |
| `promptLoader.ts` | Already API-compliant | Keep (fetches from `/api/prompts/`) |

**8 services** can be deleted immediately (MCP tools exist).
**7 services** need new MCP tools first.
**5 services** are already compliant or infrastructure.

#### New MCP Tools Required

| Step | Tool Name | Hub/Skill | What It Reads | Blocks/Pages That Need It |
|------|-----------|-----------|---------------|--------------------------|
| B.1 | `list-places` | lifestyle/lifestyle | `augur/data/places/*.yaml` | Places page, places block |
| B.2 | `list-venture-posts` | professional/venture-augur | `augur/data/venture/posts/index.yaml` | Social media pages, content block |
| B.3 | `get-growth-habits` | career/growth | `augur/data/habits/habits.yaml` | Habits page, habits block |
| B.4 | `get-eisenhower-tasks` | productivity/eisenhower | Eisenhower matrix data | 5 Eisenhower pages, task blocks |
| B.5 | `get-wealth-portfolio` | finance/wealth | `augur/data/portfolio.yaml` | Portfolio page, portfolio block |
| B.6 | `get-wealth-goals` | finance/wealth | `augur/data/goals.yaml` | Goals page, goals block |
| B.7 | `get-wealth-crypto` | finance/wealth | `augur/data/crypto.yaml` | Crypto page, crypto block |
| B.8 | `get-wearables-data` | health/wearables | Watch/location data | Watch page, location page |
| B.9 | `list-interview-projects` | career/career | `augur/data/interview/*.yaml` | Interview page, interview block |
| B.10 | `get-system-stats` | core | Cross-hub aggregation (counts) | System overview block, admin pages |
| B.11 | `get-page-telemetry` | observability | `runtime/metrics/page-metrics/*.json` | Telemetry dashboard |
| B.12 | `list-agent-capabilities` | ai | Plugin skill docs + telemetry | Agent dashboard pages |
| B.13 | `list-collateral-files` | files | Project file listing + git metadata | File manager pages |

Each tool follows the existing MCP registration pattern:

```python
# plugins/{hub}/skills/{skill}/augur/mcp/__init__.py
@mcp.tool(name="list-places")
async def list_places(limit: int = 20, filter: str = "all") -> str:
    """List saved places from the lifestyle plugin."""
    data_dir = get_skill_data_path("lifestyle")
    places = load_yaml_dir(f"{data_dir}/places")
    return json.dumps({"data": places[:limit], "count": len(places)})
```

Each tool must be declared in the skill's `augur.yaml` under `mcp.tools:`.

**Verification**: `aug <tool-name>` works from CLI. `/api/blocks/data?tool=<tool-name>` returns data.

---

### Phase C: Migrate API Routes to `createAPIRoute`

**Goal**: Convert all 335 non-MCP API routes to use `createAPIRoute({ toolName })`.
**Depends on**: Phase B (MCP tools must exist before routes can call them).
**Strategy**: PARALLEL by hub (routes within a hub are independent)

#### Scope

| Category | Count | Migration Path |
|---|---|---|
| Direct `fs` import | 224 | Replace with `createAPIRoute({ toolName })` |
| `exec`/`spawn` | 79 | Create MCP tool wrapper, then `createAPIRoute` |
| `runPythonScript` | 12 | Move logic into MCP tool, then `createAPIRoute` |
| Already `createAPIRoute` | 119 | No change |
| Internal/computed | 20 | Keep as-is (auth, CSRF, dispatch infrastructure) |

#### Migration by Hub

| Step | Hub | Est. Routes | MCP Tools Available | Notes |
|------|-----|-------------|--------------------|----|
| C.1 | lifestyle | ~15 | 11 (lifestyle + books) | Straightforward — all tools exist |
| C.2 | finance | ~20 | 8 (finance + wealth after B.5-B.7) | Transactions, accounts, budget already have tools |
| C.3 | career | ~18 | 18 (career + growth after B.3) | Jobs (800-line service) → `get-career-jobs` tool |
| C.4 | health | ~12 | 12 (health + wearables after B.8) | Virtual doctor tools well-implemented |
| C.5 | productivity | ~35 | 47 (apple + google-workspace + eisenhower after B.4) | Largest hub — calendar spawn → MCP |
| C.6 | professional | ~10 | 3 + new (after B.2) | Venture-augur needs more tools |
| C.7 | consulting | ~12 | 24 | SMB design well-covered |
| C.8 | ai | ~25 | 40 | Knowledge/RAG/scraper well-covered |
| C.9 | dev | ~20 | 24 | MCP app factory well-covered |
| C.10 | observability | ~15 | 15 | Observe + daemon tools exist |
| C.11 | admin | ~20 | 3 + new | Install tools exist, page-builder needs tools |
| C.12 | home | ~5 | 12 | Hue/Sonos well-covered |
| C.13 | files | ~8 | 1 + new (after B.13) | Mostly CRUD — needs file MCP tools |
| C.14 | core/system | ~30 | Various | Settings, config, logs, chat — bulk of exec/spawn routes |
| C.15 | Remaining infrastructure | ~90 | N/A | Auth, debug, metrics, bridge — assess individually |

**Pattern for each route**:
1. Identify what data the route reads/writes
2. Find or create corresponding MCP tool (Phase B)
3. Replace route body with `createAPIRoute({ toolName, extractParams?, transformResponse? })`
4. Delete any `import fs`, `import yaml`, path resolution code
5. Verify: `curl /api/...` returns same response shape

**Verification**: Zero routes import `fs` directly. `grep -r "import.*fs.*from" src/dashboard/app/api/ --include="*.ts"` returns only infrastructure utilities (if any).

---

### Phase D: Eliminate Service Layer and Direct Filesystem Imports

**Goal**: Delete `@/lib/services/*.ts`, `@/lib/api.ts` barrel, `DATA_PATHS` proxy, and convert all server-component pages to client components.
**Depends on**: Phase C (all API routes must be MCP-backed before removing the service layer that some pages still use).
**Strategy**: PIPELINE

| Step | Task | Files | Details |
|------|------|-------|---------|
| D.1 | Delete 8 services with existing MCP tools | `lib/services/{recipes,movies,ideas,shopping,travel,reading,jobs,voice-memos}.ts` | MCP tools already handle this data |
| D.2 | Delete 7 services after MCP tools created in Phase B | `lib/services/{places,social-media,interview-projects,page-telemetry,system,agents,collateral}.ts` | New MCP tools replace them |
| D.3 | Keep 3 already-compliant services | `lib/services/{reviews,calendar,inbox}.ts` | Already call `callMCPTool()` — optionally inline into routes |
| D.4 | Keep 2 infrastructure services | `lib/services/{mcp,promptLoader}.ts` | Bootstrap/infra, not data access |
| D.5 | Delete `@/lib/api.ts` barrel | `lib/api.ts` | No more service re-exports needed |
| D.6 | Remove `DATA_PATHS` proxy | `lib/paths.ts` (lines 422-558) | MCP tools resolve their own paths via Python `get_skill_data_path()` |
| D.7 | Remove `contributions.data_paths` from augur.yaml | 4 plugin `augur.yaml` files | lifestyle, career, career/interview-coach, productivity/apple |
| D.8 | Convert 15 server-component pages to client+fetch | `plugins/*/skills/*/augur/dashboard/**/page.tsx` | Replace `async function Page()` + service import with `'use client'` + `fetch()` |
| D.9 | Remove `child_process.spawn` from 2 pages | `plugins/productivity/skills/google-workspace/augur/dashboard/{gmail,calendar}/page.tsx` | Replace `spawnGog()` with `fetch('/api/...')` |
| D.10 | Remove direct `import fs` from 3 pages | Plugin pages that import `fs` | Replace with `fetch('/api/...')` |
| D.11 | Final audit: verify zero direct fs in UI layer | All `src/dashboard/` and `plugins/*/augur/dashboard/` | `grep -r "import fs\|import { readFile\|from 'fs'" --include="*.tsx" --include="*.ts"` returns zero matches in UI code |

**Verification**:
- `grep -r "from.*@/lib/services" --include="*.tsx"` returns zero matches
- `grep -r "from.*@/lib/api" --include="*.tsx"` returns zero matches
- `grep -r "DATA_PATHS" --include="*.ts" --include="*.tsx"` returns zero matches in dashboard code
- `grep -r "import fs\|import { readFile" src/dashboard/ plugins/*/augur/dashboard/ --include="*.ts" --include="*.tsx"` returns zero matches
- All existing page functionality preserved (same data, same UI, different plumbing)

## Consequences

### Positive

- **100% CLI/Dashboard parity**: Same MCP tool serves `aug` CLI, dashboard, IDE agents, and blocks
- **Single implementation**: Bug fixes and validation in MCP tools automatically apply everywhere
- **Block system unblocked**: ADR-406 blocks can fetch real data via `useBlockData` → MCP
- **Reduced code**: ~17 service files deleted, ~224 routes simplified to 4-line `createAPIRoute` calls
- **Security**: Path traversal, data validation enforced at one layer (MCP tools), not 224 routes
- **Testability**: MCP tools are independently testable via `aug <tool-name>` without a running dashboard

### Negative

- **Large migration scope**: 335 routes + 17 services + 15 pages to convert
- **MCP tool gaps**: 13 new tools must be created before full migration
- **Server-component loss**: Converting server pages to client pages loses SSR benefits (first-paint speed) — acceptable tradeoff for architectural consistency
- **Transient breakage**: During migration, some routes may have response shape differences between fs-direct and MCP paths

### Neutral

- **No user-facing change**: Pages display the same data, blocks gain real data
- **Plugin data files unchanged**: `augur/data/*.yaml` stays where it is
- **MCP tool registration unchanged**: Tools still declared in `augur.yaml` and registered in `__init__.py`
- **`createAPIRoute` unchanged**: The wrapper already exists and handles the MCP bridge correctly

### TODO_CLEANUP: MCP Tool Consolidation Opportunity

Phase B created 13 new tools, but ~5 are pure YAML readers with identical logic (read dir, filter, return JSON): `list-places`, `list-venture-posts`, `list-interview-projects`, `get-wearables-data`, `list-collateral-files`. These should be consolidated into a single generic `read-skill-data` tool with `skill` + `collection` + `filter` params. The 5 tools with real computation (`get-wealth-portfolio`, `get-wealth-goals`, `get-wealth-crypto`, `get-system-stats`, `list-agent-capabilities`) should remain specialized. The 3 middle-ground tools (`get-growth-habits`, `get-eisenhower-tasks`, `get-page-telemetry`) are borderline. This consolidation would reduce tool sprawl and enforce a canonical data-read pattern across all plugins.

## Completion Criteria

- [ ] **Phase A**: All 14 block types fetch and render real data via `useBlockData`
- [ ] **Phase B**: All 13 missing MCP tools created and accessible via CLI
- [ ] **Phase C**: Zero API routes import `fs` directly (excluding infrastructure utilities)
- [ ] **Phase C**: Zero API routes call `runPythonScript` or `exec`/`spawn`
- [ ] **Phase D**: `@/lib/services/` directory contains only MCP-compliant services and infrastructure
- [ ] **Phase D**: `@/lib/api.ts` barrel deleted
- [ ] **Phase D**: `DATA_PATHS` proxy removed from `paths.ts`
- [ ] **Phase D**: Zero server-component pages import from `@/lib/services/`
- [ ] **Phase D**: Zero `import fs` in any `.tsx` file under `src/dashboard/` or `plugins/*/augur/dashboard/`
- [ ] All existing page functionality preserved (visual regression check)
- [ ] `aug` CLI and dashboard return identical data for the same operations

## References

- ADR-406: Block System UI (amendment: MCP-First Block Data)
- ADR-250: MCP Tool Hygiene and Client-Aware Filtering
- ADR-107: MCP Package Architecture
- ADR-163: Plugin Decentralization
- `src/dashboard/lib/mcp/createAPIRoute.ts` — the target pattern for all routes
- `src/dashboard/lib/services/reviews.ts` — example of a correctly MCP-compliant service
- `src/dashboard/app/api/ide/status/route.ts` — minimal `createAPIRoute` example

## Impact Manifest

```yaml
impact:
  files_deleted:
    - glob: "src/dashboard/lib/services/{recipes,movies,ideas,shopping,travel,reading,jobs,voice-memos,places,social-media,interview-projects,page-telemetry,system,agents,collateral}.ts"
    - file: "src/dashboard/lib/api.ts"
  files_modified:
    - glob: "src/dashboard/app/api/**/route.ts"
      scope: "~335 routes migrated to createAPIRoute"
    - file: "src/dashboard/lib/paths.ts"
      scope: "Remove DATA_PATHS proxy (lines 422-558)"
    - glob: "plugins/*/skills/*/augur.yaml"
      scope: "Remove contributions.data_paths from 4 plugins"
    - glob: "plugins/*/skills/*/augur/dashboard/**/page.tsx"
      scope: "~15 server pages converted to client components"
  files_created:
    - file: "src/dashboard/lib/blocks/useBlockData.ts"
    - file: "src/dashboard/app/api/blocks/data/route.ts"
    - glob: "plugins/*/skills/*/augur/mcp/__init__.py"
      scope: "13 new MCP tools added to existing modules"
  patterns_deprecated:
    - grep: "import.*from.*@/lib/services/"
      replacement: "fetch('/api/...') backed by createAPIRoute"
    - grep: "import.*from.*@/lib/api"
      replacement: "fetch('/api/...') backed by createAPIRoute"
    - grep: "DATA_PATHS\\."
      replacement: "MCP tools resolve paths internally via Python get_skill_data_path()"
    - grep: "import fs.*from.*fs"
      replacement: "createAPIRoute({ toolName }) — no direct fs in dashboard"
    - grep: "runPythonScript"
      replacement: "MCP tool wrapping the same Python logic"
    - grep: "child_process"
      replacement: "MCP tool wrapping the same CLI command"
```
