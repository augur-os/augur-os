---
status: Implemented
date: '2026-03-06'
deciders:
- Gur Sannikov
related:
- ADR-028
- ADR-057
- ADR-087
- ADR-130
- ADR-223
hub: null
tags:
- knowledge
- memory
- workspace
- integration
- human
superseded_by: null
---

# ADR-283: Knowledge Memory Workspace Integration and Human Report Regeneration

## Context

`docs/memory/` is already the canonical memory store for Augur (ADR-087), and the `knowledge` skill already owns `/ai/knowledge/memory`. Today, however, those two surfaces are only partially connected:

- the dashboard shows memory stats, search, daily logs, and `HUMAN_API.md`, but it does not expose the broader `docs/memory/` workspace as a first-class surface
- `docs/memory/report.html` already exists as a human-readable "Claude Code Insights" report, but it is effectively invisible from `/ai/knowledge/memory`
- the current profile regeneration path is inconsistent: the dashboard calls `memory-profile-regenerate`, which shells into `.github/scripts/memory_sync.py --profile`, but the current script no longer documents or implements `--profile`
- memory file access logic is duplicated across several knowledge API routes instead of being treated as a single workspace contract

This leaves the memory page in an awkward state: the canonical files exist locally, the dashboard page exists, and the report artifact exists, but the user still cannot manage the memory workspace from one coherent place.

The requested direction is clear:

1. integrate `docs/memory/` with `http://localhost:3000/ai/knowledge/memory`
2. include the human-readable report already generated at `docs/memory/report.html`
3. add an active regenerate affordance backed by Claude/IDE execution rather than a dashboard-side LLM shortcut

Any solution must preserve Augur's existing rules:

- plugin-owned dashboard/API changes stay in `plugins/ai/skills/knowledge/`
- dashboard AI actions must use the central dispatch model, not direct LLM calls from the page
- dashboard API routes remain MCP-first for generated intelligence, while direct static file reads are acceptable for local artifacts such as `report.html`

## Decision

We will turn `/ai/knowledge/memory` into the canonical dashboard surface for the `docs/memory/` workspace and formalize report regeneration as an IDE-dispatch action.

### 1. Treat `docs/memory/` as a workspace, not just a backend directory

The knowledge plugin will expose `docs/memory/` as a structured workspace with explicit asset metadata for:

- `docs/memory/MEMORY.md`
- `docs/memory/HUMAN_API.md` when present
- `docs/memory/report.html`
- `docs/memory/daily/*.md`
- `docs/memory/index.yaml`

This contract will live in plugin-local API routes under `plugins/ai/skills/knowledge/augur/api/memory/` and use the shared dashboard path helpers rather than repeating ad hoc `path.join(root, 'docs', 'memory')` logic in each route.

### 2. Add a first-class Human Report surface to `/ai/knowledge/memory`

The memory page will gain a dedicated workspace/report section that:

- shows whether `report.html` exists
- exposes last-modified metadata and file size
- lets the user open the report directly
- renders an embedded preview through a plugin-local route that serves the HTML safely for dashboard viewing
- falls back to a clear empty state when the report has not been generated yet

The existing memory stats, search, profile, and daily logs remain, but the page will no longer imply that `HUMAN_API.md` is the only durable artifact worth surfacing.

### 3. Split regeneration by responsibility

There are two different regeneration jobs, and they should not share one broken pathway:

#### 3.1 Deterministic profile refresh

`HUMAN_API.md` refresh, if retained, stays a deterministic backend operation exposed through MCP/API. The existing `memory-profile-regenerate` flow must be repaired so it no longer depends on the unsupported `.github/scripts/memory_sync.py --profile` path.

#### 3.2 AI-authored human report regeneration

`docs/memory/report.html` regeneration is an AI synthesis task, so it will be exposed as a page-scoped action button owned by the knowledge plugin, using `dispatch: ide`.

That action will instruct Claude/Codex to:

- read the canonical memory workspace
- rebuild the human-readable report at `docs/memory/report.html`
- preserve local-first paths and plugin boundaries
- leave a fresh artifact that the memory page can immediately display

This is the correct pattern for the requested "Claude build it" regeneration behavior: the dashboard exposes the action, but the IDE agent performs the report generation.

### 4. Keep inline page buttons non-AI

Inline buttons inside React components on `/ai/knowledge/memory` will remain limited to direct fetch/open behavior:

- refresh metadata
- open files
- reload preview state

The page itself must not directly launch an embedded LLM prompt. Any AI-backed generation will come from the central action system so it stays auditable and consistent with the rest of the dashboard.

### 5. Consolidate memory route ownership inside the knowledge plugin

All new routes, actions, and UI for this feature stay inside the `knowledge` skill:

- dashboard UI in `plugins/ai/skills/knowledge/augur/dashboard/memory/`
- file/report routes in `plugins/ai/skills/knowledge/augur/api/memory/`
- action definitions in `plugins/ai/skills/knowledge/augur/data/actions/`
- MCP-backed deterministic memory operations in `plugins/ai/skills/knowledge/augur/mcp/`

No new centralized config will be introduced.

## Consequences

### Positive

- `/ai/knowledge/memory` becomes the real front door for the memory workspace, not just a partial viewer
- `docs/memory/report.html` becomes discoverable and usable from the dashboard
- regeneration behavior becomes architecturally correct: deterministic refreshes via API/MCP, AI report generation via IDE dispatch
- the broken `memory_sync.py --profile` dependency is removed from the user-facing regeneration path
- memory asset handling becomes easier to extend because the workspace contract is explicit

### Negative

- the memory page becomes a broader surface and needs careful UI composition to avoid turning into a cluttered "everything page"
- report preview requires safe HTML-serving behavior and browser validation
- regeneration is split across two mechanisms, which adds some implementation complexity even though it is conceptually cleaner

### Neutral

- `docs/memory/` remains the canonical source of truth
- the knowledge skill remains the owner of memory UI, actions, and APIs
- existing stats/search/daily-log functionality stays in place and is extended rather than replaced

## Implementation Order

### Phase 1: Lock the workspace contract

1. Define the canonical memory asset model and identify which artifacts are read-only, editable, or AI-generated.
2. Replace duplicated memory path resolution with a shared helper for knowledge memory routes.
3. Add plugin-local routes for workspace metadata and report serving/opening.

### Phase 2: Repair regeneration ownership

1. Remove or replace the unsupported `.github/scripts/memory_sync.py --profile` dependency.
2. Keep deterministic profile refresh behind MCP/API only.
3. Add a new knowledge action for IDE-dispatch report regeneration targeting `docs/memory/report.html`.

### Phase 3: Integrate the dashboard page

1. Extend memory hooks/types to fetch workspace and report state.
2. Add a workspace panel and a report panel to `/ai/knowledge/memory`.
3. Keep inline controls limited to fetch/open/refresh behavior.
4. Surface the new regenerate action on the page through the action system for the memory route.

### Phase 4: Validate and harden

1. Validate dashboard build and knowledge plugin wiring.
2. Browser-check `/ai/knowledge/memory` with and without `report.html`.
3. Sweep for stale references to the deprecated `--profile` path and any duplicated direct memory-path logic that should now use the shared helper.

## Alternatives Considered

### Alternative 1: Keep the current page and let users open `docs/memory/` manually

Rejected because it preserves the current fragmentation. The canonical memory workspace would still exist, but the dashboard page would remain an incomplete view that hides the report artifact and the real file model.

### Alternative 2: Regenerate `report.html` from a dashboard API route or direct script call

Rejected because the report is AI-authored output. Putting that behind a page button or direct server-side script path would violate the dashboard's no-direct-LLM pattern and repeat the same architectural mistake that already exists around `memory_sync.py --profile`.

### Alternative 3: Treat `report.html` as an external curiosity and expose only `HUMAN_API.md`

Rejected because the user explicitly wants the report integrated into the memory page, and the report is already present in the canonical workspace. Ignoring it would keep Augur's most human-readable memory artifact outside the main memory UX.

## References

- `plugins/ai/skills/knowledge/augur/dashboard/memory/page.tsx`
- `plugins/ai/skills/knowledge/augur/dashboard/memory/hooks.ts`
- `plugins/ai/skills/knowledge/augur/dashboard/memory/components/HumanApiProfile.tsx`
- `plugins/ai/skills/knowledge/augur/api/memory/profile/route.ts`
- `plugins/ai/skills/knowledge/augur/api/memory/profile/regenerate/route.ts`
- `plugins/ai/skills/knowledge/augur/mcp/__init__.py`
- `.github/scripts/memory_sync.py`
- `docs/memory/MEMORY.md`
- `docs/memory/report.html`
- ADR-028: Two-Layer Memory Architecture with Human API Profile
- ADR-057: Memory System Alignment with Claude Native
- ADR-087: Data Folder Elimination

## Impact Manifest

```yaml
impact:
  apis_changed:
    - function: "GET /api/ai/knowledge/memory/workspace"
      module: "plugins/ai/skills/knowledge/augur/api/memory/workspace/route.ts"
      breaking: false
    - function: "GET /api/ai/knowledge/memory/report"
      module: "plugins/ai/skills/knowledge/augur/api/memory/report/route.ts"
      breaking: false
    - function: "POST /api/ai/knowledge/memory/profile/regenerate"
      module: "plugins/ai/skills/knowledge/augur/api/memory/profile/regenerate/route.ts"
      breaking: false
  patterns_deprecated:
    - grep: "memory_sync\\.py\\s+--profile"
      replacement: "supported MCP-backed profile refresh or IDE-dispatch report regeneration"
    - grep: "path\\.join\\((root|process\\.cwd\\(\\)),\\s*'docs',\\s*'memory'\\)"
      replacement: "shared memory path helper / AUGUR_MEMORY_DIR-backed resolution"
  files_affected:
    - glob: "plugins/ai/skills/knowledge/augur/dashboard/memory/**"
    - glob: "plugins/ai/skills/knowledge/augur/api/memory/**"
    - glob: "plugins/ai/skills/knowledge/augur/data/actions/*.yaml"
    - glob: "plugins/ai/skills/knowledge/augur/mcp/**"
    - glob: "src/dashboard/app/ai/knowledge/memory/**"
    - glob: "src/dashboard/app/api/ai/knowledge/memory/**"
    - glob: "docs/memory/report.html"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR.

You are implementing **ADR-247: Knowledge Memory Workspace Integration and Human Report Regeneration**.

Read: `docs/decisions/ADR-247-memory-workspace-integration-and-report-regeneration.md`

**Team name**: `adr-247-memory-workspace-integration`

### Phase 1: Workspace Contract and Backend Repair
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|---|---|---|---|---|
| 1.1 | architect | high | Lock the canonical asset contract for `MEMORY.md`, `HUMAN_API.md`, `report.html`, daily logs, and metadata; identify all stale regeneration paths | `docs/decisions/ADR-247-memory-workspace-integration-and-report-regeneration.md`, `plugins/ai/skills/knowledge/augur/api/memory/**`, `plugins/ai/skills/knowledge/augur/mcp/**`, `.github/scripts/memory_sync.py` |
| 1.2 | developer | medium | Introduce a shared memory path helper and remove duplicated direct `docs/memory` path joins from knowledge routes that participate in this feature | `plugins/ai/skills/knowledge/augur/api/memory/**/*.ts`, `src/dashboard/lib/paths.ts` |
| 1.3 | developer | medium | Add plugin-local routes for workspace metadata and safe report serving/opening | `plugins/ai/skills/knowledge/augur/api/memory/workspace/route.ts`, `plugins/ai/skills/knowledge/augur/api/memory/report/route.ts`, related `symbols.yaml` files |
| 1.4 | developer | high | Replace the unsupported `memory_sync.py --profile` dependency with a supported deterministic regeneration path or remove the invalid call site if the action is superseded | `plugins/ai/skills/knowledge/augur/mcp/__init__.py`, `plugins/ai/skills/knowledge/augur/api/memory/profile/regenerate/route.ts`, `.github/scripts/memory_sync.py` |

### Phase 2: Dashboard Integration
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|---|---|---|---|---|
| 2.1 | frontend | medium | Extend memory hooks/types to fetch workspace and report state in addition to stats/profile/logs | `plugins/ai/skills/knowledge/augur/dashboard/memory/hooks.ts`, `plugins/ai/skills/knowledge/augur/dashboard/memory/types.ts` |
| 2.2 | frontend | medium | Add a memory workspace panel that surfaces canonical files, report status, and open actions | `plugins/ai/skills/knowledge/augur/dashboard/memory/page.tsx`, new components under `plugins/ai/skills/knowledge/augur/dashboard/memory/components/` |
| 2.3 | frontend | medium | Add an embedded human-report preview with robust empty, loading, and error states | `plugins/ai/skills/knowledge/augur/dashboard/memory/page.tsx`, new report component files under `plugins/ai/skills/knowledge/augur/dashboard/memory/components/` |

### Phase 3: Action Wiring for AI Report Generation
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|---|---|---|---|---|
| 3.1 | architect | medium | Define the page-scoped IDE action contract for regenerating `docs/memory/report.html` so it follows the dashboard dispatch rules | `plugins/ai/skills/knowledge/augur/data/actions/*.yaml`, `plugins/ai/skills/knowledge/augur.yaml`, `docs/decisions/ADR-247-memory-workspace-integration-and-report-regeneration.md` |
| 3.2 | developer | medium | Add the new knowledge action for report regeneration and ensure the memory page exposes it through the existing action system rather than inline LLM code | `plugins/ai/skills/knowledge/augur/data/actions/regenerate-memory-report.yaml`, `plugins/ai/skills/knowledge/augur.yaml`, related page metadata |

### Final Phase: Verification

| Step | Agent | Tier | Task |
|---|---|---|---|
| V.1 | validator | low | Run `python3 .github/scripts/validate_dashboard.py knowledge` |
| V.2 | validator | low | Run `cd src/dashboard && npm run build` |
| V.3 | frontend | low | Browser-validate `/ai/knowledge/memory` with `docs/memory/report.html` present and with the file temporarily absent |
| V.4 | devops | low | Grep for stale `memory_sync.py --profile` references and stale duplicated direct `docs/memory` path joins in the touched knowledge routes |
| V.5 | architect | low | Verify ADR intent against implementation and update status to Accepted only after wiring and validation pass |

### Completion Criteria

- [ ] `/ai/knowledge/memory` exposes the canonical `docs/memory/` workspace, not just partial memory statistics
- [ ] `docs/memory/report.html` is visible and usable from the memory page
- [ ] AI-authored report regeneration is exposed through a knowledge action with `dispatch: ide`
- [ ] Inline page buttons remain limited to non-AI fetch/open/refresh behavior
- [ ] No supported user flow depends on `.github/scripts/memory_sync.py --profile`
- [ ] `python3 .github/scripts/validate_dashboard.py knowledge` passes
- [ ] `cd src/dashboard && npm run build` passes
