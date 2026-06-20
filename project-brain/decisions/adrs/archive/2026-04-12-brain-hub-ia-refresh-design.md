# Brain Hub IA Refresh Design

**Date:** 2026-04-12  
**Status:** Proposed  
**Scope:** Brain hub information architecture, Settings navigation, Brain Agents positioning, Memory page split

## Goal

Make the Brain hub easier to use by giving each page a clear job:

1. Move provider configuration out of Brain and into Settings
2. Turn Brain Agents into a control surface with unique value instead of a duplicate inventory view
3. Split Memory so valuable content is immediately reachable instead of hidden behind collapsible sections

## Problem

The current Brain hub mixes three different kinds of UX:

1. **System configuration**
   - `/brain/ai/providers` is configuration, not brain content
   - Settings still includes an `Integrations` tab that jumps out to Browse instead of owning the relevant configuration surface

2. **Duplicate agent surfaces**
   - Browse already functions as the inventory and exploration surface for agent-related assets
   - `/brain/ai/agents` does not clearly explain why it exists separately
   - The current page can also fail to show useful content, making the duplication feel worse

3. **Hidden high-value memory content**
   - `/brain/knowledge/memory` contains useful workspace/report/profile/log content
   - That material is minimized behind disclosure sections instead of being available as first-class destinations

The result is weak hub boundaries:

- Brain contains configuration that belongs in Settings
- Settings links to Browse instead of owning settings flows
- Brain Agents overlaps Browse
- Memory hides important information instead of exposing it

## Design Principles

1. **One page, one job**
   - Brain is for thinking, memory, and agent control
   - Settings is for configuration
   - Browse is for discovery and inventory

2. **No duplicate navigation**
   - Do not keep multiple first-class routes for the same responsibility
   - Do not keep Settings tabs that are just detours into Browse

3. **Immediate access beats collapsible hiding**
   - If a section contains durable, frequently useful information, it should have its own route

4. **Brain Agents must earn its existence**
   - The page must answer operational questions Browse does not answer:
     - what execution path Augur will use
     - what is healthy vs blocked
     - what needs setup now
     - what the user should fix next

5. **Prefer canonical cleanup over compatibility**
   - Remove the wrong route rather than preserving a stale parallel surface

## Recommended Model

### 1. Providers move to Settings

`/settings/providers` becomes the canonical provider configuration page.

This page owns:

- remote provider configuration
- active LLM profile selection
- budget settings
- usage visibility related to provider configuration
- actions such as testing a provider or opening config files

`/brain/ai/providers` is retired as a Brain destination rather than preserved as a parallel route.

### 2. Settings owns settings navigation

The Settings hub should stop linking users to Browse for integrations.

Changes:

- remove the legacy `Integrations` tab that points to `/browse?category=integrations`
- add a first-class `Providers` tab in Settings
- keep Settings focused on configuration surfaces the user can act on directly

This removes a confusing IA break where the user enters Settings and is then kicked into an unrelated browsing experience.

### 3. Brain Agents becomes a Control Center

`/brain/ai/agents` should no longer behave like a generic list of agents.

Its primary role becomes **Agent Control Center**:

- show which client/path Augur will currently use
- show health state for local IDE/CLI paths and API-backed paths
- identify blocked setup conditions clearly
- present actionable next steps
- explain dispatch consequences in plain language

Core questions the page should answer immediately:

1. Which execution paths are available right now?
2. Which path is preferred/default?
3. What is broken, missing, or unconfigured?
4. What should the user do next?

This is distinct from Browse:

- **Browse** = inventory, discovery, metadata, catalog
- **Brain Agents** = operational control, routing clarity, setup status, quick fixes

### 4. Memory becomes a small sub-area instead of one overloaded page

Keep `/brain/knowledge/memory` as the landing page, but narrow it to overview content.

Canonical structure:

- `/brain/knowledge/memory`
  - Overview
- `/brain/knowledge/memory/workspace`
  - Workspace
- `/brain/knowledge/memory/profile`
  - Profile
- `/brain/knowledge/memory/daily-logs`
  - Daily Logs

#### Memory Overview keeps:

- search
- stats
- recent decisions
- decision categories
- insights
- wiki maintenance

#### Workspace page owns:

- workspace files
- knowledge report preview
- report regeneration/open actions

#### Profile page owns:

- API profile / human profile content
- profile-related refresh and supporting actions

#### Daily Logs page owns:

- curated daily logs timeline/calendar
- log-specific reading/opening workflows

This directly solves the current issue: valuable memory content is no longer buried inside accordions.

## Navigation Changes

### Brain hub

Current relevant destinations:

- `AI > Agents`
- `AI > Providers`
- `Memory`

Proposed relevant destinations:

- `AI > Agents`
- `Memory > Overview`
- `Memory > Workspace`
- `Memory > Profile`
- `Memory > Daily Logs`

`Providers` is removed from Brain.

### Settings hub

Current relevant destinations:

- General
- Layout
- Plugins
- Integrations -> Browse detour
- Security
- Permissions
- Dispatch

Proposed relevant destinations:

- General
- Layout
- Plugins
- Providers
- Security
- Permissions
- Dispatch

`Integrations` is removed.

## Page-Level UX Direction

### Providers page

The existing providers UI can be reused, but reframed as settings.

Adjustments:

- rename visible context from Brain/AI framing to Settings/Providers framing
- keep configuration and budget controls
- remove any implication that this page is part of Brain knowledge work

### Brain Agents page

The page should lead with control and clarity, not raw inventory.

Recommended structure:

1. **Current execution summary**
   - current available paths
   - current default/preferred path
   - concise explanation of how Augur will dispatch work now

2. **Attention states**
   - setup required
   - degraded
   - healthy

3. **Action area**
   - configure/fix/test
   - next best action based on current state

4. **Supporting detail**
   - grouped agent cards or rows only after the control summary

Success condition:

The user should understand the page’s value within a few seconds even if they never visit Browse.

### Memory pages

The Memory experience should behave like a compact information workspace:

- overview for summary and orientation
- dedicated pages for deep content
- no critical information hidden by default

Where progressive disclosure remains useful, it should happen within a dedicated page, not across unrelated content types on the main overview.

## Non-Goals

This work does not attempt to:

1. Redesign Browse
2. Re-architect provider backends
3. Merge all agent concepts into a single universal page
4. Expand Memory into a much larger multi-tool suite beyond the four-page split

## Acceptance Criteria

### Information architecture

1. There is exactly one canonical provider configuration destination: `/settings/providers`
2. Brain no longer exposes `Providers`
3. Settings no longer exposes a tab that simply routes to Browse

### Agents

1. Brain Agents has a distinct operational purpose from Browse
2. The page clearly communicates:
   - current usable execution paths
   - missing setup
   - next actions
3. The page remains useful even when registry data is sparse or partially degraded

### Memory

1. The Memory overview keeps summary content visible immediately
2. Workspace, Profile, and Daily Logs are reachable as dedicated pages
3. Valuable content currently hidden in collapsed sections becomes directly accessible from navigation

### Verification

1. Brain and Settings tabs reflect the new structure
2. Removed routes/tabs are no longer visible in navigation
3. Browser verification confirms the new pages show real content and not just empty shells

## Risks

1. **Tab registry drift**
   - Brain and Settings navigation are generated from different sources; route changes must update the correct ownership points

2. **Accidental duplication**
   - If Providers remains reachable from both hubs as a first-class nav destination, the IA problem remains unresolved

3. **Memory split without content focus**
   - Simply copying collapsed sections into separate pages without rebalancing overview content would create more pages without better UX

4. **Agents page still reading like inventory**
   - If the redesign only changes layout, the page will still overlap Browse and fail the uniqueness requirement

## Open Implementation Notes

Implementation should favor:

- route cleanup rather than aliases
- metadata/tab ownership changes at the source of registry generation
- reuse of existing page components where the responsibility remains valid
- extraction of Memory subpage components from the current monolith rather than re-implementing the same content from scratch
