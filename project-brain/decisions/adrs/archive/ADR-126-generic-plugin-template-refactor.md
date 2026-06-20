---
status: Implemented
date: '2026-02-19'
deciders:
- Project team
related:
- ADR-040 (Portable Plugin Template Standard)
- ADR-105 (Hub-Driven Plugin Architecture)
- ADR-109 (Filesystem-Driven Dashboard)
- ADR-112 (Plugin Completeness)
- ADR-121 (Hub Ownership)
- ADR-122 (Plugin Lifecycle)
hub: null
tags:
- generic
- plugin
- template
- refactor
- claude
superseded_by: null
---

# ADR-126: Generic Plugin Template Refactor — Claude-Native Skill Standard

**Priority**: Critical — foundational to Augur's plugin architecture
**Supersedes**: ADR-040 (Portable Plugin Template Standard)

## Context

Augur has 50+ skills across 17 hubs. The current plugin format is Augur-proprietary: `dashboard.yaml`, `chains/` YAML workflows, custom `SKILL.md` frontmatter extensions, and Augur-specific directory conventions. This creates three fundamental problems:

**1. Not installable in Claude Code.** Claude's official skill format (per Anthropic's "Complete Guide to Building Skills for Claude") is: `SKILL.md` with YAML frontmatter + optional `scripts/`, `references/`, `assets/` directories. Augur skills cannot be installed into Claude Code, Claude.ai, or the Claude API without extensive manual conversion. The Claude skill standard is an open standard — skills should work across platforms.

**2. Chains are a proprietary dead end.** Augur's `chains/` directory contains YAML workflow definitions with custom syntax. Claude's skill guide shows that orchestration belongs directly in `SKILL.md` using markdown workflow steps with `Call MCP tool:` references. This is the industry-standard pattern: sequential workflows, multi-MCP coordination, iterative refinement, context-aware tool selection, and domain-specific intelligence — all expressed as structured markdown instructions that Claude natively understands. Chains duplicate what SKILL.md already handles better.

**3. Internal vs external dependencies are different.** Currently, depending on another Augur plugin uses `dependencies.plugins: [knowledge]` (a proprietary mechanism), while depending on an external service uses `mcp_servers: [context7]`. This distinction is artificial. If every skill exposes its capabilities through MCP tools, then depending on `knowledge` should work the same way as depending on `github` or `linear` — you call their MCP tools. The dependency boundary should be MCP, not import paths.

**Additional problems from original analysis:**
- 80% boilerplate in dashboard pages, API routes, and MCP tools
- 60-80% of code is copy-pasted structural duplication across all skills
- No src/lib runtime library — each skill reinvents `_read_yaml()`, `useEntityData()`, error boundaries
- Hardening audit flags identical structural issues in every unhardened skill

## Decision

Refactor every Augur plugin to be a **standard Claude skill first**, with Augur-specific extensions in a cleanly separable layer. The base skill works natively in Claude Code. The Augur layer adds dashboard UI, hub assignment, and enhanced orchestration.

### Part 1: Adopt Claude's Standard Skill Format as the Base

Every Augur skill's base layer is 100% compatible with Claude's skill standard:

```
my-skill/
├── SKILL.md              # Required — instructions + orchestration + frontmatter
├── scripts/              # Optional — executable code (Python, Bash, etc.)
│   ├── process_data.py
│   └── validate.sh
├── references/           # Optional — documentation loaded on demand
│   ├── api-patterns.md
│   └── data-schema.md
└── assets/               # Optional — templates, icons, etc.
    └── report-template.md
```

**SKILL.md frontmatter** follows Claude's standard exactly:

```yaml
---
name: health-tracker
description: >
  Personal health tracking and symptom management. Use when user mentions
  "symptoms", "medications", "health log", "track health", or "health report".
  Manages symptom logging, medication tracking, and generates health summaries.
license: MIT
compatibility: Requires MCP server with health data access. Works with any YAML-based data store.
metadata:
  author: Augur
  version: 1.0.0
  mcp-server: augur
---
```

**Field compliance with Claude's standard:**
- `name`: kebab-case, matches folder name — **required**
- `description`: what it does + when to trigger + key capabilities — **required**, under 1024 chars
- `license`: MIT, Apache-2.0, etc. — **optional but encouraged**
- `compatibility`: environment requirements — **optional**
- `metadata`: custom key-value pairs (author, version, mcp-server) — **optional**

**Security restrictions respected:**
- No XML angle brackets in frontmatter
- No "claude" or "anthropic" in skill name

### Part 2: SKILL.md Orchestration Replaces Chains

All workflow orchestration moves from `chains/*.yaml` into SKILL.md using Claude's native patterns. The `chains/` directory is eliminated.

**Pattern 1 — Sequential Workflow (replaces linear chains):**

```markdown
## Workflow: Log New Symptom

### Step 1: Validate Input
Call MCP tool: `validate-symptom-data`
Parameters: name, severity (1-10), notes (optional)
If validation fails, ask user to correct the input.

### Step 2: Store Symptom
Call MCP tool: `add-symptom`
Parameters: name, severity, notes, date (auto-generated)
Wait for: confirmation of storage

### Step 3: Update Health Score
Call MCP tool: `calculate-health-score`
Parameters: include latest symptom data
Result: Updated health score

### Step 4: Notify If Critical
IF severity >= 8:
  Call MCP tool: `send-notification`
  Parameters: type=critical, message="High severity symptom logged"
```

**Pattern 2 — Multi-MCP Coordination (replaces cross-skill chains):**

```markdown
## Workflow: Weekly Health Report

### Phase 1: Gather Data (Health MCP)
1. Call MCP tool: `get-symptoms` — fetch last 7 days
2. Call MCP tool: `get-medications` — fetch active medications
3. Call MCP tool: `get-health-score` — current composite score

### Phase 2: Enrich with Context (Knowledge MCP)
1. Call MCP tool: `semantic-search` — find relevant health articles
2. Call MCP tool: `get-user-context` — retrieve health goals

### Phase 3: Generate Report
1. Synthesize data from Phase 1 and Phase 2
2. Run `scripts/generate_report.py` with collected data
3. Save to temporary file

### Phase 4: Deliver
Based on user preference:
- Call MCP tool: `send-email` (Google Workspace MCP) — if email preferred
- Call MCP tool: `create-document` (Google Workspace MCP) — if doc preferred
- Display inline — if chat preferred
```

**Pattern 3 — Context-Aware Tool Selection (replaces conditional chains):**

```markdown
## Workflow: Store Health Data

### Decision Tree
1. Check data type and size
2. Determine best storage:
   - Structured data (symptoms, meds): Call MCP tool: `store-yaml-data`
   - Large datasets (> 1000 records): Call MCP tool: `store-sqlite-data`
   - Temporary analysis results: Save to local file via scripts/

### Provide Context to User
Explain why that storage method was chosen.
```

**Key insight from Claude's guide:** Orchestration via structured markdown in SKILL.md is more powerful than YAML chain files because:
- Claude natively understands markdown workflow steps
- Steps can reference ANY available MCP tool (internal or external)
- Conditional logic, error handling, and rollback are expressed in natural language
- No custom parser needed — Claude's instruction-following handles it
- Progressive disclosure: orchestration loads only when the skill activates

### Part 3: Unified MCP Dependency Model

All dependencies — internal Augur skills and external MCP servers — use the same abstraction: **MCP tool calls**. There is no `dependencies.plugins` field. There is no distinction between "internal" and "external".

**Before (Augur-proprietary):**
```yaml
# Old SKILL.md frontmatter — two different dependency mechanisms
dependencies:
  plugins: [knowledge, google-workspace]    # Internal — proprietary
  mcp_servers: [context7, brightdata]       # External — different format
  python: [requests]
  cli: [{id: gh, check: "gh --version"}]
```

**After (unified MCP):**
```markdown
## Dependencies

This skill requires the following MCP tools to be available:

### Required MCP Tools
- `semantic-search` — For knowledge retrieval (provided by knowledge skill or any search MCP)
- `get-symptoms`, `add-symptom` — Core health data operations (provided by this skill's MCP server)

### Optional MCP Tools
- `send-email`, `create-document` — For report delivery (provided by Google Workspace MCP)
- `search-web` — For health article enrichment (provided by any web search MCP)

### Scripts Dependencies
- Python 3.9+ with plugins: `pyyaml`, `requests`
- Install: `pip install -r scripts/requirements.txt`

### Environment
- Augur MCP server must be running for core data tools
- Google Workspace MCP server optional for email/doc delivery

## Common Issues

### MCP Tool Not Found
If a required tool is unavailable:
1. Check MCP server is running: verify in Claude settings
2. The skill will degrade gracefully — features requiring missing tools will be skipped
3. Core functionality (symptom logging) works with local storage fallback
```

**Why this matters:**
- A skill that needs `semantic-search` doesn't care if it comes from Augur's `knowledge` plugin or from an external search MCP server
- Dependencies are expressed as **capabilities needed** (tool names), not **implementations required** (plugin names)
- The skill remains self-contained: it describes what it needs, not where to get it
- If installed in Claude Code without Augur, the user connects whatever MCP servers provide the needed tools

### Part 4: Augur Extension Layer (`augur.yaml`)

Augur-specific features live in a separate `augur.yaml` file that is NOT part of the Claude skill standard. Stripping this file produces a working Claude skill.

```
my-skill/
├── SKILL.md              # Portable ─┐
├── scripts/              # Portable  │ This IS a standard Claude skill
│   ├── process_data.py   #           │ (export = copy these as-is)
│   └── requirements.txt  #           │
├── references/           # Portable  │
│   └── api-patterns.md   #           │
├── assets/               # Portable ─┘
│
├── augur.yaml            # Augur config ─┐
└── augur/                # ALL Augur-specific files grouped
    ├── dashboard/        #   Next.js UI  │ Strip augur.yaml + augur/
    │   ├── page.tsx      #               │ for Claude Code export
    │   └── layout.tsx    #               │
    ├── api/              #   API routes  │
    │   └── route.ts      #               │
    ├── mcp/              #   MCP tools   │
    │   └── __init__.py   #               │
    ├── lib/              #   TS utils    │
    └── data/             #   YAML store ─┘
        └── symptoms.yaml
```

**Directory boundary rule:** Everything outside `augur.yaml` + `augur/` is a standard Claude skill. Everything inside is Augur-specific. Export = delete `augur.yaml` + `augur/`.

**`augur.yaml` schema:**

```yaml
# Augur extension configuration — stripped on export to Claude Code
version: '1.0'

# Hub assignment (Augur dashboard routing)
hub:
  id: health
  role: primary              # primary | extension
  title: Health Hub
  subtitle: Personal health tracking
  icon: Heart
  iconBg: bg-rose-500/20
  iconColor: text-rose-400

# For extensions that add sub-routes to an existing hub:
# hub:
#   role: extension
#   extends: career
#   routePrefix: linkedin-writer

# Dashboard tab configuration
tabs:
  - id: overview
    label: Overview
    icon: LayoutDashboard
    default: true
  - id: symptoms
    label: Symptoms
    icon: Thermometer
    href: /health/symptoms
  - id: medications
    label: Medications
    icon: Pill
    href: /health/medications

# Action buttons (trigger SKILL.md workflows or MCP tools)
actions:
  - id: log-symptom
    label: Log Symptom
    icon: Plus
    type: modal
    modal: add-symptom
  - id: health-report
    label: Weekly Report
    icon: FileText
    flow: llm                  # Triggers SKILL.md "Weekly Health Report" workflow
    mode: ide
    mcp_tools:
      - get-symptoms
      - get-medications
      - get-health-score
      - semantic-search         # Cross-skill MCP tool — no import, just call
      - send-email              # External MCP tool — same abstraction
  - id: analyze-trends
    label: Trend Analysis
    flow: llm
    mcp_tools:
      - get-symptoms
      - get-health-score
    context: |
      Analyze the user's health trends over the past 30 days.
      Identify patterns, improvements, and areas of concern.

# Modal form definitions
modals:
  add-symptom:
    title: Log New Symptom
    submitTool: mcp://augur/add-symptom
    submitLabel: Log Symptom
    fields:
      - name: name
        label: Symptom
        type: text
        required: true
      - name: severity
        label: Severity (1-10)
        type: number
        required: true
        min: 1
        max: 10
      - name: notes
        label: Notes
        type: textarea

# MCP tool registration metadata
mcp:
  tools:
    - get-symptoms
    - add-symptom
    - update-symptom
    - delete-symptom
    - get-health-score
    - calculate-health-score

# Data entity schemas (drives code generation for MCP tools, API routes, dashboard pages)
schema:
  entities:
    - name: symptom
      plural: symptoms
      icon: Thermometer
      color: rose
      storage: yaml
      file: symptoms.yaml
      fields:
        - name: name
          type: string
          required: true
        - name: severity
          type: number
          required: true
          min: 1
          max: 10
        - name: date
          type: date
          auto: true
        - name: notes
          type: text

# Connected hubs (cross-navigation links in dashboard)
cross_hub_links:
  - hub: productivity
    label: Eisenhower Matrix
    description: Prioritize health tasks
  - hub: integrations
    label: Google Calendar
    description: Schedule health reminders
```

**Action buttons trigger SKILL.md workflows.** When a user clicks "Weekly Report" in the dashboard, Augur invokes the skill with `flow: llm`, which loads the SKILL.md and executes the "Weekly Health Report" workflow section. The `mcp_tools` array tells Augur which MCP tools to make available during execution — these can be from ANY MCP server (internal or external).

### Part 5: Per-Skill RAG Index

Every skill has an optional RAG (Retrieval-Augmented Generation) index for semantic search across its domain knowledge. The index is per-skill and independent — cross-skill search uses MCP tool calls (e.g., calling the knowledge skill's `semantic-search` tool).

**Directory structure:**

```
augur/rag/
├── sources.yaml          # Manifest of all indexed sources (tracked in git)
├── index/                # Vector embeddings + chunk store (gitignored)
│   └── chunks.db
├── cache/                # Extracted text from PDFs, images (gitignored)
│   ├── summary.yaml      # File-level summaries for quick context
│   └── extracts/         # Per-file extracted text
│       ├── {hash}.txt
│       └── {hash}.txt
└── imports/              # Imported files — full copies (gitignored)
    ├── lab-results/
    │   └── blood-test-2026-01.pdf
    ├── photos/
    │   └── xray-shoulder.png
    └── notes/
        └── doctor-visit.md
```

**Three source modes:**

| Mode | Where files live | Operation | When to use |
|------|-----------------|-----------|-------------|
| `linked` | External path (e.g., `~/Documents/Health/`) | Index only, files stay in place | User has existing folder they manage externally |
| `imported` | `augur/rag/imports/` inside the skill | **Move** (source deleted after copy) | User wants full migration — skill becomes single source of truth |
| `self` | Skill's own `references/` and `augur/data/` | Index in place | Always — skill's built-in knowledge |

**Import is a move, not a copy.** When files are imported into a skill (`import-to-{skill}` MCP tool), the original file is deleted after successful copy into `augur/rag/imports/`. This prevents duplicate source of truth — the skill directory becomes the canonical location. The import operation:
1. Copies file into `augur/rag/imports/{subfolder}/`
2. Verifies integrity (checksum match)
3. Deletes the original source file
4. Records the original path in `sources.yaml` (`imported_from` field) for provenance
5. Triggers re-index of the imported file

**`sources.yaml` manifest:**

```yaml
sources:
  # Linked — files stay external, only index created
  - id: health-docs
    type: linked
    path: /Users/gur/Documents/Health/
    glob: "**/*.{pdf,docx,txt,md}"
    description: Personal health documents and lab results
    last_indexed: 2026-02-19T10:30:00Z
    file_count: 47

  # Imported — files MOVED into skill (source deleted after copy)
  - id: lab-results
    type: imported
    subfolder: lab-results
    glob: "**/*.pdf"
    description: Blood work and lab results
    imported_from: /Users/gur/Documents/Health/Labs/   # Original location (provenance only)
    imported_at: 2026-02-19T10:30:00Z
    file_count: 12

  # Self — skill's own docs (always indexed)
  - id: internal
    type: self
    paths: [references/, augur/data/]
    auto_reindex: true
```

**File type extraction:**

| Type | Method | Output |
|------|--------|--------|
| `.md`, `.txt` | Direct text | Chunks in index |
| `.pdf` | PyMuPDF text extraction | `cache/extracts/{hash}.txt` |
| `.docx` | python-docx extraction | `cache/extracts/{hash}.txt` |
| `.jpg`, `.png`, `.heic` | Vision model description + OCR | `cache/extracts/{hash}.txt` |
| `.yaml`, `.json` | Structured content flattening | Chunks in index |
| `.csv`, `.xlsx` | Header + sample rows + statistics | `cache/extracts/{hash}.txt` |

**Indexing triggers:**
- **On-demand**: MCP tool `reindex-skill-rag` or dashboard button
- **File watcher**: Daemon monitors linked folders and `augur/rag/imports/` for changes, auto-reindexes on file add/modify/delete
- **Self-reindex**: Triggered automatically when `references/` or `augur/data/` files change

**MCP tools per skill (auto-registered):**
- `search-{skill}-knowledge` — semantic search across the skill's RAG index
- `import-to-{skill}` — import files from external path into `augur/rag/imports/`
- `link-to-{skill}` — add an external folder as a linked source
- `reindex-{skill}-rag` — trigger manual re-indexing
- `list-{skill}-sources` — show all indexed sources with status

**Gitignore rules:**
- `augur/rag/index/` — regenerable, gitignored
- `augur/rag/cache/` — regenerable, gitignored
- `augur/rag/imports/` — user data, gitignored
- `augur/rag/sources.yaml` — manifest, **tracked** (defines what should be indexed)

### Part 6: Export to Claude Code

A single command strips the Augur layer and produces a standard Claude skill:

```bash
python3 src/scripts/export-skill.py plugins/health/skills/health-tracker/ --target claude-code
```

**What it does:**
1. Copies `SKILL.md`, `scripts/`, `references/`, `assets/` unchanged
2. Strips `augur.yaml` and entire `augur/` directory (dashboard, api, mcp, lib, data, rag)
3. Appends MCP tool descriptions from `augur/mcp/__init__.py` docstrings into `references/mcp-tools.md`
4. Produces a zip-ready folder that can be:
   - Uploaded to Claude.ai via Settings > Capabilities > Skills
   - Placed in `~/.claude/skills/` for Claude Code
   - Added to Messages API via `container.skills` parameter

**What the exported skill can do:**
- All orchestration workflows work (they're in SKILL.md)
- MCP tool calls work IF the user has connected equivalent MCP servers
- Scripts run in Claude's code execution environment
- References are loaded progressively by Claude

**What it cannot do without Augur:**
- No dashboard UI (lives in `augur/dashboard/`)
- No modal forms (defined in `augur.yaml`)
- No hub navigation (defined in `augur.yaml`)
- No local YAML data persistence (lives in `augur/data/`, user needs to connect an MCP data store)

### Part 7: Shared Runtime Library (Augur Layer)

For the Augur extension layer, extract duplicated boilerplate into src/lib components.

**React src/lib runtime** (`src/dashboard/lib/plugin-runtime/`):

| Component | Replaces | Usage |
|-----------|----------|-------|
| `useEntityData<T>()` | 50+ copy-pasted useEffect fetch blocks | Generic data fetching hook per entity |
| `EntityTable<T>` | 30+ similar table implementations | Configurable table from schema |
| `StatsGrid` | Copy-pasted stat card grids in every overview | Stats from augur.yaml overview config |
| `ConnectedHubs` | Identical cross-hub section in every page | Links from augur.yaml cross_hub_links |
| `SkeletonCard` | Inconsistent loading states | Standard skeleton markup |
| `ErrorBoundary` | Missing or inconsistent error handling | Standard error gate |
| `PageWrapper` | Repeated layout boilerplate | Standard page layout |
| `EntityCrudPage` | Full CRUD page with table + modal + actions | Complete page from schema |

**Python src/lib runtime** (`src/mcp/plugin_utils.py`):

```python
class SkillDataStore:
    """Generic YAML/JSON data store for any skill's MCP tools."""
    def __init__(self, skill_path: Path): ...
    def read(self, filename: str) -> dict: ...
    def write(self, filename: str, data: dict) -> None: ...
    def list_entities(self, filename: str, key: str) -> list: ...
    def add_entity(self, filename: str, key: str, entity: dict) -> dict: ...
    def update_entity(self, filename: str, key: str, entity_id: str, updates: dict) -> dict: ...
    def delete_entity(self, filename: str, key: str, entity_id: str) -> dict: ...

def register_crud_tools(mcp: FastMCP, store: SkillDataStore, entity_name: str, fields: list):
    """Auto-register get/add/update/delete MCP tools for an entity from augur.yaml schema."""
```

### Part 8: Code Generator

`src/scripts/generate-skill.py` reads `augur.yaml` and generates the Augur extension files:

| Input | Generated Output |
|-------|-----------------|
| `hub.*` | Dashboard layout, navigation config |
| `schema.entities` | MCP `__init__.py` CRUD tools via `register_crud_tools()` |
| `schema.entities` | API routes (`route.ts`) per entity using `createAPIRoute` |
| `tabs` | `dashboard/page.tsx` with `PageWrapper`, `EntityTable`, `StatsGrid` |
| `modals` with entity ref | Auto-generated form fields from entity schema |
| `actions` | Action button wiring in pages |
| `cross_hub_links` | `ConnectedHubs` component in overview |

The generator does NOT touch `SKILL.md`, `scripts/`, `references/`, or `assets/` — those are hand-written portable files.

```bash
# Generate Augur extension files from augur.yaml
python3 src/scripts/generate-skill.py plugins/health/skills/health-tracker/

# Preview without writing
python3 src/scripts/generate-skill.py plugins/health/skills/health-tracker/ --dry-run

# Regenerate only MCP tools
python3 src/scripts/generate-skill.py plugins/health/skills/health-tracker/ --target mcp
```

### Part 9: Migration Path

**Every existing skill** is refactored in this order:

1. **Move chain workflows into SKILL.md** — Convert each `chains/*.yaml` into a markdown workflow section in SKILL.md. Delete `chains/` directory.
2. **Split config** — Extract Augur-specific config from SKILL.md frontmatter into `augur.yaml`. SKILL.md frontmatter retains only Claude-standard fields.
3. **Move web files into `augur/`** — Move `dashboard/`, `api/`, `mcp/`, `lib/`, `data/` into the `augur/` subdirectory. Update import paths.
4. **Unify dependencies** — Replace `dependencies.plugins` and `mcp_servers` with SKILL.md dependency documentation referencing MCP tool names.
5. **Validate export** — Run `export-skill.py` and verify the exported skill works in Claude Code.
6. **Adopt src/lib runtime** — Replace boilerplate dashboard code with src/lib components from `plugin-runtime/`.

**Migration waves:**

| Wave | Skills | Scope |
|------|--------|-------|
| 1 — Pilot | 3 simple skills (channels, system-cleanup, organizer) | Full migration + export validation |
| 2 — Simple | All skills without complex UI (~20 skills) | SKILL.md orchestration + augur.yaml split |
| 3 — Complex | Skills with custom dashboards (finance, health, career) | Full migration + src/lib runtime adoption |
| 4 — Complete | All remaining skills | Final cleanup + export validation |

## Consequences

**Positive:**
- Every Augur skill is installable in Claude Code by stripping one file (`augur.yaml`) and its extension directories
- Chain workflows eliminated — orchestration lives in SKILL.md where Claude natively understands it
- Internal and external dependencies use identical MCP abstraction — no proprietary dependency mechanism
- Skills are truly self-contained: one folder = one skill, regardless of platform target
- Aligns with Anthropic's open standard for skills — positions Augur plugins for community distribution
- Action buttons in dashboard trigger SKILL.md workflows that can call ANY MCP tool (cross-hub, cross-server)
- Shared runtime library eliminates 60-80% of dashboard boilerplate
- Code generator produces Augur extension files from `augur.yaml` schema

**Negative:**
- Breaking change: every existing skill must be migrated (chains → SKILL.md, split config)
- Two config files per skill: `SKILL.md` (portable) + `augur.yaml` (Augur extension) adds cognitive overhead
- SKILL.md orchestration is less structured than YAML chains — harder to validate programmatically
- Export produces a "reduced" skill — features requiring Augur's dashboard don't transfer
- MCP dependency model requires all Augur skills to expose well-named tools — naming discipline needed

**Neutral:**
- Mount system updated to read from `augur/dashboard/`, `augur/api/`, `augur/lib/` — same mounting behavior, different source path
- MCP tool registration updated to load from `augur/mcp/` — same `register_tools(mcp)` signature
- Dashboard rendering unchanged — same React components, same Next.js routing
- Progressive disclosure preserved — SKILL.md frontmatter (level 1) → body (level 2) → references/ (level 3)

## Implementation Order

```
Phase 1: Core Format Change
├── Step 1: Create augur.yaml JSON Schema (validates new config format)
├── Step 2: Create export-skill.py (produces Claude Code compatible skill)
├── Step 3: Update mount-plugins.ts to read augur.yaml instead of dashboard.yaml
├── Step 4: Create migration script: chains/*.yaml → SKILL.md workflow sections
└── Step 5: Create migration script: dashboard.yaml → augur.yaml + standard SKILL.md

Phase 2: Shared Runtime Library (PARALLEL with Phase 1)
├── Step 6: Create src/dashboard/lib/plugin-runtime/ components
├── Step 7: Create src/mcp/plugin_utils.py SkillDataStore
├── Step 8: Write tests for src/lib runtime (React + Python)
└── Step 9: Integration test with one sample skill

Phase 2b: RAG Index Infrastructure (PARALLEL with Phase 1)
├── Step 9a: Create RAG indexer: sources.yaml parser, file extraction (PDF/image/text), vector index builder
├── Step 9b: Create RAG MCP tools: search-{skill}-knowledge, import-to-{skill}, link-to-{skill}, reindex-{skill}-rag
├── Step 9c: Create file watcher integration: daemon monitors linked/imported folders, triggers reindex
├── Step 9d: Create RAG dashboard component: sources list, index status, import/link buttons
└── Step 9e: Write tests for RAG indexer (extraction, search, import)

Phase 3: Code Generator (depends on Phase 1)
├── Step 10: Create generate-skill.py reading augur.yaml
├── Step 11: Generate MCP tools from schema.entities
├── Step 12: Generate dashboard pages from tabs config
├── Step 13: Generate API routes from entities
└── Step 14: Add --dry-run, --incremental, --target flags + golden tests

Phase 4: Pilot Migration (depends on Phases 1, 2, 3)
├── Step 15: Migrate 3 pilot skills (channels, system-cleanup, organizer)
├── Step 16: Validate each pilot skill exports to Claude Code
├── Step 17: Validate dashboard works with augur.yaml
└── Step 18: Fix issues discovered during pilot

Phase 5: Full Migration (depends on Phase 4)
├── Step 19: Bulk migrate all skills (chains → SKILL.md, dashboard.yaml → augur.yaml)
├── Step 20: Delete chains/ directories across all skills
├── Step 21: Update all skill SKILL.md frontmatter to Claude standard fields only
├── Step 22: Adopt src/lib runtime in dashboard pages
└── Step 23: Validate export for all skills

Phase 6: Integration & Cleanup (depends on Phase 5)
├── Step 24: Update hardening audit to check augur.yaml + SKILL.md compliance
├── Step 25: Update /skill-setup wizard for new format
├── Step 26: Update SKILLS.md topic doc + agent-topics
├── Step 27: Delete deprecated scaffold.py, replace with generate-skill.py
└── Step 28: Update CLAUDE.md and sync_agents.py for new conventions

Phase 7: Verification
├── Step 29: Run full test suite (pytest + npm run build)
├── Step 30: Run hardening audit on all skills
├── Step 31: Run stale path scanner
├── Step 32: Export 5 diverse skills and test in Claude Code
└── Step 33: Update ADR status to Implemented
```

## Alternatives Considered

### Alternative 1: Keep Chains, Add Export Layer

Keep `chains/*.yaml` and write a converter that transforms them to SKILL.md markdown on export.

**Rejected because:** Maintaining two orchestration formats (chains for Augur, SKILL.md for export) doubles the maintenance burden. SKILL.md orchestration is strictly more expressive (natural language conditions, multi-MCP coordination, error handling in prose) and is what Claude natively optimizes for. There is no advantage to the YAML chain format.

### Alternative 2: Keep dashboard.yaml, Add SKILL.md Layer

Keep `dashboard.yaml` as the primary config and generate `SKILL.md` from it on export.

**Rejected because:** This inverts the priority. The portable Claude skill (SKILL.md) should be the primary artifact that humans write and review. The Augur extension (augur.yaml) should be secondary. Generating the primary artifact from the secondary one creates a dependency inversion where the proprietary format drives the standard one.

### Alternative 3: Single Config File (SKILL.md with Augur YAML Extensions)

Put everything in SKILL.md frontmatter with `# @augur` markers for stripping.

**Rejected because:** SKILL.md frontmatter has a 1024-character limit on description and security restrictions on content. Augur's hub config, tab definitions, modal schemas, and action configurations are too large and complex for frontmatter. A separate `augur.yaml` file keeps SKILL.md clean and portable while giving the Augur layer unlimited configuration space.

### Alternative 4: Keep Internal Plugin Dependencies as Imports

Allow `dependencies.plugins: [knowledge]` alongside MCP tool dependencies.

**Rejected because:** This creates two dependency resolution mechanisms. If `knowledge` exposes `semantic-search` as an MCP tool, then depending on the tool name is sufficient. The skill doesn't need to know (or care) that `semantic-search` comes from an Augur plugin called `knowledge` vs. an external search MCP server. Unified MCP dependencies make skills truly portable and self-contained.

## References

- [Anthropic: The Complete Guide to Building Skills for Claude](https://docs.anthropic.com/en/docs/build-with-claude/skills) (PDF, 2026)
- [Agent Skills — Open Standard](https://github.com/anthropics/agent-skills) — Anthropic's open skill standard
- [MCP Specification (2025-11-25)](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Registry server.json](https://github.com/modelcontextprotocol/registry)
- [ADR-040: Portable Plugin Template Standard](./ADR-040-portable-plugin-template-standard.md) — superseded by this ADR
- ADR-105: Hub-Driven Plugin Architecture
- ADR-112: Plugin Completeness & Standalone Compatibility
- [ADR-122: Filesystem-Driven Plugin Lifecycle](./ADR-122-filesystem-driven-plugin-lifecycle.md)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-126: Generic Plugin Template Refactor — Claude-Native Skill Standard**.

Read the full ADR: `docs/decisions/ADR-126-generic-plugin-template-refactor.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-126-claude-native", description="Implementing ADR-126: Claude-Native Skill Standard")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-126-claude-native", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-126-claude-native team.
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

**Team name**: `adr-126-claude-native`

#### Phase 1: Core Format Change
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | architect | high | Define augur.yaml JSON Schema. Must include: hub config, tabs, actions, modals, mcp tools, schema.entities, cross_hub_links. Write validation script | `src/config/augur-yaml-schema.json`, `src/scripts/validate-augur-yaml.py` |
| 1.2 | developer | high | Create export-skill.py: reads a skill directory, strips augur.yaml + dashboard/ + api/ + mcp/ + data/, copies SKILL.md + scripts/ + references/ + assets/, generates references/mcp-tools.md from __init__.py docstrings, produces zip-ready output | `src/scripts/export-skill.py` |
| 1.3 | developer | high | Update mount-plugins.ts to discover `augur.yaml` and mount from `augur/dashboard/`, `augur/api/`, `augur/lib/` instead of top-level directories. Must be backward-compatible during migration (read augur.yaml if exists, fall back to dashboard.yaml) | `src/dashboard/scripts/mount-plugins.ts` |
| 1.4 | developer | medium | Create chain-to-skillmd migration script: parses chains/*.yaml, generates markdown workflow sections, inserts into SKILL.md at correct position | `src/scripts/migrate-chains-to-skillmd.py` |
| 1.5 | developer | medium | Create dashboard-to-augur migration script: reads dashboard.yaml, writes augur.yaml (same schema minus `version`), strips Augur extensions from SKILL.md frontmatter leaving only Claude-standard fields | `src/scripts/migrate-dashboard-to-augur.py` |

#### Phase 2: Shared Runtime Library
**Strategy**: PARALLEL (runs alongside Phase 1)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | high | Create all src/lib React components: useEntityData, EntityTable, EntityCrudPage, StatsGrid, ConnectedHubs, SkeletonCard, ErrorBoundary, PageWrapper, types.ts, index.ts barrel | `src/dashboard/lib/plugin-runtime/*.tsx` |
| 2.2 | developer | medium | Create Python SkillDataStore + register_crud_tools() for auto MCP tool generation from schema | `src/mcp/plugin_utils.py` |
| 2.3 | developer | medium | Write tests for React src/lib runtime (render, hooks, props) | `src/dashboard/lib/plugin-runtime/__tests__/*.test.tsx` |
| 2.4 | developer | medium | Write tests for Python SkillDataStore (CRUD, edge cases) | `tests/src/mcp/test_plugin_utils.py` |

#### Phase 2b: RAG Index Infrastructure
**Strategy**: PARALLEL (runs alongside Phase 1 and 2)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2b.1 | developer | high | Create RAG indexer: sources.yaml parser, file extractors (PDF via PyMuPDF, images via vision+OCR, docx, csv/xlsx), vector index builder (chunks.db), summary.yaml generator | `src/mcp/rag_indexer.py` |
| 2b.2 | developer | high | Create RAG MCP tools auto-registration: for each skill with augur/rag/, register search-{skill}-knowledge, import-to-{skill}, link-to-{skill}, reindex-{skill}-rag, list-{skill}-sources | `src/mcp/rag_tools.py` |
| 2b.3 | developer | medium | Create daemon file watcher integration: monitor linked folders + augur/rag/imports/ for changes, trigger auto-reindex | `src/daemon/rag_watcher.py` |
| 2b.4 | developer | medium | Create RAG dashboard component: source list with status, import/link buttons, search preview, index stats | `src/dashboard/lib/plugin-runtime/RagSources.tsx` |
| 2b.5 | developer | medium | Write tests for RAG indexer (extraction per file type, search accuracy, import/link operations) | `tests/src/mcp/test_rag_indexer.py` |

#### Phase 3: Code Generator
**Strategy**: PIPELINE (depends on Phase 1)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | high | Create generate-skill.py: reads augur.yaml, generates MCP __init__.py using SkillDataStore + register_crud_tools(), generates dashboard pages using src/lib runtime, generates API routes using createAPIRoute | `src/scripts/generate-skill.py` |
| 3.2 | developer | medium | Add --dry-run, --incremental, --target flags. Write golden-file tests | `src/scripts/generate-skill.py` (extend), `tests/src/scripts/test_generate_skill.py` |

#### Phase 4: Pilot Migration
**Strategy**: PIPELINE (depends on Phases 1, 2, 3)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Migrate `channels` skill: run migration scripts, convert chains to SKILL.md workflows, validate dashboard and export | `plugins/admin/skills/channels/` |
| 4.2 | developer | medium | Migrate `system-cleanup` skill: same process | `plugins/admin/skills/system-cleanup/` |
| 4.3 | developer | medium | Migrate one lifestyle skill (organizer): same process | `plugins/lifestyle/skills/organizer/` |
| 4.4 | validator | low | Test all 3 pilot skills: dashboard renders, MCP tools work, export produces valid Claude Code skill | Validation report |

#### Phase 5: Bulk Migration
**Strategy**: PIPELINE (depends on Phase 4)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer | medium | Run migration scripts on ALL remaining skills. For each: chains → SKILL.md, dashboard.yaml → augur.yaml, move web dirs into augur/, standardize frontmatter | All `plugins/*/skills/*/` |
| 5.2 | developer | low | Delete all chains/ directories across all skills | All `plugins/*/skills/*/chains/` |
| 5.3 | developer | medium | Adopt src/lib runtime components in dashboard pages (replace boilerplate with imports) | All `plugins/*/skills/*/augur/dashboard/` |
| 5.4 | developer | low | Delete all top-level dashboard.yaml, dashboard/, api/, mcp/, data/ (now inside augur/) | All `plugins/*/skills/*/` |

#### Phase 6: Integration & Cleanup
**Strategy**: PARALLEL (depends on Phase 5)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 6.1 | developer | medium | Update hardening audit to check augur.yaml compliance + SKILL.md Claude-standard fields | `plugins/dev/skills/frontend/scripts/dashboard_hardening_audit.py` |
| 6.2 | developer | medium | Update /skill-setup wizard for new format: generate augur.yaml + SKILL.md skeleton | Relevant wizard code |
| 6.3 | devops | low | Update SKILLS.md topic doc, agent-topics, CLAUDE.md references | `plugins/ai/skills/ai_bridge/augur/agent-topics/SKILLS.md` |
| 6.4 | devops | low | Delete deprecated scaffold.py, update references to generate-skill.py | `plugins/ai/skills/mcp-app-factory/scripts/scaffold.py` |

#### Final Phase: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 7.1 | validator | low | Run all tests: `pytest tests/src/` and `npm run build` in `src/dashboard/` |
| 7.2 | architect | medium | Verify ADR intent: review 5 diverse skills for correct SKILL.md orchestration, augur.yaml config, export compatibility |
| 7.3 | devops | low | Run stale path scanner: `python3 .github/scripts/scan_stale_paths.py --ci` |
| 7.4 | validator | low | Export 5 skills to Claude Code format, verify each produces valid skill folder |
| 7.5 | devops | low | Run augur.yaml schema validation on all skills |

### Stale Path Scan

This ADR renames `dashboard.yaml` → `augur.yaml`, moves `dashboard/`+`api/`+`mcp/`+`data/` into `augur/` subdirectory, deletes `chains/` directories, and introduces new paths. The final verification MUST include:

```bash
python3 .github/scripts/scan_stale_paths.py --ci
```

### Completion Criteria
- [ ] All skills have `SKILL.md` with Claude-standard frontmatter only
- [ ] All skills have `augur.yaml` for Augur-specific config (where applicable)
- [ ] No `chains/` directories remain — all orchestration in SKILL.md
- [ ] No `dashboard.yaml` files remain — replaced by `augur.yaml`
- [ ] No `dependencies.plugins` in any SKILL.md — replaced by MCP tool dependencies
- [ ] `export-skill.py` produces valid Claude Code skills for all exported skills
- [ ] Shared runtime library used by all dashboard pages
- [ ] `generate-skill.py` produces working files from `augur.yaml`
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Stale path scanner clean
- [ ] ADR status updated to "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-126-generic-plugin-template-refactor.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
