---
status: Implemented
date: '2026-02-28'
deciders:
- Gur Sannikov
related:
- ADR-032 (Install-driven dashboard)
- ADR-126 (generic plugin template)
- ADR-178 (decentralized command discovery)
hub: null
tags:
- evolve
- legacy
- discovery
- install
- skill
superseded_by: null
---

# ADR-180: Evolve Legacy Discovery to Install Skill

## Context

The Install skill provides a discovery/evaluation catalog for external skills with a 6-status workflow (new → evaluating → approved → rejected → installed → dismissed) and 3-axis scoring (relevance, popularity, integration). In practice, this workflow is too heavy — the sonoscli integration was done entirely by hand, bypassing Install completely. The evaluation ceremony adds friction without proportional value. Of 37 cataloged discoveries, most remain in "new" status with zero scores.

What's actually needed is a direct install flow: give it a URL, it generates MCP tools, API routes, tests, and augur.yaml entries — matching the pattern we use for manual integrations.

## Decision

### 1. Rename Install → Install

Rename `plugins/ai/skills/install/` → `plugins/ai/skills/install/`. Update all references:

- `augur.yaml`: `skill: install`, `data_dir: install`, all hrefs `/install/`
- Config files: `plugin_state.json`, `tool_display_names.yaml`, `mcp_tool_groups.yaml`, `page-skills.yaml`, `external_mcp_registry.yaml`
- Cross-skill references in consulting and professional bundles
- Build scripts: `validate_structure.py`, `scan_stale_paths.py`
- MCP tool logger: `mcp.install`
- Auto-generated files regenerated via `mount-plugins` + `sync_agents.py`

**Action**:
- `git mv plugins/ai/skills/install plugins/ai/skills/install`
- Update 5 config YAML/JSON files
- Update 2 cross-skill dashboard references
- Update 2 build scripts

### 2. Simplified Data Model

Replace `discoveries.yaml` (28-field schema with scoring) with:

**registry.yaml** — tracks installed external skills:
```yaml
entries:
- id: <sha256-16-char>
  title: "Sonos Extended Controls"
  source_url: "https://skillsmp.com/skills/..."
  source_type: skillsmp | github | local | url
  category: home-automation
  status: pending | installing | installed | failed
  added: 2026-02-28
  install_metadata:
    target_bundle: home
    target_skill: home-automation
    install_type: enhance | new
    files_created: [...]
    installed_at: 2026-02-28T...
    error: null
```

**discoveries.yaml** — simplified to catalog backlog (drop 18 scoring/evaluation fields, keep 10 core fields, all statuses reset to `pending`).

Delete `sources.yaml` (import tracking — no longer needed).

**Action**:
- Create `registry.yaml` with empty entries
- Run migration script to strip scoring fields from discoveries
- Delete `sources.yaml`

### 3. Three New MCP Tools (replace 8 existing)

Replace `discover-skill`, `list-discoveries`, `evaluate-discovery`, `update-discovery-status`, `get-discovery-stats`, `install-analyze-import`, `install-apply-import`, `install-discovery` with:

1. **`install-skill`** (read/write) — Analyze or install from URL/path. `dry_run=True` returns source analysis. `dry_run=False` records installation in registry. Actual codegen runs in IDE agent context.
2. **`list-installed`** (read-only) — Query registry with optional status filter.
3. **`uninstall-skill`** (destructive) — Remove registry entry by ID or source URL.

Create `_registry.py` helper module for YAML read/write with file locking.

**Action**:
- Rewrite `augur/mcp/__init__.py` (1106 lines → ~200 lines)
- Create `augur/mcp/_registry.py`
- Register 3 tools in `augur.yaml`

### 4. Install Pipeline Library (3 modules)

Create `augur/lib/` with three modules powering the pipeline:

**fetcher.py** — Source format detection and local file reading:
- `detect_source_type(source)` → `skillsmp | github | local | url`
- `fetch_source(source)` → content dict (local reads directly; URLs return `needs_web_fetch=True` for IDE agent to handle)

**manifest.py** — Capability manifest schema:
- `CapabilityManifest` dataclass: name, description, cli_binary, install_hint, capabilities (list of action groups), suggested_bundle/skill, troubleshooting
- `validate_manifest(data)` → validated dataclass
- `MANIFEST_PROMPT` — LLM extraction prompt template

**codegen.py** — Code generation from manifests:
- `generate_mcp_tool(manifest, capability, hub)` → Python source for one @mcp.tool function
- `generate_test(manifest, capability)` → pytest contract test class
- `generate_api_route(manifest, capability, hub)` → TypeScript createAPIRoute source
- `generate_augur_yaml_entries(manifest, hub)` → tool + action button entries

**Action**:
- Create `augur/lib/__init__.py`, `fetcher.py`, `manifest.py`, `codegen.py`
- Create tests: `test_fetcher.py`, `test_manifest.py`, `test_codegen.py`

### 5. Dashboard Evolution (3 pages)

Replace Install's 3 pages (overview, catalog, discover) with:

**Install page** (`/ai/install/install`) — URL input field + "Analyze" button dispatching to IDE via `useActionRunner`. Shows progress stages and detected capabilities.

**Registry page** (`/ai/install/registry`) — Table of installed external skills from registry.yaml. Columns: title, source, bundle/skill, date, status. Actions: uninstall, reinstall.

**Catalog page** (`/ai/install/catalog`) — Simplified backlog. Drop scoring columns. Keep: title, source, category, status, tags. Add per-row "Install" action.

Delete: `DiscoverPanel.tsx`, `discover/page.tsx` (featured hubs UI — not needed for direct install).
Rename: `DiscoveryTable.tsx` → `RegistryTable.tsx`, `DiscoveryDetail.tsx` → `SkillDetail.tsx`.

**Action**:
- Rewrite `page.tsx` (overview)
- Create `install/page.tsx`, `registry/page.tsx`
- Simplify `catalog/page.tsx`
- Rename + simplify table and detail components
- Delete discover page + panel

### 6. API Route Evolution

Simplify 5 existing routes:

- `discoveries/route.ts` → catalog CRUD (simplified, no scoring)
- `discoveries/status/route.ts` → only 3 valid transitions (pending→installing, installing→installed, installing→failed)
- `discoveries/install/route.ts` → install trigger (calls install-skill MCP tool)
- `stats/route.ts` → simplified stats (total_installed, total_pending, total_failed)
- `health/route.ts` → unchanged

Create 1 new route:
- `registry/route.ts` → list-installed MCP tool proxy

**Action**:
- Simplify 4 existing routes
- Create 1 new registry route
- Delete `refactor/` route (no longer needed)

### 7. `/install` Slash Command

Create `commands/install/SKILL.md` defining the 5-stage pipeline:
1. Fetch & detect source format
2. Extract capability manifest via LLM
3. Resolve target bundle/skill with user confirmation
4. Full codegen (MCP tools, API routes, tests, augur.yaml)
5. Mount & verify

Register in `augur.yaml` contributions.commands per ADR-178.

**Action**:
- Create `commands/install/SKILL.md`
- Add command entry to augur.yaml

## Consequences

**Positive**:
- Direct URL → working integration in one command
- 8 MCP tools → 3 (simpler mental model)
- No evaluation ceremony for known-good skills
- Full codegen matches manual integration quality (proven with sonoscli)
- `/install` slash command, MCP tool, and dashboard UI all supported

**Negative**:
- Loses Install's evaluation/scoring framework (37 discoveries lose scores)
- Discover page's curated MCP hub links removed (could be re-added later)
- ~37 files need legacy-discovery→install reference updates
- ADR-032 design partially superseded

**Neutral**:
- Catalog backlog preserved (simplified schema)
- Health check route unchanged
- Plugin mount system handles new paths automatically

## Implementation Order

```
Phase 1: Directory rename + config updates
├── Step 1: git mv install → install
├── Step 2: Update augur.yaml identity (skill, data_dir, hrefs, tools, actions, tabs)
├── Step 3: Update SKILL.md + README.md
├── Step 4: Update 5 config files (plugin_state, tool_display_names, mcp_tool_groups, page-skills, external_mcp_registry)
├── Step 5: Update 2 cross-skill references (consulting, professional)
└── Step 6: Update 2 build scripts + commit

Phase 2: Data model migration (depends on Phase 1)
├── Step 1: Create registry.yaml
├── Step 2: Run migration script on discoveries.yaml
├── Step 3: Delete sources.yaml
└── Step 4: Commit

Phase 3: Pipeline library (depends on Phase 1) — PARALLEL steps
├── Step 1: Write fetcher.py + test_fetcher.py (TDD)
├── Step 2: Write manifest.py + test_manifest.py (TDD)
└── Step 3: Write codegen.py + test_codegen.py (TDD)

Phase 4: MCP tools rewrite (depends on Phase 2 + Phase 3)
├── Step 1: Create _registry.py helper
├── Step 2: Rewrite __init__.py with 3 tools
├── Step 3: Write test_install_mcp.py
└── Step 4: Commit

Phase 5: Dashboard + API rewrite (depends on Phase 4) — PARALLEL steps
├── Step 1: Delete DiscoverPanel + discover page
├── Step 2: Rewrite overview page
├── Step 3: Create install page
├── Step 4: Create registry page + API route
├── Step 5: Simplify catalog page
├── Step 6: Rename + simplify table/detail components
├── Step 7: Simplify existing API routes
└── Step 8: Commit

Phase 6: Slash command (depends on Phase 4)
├── Step 1: Create commands/install/SKILL.md
├── Step 2: Register in augur.yaml
└── Step 3: Commit

Phase 7: Verification (depends on all)
├── Step 1: Run all install skill tests
├── Step 2: Run mount-plugins + generate-tab-registry
├── Step 3: Run npm run build
├── Step 4: Run sync_agents.py --all
├── Step 5: Run scan_stale_paths.py --ci
└── Step 6: Final commit + update ADR status
```

## Alternatives Considered

### Alternative 1: Replace Install with new Install skill (clean break)

Create `plugins/ai/skills/install/` from scratch, disable Install.

**Rejected**: Wastes existing API routes, dashboard components, and data model infrastructure. Install's catalog page bones are reusable.

### Alternative 2: Add install as separate skill alongside Install

Keep Install for catalog/evaluation, add Install as a separate skill for codegen.

**Rejected**: Two skills to maintain, unclear ownership boundary, Install's evaluation ceremony still applies to new discoveries.

## References

- ADR-032: Install-driven dashboard user journeys (partially superseded)
- ADR-126: Generic plugin template (augur.yaml v3.0 schema)
- ADR-178: Decentralized slash command discovery
- [openclaw/sonoscli skill](https://skillsmp.com/skills/openclaw-openclaw-skills-sonoscli-skill-md) — first manual integration that motivated this ADR

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "plugins/ai/skills/install"
      to: "plugins/ai/skills/install"
      scope: "plugins/, config/, src/, docs/, .github/"
    - from: "/api/install/"
      to: "/api/install/"
      scope: "plugins/ai/skills/install/augur/"
    - from: "/ai/install/"
      to: "/ai/install/"
      scope: "plugins/, src/"
    - from: "skill: install"
      to: "skill: install"
      scope: "plugins/ai/skills/install/, config/"
  apis_changed:
    - function: register_tools
      module: plugins.ai.skills.install.augur.mcp.__init__
      breaking: true
    - function: discover-skill
      module: mcp-tool
      breaking: true
    - function: list-discoveries
      module: mcp-tool
      breaking: true
    - function: evaluate-discovery
      module: mcp-tool
      breaking: true
    - function: install-analyze-import
      module: mcp-tool
      breaking: true
    - function: install-apply-import
      module: mcp-tool
      breaking: true
  patterns_deprecated:
    - grep: "install-analyze-import|install-apply-import|discover-skill|list-discoveries|evaluate-discovery|update-discovery-status|get-discovery-stats|install-discovery"
      replacement: "install-skill, list-installed, uninstall-skill"
    - grep: "relevance_score|popularity_score|integration_score|overall_score"
      replacement: "Scoring fields removed — use status field only"
  files_affected:
    - glob: "config/system/plugin_state.json"
    - glob: "config/dashboard/tool_display_names.yaml"
    - glob: "config/dashboard/mcp_tool_groups.yaml"
    - glob: "config/dashboard/page-skills.yaml"
    - glob: "config/integrations/external_mcp_registry.yaml"
    - glob: "plugins/consulting/skills/client-smb-design/augur/dashboard/*.tsx"
    - glob: ".github/scripts/validate_structure.py"
    - glob: ".github/scripts/scan_stale_paths.py"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-180: Evolve Legacy Discovery to Install Skill**.

Read the full ADR: `docs/decisions/ADR-180-evolve-install-to-install-skill.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-180-legacy-to-install", description="Implementing ADR-180: Evolve Legacy Discovery to Install Skill")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Agent(subagent_type="general-purpose", team_name="adr-180-legacy-to-install", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-180 team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases → spawn all at once. PIPELINE phases → use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` → haiku, `medium` → sonnet, `high` → opus

### Execution Plan

**Team name**: `adr-180-legacy-to-install`

#### Phase 1: Directory Rename + Config Updates
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | git mv plugins/ai/skills/install → plugins/ai/skills/install | `plugins/ai/skills/install/` |
| 1.2 | developer | medium | Rewrite augur.yaml (skill: install, new tools, new pages, new actions, new tabs) | `plugins/ai/skills/install/augur.yaml` |
| 1.3 | developer | low | Rewrite SKILL.md and README.md for install skill identity | `plugins/ai/skills/install/SKILL.md`, `plugins/ai/skills/install/README.md` |
| 1.4 | developer | low | Update 5 config files (plugin_state.json, tool_display_names.yaml, mcp_tool_groups.yaml, page-skills.yaml, external_mcp_registry.yaml) | `config/system/plugin_state.json`, `config/dashboard/tool_display_names.yaml`, `config/dashboard/mcp_tool_groups.yaml`, `config/dashboard/page-skills.yaml`, `config/integrations/external_mcp_registry.yaml` |
| 1.5 | developer | low | Update cross-skill references in consulting + professional bundles | `plugins/consulting/skills/client-smb-design/augur/dashboard/page.tsx`, `plugins/consulting/skills/client-smb-design/augur/dashboard/content-pipeline/page.tsx` |
| 1.6 | developer | low | Update build scripts + update layout.tsx | `.github/scripts/validate_structure.py`, `.github/scripts/scan_stale_paths.py`, `plugins/ai/skills/install/augur/dashboard/layout.tsx` |

#### Phase 2: Data Model Migration (depends on Phase 1)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | low | Create empty registry.yaml + write migration script | `plugins/ai/skills/install/augur/data/registry.yaml`, `plugins/ai/skills/install/scripts/migrate_data.py` |
| 2.2 | developer | low | Run migration on discoveries.yaml, delete sources.yaml | `plugins/ai/skills/install/augur/data/discoveries.yaml`, `plugins/ai/skills/install/augur/data/sources.yaml` |

#### Phase 3: Pipeline Library (depends on Phase 1) — PARALLEL steps
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer-a | medium | Write fetcher.py + test_fetcher.py (TDD) | `plugins/ai/skills/install/augur/lib/__init__.py`, `plugins/ai/skills/install/augur/lib/fetcher.py`, `plugins/ai/skills/install/tests/test_fetcher.py` |
| 3.2 | developer-b | medium | Write manifest.py + test_manifest.py (TDD) | `plugins/ai/skills/install/augur/lib/manifest.py`, `plugins/ai/skills/install/tests/test_manifest.py` |
| 3.3 | developer-c | medium | Write codegen.py + test_codegen.py (TDD) | `plugins/ai/skills/install/augur/lib/codegen.py`, `plugins/ai/skills/install/tests/test_codegen.py` |

#### Phase 4: MCP Tools Rewrite (depends on Phase 2 + Phase 3)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Create _registry.py helper module | `plugins/ai/skills/install/augur/mcp/_registry.py` |
| 4.2 | developer | medium | Rewrite __init__.py with install-skill, list-installed, uninstall-skill | `plugins/ai/skills/install/augur/mcp/__init__.py` |
| 4.3 | developer | medium | Write test_install_mcp.py | `plugins/ai/skills/install/tests/test_install_mcp.py` |

#### Phase 5: Dashboard + API Rewrite (depends on Phase 4) — PARALLEL steps
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer-a | low | Delete DiscoverPanel.tsx + discover/page.tsx | `plugins/ai/skills/install/augur/dashboard/DiscoverPanel.tsx`, `plugins/ai/skills/install/augur/dashboard/discover/page.tsx` |
| 5.2 | developer-a | medium | Rewrite overview page.tsx + create install/page.tsx | `plugins/ai/skills/install/augur/dashboard/page.tsx`, `plugins/ai/skills/install/augur/dashboard/install/page.tsx` |
| 5.3 | developer-b | medium | Create registry/page.tsx + registry/route.ts API | `plugins/ai/skills/install/augur/dashboard/registry/page.tsx`, `plugins/ai/skills/install/augur/api/registry/route.ts` |
| 5.4 | developer-a | medium | Simplify catalog/page.tsx, rename DiscoveryTable→RegistryTable, DiscoveryDetail→SkillDetail | `plugins/ai/skills/install/augur/dashboard/catalog/page.tsx`, `plugins/ai/skills/install/augur/dashboard/DiscoveryTable.tsx`, `plugins/ai/skills/install/augur/dashboard/DiscoveryDetail.tsx` |
| 5.5 | developer-b | medium | Simplify API routes (discoveries, status, install, stats) + delete refactor route | `plugins/ai/skills/install/augur/api/discoveries/route.ts`, `plugins/ai/skills/install/augur/api/discoveries/status/route.ts`, `plugins/ai/skills/install/augur/api/discoveries/install/route.ts`, `plugins/ai/skills/install/augur/api/stats/route.ts`, `plugins/ai/skills/install/augur/api/discoveries/refactor/route.ts` |

#### Phase 6: Slash Command (depends on Phase 4)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 6.1 | developer | medium | Create commands/install/SKILL.md with 5-stage pipeline definition | `plugins/ai/skills/install/commands/install/SKILL.md` |
| 6.2 | developer | low | Register command in augur.yaml contributions.commands | `plugins/ai/skills/install/augur.yaml` |

#### Phase 7: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 7.1 | validator | low | Run all install skill tests: `PYTHONPATH=... pytest plugins/ai/skills/install/tests/ -v` |
| 7.2 | devops | low | Run mount-plugins + generate-tab-registry: `npm run mount-plugins` |
| 7.3 | devops | low | Run full build: `npm run build` |
| 7.4 | devops | low | Run sync_agents.py --all and verify /install in CLAUDE.md |
| 7.5 | devops | low | Run stale path scan: `python3 .github/scripts/scan_stale_paths.py --ci` — verify zero HIGH-risk install references |
| 7.6 | architect | low | Verify ADR-180 intent matches implementation, update status to Implemented |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/`, `npm run build`)
- [ ] No orphaned files or broken references
- [ ] Stale path scanner clean — zero HIGH-risk `install` references in active code
- [ ] Impact Manifest validated — zero stale references for `plugins/ai/skills/install`, `/api/install/`, `/ai/install/`, `skill: install`
- [ ] All 8 old MCP tools removed, 3 new tools registered
- [ ] `/install` slash command appears in CLAUDE.md
- [ ] ADR status updated to "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-180-evolve-install-to-install-skill.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
