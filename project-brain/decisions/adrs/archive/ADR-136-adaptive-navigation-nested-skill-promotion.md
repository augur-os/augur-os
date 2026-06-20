---
status: Implemented
date: '2026-02-22'
deciders:
- Project team
related:
- ADR-128 (contribution-based hub assembly)
- ADR-109 (filesystem-driven dashboard)
- ADR-058 (dynamic plugin navigation)
hub: null
tags:
- adaptive
- navigation
- nested
- skill
- promotion
superseded_by: null
---

# ADR-136: Adaptive Navigation — Nested Skill Promotion

## Context

ADR-128 consolidated navigation from 40 per-skill sidebar entries to 14 per-hub entries by grouping skills under their contributing hub. This solved sidebar bloat but created **tab bloat** — large hubs now have too many flat tabs from unrelated skills mixed in one tab bar:

| Hub | Total Tabs | Skills | Problem |
|-----|-----------|--------|---------|
| career | 21 | 4 | Job search (8) + content creation (6) + personal growth (7) in one bar |
| ai | 20 | 5 | Platform (6) + knowledge (5) + plugin factory (4) + install (2) + scraper (3) |
| productivity | 18 | 4 | Apple (6) + Eisenhower (5) + Google (4) + Organizer (3) — all distinct tools |
| professional | 14 | 2 | Venture ops (8) + dev ops (6) mixed |
| observability | 9 | 3 | Monitoring (7) + daemon (2) |

A 21-item tab bar overflows horizontally and forces users to scroll to find what they need. Unrelated workflows (job search vs LinkedIn writing vs personal growth) compete for attention in the same flat namespace.

### Historical Approaches

| Approach | Sidebar | Tabs per Page | Problem |
|----------|---------|---------------|---------|
| Per-skill nav (pre ADR-128) | 40 items | 3-8 | Sidebar overwhelmed; tiny 1-page skills wasted nav space |
| Per-hub nav (current, ADR-128) | 14 items | up to 21 | Tab bar overwhelmed; unrelated skills mixed |
| **Needed** | ~14-33 items (collapsible) | max ~10 | Balanced — neither level overwhelmed |

### Constraints

1. **Self-contained** — each skill declares its own navigation behavior in `augur.yaml`, no central manifest
2. **Backward compatible** — existing skills without new fields must work unchanged
3. **No routing changes** — extension skills already mount at `/{hubId}/{skillId}/{pageId}`
4. **Filesystem-driven** — per ADR-109 principles, the build discovers everything from augur.yaml

## Decision

### 1. Skill-Level `nav_mode` Declaration

Add a `nav_mode` field to each skill's `augur.yaml`. Each skill decides how its pages appear in navigation:

```yaml
# Example: a large skill that warrants its own sidebar entry
contributes_to: career
nav_mode: nested        # NEW FIELD

contributions:
  pages:
    - id: posts
      title: Posts
      icon: FileText
    - id: books
      title: Books
      icon: BookOpen
    # ... 6 total pages
```

| Value | Sidebar | Tabs | When to Use |
|-------|---------|------|-------------|
| `inline` (default) | Pages appear as tabs in hub overview tab bar | Part of hub tab bar | Small skills (1-3 pages), or primary skill whose pages ARE the hub |
| `nested` | Skill gets its own sub-item under the hub in sidebar, with its own tab bar | Own tab bar | Large skills (4+ pages) with a distinct workflow |
| `hidden` | Pages exist at URL but not in sidebar or tab bar | None | Backend-focused, utility pages accessed via links/widgets |

**Self-containment**: The skill author decides. No build-time inference, no magic page-count thresholds, no central config. The build reads `nav_mode` from each `augur.yaml` and assembles navigation accordingly.

### 2. Sidebar: Two-Level Collapsible Tree

The sidebar renders hubs as collapsible groups. Hubs with nested skills expand to show sub-items:

```
Career                        ← Hub group (collapsible)
  Overview                    ← Hub overview (inline tabs from career + linkedin-writer)
  Content                     ← Nested skill (own page with 6 tabs)
  Growth                      ← Nested skill (own page with 7 tabs)

AI                            ← Hub group (collapsible)
  Overview                    ← Inline tabs from ai_bridge (6) + install (2) = 8 tabs
  Knowledge                   ← Nested skill (5 tabs)
  Plugin Factory              ← Nested skill (4 tabs)
  Scraper                     ← Nested skill (3 tabs)

Productivity                  ← Hub group (collapsible)
  Apple                       ← Nested skill (6 tabs)
  Eisenhower                  ← Nested skill (5 tabs)
  Google Workspace            ← Nested skill (4 tabs)
  Organizer                   ← Nested skill (3 tabs)

Lifestyle                     ← Single flat item (no nested skills → no expand)
Home                          ← Single flat item
Health                        ← Single flat item (2 small inline skills)
Enterprise                    ← Single flat item
```

**Rendering rules:**

| Hub State | Sidebar Rendering |
|-----------|------------------|
| All skills `inline` | Single flat item — click goes to hub overview with tabs. Same as today. |
| Mix of `inline` + `nested` | Collapsible group. "Overview" first (shows inline tabs), then nested skill sub-items. |
| All skills `nested` | Collapsible group. No "Overview" sub-item — first nested skill is the default. Hub route shows a landing page with navigation cards. |

**Collapsed vs Expanded:**
- Collapsed: 14 hub items (same as today)
- All expanded: ~33 items (14 hubs + ~19 nested sub-items)
- Typical use: 2-3 hubs expanded at a time → ~20 visible items

The collapsible tree is the same pattern used by VS Code's sidebar, Notion's page tree, and Linear's project nav.

### 3. Hub Overview Page Adaptation

The `HubOverview` component adapts based on the hub's inline/nested mix:

**Scenario A: All inline (lifestyle, home, health, enterprise, admin)**
- Tab bar shows all contributed pages from inline skills
- No changes from today

**Scenario B: Mix of inline + nested (career, ai, professional, finance)**
- Tab bar shows ONLY inline skill pages (max ~9 tabs instead of 21)
- Overview tab content includes navigation cards to nested skills (title, icon, brief description, page count)
- Cards render below widgets, in a "More in this hub" section

**Scenario C: All nested (productivity, consulting)**
- No tab bar (or a single "Overview" tab)
- Overview page renders as a navigation landing page: hub header + widget grid + skill navigation cards
- Each card links to the nested skill's own page

### 4. Nested Skill Pages

Each nested skill gets its own page with its own tab bar at its existing URL:

- **URL**: `/{hubId}/{skillId}/` → skill overview, `/{hubId}/{skillId}/{pageId}` → specific page
- **Tab bar**: shows only that skill's contributed pages
- **Layout**: uses a light layout that inherits the hub's visual theme
- **Breadcrumb**: `Hub Name > Skill Name > Page Name` (helps orientation)

No routing changes needed — extension skills already mount at `/{hubId}/{skillId}/`. The `nested` flag only changes where the navigation link appears (sidebar sub-item instead of hub tab bar).

### 5. Tab Grouping for Multi-Skill Inline Tabs

When a hub overview has inline tabs from multiple skills, group them visually in the tab bar:

```
Career:  [Pipeline | Companies | Scoring | Interview | STAR | Resume | Profile]  ·  [LinkedIn Writer]
```

Implementation:
- Tabs are ordered: primary skill first, then contributing skills alphabetically
- A subtle visual separator (thin divider or extra spacing) appears between skill groups
- Optional: a small muted label above each group identifying the contributing skill (shown on hover or always for multi-group bars)
- Single-skill inline hubs (lifestyle, home) show no grouping — just tabs

### 6. Schema Changes

#### augur.yaml — New `nav_mode` field

```yaml
nav_mode: inline | nested | hidden    # Optional, default: inline
```

Added alongside existing fields (`contributes_to`, `hub`, `contributions`). No changes to existing fields.

#### DashboardYaml type

```typescript
// In lib/plugin-schema/types.ts
export interface DashboardYaml {
  // ... existing fields ...
  nav_mode?: 'inline' | 'nested' | 'hidden';  // NEW — default: 'inline'
}
```

#### AssembledHub type — Tag tabs with nav_mode

```typescript
// In lib/plugin-schema/types.ts
export interface AssembledHub {
  // ... existing fields ...
  tabs: (PageDefinition & {
    skill: string;
    nav_mode: 'inline' | 'nested' | 'hidden';  // NEW
    skill_title: string;   // NEW — for tab group labels
    skill_icon?: string;   // NEW — for sidebar sub-item icon
  })[];
}
```

#### PluginNavItem type — Add children for nested skills

```typescript
// In lib/tabs/types.ts
export type PluginNavItem = {
  // ... existing fields ...
  children?: PluginNavSubItem[];  // NEW — nested skill sidebar entries
};

export type PluginNavSubItem = {
  skillId: string;
  label: string;
  icon: string;
  href: string;
  pageCount: number;  // For display: "Knowledge (5)"
};
```

#### TabItem type — Add group metadata

```typescript
// In lib/tabs/types.ts
export type TabItem = {
  // ... existing fields ...
  group?: string;      // NEW — skill ID for visual grouping
  groupLabel?: string; // NEW — skill title for group label
};
```

### 7. Build Pipeline Changes

Updates to `generate-tab-registry.ts`:

1. **Read `nav_mode`** from each skill's `augur.yaml` during scanning (default: `inline`)
2. **Tag assembled hub tabs** with `nav_mode`, `skill_title`, and `skill_icon`
3. **Split `pluginTabRegistry` output**: for each hub, only `inline` tabs go into the hub's tab list; `nested` tabs go into separate per-skill tab entries
4. **Generate `children[]`** on `pluginNavItems`: for each hub with nested skills, populate the `children` array with `{ skillId, label, icon, href, pageCount }`
5. **Add `group` and `groupLabel`** to inline tab entries when multiple inline skills contribute to the same hub

### 8. Recommended nav_mode Assignments

Based on page count and workflow distinctness:

| Hub | Skill | Pages | nav_mode | Rationale |
|-----|-------|-------|----------|-----------|
| **career** | career | 8 | inline | Primary skill — its pages ARE the career hub |
| | content | 6 | **nested** | Distinct creative workflow |
| | growth | 7 | **nested** | Distinct learning/growth workflow |
| | linkedin-writer | 1 | inline | Single page, small addition |
| **ai** | ai_bridge | 6 | inline | Primary skill — platform core |
| | knowledge | 5 | **nested** | Distinct knowledge management |
| | mcp-app-factory | 4 | **nested** | Distinct plugin creation |
| | install | 2 | inline | Small, core AI discovery function |
| | scraper | 3 | **nested** | Distinct web scraping workflow |
| **productivity** | apple | 6 | **nested** | Distinct Apple suite |
| | eisenhower | 5 | **nested** | Distinct prioritization system |
| | google-workspace | 4 | **nested** | Distinct Google suite |
| | organizer | 3 | **nested** | Distinct file organization |
| **professional** | venture-augur | 8 | inline | Primary skill — venture ops |
| | project-dev | 6 | **nested** | Distinct dev ops workflow |
| **observability** | observe | 7 | inline | Primary skill — core monitoring |
| | daemon | 2 | inline | Small, closely related to monitoring |
| | metrics | 0 | hidden | Backend-only |
| **finance** | finance | 3 | inline | Primary skill |
| | wealth | 5 | **nested** | Distinct investment workflow |
| **consulting** | client-hub | 0 | inline | Hub owner, no pages |
| | client-ai-consulting | 3 | **nested** | Distinct per-client workflow |
| | client-smb-design | 1 | **nested** | Distinct per-client workflow |
| | client-terminal-automation | 3 | **nested** | Distinct per-client workflow |
| **home** | home-automation | 6 | inline | Single-skill hub |
| **lifestyle** | lifestyle | 7 | inline | Single-skill hub |
| **health** | health | 2 | inline | Primary skill |
| | wearables | 1 | inline | Small addition |
| **enterprise** | enterprise | 3 | inline | Single-skill hub |
| **admin** | updater | 3 | inline | Primary skill |
| | renderer | 0 | hidden | No tabs contributed |
| | channels | 0 | hidden | Backend-only |
| | system-cleanup | 0 | inline | No tabs contributed |

**Result after applying nav_mode:**

| Hub | Inline Tabs | Nested Skills | Sidebar Sub-items |
|-----|-------------|---------------|-------------------|
| career | 9 | content, growth | 3 (Overview + 2) |
| ai | 8 | knowledge, factory, scraper | 4 (Overview + 3) |
| productivity | 0 | apple, eisenhower, google, organizer | 4 (all nested) |
| professional | 8 | project-dev | 2 (Overview + 1) |
| finance | 3 | wealth | 2 (Overview + 1) |
| consulting | 0 | ai-consulting, smb-design, terminal-auto | 3 (all nested) |
| observability | 9 | — | 0 (flat item) |
| home | 6 | — | 0 (flat item) |
| lifestyle | 7 | — | 0 (flat item) |
| health | 3 | — | 0 (flat item) |
| enterprise | 3 | — | 0 (flat item) |
| admin | 3 | — | 0 (flat item) |

**Max tab bar: 9** (down from 21). **Sidebar collapsed: 14** (same as today). **Sidebar expanded: ~32** (manageable with collapsible groups).

### 9. Navigation Component Updates

#### SidebarNav.tsx

The sidebar needs to support two-level rendering:

```tsx
// For each section:
{section.items.map(item => (
  item.children?.length > 0 ? (
    // Collapsible group with sub-items
    <CollapsibleNavGroup key={item.href} item={item} activeHref={activeHref}>
      <NavSubItem href={item.href} label="Overview" icon={item.icon} />
      {item.children.map(child => (
        <NavSubItem key={child.href} href={child.href} label={child.label} icon={child.icon} />
      ))}
    </CollapsibleNavGroup>
  ) : (
    // Flat item (no nested skills)
    <NavLink key={item.href} item={item} isActive={activeHref === item.href} />
  )
))}
```

The `NavItem` type gets a `children` field:

```typescript
export type NavItem = {
  href: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  tooltip?: string;
  category?: NavCategory;
  children?: NavSubItem[];  // NEW
};

export type NavSubItem = {
  href: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
};
```

#### UnifiedHubTabs.tsx

Add tab group support:

```tsx
export type UnifiedHubTabsProps = {
  tabs: TabItem[];
  mode?: 'path' | 'query';
  queryParam?: string;
  showGroups?: boolean;  // NEW — render group labels and separators
};
```

When `showGroups` is true and tabs have different `group` values:
1. Render a subtle muted label for each group
2. Add a thin divider or extra spacing between groups
3. First group (primary skill) has no label if it's the hub owner

#### HubOverview.tsx

Filter tabs and render nested skill cards:

```tsx
// Split tabs by nav_mode
const inlineTabs = hubConfig.tabs.filter(t => t.nav_mode === 'inline');
const nestedSkills = hubConfig.tabs
  .filter(t => t.nav_mode === 'nested')
  .reduce(/* group by skill_id */);

// Render inline tabs in tab bar
<UnifiedHubTabs tabs={inlineTabs} showGroups={hasMultipleInlineSkills} />

// Render nested skill navigation cards
{nestedSkills.length > 0 && (
  <NestedSkillCards skills={nestedSkills} hubId={hubId} />
)}
```

### 10. Nested Skill Layout

Each nested skill's layout at `/{hubId}/{skillId}/layout.tsx` wraps its pages with:
1. A breadcrumb: `Hub Name > Skill Name`
2. The skill's own tab bar (its contributed pages)
3. The hub's visual theme (consistent styling)

Currently, extension skill layouts are passthrough (`<>{children}</>`). They need to be updated to render their own tab bar sourced from the assembled hub registry.

A shared `NestedSkillLayout` component handles this:

```tsx
// src/dashboard/components/plugin/NestedSkillLayout.tsx
export function NestedSkillLayout({ hubId, skillId, children }: Props) {
  const hubConfig = getAssembledHub(hubId);
  const skillTabs = hubConfig.tabs.filter(t => t.skill === skillId && t.nav_mode === 'nested');

  return (
    <>
      <Breadcrumb hub={hubConfig.title} skill={skillTabs[0]?.skill_title} />
      <UnifiedHubTabs tabs={skillTabs} />
      {children}
    </>
  );
}
```

Extension skill layouts are updated during mount to use this component instead of passthrough.

## Consequences

### Positive

1. **Tab bar manageable** — Max 9 tabs per page (down from 21)
2. **Sidebar manageable** — 14 items collapsed, ~32 expanded with collapsible groups
3. **Self-contained** — Each skill declares its own `nav_mode` in augur.yaml, no central config
4. **Backward compatible** — Default `inline` preserves current behavior for all existing skills
5. **No routing changes** — Nested skills already use `/{hubId}/{skillId}/` URL pattern
6. **Progressive disclosure** — Hub overview shows essential inline tabs; large workflows one click deeper
7. **Portable** — Moving a skill between bundles doesn't change its nav_mode; it re-groups automatically

### Negative

1. **Two navigation levels** — Users must learn that some skills are sub-items, others are tabs
2. **Hub overview complexity** — HubOverview must handle 3 scenarios (all inline, mixed, all nested)
3. **13 augur.yaml edits** — Each recommended nested skill needs `nav_mode: nested` added
4. **Sidebar animation** — Collapsible groups need smooth expand/collapse transitions
5. **Nested skill layouts** — Extension skill layouts must be updated from passthrough to NestedSkillLayout

### Neutral

1. URL structure unchanged — `/{hubId}/` and `/{hubId}/{skillId}/{pageId}/` already exist
2. Mobile nav follows desktop pattern (collapsible groups in hamburger menu)
3. Favorites system works with both hub-level and skill-level items
4. MCP context routing unchanged — nested skill pages already use `focus-context`
5. Overview widget system unchanged — widgets render on hub overview regardless of nav_mode

## Implementation Order

```
Phase 1: Schema & Types (no runtime changes)
├── Step 1.1: Add nav_mode to DashboardYaml type in lib/plugin-schema/types.ts
├── Step 1.2: Add children to PluginNavItem type in lib/tabs/types.ts
├── Step 1.3: Add PluginNavSubItem type to lib/tabs/types.ts
├── Step 1.4: Add group/groupLabel to TabItem type in lib/tabs/types.ts
└── Step 1.5: Extend AssembledHub tab entries with nav_mode, skill_title, skill_icon

Phase 2: Build Pipeline (depends on Phase 1)
├── Step 2.1: Update scanSkillConfigs() in scanner.ts to read nav_mode from augur.yaml
├── Step 2.2: Update assembleHubs() to tag tabs with nav_mode and skill metadata
├── Step 2.3: Update generate-tab-registry.ts to split tabs by nav_mode
├── Step 2.4: Update generate-tab-registry.ts to output children[] on pluginNavItems
└── Step 2.5: Update generate-tab-registry.ts to add group/groupLabel to inline tabs

Phase 3: augur.yaml Updates (PARALLEL, depends on Phase 2)
├── Step 3.1: Add nav_mode: nested to 13 skills (content, growth, knowledge, mcp-app-factory,
│             install→keep inline, scraper, apple, eisenhower, google-workspace, organizer,
│             project-dev, wealth, client-ai-consulting, client-smb-design,
│             client-terminal-automation)
└── Step 3.2: Run build to verify all hubs assemble correctly with new nav_mode values

Phase 4: Sidebar Rendering (depends on Phase 2)
├── Step 4.1: Add NavSubItem type and children to NavItem in navigation.ts
├── Step 4.2: Update pluginToNavItem() to include children from pluginNavItems
├── Step 4.3: Create CollapsibleNavGroup component in SidebarNav.tsx
├── Step 4.4: Update SidebarNav to render two-level tree (flat items + collapsible groups)
└── Step 4.5: Add expand/collapse state to localStorage (augur:sidebar-expanded:v1)

Phase 5: Hub Overview Adaptation (depends on Phases 3-4)
├── Step 5.1: Update HubOverview to filter tabs by nav_mode (inline only)
├── Step 5.2: Create NestedSkillCards component for linking to nested skills
├── Step 5.3: Handle Scenario C (all nested) — render landing page with cards, no tabs
└── Step 5.4: Update assembled-hubs.json consumer to respect nav_mode

Phase 6: Tab Grouping (depends on Phase 5)
├── Step 6.1: Update UnifiedHubTabs to accept showGroups prop
├── Step 6.2: Add visual separators between tab groups (when group values differ)
└── Step 6.3: Add muted skill name labels for multi-group tab bars

Phase 7: Nested Skill Layout (depends on Phases 3-4)
├── Step 7.1: Create NestedSkillLayout component (breadcrumb + own tab bar)
├── Step 7.2: Update mount-plugins to generate NestedSkillLayout wrapper for nested skills
└── Step 7.3: Add breadcrumb component (Hub > Skill > Page)

Phase 8: Verification (depends on all)
├── Step 8.1: npm run build passes
├── Step 8.2: All 14 hubs render correctly in browser
├── Step 8.3: Nested skills navigable from sidebar sub-items
├── Step 8.4: Inline tabs ≤ 10 for every hub
├── Step 8.5: Collapsible sidebar groups work (expand, collapse, persist state)
├── Step 8.6: Tab group labels render for multi-inline-skill hubs
├── Step 8.7: Nested skill breadcrumbs render correctly
└── Step 8.8: Plugin lint passes
```

## Alternatives Considered

### Alternative 1: Automatic Promotion by Page Count

Auto-promote skills with 4+ pages to sidebar sub-items. No `nav_mode` field needed — the build counts pages and decides.

**Rejected because**: Magic thresholds are fragile and unpredictable. A skill with exactly 4 pages could flip between inline and nested on different builds if a page is added/removed. Skill authors can't predict or control their navigation placement. "Self-contained" means the skill declares its intent, not that the build infers it.

### Alternative 2: Tab Sub-Grouping Only (No Sidebar Changes)

Keep 14 flat sidebar items. Add visual tab groups within the tab bar, grouped by contributing skill. A 21-tab bar becomes 4 visual groups.

**Rejected because**: A 21-tab bar with group labels is still overwhelming — horizontal overflow is the core UX problem, and visual grouping doesn't reduce the item count. Users still scroll to find tabs. The conceptual issue of unrelated skills sharing a flat namespace isn't solved by cosmetic grouping alone.

### Alternative 3: Overflow Dropdown / "More" Menu

Replace horizontal tab overflow with a dropdown "more tabs" menu that appears when tabs exceed a threshold.

**Rejected because**: Hides content behind a menu, making tabs harder to discover. Doesn't solve the conceptual problem of unrelated workflows in a flat list. It's a technical patch for what's fundamentally a UX navigation design problem.

### Alternative 4: Return to Per-Skill Sidebar with Collapsible Bundles

Go back to 40 sidebar items but make bundle groups collapsible (one entry per skill, grouped under bundle headers).

**Rejected because**: Collapsed state still shows 14+ bundle headers. Expanded state shows 40+ items, many with only 1-2 pages. Small skills waste sidebar space as full entries. The `nav_mode: nested` approach is more surgical — only skills that need promotion get sidebar entries.

## References

- [ADR-128: Contribution-Based Hub Assembly](ADR-128-contribution-based-hub-assembly.md) — Current hub grouping model
- [ADR-109: Filesystem-Driven Dashboard](ADR-109-filesystem-driven-dashboard.md) — Self-contained navigation principles
- [ADR-058: Dynamic Plugin Navigation](ADR-058-dynamic-plugin-navigation.md) — Generated nav from plugins
- `src/dashboard/components/SidebarNav.tsx` — Sidebar renderer
- `src/dashboard/components/UnifiedHubTabs.tsx` — Tab bar renderer
- `src/dashboard/lib/navigation.ts` — Nav section assembly
- `src/dashboard/lib/tabs/types.ts` — PluginNavItem, TabItem types
- `src/dashboard/lib/plugin-discovery/scanner.ts` — Plugin scanning / hub assembly
- `src/dashboard/scripts/generate-tab-registry.ts` — Build-time registry generation
- `src/dashboard/components/plugin/HubOverview.tsx` — Hub overview page component

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-136: Adaptive Navigation — Nested Skill Promotion**.

Read the full ADR: `docs/decisions/ADR-136-adaptive-navigation-nested-skill-promotion.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-136-adaptive-nav", description="Implementing ADR-136: Adaptive Navigation — Nested Skill Promotion")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-136-adaptive-nav", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-136 team.
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

**Team name**: `adr-136-adaptive-nav`

#### Phase 1: Schema & Types
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Add `nav_mode?: 'inline' \| 'nested' \| 'hidden'` to `DashboardYaml` interface. Add `nav_mode`, `skill_title`, `skill_icon` to the tab entry type within `AssembledHub`. | `src/dashboard/lib/plugin-schema/types.ts` |
| 1.2 | developer | medium | Add `children?: PluginNavSubItem[]` to `PluginNavItem`. Create `PluginNavSubItem` type with `{ skillId, label, icon, href, pageCount }`. Add `group?: string` and `groupLabel?: string` to `TabItem`. | `src/dashboard/lib/tabs/types.ts` |

#### Phase 2: Build Pipeline (depends on Phase 1)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Update `scanSkillConfigs()` in `scanner.ts` to read `nav_mode` from augur.yaml (default `'inline'` if absent). Pass through to `SkillConfig`. | `src/dashboard/lib/plugin-discovery/scanner.ts`, `src/dashboard/lib/plugin-discovery/types.ts` |
| 2.2 | developer | high | Update `assembleHubs()` in `scanner.ts`: tag each tab entry with `nav_mode`, `skill_title` (from the contributing skill's hub title or skill name), and `skill_icon`. Write these into `assembled_hubs.json`. | `src/dashboard/lib/plugin-discovery/scanner.ts` |
| 2.3 | developer | high | Update `generate-tab-registry.ts`: (1) For each hub, split tabs into inline vs nested based on `nav_mode`. (2) Only inline tabs go into the hub's `pluginTabRegistry` entry. (3) Nested tabs get separate per-skill entries. (4) Generate `children[]` on each `pluginNavItems` entry for hubs with nested skills. (5) Add `group` and `groupLabel` to inline tabs when multiple inline skills contribute. | `src/dashboard/scripts/generate-tab-registry.ts` |

#### Phase 3: augur.yaml Updates (PARALLEL, depends on Phase 2)
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | low | Add `nav_mode: nested` to 13 augur.yaml files: `plugins/career/skills/content/augur.yaml`, `plugins/career/skills/growth/augur.yaml`, `plugins/ai/skills/knowledge/augur.yaml`, `plugins/ai/skills/mcp-app-factory/augur.yaml`, `plugins/ai/skills/scraper/augur.yaml`, `plugins/productivity/skills/apple/augur.yaml`, `plugins/productivity/skills/eisenhower/augur.yaml`, `plugins/productivity/skills/google-workspace/augur.yaml`, `plugins/productivity/skills/organizer/augur.yaml`, `plugins/professional/skills/project-dev/augur.yaml`, `plugins/finance/skills/wealth/augur.yaml`, `plugins/consulting/skills/client-ai-consulting/augur.yaml`, `plugins/consulting/skills/client-smb-design/augur.yaml`, `plugins/consulting/skills/client-terminal-automation/augur.yaml`. | 13 augur.yaml files |
| 3.2 | developer | low | Add `nav_mode: hidden` to backend-only skills that currently have no tabs: `plugins/observability/skills/metrics/augur.yaml`, `plugins/admin/skills/channels/augur.yaml`, `plugins/admin/skills/renderer/augur.yaml`. Run build scripts to verify assembly. | 3 augur.yaml files |

#### Phase 4: Sidebar Rendering (depends on Phase 2)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | frontend | medium | In `navigation.ts`: (1) Add `NavSubItem` type with `{ href, label, icon }`. (2) Add `children?: NavSubItem[]` to `NavItem`. (3) Update `pluginToNavItem()` to include `children` by mapping `PluginNavItem.children` to resolved icon sub-items. | `src/dashboard/lib/navigation.ts` |
| 4.2 | frontend | high | In `SidebarNav.tsx`: (1) Create `CollapsibleNavGroup` component that renders a hub label with expand/collapse chevron, and sub-items when expanded. (2) Update the main render loop: if a NavItem has `children.length > 0`, render it as a `CollapsibleNavGroup`; otherwise render as a flat `NavLink`. (3) Add "Overview" as auto-generated first sub-item (links to hub route). (4) Store expand/collapse state in localStorage key `augur:sidebar-expanded:v1`. (5) Auto-expand the group containing the active route. | `src/dashboard/components/SidebarNav.tsx` |

#### Phase 5: Hub Overview Adaptation (depends on Phases 3-4)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | frontend | high | In `HubOverview.tsx`: (1) Read assembled hub config and filter tabs to inline-only (where `nav_mode !== 'nested'` and `nav_mode !== 'hidden'`). (2) Pass only inline tabs to `UnifiedHubTabs`. (3) Collect nested skills (group tabs by `skill` where `nav_mode === 'nested'`). (4) Render a "More in this hub" section below widgets with navigation cards for each nested skill (title, icon, page count, link). (5) Handle the all-nested case: no tab bar, just hub header + widgets + skill cards. | `src/dashboard/components/plugin/HubOverview.tsx` |
| 5.2 | frontend | medium | Create `NestedSkillCards` component: renders a grid of cards for nested skills. Each card shows skill icon, title, page count, and links to `/{hubId}/{skillId}/`. Uses GlassCard styling consistent with the hub overview. | `src/dashboard/components/plugin/NestedSkillCards.tsx` |

#### Phase 6: Tab Grouping (depends on Phase 5)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 6.1 | frontend | medium | Update `UnifiedHubTabs.tsx`: (1) Add `showGroups?: boolean` prop. (2) When `showGroups` is true and tabs have different `group` values, render a thin divider between groups and an optional muted label showing the group name. (3) Group order: primary skill's group first, then alphabetical by group name. | `src/dashboard/components/UnifiedHubTabs.tsx` |

#### Phase 7: Nested Skill Layout (depends on Phases 3-4)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 7.1 | frontend | high | Create `NestedSkillLayout` component: (1) Reads assembled hub config for the current hubId + skillId. (2) Filters tabs for this skill only. (3) Renders breadcrumb (`Hub > Skill`). (4) Renders own `UnifiedHubTabs` with skill-scoped tabs. (5) Renders `{children}`. | `src/dashboard/components/plugin/NestedSkillLayout.tsx` |
| 7.2 | developer | medium | Update `mount-plugins.ts`: for skills with `nav_mode: nested`, generate layout.tsx files that wrap content with `<NestedSkillLayout hubId="..." skillId="...">`. Replace existing passthrough layouts (`<>{children}</>`) for nested skills only. | `src/dashboard/scripts/mount-plugins.ts` |

#### Final Phase: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 8.1 | validator | low | Run `npm run build` in `src/dashboard/` — must pass cleanly |
| 8.2 | validator | medium | Browser verification: navigate to each of the 14 hub overview pages. Verify inline tabs ≤ 10 for career (9), ai (8), professional (8). Verify nested skill cards appear. |
| 8.3 | validator | medium | Browser verification: click nested skill sidebar sub-items. Verify breadcrumb, own tab bar, and pages render. Test at least: career/content, ai/knowledge, productivity/apple. |
| 8.4 | validator | low | Verify sidebar: collapsed shows 14 items. Expand career, ai, productivity — verify sub-items appear. Verify expand/collapse persists on page reload. |
| 8.5 | validator | low | Run plugin lint: `python3 src/scripts/plugin-lint.py --ci` — all skills pass |
| 8.6 | architect | medium | Verify ADR intent: no tab bar exceeds 10 items, sidebar expanded doesn't exceed 35 items, all nested skills accessible from sidebar, nav_mode declarations match recommendation table |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`npm run build`)
- [ ] No hub has more than 10 inline tabs
- [ ] Sidebar shows 14 items collapsed, ~32 expanded
- [ ] Collapsible groups expand/collapse with state persistence
- [ ] Nested skills have own tab bar and breadcrumb
- [ ] Tab groups render visual separators for multi-inline-skill hubs
- [ ] All 13 nested skills navigable from sidebar sub-items
- [ ] Plugin lint passes
- [ ] ADR status updated to "Accepted" or "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-136-adaptive-navigation-nested-skill-promotion.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
