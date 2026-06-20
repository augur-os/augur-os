---
status: Implemented
date: '2026-03-04'
deciders:
- Gur Sannikov
related:
- ADR-065
- ADR-109
- ADR-163
- ADR-217
hub: null
tags:
- consolidate
- around
- core
- repatriate
- non
superseded_by: null
---

# ADR-223: Consolidate `/ai` Around Core AI and Repatriate Non-AI Features

## Audit Summary

Audit source: `http://localhost:3000/ai` (2026-03-04), composite **82/100**.

| Dimension | Score | Key Finding |
|---|---:|---|
| UI Compliance | 65 | `/ai/agents` and mirrored routes are oversized and under-structured |
| Workflows | 64 | 8/30 actions are YAML-only or not executable |
| Performance | 72 | Large page surfaces (`/ai/agents`, `/ai/ai_bridge/*`) |
| Cross-Hub Connectivity | 80 | `/ai` links outward but still acts as a mixed "catch-all" hub |

User focus for this ADR: **page consolidation + repatriation to other plugins for anything not directly related to AI**.

## Context

`/ai` currently mixes core AI workflows with several non-AI platform/developer operations:

- 22 tabs from 7 skills (`ai_bridge`, `knowledge`, `install`, `mcp-app-factory`, `page-builder`, `rag`, `scraper`)
- plugin ownership drift: feature pages live under `/ai` even when they are fundamentally admin/dev/observability workflows

This conflicts with plugin decentralization intent (ADR-163) and makes `/ai` harder to reason about as a user-facing hub.

## Decision

### 1. Consolidate `/ai` into a core AI surface

`/ai` becomes a focused AI hub, not a catch-all bucket.

- Keep only directly AI capabilities (agents, model/provider setup, AI knowledge/search/index, AI ingestion and OCR).
- Route non-AI platform operations to their owning hubs.
- Maintain temporary route compatibility from `/ai` to new destinations during migration.

### 2. Repatriate non-AI features to owning hubs/plugins

Repatriation matrix:

| Current skill under `/ai` | Repatriate to | Rationale |
|---|---|---|
| `install` | `admin` hub | External skill lifecycle is platform administration |
| `mcp-app-factory` | `dev` hub | Plugin generation/audit/migration is developer tooling |
| `page-builder` | `admin` hub | Template-first page composition should be managed as a platform-level capability |
| `ai_bridge/schedules` | `observability` hub | Schedules are system automation operations, not AI intent |
| `ai_bridge/tools` | `observability` hub | MCP diagnostics/tool inventory is observability responsibility |
| `ai_bridge/terminal` | `dev` hub | Generic terminal execution is developer tooling, not AI-specific |

AI features that remain in `/ai`:

- `ai_bridge`: `agents`, `setup`
- `knowledge`: `memory`, `search`, `index`, `documents`, `ocr`
- `rag`: AI knowledge retrieval operations
- `scraper`: AI data-ingestion workflow (`sources`, `jobs`, `settings`)

### 3. Plugin-level changes required

- Update `contributes_to` in repatriated skills' `augur.yaml` files.
- Move/retarget tab contributions so destination hubs expose these tabs directly.
- Remove non-AI tab ownership from `/ai`.
- Keep mounted copies in `src/dashboard/app/*` untouched; edit plugin source only.

### 4. Route compatibility policy

For one release window, keep redirects from old `/ai/*` routes to new hubs:

- `/ai/install*` -> `/admin/*`
- `/ai/audit|create|templates|migrate|import` -> `/dev/*`
- `/ai/page-builder*` -> `/admin/page-builder*`
- `/ai/terminal*` -> `/dev/terminal*` (or chosen dev terminal route)
- `/ai/schedules*` -> `/observability/daemon/loops|jobs`
- `/ai/tools*` -> `/observability/mcp*`

After one full validation cycle, remove deprecated `/ai` tab registrations and route aliases.

## Consequences

### Positive

- `/ai` becomes coherent and aligned with AI intent
- stronger plugin ownership locality (ADR-163)
- clearer user navigation: AI vs platform/dev/observability responsibilities are explicit
- reduced mixed-responsibility pages under `/ai`

### Negative

- migration requires coordinated tab/action/API moves across multiple plugins
- temporary redirect complexity and route migration risk
- documentation, tests, and bookmarks need synchronized updates

### Neutral

- MCP-first pattern remains unchanged
- action dispatch model (`fire`, `oneshot`, `ide`, `modal`) remains unchanged

## Alternatives Considered

### Alternative 1: Keep `/ai` as the mixed umbrella

Rejected: preserves current ambiguity and ownership drift; continues accumulating unrelated features under one hub.

### Alternative 2: Keep `/ai` as umbrella for all "tech" features

Rejected: repeats current problem under a broader label and preserves ownership drift.

### Alternative 3: Create a new standalone "brain" hub now

Rejected for this cycle: would add extra IA churn and delay the immediate consolidation/repatriation objective.

## References

- Audit report: `plugins/dev/skills/frontend/augur/data/hardening-reports/ai_20260304_74a4.yaml`

> Note: Hardening reports moved to `~/Library/Application Support/Augur/state/hardening/` per ADR-416.
- ADR-163: Config decentralization and plugin ownership
- ADR-217: Repatriation precedent (services tab from settings to daemon)

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "plugins/ai/skills/install/**"
      to: "plugins/admin/skills/install/**"
      scope: "dashboard/api/mcp/data/actions"
    - from: "plugins/ai/skills/mcp-app-factory/**"
      to: "plugins/dev/skills/mcp-app-factory/**"
      scope: "dashboard/api/mcp/data/actions"
    - from: "plugins/ai/skills/page-builder/**"
      to: "plugins/admin/skills/page-builder/**"
      scope: "dashboard/api/mcp"
  apis_changed:
    - function: "getSchedules / schedule pages"
      module: "plugins/ai/skills/ai_bridge/augur/dashboard/schedules"
      breaking: false
    - function: "tools pages"
      module: "plugins/ai/skills/ai_bridge/augur/dashboard/tools"
      breaking: false
  patterns_deprecated:
    - grep: "contributes_to:\\s*ai"
      replacement: "contributes_to: <destination hub> for non-AI features"
    - grep: "href:\\s*\"/ai"
      replacement: "href: \"/<ai|admin|dev|observability>/...\""
  files_affected:
    - glob: "plugins/*/skills/*/augur.yaml"
    - glob: "config/dashboard/generated/assembled_hubs.json"
    - glob: "src/dashboard/lib/plugin-runtime/assembled-hubs.json"
    - glob: "src/dashboard/app/ai/**"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR.

You are implementing **ADR-223: Consolidate `/ai` Around Core AI and Repatriate Non-AI Features**.

Read: `docs/decisions/ADR-223-ai-consolidation-repatriation.md`

**Team name**: `adr-221-ai-consolidation-repatriation`

### Phase 1: Consolidate `/ai` to AI-Core
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|---|---|---|---|---|
| 1.1 | architect | high | Classify `/ai` tabs into AI-core vs non-AI and lock ownership map | `config/dashboard/generated/assembled_hubs.json`, `plugins/ai/skills/*/augur.yaml` |
| 1.2 | developer | medium | Retarget `/ai` layout/page copy and nav to AI-core responsibilities | `plugins/ai/skills/ai_bridge/augur/dashboard/layout.tsx`, `plugins/ai/skills/ai_bridge/augur/dashboard/page.tsx` |
| 1.3 | frontend | medium | Remove non-AI tab exposure from `/ai` rendering | `plugins/ai/skills/ai_bridge/augur/dashboard/tabs/*`, `plugins/ai/skills/ai_bridge/augur/dashboard/symbols.yaml` |

### Phase 2: Repatriate Admin + Dev Features
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|---|---|---|---|---|
| 2.1 | developer | medium | Move `install` skill ownership from `ai` to `admin` and update tabs/routes/actions | `plugins/ai/skills/install/**`, `plugins/admin/skills/**` |
| 2.2 | developer | high | Move `mcp-app-factory` and `terminal` ownership from `ai` to `dev` | `plugins/ai/skills/mcp-app-factory/**`, `plugins/ai/skills/ai_bridge/augur/dashboard/terminal/**`, `plugins/dev/skills/**` |
| 2.3 | developer | medium | Move `page-builder` ownership from `ai` to `admin` and expose it as template-first user workflow | `plugins/ai/skills/page-builder/**`, `plugins/admin/skills/**` |

### Phase 3: Repatriate Observability Operations
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|---|---|---|---|---|
| 3.1 | developer | medium | Move `schedules` pages/actions ownership from `ai_bridge` to observability daemon | `plugins/ai/skills/ai_bridge/augur/dashboard/schedules/**`, `plugins/ai/skills/ai_bridge/augur.yaml`, `plugins/observability/skills/daemon/**` |
| 3.2 | developer | medium | Move `tools` pages/actions ownership from `ai_bridge` to observability observe | `plugins/ai/skills/ai_bridge/augur/dashboard/tools/**`, `plugins/ai/skills/ai_bridge/augur.yaml`, `plugins/observability/skills/observe/**` |

### Phase 4: Registry, Mount, and Cleanup
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|---|---|---|---|---|
| 4.1 | devops | low | Regenerate assembled hub metadata and mounted dashboard files | `config/dashboard/generated/assembled_hubs.json`, `src/dashboard/lib/plugin-runtime/assembled-hubs.json`, `src/dashboard/app/**` |
| 4.2 | architect | medium | Remove deprecated `/ai` tab registrations after compatibility checks pass | `plugins/ai/skills/ai_bridge/augur.yaml`, destination `augur.yaml` files |
| 4.3 | developer | low | Update references/docs for moved routes and ownership | `docs/decisions/*.md`, `docs/generated/skill-registry.md`, related route docs |

### Final Phase: Verification

| Step | Agent | Tier | Task |
|---|---|---|---|
| V.1 | validator | low | Run `pytest tests/` and `npm run build` (`src/dashboard`) |
| V.2 | frontend | low | Browser validation of `/ai`, `/observability`, `/admin`, `/dev` |
| V.3 | devops | low | Stale reference sweep for old `/ai/*` links and stale `contributes_to: ai` values in repatriated non-AI skills |
| V.4 | architect | low | Validate ADR intent vs implementation and update status to Accepted |

### Completion Criteria

- [ ] `/ai` exposes only AI-core entrypoints
- [ ] Non-AI tabs are available in destination hubs
- [ ] Redirects for legacy `/ai/*` routes work during compatibility window
- [ ] No stale route references remain for repatriated non-AI pages
- [ ] `npm run build` and `pytest tests/` pass
- [ ] ADR-223 status updated from Proposed to Accepted after implementation
