---
status: Implemented
date: '2026-02-21'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- platform
- hardening
superseded_by: null
---

# ADR-131: Platform Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 41/100 | 12% | critical | Missing proper layout structure in /ai/knowledge/documents |
| 2 | Page Coverage | 62/100 | 10% | significant-gaps | 4/21 pages use mock/hardcoded data instead of real fetching |
| 3 | API Completeness | 92/100 | 12% | good | 3/42 API routes are stubs with no real backend logic |
| 4 | MCP Tool Wiring | 0/100 | 10% | critical | No actions and no MCP integration — hub is entirely passive |
| 5 | Performance | 32/100 | 10% | critical | Large page (634 lines): /ai/knowledge/documents |
| 6 | User Value | 33/100 | 15% | critical | No data directory — hub produces no persisted data |
| 7 | Workflows | 0/100 | 8% | critical | No actions defined — hub has no workflows |
| 8 | Cross-Hub Connectivity | 60/100 | 5% | significant-gaps | Links to 2 other hubs: /career, /health |
| 9 | Action Buttons | 0/100 | 8% | critical | No action buttons defined — hub has no interactivity |
| 10 | Wow Effect | 0/100 | 10% | critical | Best candidate: No wow effect identified |

**Composite Score**: 33/100 (major-rebuild)

## Wow Effect: AI Agent Live Dashboard

> Real-time view of running agents with status, token usage, task progress, and health. Wire System Health + Agent Registry into a live-updating panel with auto-refresh.

**Score**: 0/100

**Demo Flow**:
1. Open /ai overview or /ai/agents page
2. System auto-detects connected IDE agents via get-ide-status MCP tool
3. Live cards show each agent name, model, status (idle/running/error), token budget
4. Agent Registry refreshes every 10s showing real-time state
5. Click agent card to see recent task history and token usage chart
6. Ping Agent action button tests connectivity with toast feedback

**Current state**: Agent Registry shows "Unknown" with 0 agents
**Gap to demo-ready**: Need Agent Registry API to return real data, live WebSocket or polling, and agent detail view

**Cross-hub leverage**: Pulls data from observe hub (daemon health), admin hub (system status)

**Other candidates**:
- Smart Search (70/100, )
- One-Click Skill Install (60/100, )
- Schedule & Forget (55/100, )

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Platform** (http://localhost:3000/ai) on 2026-02-21.
Composite score: **33/100**.

### Issues Identified

**UI Compliance** (41/100):
- Missing proper layout structure in /ai/knowledge/documents
- No GlassCard usage in /ai/knowledge/memory
- Missing proper layout structure in /ai/knowledge/ocr

**Page Coverage** (62/100):
- 4/21 pages use mock/hardcoded data instead of real fetching
- Missing page.tsx for tab 'Agents' (/ai/agents)
- Missing page.tsx for tab 'Tools' (/ai/tools)

**MCP Tool Wiring** (0/100):
- No actions and no MCP integration — hub is entirely passive

**Performance** (32/100):
- Large page (634 lines): /ai/knowledge/documents
- No code splitting for large page: /ai/knowledge/documents
- Large page (695 lines): /ai/knowledge/index

**User Value** (33/100):
- No data directory — hub produces no persisted data
- 36/42 API routes have real backend logic
- 7/20 pages fetch real data

**Workflows** (0/100):
- No actions defined — hub has no workflows

**Cross-Hub Connectivity** (60/100):
- Links to 2 other hubs: /career, /health
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 22 connections

**Action Buttons** (0/100):
- No action buttons defined — hub has no interactivity

**Wow Effect** (0/100):
- Best candidate: No wow effect identified
- Description: Hub has no complete actions that could serve as a demo
- Gap to demo-ready: Add at least one action with real backend, real data, and visible output

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 0/100):
- Best candidate: No wow effect identified
- Description: Hub has no complete actions that could serve as a demo
- Gap to demo-ready: Add at least one action with real backend, real data, and visible output

**UI Compliance** (current: 41/100):
- Missing proper layout structure in /ai/knowledge/documents
- No GlassCard usage in /ai/knowledge/memory
- Missing proper layout structure in /ai/knowledge/ocr

**MCP Tool Wiring** (current: 0/100):
- No actions and no MCP integration — hub is entirely passive

**Performance** (current: 32/100):
- Large page (634 lines): /ai/knowledge/documents
- No code splitting for large page: /ai/knowledge/documents
- Large page (695 lines): /ai/knowledge/index

**User Value** (current: 33/100):
- No data directory — hub produces no persisted data
- 36/42 API routes have real backend logic
- 7/20 pages fetch real data

**Workflows** (current: 0/100):
- No actions defined — hub has no workflows

**Action Buttons** (current: 0/100):
- No action buttons defined — hub has no interactivity

### Phase 2: Completeness

**Page Coverage** (current: 62/100):
- 4/21 pages use mock/hardcoded data instead of real fetching
- Missing page.tsx for tab 'Agents' (/ai/agents)
- Missing page.tsx for tab 'Tools' (/ai/tools)

**Cross-Hub Connectivity** (current: 60/100):
- Links to 2 other hubs: /career, /health
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 22 connections

## Consequences

### Positive

- Platform hub upgraded with standardized hardening across 9 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: AI Agent Live Dashboard

### Negative

- Requires implementation effort across 9 dimensions
- Some dimensions may require runtime testing (performance, cross-hub connectivity)

### Neutral

- Existing working features remain untouched
- Audit report stored for trend tracking

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065).
No manual alternatives were evaluated.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- Audit report: `ai` hub audit
- Audit timestamp: 2026-02-21T01:31:55.294201

## Browser Findings (Chrome MCP Live Audit)

| Page | Status | Issue |
|------|--------|-------|
| `/ai` | Clean | Overview renders with live System Health data (MCP Bridge Healthy, 93 tools) |
| `/ai/knowledge` | Clean | Well-structured with real API hooks, Quick Search, Knowledge Sources |
| `/ai/scraper` | Clean | Provider Status, Registered Sources with real data |
| `/ai/mcp-app-factory` | **Broken** | `SyntaxError: Unexpected token '<'` — JSON parse error + "Factory hub configuration not found" |
| `/ai/install` | Warning | "Install hub configuration not found" but renders Discovery Stats |
| `/ai/schedules` | UI Issue | Dark grey stat cards + chart with unreadable text — contrast/theme mismatch |

## User Notes

Focus on action buttons — the main gap is interactivity. Every skill page needs action buttons that wire to MCP tools.

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-131: Platform Hardening**.

Read the full ADR: `docs/decisions/ADR-131-ai-hardening.md`

### Hub Architecture

The AI hub spans **5 skills** across the `plugins/ai/` bundle:

| Skill | Dashboard Path | Pages | Actions | MCP Tools |
|-------|---------------|-------|---------|-----------|
| `ai_bridge` | `plugins/ai/skills/ai_bridge/augur/dashboard/` | overview, tabs/ | 0 | 0 |
| `knowledge` | `plugins/ai/skills/knowledge/augur/dashboard/` | search, index, memory, documents, ocr | 4 | 15 |
| `install` | `plugins/ai/skills/install/augur/dashboard/` | discover, catalog | 0 | 0 |
| `scraper` | `plugins/ai/skills/scraper/augur/dashboard/` | jobs, sources, settings | 0 | 0 |
| `mcp-app-factory` | `plugins/ai/skills/mcp-app-factory/augur/dashboard/` | create, audit, templates, migrate | 0 | 0 |

**Existing actions** (knowledge only): `analyze-knowledge-gaps` (oneshot), `smart-search` (oneshot), `refresh-graph` (fire), `reindex-all` (fire) — at `plugins/ai/skills/knowledge/augur/data/actions/`

**Action YAML schema** (ADR-130): `plugins/ai/skills/ai_bridge/augur/data/action-schema.yaml`

### Team Orchestration

**Team name**: `adr-131-ai-hardening`

1. **Create team**: `TeamCreate(team_name="adr-131-ai-hardening")`
2. **Create tasks**: For each step below, `TaskCreate` with `blocked_by` for sequential deps
3. **Spawn 4 teammates**: actions, frontend, pages, validator
4. Each teammate reads `.claude/agents/{name}.md`, claims tasks via `TaskList` + `TaskUpdate`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

#### Phase 1: Action Buttons & MCP Wiring (PARALLEL — all skills independent)
**Priority**: This is the main gap — every skill needs action buttons.

| Step | Agent | Tier | Task | Details |
|------|-------|------|------|---------|
| 1.1 | actions | medium | Create action YAMLs for `ai_bridge` skill | Create `plugins/ai/skills/ai_bridge/augur/data/actions/` with: `ping-agent.yaml` (fire — call `get-ide-status`), `refresh-health.yaml` (fire — call System Health API), `diagnose-bridge.yaml` (oneshot — analyze MCP Bridge status) |
| 1.2 | actions | medium | Create action YAMLs for `install` skill | Create `plugins/ai/skills/install/augur/data/actions/` with: `discover-skills.yaml` (oneshot — call `discover-skill`), `evaluate-all.yaml` (oneshot — score all discoveries), `install-skill.yaml` (ide — send install command to IDE) |
| 1.3 | actions | medium | Create action YAMLs for `scraper` skill | Create `plugins/ai/skills/scraper/augur/data/actions/` with: `scrape-url.yaml` (modal — user inputs URL + provider), `check-providers.yaml` (fire — ping all providers), `view-jobs.yaml` (fire — refresh recent jobs) |
| 1.4 | actions | medium | Create action YAMLs for `mcp-app-factory` skill | Create `plugins/ai/skills/mcp-app-factory/augur/data/actions/` with: `create-app.yaml` (ide — scaffold new MCP app), `audit-tools.yaml` (oneshot — analyze tool coverage), `migrate-legacy.yaml` (ide — migrate old tool format) |
| 1.5 | actions | medium | Wire knowledge actions to pages | Knowledge has 4 actions already — ensure each knowledge page imports and renders the relevant `ActionButton` components. Check `plugins/ai/skills/knowledge/augur/dashboard/` pages. |

#### Phase 2: Wow Effect — AI Agent Live Dashboard (PIPELINE after 1.1)
**Priority**: Headline demo.

| Step | Agent | Tier | Task | Details |
|------|-------|------|------|---------|
| 2.1 | pages | high | Build Agent Registry live view | Create `/ai/agents` page that fetches `get-ide-status` MCP tool on 10s interval. Show agent cards with name, model, status badge (idle/running/error), connection type. Use GlassCard layout. |
| 2.2 | pages | medium | Build Agent Detail panel | Click an agent card -> slide-out panel showing: recent tasks, token usage, last activity. Fetch from `/api/ai/agents/[id]` route. |
| 2.3 | actions | medium | Add "Ping Agent" action button | `plugins/ai/skills/ai_bridge/augur/data/actions/ping-agent.yaml` — dispatch: fire, calls `get-ide-status`, shows toast with response. Wire into agents page header. |

#### Phase 3: Fix Broken Pages & UI (PARALLEL)

| Step | Agent | Tier | Task | Details |
|------|-------|------|------|---------|
| 3.1 | frontend | medium | Fix `/ai/mcp-app-factory` JSON parse error | The page fetches a config endpoint that returns HTML instead of JSON. Debug the API route, fix the fetch URL or add error boundary. Page source: `plugins/ai/skills/mcp-app-factory/augur/dashboard/page.tsx` |
| 3.2 | frontend | medium | Fix `/ai/schedules` dark grey theme | Stat cards and chart use wrong color scheme. Ensure all cards use `GlassCard` pattern with light background. Source: `plugins/ai/skills/ai_bridge/augur/dashboard/schedules/page.tsx` |
| 3.3 | frontend | medium | Fix `/ai/install` config warning | "Install hub configuration not found" — check what config the page expects and provide it or suppress the warning gracefully |
| 3.4 | frontend | medium | Add GlassCard to knowledge pages | `/ai/knowledge/memory`, `/ai/knowledge/search`, `/ai/knowledge` overview — wrap content sections in GlassCard. Add loading states to `/ai/knowledge/ocr` |

#### Phase 4: Performance — Code Splitting (PARALLEL)

| Step | Agent | Tier | Task | Details |
|------|-------|------|------|---------|
| 4.1 | frontend | medium | Split large knowledge pages | 5 pages >600 lines: documents (634), index (695), overview (754), search (599), schedules (641). Extract table/list components into separate files with `dynamic(() => import(...))`. Target <300 lines per page. |

#### Phase 5: Page Coverage & Missing Pages (PARALLEL)

| Step | Agent | Tier | Task | Details |
|------|-------|------|------|---------|
| 5.1 | pages | medium | Create `/ai/agents` page | Live agent registry with cards showing IDE connections. Main wow effect page. |
| 5.2 | pages | medium | Create `/ai/tools` page | List all 93 MCP tools with search/filter. Fetch from `list-mcp-tools` or `/api/ai/tools`. Group by category. |
| 5.3 | pages | medium | Create `/ai/memory` page | View curated memory (MEMORY.md), daily logs, memory stats. Fetch from `memory-stats` and `memory-search` MCP tools. |
| 5.4 | pages | medium | Create `/ai/terminal` page | Embedded terminal or CLI command history. Show recent Claude Code / agent sessions. |
| 5.5 | pages | low | Create `/ai/setup` page | Onboarding wizard — check MCP server status, IDE connections, API keys configured. Use existing System Health data. |
| 5.6 | pages | medium | Fill 4 stub pages | `mcp-app-factory/create`, `mcp-app-factory/audit`, `mcp-app-factory/templates`, `mcp-app-factory/migrate` — all 17-line placeholders. Build real content or clear empty-state UI. |

#### Phase 6: Cross-Hub Connectivity (PARALLEL)

| Step | Agent | Tier | Task | Details |
|------|-------|------|------|---------|
| 6.1 | frontend | medium | Add cross-hub links | Link to observe hub (daemon health), admin hub (system status), career hub (knowledge sources used by career). Add RelatedHubs component to overview page. Import shared services where applicable. |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | `npm run build` + `npx tsc --noEmit` in `src/dashboard/` |
| V.2 | validator | low | Browser validation: open every `/ai/*` page in Chrome MCP, screenshot, check console errors |
| V.3 | validator | low | Action validation: verify all new action YAMLs pass schema validation against `action-schema.yaml` |
| V.4 | validator | low | MCP tool validation: every `mcp_tool` reference resolves to a registered tool |
| V.5 | validator | low | Re-run audit: `python3 plugins/dev/skills/frontend/scripts/dashboard_hardening_audit.py --url http://localhost:3000/ai` — all dimensions >= 90 |

### Completion Criteria

- [ ] **Action Buttons**: Every skill page has action buttons (ai_bridge 3+, knowledge 4, install 3+, scraper 3+, factory 3+)
- [ ] **MCP Tool Wiring**: Actions wire to real MCP tools (`get-ide-status`, `discover-skill`, `memory-search`, etc.)
- [ ] **Wow Effect**: `/ai/agents` page shows live agent registry with auto-refresh and Ping Agent action
- [ ] **UI Compliance**: All pages use GlassCard pattern, proper layout structure, loading states
- [ ] **Performance**: No page >400 lines — large pages split via dynamic imports
- [ ] **Page Coverage**: All 5 missing pages created (agents, tools, memory, terminal, setup), 4 stubs filled
- [ ] **Cross-Hub**: Links to observe, admin, career hubs; RelatedHubs on overview
- [ ] **Broken pages fixed**: mcp-app-factory renders without errors, schedules uses correct theme, install config warning resolved
- [ ] **Build passes**: `npm run build` + `npx tsc --noEmit` zero errors
- [ ] **Browser clean**: Every `/ai/*` page renders with zero console errors in Chrome MCP
- [ ] **Audit re-score**: Composite score >= 85/100 (up from 33)
- [ ] ADR-131 status updated to Implemented
