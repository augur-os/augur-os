# Page Type Consolidation: 2 Types, 3 Access Tiers

**Date:** 2026-03-31
**Status:** Draft
**Scope:** Dashboard page discovery, storage, navigation, and rendering

## Problem

The dashboard has 3 page types (Custom TSX, Config YAML, Auto-generated) with overlapping behavior and unclear boundaries:

- Config YAML and Auto-pages both render through `ConfigPage` with blocks — same technology, different inputs
- Config YAML pages appear as hub tabs alongside Custom TSX — users can't distinguish them
- Auto-pages are only accessible from `/browse/[skill]` — inconsistent with other pages
- No clear promotion path from "skill exists" to "skill has a good dashboard page"
- Storage is inconsistent: some custom pages live in skill dirs, some in the dashboard plugin

## Design

### 2 Types

| Type | Renderer | Purpose |
|------|----------|---------|
| **Custom TSX** | React component | Rich interactive apps with mutations, charts, domain-specific UI |
| **Config** | `ConfigPage` block renderer | Declarative data views — two sub-modes (explicit YAML, implicit auto-generated) |

### 3 Access Tiers

| Tier | Source | Hub Tabs | Block Picker | Browse | Investment |
|------|--------|----------|-------------|--------|------------|
| **1. Custom TSX** | Hand-built React | Yes | No | Yes | High |
| **2. Config YAML** | Declarative YAML blocks | No | Yes | Yes | Medium |
| **3. Auto-generated** | Runtime from SKILL.md `x-augur-mcp-tools` | No | No | Yes | Zero |

### Storage Rules

| Tier | Location | Rationale |
|------|----------|-----------|
| Custom TSX | `skills/dashboard/pages/{hub}/{skill}/page.tsx` | Centralized in the dashboard plugin — UI is a dashboard concern |
| Config YAML | `skills/{skill}/augur/pages/*.yaml` | Inside the skill — portable, self-contained, follows ADR-163 decentralization |
| Auto-generated | No file — runtime from `SKILL.md` frontmatter | Zero-cost default, no storage overhead |

### Promotion Ladder

```
Every skill starts at Tier 3 (auto-generated, browse-only)
    |
    | Author a YAML config in skills/{skill}/augur/pages/
    v
Tier 2 (appears in block picker panel for users to discover)
    |
    | Build a custom TSX page in skills/dashboard/pages/{hub}/{skill}/
    v
Tier 1 (permanent hub tab — premium navigation real estate)
```

## Changes Required

### 1. Hub tabs become TSX-only

**Current:** Both Custom TSX (`@skill/pages/...`) and Config YAML (`@/lib/configs/...`) appear as hub tabs.

**Target:** Only Custom TSX pages appear as hub tabs. Config YAML pages are removed from hub tab navigation entirely.

**Implementation:**
- Modify `generate-tab-registry.ts` to exclude YAML-sourced pages from `config.tabs`
- YAML pages still get discovered and registered, but placed in the block picker registry instead
- The `PAGES` map in `app/{hub}/[[...slug]]/registry.ts` still contains YAML routes (for direct URL access and block picker rendering) but they don't generate tabs

**Affected pages (26 YAML configs currently in hub tabs):**

| Hub | Pages moving from tabs to block picker |
|-----|----------------------------------------|
| life | attention, eisenhower, health, wealth, wearables, home-automation/scenes, file-manager/organize |
| brain | books, scraper, obsidian/vault, ai/sync, knowledge/index, reading-list (articles, books, notes) |
| career | pipeline, project-dev, smb-client-template (content-pipeline, knowledge) |
| command | daemon (overview, self-heal), observe, document-extractor, updater/plugins |
| studio | (none — already 0 YAML tabs) |
| adaptive | auto-vault-hygiene |
| templates | consulting-template |

**Decision needed:** Some of these (wealth, health, pipeline, eisenhower) are important user-facing pages. They should be promoted to Custom TSX before this migration. Otherwise users lose tab access to pages they currently use.

### 2. Block picker shows YAML config pages

**Current:** The block picker panel (grid icon, top-right) shows "Available Blocks" for adding to widget views.

**Target:** Block picker also shows YAML config pages, grouped by hub, with icons and titles from the YAML frontmatter. Clicking a YAML page in the block picker navigates to it (renders as a full page via ConfigPage).

**Implementation:**
- Add a "PAGES" section to the block picker panel, below "AVAILABLE BLOCKS"
- Source page list from YAML configs discovered at build time
- Each entry shows: icon, title, hub badge
- Click navigates to `/{hub}/{route}` (the YAML page still has a route for direct URL access)

### 3. Auto-generated pages stay browse-only

**Current:** Auto-pages render at `/browse/[skill]` using `buildDefaultPageConfig()`.

**Target:** No change. Auto-pages continue to render at `/browse/[skill]` with smart layout from `x-augur-mcp-tools`. They never appear in hub tabs or block picker.

**Implementation:** No changes needed. Already works this way.

### 4. Storage enforcement

**Current:** Some custom pages live in `skills/{skill}/augur/dashboard/` and some in `skills/dashboard/pages/`. YAML configs generate TSX wrappers in `apps/dashboard/lib/configs/`.

**Target:**
- Custom TSX: ONLY in `skills/dashboard/pages/{hub}/{skill}/page.tsx`
- YAML: ONLY in `skills/{skill}/augur/pages/*.yaml`
- Generated wrappers (`lib/configs/*.tsx`) still needed for URL routing but no longer generate tabs

**Migration:**
- Any custom pages currently in `skills/{skill}/augur/dashboard/` move to `skills/dashboard/pages/{hub}/{skill}/`
- Pre-commit hook or lint rule enforces: no `page.tsx` in `skills/*/augur/dashboard/` (except skills/dashboard itself)

### 5. Priority pages promoted to Custom TSX

Before removing YAML pages from hub tabs, these high-traffic pages should be promoted to Custom TSX:

| Page | Current | Priority | Rationale |
|------|---------|----------|-----------|
| `/life/wealth` | YAML | P1 | Financial dashboard — needs rich progress bars, gain/loss visualization |
| `/life/health` | YAML | P1 | Health tracking — needs interactive elements |
| `/life/eisenhower` | YAML | P2 | Task management — has group_by, quick_add, confirm dialogs |
| `/career/pipeline` | YAML | P1 | Job pipeline — has search, filters, row_actions |
| `/life/attention` | YAML | P2 | Attention triage — interactive sync/resolve actions |
| `/brain/obsidian/vault` | YAML | P2 | Vault browser — search + row_actions |

The remaining 20 YAML pages can move to block picker without promotion — they're lower-traffic or internal tools.

## Architecture

### Page Discovery Flow (after changes)

```
SKILL.md (x-augur-mcp-tools)
    → buildDefaultPageConfig() at runtime
    → /browse/[skill] renders ConfigPage
    → Tier 3: Browse-only

skills/{skill}/augur/pages/*.yaml
    → Discovered at build time by mount-plugins
    → Registered in PAGES map (for URL routing)
    → Listed in block picker registry (for discovery)
    → NOT added to hub tabs
    → Tier 2: Block picker + Browse + Direct URL

skills/dashboard/pages/{hub}/{skill}/page.tsx
    → Discovered at build time by mount-plugins
    → Registered in PAGES map
    → Added to hub tabs (visible or overflow)
    → Tier 1: Hub tabs + Browse + Direct URL
```

### Registry Changes

**`app/{hub}/[[...slug]]/registry.ts`** (auto-generated):
```typescript
// Tier 1: Hub tabs — Custom TSX only
export const PAGES: Record<string, () => Promise<...>> = {
  'venture-augur': () => import('@skill/pages/career/venture-augur/page'),
  'learning/quiz': () => import('@skill/pages/career/learning/quiz/page'),
};

// Tier 2: Block picker pages — YAML configs (still routable via direct URL)
export const CONFIG_PAGES: Record<string, () => Promise<...>> = {
  'pipeline': () => import('@/lib/configs/career-pipeline'),
  'project-dev': () => import('@/lib/configs/career-project-dev'),
};
```

**`lib/tabs/generated-registry.ts`**:
- `tabs` array contains ONLY Custom TSX pages
- New `configPages` array contains YAML config page metadata (title, icon, route) for block picker

### Block Picker Integration

The block picker panel (`HubBlockPicker.tsx` or similar) adds a new section:

```
+----------------------------------+
| ... More                    [X]  |
|                                  |
| AVAILABLE BLOCKS                 |
|   Search blocks...               |
|   Application Trends      [Add]  |
|   Companies               [Add]  |
|                                  |
| SKILL PAGES                      |
|   Pipeline            [Navigate] |
|   Project Dev         [Navigate] |
|   SMB Client          [Navigate] |
+----------------------------------+
```

## Migration Plan (High-Level)

1. **Phase 1:** Promote 6 priority YAML pages to Custom TSX (wealth, health, eisenhower, pipeline, attention, obsidian/vault)
2. **Phase 2:** Modify `generate-tab-registry.ts` to separate TSX tabs from YAML config pages
3. **Phase 3:** Add "Skill Pages" section to block picker panel
4. **Phase 4:** Delete ~6 simple YAML configs that auto-generation fully covers
5. **Phase 5:** Enforce storage rules via lint/pre-commit hook

## Success Criteria

- Hub tabs contain ONLY Custom TSX pages — no YAML config pages
- Block picker panel shows all YAML config pages grouped by hub
- `/browse/[skill]` renders smart auto-pages for all skills with MCP tools
- No duplicate rendering paths — each page has exactly one source of truth
- Storage is consistent: TSX in dashboard plugin, YAML in skill dirs, auto has no files
- Users can still access any page via direct URL regardless of tier

## Widget Consolidation (Option C)

### Problem

The `/view/[id]` widget page is a standalone user-composed dashboard canvas, disconnected from hubs. It has its own sidebar link ("Widgets"), its own storage (`$AUGUR_STATE_DIR/views/{id}.yaml`), and its own editing UI (ViewCanvas + BlockCatalogPanel). Users must navigate away from their hub to compose a custom dashboard.

### Solution: Embed widget canvas in hub overview pages

Each hub overview page (`/life`, `/career`, `/brain`, etc.) gains a "customize" mode where users can add blocks from the block catalog directly to their hub overview.

### What Changes

1. **Hub overview pages become widget canvases** — the existing overview page gets an optional user-block section below the default content
2. **Block picker "Add" buttons work** — clicking "Add" on a block in the block picker panel adds it to the current hub's overview
3. **Per-hub view storage** — each hub gets its own view file (e.g., `views/life-overview.yaml`) storing user-added blocks
4. **Delete standalone widget page** — remove `/view/[id]` route, ViewCanvas standalone page, sidebar "Widgets" link
5. **Keep reusable infrastructure** — ViewCanvas component, BlockCatalogPanel, block drag-drop, view persistence API all get reused, just embedded in hub overviews

### Hub Overview Layout (after change)

```
┌─────────────────────────────────────────┐
│ Hub Header (Life / Career / etc.)       │
├─────────────────────────────────────────┤
│ Tab Navigation                          │
├─────────────────────────────────────────┤
│ Default Overview Content                │
│ (hub-specific summary, if any)          │
├─────────────────────────────────────────┤
│ User Blocks (from block picker)    [+]  │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│ │ Block 1 │ │ Block 2 │ │ Block 3 │   │
│ └─────────┘ └─────────┘ └─────────┘   │
└─────────────────────────────────────────┘
```

### What Gets Deleted

- `apps/dashboard/app/(views)/view/[id]/page.tsx` — standalone view page
- `apps/dashboard/app/(views)/view/[id]/` — entire route directory
- Sidebar "Widgets" nav item in `SidebarNav.tsx`
- View tabs bar (multiple views concept — replaced by per-hub storage)

### What Gets Reused

- `ViewCanvas` component — embedded in hub overview instead of standalone page
- `BlockCatalogPanel` — already accessible via grid icon in hub header
- `view-storage.ts` — persistence layer, adapted for per-hub views
- Block rendering infrastructure — unchanged

## Risks

| Risk | Mitigation |
|------|-----------|
| Removing 26 YAML pages from hub tabs breaks user workflows | Phase 1 promotes high-traffic pages to TSX first |
| Block picker is less discoverable than hub tabs | Block picker already exists and is visible; add count badge |
| Auto-generated pages quality varies by skill | Smart generation from MCP tools covers 80%; YAML override for the rest |
| Storage enforcement breaks existing custom pages in skill dirs | Migration script moves files; pre-commit hook catches regressions |
