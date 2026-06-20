---
status: Implemented
date: '2026-02-27'
deciders:
- GS
related:
- ADR-086 (Hub Data Bridge)
- ADR-102 (Adaptive Slash Commands)
- ADR-126 (Generic Plugin Template)
- '`/import` skill'
hub: null
tags:
- notion
- export
- import
- command
superseded_by: null
---

# ADR-170: Notion Export Import Command

## Context

Augur has accumulated significant personal knowledge and task management data in Notion. The current migration strategy is manual: export from Notion as HTML, then hand-place content into Augur plugins. This is error-prone and doesn't scale — a single "Priority Dashboard" export contains 130 Eisenhower tasks, 120+ sub-page HTML files, CSV databases, and strategy documents spanning 6+ plugin hubs.

The existing `/import` skill creates **new hubs** from data folders. But Notion migration is different — data must be **routed into existing plugins** (eisenhower, finance, health, career, home, lifestyle) based on content classification, not create a new hub per export.

**Current pain points:**
- Notion exports use HTML with heavy CSS boilerplate (~700 lines of styles per file) — raw files are unreadable without parsing
- CSV databases have Notion-specific column formats (URL-encoded sub-task references, mixed status/parent-task columns)
- No automated way to classify which of Augur's 17 hubs a task belongs to
- The existing Eisenhower plugin has 5 seed tasks — 130 real tasks from Notion would immediately make it useful
- Sub-task hierarchy (parent → child) exists in the CSV but is lost without explicit extraction
- Unstructured content pages (strategy notes, lists) need to become markdown in the appropriate plugin's data directory

**Notion export structure** (observed from real export):
```
ExportBlock-{uuid}-Part-N/
├── {Page Title} {uuid}.html          # Main page (Eisenhower quadrants)
├── {Page Title}/                      # Sub-directory
│   ├── {Database} {uuid}.csv         # Structured database
│   ├── {Database}/                    # Individual row pages
│   │   ├── {Row Title} {uuid}.html   # Per-row detail pages
│   │   └── ...
│   └── {Subpage Title} {uuid}.html   # Embedded sub-pages
```

## Decision

Build a `/notion-import` slash command as a new skill in `plugins/admin/skills/notion-import/` that implements a 4-stage pipeline: **Parse → Classify → Transform → Ingest**.

### 1. Parser Module (`scripts/notion_parser.py`)

Extracts structured content from Notion HTML exports:

- **HTML Parser**: Strips Notion boilerplate CSS (~700 lines), extracts `<h1>`–`<h3>` headers, `<table>` data, `<ul>`/`<ol>` lists, `<p>` text, and `to-do-list` checkboxes. Handles Hebrew/RTL content.
- **CSV Parser**: Reads Notion database CSVs. Decodes URL-encoded sub-task references (`Priority%20Dashboard/EisenhowerTasks/...` → task titles). Normalizes status values.
- **Page Tree Builder**: Walks the export directory recursively, builds a tree of `NotionPage` objects with parent→child relationships.
- **Output**: A `NotionExport` object containing typed items:
  - `DatabaseItem` — rows from CSV databases (structured)
  - `ContentPage` — text/list content from HTML pages (unstructured)
  - `StrategyDoc` — longer-form pages with numbered lists or bullet points

### 2. Classifier Module (`scripts/notion_classifier.py`)

Routes each parsed item to a target Augur plugin using a 3-tier classification:

**Tier 1 — Schema Match** (deterministic, no LLM):
- CSV databases with Eisenhower columns (Urgent, Important, Quadrant) → `eisenhower` plugin
- Items with `Theme` field → map directly:
  | Theme | Target Plugin | Skill |
  |-------|--------------|-------|
  | Finance | finance | finance |
  | Family | lifestyle | lifestyle |
  | Home Tasks | home | home-automation |
  | Growth | career | growth |
  | Career | career | career |
  | Health | health | health |
  | Danit Design | consulting | client-smb-design |

**Tier 2 — Keyword Match** (deterministic, no LLM):
- Scan title + content for keyword patterns:
  - `insurance|pension|tax|investment|budget|ILS|₪` → finance
  - `dental|blood test|doctor|medical|checkup|health` → health
  - `closet|painting|organize|appliance|home` → home
  - `LinkedIn|CV|job|interview|certificate` → career
  - `kids|children|family|school` → lifestyle

**Tier 3 — Manual** (user prompt):
- Items that don't match Tier 1 or 2 are presented to the user via `AskUserQuestion` with suggested targets, or placed in an `_unclassified/` staging directory for later triage.

**Output**: Each item gets a `classification` field: `{ plugin, skill, confidence, tier }`.

### 3. Transformer Module (`scripts/notion_transformer.py`)

Converts classified items into Augur-native formats:

**Eisenhower Tasks** (CSV → YAML):
Maps Notion fields to existing `tasks.yaml` schema:
```yaml
tasks:
  - id: "notion-{uuid-suffix}"
    title: "Complete 2025 tax return filing"
    quadrant: "do-first"              # Derived from Urgent + Important columns
    due: "2026-04-01"
    completed: false                  # Status == "Done" → true
    created_at: "2026-02-27T00:00:00"
    notes: ""
    # Extended fields (new):
    assigned_to: "GS"
    effort: "low"                     # "Low < day" → low, "Medium < 7 days" → medium, "High > 7 days" → high
    theme: "Finance"
    source: "notion"
    parent_task: "Finance"            # Preserves hierarchy
    sub_tasks: ["RISC Private Review...", "Migdal appeal..."]
    status_original: "Not started"    # Preserves Notion status
```

Quadrant derivation:
| Urgent | Important | Quadrant |
|--------|-----------|----------|
| Yes | Yes | do-first |
| No | Yes | schedule |
| Yes | No | delegate |
| No | No | eliminate |
| (missing) | (missing) | inbox |

**Content Pages** (HTML → Markdown):
- Strip Notion CSS and HTML boilerplate
- Convert `<h1>`→`#`, `<ol>`→numbered lists, `<ul>`→bullet lists
- Preserve checkbox state (`to-do-children-checked` → `- [x]`)
- Save as `{slug}.md` in target plugin's `augur/data/notes/` directory
- Add YAML frontmatter: `title`, `source: notion`, `imported_at`, `original_path`

**Strategy Docs** (HTML → Markdown):
- Same HTML→Markdown conversion
- Save in target plugin's `augur/data/notes/` or `docs/references/` based on content type

### 4. Ingest Module (`scripts/notion_ingest.py`)

Writes transformed data to target plugin directories:

- **Merge strategy**: Append to existing YAML arrays (don't overwrite). Deduplicate by title.
- **File placement**:
  | Item Type | Target Path |
  |-----------|-------------|
  | Eisenhower tasks | `plugins/productivity/skills/eisenhower/augur/data/tasks.yaml` |
  | Finance items | `plugins/finance/skills/finance/augur/data/tasks.yaml` (new file) |
  | Health items | `plugins/health/skills/health/augur/data/tasks.yaml` (new file) |
  | Content pages | `plugins/{hub}/skills/{skill}/augur/data/notes/{slug}.md` |
  | Unclassified | `runtime/notion-import/{run-id}/_unclassified/` |
- **Migration report**: Writes `runtime/notion-import/{run-id}/report.yaml` with counts per plugin, unclassified items, and any parse errors.
- **Idempotency**: Tracks imported Notion UUIDs in `runtime/notion-import/imported_ids.yaml` to prevent duplicate imports on re-run.

### 5. Eisenhower Schema Extension

Extend `tasks.yaml` schema to support Notion's richer fields. The existing 5-field schema (`id`, `title`, `quadrant`, `due`, `completed`, `created_at`, `notes`) gains optional fields:

```yaml
# New optional fields (backward compatible)
assigned_to: string    # Person responsible
effort: enum           # low | medium | high
theme: string          # Cross-cutting category
source: string         # "notion" | "manual" | "apple"
parent_task: string    # Parent task title for hierarchy
sub_tasks: [string]    # Child task titles
status_original: string # Preserved from source system
```

The dashboard and API routes read these if present, ignore if absent — zero breaking changes.

### 6. Slash Command (`/notion-import`)

**SKILL.md** at `plugins/admin/skills/notion-import/augur/data/skills/notion-import/SKILL.md`:

```
/notion-import <path-to-notion-export>
/notion-import <path> --dry-run          # Show classification without writing
/notion-import <path> --auto             # Skip manual classification prompts
/notion-import <path> --target eisenhower # Force all items to one plugin
```

**Execution flow**:
1. Validate path exists and looks like a Notion export (has `.html` + subdirectories)
2. Run Parser → show summary: "Found 130 tasks in CSV, 5 content pages, 1 strategy doc"
3. Run Classifier → show mapping: "92 auto-classified, 12 keyword-matched, 26 need manual routing"
4. If not `--auto`: present unclassified items for user routing
5. Run Transformer → show preview of YAML/markdown output
6. Ask confirmation: "Write 130 tasks to eisenhower, 15 notes to 4 plugins?"
7. Run Ingest → write files, print report

## Consequences

**Positive:**
- Notion data becomes immediately usable in Augur's existing plugins
- The Eisenhower plugin goes from 5 seed tasks to 130+ real tasks — actually useful
- Classification logic is reusable for future imports (Todoist, Apple Reminders, etc.)
- Preserves Notion's rich metadata (effort, assignments, hierarchy) that would be lost in manual migration
- Idempotent — safe to re-run on same export or new exports

**Negative:**
- HTML parsing is fragile — Notion may change export format without notice
- Extended Eisenhower schema adds fields the dashboard doesn't render yet (assigned_to, effort)
- Manual classification for unclassified items requires user interaction each time

**Neutral:**
- Does not replace the `/import` skill — that creates new hubs, this routes to existing ones
- Does not connect to Notion API — operates on downloaded exports only (local-first)

## Implementation Order

```
Phase 1: Parser + Classifier (core pipeline)
├── Step 1: Create notion-import skill scaffold
├── Step 2: Build HTML parser (strip CSS, extract content)
├── Step 3: Build CSV parser (decode Notion references, normalize)
├── Step 4: Build page tree builder (directory walker)
├── Step 5: Build theme-based classifier (Tier 1 + 2)
└── Step 6: Unit tests with sample Notion export

Phase 2: Transformer + Ingest (output pipeline)
├── Step 7: Build Eisenhower YAML transformer
├── Step 8: Build markdown converter (HTML → MD)
├── Step 9: Extend Eisenhower tasks.yaml schema
├── Step 10: Build ingest module (merge + dedupe + write)
├── Step 11: Build migration report generator
└── Step 12: Integration test with real Notion export

Phase 3: Slash Command + Polish
├── Step 13: Write SKILL.md with command definition
├── Step 14: Add augur.yaml for skill registration
├── Step 15: Add --dry-run and --auto flags
├── Step 16: Add manual classification prompt (Tier 3)
└── Step 17: End-to-end test with Priority Dashboard export
```

## Alternatives Considered

### A. Extend `/import` to handle Notion routing

Rejected — `/import` creates new hubs with generated dashboard pages. Adding routing-to-existing-plugins logic would conflate two different concerns (hub creation vs. data distribution). Better to keep `/import` for "I have a folder, make a hub" and `/notion-import` for "I have Notion data, put it where it belongs."

### B. Use Notion API instead of HTML exports

Rejected — violates local-first principle (ADR-006). Would require API credentials, network access, and Notion account permissions. HTML export is already the user's workflow and works offline.

### C. LLM-based classification for all items

Rejected for Tier 1/2 — the theme column and keyword patterns handle 80%+ of items deterministically. Using LLM for every item wastes tokens and adds latency. LLM classification could be a future Tier 3 enhancement for items that don't match any keyword pattern.

## References

- `/import` skill: `plugins/ai/skills/ai_bridge/augur/data/skills/import/SKILL.md`
- Eisenhower plugin: `plugins/productivity/skills/eisenhower/`
- ADR-086: Hub Data Bridge
- ADR-102: Adaptive Slash Commands
- ADR-006: Local-first architecture
- Sample export: `~/Downloads/ExportBlock-7a95a468-ad34-4853-a51a-4336138f3d55-Part-1/`

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-170: Notion Export Import Command**.

Read the full ADR: `docs/decisions/ADR-170-notion-import-command.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-170-notion-import", description="Implementing ADR-170: Notion Export Import Command")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-170-notion-import", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-170 team.
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

**Team name**: `adr-170-notion-import`

#### Phase 1: Parser + Classifier (core pipeline)
**Strategy**: PIPELINE (steps build on each other)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Create skill scaffold: SKILL.md, augur.yaml, scripts/, tests/ | `plugins/admin/skills/notion-import/SKILL.md`, `plugins/admin/skills/notion-import/augur.yaml`, `plugins/admin/skills/notion-import/scripts/__init__.py` |
| 1.2 | developer | medium | Build HTML parser — strip Notion CSS, extract headers/tables/lists/text, handle RTL | `plugins/admin/skills/notion-import/scripts/notion_parser.py` |
| 1.3 | developer | medium | Build CSV parser — decode URL-encoded refs, normalize status, extract parent/sub-task hierarchy | `plugins/admin/skills/notion-import/scripts/notion_parser.py` (extend) |
| 1.4 | developer | medium | Build page tree builder — recursive directory walk, build NotionPage tree | `plugins/admin/skills/notion-import/scripts/notion_parser.py` (extend) |
| 1.5 | developer | medium | Build classifier — Tier 1 schema match, Tier 2 keyword match, theme→plugin mapping | `plugins/admin/skills/notion-import/scripts/notion_classifier.py` |
| 1.6 | developer | medium | Unit tests for parser + classifier using sample data from Priority Dashboard export | `plugins/admin/skills/notion-import/tests/test_parser.py`, `plugins/admin/skills/notion-import/tests/test_classifier.py` |

#### Phase 2: Transformer + Ingest (output pipeline)
**Strategy**: PARALLEL (transformer + schema extension are independent)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Build Eisenhower YAML transformer — map Notion fields to tasks.yaml schema, derive quadrants from Urgent+Important | `plugins/admin/skills/notion-import/scripts/notion_transformer.py` |
| 2.2 | developer | medium | Build markdown converter — HTML→MD with frontmatter, checkbox preservation, RTL support | `plugins/admin/skills/notion-import/scripts/notion_transformer.py` (extend) |
| 2.3 | developer | low | Extend Eisenhower tasks.yaml schema — add optional fields (assigned_to, effort, theme, source, parent_task, sub_tasks, status_original) | `plugins/productivity/skills/eisenhower/augur/data/tasks.yaml` |
| 2.4 | developer | medium | Build ingest module — merge YAML arrays, deduplicate by title, write files, track imported IDs | `plugins/admin/skills/notion-import/scripts/notion_ingest.py` |
| 2.5 | developer | medium | Build migration report generator — counts per plugin, unclassified items, parse errors | `plugins/admin/skills/notion-import/scripts/notion_ingest.py` (extend) |
| 2.6 | developer | medium | Integration test with real Priority Dashboard export | `plugins/admin/skills/notion-import/tests/test_integration.py` |

#### Phase 3: Slash Command + Polish
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Write SKILL.md with full command definition, flags, examples | `plugins/admin/skills/notion-import/augur/data/skills/notion-import/SKILL.md` |
| 3.2 | developer | low | Register in augur.yaml with MCP tools if needed | `plugins/admin/skills/notion-import/augur.yaml` |
| 3.3 | developer | medium | Add --dry-run and --auto flags, manual classification prompt (Tier 3) | `plugins/admin/skills/notion-import/scripts/notion_ingest.py` |
| 3.4 | developer | medium | End-to-end test with Priority Dashboard export, verify all 130 tasks land correctly | `plugins/admin/skills/notion-import/tests/test_e2e.py` |

#### Final Phase: Verification
**Strategy**: PIPELINE
**Agents**:
| Step | Agent | Tier | Task |
|------|-------|------|------|
| 4.1 | validator | low | Run all tests: `pytest plugins/admin/skills/notion-import/tests/` |
| 4.2 | validator | low | Verify Eisenhower plugin still works with extended schema — existing 5 tasks + imported tasks load correctly |
| 4.3 | architect | low | Verify ADR-170 intent matches implementation — all 4 modules exist, classification tiers work, no centralized registries |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest plugins/admin/skills/notion-import/tests/`)
- [ ] Parser handles HTML + CSV + directory tree from real Notion export
- [ ] Classifier routes 80%+ items automatically (Tier 1 + 2)
- [ ] Eisenhower plugin loads extended schema without breaking
- [ ] No orphaned files or broken references
- [ ] ADR status updated to "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-170-notion-import-command.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
