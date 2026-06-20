---
title: Settings Hub Domain-Cohesive IA
date: 2026-05-21
status: draft
adr: ADR-773
---

# Settings Hub — Domain-Cohesive Information Architecture

## Problem

The Settings hub's five tabs split along inconsistent seams. A per-tab inventory
classified every rendered concept block by **type** (the nature of the control,
not its domain):

| Type | Meaning |
|---|---|
| Onboarding | Guided setup task — a *flow*, not a persistent setting |
| Status | Read-only display of system state (diagnostic) |
| Analytics | Read-only usage/metrics |
| Preference | Persisted user setting (toggle / select / input) |
| Credential | Secrets / provider / account connection config |
| Budget | Numeric spend caps |
| Action | Runs a one-off operation (scan, test, export) |
| Console | Interactive install/configure/rebuild manager |
| Layout/IA | Page structure, navigation, theme config |

Reading down the Type column exposed the defect:

- **Coherent tabs** (Appearance, Privacy & Security) cluster around 1–2 types
  that share one mental model.
- **Mixed tabs** (General, AI & Models, Integrations) each carry 3–6 unrelated
  types.
- Two cross-cutting offenders sit in the wrong place:
  - **Onboarding** (`SetupWidget`) is the only *flow* in the hub, wedged into General.
  - **Dashboard Mode** is an *appearance/UI* preference in General, while the
    actual Appearance tab is one tab over.

### Current per-tab inventory

**General** (`/settings` → `SetupWidget` + `GeneralTab.tsx`)
- Onboarding checklist — `SetupWidget variant="settings"` — *Onboarding*
- Storage & Paths + RAG index — `buildStorageCards` / `RagIndexCard` — *Status*
- Default Editors — `EditorPreferences` — *Preference*
- Dashboard Mode (Operation/Development) — `DashboardModeSettings` — *Preference·UI*

**AI & Models** (`/settings/ai` → `ProvidersPage` + `LocalBackendSection`)
- System LLM profile — *Preference*
- API Budget Limits — *Budget*
- Providers / credentials — `ProviderCard` — *Credential*
- Usage Stats — *Analytics*
- By Provider table — *Analytics*
- Local Backend / Ollama — *Status + Preference + Action*
- Airplane mode — *Preference*
- Agent compatibility — *Status*

**Integrations** (`/settings/integrations` → `McpControlPanel` + `DispatchTargetsTab` + `PluginsTab`)
- MCP Configuration — *Status + Action*
- Dispatch Targets — *Preference*
- Extensions & Bundles — `ExtensionsBundlesPanel` — *Console*

**Appearance** (`/settings/appearance` → `SkillNavSettingsCard` + `LayoutConfigModal embedded`)
- Sidebar Skills — *Preference*
- Layout Settings (incl. Theme/color/typography via `useTheme`) — *Layout/IA*

**Privacy & Security** (`/settings/privacy` → `SecurityTab` + `PermissionsTab`)
- AI Guardrails — *Preference*
- Codebase Security Audit — *Action + Status*
- Audit Log — *Status + Action*
- System Permissions + categories — *Status*

## Principles

1. **One tab = one mental model.** A tab answers a single user question.
2. **Flows leave Settings.** Onboarding is a task, not a setting → its own page.
3. **Type ordering inside a tab.** Editable settings first; read-only
   diagnostics/analytics last, in a clearly demarcated subsection.
4. **Domain cohesion over type fragmentation.** Diagnostics live with the domain
   they describe (AI usage stays in AI & Models), not in a global "System" dump.
   (Chosen over a type-split "System/Diagnostics" tab, which scattered context.)
5. **Minimal route churn.** Relabel tabs; keep existing hrefs/ids to avoid a
   full route migration. Renames are label-only.

## Target IA

Five settings tabs + one separate onboarding page.

```
SETTINGS  (5 tabs)                            href (unchanged)
  Workspace      Default Editors              /settings
                 Storage & Paths · RAG index  (read-only subsection)
  AI & Models    ┌ Configure ─────────────┐   /settings/ai
                 │ System LLM · Providers  │
                 │ Budgets · Local/Airplane│
                 └ Activity (read-only) ───┘
                   Usage · By-provider · Agent compatibility
  Connections    MCP servers · Dispatch · Extensions   /settings/integrations
  Appearance     Theme & Mode · Dashboard Mode         /settings/appearance
                 Sidebar Skills · Layout Settings
  Privacy &      Guardrails · Security Audit            /settings/privacy
  Security       Audit Log · Permissions

SEPARATE PAGE
  /setup         Onboarding checklist  (OUT of Settings)
```

### Tab labels (locked)

- `general` tab → label **"Workspace"** (href stays `/settings`)
- `integrations` tab → label **"Connections"** (href stays `/settings/integrations`)
- `ai`, `appearance`, `privacy` → unchanged labels.
- Tab order preserved: Workspace, AI & Models, Connections, Appearance, Privacy & Security.

## Before → after item mapping (exhaustive — nothing dropped)

| Current item | now | → target |
|---|---|---|
| Onboarding checklist | General | **`/setup` page (out of Settings)** |
| Default Editors | General | Workspace |
| Storage & Paths + RAG index | General | Workspace (read-only "Data locations" subsection) |
| Dashboard Mode op/dev | General | Appearance |
| System LLM profile | AI & Models | AI & Models · Configure |
| Providers / credentials | AI & Models | AI & Models · Configure |
| API Budget Limits | AI & Models | AI & Models · Configure |
| Local Backend / Ollama | AI & Models | AI & Models · Configure |
| Airplane mode | AI & Models | AI & Models · Configure |
| Usage Stats | AI & Models | AI & Models · Activity (demoted) |
| By Provider table | AI & Models | AI & Models · Activity (demoted) |
| Agent compatibility | AI & Models | AI & Models · Activity (demoted) |
| MCP Configuration | Integrations | Connections |
| Dispatch Targets | Integrations | Connections |
| Extensions & Bundles | Integrations | Connections |
| Theme/color/typography | Appearance (in Layout modal) | Appearance (surfaced as top-level Theme & Mode card) |
| Sidebar Skills | Appearance | Appearance |
| Layout Settings | Appearance | Appearance |
| AI Guardrails | Privacy | Privacy & Security |
| Codebase Security Audit | Privacy | Privacy & Security |
| Audit Log | Privacy | Privacy & Security |
| System Permissions + categories | Privacy | Privacy & Security |

## Per-tab target layout

### Workspace (`/settings`)
1. Section header: "Workspace".
2. **Default Editors** (`EditorPreferences`) — editable, first.
3. **Data locations** subsection (read-only): Storage path cards + RAG index.
4. Remove the SetupWidget render and the `dashboard` filter chip /
   `DashboardModeSettings` block from `GeneralTab`.

### AI & Models (`/settings/ai`)
1. **Configure** zone header → System LLM, Providers/credentials, Budgets,
   Local Backend (Ollama model + airplane).
2. **Activity & status** zone header (read-only, visually demoted) → Usage Stats,
   By-provider table, Agent compatibility.
3. Requires extracting the Usage/By-provider blocks from `ProvidersPage` and the
   Agent-compatibility block from `LocalBackendSection` into an
   `AiActivitySection` so the page can place all read-only blocks together.

### Connections (`/settings/integrations`)
- Same three blocks (MCP, Dispatch, Extensions), each with a clear section
  header. Label-only rename of the tab from "Integrations" to "Connections".

### Appearance (`/settings/appearance`)
1. **Theme & Mode** card (top) — light/dark + theme name via existing `useTheme`.
2. **Dashboard Mode** (Operation/Development) — moved from General; extract
   `DashboardModeSettings` to a shared component.
3. **Sidebar Skills** (`SkillNavSettingsCard`).
4. **Layout Settings** (`LayoutConfigModal embedded`).

### Privacy & Security (`/settings/privacy`)
- Unchanged.

### Onboarding (`/setup`, new)
- New route `app/setup/page.tsx` rendering the full onboarding card
  (`SetupWidget` full variant).
- Sidebar/first-run entry points link to `/setup` instead of `/settings`.
- Remove `<SetupWidget variant="settings" />` from `app/settings/page.tsx`.

## Out of scope

- No route renames (hrefs/ids unchanged); avoids a cross-repo migration.
- No new theme engine — surfaces the existing `useTheme`.
- No change to the underlying MCP tools, preferences keys, or data flow.
