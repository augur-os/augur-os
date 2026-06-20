---
title: Track 3b — Dashboard Hub-Routing Redesign (Design)
date: 2026-04-29
status: proposed
scope: design
related:
  - 2026-04-28-cross-client-bundle-architecture-design.md
  - 2026-04-28-cross-client-bundle-migration-design.md
  - 2026-04-29-track2-vault-server-split-design.md
---

# Track 3b — Dashboard Hub-Routing Redesign (Design)

## Purpose

Layer 4 of the cross-client bundle architecture migration described Track 3b conceptually as "removes the dashboard's structural assumption that `lifestyle` and `apple` are first-class hub URL prefixes" and explicitly deferred the design to its own spec. The dashboard today hardcodes specific hub names (`lifestyle`, `apple`) across 50+ files instead of reading hub assignments from skill metadata. This spec defines the canonical hub model, the metadata pipeline, and the migration shape that retires those hardcodes.

Track 3b is independent of Track 3a per the migration spec; both can execute in parallel.

## Decisions

- **Hub model: flat list of hub names with central metadata.** `x-augur-hub` (already in SKILL.md frontmatter, per CLAUDE.md rule #13) remains the per-skill hub assignment. Hub-level metadata (icon, label, category, layout, ordering) lives in `config/system/hubs.yaml` — the canonical source-of-truth.
- **Skill-level metadata stays in SKILL.md.** Per CLAUDE.md rule #13 "Hub ownership follows skill metadata. Do not add skill-specific hub data to central config." `hubs.yaml` describes hubs, not skills.
- **Hub metadata pipeline: YAML source + generated TS derivative.** `config/system/hubs.yaml` is hand-edited; a Python scanner emits `apps/dashboard/lib/hubs/generated.ts` (typed `HUBS` map). Matches the existing pattern of `apps/dashboard/lib/plugin-runtime/assembled-hubs.json` and `apps/dashboard/lib/tabs/generated-registry.ts` being auto-generated artifacts.
- **The legacy `{vertical/horizontal/factory}` taxonomy is retired.** It was a 3-axis layout map in `dashboard_generator.py` not reflected in `x-augur-hub` and not documented in CLAUDE.md. Replaced by a single `category` field on each hub in `hubs.yaml` (values: `personal`, `knowledge`, `work`, `system`, `creative`, `meta`).
- **5 PRs phased by surface boundary.** Infrastructure → dashboard production → scanner templates → workflow tools → cleanup + ADR. Each PR has a distinct verification gate (browser load / generate-a-skill smoke / workflow execution).
- **Validation gate: every `x-augur-hub` must reference a hub in `hubs.yaml`.** New unit test enforces this; CI fails on orphan references.
- **Track 3b retires no architecture-test allowlist entries.** Allowlist is about cross-skill Python imports; this track touches dashboard hub routing.

## Architecture

### Hub schema (`config/system/hubs.yaml`)

```yaml
# Augur dashboard hub registry.
# Source-of-truth for hub-level metadata. Hand-edited.
# Read by:
#   - dashboard_generator.py — to emit apps/dashboard/lib/hubs/generated.ts
#   - skill scanner          — to validate x-augur-hub references
#
# Per-skill hub assignment lives in each skill's SKILL.md frontmatter
# (`x-augur-hub: <id>`). This file describes hubs themselves.

hubs:
  - id: life
    label: Life
    subtitle: Personal operating system surfaces
    icon: Home
    category: personal
    layout: masonry
    order: 1

  - id: brain
    label: Brain
    subtitle: Knowledge, memory, and learning
    icon: Brain
    category: knowledge
    layout: masonry
    order: 2

  - id: career
    label: Career
    subtitle: Professional growth and outreach
    icon: Briefcase
    category: work
    layout: masonry
    order: 3

  - id: command
    label: Command
    subtitle: Operational tooling and platform admin
    icon: Terminal
    category: system
    layout: masonry
    order: 4

  - id: studio
    label: Studio
    subtitle: Content, creative, and production
    icon: Palette
    category: creative
    layout: masonry
    order: 5

  - id: adaptive
    label: Adaptive
    subtitle: Self-improving loops and meta-tooling
    icon: Activity
    category: meta
    layout: masonry
    order: 6
    nav_hidden: true  # current state — adaptive is meta-level
```

Field semantics:
- `id` (string, required, unique) — slug used in `x-augur-hub` and URL routes (`/{id}`)
- `label` (string, required) — human-readable display name in nav, headers
- `subtitle` (string, optional) — short description shown in hub overview
- `icon` (string, required) — Lucide icon name; rendered in nav + hub headers
- `category` (string, required, enum) — broad grouping; replaces legacy `{vertical/horizontal/factory}` map. One of: `personal`, `knowledge`, `work`, `system`, `creative`, `meta`
- `layout` (string, required, enum) — overview layout. Currently only `masonry` is used; field exists for future extensibility (`grid`, `list`, etc.)
- `order` (integer, required, unique) — sort order in nav
- `nav_hidden` (bool, optional, default `false`) — hub URL exists but doesn't appear in primary nav
- `search.enabled` (bool, optional, default `true`) — overview-page search behavior

### Generated TypeScript artifact (`apps/dashboard/lib/hubs/generated.ts`)

```typescript
// Auto-generated from config/system/hubs.yaml by dashboard_generator.py.
// Do not edit by hand. Run `pnpm --filter dashboard build` to regenerate.

export interface Hub {
  id: string;
  label: string;
  subtitle?: string;
  icon: string;
  category: "personal" | "knowledge" | "work" | "system" | "creative" | "meta";
  layout: "masonry";
  order: number;
  navHidden: boolean;
  search: { enabled: boolean };
}

export const HUBS: Record<string, Hub> = {
  life: { id: "life", label: "Life", icon: "Home", category: "personal", layout: "masonry", order: 1, navHidden: false, search: { enabled: true } },
  // ... etc.
};

export const HUBS_BY_CATEGORY: Record<string, Hub[]> = { /* derived */ };
export const NAV_VISIBLE_HUBS: Hub[] = Object.values(HUBS).filter(h => !h.navHidden).sort((a, b) => a.order - b.order);
```

Consumers import from `@/lib/hubs/generated` — the typed `HUBS` map replaces all hardcoded string literals.

### Generation pipeline

The Python scanner sequence runs as part of `pnpm --filter dashboard build`:

1. **Read `config/system/hubs.yaml`** — load + validate against schema.
2. **Scan all SKILL.md files** — collect `x-augur-hub` values; group skills under their declared hub.
3. **Validate orphan-free** — every `x-augur-hub` must reference a hub `id` in `hubs.yaml`. Error with file path + value if not.
4. **Emit `apps/dashboard/lib/hubs/generated.ts`** — typed `HUBS` map.
5. **Emit `apps/dashboard/lib/plugin-runtime/assembled-hubs.json`** (existing artifact) — regenerated to consume `HUBS`.
6. **Emit `apps/dashboard/lib/tabs/generated-registry.ts`** (existing artifact) — regenerated.

Generation is idempotent: running twice with no input change produces no diff.

### Migration shape

5 PRs, each phased by file-structure boundary:

#### PR 1 — Infrastructure

Adds `config/system/hubs.yaml`, the scanner extension that emits `apps/dashboard/lib/hubs/generated.ts`, and the orphan-free validator. Updates `dashboard_generator.py` to consume the new metadata source. No production-code consumers updated yet — `generated.ts` exists but isn't imported anywhere besides its own type smoke test. Existing `assembled-hubs.json` regenerated to verify the new pipeline reproduces current state byte-equal where possible.

Verification:
- `pnpm --filter dashboard build` succeeds
- `tests/cli/test_hub_metadata.py` passes (orphan check + schema validation)
- Browser load: dashboard renders unchanged (no consumer changes yet)

#### PR 2 — Dashboard production code

Migrates 8 files in `apps/dashboard/{app,lib,features}/` from hardcoded `"lifestyle"` / `"apple"` literals to `HUBS[hubId]` lookups via `@/lib/hubs/generated`:

- `apps/dashboard/app/actions.ts`
- `apps/dashboard/lib/api/record-helpers.ts`
- `apps/dashboard/lib/help.ts`
- `apps/dashboard/lib/paths.ts`
- `apps/dashboard/lib/server/voice-memos.ts`
- `apps/dashboard/lib/browse/types.ts`
- `apps/dashboard/features/components/CalendarWidget.tsx`
- `apps/dashboard/features/extensions-bundles/plugins/plugin-dialogs.tsx`

Each replacement preserves behavior: a hardcoded `"lifestyle"` becomes `HUBS["life"].id` or similar typed reference. Where the hardcode was a fallback ("if no hub specified, use lifestyle"), the fallback is replaced with `Object.values(HUBS).find(h => h.category === "personal")` or an explicit error if no fallback is appropriate.

Verification:
- All affected pages load in browser (Chrome MCP or screenshot)
- Settings UI renders correctly
- Calendar widget renders correctly
- Production tests pass

#### PR 3 — Scanner templates

Migrates ~10 files in the skill-import pipeline so newly-generated skills don't hardcode `lifestyle`:

- `scripts/skill-scripts/skill_generation/blueprint_generator.py`
- `scripts/skill-scripts/skill_generation/placement_analyzer.py`
- `scripts/skill-scripts/skill_generation/route_templates.py`
- `scripts/skill-scripts/skill_generation/productization_plan_generator.py`
- `scripts/skill-scripts/skill_generation/_hardening_implementation.py`
- `scripts/skill-scripts/skill_generation/import_stages/blueprint.py`
- `scripts/skill-scripts/skill_importer.py`
- `scripts/skill-scripts/skill_import.py`
- `scripts/skill-scripts/import_codegen.py`
- `scripts/skill-scripts/generate_skill_ui.py`

Each template now reads `config/system/hubs.yaml` and emits hub-neutral code. Where the template needs a default hub for a new skill, it picks based on the skill's declared `x-augur-type` or falls back to user prompt — never hardcoded to `lifestyle`.

Verification:
- "Generate a new skill" smoke test produces a skill with a valid `x-augur-hub`
- Existing scanner output unchanged (idempotency check)

#### PR 4 — Workflow tools

Migrates ~5 files in workflow / MCP tools that case-by-case reference hub names:

- `apps/dashboard/scripts/skill-scripts/tools_plugin.py`
- `apps/dashboard/scripts/skill-scripts/tools_workflow.py`
- `apps/dashboard/scripts/skill-scripts/workflow/engine.py`
- `apps/dashboard/scripts/skill-scripts/workflow/state_manager.py`
- `apps/dashboard/scripts/skill-scripts/scoring/user_research.py`

Some references may be domain logic that legitimately needs a specific hub (e.g., user-research scoring rules tied to a hub). Each site is reviewed: if the reference is templating that should be metadata-driven, migrate; if it's intentional domain logic, leave + add a comment explaining why.

Verification:
- Workflow execution test passes
- MCP tool invocations against the affected tools work end-to-end

#### PR 5 — Cleanup + ADR

Final pass:
- Delete the legacy `{vertical: lifestyle, horizontal: hands, factory: agents}` map from `dashboard_generator.py` and `comprehensive_dashboard_generator.py`
- Audit grep: zero remaining `"lifestyle"` / `"apple"` / `"obsidian"` / `"file-manager"` / `"ingest"` / `"vertical"` / `"horizontal"` / `"factory"` literals in dashboard production code (excluding allowlists, test fixtures, comments)
- Write ADR `track3b-dashboard-hub-routing.md` recording the canonical model + 5-PR shape
- Final dashboard build verification

### Validation gates

Every PR runs:
- `pytest tests/cli/test_hub_metadata.py` — orphan-free check
- `pytest tests/architecture/` — no regressions
- `pnpm --filter dashboard build` — generators emit clean artifacts; build succeeds
- `pytest skills/` — existing skill tests pass

PRs 1, 2, 5 additionally run a browser verification (Chrome MCP or screenshot) per CLAUDE.md rule #28: "Client-side verification for any browser-touching change."

### Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Generated `generated.ts` drifts from `hubs.yaml` between regenerations | Medium | `pnpm --filter dashboard build` always regenerates; CI fails if generated artifacts have unstaged changes after build |
| `vertical/horizontal/factory` references in workflow code that legitimately distinguish behavior | Medium | PR 4 reviews each site case-by-case; preserves intentional uses with comments |
| TypeScript build fails on missing import after migration | Low | Each PR runs `pnpm --filter dashboard build` before commit |
| Orphan validator catches existing skills with stale `x-augur-hub` values | Medium | PR 1 audits + fixes any orphans before adding the validator |
| Browser regression in PR 2 affects production UI | Medium | PR 2 verification requires browser screenshot of every affected page; Chrome MCP for interactive tests |

## Track 3b ADR

After PR 5 ships, write `track3b-dashboard-hub-routing.md` ADR recording:

- Canonical hub model: `config/system/hubs.yaml` + per-skill `x-augur-hub`
- Generation pipeline: Python scanner → typed TS derivative
- Retirement of the `{vertical/horizontal/factory}` legacy taxonomy
- 5 PRs landed with their dates and SHAs

## Done criteria for Track 3b

1. `config/system/hubs.yaml` exists with all 6 hubs registered.
2. `apps/dashboard/lib/hubs/generated.ts` is auto-generated and imported across the dashboard.
3. Zero hardcoded `"lifestyle"` / `"apple"` / `"obsidian"` / `"file-manager"` / `"ingest"` / `"vertical"` / `"horizontal"` / `"factory"` literals in dashboard production code (excluding allowlists, test fixtures, intentional domain logic with explanatory comments).
4. Orphan validator passes: every `x-augur-hub` references a hub in `hubs.yaml`.
5. Dashboard builds successfully and renders correctly in browser (verified via Chrome MCP or screenshots).
6. All 5 PRs merged to `main`.
7. ADR `track3b-dashboard-hub-routing.md` written.
