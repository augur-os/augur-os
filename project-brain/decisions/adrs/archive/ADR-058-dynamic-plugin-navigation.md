---
status: Implemented
date: '2026-02-08'
deciders:
- User
- Claude
related: []
hub: null
tags:
- dynamic
- plugin
- navigation
superseded_by: null
---

# ADR-058: Dynamic Plugin Navigation

## Context

The sidebar navigation is fully hardcoded in `src/dashboard/lib/navigation.ts`. When plugins are added or removed, their nav entries must be manually edited — including icon imports, section placement, `isPluginRoute` array, and tooltip map. This resulted in 12 of 24 plugins being orphaned (have `dashboard.yaml` + mounted pages but no nav entry).

The generated registry (`scripts/generate-tab-registry.ts`) already scans all plugins at build time and knows their hub ID, title, subtitle, icon, bundle, and category. But it only outputs tab configs — not nav entries.

**Root cause**: Navigation is static TypeScript, while plugins are dynamic YAML configs. The build pipeline generates tab registries but not nav registries.

## Decision

Extend the build-time registry generator to also output **plugin nav items**. The sidebar then merges static core items (Overview, Inbox, Settings, Help) with dynamically generated plugin items grouped by their `category` field in `dashboard.yaml`.

### Category → Section Mapping

| dashboard.yaml `category` | Sidebar Section | Priority |
|---------------------------|----------------|----------|
| `personal` | Life | primary |
| `business` | Business | primary |
| `productivity` | Capabilities | secondary |
| `system` | Operations | tertiary |

### dashboard.yaml Schema Additions (Optional Fields)

```yaml
hub:
  id: my-plugin
  title: My Plugin
  icon: Sparkles
  category: personal
  nav_label: Custom Name    # Override sidebar label (default: hub title)
  nav_route: /custom-path   # Override route (default: /{hub.id})
  nav_hidden: true           # Hide from nav, keep page accessible via URL
mode: dev                    # Hub-level: only visible in dev mode
```

### Static Items (Not Plugin-Driven)

These nav items remain hardcoded — they are core routes, not plugins:
- `/` (Overview), `/inbox` (Inbox), `/projects` (Projects)
- `/operations` (Operations, dev), `/control` (Control, dev)
- `/settings` (Settings), `/help` (Help)

### Expected Results

All 24 plugins auto-register in their correct section:

| Plugin | Category | Section | Nav Label |
|--------|----------|---------|-----------|
| lifestyle | personal | Life | Lifestyle |
| health | personal | Life | Health |
| finance | personal | Life | Finance |
| wearables | personal | Life | Wearables |
| venture-augur | business | Business | Venture |
| client-smb-design | business | Business | SMB Design Office |
| client-ai-consulting | business | Business | AI Consulting |
| client-terminal-automation | business | Business | Bossa Nova |
| content | business | Business | Content Studio |
| enterprise | business | Business | Enterprise |
| career | productivity | Capabilities | Career |
| eisenhower | productivity | Capabilities | Eisenhower Matrix |
| knowledge | productivity | Capabilities | Knowledge |
| apple | productivity | Capabilities | Apple |
| google-workspace | productivity | Capabilities | Google Workspace |
| organizer | productivity | Capabilities | System Organizer |
| install | productivity | Capabilities | Install |
| home-automation | system | Operations | Smart Home |
| daemon | system | Operations | Services |
| updater | system | Operations | Updates |
| renderer | system | Operations | Renderer |
| scraper | system | Operations | Web Scraper |
| ai_bridge | system | Operations | Platform |
| mcp-app-factory | system | Operations | Plugin Factory (dev only) |

## Consequences

### Positive
- Adding/removing a plugin automatically updates the sidebar after `npm run build`
- No more orphaned plugins — every plugin with `dashboard.yaml` gets a nav entry
- Single source of truth: `dashboard.yaml` controls both tabs and nav
- Users can still hide items via Settings sidebar config panel

### Negative
- Nav order within sections is now alphabetical (or by discovery order) instead of manually curated
- Adding a new `category` value requires updating the category→section mapping

### Neutral
- Build step (`generate-tabs`) already runs on every build — no new build steps needed
- Icon resolution uses existing `import * as LucideIcons` pattern from `HubRenderer.tsx`

## Alternatives Considered

### Alternative 1: Runtime API-Driven Nav
Fetch plugin list from `/api/registry` at runtime (like `DynamicSkillsNav.tsx` does for skills). Rejected because: adds loading state to nav, slower initial render, and the data is already available at build time.

### Alternative 2: Separate Nav Registry Script
Create a second generator script for nav items. Rejected because: duplicates the plugin scanning logic already in `generate-tab-registry.ts`. Better to extend the existing script.

## References

- `src/dashboard/scripts/generate-tab-registry.ts` — Existing registry generator to extend
- `src/dashboard/lib/navigation.ts` — Current hardcoded navigation
- `src/dashboard/lib/tabs/generated-registry.ts` — Current generated output (auto-generated)
- `src/dashboard/components/plugin/HubRenderer.tsx` — Dynamic icon resolution pattern (`import * as LucideIcons`)
- `src/dashboard/components/SidebarNav.tsx` — Nav consumer
- `src/dashboard/components/DynamicSkillsNav.tsx` — Runtime dynamic nav (skills, not plugins)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-058-dynamic-nav`

### Phase 1: Generator Extension
**Strategy**: PIPELINE (must generate before consuming)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Extend `generate-tab-registry.ts`: add `category`, `icon`, `mode`, `nav_label`, `nav_route`, `nav_hidden` to `DashboardYaml` interface. Extract from each dashboard.yaml. Output new export `pluginNavItems: PluginNavItem[]` with shape `{ hubId, title, subtitle, icon, category, mode?, navLabel?, navRoute?, navHidden? }`. Add `PluginNavItem` type to `types.ts`. | `src/dashboard/scripts/generate-tab-registry.ts`, `src/dashboard/lib/tabs/types.ts` |
| 1.2 | developer | low | Update dashboard.yaml files that need overrides: `client-terminal-automation` → `nav_label: "Bossa Nova"`, `venture-augur` → `nav_route: /venture`, `daemon` → `nav_label: "Services"`, `updater` → `nav_label: "Updates"` | `plugins/consulting/skills/client-terminal-automation/dashboard.yaml`, `plugins/professional/skills/venture-augur/augur.yaml`, `plugins/observability/skills/daemon/dashboard.yaml`, `plugins/admin/skills/updater/augur.yaml` |
| 1.3 | developer | low | Run `npm run generate-tabs` in `src/dashboard/` to regenerate `generated-registry.ts` with new `pluginNavItems` export. Verify output contains all 24 plugins. | `src/dashboard/lib/tabs/generated-registry.ts` |

### Phase 2: Navigation Refactor
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | frontend | medium | Refactor `navigation.ts`: (1) Remove all hardcoded plugin items from SECTIONS — keep only static core items (Overview, Inbox, Projects in root section; Operations + Control in Operations section with `category: 'dev'`; Settings + Help in Operations section). (2) Import `pluginNavItems` from `generated-registry`. (3) Import `* as LucideIcons from 'lucide-react'` for dynamic icon resolution (pattern from `HubRenderer.tsx` line 12+25). (4) Add `getPluginSections()` that groups `pluginNavItems` by category→section using the mapping table. (5) Update `getEnabledSections()` to merge static sections + plugin sections. (6) Remove `isPluginRoute` array — all items from `pluginNavItems` are plugin routes by definition, check against `pluginManagedHubs`. (7) Remove `routeToHubId` map — use `navRoute` from generated data. (8) Generate `TOOLTIP_MAP` from plugin title+subtitle. (9) Support `mode: 'dev'` items with `category: 'dev'`. (10) Respect `navHidden` flag. | `src/dashboard/lib/navigation.ts` |
| 2.2 | frontend | low | Update `SidebarNav.tsx` if needed — should be minimal since it already calls `getEnabledSections()`. Verify existing patterns still work (visibility localStorage, mode filtering, DynamicSkillsNav). | `src/dashboard/components/SidebarNav.tsx` |

### Phase 3: Verification
**Strategy**: PARALLEL

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 3.1 | validator | low | Run `npx tsc --noEmit` in `src/dashboard/`, run `npx jest SidebarNav`, run `npm run build`. All must pass. |
| 3.2 | validator | low | Verify in browser (Chrome MCP): navigate to localhost:3000, check sidebar shows all 24 plugins in correct sections. Check dev mode toggle shows/hides dev-only items. Click at least 3 plugins to verify pages load. |

### Completion Criteria
- [ ] `generate-tab-registry.ts` outputs `pluginNavItems` with all 24 plugins
- [ ] `navigation.ts` has zero hardcoded plugin items — all come from generated registry
- [ ] All 24 plugins appear in correct sidebar sections
- [ ] Dev-only plugins (mcp-app-factory) only visible in dev mode
- [ ] TypeScript compiles clean, SidebarNav tests pass, build succeeds
- [ ] Browser verification: all sections render, plugins clickable
