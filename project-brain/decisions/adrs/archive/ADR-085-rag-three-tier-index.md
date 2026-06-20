---
status: Implemented
date: '2026-02-12'
deciders:
- Core team
related:
- ADR-004 (Markdown RAG)
- ADR-033 (RAG Search Hardening)
- ADR-028 (Two-Layer Memory)
- ADR-082 (Knowledge Hardening)
- ADR-083 (Plugin Data Colocation)
hub: null
tags:
- rag
- three
- tier
- index
- memory
superseded_by: null
---

# ADR-085: RAG Three-Tier Index — Memory, Project, and External Files

## Context

The Knowledge hub currently has a functioning Memory tier (decisions, patterns, preferences from `data/memory/`) and a dormant RAG project system (`plugins/ai/skills/knowledge/data/rag/`) that's wired but empty. The dashboard shows working memory stats (89 decisions, 18 patterns) but the Documents, Index, and Sources tabs are all empty because there's no data flowing into the other two tiers.

### Current State

| Component | Status | Data |
|-----------|--------|------|
| Memory search (`/api/knowledge/memory/search`) | Working | 89 decisions, 18 patterns, 11 preferences |
| Memory stats/config/curate | Working | Daily logs, MEMORY.md parsing |
| RAG projects (`/api/knowledge/projects`) | Wired, empty | No projects created |
| Sources (`/api/knowledge/sources`) | Wired, empty | `[]` |
| Document search (`/api/knowledge/search`) | Wired, errors | Python subprocess can't find RAG module |
| OCR (`/knowledge/ocr`) | UI only | Upload form placeholder |
| Index (`/knowledge/index`) | Shows config | 0 indexed items, 0 linked folders |

### The Three Use Cases

**Tier 1 — Memory** (existing, working):
Session memory analysis. Decisions, patterns, preferences extracted from MEMORY.md and daily logs. Searched via ripgrep. Already functional.

**Tier 2 — Project Index** (missing):
Index the Augur project itself. Users need to find: "which skill handles email?", "where is finance data stored?", "what chains exist for career?", "what does ADR-033 say?". Currently this requires manual grep. The project has 35 skills, 33 chains, 84 ADRs, 25 dashboard configs — all searchable text that should be one query away.

**Tier 3 — External Files Metadata** (missing):
User documents linked from specific hubs. Finance hub users track Excel spreadsheets. Health hub users store medical PDFs. Career hub users keep contracts and offer letters. These files live on the user's filesystem — the RAG system needs to index their metadata (path, name, type, size, linked hub, added date) and optionally OCR/extract text content for search.

### What Exists but Isn't Connected

The RAG project system (`rag-projects.ts`) already supports:
- Creating named projects with settings
- Adding file/directory sources to projects
- Per-project `sources.yaml`, `settings.yaml`
- Indexing scripts (`index_docs.py`, `batch_index.py`)

But nothing creates the initial projects, nothing links projects to hubs, and the dashboard tabs that would show this data are empty.

## Decision

### Architecture: Three Tiers Under One Roof

```
Knowledge Hub
├── Tier 1: Memory Index (existing)
│   ├── Source: data/memory/MEMORY.md + data/memory/daily/*.md
│   ├── Search: ripgrep on memory dir
│   ├── API: /api/knowledge/memory/*
│   └── UI: /knowledge/memory
│
├── Tier 2: Project Index (new)
│   ├── Source: plugins/**/SKILL.md, dashboard.yaml, chains/*.yaml, docs/decisions/*.md
│   ├── Search: ripgrep on project dirs
│   ├── API: /api/knowledge/project-index/*
│   └── UI: /knowledge/index (enhanced)
│
└── Tier 3: External Files (new)
    ├── Source: user-linked files from any hub (~/Documents/*.pdf, ~/Finance/*.xlsx)
    ├── Search: metadata YAML + optional OCR text
    ├── API: /api/knowledge/sources + /api/knowledge/projects/*
    └── UI: /knowledge/documents (enhanced)
```

### Component 1: Project Index (Tier 2)

Auto-index the Augur project to make skills, chains, ADRs, and configs searchable.

**What gets indexed:**

| Source | Pattern | Fields Extracted |
|--------|---------|-----------------|
| Skills | `plugins/*/skills/*/SKILL.md` | name, description, bundle, capabilities |
| Dashboard configs | `plugins/*/skills/*/dashboard.yaml` | hub id, title, tabs, actions, MCP tools |
| Chains | `plugins/*/skills/*/chains/*.yaml` | chain_id, name, steps, agents |
| ADRs | `docs/decisions/ADR-*.md` | number, title, status, date, related |
| Agent profiles | `.claude/agents/*.md` | name, role, iron laws |
| Data configs | `config/**/*.yaml` | config keys and values |

**New API: `/api/knowledge/project-index`**

```typescript
// GET /api/knowledge/project-index/stats
// Returns: { skills: 35, chains: 33, adrs: 84, configs: N, lastIndexed: ISO }

// GET /api/knowledge/project-index/search?q=email&type=skill
// Returns: [{ type: "skill", name: "apple", path: "...", snippet: "...", relevance: 0.8 }]

// POST /api/knowledge/project-index/rebuild
// Triggers re-scan of all project files
```

**New files:**
- `plugins/ai/skills/knowledge/api/project-index/stats/route.ts`
- `plugins/ai/skills/knowledge/api/project-index/search/route.ts`
- `plugins/ai/skills/knowledge/api/project-index/rebuild/route.ts`
- `plugins/ai/skills/knowledge/scripts/project_indexer.py` — Scans project, builds `plugins/ai/skills/knowledge/data/rag/project-index.yaml`

**Index format** (`plugins/ai/skills/knowledge/data/rag/project-index.yaml`):
```yaml
version: 1
indexed_at: "2026-02-12T10:00:00Z"
entries:
  - type: skill
    name: apple
    bundle: services
    path: plugins/productivity/skills/apple/SKILL.md
    title: "Apple Integration"
    description: "Email, calendar, reminders, voice memos"
    tags: [email, calendar, reminders]
  - type: adr
    name: ADR-004
    path: docs/decisions/ADR-004-markdown-rag.md
    title: "Markdown RAG over Vector Databases"
    status: Implemented
    date: "2025-01-08"
  - type: chain
    name: knowledge_capture
    path: plugins/ai/skills/knowledge/chains/knowledge_capture.yaml
    steps: 3
```

**Search implementation:** Ripgrep for full-text search across indexed source files + YAML metadata lookup for structured queries (type filter, bundle filter).

### Component 2: External Files Registry (Tier 3)

Enable hubs to register external user files with metadata.

**How it works:**
1. Each hub can register external files via the existing RAG project system
2. A RAG project is auto-created per hub when the first file is linked (e.g., project `finance-docs`, `health-docs`)
3. Files are registered as sources in the project's `sources.yaml`
4. Metadata (name, type, size, hub, tags) stored in a per-project `metadata.yaml`
5. Optional: OCR/text extraction stores searchable content in `_indexed/` alongside the metadata

**Hub-to-project mapping:**

| Hub | Auto-Created Project | Typical Files |
|-----|---------------------|---------------|
| Finance | `finance-docs` | Spreadsheets, bank statements, tax forms |
| Health | `health-docs` | Medical reports, lab results, prescriptions |
| Career | `career-docs` | Contracts, offer letters, resumes |
| Lifestyle | `lifestyle-docs` | Recipes (PDF), travel docs |
| Any hub | `{hub}-docs` | Auto-created on first file link |

**New API: `/api/knowledge/hub-files`**

```typescript
// POST /api/knowledge/hub-files
// Body: { hub: "finance", path: "/Users/.../taxes-2025.xlsx", tags: ["tax", "2025"] }
// Creates finance-docs project if needed, adds source, indexes metadata

// GET /api/knowledge/hub-files?hub=finance
// Returns: [{ name: "taxes-2025.xlsx", path: "...", type: "xlsx", size: 45000, hub: "finance", added_at: "...", tags: ["tax"] }]

// GET /api/knowledge/hub-files/stats
// Returns: { totalFiles: 12, byHub: { finance: 5, health: 4, career: 3 }, totalSizeMb: 23.4 }

// DELETE /api/knowledge/hub-files
// Body: { hub: "finance", path: "/Users/.../taxes-2025.xlsx" }
// Removes source and metadata
```

**New files:**
- `plugins/ai/skills/knowledge/api/hub-files/route.ts` — GET (list), POST (add), DELETE (remove)
- `plugins/ai/skills/knowledge/api/hub-files/stats/route.ts` — Aggregated stats
- `plugins/ai/skills/knowledge/scripts/file_metadata_extractor.py` — Extract metadata from files (size, type, page count for PDFs, sheet names for Excel)

**Metadata format** (per project, e.g. `plugins/ai/skills/knowledge/data/rag/projects/finance-docs/metadata.yaml`):
```yaml
version: 1
hub: finance
files:
  - path: /Users/gur/Documents/taxes-2025.xlsx
    name: taxes-2025.xlsx
    type: xlsx
    size_bytes: 45000
    added_at: "2026-02-12T10:00:00Z"
    tags: [tax, "2025"]
    extracted:
      sheet_names: [Summary, Income, Expenses]
  - path: /Users/gur/Documents/bank-statement-jan.pdf
    name: bank-statement-jan.pdf
    type: pdf
    size_bytes: 120000
    added_at: "2026-02-12T10:00:00Z"
    tags: [bank, january]
    extracted:
      page_count: 3
      ocr_indexed: true
```

### Component 3: Unified Dashboard Wiring

Connect all three tiers to the existing dashboard pages.

**Overview page (`/knowledge`):**
Currently shows memory stats. Add tier summary cards:
- Memory: 89 decisions, 18 patterns (existing)
- Project: 35 skills, 33 chains, 84 ADRs indexed
- External: N files across M hubs, total size

**Index page (`/knowledge/index`):**
Currently shows RAG config. Enhance to show:
- Project Index stats and last indexed time
- "Rebuild Project Index" button
- Browse indexed skills/chains/ADRs by type
- Quick search within project index

**Documents page (`/knowledge/documents`):**
Currently empty. Wire to show:
- External files grouped by hub
- Add file button (opens file picker, asks which hub)
- File metadata cards (name, type, size, tags, hub)
- Remove file button

**Search page (`/knowledge/search`):**
Currently has Memory and Documents modes. Add Project mode:
- Memory mode: searches `data/memory/` (existing)
- Project mode: searches skills, chains, ADRs, configs
- Documents mode: searches external file metadata + OCR content
- All mode: searches across all three tiers

### Component 4: Cross-Hub File Linking

Allow other hubs to link files to the Knowledge hub.

**Integration point:** Each hub's dashboard.yaml can declare `external_files: true` to show a "Link to Knowledge" action on file-related pages.

**Implementation:** Hub pages call `/api/knowledge/hub-files` POST with their hub ID to register files. The Knowledge hub's Documents tab shows all files grouped by source hub.

**Example flow:**
1. User is on Finance hub, has an Excel spreadsheet open
2. Clicks "Add to Knowledge Base" action button
3. Finance page calls `POST /api/knowledge/hub-files { hub: "finance", path: "/path/to/file.xlsx" }`
4. Knowledge hub now shows this file in Documents tab under "Finance" folder
5. File is searchable from Knowledge search page

## Consequences

### Positive

- **Complete knowledge coverage**: All three data tiers (memory, project structure, external files) searchable from one place
- **Zero-config project index**: Auto-indexes the Augur project — no manual source linking needed
- **Hub-aware file management**: Files naturally organized by domain (finance, health, career)
- **Existing infrastructure reuse**: RAG projects, sources.yaml, ripgrep search — all already built
- **Incremental adoption**: Each tier is independent. Memory already works, Project Index adds value immediately, External Files grow as users link files

### Negative

- **Project Index re-scan cost**: Scanning 35 plugins + 84 ADRs takes a few seconds. Mitigated by caching in `project-index.yaml` and only rebuilding on demand or nightly
- **External files trust model**: We store paths to user files but don't copy them. If user moves/deletes a file, the metadata becomes stale. Mitigated by a "verify paths" button that checks `fs.existsSync`
- **Dashboard complexity**: Three tiers means more cards, more tabs, more data on the overview. Mitigated by progressive disclosure (collapsed sections, "show more" links)

### Neutral

- Memory tier is unchanged — no migration
- Existing RAG project system is reused, not replaced
- OCR infrastructure (Tesseract) remains optional, only used for Tier 3 PDFs/images

## Implementation Order

```
Phase 1: Project Index (Tier 2)
├── Step 1.1: Create project_indexer.py — scan skills, chains, ADRs, configs → project-index.yaml
├── Step 1.2: Create API routes — stats, search, rebuild
├── Step 1.3: Enhance Index page — show project index stats, browse, search
└── Step 1.4: Add "Project" mode to Search page

Phase 2: External Files Registry (Tier 3)
├── Step 2.1: Create hub-files API routes — GET, POST, DELETE, stats
├── Step 2.2: Create file_metadata_extractor.py — extract type, size, page count, sheet names
├── Step 2.3: Enhance Documents page — show hub-grouped files, add/remove buttons
└── Step 2.4: Wire OCR page to Tier 3 — OCR results stored as extracted text in metadata

Phase 3: Unified Dashboard (All Tiers)
├── Step 3.1: Enhance Overview page — three-tier summary cards
├── Step 3.2: Enhance Search page — "All" mode searches all three tiers
└── Step 3.3: Add cross-hub file linking — action button in hub dashboard.yaml files

Phase 4: Verification
├── Step 4.1: Run all tests, verify no regressions
├── Step 4.2: npm run build passes
└── Step 4.3: Browser verification — all pages render, APIs return real data
```

## Alternatives Considered

### Alternative 1: Single Monolithic Index for All Three Tiers

Build one giant index that mixes memory entries, project files, and external documents.

**Rejected because**: The three tiers have fundamentally different update frequencies (memory: every commit, project: on rebuild, external: on user action), different schemas (decisions vs skills vs PDFs), and different access patterns. Separate indices allow independent rebuild and targeted search.

### Alternative 2: Use the Existing RAG Project System for All Three Tiers

Create RAG projects for memory, project index, and external files — all using `rag-projects.ts`.

**Rejected because**: Memory already has its own dedicated search infrastructure (stats, daily-logs, categories, profile). Forcing it through the RAG project abstraction would add indirection without benefit. The RAG project system is appropriate for Tier 3 (external files) where per-hub project isolation makes sense, but not for Tier 1 (memory) or Tier 2 (project index) which are single-instance.

### Alternative 3: Use a Database (SQLite/DuckDB) Instead of YAML Index Files

Store all three tiers in a structured database for faster queries.

**Rejected because**: Violates ADR-004 (zero infrastructure, human-readable, git-trackable). YAML + ripgrep is sufficient for the scale we operate at (< 100K entries across all tiers).

## References

- [ADR-004](./ADR-004-markdown-rag.md) — Markdown RAG over Vector Databases (foundational architecture)
- [ADR-028](./ADR-028-two-layer-memory-architecture.md) — Two-Layer Memory Architecture (Tier 1 foundation)
- [ADR-033](./ADR-033-rag-search-hardening.md) — RAG Search Hardening (security fixes, unified search)
- [ADR-082](./ADR-082-knowledge-hardening.md) — Knowledge Hub Hardening (dashboard improvements)
- [ADR-083](./ADR-083-plugin-data-colocation.md) — Plugin Data Colocation (data directory structure)
- `plugins/ai/skills/knowledge/` — Knowledge plugin source
- `plugins/ai/skills/knowledge/lib/rag-projects.ts` — Existing RAG project service
- `plugins/ai/skills/knowledge/scripts/index_docs.py` — Existing indexer
- `plugins/ai/skills/knowledge/data/rag/` — RAG data directory

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-085: RAG Three-Tier Index**.

Read the full ADR: `docs/decisions/ADR-085-rag-three-tier-index.md`

### Offload Protocol (ADR-054)

Before dispatching each step, check if it can be offloaded to a cheap CLI:

1. Read offload config: `cat config/system/llm.yaml` → look for `offload:` section
2. If `offload.enabled: true` AND the step's tier is `low`:
   ```bash
   python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py \
     --task "STEP DESCRIPTION" \
     --files "TARGET_FILE_1,TARGET_FILE_2" \
     --context-files "REFERENCE_FILE_FOR_PATTERNS" \
     --work-dir $(pwd)
   ```
3. Review the JSON output — check `success`, `files_changed`, and `diff` fields
4. Record the verdict:
   - Accept (diff is correct): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict accept`
   - Fix (you patched the output): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict fix`
   - Escalate (offload failed, you did it yourself): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict escalate`
5. If `offload.enabled: false` OR tier is `medium`/`high` → do the step yourself as normal

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-085-rag-tiers", description="Implementing ADR-085: RAG Three-Tier Index")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-085-rag-tiers", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-085-rag-tiers team.
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

**Team name**: `adr-085-rag-tiers`

#### Phase 1: Project Index (Tier 2)
**Strategy**: PARALLEL (steps 1.1-1.2 have no dependencies; 1.3-1.4 depend on 1.1+1.2)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create `project_indexer.py` — scan `plugins/*/skills/*/SKILL.md`, `plugins/*/skills/*/dashboard.yaml`, `plugins/*/skills/*/chains/*.yaml`, `docs/decisions/ADR-*.md`, `.claude/agents/*.md`. Output `plugins/ai/skills/knowledge/data/rag/project-index.yaml` with entries typed as skill/adr/chain/config/agent. Use `getDataDir()` pattern for path resolution. | `plugins/ai/skills/knowledge/scripts/project_indexer.py`, `plugins/ai/skills/knowledge/data/rag/project-index.yaml` |
| 1.2 | developer | medium | Create 3 API routes: `project-index/stats/route.ts` (GET — reads project-index.yaml, returns counts by type), `project-index/search/route.ts` (GET — `?q=email&type=skill` — ripgrep on source files + YAML metadata filter), `project-index/rebuild/route.ts` (POST — runs `project_indexer.py` via subprocess). Use `getDataDir()`/`getProjectRoot()` function pattern, not module-level constants. | `plugins/ai/skills/knowledge/api/project-index/stats/route.ts`, `plugins/ai/skills/knowledge/api/project-index/search/route.ts`, `plugins/ai/skills/knowledge/api/project-index/rebuild/route.ts` |
| 1.3 | developer | medium | Enhance Index page (`plugins/ai/skills/knowledge/augur/index/page.tsx`) — add Project Index section with stats (skills count, chains count, ADRs count), "Rebuild Project Index" button calling `/api/knowledge/project-index/rebuild`, and a searchable list of indexed entries by type. Keep existing RAG config section. | `plugins/ai/skills/knowledge/augur/index/page.tsx` |
| 1.4 | developer | medium | Add "Project" search mode to Search page (`plugins/ai/skills/knowledge/augur/search/page.tsx`) — new mode button alongside Memory/Documents, calls `/api/knowledge/project-index/search`, displays results as typed cards (Skill/ADR/Chain). | `plugins/ai/skills/knowledge/augur/search/page.tsx` |

#### Phase 2: External Files Registry (Tier 3)
**Strategy**: PARALLEL (steps 2.1-2.2 independent; 2.3-2.4 depend on 2.1+2.2)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create hub-files API routes: `hub-files/route.ts` (GET list by hub, POST add file with hub+path+tags, DELETE remove), `hub-files/stats/route.ts` (GET aggregated stats by hub). Auto-create RAG project `{hub}-docs` on first POST via `createRagProject()` from `@/lib/plugins/ai/rag-projects`. Store metadata in per-project `metadata.yaml`. Use `getDataDir()` pattern. | `plugins/ai/skills/knowledge/api/hub-files/route.ts`, `plugins/ai/skills/knowledge/api/hub-files/stats/route.ts` |
| 2.2 | developer | medium | Create `file_metadata_extractor.py` — given a file path, extract: name, type (extension), size, and type-specific fields (PDF page count via `PyPDF2` or subprocess `mdls`, Excel sheet names via `openpyxl` or `xlrd`). Return JSON. Fail gracefully if optional deps missing — always return at least name/type/size. | `plugins/ai/skills/knowledge/scripts/file_metadata_extractor.py` |
| 2.3 | developer | medium | Enhance Documents page (`plugins/ai/skills/knowledge/augur/documents/page.tsx`) — fetch from `/api/knowledge/hub-files/stats` for overview, `/api/knowledge/hub-files?hub=all` for file list. Group files by hub. Add "Link File" button that opens a form (hub selector + file path input + tags). Show file cards with metadata (type badge, size, hub, date). | `plugins/ai/skills/knowledge/augur/documents/page.tsx` |
| 2.4 | developer | low | Wire OCR page's upload result to Tier 3 — after OCR succeeds, auto-register the file via `POST /api/knowledge/hub-files` with hub="ocr" and the extracted text stored in metadata. | `plugins/ai/skills/knowledge/augur/ocr/page.tsx` |

#### Phase 3: Unified Dashboard
**Strategy**: PIPELINE (depends on Phase 1 + Phase 2)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Enhance Overview page (`plugins/ai/skills/knowledge/augur/page.tsx`) — add three-tier summary: Memory section (existing stats), Project Index section (fetch from `/api/knowledge/project-index/stats`), External Files section (fetch from `/api/knowledge/hub-files/stats`). Each section shows key counts and a "View" link to the relevant tab. | `plugins/ai/skills/knowledge/augur/page.tsx` |
| 3.2 | developer | medium | Enhance Search page "All" mode — when mode is "all", also search project index (`/api/knowledge/project-index/search`) alongside memory and documents. Merge results with source labels (Memory/Project/Document). | `plugins/ai/skills/knowledge/augur/search/page.tsx` |
| 3.3 | developer | low | Update `dashboard.yaml` — add `project-index` to `mcp_tools` list, add "Rebuild Project Index" action button, add hub-files action for cross-hub linking. | `plugins/ai/skills/knowledge/augur.yaml` |

#### Phase 4: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 4.1 | validator | low | Run `npm run build` in `src/dashboard/`, verify zero errors |
| 4.2 | validator | low | Run `python3 plugins/ai/skills/knowledge/scripts/project_indexer.py` and verify it produces valid `project-index.yaml` |
| 4.3 | validator | low | Curl all new API endpoints and verify real data: `project-index/stats`, `project-index/search?q=career`, `hub-files/stats` |
| 4.4 | validator | low | Verify ADR intent — all three tiers searchable from Knowledge hub, Overview shows all three, Search page has all modes |

### Completion Criteria
- [ ] Project indexer scans all skills/chains/ADRs and produces `project-index.yaml`
- [ ] Project index API returns real stats (35 skills, 33 chains, etc.)
- [ ] Project index search returns relevant results for "email", "career", "calendar"
- [ ] Hub-files API accepts POST with hub+path, returns file list, aggregates stats
- [ ] Documents page shows files grouped by hub (even if only test files initially)
- [ ] Overview page shows three-tier summary with real numbers
- [ ] Search page has Memory/Project/Documents/All modes all functional
- [ ] `npm run build` passes
- [ ] All pre-existing tests still pass

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr ADR-085

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
