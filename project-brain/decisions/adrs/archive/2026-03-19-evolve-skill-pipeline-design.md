---
title: "Evolve Skill Pipeline"
status: proposed
date: 2026-03-19
depends_on: [ADR-450, ADR-454, ADR-432]
plugin: augur-ops
---

# Evolve Skill Pipeline — Design Spec

## Overview

`/evolve` is a thin orchestrator skill that provides a unified user journey for growing an Augur project. When a user encounters a new problem, `/evolve` guides them from problem description through skill creation/extension to a verified, working capability — optionally with a dashboard page.

**Plugin:** `augur-ops`
**Location:** `.claude/skills/evolve/` (Claude Code-mastered, `x-augur-plugin: augur-ops`)
**Visibility:** `app` (system-wide)
**Surfaces:** CLI (`/evolve`) + Dashboard (horizontal stepper page)
**Master:** `claude-code` (matches all other augur-ops skills which live in `.claude/skills/`)

## Architecture: Thin Orchestrator

`/evolve` is a conversational state machine that manages pipeline steps and user decisions, delegating all real work to existing skills via MCP tool calls:

- **import** tools — collateral extraction, data processing
- **discovery** tools — semantic matching against installed skills
- **skillstore** tools — community/GitHub skill search
- **mcp-app-factory** tools — plugin scaffolding, MCP wiring
- **verify/test** tools — smoke testing, wiring audits
- **ADR-450 template system** — dashboard page composition

Existing skills stay independent and testable. Each step can still be invoked standalone via the original skill.

## Pipeline State Machine

8 sequential steps. Each has an entry condition, MCP tool delegation, user decision point, and next-step transition.

```
INTAKE → CLASSIFY → SEARCH → SCAFFOLD → ENRICH → WIRE → VERIFY → PAGE (optional)
```

### Step Details

| Step | Input | Delegates to | User decision | Output |
|------|-------|-------------|---------------|--------|
| **Intake** | Problem desc, docs, photos, or SKILL.md | `import` tools (data extraction, OCR) | Confirm extracted problem statement | Normalized problem + collateral manifest |
| **Classify** | Problem + collateral | `discovery` tools (semantic matching) — **prerequisite:** discovery skill needs semantic search MCP tools before evolve can use it | Confirm: extend existing / create new | Classification result + confidence |
| **Search** | Problem (when no SKILL.md provided) | `skillstore` tools + internal skill search | Pick: install & extend / build new / skip | Matched skill or null |
| **Scaffold** | Classification + optional matched skill | `mcp-app-factory` tools (scaffold/extend) | Review generated skeleton | Skill directory with SKILL.md frontmatter |
| **Enrich** | Collateral manifest + skill directory | `import` tools (process into skill data) | Review processed data | Populated vault data directory |
| **Wire** | Skill directory | `mcp-app-factory` tools (MCP/API setup) | Review tool registrations | Working MCP tools + API routes |
| **Verify** | Complete skill | Existing verify/test tools | Confirm skill works | Pass/fail + report |
| **Page** (optional) | Verified skill's blocks | ADR-450 template composition | Pick template, customize | YAML template in `plugins/ui/` |

### Skip Logic

- Entry via SKILL.md → skip Search (skill already provided)
- Entry via "extend existing" classification → skip Scaffold (skill exists)
- User declines page → skip Page

### State Persistence

Pipeline state lives at `{get_state_dir()}/evolve/<pipeline-id>.yaml` — fully project-scoped per ADR-454. `get_state_dir()` resolves to the platform-appropriate state directory scoped by `get_project_name()` from `project.yaml`.

All steps are idempotent — re-running a completed step is safe. `/evolve --resume <id>` picks up from the last completed step.

CLI flags map to MCP tools: `--status` calls `get-evolve-pipelines`, `--resume` calls `evolve-step-action` with a resume payload.

## Entry Points

Three ways to start a pipeline, each normalizing into the same internal representation.

### A: Collateral (docs, photos, files)

```
/evolve --from-docs ~/Downloads/meal-planning/
```

1. Scan directory — list files by type
2. Delegate to `import` tools for extraction (OCR, PDF parse, markdown read)
3. Classify extracted content → produce problem summary
4. Present to user for confirmation

### B: Problem description in chat

```
/evolve
> What problem are you trying to solve?
> I want to track my home renovation projects...
```

1. Problem statement captured directly
2. Optionally ask for related collateral
3. Move to classify

### C: SKILL.md provided

```
/evolve --from-skill ~/Downloads/home-reno-skill/SKILL.md
```

1. Parse SKILL.md frontmatter
2. Validate against current standards
3. Skip search step → move to scaffold

### Normalized Representation

```yaml
pipeline:
  id: evolve-2026-03-19-001
  entry_point: collateral | chat | skill
  problem_statement: "Track home renovation projects..."
  collateral:
    - path: ~/Downloads/reno-budget.xlsx
      type: spreadsheet
      extracted: true
  provided_skill: null | path/to/SKILL.md
  classification: null
```

## Classify & Search

### Classification (Hybrid)

Semantic search across installed skills, scoring matches with confidence (0-1):

- **High confidence (>0.8):** Pre-select, user confirms or overrides
- **Medium (0.4-0.8):** Show top matches with gap analysis, user picks
- **Low (<0.4):** Suggest search or create new

User confirms: `extend <skill>` | `create new` | `search`

### Search (Gap Analysis)

When no SKILL.md provided and user chose "search" or classification found nothing:

1. Search installed skills via `skill_registry`
2. Search skillstore (skills.sh) via `skills-sh-search`
3. Search GitHub via `skillstore-gh-search`
4. For each match, produce gap analysis:

```
Found: home-tracker (skills.sh, by @builder-community)
  Covers: project timelines, task lists
  Missing: budget tracking, photo progress
  Confidence: 67%

Options: Install and extend | Build new | Skip
```

Search is a discovery step, not an action step — it narrows the decision space, it doesn't make the decision.

## Scaffold, Enrich & Wire

### Scaffold

**Create mode:** Call `mcp-app-factory` scaffold tools → generates skill directory with SKILL.md (frontmatter: `x-augur-master`, `x-augur-plugin`, `x-augur-visibility`), `scripts/mcp/__init__.py` stub. Location depends on `x-augur-master`: Claude Code-mastered skills go to `.claude/skills/{name}/`, augur-mastered to `plugins/{bundle}/skills/{name}/`.

**Prerequisite:** `mcp-app-factory` scaffold templates must emit SKILL.md frontmatter only (per ADR-432), not `augur.yaml`. Verify scaffold output is compliant before evolve implementation.

**Extend mode:** Load target skill's SKILL.md and current MCP tool registrations. Diff against problem + gap analysis. Present change plan ("Adding 2 MCP tools, 1 data type"). User approves. New tools are appended to the existing `x-augur-mcp-tools` frontmatter list.

### Enrich

Process collateral into skill data:
- Spreadsheets → seed data YAML
- PDFs/markdown → vault data files
- Images → skill `assets/`, index entry

Write to vault via `get_skill_vault_dir(skill_name)` from `src.config.paths` — resolves to the correct project-scoped vault path. Never hardcode vault path structure.

No collateral → skip (skill starts with empty data + seed templates).

### Wire

**Create mode:**
1. Generate MCP tool implementations in `scripts/mcp/__init__.py`
2. Generate API routes in `augur/api/`
3. Ensure `@mcp.tool(name=...)` matches SKILL.md `x-augur-mcp-tools`
4. Run `mount-plugins` to update dashboard mount registry

**Extend mode:**
1. Read existing `scripts/mcp/__init__.py` — append new `@mcp.tool` registrations
2. Add new API routes alongside existing ones in `augur/api/`
3. Update SKILL.md `x-augur-mcp-tools` list with new tool names
4. Run `mount-plugins` to refresh registry

## Verify & Page

### Verify (5 checks)

1. **MCP tool health** — smoke-test each registered tool
2. **API route health** — confirm 200 on each route
3. **Wiring audit** — grep toolName vs `@mcp.tool(name=...)` exact match
4. **Data access** — confirm vault directory readable via MCP
5. **SKILL.md validation** — frontmatter complete and consistent

Failures pause the pipeline — user can `/evolve --resume` after fixing.

### Page (optional, ADR-450)

After verify passes:
1. List skill's available blocks
2. Suggest template from `plugins/ui/templates/` catalog
3. User picks template or customizes
4. Write YAML template to `plugins/ui/templates/{hub}/{template-id}.yaml` (organized by hub per ADR-450 template resolver)
5. User can further customize via vault override at `{get_vault_dir()}/dashboard/templates/{hub}/{template-id}.overrides.yaml`

## Dashboard UI

**Layout:** Horizontal stepper (sequential pipeline visualization)

**Page structure (ADR-450 YAML template):**
- **Stepper block** (top) — 8 steps with progress indicators, active step expanded with detail panel, user decision buttons
- **History table** (bottom) — completed pipelines: name, entry point, action, skill produced, date

**States:**
1. **Empty** — "Start your first evolution" CTA with three entry points
2. **Active** — stepper expanded, history below
3. **All complete** — history table with "Start new" button

**MCP tools for dashboard:**
- `get-evolve-pipelines` — list all pipelines
- `get-evolve-pipeline-detail` — single pipeline with step history
- `evolve-step-action` — submit user decision for current step

## CLI Interface

```
/evolve                        # Start interactive pipeline
/evolve --from-docs <path>     # Start from collateral
/evolve --from-skill <path>    # Start from SKILL.md
/evolve --status               # Show active pipelines
/evolve --resume <id>          # Resume paused pipeline
```

## Skill Config Format

All skill metadata uses SKILL.md `x-augur-*` frontmatter per ADR-432. No augur.yaml anywhere in the pipeline. The scaffold step generates SKILL.md with:

```yaml
---
name: home-renovation
description: Track renovation projects with budgets and progress photos
x-augur-master: claude-code
x-augur-plugin: augur-life
x-augur-visibility: app
x-augur-mcp-tools:
  - get-renovation-projects
  - update-renovation-status
  - add-renovation-photo
x-augur-data-dir: home-renovation
---
```

## ADR Dependencies

| ADR | Dependency | Impact |
|-----|-----------|--------|
| **ADR-450** | Template-driven dashboard | Page step uses YAML template composition instead of TSX generation |
| **ADR-454** | Multi-project framework | All state/vault paths scoped via `get_project_name()` from `project.yaml` |
| **ADR-432** | Frontmatter migration | SKILL.md `x-augur-*` fields only, no augur.yaml |

**Implementation order:** ADR-454 → ADR-450 → evolve skill (this spec)

## Prerequisites (must be done before evolve implementation)

1. **Discovery skill needs semantic search MCP tools** — currently a stub with no tools registered. Needs at least a `classify-problem` tool that takes a problem statement and returns ranked skill matches with confidence scores.
2. **mcp-app-factory scaffold templates must emit SKILL.md frontmatter** — verify scaffold output produces `x-augur-*` frontmatter, not `augur.yaml` (per ADR-432).
3. **ADR-454 `get_project_name()` and `get_state_dir()` must be implemented** — evolve depends on project-scoped paths.
4. **ADR-450 template resolver must be implemented** — Page step depends on YAML template composition.

## Existing Skill Relationship

| Skill | Role after evolve |
|-------|------------------|
| **mcp-app-factory** | Low-level scaffolding engine — evolve calls it |
| **skillstore** | Search backend — evolve calls it in search step |
| **import** | Intake engine — evolve calls it for collateral processing |
| **page-builder** | Absorbed by ADR-450 template system |
| **discovery** | Classification backend — evolve calls it |
