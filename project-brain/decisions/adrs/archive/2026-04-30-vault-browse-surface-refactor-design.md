---
title: Vault, Browse, and Dashboard Surface Refactor Design
date: 2026-04-30
status: proposed
scope: design
related:
  - 2026-04-23-vault-user-surfaces-phase1-design.md
  - 2026-04-29-track3b-dashboard-hub-routing-design.md
---

# Vault, Browse, and Dashboard Surface Refactor Design

## Purpose

Augur's vault and dashboard have outgrown the original skill-aligned mental model. The vault now contains protected runtime roots, user notes, source captures, drafts, memory, wiki pages, and user skills. Browse also mixes user-facing knowledge, capability discovery, dashboard route inventory, commands, actions, agent profiles, workflows, MCP internals, and package management.

This design defines a more aggressive product model:

- the vault becomes Obsidian-first and user-journey oriented without moving runtime-protected roots;
- Browse separates operation-mode user value from development-mode internals;
- the legacy dashboard `Pages` model is retired in favor of app surfaces, generated capability profiles, and dev-only surface diagnostics.

## Goals

- Make the vault understandable in Obsidian with shallow, stable folders.
- Preserve Augur runtime integrations for protected roots.
- Make Browse reflect user journeys and usable capabilities instead of implementation categories.
- Retire the current mixed page taxonomy of `custom`, `yaml`, `auto`, `pageType`, and `contributions.pages` as user-facing concepts.
- Keep custom dashboard UI only where it represents a real app workflow.
- Ensure every skill remains discoverable through a generated capability profile.
- Move extension and bundle management from Settings into Browse as a first-class management surface.

## Non-Goals

- Do not move `skills/`, `memory/`, `wiki/`, `sources/`, or `_drafts/` in the first migration.
- Do not ban custom React surfaces entirely; app workflows still need custom product UI.
- Do not let vault/user skills ship arbitrary custom TSX into the dashboard build.
- Do not delete current dashboard routes before they have been classified and mapped.
- Do not implement this directly from the design; a separate implementation plan must sequence the migration.

## Vault Model

The vault root should become Obsidian-first, but runtime-safe. The first migration keeps these protected roots physically stable:

- `skills/`
- `memory/`
- `wiki/`
- `sources/`
- `_drafts/`

New or cleaned user-facing roots:

- `inbox/`
- `notes/`
- `archive/`
- `_system/`

`notes/` uses one level of domain or life-area grouping, such as `notes/venture-augur/`, `notes/career/`, `notes/health/`, and `notes/finance/`. Note type, source, skill linkage, status, and routing should live in frontmatter and links, not in deeper folders.

Legacy top-level domain folders are not bulk-moved. Each item is reviewed and classified as:

- migrate to `notes/{domain}/`;
- consolidate into a stronger existing note;
- archive under `archive/{domain}/`;
- hard delete after explicit classification;
- defer when source ownership or runtime use cannot be proven from inventory evidence.

The migration must preserve RAG provenance and Obsidian links. Deletions require a migration ledger entry or Git diff evidence so authored knowledge is not silently lost.

## Dashboard Surface Taxonomy

The final dashboard model has three concepts.

### App Surface

An app surface is a custom product route for a real user workflow.

Examples:

- Brain Inbox
- Brain Search
- Brain Memory
- Brain Wiki
- Integrations
- Extensions & Bundles

Rules:

- Source lives under `apps/dashboard/features/pages/{app}/{surface}/page.tsx`.
- The route belongs to an app, not to a skill.
- It may compose many skills behind the scenes.
- It must use MCP-backed data flows.
- It must pass browser/page-health verification.
- It is operation-visible by default unless explicitly marked dev-only.

### Capability Profile

A capability profile is the generated profile for a skill or capability. It replaces arbitrary skill-owned dashboard pages.

Inputs:

- `SKILL.md` metadata;
- MCP tools;
- actions;
- prompts;
- commands;
- integrations;
- docs and examples;
- health and freshness data;
- app placements;
- safety and permissions metadata.

Sections may be customized through profile metadata, but they do not create standalone dashboard routes.

Capability profiles answer: what can this skill do, how do I use it, what data does it touch, where does it appear, and is it healthy?

### Developer Surface

A developer surface is a dev-only route or inventory for implementation health.

Examples:

- Dashboard Surface Registry
- Agent Profiles
- Workflow Definitions
- MCP Servers
- MCP Tools
- API Routes
- Scripts
- Tests
- Logs
- generated output diagnostics

Developer surfaces are not part of the operation-mode user journey.

## Retired Page Model

The migration retires these as supported route-authoring mechanisms:

- `skills/{skill}/augur/dashboard/**`;
- `skills/{skill}/augur/pages/*.yaml` as standalone routes;
- `contributions.pages` as a route declaration source;
- `page_type: auto` as a route source;
- generated YAML wrapper routes as a distinct product concept;
- operation-mode `Pages` as a Browse category.

`contributions.pages` can remain temporarily as migration metadata for label, icon, order, visibility, and classification while legacy routes are being retired. After migration, route-related data must move into explicit app-surface metadata and capability-profile metadata, and the `contributions.pages` key must be rejected.

Declarative config is not removed entirely. It is reframed as capability-profile section metadata, not as standalone dashboard pages.

## Routing Source Of Truth

The route registry should expose two route classes:

### `app_surface`

- Source: `apps/dashboard/features/pages/{app}/{surface}/page.tsx`
- Owner: app-surface registry metadata
- Linked skills: explicit list of powering capabilities
- Visibility: operation or development
- Verification: browser load and page-health checks

### `developer_surface`

- Source: dashboard framework or diagnostics modules
- Owner: dashboard/dev tooling
- Visibility: development only
- Verification: route load and diagnostics tests

Capability profiles should render through `/browse/skills/{skillId}`. They are generated from the capability registry and should not be standalone skill-owned routes.

## Browse Category Design

Operation mode should prioritize user journey and usable capabilities.

Operation categories:

- `Inbox`
- `Notes`
- `Sources`
- `Wiki`
- `Skills`
- `Actions`
- `Prompts`
- `Integrations`
- `Extensions & Bundles`
- `Scheduled Executions`

Operation categories that become visible when their backing indexes exist:

- `Drafts`
- `Archive`

Development mode adds implementation and diagnostic surfaces:

- `Dashboard Surface Registry`
- `Agent Profiles`
- `Workflow Definitions`
- `Commands`
- `MCP Servers`
- `MCP Tools`
- `API Routes`
- `Scripts`
- `Tests`
- `Logs`
- `_System Metadata`

### Category Meanings

`Skills` is the capability catalog. It includes core repo skills, vault skills, external skills, and client-visible skills. It does not mean the physical vault `skills/` folder.

`Actions` is the normal operation-mode "do something" surface. Actions should classify safety and intent: user action, maintenance action, destructive action, and dev action.

`Prompts` is the reusable LLM-template library. User-facing prompt templates stay operation-visible; internal eval or scaffold prompts move to development.

`Commands` is demoted from primary operation mode. Commands are slash/agent entrypoints and policy aliases. User-facing commands may appear through Actions or advanced filters, while dev/test/internal commands stay development-only.

`Integrations` shows connected systems such as GitHub, Gmail, Google Drive, Google Calendar, Obsidian, Apple, Browser, and filesystem. It should show per-client availability, auth status, transport, and capabilities. MCP implementation details move to `MCP Servers` and `MCP Tools` in development mode.

`Extensions & Bundles` replaces the Settings plugin tab as the package-management surface. It should expose installed bundles, imported skill packages, enable/disable state, dependency status, export/install actions, and source provenance.

`Agent Profiles` replaces the overloaded `Agents` category. It is development-only until Augur exposes real interoperable agents. Current `plugins/agents/*.md` entries are execution profiles, not user-facing agents.

`Workflow Definitions` is development-only by default. User-facing journeys should become app surfaces, actions, or playbooks. Machine-readable workflows may later align with a standard workflow format, but they should not remain a mixed operation-mode category.

`Dashboard Surface Registry` replaces `Pages` as a dev-only inventory. It should show app routes, developer routes, source paths, owner, implementation class, health, generated outputs, and migration classification.

## User Dashboard Creation Model

The user no longer starts by "adding a page." They choose one of two product paths.

### Build An App Surface

Use this when the user needs a real workflow dashboard.

Example: a Venture app with pipeline, competitor review, investor prep, and content calendar.

Process:

- create or extend an app;
- implement a route under `apps/dashboard/features/pages/{app}/{surface}/page.tsx`;
- wire data through MCP tools;
- register it as an app surface;
- verify it in the browser.

### Build A Capability Profile

Use this when the user needs to expose what a skill can do.

Example: a Gmail triage skill that exposes tools, actions, prompts, commands, examples, health, and app placements.

Process:

- update `SKILL.md`;
- declare MCP tools, prompts, commands, actions, integrations, docs, examples, and safety metadata;
- add capability-profile section metadata when default generated sections are insufficient;
- Browse renders the capability profile automatically.

The user loses casual arbitrary mini-dashboard creation inside each skill. The user gains a cleaner product architecture where routes are app workflows and skills are discoverable capabilities.

## Migration Strategy

### Phase 1: Inventory

Build a dashboard surface inventory for every current route and page entry.

Each item must be classified as one of:

- `promote_app_surface`;
- `convert_capability_profile`;
- `convert_profile_section`;
- `move_dev_surface`;
- `delete`;
- `blocked_needs_decision`.

Inventory fields:

- route;
- source path;
- owning skill;
- hub/app;
- current implementation type;
- current Browse category;
- dev-only flag;
- MCP tools and actions used;
- browser health;
- proposed destination;
- migration notes.

### Phase 2: Freeze Legacy Inputs

Add checks that block new legacy page authoring:

- no new `skills/*/augur/dashboard/**`;
- no new standalone `skills/*/augur/pages/*.yaml`;
- no new `contributions.pages` route declarations;
- no new `page_type: auto` route sources.

Existing legacy files are allowed only while they have inventory entries.

### Phase 3: Build Capability Profile Renderer

Create the generated capability profile before deleting old skill pages.

Required profile sections:

- summary;
- tools;
- actions;
- prompts;
- commands;
- integrations;
- app placements;
- docs and examples;
- data paths;
- health and freshness;
- safety and permissions.

### Phase 4: Promote Real App Surfaces

Promote routes that represent real user workflows into app surfaces. Brain custom pages are the reference model.

Move plugin/bundle management from Settings into Browse as `Extensions & Bundles`.

Any old skill route that is actually an app workflow must move into `apps/dashboard/features/pages/{app}/{surface}/page.tsx`.

### Phase 5: Retire Legacy Discovery

After the inventory has no active legacy routes:

- remove `skills/*/augur/dashboard` discovery;
- remove standalone YAML page discovery;
- remove `autoPages` route generation;
- invalidate `contributions.pages` route declarations;
- rename operation `Pages` away and expose only dev `Dashboard Surface Registry`.

### Phase 6: Verification

Required checks:

- route inventory has zero unclassified legacy routes;
- operation Browse has no `Pages`;
- every operation category has useful data or an honest empty state;
- core repo skills appear in `Skills`;
- vault skills appear in `Skills`;
- integrations show client availability for systems like GitHub and Gmail;
- affected app surfaces load in a real browser;
- page-health checks pass for app routes;
- generated capability-profile tests pass for representative core, vault, and external skills.

## Risks And Mitigations

### Useful Skill Pages Disappear

Mitigation: no route deletion without inventory classification and a mapped destination.

### Capability Profiles Feel Weaker Than Existing Custom Pages

Mitigation: build the profile renderer before retiring skill pages, and include tools, actions, prompts, commands, docs, app placements, and health in the first version.

### Generators Encode The Old Split

Mitigation: migrate generator tests alongside the route registry, and keep `Dashboard Surface Registry` until legacy count is zero.

### Vault Skills Lose Standalone Page Power

Mitigation: vault skills get capability profiles. Custom app surfaces remain repo-owned for build stability and security. If a vault skill deserves app UI, it is promoted through an app-surface change rather than compiled directly from the vault.

### Browse Becomes Too Sparse

Mitigation: operation categories should expose user-value data from the same underlying indexes: Inbox, Notes, Sources, Wiki, Skills, Actions, Prompts, Integrations, Extensions & Bundles, and Scheduled Executions.

## Acceptance Criteria

- The spec is followed by an implementation plan before any code migration.
- Existing dashboard surfaces are inventoried and classified before deletion.
- `Pages` no longer appears as an operation-mode Browse category.
- `Dashboard Surface Registry` exists only as development inventory.
- `Skills` opens generated capability profiles rather than arbitrary skill dashboard pages.
- Custom TSX routes are app surfaces, not skill-owned mini-apps.
- Standalone YAML pages no longer create routes after migration.
- Runtime-protected vault roots remain physically stable in the first migration.
- Browser verification is required for changed app surfaces.
