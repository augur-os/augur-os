---
status: Implemented
date: '2026-02-17'
deciders:
- Project owner
related:
- ADR-109 (filesystem-driven dashboard)
- ADR-012 (config-driven dashboard)
- ADR-108 (hub rebalancing)
- ADR-105 (plugin-driven tool scoping)
hub: null
tags:
- bundle
- overview
- template
- product
- value
superseded_by: null
---

# ADR-110: Bundle Overview Template — Product Value at a Glance

## Context

### The Problem

Augur has 14 bundles (ADR-109) with ~35 nav skills, but there is no consistent way for a user to understand what any bundle offers. Every overview page is a snowflake:

| Pattern | Count | Examples | Problem |
|---------|-------|----------|---------|
| Fully static (hardcoded cards, zero live data) | 3 | growth, wealth, creative | Shows nothing useful — placeholder pages |
| Server-side data fetch (custom getX() calls) | 2 | career, lifestyle | Works but bespoke — 7 parallel fetches in lifestyle alone |
| Client-side fetch (useEffect + APIs) | 4 | health, home, knowledge, project-dev | Each invents its own loading/error states |
| Bridge-specific (HubOverviewWidgets) | 1 | finance | One-off component used nowhere else |
| Tab dispatch (no overview at all) | 1 | observe | Skips overview entirely, goes to tab content |
| Hardcoded product copy | 1 | venture | Marketing content, not a dashboard |

**39 hub pages. 6 different patterns. Zero src/lib template.**

The closest thing to a standard is `GlassCard` (used by ~8 pages) and the `glass-panel` CSS class. "Connected Hubs" appears on almost every page but is implemented 5 different ways (GlassCard, glass-panel div, DashboardWidget, GlassLinkCard, RelatedHubs component).

### What's Missing

No overview page answers the fundamental questions:

1. **What does a user want to accomplish?** — Goals for this area of life/work
2. **What multi-step workflows are available?** — Chains that automate complex tasks
3. **Which tools are needed?** — Built-in actions + MCP tool integrations
4. **What domain knowledge is embedded?** — Best practices, frameworks, standards

Instead, pages either show raw data without context (career: "3 active jobs" — so what?) or show nothing at all (growth: empty cards with `value: 0`).

### What Already Exists

The infrastructure for a template-driven approach is already built:

| Component | Status | Role in Template |
|-----------|--------|-----------------|
| `HubRenderer` + `SectionRenderer` | Exists, underused | Config-driven rendering from dashboard.yaml |
| `DashboardYaml` type system | Exists | Full typed schema for hub config |
| `dashboard.yaml sections:` | Exists, only health uses it | Declarative section definitions |
| Chain YAML files | Exist (~20+ chains) | Workflow metadata: name, description, triggers, agents |
| `SKILL.md` frontmatter | Exists | Skill metadata: description, triggers, mcp_servers |
| `dashboard.yaml mcp.tools` | Exists | Tool declarations per skill |
| `dashboard.yaml actions[]` | Exists | Quick actions with flow types (fast/llm/modal) |
| `discoverPluginDashboards()` | Exists | Scans all bundles for dashboard.yaml |
| `GlassCard`, `glass-panel` | Exist | Shared visual primitives |

The pieces exist. They just aren't composed into a unified template.

### Design Principles

1. **One template, all bundles** — Every bundle uses the same overview template. No custom page.tsx per bundle. Consistent UX, zero per-bundle React code.
2. **overview.yaml is the authoring surface** — Bundle owners declare goals, knowledge, and featured content in a single YAML file. Everything else is auto-discovered.
3. **Build-time generation** — The build script reads overview.yaml + skill metadata and generates the overview page component. No runtime YAML parsing.
4. **Hybrid content model** — Goals and knowledge are authored (human intent). Workflows and tools are discovered (machine aggregation). Both appear on the page.
5. **Combined value + operational** — Top section shows product value (what you can do). Bottom section shows live data (what's happening now). First visit = education, return visit = operational.
6. **Skill cards for multi-skill bundles** — Bundles with 2+ nav skills show a card grid linking to each skill. Single-skill bundles skip straight to operational data.
7. **No backward compatibility** — This replaces ALL existing custom overview page.tsx files. After migration, every bundle uses the template. Clean and minimal (ADR-109 principle #8).

## Decision

### 1. Introduce overview.yaml at Bundle Level

A new file `plugins/{bundle}/overview.yaml` declares the bundle's product value. This is the only file a bundle owner needs to author — everything else is discovered.

```yaml
# plugins/career/overview.yaml
version: 1

# === AUTHORED CONTENT (human intent) ===

goals:
  title: "Career Management"
  subtitle: "Track opportunities, grow skills, build your professional brand"
  items:
    - "Find and track job opportunities through your pipeline"
    - "Develop professional skills with structured growth plans"
    - "Create and publish content that builds your brand"

knowledge:
  - label: "Job Search Strategy"
    description: "Structured pipeline from discovery → application → interview → offer"
  - label: "Skill Gap Analysis"
    description: "Map current skills to target roles, identify learning priorities"
  - label: "Content Calendar"
    description: "Consistent publishing cadence across platforms"

# === ACTION COMMANDS (one-click multi-step chains) ===

actions:
  - id: import-linkedin-jobs
    label: "Import Jobs from LinkedIn"
    description: "Fetch LinkedIn job alerts from email, parse, score, save to pipeline"
    icon: "Mail"
    chain: "career/career/chains/linkedin_import.yaml"
    inputs:
      - name: email_filter
        label: "Email filter"
        type: text
        default: "subject:LinkedIn Jobs"
    color: "blue"

  - id: analyze-resume
    label: "Analyze Resume"
    description: "Parse resume and compare against target job descriptions"
    icon: "FileText"
    chain: "career/career/chains/resume_analysis.yaml"
    inputs:
      - name: resume_path
        label: "Resume file"
        type: file
        default: "~/Documents/Resume/latest.pdf"
    color: "green"

# === EXTERNAL SOURCES (paste a link to add knowledge) ===

external_sources:
  default_paths:
    - path: "~/Documents/Resume/"
      label: "Resume folder"
    - path: "~/Documents/Career/"
      label: "Career documents"
  allow_user_additions: true

# === OPTIONAL OVERRIDES ===

# Override auto-discovered workflows (default: aggregate all chains in bundle)
# featured_workflows:
#   - chain: career/career/chains/job_pipeline.yaml
#     highlight: true
#   - chain: career/growth/chains/skill_assessment.yaml

# Override auto-discovered stats (default: aggregate all skills' overview stats)
# stats:
#   - label: "Active Jobs"
#     source: "/api/career/jobs?status=active"
#     transform: "data.length"
#     icon: "Briefcase"
#     color: "blue"

# Cross-bundle references (replaces hardcoded "Connected Hubs")
related_bundles:
  - bundle: "professional"
    reason: "Career feeds into your professional ventures"
  - bundle: "finance"
    reason: "Career decisions affect compensation and financial planning"
  - bundle: "ai"
    reason: "AI tools assist with resume, interview prep, and content"
```

**File location**: `plugins/{bundle}/overview.yaml` — at the bundle root, NOT inside any skill. This is the only bundle-level config file.

**Schema**:

| Field | Required | Type | Source |
|-------|----------|------|--------|
| `version` | Yes | number | Static (schema version) |
| `goals.title` | Yes | string | Authored — bundle display name |
| `goals.subtitle` | Yes | string | Authored — one-line value proposition |
| `goals.items` | Yes | string[] | Authored — what the user can accomplish |
| `knowledge` | Yes | object[] | Authored — embedded domain expertise |
| `knowledge[].label` | Yes | string | Authored |
| `knowledge[].description` | Yes | string | Authored |
| `actions` | No | object[] | Authored — one-click chain commands (merged with auto-discovered overview: true chains) |
| `actions[].id` | Yes | string | Authored — unique action identifier |
| `actions[].label` | Yes | string | Authored — display name on action card |
| `actions[].chain` | Yes | string | Authored — path to chain YAML relative to plugins/ |
| `actions[].inputs` | No | object[] | Authored — user-configurable parameters before execution |
| `external_sources` | No | object | Authored — paste-to-add knowledge sources |
| `external_sources.default_paths` | No | object[] | Authored — pre-registered local folders/files |
| `external_sources.allow_user_additions` | No | boolean | Default: true — enable runtime paste-to-add |
| `featured_workflows` | No | object[] | Override — curated list (default: auto-discover) |
| `stats` | No | object[] | Override — curated stats (default: auto-discover) |
| `related_bundles` | No | object[] | Authored — cross-bundle links |

### 2. Auto-Discovery at Build Time

The build script discovers everything that overview.yaml doesn't explicitly declare:

#### Workflow Discovery

```
For each bundle:
  For each skill in plugins/{bundle}/skills/:
    For each chain in plugins/{bundle}/skills/{skill}/chains/*.yaml:
      Parse: name, description, category, triggers, agents[].name
      Add to bundle's workflow list
  Sort by: featured first, then alphabetical
  Limit: top 8 workflows (overflow → "View all N workflows" link)
```

Chain YAML already has rich metadata:
```yaml
name: feature_development
description: Comprehensive feature development workflow
category: factory
triggers: ["develop feature", "new feature workflow"]
agents:
  - name: architect
    action: explore_codebase
```

The overview page renders each workflow as a card showing name, description, trigger phrase, and participating agents.

#### Tool Discovery

```
For each skill in bundle:
  Parse dashboard.yaml → mcp.tools[], actions[]
  Parse SKILL.md frontmatter → mcp_servers[]
  Collect: tool names, action labels, MCP server names
  Deduplicate across skills
```

The overview page renders tools as a compact badge/chip list, grouped by type (MCP tools, quick actions, API endpoints).

#### Stat Discovery

```
For each skill in bundle:
  Parse dashboard.yaml → tabs[0].sections[] (if type=metrics-grid)
  Parse dashboard.yaml → actions[] (if flow=fast and has endpoint)
  Collect: stat definitions with labels, sources, icons, colors
  Limit: top 4-6 stats for the overview
```

Stats that reference `mcp://` or `/api/` sources are fetched at runtime by the rendered page component. Stats with `static:` sources are inlined at build time.

#### Skill Card Discovery

```
For each skill in bundle:
  If skill has dashboard.yaml with hub.id:
    Extract: hub.title, hub.subtitle, hub.icon, hub_id (for link)
    Add to skill cards list
  Skip backend-only skills (no dashboard.yaml)
If skill count >= 2:
  Render skill cards grid on overview page
Else:
  Skip grid (single-skill bundle)
```

### 3. Overview Page Template Structure

Every bundle overview renders the same template with 9 sections:

```
┌─────────────────────────────────────────────┐
│  HERO                                        │
│  Bundle title + subtitle (from goals)        │
│  Goals list (from goals.items)               │
│  Knowledge badges (from knowledge[])         │
├─────────────────────────────────────────────┤
│  SEARCH BAR                                  │
│  ┌──────────────────────────────┐            │
│  │ 🔍 Search career knowledge...│ [scope: 📁│
│  └──────────────────────────────┘  career]   │
│  Scoped to bundle RAG index by default       │
│  Clear scope → search all indexes            │
├─────────────────────────────────────────────┤
│  SKILL CARDS (only if 2+ nav skills)         │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐           │
│  │Career│ │Growth│ │Content│ │...  │          │
│  └─────┘ └─────┘ └─────┘ └─────┘           │
├─────────────────────────────────────────────┤
│  ACTION COMMANDS                              │
│  ┌──────────────────┐ ┌──────────────────┐   │
│  │ 📧 Import Jobs   │ │ 📊 Parse Balance │   │
│  │ from LinkedIn     │ │ Sheet from Excel │   │
│  │ email→parse→score │ │ file→parse→update│   │
│  └──────────────────┘ └──────────────────┘   │
│  Multi-step chains: internal MCP + external  │
│  MCP + prompts. Trigger with one click.      │
├─────────────────────────────────────────────┤
│  EXTERNAL SOURCES                             │
│  ┌────────────┐ ┌────────────┐ [+ Add Link] │
│  │📁 ~/Resume │ │🔗 LinkedIn │              │
│  │  3 files   │ │  Connected │              │
│  └────────────┘ └────────────┘              │
│  Paste a link to file/folder/URL to add     │
│  Auto-indexes into bundle's RAG project     │
├─────────────────────────────────────────────┤
│  LIVE STATS                                  │
│  ┌───┐ ┌───┐ ┌───┐ ┌───┐                   │
│  │ 12│ │ 3 │ │ 87│ │ 5 │ stat tiles         │
│  └───┘ └───┘ └───┘ └───┘                   │
├─────────────────────────────────────────────┤
│  RECENT ACTIVITY                             │
│  Latest items/events from skills in bundle   │
│  Aggregated timeline view                    │
├─────────────────────────────────────────────┤
│  RELATED BUNDLES                             │
│  ┌────────────┐ ┌────────────┐              │
│  │Professional │ │ Finance    │              │
│  │ reason...   │ │ reason...  │              │
│  └────────────┘ └────────────┘              │
└─────────────────────────────────────────────┘
```

**Section behavior**:

| Section | Content Source | Rendering | Empty State |
|---------|--------------|-----------|-------------|
| Hero | overview.yaml `goals` + `knowledge` | Static (build-time) | Required — build fails without overview.yaml |
| Search Bar | RAG API scoped to bundle's RAG project | Dynamic (client-side) | Empty input with placeholder "Search {bundle} knowledge..." |
| Skill Cards | Auto-discovered from skills' dashboard.yaml | Static (build-time) | Hidden if < 2 nav skills |
| Action Commands | Auto-discovered from chains/*.yaml + overview.yaml `actions` | Dynamic (client-side, triggers chain execution) | "No actions configured" message |
| External Sources | Bridge connections API + overview.yaml defaults | Dynamic (client-side) | "Add your first source" prompt with paste input |
| Live Stats | Auto-discovered stats with runtime API/MCP fetch | Dynamic (client-side) | Skeleton loading → "No data yet" |
| Recent Activity | Aggregated from skills' activity APIs | Dynamic (client-side) | "No recent activity" |
| Related Bundles | overview.yaml `related_bundles` | Static (build-time) | Hidden if not declared |

### 4. Build Pipeline Integration

New build step: `generate-overview-pages` — runs as part of `npm run prebuild`, after `mount-plugins` and before `generate-tabs`.

```
Updated build sequence (from ADR-109):

1. build:scripts         → Compile TS scripts to JS
2. setup-mcp             → Configure MCP connections
3. generate-registry     → Python: generate skill registry
4. mount-plugins         → Discover bundles/skills, copy dashboard/ → app/
5. generate-overviews    → NEW: For each bundle with overview.yaml:
   │                        Read overview.yaml
   │                        Discover chains, tools, stats, skills in bundle
   │                        Generate overview data JSON
   │                        Generate page.tsx from template + data
   │                        Write to src/dashboard/app/{primary-hub-id}/page.tsx
   │                        (overwrites the skill's mounted page.tsx)
   │
6. generate-tabs         → Discover bundles/skills, write generated-registry.ts
7. next build/dev        → Next.js compiles from src/dashboard/app/
```

**Route mounting**: The overview page mounts at the bundle's "primary" skill route. The primary skill is determined by:
1. The skill whose `hub.id` matches the bundle name (e.g., `career` skill in `career/` bundle)
2. If no match, the first skill alphabetically with `dashboard.yaml`
3. Single-skill bundles: that skill IS the primary

For a bundle like `career/` (ADR-109: career, content, growth, linkedin-writer):
- Primary skill: `career` (hub.id matches bundle name)
- Overview page mounts at `/career` (overwrites career skill's page.tsx)
- `/growth`, `/creative` keep their own skill-specific pages

**Generated output**: Two files per bundle:

```typescript
// src/dashboard/app/career/.overview-data.json (generated, gitignored)
{
  "goals": { "title": "Career Management", "subtitle": "...", "items": [...] },
  "knowledge": [...],
  "searchConfig": {
    "bundleId": "career",
    "ragProject": "bundle_career",
    "placeholder": "Search career knowledge..."
  },
  "skills": [
    { "id": "career", "title": "Job Tracker", "icon": "Briefcase", "href": "/career" },
    { "id": "growth", "title": "Growth", "icon": "TrendingUp", "href": "/growth" },
    { "id": "creative", "title": "Content", "icon": "Pen", "href": "/creative" }
  ],
  "actions": [
    {
      "id": "import-linkedin-jobs",
      "label": "Import Jobs from LinkedIn",
      "description": "Fetch LinkedIn job alerts from email, parse, score, save to pipeline",
      "icon": "Mail",
      "chain": "career/career/chains/linkedin_import.yaml",
      "inputs": [{ "name": "email_filter", "label": "Email filter", "type": "text", "default": "subject:LinkedIn Jobs" }],
      "color": "blue",
      "stepCount": 5
    },
    {
      "id": "analyze-resume",
      "label": "Analyze Resume",
      "description": "Parse resume and compare against target job descriptions",
      "icon": "FileText",
      "chain": "career/career/chains/resume_analysis.yaml",
      "inputs": [{ "name": "resume_path", "label": "Resume file", "type": "file", "default": "~/Documents/Resume/latest.pdf" }],
      "color": "green",
      "stepCount": 3
    }
  ],
  "externalSources": {
    "defaultPaths": [
      { "path": "~/Documents/Resume/", "label": "Resume folder" },
      { "path": "~/Documents/Career/", "label": "Career documents" }
    ],
    "allowUserAdditions": true
  },
  "workflows": [
    { "name": "Job Pipeline", "description": "...", "triggers": [...], "agents": [...], "skill": "career" },
    { "name": "Skill Assessment", "description": "...", "triggers": [...], "agents": [...], "skill": "growth" }
  ],
  "tools": {
    "mcp": ["context7", "augur", "brightdata"],
    "actions": [{ "label": "Add Job", "flow": "fast" }, { "label": "Health Review", "flow": "llm" }]
  },
  "stats": [...],
  "relatedBundles": [...]
}

// src/dashboard/app/career/page.tsx (generated, overwrites mounted skill page)
// AUTO-GENERATED by generate-overview-pages — do not edit
// Source: plugins/career/overview.yaml
// Edit the overview config, not this file.
import { BundleOverview } from '@/components/overview/BundleOverview';
import overviewData from './.overview-data.json';

export default function CareerOverviewPage() {
  return <BundleOverview data={overviewData} bundleId="career" />;
}
```

### 5. The BundleOverview Component

A single src/lib React component that renders all 9 sections from the generated data:

```
src/dashboard/components/overview/
├── BundleOverview.tsx              ← Main template component
├── sections/
│   ├── HeroSection.tsx             ← Goals + knowledge badges
│   ├── SearchBarSection.tsx        ← RAG search scoped to bundle (client)
│   ├── SkillCardsSection.tsx       ← Grid of skill cards (conditional)
│   ├── ActionCommandsSection.tsx   ← Multi-step chain execution (client)
│   ├── ExternalSourcesSection.tsx  ← Link paste + source management (client)
│   ├── LiveStatsSection.tsx        ← Dynamic stat tiles (client-side fetch)
│   ├── RecentActivitySection.tsx   ← Aggregated timeline (client-side fetch)
│   └── RelatedBundlesSection.tsx   ← Cross-bundle links
└── types.ts                        ← OverviewData interface
```

`BundleOverview.tsx` is a Server Component that renders static sections (Hero, SkillCards, RelatedBundles) directly and wraps dynamic sections (SearchBar, ActionCommands, ExternalSources, LiveStats, RecentActivity) in Suspense boundaries with skeleton fallbacks.

Note: `WorkflowsSection` and `ToolsSection` from the original design are MERGED into `ActionCommandsSection`. The distinction between "informational workflow list" and "executable actions" was artificial — every workflow IS an action the user can trigger. Chains that declare `overview: true` appear as action cards. The full chain registry is still accessible via the knowledge search bar.

**No per-bundle customization in React** — all visual differences come from the data (overview.yaml + auto-discovered metadata). The component just maps data → sections.

### 6. Migration: Replace All Existing Overview Pages

Every existing custom `page.tsx` that serves as a hub overview is replaced by the generated template page. The custom content is migrated to `overview.yaml`.

**Migration map** (current custom pages → overview.yaml):

| Bundle (ADR-109) | Current Primary Page | Stats Source | What Migrates to overview.yaml |
|-------------------|---------------------|-------------|-------------------------------|
| career | career/dashboard/page.tsx (server, getJobs) | getJobs() API | goals, knowledge, stats config, related_bundles |
| finance | finance/dashboard/page.tsx (client, HubOverviewWidgets) | /api/bridge/summary | goals, knowledge, stats config |
| health | health/dashboard/page.tsx (client, 3 APIs) | /api/health/* | goals, knowledge, stats config |
| lifestyle | lifestyle/dashboard/page.tsx (server, 7 fetches) | 7 getX() functions | goals, knowledge, stats config |
| home | home-automation/dashboard/page.tsx (client, 3 APIs) | /api/home/* | goals, knowledge, stats config |
| ai | ai_bridge/dashboard/page.tsx | varies | goals, knowledge |
| productivity | eisenhower/dashboard/page.tsx | varies | goals, knowledge |
| professional | venture-augur/dashboard/page.tsx (hardcoded copy) | none | goals (from existing copy), knowledge |
| dev | advisor/dashboard/page.tsx (src/lib hub) | varies | goals, knowledge |
| admin | settings/dashboard/page.tsx | none | goals, knowledge |
| consulting | client-ai-consulting/dashboard/page.tsx | varies | goals, knowledge |
| enterprise | enterprise/dashboard/page.tsx | varies | goals, knowledge |
| observability | observe/dashboard/page.tsx (tab dispatch) | varies | goals, knowledge |
| orchestration | (no nav skills — backend only) | N/A | No overview needed |

**orchestration/** is the only bundle with zero nav skills (all backend-only). It gets no overview page.

**What happens to existing custom page.tsx files**: Deleted from plugin source after migration. The generated overview replaces them entirely. Custom content (hardcoded stats, product copy, action buttons) is extracted into overview.yaml fields. Runtime data fetching logic is replaced by the template's standardized stat/activity fetching.

### 7. overview.yaml Validation

Add validation to the CI pipeline (extends `validate-nav-alignment.ts` from ADR-109):

```typescript
// Assertions:
1. Every bundle with 1+ nav skills MUST have overview.yaml
2. overview.yaml MUST have goals.title, goals.subtitle, goals.items (non-empty)
3. overview.yaml MUST have knowledge (non-empty array)
4. featured_workflows (if declared) must reference existing chain YAML files
5. stats (if declared) must have valid source (mcp://, /api/, or static:)
6. related_bundles (if declared) must reference existing bundle names
7. Backend-only bundles (orchestration) must NOT have overview.yaml
```

### 8. Zod Schema for overview.yaml

Type-safe parsing using Zod (consistent with existing dashboard.yaml validation pattern):

```typescript
// src/dashboard/lib/plugin-schema/overview-schema.ts

const OverviewGoalsSchema = z.object({
  title: z.string().min(1),
  subtitle: z.string().min(1),
  items: z.array(z.string().min(1)).min(1).max(10),
});

const KnowledgeItemSchema = z.object({
  label: z.string().min(1),
  description: z.string().min(1),
});

const StatOverrideSchema = z.object({
  label: z.string(),
  source: z.string().regex(/^(mcp:\/\/|\/api\/|static:)/),
  transform: z.string().optional(),
  icon: z.string().optional(),
  color: z.string().optional(),
});

const WorkflowOverrideSchema = z.object({
  chain: z.string(),  // relative path to chain YAML
  highlight: z.boolean().optional(),
});

const RelatedBundleSchema = z.object({
  bundle: z.string().min(1),
  reason: z.string().min(1),
});

const DefaultPathSchema = z.object({
  path: z.string().min(1),
  label: z.string().min(1),
});

const ExternalSourcesConfigSchema = z.object({
  default_paths: z.array(DefaultPathSchema).optional(),
  allow_user_additions: z.boolean().optional().default(true),
});

export const OverviewYamlSchema = z.object({
  version: z.literal(1),
  goals: OverviewGoalsSchema,
  knowledge: z.array(KnowledgeItemSchema).min(1),
  featured_workflows: z.array(WorkflowOverrideSchema).optional(),
  actions: z.array(ActionCommandSchema).optional(),
  external_sources: ExternalSourcesConfigSchema.optional(),
  stats: z.array(StatOverrideSchema).optional(),
  related_bundles: z.array(RelatedBundleSchema).optional(),
});
```

### 9. Bundle-Scoped Search Bar

Every overview page includes a search bar that queries the RAG knowledge system. The search is scoped to the bundle's folder by default — the user can clear the scope to search across all indexed knowledge.

**How it works:**

```
User types query in search bar
  → scope = bundle (default)
    → GET /api/knowledge/search?q={query}&project=bundle_{bundleName}
    → Searches only files indexed under this bundle's RAG project
  → scope = all (user clears scope chip)
    → GET /api/knowledge/search?q={query}
    → Searches all RAG indexes across the entire project
```

**RAG project per bundle**: The build script (or first-run initialization) creates a RAG project named `bundle_{bundleName}` with sources pointing to the bundle's plugin directory:

```yaml
# plugins/ai/skills/knowledge/data/rag/projects/bundle_career/sources.yaml
sources:
  - path: plugins/career/skills/career/augur/
  - path: plugins/career/skills/growth/data/
  - path: plugins/career/skills/content/data/
  # Plus any user-added external sources (see Decision 10)
```

This leverages the existing RAG infrastructure (`plugins/ai/skills/knowledge/data/rag/projects/{project-id}/`) without modification. The only new code is:
1. A build step that creates bundle RAG projects from the discovered bundle/skill structure
2. The `SearchBar` component scoped to the bundle's project ID

**Component**: `SearchBarSection.tsx` — a client component that:
- Shows an input with placeholder "Search {bundleTitle} knowledge..."
- Displays a scope chip (`📁 career` by default, clickable to expand to "All")
- Calls `/api/knowledge/search` with the project filter
- Renders results inline below the search bar (expandable)
- Results link to the source file/document

**No overview.yaml config needed** — search is always present on every overview. The scope is derived from the bundle name. The only configuration is whether additional external sources are registered (Decision 10).

### 10. External Source Resolution

Users can add external knowledge sources (files, folders, URLs) to any bundle by pasting a link directly on the overview page. Added sources are indexed into the bundle's RAG project and become searchable via the search bar (Decision 9).

**How it works:**

```
User pastes a link on the overview page
  → Link type detected:
    file:///path/to/file.pdf       → Local file
    /Users/me/Documents/Resume/    → Local folder
    https://notion.so/page/...     → Notion page (future)
    https://docs.google.com/...    → Google Doc (future)
  → POST /api/bridge/connections
    { hub: bundleName, type: "folder"|"url", path: "..." }
  → Backend:
    1. Saves connection to plugins/{bundle}/data/connections.yaml
    2. Calls /api/knowledge/linked-folders to register path in RAG
    3. Triggers indexing of the new source into bundle_{bundleName} project
  → Source appears in External Sources section with file count and status
```

This reuses the existing Hub Data Bridge (ADR-086) infrastructure:
- `ExternalSourcesSection` component already handles connections and display
- `/api/bridge/connections` API already stores connections per hub
- Knowledge RAG already supports linked folders via `/api/knowledge/linked-folders`

**What's new**: The overview template embeds `ExternalSourcesSection` with a simplified "paste a link" input at the top. No wizard needed — just paste and it auto-detects the type.

**overview.yaml optional defaults**:

```yaml
# plugins/career/overview.yaml
external_sources:
  default_paths:
    - path: "~/Documents/Resume/"
      label: "Resume folder"
    - path: "~/Documents/Career/"
      label: "Career documents"
  allow_user_additions: true  # default: true
```

Default paths are auto-registered on first build. Users can add more at runtime via the paste input.

### 11. Action Commands — Multi-Step Chain Execution

The most powerful section of the overview template. Action commands are multi-step workflows (chains) that users trigger with one click. Each action can orchestrate internal MCP tools, external MCP servers, prompt-based AI processing, and cross-bundle data.

**What makes this different from the "Workflows" section**: Workflows (Decision 2) are informational — they show what chains exist. Action Commands are operational — they execute chains with configured parameters, show progress, and write results back to the dashboard.

#### Action Command Architecture

```
User clicks "Import Jobs from LinkedIn"
  → Action UI shows parameter form (if action has inputs)
  → POST /api/agents/chain
    { chain_name: "career_linkedin_import", user_input: "...", dry_run: false }
  → Chain executor orchestrates steps:

    Step 1: Internal MCP → augur/get-emails
            Filter: subject contains "LinkedIn Jobs"
            Output: email_body (HTML)

    Step 2: Prompt → parse_job_listings
            Input: email_body
            Output: structured job list [{title, company, url, ...}]

    Step 3: External MCP → brightdata/scrape-linkedin-job
            Input: job URLs from step 2
            Output: full job details [{description, requirements, salary, ...}]

    Step 4: Prompt → score_jobs
            Input: job details + career/data/scoring_criteria.yaml
            Output: scored job list with match percentages

    Step 5: Internal MCP → augur/save-jobs
            Input: scored jobs
            Output: saved to career pipeline

  → Progress shown in real-time on the action card
  → Results: "5 new jobs imported, 2 scored above 80%"
  → Dashboard stats refresh automatically
```

#### Another Example: Finance Balance Sheet Import

```
User clicks "Parse Balance Sheet"
  → Action UI shows file picker or uses default Excel path
  → Chain executor:

    Step 1: Internal MCP → augur/read-file
            Input: ~/Documents/Finance/balance_2026_Q1.xlsx
            Output: raw Excel data

    Step 2: Prompt → parse_excel_balance_sheet
            Input: raw data + parsing rules from finance/data/excel_schema.yaml
            Output: structured financial data {assets, liabilities, equity, ...}

    Step 3: Internal MCP → augur/update-finance-data
            Input: parsed financial data
            Output: dashboard metrics updated

  → Results: "Balance sheet parsed: $X assets, $Y liabilities"
  → Finance stats tiles update in real-time
```

#### How Actions Are Defined

Actions are declared in `overview.yaml` under the `actions` key. Each action references a chain YAML file and optionally overrides parameters:

```yaml
# plugins/career/overview.yaml
actions:
  - id: import-linkedin-jobs
    label: "Import Jobs from LinkedIn"
    description: "Fetch latest LinkedIn job alerts from email, parse, score, and save to pipeline"
    icon: "Mail"
    chain: "career/career/chains/linkedin_import.yaml"
    inputs:
      - name: email_filter
        label: "Email filter"
        type: text
        default: "subject:LinkedIn Jobs"
    schedule: "daily"  # optional: auto-run on schedule
    color: "blue"

  - id: parse-resume
    label: "Analyze Resume"
    description: "Parse your resume and compare against target job descriptions"
    icon: "FileText"
    chain: "career/career/chains/resume_analysis.yaml"
    inputs:
      - name: resume_path
        label: "Resume file"
        type: file
        default: "~/Documents/Resume/latest.pdf"
    color: "green"
```

Actions can also be auto-discovered from chain YAML files that declare `overview: true`:

```yaml
# plugins/career/skills/career/chains/linkedin_import.yaml
name: linkedin_import
description: Import LinkedIn job alerts from email
overview: true          # ← surfaces this chain as an overview action command
overview_label: "Import Jobs from LinkedIn"
overview_icon: "Mail"
overview_color: "blue"
category: import
triggers: ["import linkedin jobs", "check job emails"]
agents:
  - name: email_reader
    action: get_emails
    mcp_server: augur           # internal MCP
    tool: get-emails
    params:
      filter: "subject:LinkedIn Jobs"
    output: email_body

  - name: parser
    action: parse_listings
    type: prompt                 # LLM processing step
    prompt: "Extract job listings from this email: {email_body}"
    output: job_list

  - name: scraper
    action: scrape_details
    mcp_server: brightdata       # external MCP server
    tool: scrape-linkedin-job
    input: job_list[].url
    output: job_details

  - name: scorer
    action: score_jobs
    type: prompt
    prompt: "Score these jobs against criteria: {scoring_criteria}"
    context_files:
      - "plugins/career/skills/career/augur/scoring_criteria.yaml"
    output: scored_jobs

  - name: saver
    action: save_to_pipeline
    mcp_server: augur
    tool: save-jobs
    input: scored_jobs
```

#### Chain Step Types

| Type | How It Executes | Example |
|------|----------------|---------|
| `mcp_server: augur` | Calls tool on the internal Augur MCP server via MCPBridge | get-emails, save-jobs, read-file |
| `mcp_server: {external}` | Calls tool on an external MCP server (configured in MCP settings) | brightdata/scrape-linkedin-job, context7/query-docs |
| `type: prompt` | Sends prompt + context to LLM for processing | Parse email HTML → structured data, Score jobs against criteria |
| `type: script` | Executes a Python/Node script locally | Excel parsing, file transformation |
| `action: api_call` | Calls an HTTP endpoint directly | POST to external API, webhook trigger |

#### Cross-Bundle Actions

Actions can reference data and tools from other bundles. The chain YAML explicitly declares cross-bundle dependencies:

```yaml
# A career action that uses AI bundle's knowledge search
agents:
  - name: researcher
    action: search_company
    mcp_server: augur
    tool: knowledge-search
    params:
      project: "bundle_ai"       # cross-bundle RAG search
      query: "{company_name} culture interview process"
```

This is safe because MCP tools are registered globally — the chain executor has access to all tools regardless of which bundle the chain belongs to. The bundle scoping (ADR-105) applies to the dashboard UI, not to chain execution.

#### Action Command UI Component

`ActionCommandsSection.tsx` — a client component that:
- Renders action cards in a responsive grid (2-3 columns)
- Each card shows: icon, label, description, step count, last run time
- Click → expands to show inputs (if any) + "Execute" button
- During execution → shows step-by-step progress with status indicators
- After completion → shows result summary + "View Details" link
- Scheduled actions show next run time and last result

**Zod schema addition:**

```typescript
const ActionInputSchema = z.object({
  name: z.string(),
  label: z.string(),
  type: z.enum(['text', 'file', 'select', 'number']),
  default: z.string().optional(),
  options: z.array(z.string()).optional(),  // for select type
});

const ActionCommandSchema = z.object({
  id: z.string(),
  label: z.string(),
  description: z.string(),
  icon: z.string().optional(),
  chain: z.string(),  // path to chain YAML
  inputs: z.array(ActionInputSchema).optional(),
  schedule: z.string().optional(),  // cron or named schedule
  color: z.string().optional(),
});
```

**Files affected:**
- `src/dashboard/components/overview/sections/ActionCommandsSection.tsx` — New component
- `src/dashboard/components/overview/sections/SearchBarSection.tsx` — New component
- Chain YAML schema — add `overview`, `overview_label`, `overview_icon`, `overview_color` fields
- `src/dashboard/lib/plugin-schema/overview-schema.ts` — Add ActionCommandSchema, ExternalSourcesConfigSchema

## Consequences

### Positive

- **Consistent product story** — Every bundle answers the same questions: goals, workflows, tools, knowledge, actions. Users understand value before interacting.
- **Zero custom React per bundle** — Bundle owners author YAML, the build generates the page. No more 39 snowflake page.tsx files.
- **Auto-discovery reduces drift** — Workflows and tools surface automatically from chain YAML and dashboard.yaml. Adding a new chain → it appears on the overview. No manual update needed.
- **Unified live data pattern** — Stats and activity use a standardized fetch pattern with skeleton loading. No more per-page useEffect/loading state boilerplate.
- **New bundles get overview for free** — Create `plugins/{bundle}/overview.yaml`, run build → complete overview page appears with skill cards, workflows, tools, search, and external sources.
- **Skill cards surface bundle depth** — Multi-skill bundles (career with 4 skills, ai with 5) show their full capability via the skill cards grid.
- **Scoped search makes knowledge accessible** — Every bundle has a search bar scoped to its own RAG index. Users find domain-specific knowledge without wading through all indexes. One click to expand to global search.
- **External sources turn passive pages into knowledge hubs** — Paste a link → folder gets indexed → searchable from the overview. Each bundle accumulates its own knowledge base over time.
- **Action commands close the loop** — Users don't just see data — they act on it. One-click chains that span internal MCP, external MCP (brightdata, context7), and LLM processing. The overview becomes a command center, not just a dashboard.

### Negative

- **Loss of per-bundle customization** — Venture's hardcoded product copy, finance's HubOverviewWidgets bridge, observe's tab dispatch — all replaced. Some nuance may be lost in favor of consistency.
- **Migration effort** — 13 bundles need overview.yaml authored (including actions and external source defaults). ~12 custom page.tsx files need content extracted. Chains need `overview: true` flags where applicable.
- **Build step dependency** — `generate-overviews` runs after `mount-plugins` (needs skill pages mounted) but before `generate-tabs` (needs to overwrite page.tsx). Bundle RAG project creation adds another build step.
- **Chain YAML quality varies** — Auto-discovered workflows and actions are only as good as the chain metadata. Poorly documented chains will produce unhelpful overview entries.
- **External MCP server availability** — Action commands that depend on external MCP servers (brightdata, context7) fail if those servers aren't configured. Actions must handle missing servers gracefully with clear error messages.
- **RAG index per bundle adds storage** — Each bundle gets its own RAG project. For 13 bundles, that's 13 index directories. Acceptable given the search quality improvement.

### Neutral

- `HubRenderer` continues to exist for tab-level section rendering — this ADR addresses the overview/landing page only, not tab content
- `dashboard.yaml` schema unchanged — skills don't need modifications
- `GlassCard` and `glass-panel` primitives remain the visual building blocks inside the template sections
- Backend-only bundles (orchestration) are unaffected — no overview needed where there's no nav

## Implementation Order

```
Phase 1: Schema & Template (PARALLEL)
├── Step 1: Create overview.yaml Zod schema (overview-schema.ts)
│           Include ActionCommandSchema, ActionInputSchema, ExternalSourcesConfigSchema
├── Step 2: Create OverviewData TypeScript interface (types.ts)
│           Include actions[], externalSources, searchConfig fields
└── Step 3: Create BundleOverview component + 8 section components
            (Hero, SearchBar, SkillCards, ActionCommands, ExternalSources,
             LiveStats, RecentActivity, RelatedBundles)

Phase 2: Build Script & RAG Setup (depends on Phase 1)
├── Step 4: Create generate-overview-pages.ts build script
│           (discovers bundles, reads overview.yaml, aggregates chains/tools/stats,
│            discovers overview: true chains as actions,
│            writes .overview-data.json + page.tsx per bundle)
├── Step 5: Integrate into prebuild pipeline (after mount-plugins, before generate-tabs)
├── Step 6: Add overview.yaml validation to validate-nav-alignment.ts
├── Step 7: Create bundle RAG project initialization script
│           (create plugins/ai/skills/knowledge/data/rag/projects/bundle_{name}/sources.yaml
│            pointing to plugins/{bundle}/skills/*/data/)
└── Step 8: Add overview/overview_label/overview_icon/overview_color fields
            to chain YAML schema documentation and validation

Phase 3: Author Overview Configs (PARALLEL, depends on Phase 2)
├── Step 9: Write overview.yaml for career, finance, health, lifestyle (data-rich bundles)
│           Include actions with chain references, external_sources defaults
├── Step 10: Write overview.yaml for professional, ai, productivity, dev (moderate bundles)
│            Include actions where applicable
├── Step 11: Write overview.yaml for admin, consulting, enterprise, home, observability (lighter)
└── Step 12: Add overview: true to existing chain YAML files that should surface as actions

Phase 4: Migration — Delete Custom Pages (depends on Phase 3)
├── Step 13: Extract stats/activity config from existing custom page.tsx → overview.yaml stats overrides
├── Step 14: Delete all custom overview page.tsx files from plugin sources
└── Step 15: Verify generated pages match or exceed previous pages' functionality

Phase 5: Verification (depends on all)
├── Step 16: npm run build — verify all overview pages generate and compile
├── Step 17: npm run validate-nav — verify overview.yaml exists for all nav bundles
├── Step 18: Verify search bar queries RAG API scoped to bundle project
├── Step 19: Verify action commands execute chains via /api/agents/chain
├── Step 20: Verify external sources paste flow → bridge connection → RAG indexing
├── Step 21: Verify auto-discovery — add a new chain with overview: true, rebuild, confirm it appears
└── Step 22: Visual regression — screenshot each overview page, compare with previous
```

## Alternatives Considered

### Alternative 1: Extend HubRenderer to Handle Overview Pages

Reuse the existing `HubRenderer` component and extend `dashboard.yaml` schema with overview sections.

**Rejected because**: `HubRenderer` is skill-scoped (one dashboard.yaml per skill), but overviews are bundle-scoped (aggregate across multiple skills). The scope mismatch would require awkward cross-skill aggregation inside a single dashboard.yaml.

### Alternative 2: AI-Generated Overview Content

Use an LLM to generate goals, knowledge, and descriptions from SKILL.md and chain YAML at build time.

**Rejected because**: Goals and knowledge require human intent — they describe WHY the bundle exists, not just WHAT it does. Auto-generated copy would lack the strategic perspective. The hybrid approach (human goals + machine discovery) preserves intent while automating the mechanical parts.

### Alternative 3: Runtime Config Loading (No Build-Time Generation)

Load overview.yaml at runtime instead of generating pages at build time.

**Rejected because**: Runtime YAML parsing adds latency and complexity. Build-time generation produces static React components that Next.js can optimize (static rendering, code splitting). The data is stable — it only changes when the filesystem changes, which is a build event.

### Alternative 4: Keep Custom Pages with Shared Sub-Components

Instead of one template, create src/lib sub-components (GoalsSection, WorkflowsSection, etc.) that custom pages import.

**Rejected because**: This is the current approach in disguise — each page still has custom React code that arranges components. It doesn't solve the snowflake problem, just provides better building blocks. The template approach is more opinionated (every page looks the same) which is the explicit goal.

## References

- ADR-109: Filesystem-Driven Dashboard — bundle/skill structure, build pipeline, overview.yaml file location
- ADR-012: Config-driven dashboard — dashboard.yaml and HubRenderer
- ADR-108: Hub rebalancing — bundle structure
- ADR-105: Plugin-driven tool scoping — MCP tool declarations
- `src/dashboard/components/plugin/HubRenderer.tsx` — Existing config-driven renderer
- `src/dashboard/lib/plugin-schema/types.ts` — DashboardYaml type definitions
- `src/dashboard/lib/plugin-schema/loader.ts` — Plugin discovery functions
- `plugins/*/skills/*/chains/*.yaml` — Chain YAML metadata schema
- `plugins/*/skills/*/SKILL.md` — Skill frontmatter metadata

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-110: Bundle Overview Template — Product Value at a Glance**.

Read the full ADR: `docs/decisions/ADR-110-bundle-overview-template.md`

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

1. **Create team**: `TeamCreate(team_name="adr-110-overview-template", description="Implementing ADR-110: Bundle Overview Template")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-110-overview-template", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-110 team.
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

**Team name**: `adr-110-overview-template`

#### Phase 1: Schema & Template
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create Zod schema for overview.yaml validation. Include all fields from Decision 8: OverviewGoalsSchema, KnowledgeItemSchema, StatOverrideSchema, WorkflowOverrideSchema, RelatedBundleSchema, ActionInputSchema, ActionCommandSchema, ExternalSourcesConfigSchema, OverviewYamlSchema. Export parse/validate functions. Follow existing pattern in `src/dashboard/lib/plugin-schema/`. | `src/dashboard/lib/plugin-schema/overview-schema.ts` |
| 1.2 | developer | medium | Create OverviewData TypeScript interface that represents the generated JSON data (goals, knowledge, skills[], workflows[], tools, stats[], relatedBundles[], actions[], externalSources, searchConfig). This is the contract between the build script and the BundleOverview component. Include ActionCommand, ActionInput, ExternalSourceConfig, SearchConfig interfaces. | `src/dashboard/components/overview/types.ts` |
| 1.3 | frontend | high | Create `BundleOverview` component and all 8 section sub-components. BundleOverview is a Server Component that renders HeroSection, SkillCardsSection (conditional on 2+ skills), RelatedBundlesSection. Wraps SearchBarSection, ActionCommandsSection, ExternalSourcesSection, LiveStatsSection, and RecentActivitySection in Suspense boundaries (client components with runtime data). Use GlassCard/glass-panel visual primitives. Follow existing design-standards.md patterns. **SearchBarSection**: input with scope chip, calls `/api/knowledge/search?project=bundle_{id}`, inline results. **ActionCommandsSection**: card grid, each card shows icon/label/description/step count, click expands to inputs + Execute button, execution shows step progress via `/api/agents/chain`, result summary after completion. **ExternalSourcesSection**: shows registered sources with file counts, paste input at top for adding links, calls `/api/bridge/connections` on paste. Reference existing ExternalSourcesSection in hub data bridge for patterns. | `src/dashboard/components/overview/BundleOverview.tsx`, `src/dashboard/components/overview/sections/HeroSection.tsx`, `src/dashboard/components/overview/sections/SearchBarSection.tsx`, `src/dashboard/components/overview/sections/SkillCardsSection.tsx`, `src/dashboard/components/overview/sections/ActionCommandsSection.tsx`, `src/dashboard/components/overview/sections/ExternalSourcesSection.tsx`, `src/dashboard/components/overview/sections/LiveStatsSection.tsx`, `src/dashboard/components/overview/sections/RecentActivitySection.tsx`, `src/dashboard/components/overview/sections/RelatedBundlesSection.tsx` |

#### Phase 2: Build Script & RAG Setup (depends on Phase 1)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | high | Create `generate-overview-pages.ts` build script. It must: (1) Discover all bundles via readdir (per ADR-109). (2) For each bundle, check for overview.yaml. (3) Parse overview.yaml with Zod schema. (4) Discover all skills in bundle (dashboard.yaml → hub.id, title, icon). (5) Discover all chains (chains/*.yaml → name, description, triggers, agents, overview flag). (6) Merge overview.yaml `actions` with auto-discovered `overview: true` chains (declared actions take priority). (7) Discover all MCP tools (dashboard.yaml mcp.tools + SKILL.md mcp_servers). (8) Discover stats (dashboard.yaml sections with metrics-grid type). (9) Determine primary skill (hub.id matches bundle name, or first alphabetically). (10) Build searchConfig with bundleName and RAG project ID. (11) Build externalSources from overview.yaml defaults + bridge connections. (12) Write .overview-data.json to src/dashboard/app/{primary-hub-id}/. (13) Write generated page.tsx importing BundleOverview + data JSON. | `src/dashboard/scripts/generate-overview-pages.ts` |
| 2.2 | devops | medium | Integrate `generate-overviews` into prebuild pipeline. Add to package.json scripts. Must run AFTER mount-plugins (needs skill pages mounted) and BEFORE generate-tabs (page.tsx must exist for Next.js). Update the build sequence in any documentation that references it. | `src/dashboard/package.json`, build pipeline scripts |
| 2.3 | developer | medium | Add overview.yaml validation to `validate-nav-alignment.ts` (ADR-109). Assert: every bundle with 1+ nav skills has overview.yaml. Assert: overview.yaml passes Zod schema (including actions and external_sources). Assert: referenced chain paths exist. Assert: referenced bundle names exist. Assert: backend-only bundles do NOT have overview.yaml. Assert: action command chain references resolve to existing YAML files. | `src/dashboard/scripts/validate-nav-alignment.ts` |
| 2.4 | devops | medium | Create bundle RAG project initialization script. For each bundle with overview.yaml: create `plugins/ai/skills/knowledge/data/rag/projects/bundle_{bundleName}/sources.yaml` pointing to all `plugins/{bundle}/skills/*/data/` directories. Register external_sources.default_paths from overview.yaml. Integrate as a build step or first-run initialization. | `src/dashboard/scripts/init-bundle-rag-projects.ts` |
| 2.5 | developer | low | Document chain YAML schema additions: `overview` (boolean), `overview_label` (string), `overview_icon` (string), `overview_color` (string). Add to chain YAML documentation and any existing validation scripts. These fields allow chains to self-declare as overview action commands without manual overview.yaml entries. | Chain YAML schema docs, validation scripts |

#### Phase 3: Author Overview Configs
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Write overview.yaml for career, finance, health, lifestyle bundles. These are the data-rich bundles with existing live stats. Extract goals from current page.tsx content. Define knowledge areas based on SKILL.md descriptions. Configure stats overrides to preserve existing stat tiles. Set related_bundles based on current "Connected Hubs" links. **Include actions**: career gets import-linkedin-jobs and analyze-resume actions. Finance gets parse-balance-sheet action. Health and lifestyle get relevant actions from their chains. **Include external_sources defaults**: career gets ~/Documents/Resume/ and ~/Documents/Career/. Finance gets ~/Documents/Finance/. | `plugins/career/overview.yaml`, `plugins/finance/overview.yaml`, `plugins/health/overview.yaml`, `plugins/lifestyle/overview.yaml` |
| 3.2 | developer | medium | Write overview.yaml for professional, ai, productivity, dev bundles. Extract goals from current page.tsx. Define knowledge areas. **Include actions** where applicable (dev gets run-nightly, deploy actions from existing chains). **Include external_sources defaults** where relevant. | `plugins/professional/overview.yaml`, `plugins/ai/overview.yaml`, `plugins/productivity/overview.yaml`, `plugins/dev/overview.yaml` |
| 3.3 | developer | medium | Write overview.yaml for admin, consulting, enterprise, home, observability bundles. These are lighter bundles — focus on clear goals and knowledge. Consulting has 3 client skills — skill cards will auto-generate. Home gets smart-home action commands if chains exist. | `plugins/admin/overview.yaml`, `plugins/consulting/overview.yaml`, `plugins/enterprise/overview.yaml`, `plugins/home/overview.yaml`, `plugins/observability/overview.yaml` |
| 3.4 | developer | low | Add `overview: true` flag (and overview_label, overview_icon, overview_color) to existing chain YAML files that should surface as action commands on their bundle's overview page. Scan all chains/*.yaml files, identify user-facing automation chains (not internal/CI chains), add the flags. | `plugins/*/skills/*/chains/*.yaml` (selected files) |

#### Phase 4: Migration — Delete Custom Pages (depends on Phase 3)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Extract any custom stats configuration from existing custom page.tsx files into overview.yaml `stats` overrides. Focus on: career (getJobs counts), lifestyle (7 data fetches), health (3 API stats), home (4 stat tiles), knowledge (6 API stats), project-dev (3 API stats). Map each existing stat to the overview.yaml stat format (label, source, transform, icon, color). | `plugins/*/overview.yaml` (update stats sections) |
| 4.2 | developer | low | Delete all custom overview page.tsx files from plugin source directories. These are the files in `plugins/{bundle}/skills/{primary-skill}/dashboard/page.tsx` that were serving as overview pages. The generated pages will replace them. List: career, finance, health, lifestyle, home-automation, ai_bridge, knowledge, venture-augur, project-dev, observe, enterprise, growth, wealth, creative. | `plugins/*/skills/*/dashboard/page.tsx` (14 files) |
| 4.3 | validator | medium | Run build and verify each bundle's generated overview page renders correctly. Compare generated overview data with what the old custom pages showed. Flag any missing stats, broken links, or lost functionality. Verify action commands, search bar, and external sources render for data-rich bundles. | All generated pages |

#### Phase 5: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 5.1 | validator | low | Run `npm run build` — verify all overview pages generate and compile. Zero TypeScript errors. |
| 5.2 | validator | low | Run `npm run validate-nav` — verify overview.yaml exists for all 13 nav bundles (not orchestration). Verify schema validation passes including actions and external_sources fields. |
| 5.3 | validator | medium | Verify search bar: confirm bundle RAG projects exist for all 13 bundles. Test `/api/knowledge/search?project=bundle_career` returns scoped results. Verify scope chip toggles between bundle and global. |
| 5.4 | validator | medium | Verify action commands: confirm career overview shows Import Jobs action. Trigger a dry-run chain execution via `/api/agents/chain` with `dry_run: true`. Verify progress UI renders step indicators. |
| 5.5 | validator | medium | Verify external sources: confirm default_paths from overview.yaml are registered in bridge connections. Test paste flow with a local folder path. Verify source appears in ExternalSources section. |
| 5.6 | validator | medium | Verify auto-discovery: check that generated .overview-data.json for career bundle includes chains from career, growth, and content skills. Verify chains with `overview: true` appear in actions[]. Verify skill cards show 3 entries (career, growth, creative — not linkedin-writer which is backend-only). |
| 5.7 | validator | low | Verify no custom overview page.tsx files remain in plugin sources. Grep `plugins/*/skills/*/dashboard/page.tsx` — these should be tab-specific pages only, not overview landing pages. |
| 5.8 | architect | low | Final review: verify template consistency across all 13 bundles. Verify no hardcoded per-bundle React code exists. Update ADR-110 status to "Accepted". |

### Completion Criteria

- [ ] overview.yaml Zod schema created — validates all fields including actions, external_sources
- [ ] BundleOverview component + 8 section components created (Hero, SearchBar, SkillCards, ActionCommands, ExternalSources, LiveStats, RecentActivity, RelatedBundles)
- [ ] generate-overview-pages.ts build script discovers bundles, chains, tools, stats, actions (from YAML + overview: true chains), search config, external sources
- [ ] Build pipeline integrates generate-overviews between mount-plugins and generate-tabs
- [ ] Bundle RAG projects created for all 13 nav bundles (plugins/ai/skills/knowledge/data/rag/projects/bundle_{name}/)
- [ ] overview.yaml authored for all 13 nav bundles — including actions and external_sources where applicable
- [ ] Chain YAML files with user-facing automation flagged with overview: true
- [ ] All existing custom overview page.tsx files deleted from plugin sources
- [ ] Stats from existing pages migrated to overview.yaml stat overrides
- [ ] `npm run build` passes
- [ ] `npm run validate-nav` passes (including overview.yaml validation with action chain references)
- [ ] Search bar queries bundle-scoped RAG project, scope chip toggles to global
- [ ] Action commands render, accept inputs, trigger chain execution via /api/agents/chain, show progress
- [ ] External sources display default paths, paste input adds new sources via /api/bridge/connections
- [ ] Auto-discovery verified — new chain with overview: true appears as action after rebuild
- [ ] Skill cards render for multi-skill bundles (2+), hidden for single-skill
- [ ] No per-bundle custom React code — all differences come from overview.yaml + auto-discovery
- [ ] All 5 phases executed
- [ ] ADR status updated to "Accepted"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-110-bundle-overview-template.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
