---
status: Implemented
date: 2026-04-29
deciders:
  - gsannikov
related:
  - docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md
  - docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md
  - docs/superpowers/specs/2026-04-29-track3b-dashboard-hub-routing-design.md
  - docs/superpowers/plans/2026-04-29-track3b-dashboard-hub-routing.md
  - ADR-567-bundle-architecture-phase0-cleanup.md
hub: null
tags:
  - architecture
  - bundle-migration
  - track-3b
  - dashboard
  - hub-routing
superseded_by: null
---

# ADR-568: Track 3b — Dashboard Hub-Routing Redesign

## Status

Implemented (with deferred legacy-taxonomy deletion, see Consequences).

## Context

Layer 4 of the cross-client bundle architecture migration deferred the
dashboard hub-routing redesign to its own track (3b). Three pre-track
findings shaped the work:

1. Hub identity scattered: there was no single source-of-truth for
   hub-level metadata. `apps/dashboard/lib/plugin-runtime/assembled-hubs.json`
   carried the runtime view (icon, category, nav_hidden), but hub ids and
   their attributes lived in skill SKILL.md `x-augur-hub` declarations
   plus various hardcoded TS/Python literals.
2. Legacy `{vertical/horizontal/factory}` taxonomy: the skill-import
   pipeline (`dashboard_generator.py`,
   `comprehensive_dashboard_generator.py`, `route_templates.py`,
   `productization_plan_generator.py`, `generate_skill_ui.py`) maps
   layer types to URL prefixes (`vertical->lifestyle`,
   `horizontal->hands`, `factory->agents`). Predates the hubs runtime
   and is not reflected in `x-augur-hub`.
3. Plan vs reality drift: the implementation plan
   (`docs/superpowers/plans/2026-04-29-track3b-dashboard-hub-routing.md`)
   was authored speculatively. Its inventory of "8 hardcoded hub
   literals" in production code and "10 scanner templates with
   hardcoded `lifestyle`" turned out, on audit, to mostly reference
   plugin BUNDLES, skill names (the apple/lifestyle skills), calendar
   provider ids, or the legacy taxonomy — all separate concepts from
   hub ids.

## Decision

Track 3b ships the canonical hub registry as additive infrastructure:

- **`config/system/hubs.yaml`** — hand-edited source-of-truth for
  hub-level metadata (id, label, subtitle, icon, category, layout,
  order, nav_hidden). Five hubs registered (life, brain, command, dev,
  adaptive) matching the existing assembled-hubs runtime.
- **`apps/dashboard/lib/hubs/generated.ts`** — auto-generated typed
  `HUBS` map plus `Hub` interface, `HUBS_BY_CATEGORY`,
  `NAV_VISIBLE_HUBS`. Idempotent emission.
- **`apps/dashboard/scripts/skill-scripts/skill_generation/hubs_loader.py`**
  / **`hubs_emitter.py`** — Python loader (with schema/uniqueness
  validation) and TypeScript emitter. Exposes
  `resolve_default_hub_for_type` for downstream callers.
- **`tests/cli/test_hub_metadata.py`** — orphan-free validator: every
  SKILL.md `x-augur-hub` value must reference a hub id in `hubs.yaml`.
- **`tests/dashboard/lib/hubs/generated.test.ts`** — Jest smoke (6
  cases) covering schema, ordering, category grouping.

Per-skill hub assignment stays in each skill's SKILL.md via
`x-augur-hub`, per CLAUDE.md rule #13. The dashboard's nav-link
construction continues to read from `assembled-hubs.json` (the
runtime-assembled view) — `hubs.yaml` is the canonical *registry*, not
a runtime replacement.

## Plan deviations (significant)

The implementation plan listed concrete file targets that did not
match reality. The track was executed pragmatically against the actual
codebase:

- **PR 2 (8 dashboard production files)**: audit revealed those files
  contain skill names (`apple` skill), calendar source ids
  (`"apple" | "google"`), plugin bundle names, or skill folder paths
  — NOT hub-id literals. The single file with actual hardcoded hub-id
  references is `apps/dashboard/lib/navigation.ts` (HUB_TOOLTIPS map);
  that file was migrated to consume `HUBS` for its registered-hub
  keys while keeping legacy hub-name keys for back-compat with older
  assembled-hubs snapshots.
- **PR 3 (10 scanner templates) and PR 4 (5 workflow tools)**: the
  hardcoded `'lifestyle'` literals across these files are all plugin
  BUNDLE defaults (the user-facing-personal bundle), plugin category
  classification keys, or domain-name icon hints — none are hub-id
  literals. PRs 3 and 4 added `Track 3b:` clarifying comments at the
  most ambiguous sites where field naming (`hub_bundle`,
  `target_bundle`, `self.bundle = self.hub.get(...)`) blurs the
  bundle/hub distinction.
- **PR 5 (delete legacy taxonomy)**: the
  `{vertical/horizontal/factory}` mapping in `dashboard_generator.py`
  and `comprehensive_dashboard_generator.py` is reached via a
  `--layer` CLI flag in `generate_skill_ui.py`. Deleting it requires a
  CLI contract change plus updates to all skill-import callers — a
  larger refactor than this track's scope. PR 5 marked the legacy
  branches with `TODO_OUTDATED(track3b)` and deferred the deletion to
  a follow-up track. The orphan validator catches any new
  `x-augur-hub` references that would reintroduce stale ids.
- **Browser verification**: PRs 1, 2, 5 were specified to require a
  browser-load smoke per CLAUDE.md rule #28. The dispatched-agent
  environment for this track did not have Chrome MCP or other
  browser-control tooling available, so Jest tests + `pnpm typecheck`
  were used as proxies. Each PR commit body explicitly notes the
  skipped browser step. PR 1 and PR 2 are runtime-no-op (PR 1 is
  additive; PR 2 preserves HUB_TOOLTIPS keys and values byte-for-byte
  via HUBS lookups). PR 5 only adds comments and a TODO marker — no
  runtime impact.

## Consequences

- The orphan validator now enforces hub-id correctness as a hard CI
  gate. Adding a new hub means editing `config/system/hubs.yaml` and
  running the dashboard build; adding a skill means declaring
  `x-augur-hub: <existing-id>` and the validator confirms it.
- The legacy `{vertical/horizontal/factory}` taxonomy continues to
  operate the skill-import pipeline. `TODO_OUTDATED(track3b)`
  comments mark the migration debt at each site. A follow-up track
  should:
  - Migrate `generate_skill_ui.py` from `--layer {factory,horizontal,vertical}`
    to `--hub <id>` (or accept either with a deprecation warning).
  - Replace the `{layer -> URL prefix}` map in `dashboard_generator.py`,
    `comprehensive_dashboard_generator.py`, `route_templates.py`,
    `productization_plan_generator.py`, and `generate_skill_ui.py`
    with `f"/{hub}"` derived from hub ids.
  - Delete the legacy mapping once all callers pass `hub` directly.
- The `HUB_TOOLTIPS` map in `apps/dashboard/lib/navigation.ts` retains
  legacy keys (`career`, `studio`, `websites`) so older
  assembled-hubs snapshots that include those hubs still get
  tooltips. They can be removed once the assembled-hubs runtime is
  updated to reflect only hubs registered in `hubs.yaml`.
- Plugin bundles (`lifestyle`, `ai`, `dev`, `career`, ...) remain a
  separate taxonomy from hubs. The bundle-vs-hub distinction is now
  documented inline at the most-confused call sites
  (`import_codegen.py`, `skill_importer.py`, `blueprint_generator.py`,
  `workflow/engine.py`, `workflow/state_manager.py`,
  `mcp/tools_plugin.py`, `mcp/tools_workflow.py`,
  `scoring/user_research.py`).

## Verification

- `tests/cli/test_hub_metadata.py`: 5 passed (schema + orphan-free).
- `pnpm test --testPathPatterns="navigation|hubs"`: 18 passed.
- `pnpm typecheck` (apps/dashboard): clean.
- Audit grep: zero new hub-id literal hardcodes introduced. Existing
  legacy-taxonomy and bundle-default literals carry inline `# Track 3b:`
  or `TODO_OUTDATED(track3b)` markers.

## Commits

Five PRs landed sequentially on branch `track3b-dashboard-hub-routing`:

1. **PR 1**: `feat(dashboard): add config/system/hubs.yaml + generated TS map`
2. **PR 2**: `refactor(dashboard): consume @/lib/hubs/generated in navigation.ts`
3. **PR 3**: `docs(scanner): clarify bundle vs hub distinction in skill-import pipeline`
4. **PR 4**: `docs(workflow): clarify bundle vs hub distinction in workflow tools`
5. **PR 5**: `refactor(dashboard): mark legacy {vertical/horizontal/factory} taxonomy + ADR`
