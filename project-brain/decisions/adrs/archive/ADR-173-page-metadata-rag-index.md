---
status: Implemented
date: '2026-02-27'
deciders:
- Project team
related:
- ADR-085 (project indexer)
- ADR-126 (plugin template)
- ADR-128 (contribution model)
- ADR-130 (action dispatch)
hub: null
tags:
- unified
- capabilities
- search
- extend
- project
superseded_by: null
---

# ADR-173: Unified Capabilities Search — Extend Project Index with Pages, Tools, Actions, Commands

## Context

Augur has four categories of user-facing capabilities that are invisible to search:

| Category | ~Count | Source | Has Description? |
|----------|--------|--------|-----------------|
| Dashboard pages | 60 | `augur.yaml` `contributions.pages` | No — only `id`, `title`, `icon`, `order` |
| MCP tools | 358 | Python `@mcp.tool()` decorators | Yes — in Python docstrings, but not indexed |
| Action commands | 40 | `augur/data/actions/*.yaml` | Yes — `description` field exists, not indexed |
| Slash commands | 56 | `agent-workflows/*.md` | Yes — frontmatter `description`, not indexed |

A user searching "how do I add a job?" gets nothing, despite the existence of a page (`/career/pipeline`), an MCP tool (`add-career-job`), an action button (`add-job`), and a related command (`/ask`).

### Existing Infrastructure

`project_indexer.py` (ADR-085) already indexes 5 entity types (skills, dashboards, ADRs, agents, chains) into a structured YAML file (`project-index.yaml`). A dedicated search API (`/api/knowledge/project-index/search`) scores results by name/title/description/tags with ranked relevance. The dashboard search UI renders `ProjectResult` cards with per-type color badges.

**This infrastructure is the right place to add capabilities.** It has typed entries, field-level scoring, and a working UI — all missing from RAG fulltext search.

### Current Bugs in Project Index

1. **Stale read path**: Search routes read from `services/rag/project-index.yaml` (pre-ADR-087 path). Indexer writes to `plugins/ai/skills/knowledge/data/rag/project-index.yaml`. Neither file exists — the index is effectively broken.
2. **Stale dashboard scanner**: `scan_dashboards()` reads `dashboard.yaml` (legacy format). Should read `augur.yaml` (ADR-126).

### Page State Gap

No canonical page readiness state exists. Ad-hoc mechanisms approximate it:
- `maturity-utils.ts` — feature maturity, not page maturity
- Demo page — hardcoded `Readiness` type as mock visualization data
- `SkeletonCard` — loading placeholder

**Constraint**: Page `state` must not duplicate these existing mechanisms.

## Decision

### 1. Add Page Metadata to `augur.yaml`

Pages currently lack descriptions. Add three fields to `contributions.pages` entries:

```yaml
contributions:
  pages:
  - id: pipeline
    title: Pipeline
    icon: Briefcase
    order: 10
    # --- NEW ---
    purpose: "Track job applications from inbox through offer. Filter by status, sort by date, bulk-update stages."
    keywords: [jobs, applications, tracking, pipeline, inbox, offers, interviews]
    state: mature
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `purpose` | string | — | 1-2 sentences: what this page solves for users |
| `keywords` | string[] | `[]` | Additional search terms (jargon, synonyms) |
| `state` | enum | `dev` | `mock` = hardcoded/fake data, `dev` = functional with gaps, `mature` = production-ready |

### 2. Extend Project Indexer with 4 New Scan Functions

Add to `project_indexer.py`:

**`scan_pages(root)`** — reads `augur.yaml` `contributions.pages` entries:
```yaml
- type: page
  name: pipeline
  hub: career
  skill: career
  path: /career/pipeline
  title: Pipeline
  description: "Track job applications from inbox through offer..."   # from purpose
  tags: [jobs, applications, tracking, pipeline]                       # from keywords
  state: mature
```

**`scan_mcp_tools(root)`** — extracts tool names and docstrings via `ast` module (no imports, no runtime dependencies):
```yaml
- type: mcp-tool
  name: add-career-job
  skill: career
  path: plugins/career/skills/career/augur/mcp/__init__.py
  description: "Add a job URL to inbox for automatic parsing and tracking"  # from docstring
```

**`scan_actions(root)`** — reads `augur/data/actions/*.yaml`:
```yaml
- type: action
  name: scan-linkedin-jobs
  skill: career
  path: plugins/career/skills/career/augur/data/actions/scan-linkedin-jobs.yaml
  title: Scan LinkedIn
  description: "Search LinkedIn for jobs matching your profile using Bright Data"
  tags: [ide, career]   # dispatch mode + hub as tags
```

**`scan_commands(root)`** — reads `agent-workflows/*.md` frontmatter:
```yaml
- type: command
  name: dev-build
  path: plugins/ai/skills/ai_bridge/augur/data/agent-workflows/dev-build.md
  description: "Clean caches, rebuild UI, and validate pages for build issues"
  tags: [dev]   # visibility as tag
```

### 3. Fix Stale Project Index Paths

- **Indexer output**: write to `runtime/rag/project-index.yaml` (runtime data belongs in `runtime/`, not plugin `data/`)
- **Search routes**: read from `runtime/rag/project-index.yaml`
- **Remove**: stale `scan_dashboards()` that reads `dashboard.yaml` (replaced by `scan_pages()` which reads `augur.yaml`)

### 4. Update `build_index()` and Print Summary

```python
def build_index(root: Path) -> dict:
    skills = scan_skills(root)
    pages = scan_pages(root)
    mcp_tools = scan_mcp_tools(root)
    actions = scan_actions(root)
    commands = scan_commands(root)
    adrs = scan_adrs(root)
    agents = scan_agents(root)
    chains = scan_chains(root)

    all_entries = skills + pages + mcp_tools + actions + commands + adrs + agents + chains
    return {"version": 2, "indexed_at": ..., "entries": all_entries}
```

### 5. Add Type Colors to Search UI

In `PROJECT_TYPE_COLORS`:

```typescript
export const PROJECT_TYPE_COLORS: Record<string, string> = {
  // existing
  skill: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  adr: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  chain: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  agent: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  dashboard: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
  // new
  page: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  'mcp-tool': 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  action: 'bg-pink-500/20 text-pink-400 border-pink-500/30',
  command: 'bg-teal-500/20 text-teal-400 border-teal-500/30',
};
```

### 6. Extend TypeScript Types

In `src/dashboard/lib/plugin-runtime/types.ts`, add page metadata fields (assembly pass-through):

```typescript
// In the existing page contribution shape used by augur.yaml parsing
purpose?: string;
keywords?: string[];
state?: 'mock' | 'dev' | 'mature';
```

Update `assembleHubs()` in `copier.ts` to pass `purpose`, `keywords`, `state` through to `assembled-hubs.json` tab entries so the indexer (and any dashboard component) can read them.

## Consequences

**Positive:**
- "How do I add a job?" returns the page, MCP tool, and action — all from one search
- Zero new infrastructure — extends existing project indexer, search API, and UI
- MCP tool descriptions extracted from source (Python docstrings) — no dual maintenance
- Page `state` is declarative and canonical — single source of truth
- Project index version bumped to 2 with ~500 entries (up from ~200)

**Negative:**
- 29 `augur.yaml` files need `purpose`/`keywords`/`state` on ~60 page entries (one-time)
- AST-based docstring extraction is best-effort — tools with no docstring get indexed by name only
- Project index file grows ~3x (mitigated: still small YAML, search is instant)

**Neutral:**
- `maturity-utils.ts` unchanged (feature maturity, different domain)
- Existing 5 scan functions unchanged
- UnifiedSearcher unchanged — project index is a separate search path
- Action/command YAML schemas unchanged

## Implementation Order

```
Phase 1: Fix & Extend Indexer
├── Step 1: Fix output path → runtime/rag/project-index.yaml
├── Step 2: Fix search route read path → runtime/rag/project-index.yaml
├── Step 3: Add scan_pages() — reads augur.yaml contributions.pages
├── Step 4: Add scan_mcp_tools() — extracts docstrings via ast module
├── Step 5: Add scan_actions() — reads augur/data/actions/*.yaml
├── Step 6: Add scan_commands() — reads agent-workflows/*.md frontmatter
├── Step 7: Replace scan_dashboards() with scan_pages() in build_index()
└── Step 8: Bump version to 2, update print summary

Phase 2: Page Metadata (depends on Phase 1)
├── Step 9: Extend PageContribution type in types.ts
├── Step 10: Update assembleHubs() to pass through purpose/keywords/state
└── Step 11: Add purpose/keywords/state to all augur.yaml page entries

Phase 3: Search UI (depends on Phase 1)
└── Step 12: Add 4 type colors to PROJECT_TYPE_COLORS

Phase 4: Verification (depends on all)
├── Step 13: Run project_indexer.py, verify runtime/rag/project-index.yaml has all 9 types
├── Step 14: Search /api/knowledge/project-index/search?q=add+job — verify page + tool + action results
├── Step 15: npm run build + pytest tests/src/
└── Step 16: Remove stale scan_dashboards() references
```

## Alternatives Considered

### A. Generate Markdown Index + New RAG Scope (Previous ADR-173 Draft)
Create `capabilities-index.md`, add `capabilities` scope to UnifiedSearcher, new API endpoint. **Rejected**: builds parallel infrastructure when project indexer already handles typed entities with scored search. Markdown + ripgrep gives worse relevance than field-level scoring.

### B. Add MCP Tool Descriptions to `augur.yaml`
Change `mcp.tools` from bare strings to `{name, description}` objects. **Rejected**: creates dual maintenance — descriptions already exist in Python docstrings. AST extraction at index time is zero-maintenance.

### C. Centralized Capabilities Registry
Single YAML file listing all pages, tools, actions, commands. **Rejected**: violates Rule #1 (plugin decentralization).

## References

- ADR-085: Project indexer (Tier 2 RAG)
- ADR-087: Data directory elimination (stale `services/rag/` path origin)
- ADR-126: Generic plugin template (`augur.yaml` canonical config)
- ADR-128: Contribution model (`contributions.pages`)
- ADR-130: Action dispatch modes
- `plugins/ai/skills/knowledge/scripts/project_indexer.py`: Existing indexer
- `plugins/ai/skills/knowledge/augur/api/project-index/search/route.ts`: Search API
- `plugins/ai/skills/knowledge/augur/dashboard/search/components.tsx`: Search UI

## Impact Manifest

```yaml
impact:
  apis_changed:
    - function: build_index
      module: plugins/ai/skills/knowledge/scripts/project_indexer.py
      breaking: false
    - function: assembleHubs
      module: src/dashboard/scripts/mount/copier.ts
      breaking: false
  patterns_deprecated:
    - grep: "services/rag/project-index\\.yaml"
      replacement: "runtime/rag/project-index.yaml"
    - grep: "scan_dashboards"
      replacement: "scan_pages (reads augur.yaml instead of dashboard.yaml)"
  files_affected:
    - glob: "plugins/ai/skills/knowledge/scripts/project_indexer.py"
    - glob: "plugins/ai/skills/knowledge/augur/api/project-index/*/route.ts"
    - glob: "plugins/ai/skills/knowledge/augur/dashboard/search/components.tsx"
    - glob: "plugins/*/skills/*/augur.yaml"
    - glob: "src/dashboard/lib/plugin-runtime/types.ts"
    - glob: "src/dashboard/scripts/mount/copier.ts"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-173: Unified Capabilities Search — Extend Project Index with Pages, Tools, Actions, Commands**.

Read the full ADR: `docs/decisions/ADR-173-page-metadata-rag-index.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-173-capabilities", description="Implementing ADR-173: Unified Capabilities Search")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-173-capabilities", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-173 team.
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

**Team name**: `adr-173-capabilities`

#### Phase 1: Fix & Extend Indexer
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Fix output path: write to `runtime/rag/project-index.yaml`. Fix read path in both search and stats route source files. Ensure `runtime/rag/` dir is created. | `plugins/ai/skills/knowledge/scripts/project_indexer.py`, `plugins/ai/skills/knowledge/augur/api/project-index/search/route.ts`, `plugins/ai/skills/knowledge/augur/api/project-index/stats/route.ts` |
| 1.2 | developer | medium | Add `scan_pages(root)`: read all `plugins/*/skills/*/augur.yaml`, parse `contributions.pages`, emit entries with `type: page, name, hub, skill, path (route), title, description (from purpose), tags (from keywords), state`. Handle skills with and without `hub.id` (primary vs extension routing). | `plugins/ai/skills/knowledge/scripts/project_indexer.py` |
| 1.3 | developer | medium | Add `scan_mcp_tools(root)`: for each `plugins/*/skills/*/augur/mcp/__init__.py`, use `ast.parse()` + `ast.get_docstring()` on async function defs decorated with `@mcp.tool()`. Extract tool name from decorator `name=` kwarg, description from docstring first line. Emit `type: mcp-tool, name, skill, path, description`. | `plugins/ai/skills/knowledge/scripts/project_indexer.py` |
| 1.4 | developer | medium | Add `scan_actions(root)`: glob `plugins/*/skills/*/augur/data/actions/*.yaml`, parse YAML, emit `type: action, name (id), skill, path, title (label), description, tags [dispatch, hub]`. Skip files failing validation (missing id/description). | `plugins/ai/skills/knowledge/scripts/project_indexer.py` |
| 1.5 | developer | medium | Add `scan_commands(root)`: glob `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/*.md`, parse frontmatter, emit `type: command, name (stem), path, description, tags [visibility]`. Skip `commands.md` (meta-command). | `plugins/ai/skills/knowledge/scripts/project_indexer.py` |
| 1.6 | developer | low | Update `build_index()`: replace `scan_dashboards()` with `scan_pages()`, add `scan_mcp_tools()`, `scan_actions()`, `scan_commands()`. Bump version to 2. Update print summary. | `plugins/ai/skills/knowledge/scripts/project_indexer.py` |

#### Phase 2: Page Metadata Population (depends on Phase 1)
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer-a | medium | Extend `PageContribution` type in types.ts with `purpose?: string`, `keywords?: string[]`, `state?: 'mock' \| 'dev' \| 'mature'`. Update `assembleHubs()` in copier.ts to pass through these fields to assembled-hubs.json tab entries. | `src/dashboard/lib/plugin-runtime/types.ts`, `src/dashboard/scripts/mount/copier.ts` |
| 2.2 | developer-b | medium | Add `purpose`, `keywords`, `state` to all page entries in augur.yaml for bundles: ai, career, admin, finance, health, productivity. Write purpose as user-facing search text (what problem does this page solve?). Assess state honestly: `mock` if hardcoded data, `dev` if functional but incomplete, `mature` if production-ready. | `plugins/{ai,career,admin,finance,health,productivity}/skills/*/augur.yaml` |
| 2.3 | developer-c | medium | Add `purpose`, `keywords`, `state` to all page entries in augur.yaml for bundles: consulting, enterprise, home, lifestyle, observability, professional, dev. Same rules as step 2.2. | `plugins/{consulting,enterprise,home,lifestyle,observability,professional,dev}/skills/*/augur.yaml` |

#### Phase 3: Search UI Colors (depends on Phase 1)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | low | Add 4 type color entries to `PROJECT_TYPE_COLORS` in search components: `page` (blue), `mcp-tool` (orange), `action` (pink), `command` (teal). | `plugins/ai/skills/knowledge/augur/dashboard/search/components.tsx` |

#### Phase 4: Verification (depends on Phase 2 + Phase 3)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | validator | low | Run `python3 plugins/ai/skills/knowledge/scripts/project_indexer.py` and verify `runtime/rag/project-index.yaml` contains all 9 types (skill, page, mcp-tool, action, command, adr, agent, chain, dashboard removal OK) |  |
| 4.2 | validator | low | Run `npm run build` and `pytest tests/src/` — verify no regressions |  |
| 4.3 | validator | low | Run `npm run mount-plugins` and verify assembled-hubs.json tab entries include purpose/keywords/state fields |  |
| 4.4 | architect | low | Verify ADR intent: search `?q=add+job` returns cross-category results. No new centralized config files. No new scopes in UnifiedSearcher. Page state is the only readiness source. Stale `services/rag/` path references are gone. |  |

### Stale Path Scan

This ADR renames `services/rag/project-index.yaml` → `runtime/rag/project-index.yaml`. Final verification MUST include:

```bash
python3 .github/scripts/scan_stale_paths.py --ci
```

### Completion Criteria
- [ ] All phases executed
- [ ] `runtime/rag/project-index.yaml` generated with ~500 entries across 8 types
- [ ] Project index search returns cross-category results for capability queries
- [ ] All augur.yaml page entries have `purpose` and `state` fields
- [ ] `assembled-hubs.json` tabs include `purpose`, `keywords`, `state`
- [ ] Search UI renders 4 new type badges with distinct colors
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Stale path scanner clean (no `services/rag/` references)
- [ ] ADR status updated to "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-173-page-metadata-rag-index.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
