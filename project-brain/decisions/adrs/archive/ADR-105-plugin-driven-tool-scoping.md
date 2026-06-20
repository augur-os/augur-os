---
status: Implemented
date: ''
deciders: []
related: []
hub: null
tags:
- hub
- driven
- plugin
- architecture
superseded_by: null
---

# ADR-105: Hub-Driven Plugin Architecture

**Date:** 2026-02-15
**Implementation Date:** 2026-02-15
**Supersedes:** Bundle system (crew/services/apps/orchestrator), manual `mcp_tool_groups.yaml`, BRAIN_DATA/BRAIN_BUGS/BRAIN_INTEL/WORKFORCE_SELF_UPDATE groups
**Related:** ADR-040 (plugin template), ADR-047 (tool filtering), ADR-059 (MCP focus)

## Context

Augur has two parallel organizational systems that don't align:

```
Disk (bundles):               UI (hubs):
plugins/                      Sidebar:
├── crew/         (5 skills)  ├── Life (personal)
├── orchestrator/             ├── Business
├── services/    (13 skills)  ├── Capabilities (productivity)
└── apps/        (12 skills)  └── Operations (system)
```

`knowledge` is a "service" on disk but "productivity" in the UI. `home-automation` is an "app" but "system" in the sidebar. Three disconnected systems are built from the same plugin data:

1. **Navigation** — `generate-tab-registry.ts` reads `hub.category` → sidebar sections
2. **Tab registry** — same generator reads `tabs` → tab definitions
3. **Tool scoping** — manually maintained `mcp_tool_groups.yaml` → which tools appear per page

Additionally, `mcp_tool_groups.yaml` had 6 "src/lib groups" that leaked domain tools:

| Group | Used By | Real Purpose |
|-------|---------|--------------|
| BRAIN_DATA (15 tools) | 20+ pages | Dumping ground — search + apple + install + RAG admin |
| BRAIN_BUGS (7) | /brain only | Single-page tools pretending to be src/lib |
| BRAIN_INTEL (4) | 3 pages | Metrics for brain/observe/knowledge |
| WORKFORCE_CHAINS (12) | 4 pages | Legitimate src/lib group |
| WORKFORCE_SELF_UPDATE (10) | /workforce only | Single-page tools pretending to be src/lib |
| SETTINGS_MGMT (11) | 4 pages | Legitimate src/lib group |

## Decision

### Consolidate bundles and hubs into one concept

The plugin directory **is** the hub. No separate `hub.category` field — the directory name defines the hub. One organizing concept drives navigation, tool scoping, and tab registry.

### Hub directory structure

```
plugins/
├── core/skills/           # Always on — settings, platform
│   ├── settings/
│   └── platform/
├── career/skills/         # Standalone — job search, interviews
│   └── career/
├── finance/skills/        # Standalone — accounts, budget, portfolio
│   └── finance/
├── health/skills/         # Body — medical, wearables
│   ├── health/
│   └── wearables/
├── productivity/skills/   # Daily drivers — tasks, email, calendar, notes
│   ├── eisenhower/
│   ├── google-workspace/
│   ├── apple/
│   ├── organizer/
│   └── project-dev/
├── lifestyle/skills/      # Personal — reading, recipes, travel, content
│   ├── lifestyle/
│   └── content/
├── home/skills/           # Smart home — lights, speakers, climate
│   └── home-automation/
├── business/skills/       # Ventures + client projects
│   ├── venture-augur/
│   ├── enterprise/
│   ├── client-smb-design/
│   ├── client-terminal-automation/
│   └── client-ai-consulting/
├── ai/skills/             # Intelligence — RAG, memory, models, discovery
│   ├── knowledge/
│   ├── ai_bridge/
│   ├── install/
│   └── mcp-app-factory/
├── system/skills/         # Ops — monitoring, services, chains, bugs
│   ├── observe/
│   ├── daemon/
│   ├── scraper/
│   ├── renderer/
│   ├── updater/
│   ├── brain/
│   └── workforce/
└── dev/skills/            # Dev-mode only — crew agents
    ├── developer/
    ├── advisor/
    ├── devops/
    ├── validator/
    └── frontend/
```

**11 hubs:** core, career, finance, health, productivity, lifestyle, home, business, ai, system, dev

### Plugin-declared hub membership

Each plugin's `dashboard.yaml` no longer needs `hub.category` — the parent directory defines the hub:

```yaml
# plugins/finance/skills/finance/augur.yaml
hub:
  id: finance
  title: Finance
  subtitle: Personal finance, investments, and wealth building
  icon: DollarSign
  # No "category" or "parent" field — directory = hub

mcp:
  tools:
    - finance-summary
    - finance-accounts
    - finance-transactions
    - finance-budget
    - finance-portfolio
    - finance-goals
    - finance-import
  max_tools: 20

tabs:
  - id: overview
    label: Dashboard
    icon: LayoutDashboard
    default: true
  - id: accounts
    label: Accounts
    href: /finance/accounts
```

### New hubs emerge automatically

If a plugin is placed in `plugins/my-new-hub/skills/my-skill/` <!-- example path -->, the generator discovers `my-new-hub` as a new hub and creates navigation, tool scoping, and tab registry entries for it. No config changes needed.

### Tool scoping: 2 layers only

```
Core tools (16 visible in operation mode)
  → Loaded on EVERY page
  → Universal: skill discovery, search, workflow, status, utility
  → Works with all plugins disabled

Skill tools (per-plugin, from dashboard.yaml mcp.tools)
  → Each plugin declares its own MCP tools
  → Auto-generated at build time
```

No src/lib groups. No BRAIN_DATA, WORKFLOW, SETTINGS. If a skill needs `execute-chain`, it lists it in its `mcp.tools`.

**Tool resolution:**

```
Open a hub page   → core tools + ALL tools from ALL skills in that hub
Open a skill page → core tools + tools from THAT skill only
```

### One unified generator

Replace `generate-tab-registry.ts` with `generate-hub-registry.ts` that produces everything:

**Input:** Scan `plugins/*/skills/*/dashboard.yaml`

**Output:** `config/dashboard/generated/hub_registry.yaml`

```yaml
# AUTO-GENERATED — DO NOT EDIT
# Source: plugins/*/skills/*/dashboard.yaml
# Generator: src/dashboard/scripts/generate-hub-registry.ts
generated_at: "2026-02-15T12:00:00Z"

hubs:
  core:
    title: Core
    icon: Shield
    always_enabled: true
    skills: []

  finance:
    title: Finance
    icon: DollarSign
    skills:
      - id: finance
        route: /finance
        tools:
          - finance-summary
          - finance-accounts
          - finance-transactions
          - finance-budget
          - finance-portfolio
          - finance-goals
          - finance-import
        max_tools: 20
        tabs:
          - id: overview
            label: Dashboard
            icon: LayoutDashboard
            href: /finance
          - id: accounts
            label: Accounts
            icon: Wallet
            href: /finance/accounts

  health:
    title: Health
    icon: Heart
    skills:
      - id: health
        route: /health
        tools: [get-virtual-doctor-symptoms, ...]
        tabs: [...]
      - id: wearables
        route: /wearables
        tools: []
        tabs: [...]

  # ... all hubs
```

**Runtime reads one file.** `toolFilter.ts` loads `hub_registry.yaml`, looks up the current page, returns core + skill tools. No merging, no groups, no manual config.

### Manual overrides

Optional file for user customizations:

```yaml
# config/dashboard/hub_overrides.yaml (optional, user-created, never auto-generated)

# Move a skill to a different hub
relocate:
  career:
    hub: lifestyle           # career shows under lifestyle instead of its own hub

# Add extra tools to a skill beyond plugin declaration
extra_tools:
  venture-augur:
    - execute-chain
    - list-jobs
    - get-job-status

# Hide a skill from navigation
hidden:
  - renderer
  - updater
```

**Resolution order:**

```
1. Load generated/hub_registry.yaml (auto-generated, committed)
2. If hub_overrides.yaml exists, apply relocations + extra_tools + hidden
3. Result: final hub → skills → tools mapping
```

### Page manifest lock — zero-regression guarantee

Before any migration, generate a snapshot of all current pages:

```yaml
# config/dashboard/page_manifest.lock (committed, validated in CI)
generated_at: "2026-02-15T..."
pages:
  /career:
    skill: career
    hub: career
    has_dashboard: true
    has_api: true
    tool_count: 3
    tabs: [overview, pipeline, companies, interview]
  /finance:
    skill: finance
    hub: finance
    has_dashboard: true
    has_api: true
    tool_count: 7
    tabs: [overview, accounts, transactions, portfolio]
  # ... all pages
```

**Build validation:**

```
generate-hub-registry.ts:
  1. Scan plugins/ → discover hubs and skills
  2. Load page_manifest.lock
  3. For every page in manifest:
     - Found in discovered? → ✓ continue
     - MISSING? → ✗ BUILD FAILS:
       "ERROR: /career in manifest but not found.
        Expected: plugins/career/skills/career/augur.yaml"
  4. New pages not in manifest → WARNING (must be added)
  5. Write generated/hub_registry.yaml
```

**Three layers of protection:**

| Layer | When | Catches |
|-------|------|---------|
| Manifest lock | Every build | Missing pages — fails if any disappear |
| Pre-migration snapshot | Before `git mv` | Baseline of routes, tools, tabs |
| Post-migration diff | After generators run | Generated output must match snapshot |

### ADR-040 compatibility

Current ADR-040 uses bundles to imply plugin profiles (crew=minimal, services=standard, apps=full). With bundles gone, profile detection uses auto-detect (already implemented):

| Signal | Profile |
|--------|---------|
| No `dashboard.yaml` | Minimal (agent-only) |
| `dashboard.yaml` exists, no `api/` dir | Standard |
| `api/` dir exists | Full |

The `portable: true` flag in SKILL.md replaces the crew-implies-portable convention if Layer 1 export is needed.

## Implementation

### Phase 1: Config cleanup (done)

- Promoted BRAIN_DATA search tools to core_tools
- Eliminated 4 fake groups (BRAIN_DATA, BRAIN_BUGS, BRAIN_INTEL, WORKFORCE_SELF_UPDATE)
- Renamed remaining groups (WORKFLOW, SETTINGS)
- Moved all per-page tools to skill_tool_groups
- Updated toolFilter.ts types

### Phase 2: Manifest lock

1. Create `generate-page-manifest.ts` — scans current state, produces `page_manifest.lock`
2. Run it, commit the manifest
3. Add manifest validation to build pipeline

### Phase 3: Hub directory migration

1. Create new hub directories: `plugins/{core,career,finance,health,productivity,lifestyle,home,business,ai,system,dev}/skills/`
2. `git mv` each skill from old bundle to new hub directory
3. Update PLUGIN_BUNDLES in generators to scan hub directories
4. Run generators, validate against manifest — zero regressions

### Phase 4: Add `mcp:` block to dashboard.yaml

1. Add `mcp.tools` and `mcp.max_tools` to all 32 dashboard.yaml files
2. Populate from current `skill_tool_groups` entries
3. Remove `hub.category` field (directory defines hub now)

### Phase 5: Unified generator

1. Create `generate-hub-registry.ts` replacing `generate-tab-registry.ts`
2. Produces `config/dashboard/generated/hub_registry.yaml`
3. Contains: nav items + tab registry + tool scoping — all from one scan
4. Update `toolFilter.ts` to read from generated hub registry
5. Update `SidebarNav.tsx` to read from generated hub registry
6. Remove old `generated-registry.ts`, old manual `mcp_tool_groups.yaml` pages/skill_tool_groups sections

### Phase 6: Override support + CI

1. Implement `hub_overrides.yaml` merge logic
2. Add `generate-hubs` to `npm run build`
3. Manifest validation in CI — build fails if any page disappears
4. Drift detection — warn if generated output differs from committed

## Files Modified

| File | Change |
|------|--------|
| `plugins/` (all skills) | Move from bundle dirs to hub dirs |
| `plugins/*/skills/*/dashboard.yaml` (32) | Add `mcp:` block, remove `hub.category` |
| `src/dashboard/scripts/generate-hub-registry.ts` | New unified generator |
| `src/dashboard/scripts/generate-page-manifest.ts` | New manifest generator |
| `config/dashboard/generated/hub_registry.yaml` | New generated output |
| `config/dashboard/page_manifest.lock` | New manifest lock |
| `config/dashboard/hub_overrides.yaml` | New optional override file |
| `src/dashboard/lib/server/toolFilter.ts` | Read from hub_registry.yaml |
| `src/dashboard/components/SidebarNav.tsx` | Read from hub_registry.yaml |
| `config/dashboard/mcp_tool_groups.yaml` | Reduced to core_tools only |
| `src/dashboard/scripts/generate-tab-registry.ts` | Replaced by hub generator |
| `src/dashboard/lib/tabs/generated-registry.ts` | Replaced by hub registry |

## Consequences

**Positive:**
- One concept (hub) drives everything: nav, tabs, tools, disk layout
- New plugin → new directory → auto-discovered at build time
- No manual config sync between multiple files
- Page manifest prevents regressions during migration and ongoing
- User overrides without touching plugin code

**Negative:**
- Large file move (all plugins change directories) — one-time cost
- git history fragmented at migration point
- Build step dependency — tools/nav stale until generator runs

**Risk:**
- `focus-context` MCP tool read `include_groups` from old config — needs update
- External scripts that hardcode bundle paths (grep for `plugins/consulting/`, `plugins/ai/`, etc.)
- Parallel worktree builds during migration window
