---
status: Implemented
date: '2026-02-01'
deciders: []
related: []
hub: null
tags:
- install
- driven
- dashboard
- refactoring
- user
superseded_by: null
---

# ADR-032: Install-Driven Dashboard Refactoring — User Journey Architecture

**Decision Makers**: Augur Team

## Context

The Install skill (`plugins/ai/skills/install/`) was built to discover, evaluate, and track external skills/tools. Currently it provides a catalog table and overview stats, but the UX stops at *listing*. There is no way for a user to:

1. **Understand** what a discovered skill actually does, what problem it solves, and how it fits into their personal augur
2. **Explore** integration potential — which existing skills it connects to, what new workflows it enables
3. **Act** — install, configure, or integrate the skill into their dashboard with a single click

This is not just a Install problem. The same pattern gap exists across the system:

- **Career Hub**: Jobs are listed in a pipeline table, but there is no unified "detail → action" flow. Users navigate to sub-pages instead of drilling into an item.
- **PluginsTab** (`src/dashboard/app/settings/tabs/PluginsTab.tsx`): Plugin management is buried in Settings. Enable/disable requires a manual `npm run build` after toggling.
- **Action buttons**: Actions exist as global page-level buttons (ADR-030), but there are no *item-level* actions — no way to act on a specific discovery, job, or document from inline context.

The current dashboard architecture (ADR-003, ADR-017) established skill-owned UI and mode separation but did not define a standard **user journey** pattern: the flow from *discovery → understanding → decision → action*.

### Current Architecture Gaps

| Gap | Current State | Desired State |
|-----|---------------|---------------|
| Detail view | No detail modal/panel anywhere | Standardized detail panel for any item type |
| Item-level actions | Only page-level actions in dashboard.yaml | Actions scoped to a specific item (evaluate *this*, install *this*) |
| Integration preview | Scores shown as numbers (0-100) | Visual map showing how skill connects to existing hubs |
| Install flow | Manual: toggle in Settings → rebuild | One-click: "Add to my Augur" button with guided setup |
| Cross-skill navigation | Hubs are isolated silos | Links from Install discovery → target hub where skill would integrate |
| Install ↔ Factory gap | Install discovers skills; Factory creates them — no bridge between them | Install "Install" triggers Factory scaffolding pipeline |

### Existing Plugin Infrastructure (Underutilized by Install)

The system already has comprehensive plugin lifecycle tools that Install does not currently connect to:

**Plugin Factory** (`plugins/ai/skills/mcp-app-factory/`):
- `create-plugin` MCP tool — scaffolds a full plugin from templates (SKILL.md, dashboard.yaml, mcp/__init__.py, API routes)
- `audit-plugin` — validates compliance against plugin spec
- `skill-generate` — creates skill with specified patterns (MCP, dashboard, API, chains)
- `skill-analyze` — analyzes existing skill for refactoring opportunities
- Scripts: `scaffold.py`, `migrate.py`, `audit.py`, `transform.py`, `skill_porter.py`, `skill_import.py`
- Chains: `plugin-creation.yaml`, `plugin-migration.yaml`, `skill_refactoring.yaml`

**Plugin Management** (`src/mcp/augur_mcp/domain/plugins.py`):
- `install-plugin` — installs plugin from git URL, local path, or marketplace ID
- `toggle-plugin` — enables/disables in plugin_state.json
- `reload-plugin` — hot-reloads plugin definition from disk
- `plugin-health` — checks health of all plugins
- `uninstall-plugin` — removes user-installed plugins

**Plugin State API** (`src/dashboard/app/api/plugins/route.ts`):
- GET/POST for listing and toggling plugins
- Dependencies API for scanning and installing pip requirements

**DevOps Skill** (`plugins/dev/skills/devops/`):
- `skill_refactor.py` — analyzes skill structure and suggests improvements
- `skill_maintenance.py` — health checking
- `discover_skills.py` — discovery of all available skills

**The gap**: Install has discovery data (what to install, where it comes from, how it integrates). Factory has creation tools (how to scaffold, validate, migrate). Plugin management has lifecycle tools (how to enable, load, health-check). These three systems don't talk to each other.

## Decision

### 1. Define the Standard User Journey Pattern

Every list-based dashboard page should support a three-phase user journey:

```
Phase 1: BROWSE         Phase 2: UNDERSTAND       Phase 3: ACT
─────────────────       ──────────────────────     ───────────────
Table/Grid view    →    Detail Panel/Modal    →    Action Execution
- Filter/sort           - Full description          - One-click install
- Search                - Metadata                  - Configure options
- Quick status          - Relationships             - Integration wizard
                        - Integration map           - Status tracking
```

### 2. Introduce the Detail Panel Component

Create a reusable `DetailPanel` component that any skill can use. It opens as a slide-over panel (not a modal) to preserve table context.

**Component interface:**

```typescript
type DetailPanel<T> = {
  item: T;                          // The data item to display
  sections: DetailSection[];        // Configurable content sections
  actions: DetailAction[];          // Item-level action buttons
  onClose: () => void;
  onAction: (actionId: string, item: T) => void;
};

type DetailSection = {
  id: string;
  label: string;
  icon?: string;
  render: 'key-value' | 'markdown' | 'tag-list' | 'score-bar' | 'integration-map' | 'custom';
  data: Record<string, unknown>;
};

type DetailAction = {
  id: string;
  label: string;
  icon: string;
  variant: 'primary' | 'secondary' | 'danger';
  flow: 'fast' | 'llm' | 'modal';  // Reuses existing action system
  confirmation?: string;
  disabled?: boolean;
  disabledReason?: string;
};
```

**Location**: `src/dashboard/components/DetailPanel.tsx` (src/lib infrastructure)

### 3. Install-Specific User Journey

#### Journey: "Evaluate and Integrate a Discovered Skill"

**Phase 1 — Browse (existing, enhanced)**

User lands on `/install/catalog`. The table shows all discoveries. Enhancements:
- Clicking a row opens the detail panel (not navigating away)
- Row hover shows a subtle "View details" affordance
- Quick-action icons in the row: evaluate (sparkles), approve (check), reject (x)

**Phase 2 — Understand (new)**

The detail panel slides in from the right, showing:

| Section | Content |
|---------|---------|
| **Header** | Title, category badge, status badge, overall score |
| **Description** | Full description + creator + source link |
| **Scores** | Three horizontal bar charts: Relevance, Popularity, Integration |
| **Integration Map** | Visual diagram: which existing hubs this skill connects to, with connection descriptions |
| **Tags & License** | Tag chips, license badge |
| **Notes** | Editable notes area |

**Integration Map** is the key differentiator. For a discovery like "Job Description Analyzer", it shows:

```
┌──────────────────┐     ┌───────────────────────┐
│  Job Description │────▶│  Career Hub           │
│  Analyzer        │     │  - Enhances pipeline  │
│                  │────▶│  - Improves scoring    │
│  Score: 85       │     └───────────────────────┘
│  Status: new     │     ┌───────────────────────┐
│                  │────▶│  Content Hub           │
│                  │     │  - Resume tailoring    │
└──────────────────┘     └───────────────────────┘
```

Data for this comes from `integration_ideas` in the discovery YAML (populated by `evaluate-discovery` MCP tool).

**Phase 3 — Act (new)**

The detail panel footer contains action buttons scoped to this specific discovery:

| Button | Flow | What Happens |
|--------|------|-------------|
| **Evaluate** | `llm` | AI scores the skill against user's installed skills, fills in scores + integration_ideas |
| **Approve** | `fast` | Calls `update-discovery-status` MCP tool → status = approved |
| **Reject** | `fast` | Calls `update-discovery-status` → status = rejected, with optional reason |
| **Install** | `modal` → `llm` | Opens integration wizard (see below) |

#### The Install Journey (Sub-Flow) — Integration with Plugin Factory & Plugin Management

The install flow is the critical bridge between Install (discovery) and the existing plugin lifecycle infrastructure. Rather than building new installation logic, Install orchestrates the tools that already exist.

**Installation Type Classification:**

When a user clicks "Install" on an approved discovery, the system first classifies what kind of installation this is:

| Type | Detection Signal | Existing Tool to Use | Example |
|------|-----------------|---------------------|---------|
| **MCP Server** | `github_url` points to an MCP server repo | `install-plugin` (augur-mcp) | "Pandoc MCP Server" |
| **New Skill Plugin** | No existing skill covers this capability | `create-plugin` + `skill-generate` (mcp-app-factory) | "SEO Optimizer" |
| **Skill Enhancement** | Overlaps with existing skill (from `overlaps_with` field) | `skill-analyze` (mcp-app-factory) + manual config | "Job Description Analyzer" → enhances Career |
| **Configuration-Only** | Tool already exists, just needs enabling/wiring | `toggle-plugin` + `reload-plugin` (augur-mcp) | Re-enabling a disabled plugin |

**Step-by-step flow:**

```
User clicks "Add to My Augur" on approved discovery
          │
          ▼
┌─────────────────────────────────────────────┐
│ 1. CLASSIFY — Install determines install type │
│    Reads: source_url, github_url,           │
│           overlaps_with, integration_ideas   │
│    Output: type ∈ {mcp, plugin, enhance,    │
│                     config}                  │
└──────────────────┬──────────────────────────┘
                   │
          ▼
┌─────────────────────────────────────────────┐
│ 2. PRE-CHECK MODAL — Shows user what will   │
│    happen before anything is executed        │
│    - Install type + what changes             │
│    - Target hub / existing skill affected    │
│    - Dependencies (from github_url analysis) │
│    - Estimated files to create/modify        │
│    User confirms or cancels                  │
└──────────────────┬──────────────────────────┘
                   │
          ▼
┌─────────────────────────────────────────────┐
│ 3. EXECUTE — LLM agent orchestrates the     │
│    existing tools in sequence                │
│                                             │
│  Type: MCP Server                           │
│    → install-plugin(source=github_url)      │
│    → toggle-plugin(name, enabled=true)      │
│    → plugin-health() to verify              │
│                                             │
│  Type: New Skill Plugin                     │
│    → create-plugin(name, category, desc,    │
│         features=[mcp, dashboard, api])     │
│    → AI reads source_url for implementation │
│      details, writes MCP tools              │
│    → audit-plugin(name) to validate         │
│    → toggle-plugin(name, enabled=true)      │
│                                             │
│  Type: Skill Enhancement                    │
│    → skill-analyze(existing_skill_path)     │
│    → AI proposes changes: new action        │
│      buttons, new MCP tool, new tab         │
│    → User reviews proposed changes          │
│    → AI applies approved changes            │
│    → audit-plugin(existing_skill) to verify │
│                                             │
│  Type: Configuration-Only                   │
│    → toggle-plugin(name, enabled=true)      │
│    → reload-plugin(name)                    │
└──────────────────┬──────────────────────────┘
                   │
          ▼
┌─────────────────────────────────────────────┐
│ 4. VERIFY & REBUILD                         │
│    → plugin-health() checks all plugins     │
│    → npm run mount-plugins (re-mount UI)    │
│    → npm run build (rebuild dashboard)      │
│    → Verify new routes exist                │
└──────────────────┬──────────────────────────┘
                   │
          ▼
┌─────────────────────────────────────────────┐
│ 5. POST-INSTALL                             │
│    → Install: update-discovery-status →       │
│         status = installed                  │
│    → Install: record install metadata         │
│         (installed_at, install_type,        │
│          target_skill, files_created)       │
│    → Dashboard: refresh, navigate to new    │
│         hub page if plugin created one      │
└─────────────────────────────────────────────┘
```

**Skill Enhancement — The Most Common Case:**

Many discovered skills aren't standalone — they enhance an existing hub. For example, "Job Description Analyzer" doesn't need its own hub; it belongs in Career. The enhancement flow:

1. Install reads `integration_ideas` for this discovery:
   ```yaml
   integration_ideas:
     - target_skill: career
       idea: "Could enhance job description analysis with deeper NLP parsing"
     - target_skill: career
       idea: "Could improve scoring criteria with industry benchmarks"
   ```

2. AI calls `skill-analyze(plugins/career/skills/career)` to understand current Career structure

3. AI proposes specific changes:
   - Add new action button `analyze-jd-deep` to `career/dashboard.yaml`
   - Add new MCP tool `deep-analyze-job-description` to `career/mcp/__init__.py`
   - Or: scaffold a sub-module within Career's scripts/

4. User reviews proposed changes in a diff-style preview

5. AI applies changes, runs `audit-plugin(career)` to validate compliance

**Factory Chain Integration:**

For complex installations (new skill plugins), Install can trigger the existing `plugin-creation` chain from mcp-app-factory:

```yaml
# mcp-app-factory/chains/plugin-creation.yaml (already exists)
# Install provides: name, category, description, features
# Chain handles: scaffold → customize → validate → enable
```

This avoids duplicating the factory's sophisticated scaffolding logic. Install becomes the *front door* to plugin creation — users discover what they want in Install and Factory builds it.

**Refactoring Flow — Post-Install Improvement:**

After a skill is installed (status = `installed`), Install can trigger a refactoring cycle using DevOps tools:

1. User notices the installed skill could be improved
2. Opens discovery detail panel → sees "Refactor" action (only shown for `installed` status)
3. AI calls `skill-analyze` (mcp-app-factory) on the installed skill
4. Returns analysis: missing tests, compliance gaps, optimization opportunities
5. AI calls devops `skill_refactor.py` for deeper structural analysis
6. User reviews suggestions → AI applies approved refactorings
7. `audit-plugin` validates the refactored skill still passes compliance

### 4. Declarative Item Actions in dashboard.yaml

Extend `dashboard.yaml` schema to support item-level actions alongside page-level actions:

```yaml
# Existing: page-level actions
actions:
  - id: add-discovery
    label: "Add Discovery"
    icon: "Plus"
    type: modal
    modal: add-discovery

# New: item-level actions (appear in detail panel)
item_actions:
  - id: evaluate-item
    label: "Evaluate"
    icon: "Sparkles"
    flow: llm
    mode: ide
    requires_status: [new, evaluating]     # Only shown for these statuses

  - id: approve-item
    label: "Approve"
    icon: "Check"
    flow: fast
    tool: mcp://augur/update-discovery-status
    args:
      status: approved
    requires_status: [new, evaluating]
    confirmation: "Approve this discovery?"

  - id: reject-item
    label: "Reject"
    icon: "X"
    flow: fast
    tool: mcp://augur/update-discovery-status
    args:
      status: rejected
    requires_status: [new, evaluating]
    variant: danger

  - id: install-item
    label: "Add to My Augur"
    icon: "Download"
    flow: llm
    mode: ide
    requires_status: [approved]
    variant: primary

  - id: refactor-item
    label: "Refactor"
    description: "Analyze installed skill and suggest improvements"
    icon: "Wrench"
    flow: llm
    mode: ide
    requires_status: [installed]
    # Chains into: skill-analyze → skill_refactor.py → audit-plugin

  - id: uninstall-item
    label: "Uninstall"
    icon: "Trash2"
    flow: fast
    tool: mcp://augur/uninstall-skill
    requires_status: [installed]
    variant: danger
    confirmation: "Uninstall this skill? Data will be preserved."
```

**Key additions to the schema:**
- `item_actions[]` — actions scoped to a data item (vs page-level `actions[]`)
- `requires_status` — conditional visibility based on item status field
- `tool` — direct MCP tool binding for fast actions (no API route needed)
- `args` — static arguments merged with item data at execution time
- `variant` — button styling (primary, secondary, danger)

### 5. Install ↔ Factory ↔ Plugin Management Bridge

The three systems form a pipeline where Install is the front door:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER-FACING LAYER                           │
│                                                                     │
│  Install Dashboard (/install)                                          │
│  ├── Browse: catalog table with filter/sort                        │
│  ├── Understand: detail panel with scores + integration map        │
│  └── Act: item actions (evaluate, approve, install, refactor)      │
└────────────────────────────┬────────────────────────────────────────┘
                             │ triggers
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       ORCHESTRATION LAYER                          │
│                                                                     │
│  Install MCP Tools (plugins/ai/skills/install/mcp/__init__.py)   │
│  ├── discover-skill           (add to catalog)                     │
│  ├── evaluate-discovery       (score against installed skills)      │
│  ├── update-discovery-status  (approve/reject lifecycle)           │
│  ├── install-discovery  [NEW] (classify + delegate to Factory)     │
│  └── get-discovery-stats      (reporting)                          │
└──────────┬──────────────────────────────┬───────────────────────────┘
           │ type: new plugin             │ type: MCP server / config
           ▼                              ▼
┌─────────────────────────┐  ┌────────────────────────────────────────┐
│  Plugin Factory          │  │  Plugin Management (augur-mcp)        │
│  (mcp-app-factory)       │  │                                        │
│  ├── create-plugin       │  │  ├── install-plugin (git/local/mktpl) │
│  ├── skill-generate      │  │  ├── toggle-plugin  (enable/disable)  │
│  ├── audit-plugin        │  │  ├── reload-plugin  (hot-reload)      │
│  ├── skill-analyze       │  │  ├── plugin-health  (verify all)      │
│  └── scaffold.py chain   │  │  └── uninstall-plugin                 │
└─────────────────────────┘  └────────────────────────────────────────┘
           │                              │
           └──────────────┬───────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       BUILD LAYER                                   │
│                                                                     │
│  mount-plugins.ts → generate-tab-registry.ts → next build          │
│  (plugin_state.json updated, dashboard rebuilt)                     │
└─────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       POST-INSTALL                                  │
│                                                                     │
│  DevOps Skill (optional follow-up)                                 │
│  ├── skill_refactor.py   (structural analysis)                     │
│  ├── skill_maintenance.py (health monitoring)                      │
│  └── discover_skills.py  (verify registration)                     │
└─────────────────────────────────────────────────────────────────────┘
```

**New MCP Tool: `install-discovery`**

Added to Install's `mcp/__init__.py`, this tool bridges Install data to Factory/Plugin management:

```python
@mcp.tool(name="install-discovery")
async def install_discovery(
    discovery_id: str,
    install_type: str = "auto",  # auto | mcp | plugin | enhance | config
    target_skill: str = "",       # for enhance type: which skill to extend
    features: str = "mcp,dashboard",  # for plugin type: features to scaffold
) -> str:
    """
    Install a discovery into the Augur system.

    Delegates to the appropriate subsystem:
    - 'mcp': calls install-plugin for MCP server repos
    - 'plugin': calls create-plugin + skill-generate via Factory
    - 'enhance': calls skill-analyze on target, proposes changes
    - 'config': calls toggle-plugin to enable existing disabled plugin
    - 'auto': reads discovery metadata to determine best type
    """
```

This tool does not duplicate Factory or Plugin Management logic. It reads Install's discovery data (source_url, github_url, integration_ideas, overlaps_with) and delegates to the right existing tool with the right parameters.

**Discovery YAML Enhancement — Install Metadata:**

After installation, Install records what happened:

```yaml
# data/install/discoveries.yaml — per-discovery install tracking
- id: mcp-debugger
  status: installed
  # ... existing fields ...
  install_metadata:
    installed_at: '2026-02-01T14:30:00Z'
    install_type: mcp          # mcp | plugin | enhance | config
    target_skill: null          # or "career" for enhancement type
    plugin_name: scraper   # name in plugin_state.json <!-- mcp-debugger removed; using scraper as example -->
    files_created:
      - plugins/ai/skills/scraper/SKILL.md
      - plugins/ai/skills/scraper/mcp/__init__.py
    audit_score: 85             # from audit-plugin post-install
    can_uninstall: true
```

### 5. Generalize for All Hub Pages

The detail panel + item actions pattern is generic. Other skills adopt it:

| Hub | List View | Detail Panel Sections | Item Actions |
|-----|-----------|----------------------|--------------|
| **Install** | Discovery catalog | Scores, integration map, notes | Evaluate, Approve, Reject, Install |
| **Career** | Job pipeline | Company info, match analysis, salary range | Analyze, Move to Active, Archive, Prep Interview |
| **Knowledge** | Document list | Content preview, related docs, citation graph | Re-index, Tag, Archive |
| **Capture** | Inbox items | Full content, source, extracted entities | Process, Tag, Forward to skill |

Each skill defines its own sections and item_actions in `dashboard.yaml`. The src/lib `DetailPanel` component renders them.

### 6. Navigation Integration (Cross-Hub Links)

When Install shows an integration idea like "enhances Career Hub pipeline", that text becomes a navigable link:

```typescript
// In integration map rendering
<Link href="/career/pipeline">
  Career Hub → Pipeline
</Link>
```

This creates a natural navigation web between skills, replacing the current siloed hub structure. Users can trace connections: Install → Career → Knowledge → back to Install.

### 7. Implementation Phases

| Phase | Scope | Files | Depends On |
|-------|-------|-------|------------|
| **P1: DetailPanel** | Shared slide-over component | `src/dashboard/components/DetailPanel.tsx`, `DetailPanel.test.tsx` | — |
| **P2: Install Detail** | Wire DetailPanel to Install catalog | `plugins/ai/skills/install/augur/DiscoveryTable.tsx`, `DiscoveryDetail.tsx` | P1 |
| **P3: Item Actions Schema** | Extend dashboard.yaml + useActionRunner for item-level actions | `src/dashboard/lib/tabs/types.ts`, `hooks/useActionRunner.ts`, `hooks/useItemActions.ts` | P1 |
| **P4: Integration Map** | Visual component for showing skill connections | `src/dashboard/components/IntegrationMap.tsx` | P2 |
| **P5: install-discovery MCP** | New MCP tool that bridges Install → Factory → Plugin Mgmt | `plugins/ai/skills/install/mcp/__init__.py`, discovery YAML install_metadata | P3 |
| **P6: Factory Bridge** | Wire install-discovery to call create-plugin, install-plugin, skill-analyze | `plugins/ai/skills/install/mcp/__init__.py` (delegates to augur-mcp + mcp-app-factory) | P5 |
| **P7: Refactor Flow** | Post-install refactoring via skill-analyze + skill_refactor.py | Install item_action `refactor-item`, devops integration | P6 |
| **P8: Generalize** | Career + Knowledge + Capture adopt detail panel + item_actions | Per-skill dashboard.yaml updates, detail components | P3 |

**Phase dependency graph:**
```
P1 ──→ P2 ──→ P4
 │
 └──→ P3 ──→ P5 ──→ P6 ──→ P7
       │
       └──→ P8 (can start after P3)
```

P1-P3 are foundational. P4 (integration map) and P5-P7 (install pipeline) can proceed in parallel. P8 is independent once the src/lib components exist.

## Consequences

### Positive

1. **Complete user journey**: Users go from "what is this?" to "it's now part of my system" without leaving the Install page
2. **Reusable pattern**: DetailPanel + item_actions become a system-wide standard, reducing per-skill UI effort
3. **Discoverability**: Integration map reveals connections users wouldn't find on their own
4. **Reduced friction**: One-click install replaces manual Settings toggle + rebuild workflow
5. **Declarative**: Skill authors define item actions in YAML, no custom code needed for standard flows
6. **Cross-hub navigation**: Skills stop being isolated silos; integration links create a connected graph

### Negative

1. **New src/lib component**: `DetailPanel` becomes critical infrastructure that all skills depend on
2. **Schema expansion**: `dashboard.yaml` gets more complex (item_actions, requires_status, variant)
3. **Cross-skill coupling**: Install now depends on mcp-app-factory and augur-mcp plugin tools at runtime. If Factory's `create-plugin` changes its interface, Install's `install-discovery` breaks.
4. **Build system dependency**: Automatic rebuild after install requires solving the current manual `npm run build` step
5. **LLM reliability**: The "enhance" install type relies on AI to propose correct code changes to existing skills. This may produce invalid code or break existing functionality.
6. **Three-system coordination**: install-discovery must orchestrate Install data → Factory scaffolding → Plugin management → Build system. Failure at any step needs rollback.

### Neutral

1. **Existing page-level actions unchanged** — `actions[]` in dashboard.yaml works exactly as before
2. **Table components remain skill-owned** — only the detail panel is src/lib; list views stay custom
3. **Scoring algorithm unchanged** — evaluation logic in MCP tools stays the same
4. **Discovery YAML schema extends** — new `install_metadata` field added per-discovery; existing fields unchanged
5. **Factory tools unchanged** — `create-plugin`, `audit-plugin`, `skill-analyze` used as-is; no modifications needed to mcp-app-factory
6. **Plugin management tools unchanged** — `install-plugin`, `toggle-plugin`, `reload-plugin` used as-is from augur-mcp

## Alternatives Considered

### Alternative 1: Full-Page Detail View (Sub-Route)

Navigate to `/install/catalog/[id]` for each discovery detail page.

**Rejected**: Loses table context. User can't quickly scan through multiple items. Sub-routes add routing complexity and require loading data for a single item.

### Alternative 2: Inline Expansion (Accordion Rows)

Expand table rows in-place to show details.

**Rejected**: Limited space for rich content (integration map, score charts). Breaks table layout. Poor mobile experience.

### Alternative 3: Modal Instead of Slide-Over Panel

Use a centered modal dialog for details.

**Rejected**: Modals obstruct the table entirely. Slide-over panel keeps the table partially visible, maintaining context. Users can glance at the table while reading details.

### Alternative 4: Plugin Marketplace (Separate App)

Build a standalone marketplace app for skill discovery and installation.

**Rejected**: Over-engineering for a personal tool. Install + DetailPanel achieves the same goal within the existing dashboard architecture (ADR-003).

### Alternative 5: Skip Item Actions, Keep Page-Level Only

Only use page-level action buttons, requiring users to select items before triggering actions.

**Rejected**: Poor UX. Users expect to act on the item they're looking at, not select it and then find the right page-level button. Item-level actions reduce cognitive load.

## User Journeys

### Journey 1: Evaluate and Install an MCP Server Discovery

The most straightforward install type — the discovery points to an existing MCP server repo.

```
1. User opens /install/catalog
2. Sees 36 discoveries in the table
3. Filters by category "Developers", sorts by score
4. Clicks "MCP Debugger" row → detail panel slides open
5. Reads description: "Debug MCP server connections and tool calls"
6. Sees integration map: connects to Control Hub and Developer skill
7. Clicks "Evaluate" → AI scores it: relevance 78, popularity 45, integration 92
8. Overall score: 72 — looks good
9. Clicks "Approve" → status = approved
10. Clicks "Add to My Augur" →
    a. Install classifies: install_type = mcp (has github_url pointing to MCP server)
    b. Pre-check modal shows: "Install MCP server from github.com/x/mcp-debugger.
       Will add 3 new tools to Control Hub. No dependencies required."
    c. User confirms
11. Install calls install-discovery(id, type="mcp") →
    a. Delegates to install-plugin(source=github_url)
    b. Calls toggle-plugin(mcp-debugger, enabled=true)
    c. Calls plugin-health() — passes
12. Dashboard rebuilds, new tools appear in MCP tool list
13. Install updates: status = installed, install_metadata recorded
14. User navigates to Control Hub — sees new MCP debugger tools available
```

### Journey 2: Scaffold a New Skill Plugin from Discovery

The discovery describes a capability that doesn't exist yet — needs a full plugin.

```
1. User discovers "SEO Optimizer" from an article import (status: new)
2. Clicks row → detail panel shows: "Analyzes content for SEO keywords,
   readability scores, and meta tag suggestions"
3. Integration map shows: connects to Content Hub (content optimization)
   and Marketing category
4. User clicks "Evaluate" → relevance 85 (fills content gap),
   popularity 60, integration 70 → overall: 74
5. Clicks "Approve" → status = approved
6. Clicks "Add to My Augur" →
    a. Install classifies: install_type = plugin (no github_url,
       no overlaps_with — this is a new capability)
    b. Pre-check modal shows: "Create new skill plugin 'seo-optimizer'
       in plugins/ai/skills/. Will scaffold: SKILL.md,
       dashboard.yaml, mcp/__init__.py, API routes.
       Bundle: services. Features: mcp, dashboard, api."
    c. User confirms
7. Install calls install-discovery(id, type="plugin",
   features="mcp,dashboard,api") →
    a. Delegates to create-plugin(name="seo-optimizer",
       category="productivity", description=discovery.description,
       features=["mcp", "dashboard", "api"])
    b. Factory scaffolds full plugin skeleton
    c. AI reads source_url article for implementation hints,
       fills in MCP tool stubs
    d. Calls audit-plugin("seo-optimizer") → score 70 (basic scaffold)
    e. Calls toggle-plugin("seo-optimizer", enabled=true)
8. Dashboard rebuilds, /seo-optimizer appears in navigation
9. Install updates: status = installed, files_created recorded
10. User can now customize the scaffolded skill further
```

### Journey 3: Enhance an Existing Skill (Most Common)

The discovery overlaps with an existing skill — it should extend it, not create a new hub.

```
1. User discovers "Job Description Analyzer" (status: new)
2. Detail panel shows integration map:
   ┌──────────────────┐     ┌─────────────────────┐
   │  Job Description │────▶│  Career Hub          │
   │  Analyzer        │     │  - Enhances pipeline │
   │                  │────▶│  - Improves scoring  │
   └──────────────────┘     └─────────────────────┘
3. overlaps_with: ["career"] — this clearly extends Career
4. User evaluates → relevance 90 (direct gap fill), overall: 82
5. Clicks "Approve", then "Add to My Augur" →
    a. Install classifies: install_type = enhance
       (overlaps_with is non-empty, integration_ideas target career)
    b. Pre-check modal shows: "Enhance existing Career Hub.
       Will add new capabilities to plugins/career/skills/career/.
       Changes: new action button, possible new MCP tool."
    c. User confirms
6. Install calls install-discovery(id, type="enhance",
   target_skill="career") →
    a. Calls skill-analyze(plugins/career/skills/career) →
       returns current structure, capabilities, gaps
    b. AI proposes specific changes:
       - Add action: "Deep JD Analysis" (flow: llm) to career/dashboard.yaml
       - Add MCP tool: analyze-job-description to career/mcp/__init__.py
       - Add reference data: JD analysis prompts to career/modules/
    c. Shows proposed diff to user for review
    d. User approves 2 of 3 changes
    e. AI applies approved changes
    f. Calls audit-plugin("career") → still passes compliance
7. Install updates: status = installed, target_skill = career
8. User opens /career → sees new "Deep JD Analysis" action button
```

### Journey 4: Post-Install Refactoring

A skill was installed weeks ago. User wants to improve it.

```
1. User opens /install, filters status = installed
2. Clicks "SEO Optimizer" → detail panel shows install_metadata:
   installed_at: 2 weeks ago, audit_score: 70, type: plugin
3. Clicks "Refactor" action button →
    a. AI calls skill-analyze(plugins/ai/skills/scraper) <!-- seo-optimizer removed; using scraper as example -->
       returns: missing tests, no BACKLOG.md, hardcoded strings
    b. AI calls devops skill_refactor.py for structural analysis
       returns: can extract src/lib patterns, improve error handling
    c. Shows refactoring suggestions to user:
       - Add unit tests (3 files)
       - Create BACKLOG.md with improvement ideas
       - Extract API client to src/lib module
       - Improve error handling in MCP tools
    d. User selects which refactorings to apply
    e. AI applies changes
    f. audit-plugin("seo-optimizer") → score 70 → 88
4. Install updates: audit_score in install_metadata → 88
```

### Journey 5: Bulk Import from Article

```
1. User finds article "Top 50 AI Tools for 2026"
2. In chat: pastes URL, asks AI to extract skills
3. AI calls WebFetch, reads article content
4. AI calls analyze-import with extracted text
5. Returns structured list of 50 tools
6. User reviews in Install catalog (all status: new)
7. Clicks through each, reads details in detail panel
8. Batch flow: evaluates promising ones, approves 8, rejects 15
9. For the 8 approved: installs 2 as MCP servers, 3 as enhancements
   to existing skills, 3 as new plugin scaffolds
```

### Journey 6: Career Job Detail (Generalized Pattern)

Demonstrates the DetailPanel + item_actions pattern applied to a non-Install skill.

```
1. User opens /career/pipeline
2. Sees 12 jobs in table (inbox, active, archive)
3. Clicks "Senior Engineer at Acme Corp" → detail panel slides open
4. Sees: company info, salary range, match score, skill overlap analysis
5. Clicks "Analyze" → AI runs deep analysis, fills in match details
6. Clicks "Move to Active" → job moves from inbox to active pipeline
7. Clicks "Prep Interview" → AI generates interview prep materials
```

## References

- ADR-003: Skill-Owned UI Pattern — establishes plugin dashboard architecture
- ADR-017: Unified Context Management & Mode Separation — defines mode-aware filtering
- ADR-030: Unified AI Bridge with Context Switch — defines action button system
- Install skill: `plugins/ai/skills/install/`
- Plugin Factory (mcp-app-factory): `plugins/ai/skills/mcp-app-factory/`
  - MCP tools: `plugins/ai/skills/mcp-app-factory/mcp/__init__.py`
  - Scaffold script: `plugins/ai/skills/mcp-app-factory/scripts/scaffold.py`
  - Plugin creation chain: `plugins/ai/skills/mcp-app-factory/chains/plugin-creation.yaml`
  - Skill refactoring chain: `plugins/ai/skills/mcp-app-factory/chains/skill_refactoring.yaml`
- Plugin management (augur-mcp): `src/mcp/augur_mcp/domain/plugins.py`
  - Plugin loader: `src/plugins/loader.py`
  - Skill registry: `src/plugins/skill_registry.py`
  - Plugin registry: `src/plugins/registry.py`
- DevOps skill refactor: `plugins/dev/skills/devops/scripts/skill_refactor.py`
- Action runner: `src/dashboard/hooks/useActionRunner.ts`
- Plugin manager UI: `src/dashboard/app/settings/tabs/PluginsTab.tsx`
- Plugin state: `src/config/plugin_state.json`
- Plugin API: `src/dashboard/app/api/plugins/route.ts`
- Career dashboard.yaml: `plugins/career/skills/career/augur.yaml`
