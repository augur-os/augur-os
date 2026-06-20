---
status: Implemented
date: '2026-03-12'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- enhanced
- auto
- pages
- runtime
- skill
superseded_by: null
---

# ADR-272: Enhanced Auto-Pages — Runtime Skill Pages from Standard Sources

**Related ADRs**: ADR-406 (Block System UI), ADR-270 (Folder Restructure), ADR-128 (Hub Assembly), ADR-190 (Page Builder)

## Context

~60-70% of Augur's 125 skills have only basic auto-generated pages (a title, state badge, and action card grid). These pages are nearly empty and require custom TSX code to become useful. Meanwhile, custom pages (like Places, Resume, Virtual Doctor) are rich and polished but take significant effort to build.

The dashboard needs a middle layer that makes auto-generated pages genuinely useful without custom code. Post ADR-270, each skill's data is distributed across three external locations (vault, documents, assets) that should be surfaced automatically.

### Three Groups of Dashboard Content

1. **Auto-pages** (this ADR) — Rich, runtime-rendered pages for every skill, derived entirely from augur.yaml + standard data sources. Cover 80% of user needs without custom code.
2. **Widget blocks** — Hub overview pages as ADR-406 seeded views composed of skill-contributed blocks. Replace today's fixed-layout hub overviews.
3. **Custom pages** — Hand-written TSX for the remaining cases that need truly unique UX. Groups 1 and 2 reduce the need for custom pages to a minimum.

## Decision

### D1: Runtime Template Component (`<SkillAutoPage>`)

A single shared `<SkillAutoPage>` component renders at runtime. It fetches the skill's config, scans data sources, resolves MCP tools, and renders standard sections dynamically. The mount copier generates a thin wrapper:

```tsx
'use client';
import { SkillAutoPage } from '@/components/plugin/SkillAutoPage';

export default function Page() {
  return <SkillAutoPage skillId="google-workspace" hubId="productivity" />;
}
```

**Why runtime over build-time:**
- Always current — no rebuild needed when skill data changes
- One component to maintain across 85+ skills
- Custom data sources in augur.yaml resolve at runtime
- Decomposition into blocks for "Customize" is a function call, not a file parse
- Dev-mode toggle works instantly (React conditional)

### D2: Skill Meta API

A single API route (`/api/skill-meta/[skillId]/route.ts`) assembles everything the auto-page needs:

```typescript
interface SkillMeta {
  skill: { id: string; title: string; icon: string; hub: string; state: 'dev' | 'mature' | 'stable' };
  health: { status: 'healthy' | 'degraded' | 'error' | 'unknown'; lastCheck: string; errors24h: number; uptime?: string };
  stats: Array<{ key: string; value: string | number; icon?: string; color?: string }>;
  actions: Array<{ id: string; title: string; description: string; icon?: string; dispatch: string; primary?: boolean }>;
  vaultNotes: Array<{ name: string; modified: string; preview: string }>;
  documents: Array<{ name: string; type: string; size: number; modified: string }>;
  assets: Array<{ name: string; type: string; purpose: string }>;
  dataFiles: Array<{ name: string; type: 'yaml' | 'json' | 'md'; count: number; preview: Array<Record<string, unknown>> }>;
  config: Array<{ key: string; value: unknown; editable: boolean }>;
  mcpTools: Array<{ name: string; description: string; schema: Record<string, unknown> }>;
  customSources: DataSource[];
  _errors: Record<string, { message: string; retryable: boolean }>;
}
```

Data source resolution:

| Section | Source |
|---------|--------|
| Health/Status | MCP tool `get-skill-health` or `/api/{hub}/{skill}/health` if exists |
| Quick Stats | Scan skill's vault data + `augur/data/` for YAML/JSON, extract counts and key values |
| Actions | `augur.yaml` → `contributions.actions[]` |
| Vault Notes | `~/Vault/Augur/{bundle}/{skill}/` — markdown files, user-editable notes and knowledge |
| Documents | `~/Documents/Augur/{bundle}/{skill}/` — PDFs, spreadsheets, images, binary files |
| Assets | `assets/` in skill root — templates, seed data, prompt templates, block templates |
| Data Preview | File listing of `augur/data/` with content preview (legacy, pre-ADR-270) |
| Configuration | `augur.yaml` parsed as key-value pairs |
| MCP Tools | `augur.yaml` → `contributions.mcp_tools[]` with JSON Schema |
| Recent Logs | `~/Library/Logs/Augur/` filtered by skill name |
| Documentation | `SKILL.md` in skill root |

### D3: Section Order and Visibility

| # | Section | Default State | Visibility |
|---|---------|--------------|------------|
| 1 | Health/Status | Expanded | Always |
| 2 | Quick Stats | Expanded | Always (hidden if no data) |
| — | Custom data sources | Expanded | Always (hidden if no data) |
| 3 | Actions | Expanded | Always (hidden if no actions) |
| 4 | Vault Notes | Expanded | Always (hidden if vault dir empty/missing) |
| 5 | Documents | Expanded | Always (hidden if documents dir empty/missing) |
| 6 | Data Preview | Expanded | Always (hidden if no data/ files) |
| 7 | Assets | Collapsed | Dev mode only |
| 8 | Configuration | Collapsed | Always (hidden if no config) |
| 9 | MCP Tools | Collapsed | Dev mode only |
| 10 | Recent Logs | Collapsed | Dev mode only |
| 11 | Documentation | Collapsed | Always (hidden if no SKILL.md) |

### D4: ADR-270 Data Layers

Post ADR-270, each skill's data is distributed across three external locations:

1. **Vault Notes** (`~/Vault/Augur/{bundle}/{skill}/`) — User-created markdown. Auto-page shows recent notes with preview, note count, and "Open in Obsidian/Editor" link.
2. **Documents** (`~/Documents/Augur/{bundle}/{skill}/`) — Binary files. Auto-page shows file listing with type icons, sizes, and "Open in Finder" action.
3. **Assets** (`assets/` in skill root) — Shipped templates and seed data. Auto-page shows as read-only reference. Dev-only: shows which assets have been overridden by vault versions (vault-first lookup order per ADR-270).

### D5: Custom Data Sources

Skills declare additional data in augur.yaml:

```yaml
contributions:
  data_sources:
    - id: inbox-stats
      type: mcp_tool        # mcp_tool | api_route | file
      source: get-inbox-stats
      display: stat-grid     # block type from ADR-406 vocabulary
      title: "Email Stats"
      config:
        refresh: 30000
        fields: [unread, flagged, total]
```

Custom data sources render between Quick Stats and Actions using the matching ADR-406 block type renderer.

### D6: Customize Flow

When user clicks "Customize":

1. API call to `/api/skill-meta/{skillId}/decompose` returns current auto-page as `BlockInstance[]` in ADR-406 format
2. Each visible section maps to a block type (Health → `stat-grid`, Actions → `action-bar`, Vault Notes → `data-list`, Documents → `data-list`, Config → `data-table`, Logs → `activity-feed`, Docs → `markdown`, etc.)
3. Opens page-builder with blocks pre-loaded in **draft state** (no files written)
4. User edits and explicitly clicks Save → codegen writes custom `page.tsx`
5. Custom page replaces auto-page on next build (copier mounts custom one)

**Reset to default**: Deletes the custom `page.tsx`. Next build regenerates thin `<SkillAutoPage>` wrapper.

### D7: Layout Adaptation

- **Pill badges** at top: status, tool count, action count (from Virtual Doctor pattern)
- **Hero action**: If skill has 1-3 actions and one is `primary: true`, that action gets the hero treatment (large card with input + suggested chips). Remaining go to sidebar. If no primary or 4+ actions, all render as equal grid.
- **Data cards**: 1 file = full width, 2 files = 2-col, 3+ = 2-col with "+N more" link
- **Stats grid**: 1-2 stats = 2-col, 3-4 = 4-col, 5+ = scrollable row

Design language borrowed from existing best pages: Places (two-tier stats, colored-border cards, warm cream theme), Resume (asymmetric 2:1 grid, stacked tool list), Virtual Doctor (pill badges, action chips).

### D8: Hub Seeded Views (Group 2)

Hub overview pages become ADR-406 views, auto-seeded from contributing skills. Each skill contributes a `contributions.headline_block` in augur.yaml. Detailed implementation deferred to ADR-406 implementation spec.

## Consequences

### Positive

- 85+ skills get rich pages immediately without custom TSX
- New skills get a useful page on install (zero effort)
- ADR-270 data layers (vault, documents, assets) surfaced automatically
- "Customize" bridges auto-pages into ADR-406 block system — smooth migration path
- Single component to maintain vs. 85+ individual page files

### Negative

- Runtime API call on every skill page mount (mitigated by SWR caching)
- Skill meta API must handle 11+ data sources with partial-failure semantics
- Custom data sources add schema complexity to augur.yaml

### Neutral

- Existing custom pages are unaffected — copier continues to mount them with priority over auto-pages
- Hub overview pages remain as-is until ADR-406 view infrastructure lands

## Alternatives Considered

### Alternative A: Template-at-Build-Time (Static Generation)

Generate full `page.tsx` at build time by reading augur.yaml and scanning data directories. Rejected because: pages are stale until next build, data preview is a snapshot, adding a new action requires rebuild.

### Alternative C: Hybrid — Static Shell + Runtime Widgets

Generate static page shell at build time, each section is a runtime widget. Rejected because: more complex than B (two layers), section ordering requires rebuild, harder to decompose for "Customize" flow.

## References

- Design spec: `docs/superpowers/specs/2026-03-12-enhanced-auto-pages-design.md`
- ADR-406: Block System UI
- ADR-270: Folder Restructure — Layer Separation
- ADR-128: Hub Assembly
- ADR-190: Page Builder

## Error Handling

Partial-success semantics — each section fetched independently with per-section `_errors`:
- augur.yaml malformed → 500 (only total failure)
- MCP server down → Health shows "unavailable", others unaffected
- Log/data directory inaccessible → section hidden
- Custom data source fails → muted error with retry button

## Testing

### Unit Tests
- Section renderers: mock data, empty data, error state (`apps/dashboard/components/plugin/sections/__tests__/`)
- SkillAutoPage: various skill configs (full, minimal, empty, dev mode)

### API Route Tests
- `/api/skill-meta/[skillId]`: real skill fixtures, partial-success scenarios
- `/api/skill-meta/[skillId]/decompose`: ADR-406 BlockInstance schema validation, dev-mode gating

### Integration Tests
- Customize round-trip: decompose → page-builder → save → mount → reset
- Mount copier: thin wrapper generation, custom page priority

## Schema Changes

New optional fields in augur.yaml:
- `contributions.data_sources[]` — custom data source declarations
- `contributions.headline_block` — hub seeded view contribution

TypeScript types in `apps/dashboard/scripts/mount/types.ts`. No migration needed — fields are optional. `auto-yaml-lint` updated to validate when present.

## Accessibility

- Collapsible sections: `<details>`/`<summary>` or `role="region"` with `aria-expanded`
- Pill badges: `aria-label` for screen readers
- Action cards: keyboard-navigable with `tabIndex` and `Enter`/`Space`
- Color never sole indicator — text labels alongside color

## Impact Manifest

```yaml
impact:
  apis_changed:
    - function: assembleAndWriteHubs
      module: apps/dashboard/scripts/mount/copier.ts
      breaking: false  # adds thin wrapper generation, existing behavior preserved
  files_affected:
    - glob: "apps/dashboard/scripts/mount/copier.ts"
    - glob: "apps/dashboard/scripts/mount/types.ts"
    - glob: "plugins/admin/skills/page-builder/augur/lib/codegen.ts"
```

## Implementation Prompt

**Team name**: `adr-272-auto-pages`

### Phase 1: Skill Meta API
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | backend | medium | Create `/api/skill-meta/[skillId]/route.ts` — read augur.yaml, scan vault/documents/assets/data dirs, resolve health, assemble SkillMeta response with partial-error handling | `apps/dashboard/app/api/skill-meta/[skillId]/route.ts` |
| 1.2 | backend | medium | Create `/api/skill-meta/[skillId]/decompose/route.ts` — convert SkillMeta into BlockInstance[] per ADR-406 format | `apps/dashboard/app/api/skill-meta/[skillId]/decompose/route.ts` |
| 1.3 | backend | low | Add DataSource, HeadlineBlock, SkillMeta types to mount types | `apps/dashboard/scripts/mount/types.ts` |

### Phase 2: Section Components
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | frontend | medium | HealthSection — status card with connection state, last check, error count | `apps/dashboard/components/plugin/sections/HealthSection.tsx` |
| 2.2 | frontend | medium | StatsSection — two-tier stat grid (sub-stats + summary row) | `apps/dashboard/components/plugin/sections/StatsSection.tsx` |
| 2.3 | frontend | medium | ActionsSection — hero action with chips + sidebar grid, or equal grid | `apps/dashboard/components/plugin/sections/ActionsSection.tsx` |
| 2.4 | frontend | medium | VaultNotesSection — recent notes list with preview, "Open in Editor" | `apps/dashboard/components/plugin/sections/VaultNotesSection.tsx` |
| 2.5 | frontend | low | DocumentsSection — file listing with type icons, sizes, "Open in Finder" | `apps/dashboard/components/plugin/sections/DocumentsSection.tsx` |
| 2.6 | frontend | low | AssetsSection — read-only template list with override indicators (dev-only) | `apps/dashboard/components/plugin/sections/AssetsSection.tsx` |
| 2.7 | frontend | low | DataPreviewSection — file cards with content preview | `apps/dashboard/components/plugin/sections/DataPreviewSection.tsx` |
| 2.8 | frontend | low | ConfigSection, McpToolsSection, LogsSection, DocsSection — collapsible panels | `apps/dashboard/components/plugin/sections/` |
| 2.9 | frontend | low | CustomSourceSection — render custom data_sources using ADR-406 block type | `apps/dashboard/components/plugin/sections/CustomSourceSection.tsx` |

### Phase 3: Main Component + Copier Integration
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | frontend | high | Create SkillAutoPage.tsx — orchestrator that fetches SkillMeta, renders sections, handles dev-mode, pill badges, Customize button | `apps/dashboard/components/plugin/SkillAutoPage.tsx` |
| 3.2 | backend | medium | Update copier.ts — generate thin `<SkillAutoPage>` wrapper when no custom page.tsx exists | `apps/dashboard/scripts/mount/copier.ts` |
| 3.3 | backend | low | Update page-builder codegen to accept pre-loaded blocks from decompose API | `plugins/admin/skills/page-builder/augur/lib/codegen.ts` |

### Phase 4: Tests
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | tester | medium | Unit tests for all section renderers (mock data, empty, error) | `apps/dashboard/components/plugin/sections/__tests__/` |
| 4.2 | tester | medium | API route tests for skill-meta and decompose | `apps/dashboard/app/api/skill-meta/__tests__/` |
| 4.3 | tester | low | Integration test for customize round-trip | `tests/dashboard/integration/` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | validator | low | Build dashboard (`npm run build`), verify no TypeScript errors |
| V.3 | validator | low | Browser validation — open 3 skill auto-pages, verify sections render |
| V.4 | architect | low | Verify ADR intent matches implementation, all 11 sections work |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass
- [ ] `npm run build` passes
- [ ] 3+ skill auto-pages verified in browser
- [ ] Customize → page-builder round-trip works
- [ ] No orphaned files or broken references
- [ ] ADR status updated to Implemented
