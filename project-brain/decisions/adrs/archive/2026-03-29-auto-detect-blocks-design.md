# Auto-Detect Blocks: metrics-dashboard + card-grid Enhancement

**Date:** 2026-03-29
**Status:** Approved
**Related ADRs:** ADR-491 (Config-Driven Pages), ADR-274 (Auto-Page Capabilities), ADR-273 (Page Consolidation)

## Problem

44 custom TSX pages remain in `skills/dashboard/pages/`. ~20 of them follow two repeating patterns that should be config-driven:

1. **Metrics dashboard** — 3-4 GlassCards, each calling a different MCP tool, displaying formatted stats/badges. (~15 pages, 300-600 lines each)
2. **Item card grid** — list of items from one MCP tool rendered as cards with custom field rendering. (~5 pages, 200-500 lines each)

The existing block types can't express these patterns: `stat-grid` is too simple (no styling, no formatting), `card-grid` exists but requires explicit field mapping that pages don't provide.

## Decision

### 1. New block type: `metrics-dashboard`

A composite block that takes multiple MCP sources and renders each as a styled metrics card.

**YAML usage:**
```yaml
- type: metrics-dashboard
  size: full
  sources:
    - mcp_tool: get-daemon-status
      title: Daemon Status
      icon: Server
      color: emerald
    - mcp_tool: get-self-heal-stats
      title: Self-Heal
      icon: ShieldCheck
      color: purple
```

**Behavior:**
- Fetches all sources in parallel via `useMcpQuery`
- Renders each source as a GlassCard in a responsive grid (2-col desktop, 1-col mobile)
- Auto-detects field types from response and renders formatted stat tiles
- `title`, `icon`, `color` optional per source — auto-derived from tool name if omitted

### 2. Enhanced `card-grid` with auto-detection

The existing `card-grid` block gains convention-based field role detection. No new block type — enhancement to existing.

**YAML usage (unchanged):**
```yaml
- type: card-grid
  mcp_tool: list-career-projects
  size: full
  search:
    enabled: true
```

**Behavior:**
- On first data load, scans field names to assign roles (title, subtitle, badge, timestamp, metric, detail)
- Renders cards with role-aware layout instead of generic field dump
- If explicit field config is provided, it takes precedence over auto-detection
- `search.enabled: true` without `search.fields` searches all string fields

### 3. Shared auto-detection engine

**New file:** `apps/dashboard/lib/blocks/auto-detect.ts`

Pure functions, no React. Usable from any block.

**Exports:**
- `detectFieldRole(key, value)` → FieldRole
- `autoFormat(value, role)` → formatted string
- `detectFields(obj)` → Map of key → FieldRole
- `badgeColor(value)` → semantic color

**Field role conventions (first match wins):**

| Field pattern | Role | Render |
|---|---|---|
| `name`, `title`, `label`, `subject`, `skill` | title | Card heading, bold |
| `description`, `summary`, `detail`, `subtitle` | subtitle | Muted text, truncated |
| `status`, `state`, `phase`, `type`, `category` | badge | Colored badge |
| `*_at`, `*_date`, `created`, `updated`, `timestamp` | timestamp | Relative time |
| `*_percent`, `*_rate`, `ratio`, `*_pct` | metric-pct | Percentage with bar |
| `*_seconds`, `*_ms`, `uptime`, `duration` | duration | Formatted duration |
| `*_bytes`, `*_size`, `*_mb` | size | Formatted size |
| `count`, `total`, `*_count`, `errors`, `warnings` | metric | Number with label |
| `icon`, `emoji` | icon | Left of title |
| Boolean | boolean | Check/X icon |
| Nested object | nested | Collapsed detail section |
| Array | array | Count badge, expandable |
| Long string (>100 chars) | longtext | Truncated with expand |
| Everything else (up to 4) | detail | Key-value pair |

**Badge color conventions:**

| Value pattern | Color |
|---|---|
| `running`, `active`, `success`, `healthy`, `ok`, `true`, `enabled` | green |
| `error`, `failed`, `critical`, `down`, `false` | red |
| `pending`, `warning`, `degraded`, `paused`, `review` | amber |
| `idle`, `unknown`, `disabled`, `stopped` | gray |
| Everything else | blue |

## Implementation

### Files to create
- `apps/dashboard/lib/blocks/auto-detect.ts` — shared detection engine
- `apps/dashboard/components/blocks/types/MetricsDashboardBlock.tsx` — new block

### Files to modify
- `apps/dashboard/lib/blocks/block-resolver.ts` — register `metrics-dashboard`
- `apps/dashboard/lib/blocks/types.ts` — add `"metrics-dashboard"` to BlockType union
- `apps/dashboard/components/blocks/types/CardGridBlock.tsx` — add auto-detection

### Conversion pipeline
After blocks ship, convert ~16 pages from custom TSX to YAML:

**metrics-dashboard conversions (11 pages, ~4,700 lines):**
- command/observe, command/daemon, career/growth, career/project-dev
- brain/books, brain/scraper, life/health, life/wearables
- command/document-extractor, studio/workbench/audit, templates/consulting-template

**card-grid conversions (5 pages, ~1,600 lines):**
- command/updater/plugins, studio/design, studio/page-builder
- studio/workbench, command/system-cleanup

**Estimated impact:** 44 → ~28 custom TSX pages. ~6,300 lines removed.

## Testing

- Each converted page verified by browser navigation — data renders correctly
- Build must pass (`pnpm run build`)
- Auto-detect engine tested via unit tests on `detectFieldRole`, `autoFormat`, `badgeColor`
- No regression in existing `card-grid` consumers — explicit config takes precedence

## Design principles

- **Convention over configuration** — field names determine rendering, zero YAML needed
- **Auto-detect is additive** — explicit config always wins over convention
- **Pure functions** — detection engine has no React, no side effects
- **First match wins** — predictable, not ambiguous
- **No new YAML vocabulary** — `sources[]` is the only new config concept
