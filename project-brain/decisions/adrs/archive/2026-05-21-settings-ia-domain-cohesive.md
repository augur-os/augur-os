---
title: Settings Hub Domain-Cohesive IA — Implementation Plan
date: 2026-05-21
adr: ADR-773
spec: 2026-05-21-settings-ia-domain-cohesive-design.md
---

# Plan: Settings Hub Domain-Cohesive IA

Drives `/adr implement` for ADR-773. Settings is a **core shell page**
(`app/settings/*` is hand-authored, not plugin-generated), so edits land directly
in `apps/dashboard/app/settings/` and siblings. Each step is independently
committable.

## Step 1 — Extract Onboarding to `/setup`
- Create `apps/dashboard/app/setup/page.tsx` (+ minimal `layout.tsx` header)
  rendering the full onboarding card. Reuse `features/setup/SetupWidget` with a
  full/page variant (the existing `variant="settings"` already renders `FullCard`
  expanded — reuse it, or add a `variant="page"` alias).
- Remove `<SetupWidget variant="settings" />` from `app/settings/page.tsx`.
- Repoint entry points: any sidebar "Setup" link / first-run redirect that
  targets `/settings` for onboarding now targets `/setup`. Search:
  `grep -rn "variant=\"settings\"\|/settings\b.*setup\|SetupWidget" apps/dashboard`.
- Verify `SetupWidget variant="sidebar"` (the collapsed chip/bar) still works and,
  on open, routes to `/setup`.

## Step 2 — Repurpose General → Workspace
- `app/settings/page.tsx`: drop the SetupWidget; keep `<GeneralTab />`. Update the
  intro copy to describe editors + data locations only.
- `GeneralTab.tsx`:
  - Remove the `dashboard` entry from `FILTER_CONFIG` and the
    `DashboardModeSettings` render branch (that component moves in Step 4 —
    extract it first to a shared module, see Step 4).
  - Default `activeFilters` to `["editors", "storage"]`.
  - Relabel the storage block's grouping as "Data locations" (read-only framing).
- `lib/tabs/registry.ts`: change the `general` tab `label` to **"Workspace"**
  (keep `id: "general"`, `href: "/settings"`, `icon`).

## Step 3 — Rename Integrations tab → Connections (label only)
- `lib/tabs/registry.ts`: change the `integrations` tab `label` to
  **"Connections"** (keep `id`, `href`, `icon`).
- `app/settings/integrations/page.tsx`: update intro copy to "Connections".
- Do **not** touch the route or the `LEGACY_TAB_ROUTES` map in
  `app/settings/page.tsx` (those keys are query-param aliases, still valid).

## Step 4 — Move Dashboard Mode + surface Theme in Appearance
- Extract `DashboardModeSettings` from `GeneralTab.tsx` into
  `app/settings/components/DashboardModeCard.tsx` (keep `useModeStore`).
- New `app/settings/components/ThemeModeCard.tsx`: light/dark + theme-name control
  built on the existing `@/hooks/useTheme` (`theme/setTheme/mode/setMode`,
  `ThemeName`). Reuse the option set already used inside `LayoutConfigModal`.
- `app/settings/appearance/page.tsx` render order:
  `ThemeModeCard` → `DashboardModeCard` → `SkillNavSettingsCard` →
  `LayoutConfigModal embedded`. Update intro copy.

## Step 5 — AI & Models Configure / Activity zoning
- Extract read-only blocks into `app/settings/components/AiActivitySection.tsx`:
  - Move "Usage Stats" + "By Provider" out of
    `features/pages/settings/providers/ProvidersPage.tsx`.
  - Move "Agent compatibility" out of `components/LocalBackendSection.tsx`.
- `app/settings/ai/page.tsx`: render a **Configure** section
  (`ProvidersPage` config remainder + `LocalBackendSection` config remainder),
  then an **Activity & status** section header + `AiActivitySection`.
- Keep all MCP queries/keys identical; this is layout extraction only.

## Step 6 — Tests + verification
- Update `app/settings/page.test.tsx` and any tab tests for the new structure
  (onboarding no longer on `/settings`; Workspace shows editors+storage).
- Add a smoke test for `/setup`.
- Run `/auto-test-build` then `/auto-lint`.
- **Browser verification (Rules 28/31/34)** on this worktree's dashboard port
  (from `.augur-worktree.yaml`, NOT :3000): load every settings tab + `/setup` to
  interactive state, screenshot each, confirm no chunk-load/overlay/empty-card
  defects and that every moved block renders real data.

## Risks / notes
- `ProvidersPage` (520 lines) and `LocalBackendSection` (500 lines) extraction is
  the heaviest step; keep the MCP query hooks where the data is consumed to avoid
  prop-drilling churn. Prefer moving the *render* blocks and passing already-fetched
  data, or co-locating a focused query in `AiActivitySection`.
- Confirm `app/settings/*` is not overwritten by a generator before editing
  (`grep -rn "app/settings" scripts/ src/` for generators).
- Label-only renames mean deep links and `LEGACY_TAB_ROUTES` keep working.
