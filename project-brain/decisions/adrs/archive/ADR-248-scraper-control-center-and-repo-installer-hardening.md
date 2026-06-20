---
status: Implemented
date: '2026-03-06'
deciders:
- Gur Sannikov
related:
- ADR-065 (dashboard hardening workflow automation)
- ADR-162 (action dispatch model)
- ADR-163 (plugin decentralization)
- ADR-237 (hub page-by-page hardening workflow)
hub: null
tags:
- scraper
- control
- center
- repo
- installer
superseded_by: null
---

# ADR-248: Scraper Control Center and Repo Installer Hardening

## Context

The scraper page at `http://localhost:3000/ai/scraper/scraper` has live data and working MCP-backed API routes, but it is still a read-mostly dashboard instead of an operational control center.

The page-specific hardening audit on 2026-03-06 scored the route at **72/100**. The important findings are:

- **UI Compliance 85/100**: the page is serviceable, but it does not use the stronger GlassCard/control-center patterns used elsewhere in the dashboard.
- **User Value 80/100**: the page fetches real data, but the main controls are not exposed inline and the experience depends on action manifests that are not visible in the page itself.
- **Workflows 60/100**: all five existing actions are IDE-assisted; there is no modal capture flow, no autonomous inline source controls, and no visible end-to-end workflow on the page.
- **Cross-Hub Connectivity 0/100**: scraped output is useful to AI knowledge and career flows, but the page does not surface that relationship.
- **Wow Effect 20/100**: the best candidate is currently a hidden action suite, not a visible flow the user can demonstrate live.

The live page confirms the core product gap:

- Source cards show provider, schedule, and active state, but the user cannot enable, disable, run, or edit a source from the page.
- "Add Source" exists only as an IDE action definition; there is no visible input surface on the page.
- The requested "add new scrapers from a repo URL" flow does not exist at all.
- The route is awkwardly nested at `/ai/scraper/scraper` instead of a canonical `/ai/scraper`.

The requested hardening scope is explicit:

1. Make scraper data actionable so the user can enable and disable sources.
2. Add the ability to add new scrapers.
3. Support a test flow where the user pastes `https://github.com/D4Vinci/Scrapling` into a box, clicks install, and the process continues through the IDE action flow.
4. Improve the overall UI and UX.

This work must preserve Augur's architectural rules:

- Dashboard AI work must continue through the central action infrastructure and `dispatch: ide`.
- Dashboard API routes must remain MCP-first.
- Scraper data, manifests, and install state must remain self-contained inside `plugins/ai/skills/scraper/`.
- Route cleanup should prefer canonical paths instead of compatibility shims.

## Decision

Harden the scraper experience into a canonical control center at `/ai/scraper`, with separate workflows for managing scraped sources and installing scraper integrations from repository URLs.

### 1. Canonical route and page ownership

- Promote the current page from `plugins/ai/skills/scraper/augur/dashboard/scraper/page.tsx` to `plugins/ai/skills/scraper/augur/dashboard/page.tsx`.
- Update all skill manifests, mounted routes, and tab references to use `/ai/scraper` as the canonical page path.
- Remove the redundant nested `/ai/scraper/scraper` page instead of keeping a compatibility route.

### 2. Actionable source management

- Extend scraper MCP with write operations for source lifecycle management:
  - toggle active/inactive
  - update schedule/provider/selector metadata
  - run a single source immediately
- Add matching MCP-backed dashboard API routes under `plugins/ai/skills/scraper/augur/api/`.
- Redesign the source surface so each source row/card has visible controls for:
  - enable or disable
  - run now
  - edit source metadata
  - inspect latest output or last job result
- Keep inline data mutations on the page as direct fetch-based interactions with optimistic refresh and explicit loading/error states.

### 3. Separate source registration from scraper installation

The product currently conflates "add a source URL to scrape" with "install a new scraper engine or integration." These are different workflows and must be modeled separately.

- Keep and improve `add-source` for registering websites or domains to scrape.
- Introduce a new "Install Scraper from Repo" workflow for repository URLs such as `https://github.com/D4Vinci/Scrapling`.
- Store installer requests in plugin-local data, for example `plugins/ai/skills/scraper/augur/data/install-requests.yaml`, with statuses such as `pending`, `in_review`, `implemented`, and `failed`.
- Expose installer requests in the page so the user can see what has been requested, what is running in IDE, and what completed.

### 4. Modal-to-IDE install flow

The repo install flow must use central dispatch instead of custom dashboard AI code.

- Add a modal-backed action definition such as `install-scraper-from-repo` with fields for:
  - repository URL
  - optional display name
  - optional notes or intended use
- The modal submit path creates a structured install request record through an MCP-backed API route.
- After submission, the action flow must continue into `dispatch: ide` with a prompt that references the saved request, asks the IDE agent to inspect the target repo, determine integration fit, and implement the scraper/provider in the scraper skill if approved.
- The dashboard must show the request and its status; the actual code modification remains an IDE task, not a dashboard-side automation.
- The first acceptance case for this flow is the Scrapling repository URL supplied by the user.

### 5. UI and UX redesign

- Rebuild the page as a visible command center using the dashboard design standards:
  - stronger KPI hero
  - GlassCard-based operational sections
  - visible action rail for scraper actions
  - clearer separation between sources, jobs, installer requests, and settings
- Replace passive status blocks with operational cards that explain the next useful action.
- Add empty, loading, success, and failure states to every section.
- Surface a visible wow flow on the page:
  - paste repo URL
  - click install
  - continue in IDE
  - watch request status appear in the page

### 6. Cross-hub leverage

- Add explicit navigation or references to downstream consumers of scraper output, starting with AI knowledge and career use cases.
- Show which skill or hub each source feeds so the user understands why a source exists.

## Consequences

### Positive

- The scraper page becomes an operational tool instead of a passive monitoring page.
- Source management and scraper installation become distinct, understandable workflows.
- The Scrapling repository install request becomes a demoable end-to-end IDE handoff.
- Canonicalizing the route to `/ai/scraper` removes an avoidable path smell and improves audit quality.

### Negative

- The scraper MCP surface grows to include more write operations and request-tracking state.
- The install workflow adds a new concept (`install-requests.yaml`) that must be kept accurate.
- Removing `/ai/scraper/scraper` is a breaking route cleanup that requires all callers and manifests to be updated together.

### Neutral

- Existing MCP-first API routing remains the backend pattern.
- Existing scraper data files remain plugin-local and continue to be the source of truth.
- Existing actions such as analyze content and capture authenticated page stay relevant, but will be surfaced differently.

## Implementation Order

### Phase 1: Route cleanup and control-plane contract

1. Canonicalize the route to `/ai/scraper` and update page/action references.
2. Add MCP tools and API routes for source toggle, source update, single-source run, and install request CRUD/status.
3. Define the installer request schema and plugin-local storage.

### Phase 2: Control center UI

1. Redesign the page into a GlassCard-based command center.
2. Add visible source controls with direct fetch-based mutations.
3. Add installer request panels and visible action surfaces.

### Phase 3: IDE handoff workflow

1. Add modal-backed "Install Scraper from Repo" capture.
2. Chain the submitted request into `dispatch: ide`.
3. Validate the Scrapling example flow from pasted URL to request creation and IDE continuation.

### Phase 4: Verification and polish

1. Re-run the scraper hardening audit against the canonical route.
2. Run browser validation for the new flow and zero-console-error rendering.
3. Verify there are no stale `/ai/scraper/scraper` references left in manifests, routes, or docs.

## Alternatives Considered

### Alternative 1: Keep the page read-only and rely on the global action menu

Rejected because it preserves the current discoverability problem. The page would still hide its best workflows behind manifest-defined actions and would not satisfy the requested enable/disable or paste-and-install experience.

### Alternative 2: Treat repo installation as a normal "add source" operation

Rejected because a repository URL represents a scraper integration or provider implementation, not a website source to crawl. Combining them would blur the data model and make the UI harder to understand.

### Alternative 3: Execute repo installs directly from dashboard code or shell commands

Rejected because it violates the dashboard's no-direct-LLM and MCP-first constraints. Repository evaluation and code changes belong in the IDE dispatch path, not in the dashboard runtime.

## References

- Page audit: plugins/dev/skills/frontend/augur/data/hardening-reports/ai_scraper_20260306.yaml
- Existing page source: plugins/ai/skills/scraper/augur/dashboard/scraper/page.tsx
- Existing scraper MCP tools: plugins/ai/skills/scraper/augur/mcp/__init__.py
- Existing source action: plugins/ai/skills/scraper/augur/data/actions/add-source.yaml
- Existing source data: plugins/ai/skills/scraper/augur/data/sources.yaml

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "plugins/ai/skills/scraper/augur/dashboard/scraper/page.tsx"
      to: "plugins/ai/skills/scraper/augur/dashboard/page.tsx"
      scope: "plugins/ai/skills/scraper/augur/dashboard/**/*.tsx"
  apis_changed:
    - function: toggle_scraper_source_tool
      module: plugins.ai.skills.scraper.augur.mcp.__init__
      breaking: false
    - function: update_scraper_source_tool
      module: plugins.ai.skills.scraper.augur.mcp.__init__
      breaking: false
    - function: run_scraper_source_tool
      module: plugins.ai.skills.scraper.augur.mcp.__init__
      breaking: false
    - function: create_scraper_install_request_tool
      module: plugins.ai.skills.scraper.augur.mcp.__init__
      breaking: false
    - function: get_scraper_install_requests_tool
      module: plugins.ai.skills.scraper.augur.mcp.__init__
      breaking: false
  patterns_deprecated:
    - grep: "/ai/scraper/scraper"
      replacement: "Use the canonical route /ai/scraper"
    - grep: "id:\\s*add-source[\\s\\S]*dispatch:\\s*ide"
      replacement: "Keep add-source for website registration and introduce a separate modal-to-IDE install-scraper-from-repo workflow."
  files_affected:
    - glob: "plugins/ai/skills/scraper/augur/dashboard/**/*.tsx"
    - glob: "plugins/ai/skills/scraper/augur/api/**/*.ts"
    - glob: "plugins/ai/skills/scraper/augur/mcp/__init__.py"
    - glob: "plugins/ai/skills/scraper/augur/data/actions/*.yaml"
    - glob: "plugins/ai/skills/scraper/augur/data/*.yaml"
    - glob: "src/dashboard/app/ai/scraper/**/*.tsx"
    - glob: "src/dashboard/app/api/ai/scraper/**/*.ts"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `/write-adr`. Edit if needed before running.

**Team name**: `adr-248-scraper-control-center`

### Phase 1: Route Cleanup and Contract
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | architect | medium | Canonicalize the scraper route to `/ai/scraper`, define the source-management vs repo-installer split, and map all impacted references before implementation starts | `plugins/ai/skills/scraper/augur/dashboard/**`, `plugins/ai/skills/scraper/augur/data/actions/*.yaml`, `src/dashboard/app/ai/scraper/**`, `plugins/dev/skills/frontend/augur/data/hardening-reports/ai_scraper_20260306.yaml` |
| 1.2 | developer | high | Extend scraper MCP with source toggle, source update, single-source run, and install-request tools using plugin-local data storage | `plugins/ai/skills/scraper/augur/mcp/__init__.py`, `plugins/ai/skills/scraper/augur/data/*.yaml` |
| 1.3 | developer | medium | Add or update MCP-backed dashboard API routes for the new source controls and install-request endpoints | `plugins/ai/skills/scraper/augur/api/**/*.ts`, `src/dashboard/app/api/ai/scraper/**/*.ts` |

### Phase 2: Control Center UI
**Strategy**: PARALLEL

Dependency: complete Phase 1 and merge results before starting.

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | frontend | high | Move the page to the canonical route and redesign it as a GlassCard-based scraper command center with visible action surfaces | `plugins/ai/skills/scraper/augur/dashboard/page.tsx`, `plugins/ai/skills/scraper/augur/dashboard/layout.tsx`, `plugins/ai/skills/scraper/augur/dashboard/components/*.tsx` |
| 2.2 | frontend | medium | Add actionable source controls with loading, optimistic refresh, edit states, and run-now interactions backed by the new APIs | `plugins/ai/skills/scraper/augur/dashboard/components/ScraperSources.tsx`, `plugins/ai/skills/scraper/augur/dashboard/components/ScraperJobs.tsx` |
| 2.3 | frontend | medium | Add installer request UI, visible install CTA, and cross-hub context for how scraper outputs feed AI knowledge and career flows | `plugins/ai/skills/scraper/augur/dashboard/components/*.tsx`, `plugins/ai/skills/scraper/augur/dashboard/page.tsx` |

### Phase 3: Modal-to-IDE Installer Flow
**Strategy**: PIPELINE

Dependency: complete Phase 2 and merge results before starting.

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | high | Add a modal-backed `install-scraper-from-repo` action that captures repo URL and writes an install request without adding custom dashboard AI logic | `plugins/ai/skills/scraper/augur/data/actions/*.yaml`, `plugins/ai/skills/scraper/augur.yaml`, `plugins/ai/skills/scraper/augur/data/install-requests.yaml` |
| 3.2 | developer | medium | Wire the install request into `dispatch: ide` so submission continues in the IDE with request ID, repo URL, and implementation expectations | `plugins/ai/skills/scraper/augur/data/actions/*.yaml`, `src/dashboard/hooks/useActionRunner.ts`, `src/dashboard/components/PageActionButtons.tsx` |
| 3.3 | validator | medium | Execute the acceptance flow with `https://github.com/D4Vinci/Scrapling`, verify request creation, visible UI state, and IDE handoff context | `plugins/ai/skills/scraper/augur/data/install-requests.yaml`, `plugins/ai/skills/scraper/augur/dashboard/**/*.tsx` |

### Phase 4: Verification and Cleanup
**Strategy**: PARALLEL

Dependency: complete Phase 3 and merge results before starting.

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | validator | low | Run dashboard verification, including `npm run build`, browser validation on `/ai/scraper`, and zero console error checks | `src/dashboard/**`, `plugins/ai/skills/scraper/augur/dashboard/**` |
| 4.2 | devops | low | Re-run the hardening audit on `http://localhost:3000/ai/scraper` and verify the route cleanup removed stale `/ai/scraper/scraper` references | `plugins/dev/skills/frontend/scripts/dashboard_hardening_audit.py`, `plugins/dev/skills/frontend/augur/data/hardening-reports/*.yaml`, `plugins/ai/skills/scraper/**` |
| 4.3 | architect | low | Confirm the final experience keeps plugin ownership self-contained and preserves the MCP-first and dispatch:ide rules | `plugins/ai/skills/scraper/**`, `docs/decisions/ADR-248-scraper-control-center-and-repo-installer-hardening.md` |

### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open the canonical scraper page, exercise source toggles and installer entry, and capture before/after evidence |
| V.3 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [x] Canonical scraper route is `/ai/scraper`
- [x] No stale `/ai/scraper/scraper` references remain
- [x] Source cards allow enable/disable and run-now operations from the page
- [x] Source registration and scraper installation are modeled as separate workflows
- [x] The page exposes a visible repo install flow with modal capture and IDE continuation
- [x] The Scrapling repository URL flow is tested end to end through request creation and IDE handoff
- [x] Dashboard API routes remain MCP-first
- [x] No custom dashboard-side LLM execution is introduced
- [x] Plugin-local scraper data remains the source of truth
- [x] Hardening audit on the canonical route reaches at least 85/100
- [x] Browser validation passes with zero console errors
- [x] `npm run build` passes
- [x] ADR status updated to Implemented after implementation and verification
