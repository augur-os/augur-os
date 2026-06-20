---
status: Implemented
date: 2026-05-21
deciders:
  - gsannikov
  - Claude (Augur agent)
related:
  - ADR-507
  - ADR-760
hub: null
tags:
  - dashboard
  - settings
  - information-architecture
  - onboarding
superseded_by: null
spec_file: 2026-05-21-settings-ia-domain-cohesive-design.md
plan_file: 2026-05-21-settings-ia-domain-cohesive.md
---

# ADR-773: Settings Hub — Domain-Cohesive Information Architecture

## Decision summary

Restructure the Settings hub so each tab maps to **one mental model**: pull the
onboarding flow out to a standalone `/setup` page, dissolve the "General" junk
drawer (Editors + Storage → **Workspace**; Dashboard Mode → **Appearance**), zone
**AI & Models** into a *Configure* block over a demoted read-only *Activity*
block, surface the existing Theme control as a top-level Appearance card, and
relabel **Integrations → Connections** — all via label-only changes with no route
migration.

## Context

The five Settings tabs split along inconsistent seams. Classifying every rendered
concept block by **type** (onboarding, status, analytics, preference, credential,
budget, action, console, layout) showed that coherent tabs (Appearance, Privacy &
Security) hold 1–2 types, while General, AI & Models, and Integrations each mix
3–6. Two items sit in the wrong tab entirely: the onboarding checklist (the only
*flow* in the hub) and Dashboard Mode (an *appearance* preference) — both in
General. Full inventory and type table live in the spec.

## Decision

Domain-cohesive grouping (chosen over a type-split "System/Diagnostics" tab, which
scattered domain context). One tab = one question; flows leave Settings; within a
tab, editable settings precede read-only diagnostics. Target shape:

- **Workspace** (`/settings`): Default Editors + Storage/Paths (read-only).
- **AI & Models** (`/settings/ai`): *Configure* (LLM, Providers, Budgets,
  Local/Airplane) then *Activity* (Usage, By-provider, Agent compatibility).
- **Connections** (`/settings/integrations`): MCP, Dispatch, Extensions.
- **Appearance** (`/settings/appearance`): Theme & Mode, Dashboard Mode, Sidebar
  Skills, Layout.
- **Privacy & Security** (`/settings/privacy`): unchanged.
- **`/setup`** (new page, outside Settings): onboarding checklist.

Routes/ids stay; only labels (`general`→"Workspace", `integrations`→"Connections")
and content placement change. The existing `useTheme` hook backs the surfaced
Theme card — no new theme engine.

## Consequences

- The "General makes no sense" defect is resolved by redistributing its four
  unrelated items to the tabs they belong to.
- AI & Models keeps its full domain story but stops feeling mixed via the
  Configure/Activity split.
- Heaviest engineering is extracting read-only blocks out of `ProvidersPage` and
  `LocalBackendSection` into an `AiActivitySection`.
- No route renames → deep links and `LEGACY_TAB_ROUTES` query aliases keep working.
- UI change → real-browser verification on the worktree port is mandatory before
  closeout (Rules 28/31/34).

## Status notes

Implemented 2026-05-21. All five tabs + the new `/setup` page were verified in a
real browser on the worktree dashboard (port 3005) with real data and zero
console errors; `tsc --noEmit` and `eslint` are clean. One hydration mismatch in
the new `ThemeModeCard` (it reads localStorage via `useTheme`, so SSR markup
differed from the client) was caught during browser verification and fixed by
importing the card with `ssr: false` — the same pattern the codebase already uses
for `LayoutConfigModal`.

Two intentional scope notes:
- **Agent compatibility** stayed inside `LocalBackendSection` rather than moving
  to the Activity zone — it is tightly coupled to the Local Backend's
  Ollama-integration query and describes that backend's capabilities. Only the
  remote-provider **Usage** analytics moved to `AiActivitySection`.
- The Workspace "Data locations" grid renders the RAG-index card with real data
  but the OS path-location cards (repo/config/vault/…) were sparse in this
  worktree — pre-existing `path-config` behavior, not introduced by this work.

Follow-up (not blocking): `docs/generated/adr-index.md` regeneration to include
ADR-773.

## Related

- ADR-507 (dashboard operation/development mode — the Dashboard Mode toggle moved here)
- ADR-760 (Browse page UX cleanup — sibling dashboard IA cleanup)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed: []
  patterns_deprecated:
    - "Onboarding flow rendered inside the Settings General tab"
    - "General settings tab as a mixed-type catch-all"
  files_affected:
    - apps/dashboard/lib/tabs/registry.ts
    - apps/dashboard/app/settings/page.tsx
    - apps/dashboard/app/settings/tabs/GeneralTab.tsx
    - apps/dashboard/app/settings/ai/page.tsx
    - apps/dashboard/app/settings/integrations/page.tsx
    - apps/dashboard/app/settings/appearance/page.tsx
    - apps/dashboard/features/pages/settings/providers/ProvidersPage.tsx
    - apps/dashboard/app/settings/components/LocalBackendSection.tsx
    - apps/dashboard/app/setup/page.tsx
```
