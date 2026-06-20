---
status: Implemented
date: '2026-02-16'
deciders:
- Project owner
related:
- ADR-108 (hub rebalancing)
- ADR-105 (plugin-driven tool scoping)
- ADR-012 (config-driven dashboard)
- ADR-018 (plugin self-containment)
- ADR-020 (operations restructure)
hub: null
tags:
- filesystem
- driven
- dashboard
- portable
- skills
superseded_by: null
---

# ADR-109: Filesystem-Driven Dashboard — Portable Skills, Zero Config

## Context

### Terminology

```
plugins/                          ← Plugins root
├── consulting/                   ← BUNDLE = sidebar nav section
│   └── skills/
│       ├── client-ai-consulting/ ← SKILL = sidebar nav link (one page with tabs)
│       ├── client-smb-design/
│       ├── client-terminal-automation/
│       └── linkedin-writer/      ← No dashboard.yaml = backend-only, hidden from nav
```

**Bundle** = folder under `plugins/`. Becomes a sidebar section header.
**Skill** = folder under `plugins/{bundle}/skills/`. Becomes a sidebar link. Self-contained — owns its dashboard, API, data, config.

### The Core Idea

A skill is a portable, self-contained unit. The only thing that determines where it appears in the nav is which bundle folder it lives in.

```bash
# Move a skill to a different bundle section:
mv plugins/career/skills/linkedin-writer plugins/career/skills/linkedin-writer
# Next build → LinkedIn Writer appears under Career instead of Consulting

# Create a new bundle:
mkdir -p plugins/my-experiments/skills
# Next build → "My Experiments" section appears in sidebar (empty until skills are added)

# Add a skill to the new bundle:
mv plugins/ai/skills/scraper plugins/ai/skills/scraper
# Next build → Scraper appears under My Experiments
```

No config files to edit. No TypeScript arrays to update. No registry to regenerate manually. The filesystem IS the configuration.

### The Unix Philosophy Violation (Current State)

Augur's core philosophy is transparency and Unix composability — what you see on disk IS the system. But the current build pipeline violates this:

1. **Hardcoded hub lists** — `PLUGIN_BUNDLES` is duplicated in both `generate-tab-registry.ts` and `mount-plugins.ts` (17 entries each). Adding a new bundle means editing two TypeScript files. The filesystem already knows what bundles exist (`ls plugins/`), but the build scripts don't trust it.

2. **Dual-source tab registry** — `registry.ts` has a hardcoded `tabRegistry` (13 entries: lifestyle, venture, brain, sense, operations, control, settings, etc.) AND `generated-registry.ts` has auto-generated entries from plugins. `getCompleteRegistry()` merges both. Nobody knows which is the source of truth.

3. **Static page cross-references** — `navigation.ts` manually injects `/operations`, `/control`, `/help` into specific bundle sections via `STATIC_OPERATIONS_ITEMS`. Pages like `settings`, `memory`, `activity`, `agents` exist in `src/dashboard/app/` without any plugin backing.

4. **Skills aren't truly portable** — Because the `category` field in `pluginNavItems` comes from the bundle directory name at generation time, moving a skill between bundles works IF you regenerate. But the hardcoded `PLUGIN_BUNDLES` won't discover the new bundle directory, and the `coreDirectories` whitelist might block cleanup of the old mount.

5. **Hardcoded MCP context routing** — `useMCPContext.ts` has a hardcoded `SYSTEM_PAGE_PREFIXES` array (~20 route prefixes) that decides whether a page uses `switch-mcp-context` (system page) or `focus-context` (skill page). Adding or removing routes requires editing this array. This should be derived: core shell pages use `switch-mcp-context`, everything else (plugin-mounted) uses `focus-context`.

### What This Means in Practice

```
# The filesystem says this:
plugins/
├── consulting/skills/client-ai-consulting/   → should appear under "Consulting"
├── consulting/skills/linkedin-writer/        → backend-only (no dashboard.yaml)
├── career/skills/career/                     → should appear under "Career"

# But the code also requires:
generate-tab-registry.ts:  PLUGIN_BUNDLES = ['consulting', 'career', ...]  ← manual
mount-plugins.ts:          PLUGIN_BUNDLES = ['consulting', 'career', ...]  ← duplicated
registry.ts:               tabRegistry = { lifestyle: {...}, ... }         ← stale fallbacks
navigation.ts:             STATIC_OPERATIONS_ITEMS = [...]                 ← manual injections
mount-plugins.ts:          coreDirectories = new Set([...])                ← manual whitelist
useMCPContext.ts:           SYSTEM_PAGE_PREFIXES = [...]                    ← manual route list
```

Six separate places that need manual maintenance. Moving a skill or adding a bundle should be a filesystem operation, not a code change.

### Design Principles

1. **Filesystem = truth** — `ls plugins/` gives you bundles. `ls plugins/{bundle}/skills/` gives you skills. `dashboard.yaml` in a skill makes it visible in nav. No exceptions.
2. **Skills are portable** — Move a skill folder between bundles. Next build, it appears in the new section. Zero config changes.
3. **Bundles are emergent** — Create a directory under `plugins/`. It becomes a nav section on next build. Delete it (or empty it), it disappears.
4. **Core shell is constant** — With zero plugins installed, a minimal dashboard still works: root overview, settings, help, error boundaries.
5. **Build scripts discover, never enumerate** — No hardcoded arrays. `readdir()` replaces `PLUGIN_BUNDLES`.
6. **One source of truth per page** — A page comes from a plugin (via `dashboard/` folder) OR it's a core shell page in `src/`. Never both.
7. **Plugin pages are build artifacts** — `src/dashboard/app/{hubId}/` for plugins is ephemeral. The build reconstructs it entirely from `plugins/`. You never hand-edit files there.
8. **No backward compatibility** — After migration, delete all redirect pages, compatibility shims, old route aliases, and stale references. No `/control → /ai_bridge` redirects, no tab name mappings, no legacy fallback entries. Clean and minimal — if a route moved, the old one is gone.

### Build Pipeline (How It Should Work)

The build discovers everything from the plugin filesystem. No manual steps.

```
plugins/                                    ← SOURCE OF TRUTH
├── consulting/skills/
│   ├── client-ai-consulting/
│   │   ├── dashboard.yaml                 ← Declares hub.id, tabs, MCP tools
│   │   ├── dashboard/                     ← UI pages (page.tsx, layout.tsx, subpages/)
│   │   └── api/                           ← API routes
│   └── linkedin-writer/
│       └── (no dashboard.yaml)            ← Backend-only, invisible to dashboard
│
        ↓ BUILD (npm run prebuild) ↓
│
src/dashboard/app/                          ← BUILD OUTPUT (ephemeral for plugins)
├── page.tsx                               ← Core shell (hand-maintained)
├── settings/                              ← Core shell (hand-maintained)
├── help/                                  ← Core shell (hand-maintained)
├── client-ai-consulting/                  ← MOUNTED from plugin (build artifact)
│   ├── .plugin-mount                      ← Marker: "this is a build artifact"
│   ├── page.tsx                           ← Copied from plugins/.../dashboard/
│   └── sessions/page.tsx
├── api/client-ai-consulting/              ← API routes mounted from plugin
│
src/dashboard/lib/tabs/
├── generated-registry.ts                  ← AUTO-GENERATED from dashboard.yaml files
│
src/dashboard/lib/navigation.ts            ← Reads generated-registry → builds sidebar
```

**Build step sequence** (`npm run prebuild`):

```
1. build:scripts       → Compile TS scripts to JS
2. setup-mcp           → Configure MCP connections
3. generate-registry   → Python: generate skill registry
4. mount-plugins       → Discover ALL bundles/skills via readdir()
   │                      For each skill with dashboard/ folder:
   │                        Copy dashboard/ → src/dashboard/app/{hubId}/
   │                        Copy api/       → src/dashboard/app/api/{hubId}/
   │                        Mark with .plugin-mount
   │                      Clean up stale mounts (skills that were removed/moved)
   │
5. generate-tabs       → Discover ALL bundles/skills via readdir()
   │                      For each skill with dashboard.yaml:
   │                        Parse hub config, tabs, nav items
   │                      Write generated-registry.ts
   │
6. next build/dev      → Next.js compiles from src/dashboard/app/
                          (sees both core shell + mounted plugin pages)
```

**Key insight**: Steps 4 and 5 both independently discover bundles and skills from the filesystem. Neither relies on a hardcoded list. If you add a new skill or move one between bundles, both steps pick it up automatically.

## Decision

### 1. Auto-Discover Bundles and Skills (Replace PLUGIN_BUNDLES)

Both `generate-tab-registry.ts` and `mount-plugins.ts` currently hardcode `PLUGIN_BUNDLES`. Replace with full filesystem discovery:

```typescript
// BEFORE (hardcoded — must update when adding bundles):
const PLUGIN_BUNDLES = ['core', 'career', 'growth', ...17 items...];
// Then iterates skills inside each bundle:
for (const bundle of PLUGIN_BUNDLES) {
  const skills = await fs.readdir(path.join(pluginsDir, bundle, 'skills'));
  // ...
}

// AFTER (discovered — just create directories):
async function discoverBundles(pluginsDir: string): Promise<string[]> {
  const entries = await fs.readdir(pluginsDir, { withFileTypes: true });
  return entries
    .filter(e => e.isDirectory() && !e.name.startsWith('.'))
    .map(e => e.name)
    .sort();
}

// Discovery chain: plugins/ → bundles → skills → dashboard.yaml + dashboard/
// Each skill's dashboard/ folder is the source of its pages.
// The build copies dashboard/ → src/dashboard/app/{hubId}/ automatically.
```

The full discovery chain at build time:

```
readdir('plugins/')                                    → ['admin', 'career', 'consulting', ...]
  readdir('plugins/consulting/skills/')                → ['client-ai-consulting', 'client-smb-design', ...]
    exists('plugins/consulting/skills/client-ai-consulting/dashboard.yaml')  → YES → register in nav
    exists('plugins/consulting/skills/client-ai-consulting/dashboard/')      → YES → mount pages
    exists('plugins/consulting/skills/client-ai-consulting/api/')            → YES → mount API routes
    exists('plugins/career/skills/linkedin-writer/dashboard.yaml')       → NO  → skip (backend-only)
```

Every skill's `dashboard/` folder contains its complete page tree (page.tsx, layout.tsx, sub-route folders). The build copies this tree into `src/dashboard/app/{hubId}/` where Next.js picks it up as routes. The skill's `dashboard.yaml` tells the registry about tabs, icons, and MCP tools. Both are discovered — nothing is hardcoded.

**Consequence**: Creating `plugins/my-new-bundle/skills/my-skill/dashboard/page.tsx` <!-- example path --> + `dashboard.yaml` is all that's needed. The build discovers it, mounts the pages, generates the registry entry, and the skill appears in the sidebar under "My New Bundle".

**Files affected:**
- `src/dashboard/scripts/generate-tab-registry.ts` — Replace `PLUGIN_BUNDLES` with `discoverBundles()`
- `src/dashboard/scripts/mount-plugins.ts` — Replace `PLUGIN_BUNDLES` with `discoverBundles()`

### 2. Skill Portability Contract

A skill is fully self-contained. Moving it between bundles requires zero config changes inside the skill. The build system derives everything from the filesystem:

| Property | Derived from |
|----------|-------------|
| Nav section label | Bundle directory name (`plugins/{bundle}/`) → `formatSectionLabel(bundle)` |
| Nav link label | `dashboard.yaml → hub.title` (or `hub.nav_label` override) |
| Route path | `dashboard.yaml → hub.id` (e.g., `/client-ai-consulting`) |
| Sidebar visibility | Presence of `dashboard.yaml` with valid `hub.id` + `tabs[]` |
| Nav section grouping | Parent bundle directory — NOT a field in `dashboard.yaml` |

**Critical**: The `hub.category` field that currently exists in `pluginNavItems` is already derived from the bundle directory name (`dashboard.pluginId`). This ADR formalizes that: **category is NEVER stored in dashboard.yaml** — it's always the bundle directory name. If a skill moves bundles, it automatically re-categorizes.

**What makes a skill portable:**
- `dashboard.yaml` declares its own `hub.id`, `title`, `tabs`, `mcp.tools` — all self-referential
- `dashboard/` folder contains its own pages — no imports from sibling skills
- `api/` folder contains its own API routes
- `dependencies.required` lists skills it depends on (by skill ID, not bundle path)
- No hardcoded bundle references anywhere inside the skill

### 3. Eliminate the Hardcoded Tab Registry

The hardcoded `tabRegistry` in `registry.ts` was a fallback from before ADR-012. Now that all hubs have `dashboard.yaml`, the fallback creates confusion.

**Current hardcoded entries and their fate:**

| Entry | Has Plugin? | Action |
|-------|------------|--------|
| `lifestyle` | Yes (plugins/lifestyle/skills/lifestyle) | DELETE — plugin provides it |
| `venture` | Yes (plugins/professional/skills/venture-augur) | DELETE — plugin provides it |
| `client-smb-design` | Yes (plugins/consulting/skills/client-smb-design) | DELETE — plugin provides it |
| `client-terminal-automation` | Yes (plugins/consulting/skills/client-terminal-automation) | DELETE — plugin provides it |
| `brain` | No plugin backing | DELETE — orphaned legacy |
| `sense` | No plugin backing | DELETE — orphaned legacy |
| `operations` | Just a redirect to /project-dev | DELETE — page is a redirect |
| `control` | Just a redirect to /ai_bridge | DELETE — page is a redirect |
| `settings` | Core shell page | KEEP as core-only entry |

**Files affected:**
- `src/dashboard/lib/tabs/registry.ts` — Remove all entries except `settings`. Rename `tabRegistry` to `coreTabRegistry`.

### 4. Define the Core Shell (Plugin-Agnostic Pages)

The core shell renders when all plugins are disabled. These pages live in `src/dashboard/app/` and are NOT mounted from plugins:

| Route | Purpose | Why core (not plugin) |
|-------|---------|----------------------|
| `/` | Root overview/dashboard | App entry point |
| `/settings` | System configuration | Configures the plugin system itself |
| `/help` | Documentation | Always available regardless of plugins |
| `layout.tsx` | App shell, sidebar | Structural |
| `not-found.tsx` / `error.tsx` | Error boundaries | Structural |

**Orphaned pages to clean up:**

| Route | Status | Action |
|-------|--------|--------|
| `/control` | Redirect to `/ai_bridge` | DELETE — hand-created redirect, no `.plugin-mount` |
| `/operations` | Redirect to `/project-dev` | DELETE — hand-created redirect, no `.plugin-mount` |
| `/content` | Plugin-mounted duplicate of `/creative` | Fix plugin source — stale mount will be cleaned by marker-based cleanup |
| `/venture-augur` | Plugin-mounted duplicate of `/venture` | Fix plugin source — stale mount will be cleaned by marker-based cleanup. Note: venture-augur skill moves to professional/ bundle |
| `/memory` | Standalone (no `.plugin-mount`) | Audit — migrate to plugin or delete if covered |
| `/activity` | Standalone (no `.plugin-mount`) | Audit — migrate to plugin or delete if covered |
| `/agents` | Standalone (no `.plugin-mount`) | Audit — migrate to plugin or delete if covered |

Note: `capture/`, `factory/`, `icloud/` were initially flagged but have `.plugin-mount` markers — they're already plugin-mounted and need no action.

### 5. Simplify Navigation to Pure Discovery

The sidebar should reflect exactly what the filesystem says. No manual injections.

**Current flow (with manual steps):**
```
pluginNavItems (generated) → grouped by category → + STATIC_OPERATIONS_ITEMS → sidebar
                                                     ↑ manual injection
```

**New flow (pure discovery):**
```
CORE_SHELL_ITEMS (constant)  ─┐
                               ├→ sidebar
pluginNavItems (generated)   ─┘
  grouped by bundle directory
```

```typescript
// Core shell items — always visible, not tied to any bundle
const CORE_SHELL_ITEMS: NavSection = {
  label: '',
  items: [
    { href: '/', label: 'Overview', icon: LayoutDashboard },
    { href: '/settings', label: 'Settings', icon: Settings },
    { href: '/help', label: 'Help', icon: HelpCircle },
  ],
};

// Everything else comes from pluginNavItems, grouped by bundle directory name
// No STATIC_OPERATIONS_ITEMS, no admin/dev merge hacks
```

**Bundle section ordering**: `HUB_SECTION_ORDER` remains as an optional UX ordering hint. It is NOT a discovery mechanism — removing a bundle from this list doesn't hide it, and adding a new bundle doesn't require updating it. The current behavior (navigation.ts:152-160) already auto-appends unknown bundles alphabetically at the end. This is the intended long-term behavior.

**Dev mode filtering**: Skills can declare `mode: dev` in `dashboard.yaml`. The nav respects this: dev-mode skills are hidden unless dev mode is enabled. This is orthogonal to bundle-based grouping — a dev-mode skill in the `admin` bundle still appears under "Admin", just only when dev mode is on. The admin/dev merge hack being removed is the `STATIC_OPERATIONS_ITEMS` injection, not the per-skill mode filtering.

**Files affected:**
- `src/dashboard/lib/navigation.ts` — Remove `STATIC_OPERATIONS_ITEMS`. Remove admin/dev special-case merge. Core shell items are a standalone section. Keep `HUB_SECTION_ORDER` as ordering hint. Keep `isNavItemEnabled()` dev mode check.

### 6. Auto-Derive Core vs Plugin in Mount Cleanup

Replace the hardcoded `coreDirectories` whitelist with marker-based detection:

```typescript
// BEFORE (manual whitelist — must update when adding core pages):
const coreDirectories = new Set(['api', 'fonts', '(auth)', '(core)', 'settings', ...]);

// AFTER (detected — plugin mounts have .plugin-mount marker, everything else is core):
async function isPluginMount(dirPath: string): Promise<boolean> {
  try {
    await fs.access(path.join(dirPath, '.plugin-mount'));
    return true;
  } catch {
    return false;
  }
}
// Only clean directories that HAVE the marker. Protect everything else.
```

**Files affected:**
- `src/dashboard/scripts/mount-plugins.ts` — Replace `coreDirectories` with marker-based detection

### 7. CI Validation: Filesystem = Navigation

Replace the existing `validate-tab-registry.ts` (which validates the generated registry against hardcoded expectations) with a new `validate-nav-alignment.ts` that validates filesystem = navigation alignment:

```typescript
// scripts/validate-nav-alignment.ts
// Assertions:
1. Every dashboard.yaml hub → appears in generated-registry
2. Every generated-registry entry → has a mounted app/ directory
3. No app/ directories are orphaned (not core AND not plugin-mounted)
4. No entries in coreTabRegistry duplicate generated entries
5. Every bundle with skills that have dashboard.yaml → appears as a nav section
6. No two dashboard.yaml files declare the same hub.id (global uniqueness)
```

**Files affected:**
- `src/dashboard/scripts/validate-nav-alignment.ts` — New file (replaces `validate-tab-registry.ts`)
- `src/dashboard/scripts/validate-tab-registry.ts` — DELETE (superseded)
- `src/dashboard/package.json` — Replace `validate-tabs` with `validate-nav` script

### 8. Eliminate SYSTEM_PAGE_PREFIXES in MCP Context Hook

`useMCPContext.ts` hardcodes ~20 route prefixes to determine whether a page uses `switch-mcp-context` (system/infrastructure page) or `focus-context` (skill page with MCP tool scoping). Replace with marker-based detection:

```typescript
// BEFORE (hardcoded — must update when routes change):
const SYSTEM_PAGE_PREFIXES = ['/settings', '/brain', '/control', '/operations', ...];

// AFTER (derived — core shell pages use switch-mcp-context, everything else uses focus-context):
function isSystemPage(pathname: string): boolean {
  if (pathname === '/') return true;
  const CORE_SHELL_ROUTES = ['/settings', '/help'];  // Only core shell pages
  return CORE_SHELL_ROUTES.some(r => pathname === r || pathname.startsWith(r + '/'));
}
// All plugin-mounted pages (discovered at build time) use focus-context automatically.
// No need to enumerate them — if it's not core shell, it's a skill page.
```

**Files affected:**
- `src/dashboard/hooks/useMCPContext.ts` — Replace `SYSTEM_PAGE_PREFIXES` with `CORE_SHELL_ROUTES` (2-3 entries instead of ~20)

### 9. Hub ID Uniqueness Validation

`hub.id` in `dashboard.yaml` determines the route path (`/{hubId}`). Two skills with the same `hub.id` would create conflicting routes. Add a uniqueness check to the CI validation:

```typescript
// In validate-nav-alignment.ts, add:
// Assert: no two dashboard.yaml files declare the same hub.id
// (even across different bundles)
```

This is added to the validation script (Decision 7), not as a runtime check. Build fails fast on collision.

**Files affected:**
- `src/dashboard/scripts/validate-nav-alignment.ts` — Add hub.id uniqueness assertion

### 10. Skill Migration — Clean Up Legacy Duplicates & Delete Stale Bundles

ADR-108 rebalanced skills into new bundles (career→career+growth, business→consulting+venture(now professional)+enterprise, etc.) but left stale copies in the old bundles. With `discoverBundles()` replacing `PLUGIN_BUNDLES`, these stale copies would now be discovered and could cause conflicts. Clean them up.

**Duplicate skill inventory** (stale copy → canonical location):

| Stale Copy | Has dashboard.yaml? | Unique Content? | Canonical Location | Action |
|-----------|---------------------|----------------|---------------------|--------|
| `business/client-ai-consulting` | NO | No (dashboard/ has only tsconfig.json) | `consulting/client-ai-consulting` | DELETE stale |
| `business/client-smb-design` | NO | No (dashboard/ has only tsconfig.json) | `consulting/client-smb-design` | DELETE stale |
| `business/client-terminal-automation` | NO | No (data/automations/*/assets are 0B empty dirs, canonical has same + more) | `consulting/client-terminal-automation` | DELETE stale |
| `business/enterprise` | NO | No (dashboard/ has only tsconfig.json) | `enterprise/enterprise` | DELETE stale |
| `business/venture-augur` | NO | No (only .DS_Store and a .bak file) | `professional/venture-augur` | DELETE stale |
| `productivity/apple` | NO | No (only __pycache__) | `integrations/apple` | DELETE stale |
| `productivity/google-workspace` | NO | No (canonical has more: data/, chains/) | `integrations/google-workspace` | DELETE stale |
| `productivity/project-dev` | NO | No (only __pycache__) | `dev/project-dev` | DELETE stale |
| `lifestyle/content` | NO | video/tsconfig.json (verify canonical has it) | `creative/content` | DELETE stale, copy tsconfig if missing |
| `services/daemon` | NO | No (only data/ dir) | `observe/daemon` | DELETE stale |

All stale copies verified: no unique code or user data. Canonical versions are strict supersets.

**Backend-only skills to KEEP** (no dashboard.yaml, no nav link, but needed):

| Skill | Bundle | Purpose | Has |
|-------|--------|---------|-----|
| channels | admin | Notification system | scripts, mcp, lib, data |
| executor | core | Chain execution engine | scripts, data |
| router | core | Request routing | scripts |
| swarm | core | Swarm orchestration | scripts |
| linkedin-writer | consulting | Content generation (future) | empty shell |
| metrics | observe | Monitoring data collection | scripts |

These are NOT duplicates — they are the only copy. Do not delete.

**Legacy bundles to delete** (empty after removing duplicates):

| Bundle | Skills Before | Skills After | Action |
|--------|--------------|-------------|--------|
| `business/` | 5 (all stale copies) | 0 | DELETE bundle |
| `services/` | 1 (stale copy) | 0 | DELETE bundle |

**Multi-skill hub pattern** (no action needed, just documented):

The dev bundle has 5 agent skills (advisor, developer, devops, frontend, validator) that share `hub_id: control` — they each contribute a tab to the AI Bridge page rather than owning standalone hubs. This pattern works with filesystem discovery because the generated registry already merges tabs from multiple skills sharing a `hub_id`. No changes needed.

**hub.id ≠ skill folder name** (no action needed, just documented):

| Skill | hub.id | Reason |
|-------|--------|--------|
| admin/settings | admin | Settings page routes as /admin |
| ai/mcp-app-factory | factory | Shorter route: /factory |
| home/home-automation | home | Shorter route: /home |

This is expected — `hub.id` is the route path, not required to match the skill folder name. The portability contract (Decision 2) only requires hub.id to be globally unique (Decision 9).

**Files affected:**
- `plugins/consulting/` — DELETE entire bundle
- `plugins/ai/` — DELETE entire bundle
- `plugins/productivity/skills/apple/` — DELETE stale copy
- `plugins/productivity/skills/google-workspace/` — DELETE stale copy
- `plugins/professional/skills/project-dev/` — DELETE stale copy
- `plugins/career/skills/content/` — DELETE stale copy

### 11. Bundle Consolidation & Skill Restructuring

ADR-108 split the original flat structure into 17 bundles. In practice, several bundles are too granular — they contain a single skill or overlap conceptually with a sibling bundle. Consolidate from 17 bundles to 14 by merging related bundles, renaming 2 for clarity, and relocating 5 skills to better-fitting homes.

**Why now (not later)**: Decision 1 replaces `PLUGIN_BUNDLES` with `discoverBundles()`. Once that lands, every bundle directory is automatically discovered and shown in the sidebar. Stale or misplaced bundles become visible problems. Cleaning the structure BEFORE enabling auto-discovery prevents the sidebar from showing defunct sections.

#### 11a. Bundle Merges (4 merges)

| Source Bundle | Target Bundle | Rationale |
|--------------|--------------|-----------|
| `growth/` → `career/` | career absorbs growth | Growth (professional development) is a sub-topic of career management |
| `wealth/` → `finance/` | finance absorbs wealth | Wealth management (investments, portfolio) is a sub-topic of finance |
| `venture/` → `professional/` | RENAME + absorb project-dev | "Venture" is too specific — the bundle represents whatever the user's profession is. For this user: building businesses and software. For another user it could be medicine, law, etc. |
| `dev/skills/project-dev` → `professional/` | professional absorbs project-dev | Project-dev (backlog, commits, throughput) is the build tool FOR the professional work |
| `core/` → `orchestration/` | RENAME only (no merge) | executor, router, swarm are orchestration primitives — "core" is vague |

**Details for each merge:**

**career + growth → career/**
```bash
# growth/ has 1 skill with dashboard
git mv plugins/career/skills/growth plugins/career/skills/growth
# Result: career/ now has career, growth (2 nav skills)
# growth/ bundle is empty → delete
rm -rf plugins/career/
```
No dashboard.yaml changes needed — growth skill keeps its `hub.id: growth` and routes as `/growth`. It just appears under the "Career" sidebar section instead of its own section.

**finance + wealth → finance/**
```bash
git mv plugins/finance/skills/wealth plugins/finance/skills/wealth
rm -rf plugins/finance/
```
Same pattern — wealth keeps `hub.id: wealth`, routes as `/wealth`, appears under "Finance" section.

**venture → professional/ (rename) + absorb project-dev**
```bash
# Rename the bundle
mkdir -p plugins/professional/skills
git mv plugins/professional/skills/venture-augur plugins/professional/skills/venture-augur
git mv plugins/professional/skills/project-dev plugins/professional/skills/project-dev
rm -rf plugins/professional/
```
venture-augur keeps `hub.id: venture`, routes as `/venture`, now appears under "Professional" section. project-dev keeps `hub.id: project-dev`, routes as `/project-dev`, also under "Professional". The 5 agent skills (advisor, developer, devops, frontend, validator) remain in `dev/` — they share `hub_id: control` and belong with the developer tooling bundle, not professional.

**core → orchestration/ (rename)**
```bash
# Create new bundle directory
mkdir -p plugins/orchestration/skills
# Move all 3 skills (all backend-only, no dashboard.yaml)
git mv plugins/orchestration/skills/executor plugins/orchestration/skills/executor
git mv plugins/orchestration/skills/router plugins/orchestration/skills/router
git mv plugins/orchestration/skills/swarm plugins/orchestration/skills/swarm
rm -rf plugins/orchestration/
```
These are all backend-only skills (no dashboard.yaml) — the rename has zero nav impact. It's purely for clarity: executor/router/swarm ARE the orchestration layer.

#### 11b. Bundle Renames (3 renames)

| Current Name | New Name | Rationale |
|-------------|----------|-----------|
| `venture/` | `professional/` | Covered in merge above — "venture" is too specific; "professional" is generic and describes any user's primary occupation |
| `core/` | `orchestration/` | Covered in merge above — executor, router, swarm describe orchestration |
| `observe/` | `observability/` | Industry-standard term; unambiguous about what daemon, metrics, observe do |

**observe → observability/**
```bash
mkdir -p plugins/observability/skills
git mv plugins/observability/skills/daemon plugins/observability/skills/daemon
git mv plugins/observability/skills/metrics plugins/observability/skills/metrics
git mv plugins/observability/skills/observe plugins/observability/skills/observe
rm -rf plugins/observability/
```
Only `observe` skill has a dashboard.yaml (hub.id: observe). daemon and metrics are backend-only. The rename changes the sidebar section label from "Observe" to "Observability" — no dashboard.yaml edits needed (category derived from bundle directory per Decision 2).

#### 11c. Skill Relocations (5 moves)

| Skill | From Bundle | To Bundle | Has Dashboard? | Rationale |
|-------|------------|-----------|---------------|-----------|
| `scraper` | admin | ai | Yes (hub.id: scraper) | Scraper uses AI/knowledge pipelines; fits better with ai_bridge, knowledge, install |
| `linkedin-writer` | consulting | career | No (backend-only) | LinkedIn content generation serves career goals, not client consulting |
| `content` | creative | career | Yes (hub.id: creative) | Content creation (video, writing) feeds career brand; creative/ bundle has only this skill |
| `apple` | integrations | productivity | Yes (hub.id: apple) | Apple integrations (Calendar, Reminders, Notes) are productivity tools |
| `google-workspace` | integrations | productivity | Yes (hub.id: google-workspace) | Google Workspace (Gmail, Calendar, Drive) are productivity tools |

```bash
# Scraper: admin → ai
git mv plugins/ai/skills/scraper plugins/ai/skills/scraper

# LinkedIn writer: consulting → career
git mv plugins/career/skills/linkedin-writer plugins/career/skills/linkedin-writer

# Content: creative → career
git mv plugins/career/skills/content plugins/career/skills/content

# Apple: integrations → productivity
git mv plugins/productivity/skills/apple plugins/productivity/skills/apple

# Google Workspace: integrations → productivity
git mv plugins/productivity/skills/google-workspace plugins/productivity/skills/google-workspace
```

No dashboard.yaml changes needed for any move — skills keep their `hub.id` values, routes stay the same. Only the sidebar section label changes (derived from new parent bundle directory).

#### 11d. Bundles Deleted After Absorption (7 deletions)

| Bundle | Skills Before | Absorbed Into | Action |
|--------|--------------|---------------|--------|
| `growth/` | growth (1 skill) | career/ | DELETE after move |
| `wealth/` | wealth (1 skill) | finance/ | DELETE after move |
| `venture/` | venture-augur, project-dev (2 skills) | professional/ (new name) | DELETE after rename+merge |
| `creative/` | content (1 skill) | career/ | DELETE after move |
| `integrations/` | apple, google-workspace (2 skills) | productivity/ | DELETE after move |
| `core/` | executor, router, swarm (3 skills) | orchestration/ (new name) | DELETE after rename |
| `observe/` | daemon, metrics, observe (3 skills) | observability/ (new name) | DELETE after rename |

```bash
# Delete empty bundles after all moves complete
rm -rf plugins/career/
rm -rf plugins/finance/
rm -rf plugins/professional/
rm -rf plugins/career/
rm -rf plugins/productivity/
rm -rf plugins/orchestration/
rm -rf plugins/observability/
```

#### 11e. Cross-Bundle Import Audit (Safety Check)

Before moving any skill, verify it has no hardcoded imports from sibling skills in the same bundle. Skills should only import from their own directory or from src/lib libraries in `src/`.

**Known safe** — all relocating skills are self-contained:
- `scraper`: standalone scraping scripts, no admin/ sibling imports
- `linkedin-writer`: empty shell (backend-only placeholder)
- `content`: standalone content management, no creative/ sibling imports
- `apple`: standalone Apple integrations, no integrations/ sibling imports
- `google-workspace`: standalone Google integrations, no integrations/ sibling imports
- `growth`: standalone growth tracking, no growth/ sibling imports (was sole skill in bundle)
- `wealth`: standalone wealth tracking, no wealth/ sibling imports (was sole skill in bundle)
- `project-dev`: standalone backlog/commits UI, no dev/ sibling imports
- `executor/router/swarm`: backend-only orchestration scripts, import from `src/` not sibling skills

The safety check should still be performed at execution time: `grep -r "from.*plugins/" plugins/{skill}/` for each relocating skill to catch any hidden cross-bundle references.

#### 11f. HUB_SECTION_ORDER Update

`navigation.ts` has `HUB_SECTION_ORDER` that controls sidebar section ordering. After consolidation, update it to reflect new bundle names:

```typescript
// BEFORE (17 bundles):
const HUB_SECTION_ORDER = [
  'core', 'career', 'growth', 'finance', 'wealth',
  'health', 'productivity', 'integrations', 'lifestyle',
  'creative', 'home', 'consulting', 'venture', 'enterprise',
  'ai', 'admin', 'observe', 'dev',
];

// AFTER (14 bundles):
const HUB_SECTION_ORDER = [
  'career',        // absorbed growth
  'finance',       // absorbed wealth
  'health',
  'productivity',  // absorbed apple, google-workspace from integrations
  'lifestyle',
  'home',
  'professional',  // renamed from venture, absorbed project-dev
  'enterprise',
  'consulting',
  'ai',            // absorbed scraper from admin
  'admin',
  'dev',
  'orchestration', // renamed from core (backend-only, but here for completeness)
  'observability', // renamed from observe
];
```

Removed: `growth`, `wealth`, `integrations`, `creative`, `core`, `observe`, `venture`
Added: `professional`, `orchestration`, `observability`
Reordered: user-facing bundles first (career→lifestyle), business (professional→consulting), infrastructure (ai→observability)

#### 11g. Final Bundle/Skill Map After All Changes

```
plugins/                              14 bundles, 41 skills (35 nav + 6 backend)
├── admin/                            3 nav + 1 backend
│   ├── channels/            [B]      Notification system
│   ├── renderer/            [D]      hub=renderer
│   ├── settings/            [D]      hub=admin
│   └── system-cleanup/      [D]      hub=system-cleanup
│
├── ai/                               5 nav
│   ├── ai_bridge/           [D]      hub=ai_bridge
│   ├── knowledge/           [D]      hub=knowledge
│   ├── mcp-app-factory/     [D]      hub=factory
│   ├── install/               [D]      hub=install
│   └── scraper/             [D]      hub=scraper          ← from admin/
│
├── career/                           4 nav + 1 backend
│   ├── career/              [D]      hub=career
│   ├── content/             [D]      hub=creative          ← from creative/
│   ├── growth/              [D]      hub=growth             ← from growth/
│   └── linkedin-writer/     [B]                             ← from consulting/
│
├── consulting/                       3 nav
│   ├── client-ai-consulting/    [D]  hub=client-ai-consulting
│   ├── client-smb-design/       [D]  hub=client-smb-design
│   └── client-terminal-automation/ [D] hub=client-terminal-automation
│
├── dev/                              5 nav (src/lib hub_id: control)
│   ├── advisor/             [D]      hub=control
│   ├── developer/           [D]      hub=control
│   ├── devops/              [D]      hub=control
│   ├── frontend/            [D]      hub=control
│   └── validator/           [D]      hub=control
│
├── enterprise/                       1 nav
│   └── enterprise/          [D]      hub=enterprise
│
├── finance/                          2 nav
│   ├── finance/             [D]      hub=finance
│   └── wealth/              [D]      hub=wealth             ← from wealth/
│
├── health/                           2 nav
│   ├── health/              [D]      hub=health
│   └── wearables/           [D]      hub=wearables
│
├── home/                             1 nav
│   └── home-automation/     [D]      hub=home
│
├── lifestyle/                        1 nav
│   └── lifestyle/           [D]      hub=lifestyle
│
├── observability/                    1 nav + 2 backend (renamed from observe/)
│   ├── daemon/              [D]      hub=daemon
│   ├── metrics/             [B]      Monitoring data collection
│   └── observe/             [D]      hub=observe
│
├── orchestration/                    0 nav, 3 backend (renamed from core/)
│   ├── executor/            [B]      Chain execution engine
│   ├── router/              [B]      Request routing
│   └── swarm/               [B]      Swarm orchestration
│
├── productivity/                     4 nav
│   ├── apple/               [D]      hub=apple              ← from integrations/
│   ├── eisenhower/          [D]      hub=eisenhower
│   ├── google-workspace/    [D]      hub=google-workspace   ← from integrations/
│   └── organizer/           [D]      hub=organizer
│
└── professional/                     2 nav (renamed from venture/)
    ├── project-dev/         [D]      hub=project-dev        ← from dev/
    └── venture-augur/       [D]      hub=venture

Legend: [D] = has dashboard.yaml (visible in nav), [B] = backend-only (no dashboard.yaml)
Arrows show where skills were relocated from.
```

**Bundles deleted** (absorbed or renamed): business/, services/, growth/, wealth/, venture/, creative/, integrations/, core/, observe/ (9 total — 2 from Decision 10 stale cleanup + 7 from Decision 11 consolidation)

#### 11h. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Cross-bundle imports break after move | Run `grep -r "from.*plugins/{old-bundle}" plugins/{skill}/` before each move |
| dashboard.yaml accidentally edited | No dashboard.yaml changes in this decision — category derives from bundle directory |
| Backend-only skills lost in move | Explicit KEEP list in Decision 10 (channels, executor, router, swarm, linkedin-writer, metrics) — verify all exist after consolidation |
| HUB_SECTION_ORDER stale after rename | Updated in 11f — unknown bundles auto-append alphabetically (existing behavior) |
| Plugin scripts reference old bundle paths | Grep `plugins/{old-bundle}` across entire codebase: Python scripts, shell aliases, TS imports, CI workflows. Include `plugins/professional` in grep. |
| Stale .next cache shows old nav | Delete `.next/` cache after consolidation, rebuild from scratch |
| Git history fragmented by moves | Use `git mv` (not `rm` + `cp`) to preserve file history across renames |

**Files affected:**
- All plugin directories being moved (see 11c, 11d)
- `src/dashboard/lib/navigation.ts` — Update `HUB_SECTION_ORDER`
- Config files referencing old bundle names (grep and update): CI workflows, agent rules, shell aliases, Python scripts

## Consequences

### Positive

- **True skill portability** — `mv plugins/a/skills/foo plugins/b/skills/foo` <!-- example path --> → next build, foo appears under bundle B. Zero config changes.
- **Bundle creation is mkdir** — `mkdir -p plugins/experiments/skills` → next build, "Experiments" section appears in sidebar.
- **Zero manual hub list maintenance** — No `PLUGIN_BUNDLES` arrays to maintain anywhere.
- **Single source of truth** — Every plugin page comes from `plugins/{bundle}/skills/{skill}/dashboard/`. The build discovers and copies it to `src/dashboard/app/{hubId}/`. You never hand-create page files in `src/dashboard/app/` for plugins.
- **Pages are build artifacts** — `src/dashboard/app/{hubId}/` for plugins is ephemeral. The build reconstructs it every time from `plugins/`. The `.plugin-mount` marker distinguishes build artifacts from core shell pages.
- **Filesystem = reality** — `ls plugins/` = sidebar sections. `ls plugins/{bundle}/skills/*/dashboard.yaml` = sidebar links. `ls plugins/{bundle}/skills/{skill}/dashboard/` = actual page files that get built. Transparent, auditable at every level.
- **Safer cleanup** — Mount cleanup uses `.plugin-mount` markers, not a fragile whitelist. Stale mounts from moved/deleted skills are automatically cleaned.

### Negative

- **Large migration effort** — 10 stale duplicate skills to delete, 9 bundles to delete (2 stale + 7 consolidated), 10 skills to relocate via `git mv`, 3 bundle renames, 2 redirect pages to delete, 2 plugin-mounted duplicates to fix at source, 3 standalone pages to audit. Mechanical but high surface area — execute in phases with verification between each.
- **Settings is special** — As a core shell page, it doesn't follow the plugin pattern. Justified: it configures the plugin system itself.
- **Brain/Sense are orphaned** — These hardcoded registry entries have no plugin backing. Either create plugins or accept they're legacy and remove them.
- **HUB_SECTION_ORDER still manual** — `discoverBundles()` returns alphabetical, but UX needs curated ordering. `HUB_SECTION_ORDER` remains as an ordering hint — not a discovery mechanism. Unknown bundles auto-appear at the end (already implemented).
- **Git history affected** — `git mv` preserves per-file history but `git log --follow` is required to trace moves. Acceptable trade-off for correct structure.

### Neutral

- ADR-108 hub rebalancing is completed and refined — this ADR finishes the migration by removing stale skill copies, deleting legacy bundles, and consolidating 17 bundles to 14
- Plugin self-containment (ADR-018) is strengthened
- The mount-plugins copy strategy remains unchanged — only discovery changes
- `dashboard.yaml` schema is unchanged — no skill needs any config edits during consolidation (category derives from filesystem)
- Bundle count reduced from 17 → 14 (4 merges + 3 absorptions + 3 renames), skill count unchanged at 41
- No backward-compatibility shims remain — no redirect pages, no tab name mappings, no legacy route aliases

## Implementation Order

```
Phase 1: Auto-discover bundles (PARALLEL)
├── Step 1: Replace PLUGIN_BUNDLES in generate-tab-registry.ts with discoverBundles()
└── Step 2: Replace PLUGIN_BUNDLES in mount-plugins.ts with discoverBundles()

Phase 2: Clean up hardcoded registry (depends on Phase 1)
├── Step 3: Remove all duplicate/orphaned entries from registry.ts
├── Step 4: Rename tabRegistry → coreTabRegistry, keep only settings
└── Step 5: Update getCompleteRegistry() to merge core + generated

Phase 3: Skill migration — delete stale duplicates (PARALLEL, before discovery changes take effect)
├── Step 6: Delete all 5 stale skills in business/ bundle, then delete business/ bundle
├── Step 7: Delete stale copies in productivity/ (apple, google-workspace, project-dev)
├── Step 8: Delete stale lifestyle/content (canonical: creative/content)
└── Step 9: Delete services/daemon (canonical: observe/daemon), then delete services/ bundle

Phase 4: Clean up orphaned pages (PARALLEL with Phase 3)
├── Step 10: Delete redirect pages (control/, operations/)
├── Step 11: Fix plugin-mounted duplicates (content/, venture-augur/) at source
└── Step 12: Audit standalone pages (memory/, activity/, agents/)

Phase 5: Simplify navigation (depends on Phases 2-4)
├── Step 13: Remove STATIC_OPERATIONS_ITEMS
├── Step 14: Define CORE_SHELL_ITEMS (Overview, Settings, Help)
└── Step 15: Remove admin/dev merge hacks in getPluginSections()

Phase 6: Auto-derive coreDirectories (depends on Phase 4)
└── Step 16: Replace hardcoded coreDirectories with marker-based detection

Phase 7: Eliminate SYSTEM_PAGE_PREFIXES (depends on Phase 5)
└── Step 17: Replace SYSTEM_PAGE_PREFIXES in useMCPContext.ts with CORE_SHELL_ROUTES

Phase 8: CI validation (depends on Phases 1-7)
├── Step 18: Create validate-nav-alignment.ts (with hub.id uniqueness check)
└── Step 19: Delete validate-tab-registry.ts (superseded)

Phase 9: Bundle Consolidation & Skill Restructuring (depends on Phase 3, before Phase 1 takes effect)
├── Step 20: Cross-bundle import audit — grep plugins/{skill}/ for sibling imports before any move
├── Step 21: Move growth skill to career/ bundle (git mv)
├── Step 22: Move wealth skill to finance/ bundle (git mv)
├── Step 23: Rename venture/ → professional/ and move project-dev into it (git mv)
├── Step 24: Rename core/ → orchestration/ (git mv executor, router, swarm)
├── Step 25: Rename observe/ → observability/ (git mv daemon, metrics, observe)
├── Step 26: Move scraper from admin/ to ai/ (git mv)
├── Step 27: Move linkedin-writer from consulting/ to career/ (git mv)
├── Step 28: Move content from creative/ to career/ (git mv)
├── Step 29: Move apple from integrations/ to productivity/ (git mv)
├── Step 30: Move google-workspace from integrations/ to productivity/ (git mv)
├── Step 31: Delete empty bundles (growth/, wealth/, venture/, creative/, integrations/, core/, observe/)
├── Step 32: Update HUB_SECTION_ORDER in navigation.ts
└── Step 33: Grep entire codebase for old bundle names — fix stale references in scripts, CI, aliases

Phase 10: Verification (depends on all)
├── Step 34: npm run generate-tabs — verify dynamic discovery works with 14 bundles
├── Step 35: npm run build — verify compilation
├── Step 36: npm run validate-nav — verify alignment (including hub.id uniqueness)
├── Step 37: Test portability — mv a skill between bundles, rebuild, verify nav updates
├── Step 38: Verify deleted bundles: business/, services/, growth/, wealth/, venture/, creative/, integrations/, core/, observe/ all gone
└── Step 39: Verify all 41 skills exist (35 nav + 6 backend) across 14 bundles
```

## Alternatives Considered

### Alternative 1: Keep PLUGIN_BUNDLES as a Validation-Only List

Keep the hardcoded list but use it only to validate discovered directories match expectations.

**Rejected because**: Still requires manual maintenance. The filesystem IS the canonical list. If someone creates `plugins/foo/`, it should just work.

### Alternative 2: Move Settings into a Plugin

Make everything a plugin, including settings. Core shell is just `layout.tsx` + `page.tsx`.

**Rejected because**: Settings configures the plugin system itself (enable/disable plugins, system config). Chicken-and-egg problem.

### Alternative 3: Use a Central plugins.yaml Manifest

Single config file declaring all bundles and their skills.

**Rejected because**: The filesystem already IS the manifest. `readdir()` > config file. A manifest file is another thing to keep in sync with the actual directory structure.

### Alternative 4: Store Category in dashboard.yaml

Let each skill declare which bundle section it belongs to via a `hub.category` field.

**Rejected because**: This breaks portability. Moving a skill between bundles would require editing its `dashboard.yaml`. The parent directory name should be the sole determinant of which section a skill appears in.

## References

- ADR-108: Hub Rebalancing — defines the current bundle/skill structure
- ADR-105: Plugin-driven tool scoping — hub boundaries determine MCP tool sets
- ADR-012: Config-driven dashboard — introduced dashboard.yaml and generated registry
- ADR-018: Plugin self-containment — skills own their files
- `src/dashboard/scripts/generate-tab-registry.ts` — Tab registry generator (has PLUGIN_BUNDLES)
- `src/dashboard/scripts/mount-plugins.ts` — Plugin mounter (has PLUGIN_BUNDLES + coreDirectories)
- `src/dashboard/lib/tabs/registry.ts` — Hardcoded fallback tab registry
- `src/dashboard/lib/navigation.ts` — Sidebar navigation builder
- `src/dashboard/hooks/useMCPContext.ts` — MCP context routing (has SYSTEM_PAGE_PREFIXES)
- `src/dashboard/scripts/validate-tab-registry.ts` — Existing validation script (to be superseded)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-109: Filesystem-Driven Dashboard — Portable Skills, Zero Config**.

Read the full ADR: `docs/decisions/ADR-109-filesystem-driven-dashboard.md`

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

1. **Create team**: `TeamCreate(team_name="adr-109-fs-dashboard", description="Implementing ADR-109: Filesystem-Driven Dashboard")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-109-fs-dashboard", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-109 team.
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

**Team name**: `adr-109-fs-dashboard`

#### Phase 1: Auto-Discover Bundles
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | In `generate-tab-registry.ts`: Delete `PLUGIN_BUNDLES` constant. Add `discoverBundles(pluginsDir)` function that calls `readdir(pluginsDir)` and returns directory names (excluding dotfiles). Update `discoverPluginDashboards()` to call `discoverBundles()` for each plugins dir instead of iterating `PLUGIN_BUNDLES`. | `src/dashboard/scripts/generate-tab-registry.ts` |
| 1.2 | developer | medium | In `mount-plugins.ts`: Delete `PLUGIN_BUNDLES` constant. Add same `discoverBundles(pluginsDir)` function. Update `scanPluginDir()` to discover bundles dynamically instead of iterating `PLUGIN_BUNDLES`. | `src/dashboard/scripts/mount-plugins.ts` |

#### Phase 2: Clean Up Hardcoded Registry (depends on Phase 1)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | In `registry.ts`: Remove ALL entries from `tabRegistry` except `settings` (lifestyle, venture, client-smb-design, client-terminal-automation, brain, sense, operations, control — all gone). Rename `tabRegistry` to `coreTabRegistry`. Update `getHubConfig()`, `getCompleteRegistry()`, `getHubKeys()`, and `HubKey` type to use `coreTabRegistry`. | `src/dashboard/lib/tabs/registry.ts` |

#### Phase 3: Skill Migration — Delete Stale Duplicates (PARALLEL, before discovery changes take effect)
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | low | Delete all 5 stale skills in `plugins/consulting/skills/` (client-ai-consulting, client-smb-design, client-terminal-automation, enterprise, venture-augur — all are empty shells with no dashboard.yaml, canonical versions exist in consulting/, enterprise/, professional/). Then delete the empty `plugins/consulting/` bundle directory. | `plugins/consulting/` (entire directory) |
| 3.2 | developer | low | Delete stale copies in `plugins/productivity/skills/`: `apple/` (canonical: integrations/apple), `google-workspace/` (canonical: integrations/google-workspace), `project-dev/` (canonical: dev/project-dev). These have no dashboard.yaml — the canonical versions do. | `plugins/productivity/skills/apple/`, `plugins/productivity/skills/google-workspace/`, `plugins/professional/skills/project-dev/` |
| 3.3 | developer | low | Delete `plugins/career/skills/content/` (canonical: creative/content, no dashboard.yaml). Delete `plugins/observability/skills/daemon/` (canonical: observe/daemon, no dashboard.yaml). Then delete the empty `plugins/ai/` bundle directory. | `plugins/career/skills/content/`, `plugins/ai/` (entire directory) |

#### Phase 4: Clean Up Orphaned Pages (PARALLEL with Phase 3)
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | low | Delete `src/dashboard/app/control/` (hand-created redirect to /ai_bridge — no `.plugin-mount`). Delete `src/dashboard/app/operations/` (hand-created redirect to /project-dev — no `.plugin-mount`). | `src/dashboard/app/control/`, `src/dashboard/app/operations/` |
| 4.2 | developer | medium | Fix plugin-mounted duplicates: `content/` (duplicate of `/creative`) and `venture-augur/` (duplicate of `/venture`) have `.plugin-mount` markers — they were mounted by the plugin system. Find the plugin source that creates them and remove the duplicate `dashboard.yaml` or hub.id alias. The marker-based cleanup (Phase 6) will handle the mounted directories. | `plugins/*/skills/*/dashboard.yaml` (find duplicates) |
| 4.3 | developer | medium | Audit standalone pages (no `.plugin-mount`): `memory/`, `activity/`, `agents/`. For each: check if a plugin already mounts equivalent content. If duplicate of a plugin page, delete. If unique with no plugin equivalent, add `TODO_CLEANUP: migrate to plugin` marker. | `src/dashboard/app/memory/`, `src/dashboard/app/activity/`, `src/dashboard/app/agents/` |

#### Phase 5: Simplify Navigation (depends on Phases 2-4)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer | medium | In `navigation.ts`: (1) Remove `STATIC_OPERATIONS_ITEMS` constant. (2) Update `STATIC_SECTIONS` to be the core shell: Overview (/), Settings (/settings), Help (/help). (3) Remove the admin/dev special-case merge in `getPluginSections()` — all bundle sections are treated equally, built purely from `pluginNavItems` grouped by category. (4) Remove `STATIC_TOOLTIPS` entries for deleted routes (/operations, /control). (5) KEEP `HUB_SECTION_ORDER` as ordering hint. (6) KEEP `isNavItemEnabled()` dev mode filtering. | `src/dashboard/lib/navigation.ts` |

#### Phase 6: Auto-Derive Core Directories (depends on Phase 4)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 6.1 | developer | medium | In `mount-plugins.ts`: Replace hardcoded `coreDirectories` set in `cleanPluginMounts()` with marker-based detection. Logic: iterate `app/` entries; if directory has `.plugin-mount` marker → it's a plugin mount (eligible for cleanup). Everything without the marker → core (protected). Delete the `coreDirectories` constant. | `src/dashboard/scripts/mount-plugins.ts` |

#### Phase 7: Eliminate SYSTEM_PAGE_PREFIXES (depends on Phase 5)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 7.1 | developer | medium | In `useMCPContext.ts`: Replace `SYSTEM_PAGE_PREFIXES` (~20 entries) with `CORE_SHELL_ROUTES` containing only core shell paths (`/settings`, `/help`). Logic: if pathname is `/` or starts with a core shell route → `switch-mcp-context`. Everything else → `focus-context` (skill page). Delete the old array. | `src/dashboard/hooks/useMCPContext.ts` |

#### Phase 8: CI Validation (depends on Phases 1-7)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 8.1 | developer | medium | Create `src/dashboard/scripts/validate-nav-alignment.ts`: (1) Discover all dashboard.yaml files in plugins. (2) Read generated-registry.ts pluginManagedHubs. (3) List directories in src/dashboard/app/. (4) Assert: every dashboard.yaml hub in generated-registry. (5) Assert: every generated-registry entry has an app/ directory. (6) Assert: no orphaned app/ directories (not core AND not plugin-mounted). (7) Assert: no duplicate hub.id values across all dashboard.yaml files. (8) Assert: no stale bundles (business, services, custom). (9) Exit non-zero on mismatch. Add `validate-nav` to package.json scripts. | `src/dashboard/scripts/validate-nav-alignment.ts`, `src/dashboard/package.json` |
| 8.2 | developer | low | Delete `src/dashboard/scripts/validate-tab-registry.ts` (superseded by validate-nav-alignment.ts). Remove its script entry from package.json. | `src/dashboard/scripts/validate-tab-registry.ts`, `src/dashboard/package.json` |

#### Phase 9: Bundle Consolidation & Skill Restructuring (depends on Phase 3, before Phase 1 takes effect)
**Strategy**: PIPELINE (moves must be sequential to avoid git conflicts; audit first, then moves, then cleanup)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 9.1 | developer | low | **Cross-bundle import audit**: For each skill being relocated (scraper, linkedin-writer, content, apple, google-workspace, growth, wealth, project-dev, executor, router, swarm, daemon, metrics, observe), run `grep -r "from.*plugins/" plugins/{bundle}/skills/{skill}/` and `grep -r "import.*plugins/" plugins/{bundle}/skills/{skill}/`. Report any cross-bundle references found. If clean → proceed. If references found → document and fix before moving. | All relocating skills |
| 9.2 | developer | low | **Merge growth → career**: `git mv plugins/career/skills/growth plugins/career/skills/growth`. Verify growth/dashboard.yaml hub.id unchanged. Delete empty `plugins/career/`. | `plugins/career/`, `plugins/career/skills/growth/` |
| 9.3 | developer | low | **Merge wealth → finance**: `git mv plugins/finance/skills/wealth plugins/finance/skills/wealth`. Verify wealth/dashboard.yaml hub.id unchanged. Delete empty `plugins/finance/`. | `plugins/finance/`, `plugins/finance/skills/wealth/` |
| 9.4 | developer | low | **Rename venture → professional + absorb project-dev**: `mkdir -p plugins/professional/skills`. `git mv plugins/professional/skills/venture-augur plugins/professional/skills/venture-augur`. `git mv plugins/professional/skills/project-dev plugins/professional/skills/project-dev`. Delete empty `plugins/professional/`. (dev/ bundle keeps 5 agent skills.) | `plugins/professional/`, `plugins/professional/`, `plugins/professional/skills/project-dev/` |
| 9.5 | developer | low | **Rename core → orchestration**: `mkdir -p plugins/orchestration/skills`. `git mv plugins/orchestration/skills/executor plugins/orchestration/skills/executor`. `git mv plugins/orchestration/skills/router plugins/orchestration/skills/router`. `git mv plugins/orchestration/skills/swarm plugins/orchestration/skills/swarm`. Delete empty `plugins/orchestration/`. | `plugins/orchestration/`, `plugins/orchestration/` |
| 9.6 | developer | low | **Rename observe → observability**: `mkdir -p plugins/observability/skills`. `git mv plugins/observability/skills/daemon plugins/observability/skills/daemon`. `git mv plugins/observability/skills/metrics plugins/observability/skills/metrics`. `git mv plugins/observability/skills/observe plugins/observability/skills/observe`. Delete empty `plugins/observability/`. | `plugins/observability/`, `plugins/observability/` |
| 9.7 | developer | low | **Move scraper → ai**: `git mv plugins/ai/skills/scraper plugins/ai/skills/scraper`. Verify dashboard.yaml hub.id unchanged. | `plugins/ai/skills/scraper/`, `plugins/ai/skills/scraper/` |
| 9.8 | developer | low | **Move linkedin-writer → career**: `git mv plugins/career/skills/linkedin-writer plugins/career/skills/linkedin-writer`. (Backend-only, no dashboard.yaml.) | `plugins/career/skills/linkedin-writer/`, `plugins/career/skills/linkedin-writer/` |
| 9.9 | developer | low | **Move content → career**: `git mv plugins/career/skills/content plugins/career/skills/content`. Verify dashboard.yaml hub.id unchanged. Delete empty `plugins/career/`. | `plugins/career/`, `plugins/career/skills/content/` |
| 9.10 | developer | low | **Move apple → productivity**: `git mv plugins/productivity/skills/apple plugins/productivity/skills/apple`. Verify dashboard.yaml hub.id unchanged. | `plugins/productivity/skills/apple/`, `plugins/productivity/skills/apple/` |
| 9.11 | developer | low | **Move google-workspace → productivity**: `git mv plugins/productivity/skills/google-workspace plugins/productivity/skills/google-workspace`. Verify dashboard.yaml hub.id unchanged. Delete empty `plugins/productivity/`. | `plugins/productivity/`, `plugins/productivity/skills/google-workspace/` |
| 9.12 | devops | medium | **Update HUB_SECTION_ORDER**: In `navigation.ts`, update `HUB_SECTION_ORDER` to reflect 14 bundles: remove growth, wealth, integrations, creative, core, observe. Add orchestration, observability. Reorder: user-facing first, business second, infrastructure last. | `src/dashboard/lib/navigation.ts` |
| 9.13 | devops | medium | **Fix stale bundle references**: Grep entire codebase for old bundle names (`plugins/career`, `plugins/finance`, `plugins/professional`, `plugins/career`, `plugins/productivity`, `plugins/orchestration/`, `plugins/observability/`). Fix all references in: Python scripts, shell aliases (.zshrc), CI workflows (.github/), agent rules, CLAUDE.md generator, sync_agents.py paths, config files. | Multiple files across codebase |

#### Phase 10: Verification (depends on all)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 10.1 | validator | low | Run `npm run generate-tabs`. Verify all 14 bundles discovered. Verify all 35 nav skills have registry entries. Grep entire codebase for `PLUGIN_BUNDLES` — must return zero matches. |
| 10.2 | validator | low | Run `npm run build` — verify dashboard compiles with no broken imports. |
| 10.3 | validator | low | Run `npm run validate-nav` — verify filesystem-navigation alignment (including hub.id uniqueness across all 35 nav skills). |
| 10.4 | validator | medium | Test portability: temporarily `git mv` one skill to a different bundle, run `npm run generate-tabs`, verify the generated-registry shows the skill under the new bundle category. Then `git checkout` to restore. |
| 10.5 | validator | low | Verify deleted bundles: `ls plugins/{name}` must fail for: business, services, growth, wealth, venture, creative, integrations, core, observe (9 bundles). Verify exactly 14 bundle directories exist under `plugins/`. |
| 10.6 | validator | low | Verify skill count: count all `skills/*/` directories across all 14 bundles. Must total 41 (35 with dashboard.yaml + 6 backend-only). List any missing or unexpected skills. |
| 10.7 | architect | low | Final review: verify no hardcoded hub arrays remain (`PLUGIN_BUNDLES`, `SYSTEM_PAGE_PREFIXES`, `coreDirectories`). Verify registry.ts has only core entries. Verify navigation.ts has no STATIC_OPERATIONS_ITEMS and HUB_SECTION_ORDER has 14 entries. Verify no stale references to old bundle names. Update ADR-109 status to "Accepted". |

### Completion Criteria

**Discovery & Registry (Decisions 1-3)**:
- [ ] Zero matches for `PLUGIN_BUNDLES` in codebase (grep returns nothing)
- [ ] `registry.ts` contains only `coreTabRegistry` with `settings`

**Navigation & MCP (Decisions 5, 7, 8)**:
- [ ] `navigation.ts` has no `STATIC_OPERATIONS_ITEMS`
- [ ] Zero matches for `SYSTEM_PAGE_PREFIXES` in codebase
- [ ] `useMCPContext.ts` uses `CORE_SHELL_ROUTES` (2-3 entries, not ~20)

**Mount System (Decision 6)**:
- [ ] `mount-plugins.ts` has no hardcoded `coreDirectories`

**Stale Cleanup (Decision 10)**:
- [ ] Stale bundles deleted: `plugins/consulting/` and `plugins/ai/` gone
- [ ] No backward-compatibility redirects, tab name mappings, or legacy route aliases remain
- [ ] Stale duplicate skills deleted: 10 copies across productivity, lifestyle, business, services
- [ ] Redirect pages (control, operations) deleted
- [ ] Plugin-mounted duplicates (content, venture-augur) fixed at source

**Bundle Consolidation (Decision 11)**:
- [ ] Exactly 14 bundle directories under `plugins/`
- [ ] Exactly 41 skills total (35 nav + 6 backend)
- [ ] Deleted bundles gone: growth/, wealth/, venture/, creative/, integrations/, core/, observe/
- [ ] Renamed bundles exist: professional/ (2 nav skills), orchestration/ (3 backend skills), observability/ (3 skills)
- [ ] Relocated skills in correct bundles: scraper in ai/, linkedin-writer+content+growth in career/, wealth in finance/, project-dev+venture-augur in professional/, apple+google-workspace in productivity/
- [ ] `HUB_SECTION_ORDER` in navigation.ts has 14 entries (no old bundle names)
- [ ] Zero stale references to old bundle names in scripts, CI, aliases, config

**Validation & Build (Decisions 7, 9)**:
- [ ] `validate-tab-registry.ts` deleted (superseded)
- [ ] `npm run build` passes
- [ ] `npm run generate-tabs` discovers all 14 bundles dynamically
- [ ] `npm run validate-nav` passes (including hub.id uniqueness)
- [ ] Skill portability verified (move between bundles → nav updates)
- [ ] All 10 phases executed
- [ ] ADR status updated to "Accepted"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-109-filesystem-driven-dashboard.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
