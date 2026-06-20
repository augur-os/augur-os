---
status: Implemented
date: '2026-03-04'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- filesystem
- aligned
- tabs
- restructuring
superseded_by: null
---

# ADR-218: Filesystem-Aligned Tabs Restructuring

## Context

Three parallel structures in Augur are completely misaligned, contradicting the trust principle that everything should be simple and reflect filesystem structure:

1. **URL routes** use `/{hub}/{page}` for owner skills but `/{hub}/{skill}/{page}` for extensions — inconsistent and not derivable from the filesystem.
2. **Plugin filesystem** follows `plugins/{bundle}/skills/{skill}/augur/dashboard/{page}/` — the canonical structure.
3. **Tab configuration** has a dual system: a vestigial `tabs:` block (ignored by the generator) and `contributions.pages` arrays (the real source) in augur.yaml.

### Specific Pain Points

- The `tabs:` block exists in 36 augur.yaml files but the generator (`generate-tab-registry.ts`) never reads it — only `contributions.pages` drives tab generation.
- `contributions.pages` requires explicit listing of every page with computed fields (`href`, `group`, `groupLabel`) — drift-prone boilerplate.
- Hub-owner skills get shortened URLs (`/ai/agents` instead of `/ai/ai_bridge/agents`), breaking filesystem alignment.
- The `dev` hub has 4 working pages but zero `contributions.pages` — uses a hardcoded `dev-subpages.ts` instead.
- `UnifiedHubTabs` (403 lines) implements Level 1/Level 2 group drill-down navigation that adds complexity without proportional value.
- The `order >= 900` magic threshold for overflow tabs is opaque.
- Group labels auto-capitalize skill IDs poorly (`ai_bridge` → "Ai_bridge").
- `tab_scorer.py` falls back to the `tabs:` block when `contributions.pages` is absent, but since the generator ignores `tabs:`, scored pages remain invisible.

## Decision

### 1. Flat Tab Hierarchy

Replace the Level 1 (group buttons) / Level 2 (drill-down) navigation with a simple flat tab bar. Each skill contributes 1-2 visible tabs directly. Remaining tabs go into a "More" dropdown. No grouping or drill-down.

### 2. Kill `tabs:` Block — Single Source of Truth

Remove the legacy `tabs:` block from all augur.yaml files. `contributions.pages` becomes the sole mechanism for tab overrides. A migration script handles the removal across ~36 files.

### 3. Auto-Discover Tabs from Filesystem

Replace explicit page listings with filesystem scanning. The generator walks `plugins/*/skills/*/augur/dashboard/*/page.tsx` to auto-discover pages. Each directory containing `page.tsx` becomes a tab automatically. The `augur.yaml` `contributions.pages` section changes from a full-declaration array to an optional override map:

```yaml
# Old (full declaration array):
contributions:
  pages:
    - id: loops
      label: Loops
      icon: Activity
      href: /observability/daemon/loops
      order: 10
      group: daemon
      state: mature

# New (override map — only specify what differs from auto-defaults):
contributions:
  pages:
    loops:
      icon: Activity
      order: 10
```

Auto-computed defaults: `id` from directory name, `label` from smart titleCase, `href` from `/{hub}/{skill}/{page}`, `order: 50`.

### 4. URLs Always `/{hub}/{skill}/{page}`

All pages mount at `app/{hub}/{skill}/{page}/` — owner skills lose their shortcut. Examples:
- `/observability/observe/sessions` (was `/observability/sessions`)
- `/ai/ai_bridge/agents` (was `/ai/agents`)
- `/observability/daemon/loops` (unchanged — already filesystem-aligned)
- `/dev/advisor/analytics` (unchanged)

No backward-compatibility redirects. Hub overview pages remain at `/{hub}`.

### 5. Max Visible Count for Overflow

Replace the `order >= 900` threshold with a simple `max_visible_tabs` count (default 6, configurable per hub). Tabs sorted by `order`, first N visible, rest overflow.

### 6. Component Changes

**UnifiedHubTabs** (403 → ~80 lines): Remove Level 1/Level 2 group rendering, `group`/`groupLabel` fields, query-param mode. Keep flat tab list, `MoreDropdown`, active tab detection via pathname match.

**TabItem type**: Remove `group` and `groupLabel` fields.

**HubHeaderSection**: Remove `mode` prop pass-through (always path mode now).

### 7. Mount Script Changes

In `mount/discovery.ts`, change `resolveOwnership()` so primary skills get `mountPath: hubId/skill` instead of `mountPath: hubId`. The copier routes root files (`page.tsx`, `layout.tsx`, `loading.tsx`) to `app/{hub}/` and subdirectory pages to `app/{hub}/{skill}/{page}/`.

### 8. Tab Scorer Updates

`tab_scorer.py`: Remove `tabs:` block fallback, read/write overrides in map format, assign sequential order values (10, 20, 30...) instead of the 900+ overflow scheme.

### 9. Dev Hub Fix

Delete `dev-subpages.ts`. Auto-discovery finds the 4 existing pages (`analytics`, `tools`, `audit`, `compliance`) and creates real tabs. Add minimal overrides for icons/order.

## Consequences

### Positive

- Tabs, URLs, and filesystem are fully aligned — users can derive any tab's URL from the plugin directory structure
- Zero-config tab registration — add a `page.tsx` and it appears automatically
- ~320 lines of component code removed (UnifiedHubTabs simplification)
- No more dual `tabs:`/`contributions.pages` confusion
- Dev hub gets real tabs without hardcoded workarounds
- Tab overrides are minimal YAML (only what differs from defaults)

### Negative

- All hub-owner URLs change (e.g., `/ai/agents` → `/ai/ai_bridge/agents`) — any external bookmarks or documentation links break
- ~20-30 hardcoded href references across components need updating
- All augur.yaml files touched by migration (high commit churn)
- `contributions.pages` format changes from array to map — any external tooling reading the old format breaks

### Neutral

- `getHubConfig()` API shape unchanged — consumers don't need rewriting
- Scoring signals and weights in `tab_scorer.py` stay the same
- Sidebar navigation and `PluginNavItem` generation are separate concerns — not affected by this ADR

## Implementation Order

### Phase 1: Migration Script (PIPELINE)
1. Write `scripts/migrate-tabs-to-map.ts` — removes `tabs:` blocks, converts `contributions.pages` to map
2. Run dry-run, verify, run for real
3. Commit augur.yaml changes

### Phase 2: Mount & Generator (PIPELINE)
4. Change `mount/discovery.ts` — owner skills mount at `/{hub}/{skill}/`
5. Update `mount/copier.ts` — root files stay at `app/{hub}/`, subdirs go to `app/{hub}/{skill}/{page}/`
6. Rewrite `generate-tab-registry.ts` — filesystem scanning, smart labels, max_visible_tabs
7. Remove `group`/`groupLabel` from `TabItem` type
8. Run mount + generator, verify output

### Phase 3: Component Simplification (PIPELINE)
9. Rewrite `UnifiedHubTabs.tsx` — flat only, ~80 lines
10. Update `HubHeaderSection.tsx` — remove mode prop
11. Update 3 plugin layouts that bypass HubHeaderSection

### Phase 4: Fixes & Cleanup (PARALLEL)
12. Update `tab_scorer.py` for map format
13. Delete `dev-subpages.ts`, update dev hub overview, add dev skill overrides
14. Update ~20-30 hardcoded href references in plugin source files
15. Update stale `page:` fields in action YAML files

### Phase 5: Verification (PIPELINE)
16. Full rebuild (clean mount + generate)
17. TypeScript build check
18. Visual verification of all hubs
19. Remove migration script and dead code

## Alternatives Considered

### Alternative 1: Incremental Migration

Add filesystem auto-discovery as a fallback to the existing generator. Migrate one hub at a time. Remove legacy code last.

**Rejected**: Two systems coexist during migration, increasing complexity. URL migration is still a big-bang change regardless. The full rewrite is mechanical and lower total risk.

### Alternative 2: Config-Only (Auto-Generate contributions.pages)

Keep the generator as-is but add a preprocessing step that auto-generates `contributions.pages` arrays from filesystem scanning.

**Rejected**: Doesn't fix URLs, doesn't simplify UnifiedHubTabs, doesn't kill the dual system. Papers over the misalignment instead of fixing it.

### Alternative 3: Owner Shortcut URLs (/{hub}/{page})

Keep the current pattern where hub-owner skills get shortened URLs.

**Rejected**: Breaks the core principle of this ADR — filesystem alignment. Users can't derive the URL from the directory path if owner skills are special-cased.

## References

- Design doc: `docs/plans/2026-03-04-filesystem-aligned-tabs-design.md`
- Implementation plan: `docs/plans/2026-03-04-filesystem-aligned-tabs-plan.md`
- ADR-012: Community Package Extraction (plugin mounting)
- ADR-136: Multi-skill tab bars (introduced grouping — now being removed)
- ADR-163: Plugin decentralization
- ADR-187: Explicit hub ownership

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "app/{hub}/{page}/"
      to: "app/{hub}/{ownerSkill}/{page}/"
      scope: "src/dashboard/app/*/page.tsx (owner skill pages)"
    - from: "contributions.pages array format"
      to: "contributions.pages map format"
      scope: "plugins/*/skills/*/augur.yaml"
  apis_changed:
    - function: resolveOwnership
      module: src/dashboard/scripts/mount/discovery.ts
      breaking: true
    - function: UnifiedHubTabs
      module: src/dashboard/components/UnifiedHubTabs.tsx
      breaking: true  # Props changed: mode/queryParam removed
  patterns_deprecated:
    - grep: "^tabs:"
      replacement: "Remove entirely — use contributions.pages map for overrides"
    - grep: "group.*groupLabel"
      replacement: "Remove — flat tabs only, no grouping"
    - grep: 'mode.*"query"'
      replacement: "Remove — always path mode"
    - grep: "order.*9[0-9][0-9]"
      replacement: "Use sequential order values; overflow determined by max_visible_tabs"
    - grep: "DEV_SUBPAGES|dev-subpages"
      replacement: "Delete — auto-discovered from filesystem"
  files_affected:
    - glob: "plugins/*/skills/*/augur.yaml"
    - glob: "src/dashboard/components/UnifiedHubTabs.tsx"
    - glob: "src/dashboard/scripts/generate-tab-registry.ts"
    - glob: "src/dashboard/scripts/mount/discovery.ts"
    - glob: "src/dashboard/scripts/mount/copier.ts"
    - glob: "src/dashboard/lib/tabs/types.ts"
    - glob: "plugins/admin/skills/system-cleanup/scripts/tab_scorer.py"
    - glob: "plugins/dev/skills/devops/augur/dashboard/dev-subpages.ts"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using the implementation plan.

**Team name**: `adr-218-filesystem-tabs`

### Phase 1: Migration Script
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Write augur.yaml migration script (remove tabs: blocks, convert contributions.pages to map) | `scripts/migrate-tabs-to-map.ts` |
| 1.2 | developer | low | Run migration dry-run, verify, execute | `plugins/*/skills/*/augur.yaml` |

### Phase 2: Mount & Generator
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | high | Change resolveOwnership — owner skills mount at /{hub}/{skill}/ | `src/dashboard/scripts/mount/discovery.ts` |
| 2.2 | developer | high | Update copier — root files at app/{hub}/, subdirs at app/{hub}/{skill}/{page}/ | `src/dashboard/scripts/mount/copier.ts` |
| 2.3 | developer | high | Rewrite generator — filesystem scanning, smart labels, max_visible_tabs | `src/dashboard/scripts/generate-tab-registry.ts`, `src/dashboard/lib/plugin-discovery/scanner.ts` |
| 2.4 | developer | low | Remove group/groupLabel from TabItem type | `src/dashboard/lib/tabs/types.ts` |

### Phase 3: Component Simplification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Rewrite UnifiedHubTabs — flat only (~80 lines) | `src/dashboard/components/UnifiedHubTabs.tsx` |
| 3.2 | developer | low | Update HubHeaderSection — remove mode prop | `src/dashboard/components/HubHeaderSection.tsx` |
| 3.3 | developer | low | Update 4 direct UnifiedHubTabs consumers | plugin layouts + settings/layout.tsx |

### Phase 4: Fixes & Cleanup
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Update tab_scorer.py for map format | `plugins/admin/skills/system-cleanup/scripts/tab_scorer.py` |
| 4.2 | developer | low | Delete dev-subpages.ts, update dev hub, add overrides | `plugins/dev/skills/*/augur.yaml`, `plugins/dev/skills/devops/augur/dashboard/` |
| 4.3 | developer | medium | Update ~30 hardcoded href references | plugin source `*.tsx` files |
| 4.4 | developer | low | Update stale page: fields in action YAMLs | `plugins/*/skills/*/augur/data/actions/*.yaml` |

### Final Phase: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Clean rebuild: mount-plugins + generate-tab-registry |
| V.2 | validator | medium | TypeScript build check (npx tsc --noEmit) |
| V.3 | validator | medium | Visual verification of all hubs via browser |
| V.4 | validator | low | Remove migration script and dead grouping code |

### Completion Criteria
- [ ] All hrefs follow `/{hub}/{skill}/{page}` pattern
- [ ] Zero `tabs:` blocks remain in any augur.yaml
- [ ] `contributions.pages` uses map format with overrides only
- [ ] UnifiedHubTabs has no grouping logic
- [ ] Dev hub shows auto-discovered tabs
- [ ] Tab scorer works with map format
- [ ] TypeScript builds clean
- [ ] All hub tab bars render correctly
- [ ] ADR-218 status updated to Implemented
