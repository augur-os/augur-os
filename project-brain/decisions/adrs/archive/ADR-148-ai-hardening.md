---
status: Implemented
date: '2026-02-25'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
- ADR-131 (AI hub platform hardening)
hub: null
tags:
- hub
- hardening
superseded_by: null
---

# ADR-148: AI Hub Hardening

## Audit Summary

| # | Dimension | Raw | Adj.¹ | Weight | Status | Key Finding |
|---|-----------|-----|-------|--------|--------|-------------|
| 1 | UI Compliance | 31 | 31 | 12% | critical | 10 findings across /ai/agents, /ai/knowledge/* — missing GlassCard, layout, loading states |
| 2 | Page Coverage | 71 | 71 | 10% | needs-work | 7/21 pages use mock/hardcoded data; 6 stub pages (Setup, Create, Audit, Templates, Migrate, Terminal) |
| 3 | API Completeness | 93 | 93 | 12% | good | 3/43 API routes are stubs (knowledge/health, knowledge/projects/[id], install/health) |
| 4 | MCP Tool Wiring | 2 | ~30 | 10% | critical | Static scan found 2/24 pages with `mcp://` refs; 20+ MCP tools exist across sub-skills but lack dashboard.yaml wiring |
| 5 | Performance | 34 | 34 | 10% | critical | 5 large pages (agents 475L, schedules 641L, knowledge/index, knowledge/ocr, install) with no code splitting |
| 6 | User Value | 33 | ~45 | 15% | critical | No data directory; 36/43 API routes have real backend; 8/24 pages fetch real data; 5 actions exist but unwired |
| 7 | Workflows | 0 | ~40 | 8% | critical | Scanner found 0 actions; actually 5 action YAMLs exist (test-all-agents, audit-agent-health, reindex-memory, sync-mcp-tools, configure-agent) — not registered in dashboard.yaml |
| 8 | Cross-Hub Connectivity | 70 | 70 | 5% | needs-work | Links to 3 hubs (/admin, /career, /observability); 23 cross-hub connections; no shared service imports |
| 9 | Action Buttons | 0 | ~35 | 8% | critical | Scanner found 0; Agents tab has Test All + Audit Health buttons with live polling — not in dashboard.yaml actions section |
| 10 | Wow Effect | 0 | 65 | 10% | needs-work | Wow analyzer scored Live Agent Health Arena at 65/100; dimensional scanner reported 0 (looks for wired actions only) |

¹ **Adjusted scores** account for static-scan under-detection of existing functionality. Raw scores reflect what the audit engine found; adjusted scores reflect manual verification of actual hub state.

**Raw Composite**: 34/100 (major-rebuild) | **Adjusted Composite**: ~49/100 (needs-work)

## Wow Effect: Live Agent Health Arena

> Hit 'Test All' on Agents tab — 8 CLI agents run 5-level probes (binary, auth, MCP, tool, round-trip), health badges flip live with 10s auto-refresh countdown. Then 'Audit Health' triggers LLM analysis returning a formatted health table with action items.

**Score**: 65/100 (current) → 95/100 (target)

**Demo Flow**:
1. User clicks 'Test All' button on /ai?tab=agents
2. API calls /api/ai-bridge/client-test with {all: true}
3. Each agent runs 5-level graduated probe (binary→auth→MCP→tool→round-trip)
4. Page auto-refreshes every 10s — health badges flip from unknown to healthy/degraded/offline
5. User clicks 'Audit Health' for LLM-powered analysis
6. IDE agent analyzes registry, checks MCP availability, returns health table

**Current state**: Actions exist (test-all-agents fire, audit-agent-health oneshot) with live polling on Agents tab

**Gap to demo-ready** (3 items):
1. **Progress indicators**: Add per-agent progress bar showing current probe level (binary → auth → MCP → tool → round-trip) with animated transitions
2. **Audit results panel**: Collapsible GlassCard below the agent grid that renders the LLM health table as a structured table (agent name, status, probe breakdown, action items) — not just raw text
3. **Auto-refresh UX**: Circular countdown indicator (10s) with pulse animation, "Live" badge in tab header

**Cross-hub leverage**: Pulls data from /observe for agent metrics, /admin for agent configuration

**Other candidates**:
- audit-agent-health (55/100, oneshot)
- semantic-memory-search (60/100, interactive)
- smart-auto-config (50/100, fire)

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **AI** (http://localhost:3000/ai) on 2026-02-25.
Composite score: **34/100**.

### Issues Identified

**UI Compliance** (31/100):
- Missing proper layout structure in /ai/agents
- No loading states or error handling in /ai/agents
- No GlassCard usage in /ai/knowledge/documents

**MCP Tool Wiring** (2/100):
- No explicit MCP tool references in actions/modals
- 2/24 pages have MCP tool calls

**Performance** (34/100):
- Large page (475 lines): /ai/agents
- No code splitting for large page: /ai/agents
- No code splitting for large page: /ai/knowledge/index

**User Value** (33/100):
- No data directory — hub produces no persisted data
- 36/43 API routes have real backend logic
- 8/24 pages fetch real data

**Workflows** (0/100):
- No actions defined — hub has no workflows

**Action Buttons** (0/100):
- No action buttons defined — hub has no interactivity

**Wow Effect** (0/100):
- Best candidate: No wow effect identified
- Description: Hub has no complete actions that could serve as a demo
- Gap to demo-ready: Add at least one action with real backend, real data, and visible output

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Infrastructure

**Wow Effect — Live Agent Health Arena** (current: 65/100, target: 95/100):
- Wire "Test All" button to show per-agent probe progress indicators (binary → auth → MCP → tool → round-trip)
- Add animated health badge transitions (unknown → testing → healthy/degraded/offline)
- Wire "Audit Health" oneshot output to a collapsible GlassCard results panel with structured table (agent, status, probe breakdown, action items)
- Add circular countdown indicator (10s) with pulse animation and "Live" badge
- Ensure auto-refresh countdown bar is visually prominent

**UI Compliance** (current: 31/100):
- 10 findings across agents, knowledge/*, and overview pages
- Fix: GlassCard wrappers, `glass-panel p-6` root, loading skeletons, error boundaries
- Full list: agents (layout + loading), knowledge/documents (GlassCard + layout), knowledge/index (loading), knowledge/memory (GlassCard), knowledge/ocr (layout + loading), knowledge overview (GlassCard)

**MCP Tool Wiring** (current: 2/100, adjusted: ~30):
- Root cause: 20+ MCP tools exist across sub-skills but aren't referenced in dashboard.yaml `actions` sections
- Fix: Register all action YAMLs in each skill's dashboard.yaml; add `mcp_tool:` field to action YAMLs that invoke MCP tools

**Workflows** (current: 0/100, adjusted: ~40):
- 5 action YAMLs exist but aren't registered in dashboard.yaml — wire all 5
- Add workflow chains: agent-test → audit → report, memory-reindex → search-verify
- Sub-skill workflows: Install discover→evaluate→approve→install, Knowledge index→search→curate

**Action Buttons** (current: 0/100, adjusted: ~35):
- Actions exist in Agents tab but weren't detected by audit — register all action YAMLs in dashboard.yaml
- Add action buttons to: Overview (quick actions), Tools (sync/auto-config), Knowledge (reindex/search), Install (discover/evaluate)
- Consistent button placement across sub-skills using GlassCard action areas

### Phase 2: Sub-Skill Integration & Data Gaps

**Sub-Skill UI Consistency**:
- Extract shared action-button pattern (GlassCard with icon, label, dispatch mode badge) used consistently across all 4 sub-skill page sets
- Ensure all sub-skill pages follow design-standards.md: `glass-panel p-6` root, no duplicate headers, dark-mode-first

**Memory Tab Deduplication**:
- ai_bridge contributes a "memory" tab (agent memory management) and knowledge contributes a "memory" tab (persistent decisions/patterns/preferences)
- Resolution: Rename ai_bridge's tab to "agent-memory" (or merge into knowledge/memory with an "Agent Memory" section) to eliminate collision

**Scraper Hardening** (currently "mostly stub"):
- Implement real API routes for /api/ai/scraper/* (jobs, sources, settings)
- Wire scraper output to Knowledge indexing pipeline (scrape → extract → index)
- Replace hardcoded values with real data fetching in all 3 scraper pages

**User Value** (current: 33/100, adjusted: ~45):
- Create data directory for hub-persisted data (agent configs, test results, audit reports)
- Wire remaining mock pages to real data fetching (Overview aggregates from sub-skills, not hardcoded arrays)
- 36/43 API routes already have real backend — focus on the 7 that don't

**Performance** (current: 34/100):
- Code-split 5 large pages: agents (475L), schedules (641L), knowledge/index, knowledge/ocr, install
- Extract heavy components (agent grid, schedule table, search results) into lazy-loaded client components
- Target: no page.tsx > 200 lines after split

**API Stub Completion** (current: 93/100):
- 3 stub API routes need real backend: `/api/ai/knowledge/health`, `/api/ai/knowledge/projects/[id]`, `/api/ai/install/health`
- These are health endpoints — wire to actual MCP tool calls or service checks

### Phase 3: Polish & Cross-Hub

**Page Coverage** (current: 71/100):
- 7/21 pages use mock/hardcoded data — replace with real API fetching
- MOCK DATA: Overview uses hardcoded arrays — wire to sub-skill stats aggregation
- 6 stub pages (Setup, Create, Audit, Templates, Migrate, Terminal) — implement or remove
- Missing page.tsx for tab 'Memory' (/ai/memory) — resolve via memory tab deduplication (Phase 2)

**Cross-Hub Connectivity** (current: 70/100):
- Links to 3 other hubs: /admin, /career, /observability
- Add shared service imports for cross-hub data (agent metrics from /observe, config from /admin)
- Wire cross-links: Install "Install" → MCP App Factory create-plugin, Knowledge search → Install discoveries
- Overview tab → aggregate stats from all sub-skills via their respective APIs

### Sub-Skill Integration (User Priority)

The AI hub contains 4 sub-skills that need consistent UI patterns and cross-linking:

| Sub-Skill | Plugin Path | Current State | Integration Needed |
|-----------|------------|---------------|-------------------|
| **Knowledge** | `plugins/ai/skills/knowledge/` | Real — 12+ MCP tools, live stats, multi-mode search | GlassCard compliance, cross-link to agent-memory tab |
| **Install** | `plugins/ai/skills/install/` | Real — 8 MCP tools, SSR, YAML-backed | Consistent action buttons, link to MCP App Factory for installs |
| **MCP App Factory** | `plugins/ai/skills/mcp-app-factory/` | Real — plugin CRUD, audit, templates | Cross-link from Install (install flow), consistent nav |
| **Scraper** | `plugins/ai/skills/scraper/` | Mostly stub — hardcoded values | Real API routes, scrape→Knowledge indexing pipeline |

**Cross-linking requirements:**
- Install "Install" → delegates to MCP App Factory create-plugin
- Knowledge search → surfaces Install discoveries
- Scraper output → feeds Knowledge indexing pipeline
- Overview tab → aggregates stats from all sub-skills
- Consistent GlassCard + action button patterns across all sub-skill pages

**Memory tab collision:**
- ai_bridge and knowledge both contribute a "memory" tab — rename ai_bridge's to "agent-memory" to eliminate collision

## Consequences

### Positive

- AI hub upgraded with standardized hardening across 10 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo: Live Agent Health Arena (already 65% functional)
- Sub-skill integration resolves memory tab collision and wires scraper→knowledge pipeline
- Adjusted scoring methodology exposes static-scan under-detection for future audit improvements

### Negative

- Requires implementation effort across 3 phases with 11 execution steps
- Scraper hardening (Phase 2) may require new MCP tools not yet implemented
- Memory tab rename (agent-memory) requires updating all cross-references

### Neutral

- Existing working features remain untouched
- Audit report stored for trend tracking
- Adjusted composite (~49) vs raw (34) gap informs audit engine calibration

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065).
No manual alternatives were evaluated.

## User Notes

Focus on sub-skill integration: Knowledge, Install, MCP App Factory, and Scraper sub-skills need consistent UI patterns and cross-linking. The audit engine underscores this hub — 5 action YAMLs, 20+ MCP tools, and several fully real pages (Agents with live polling, Tools with auto-config, Memory with semantic search, Install with full CRUD) exist but weren't detected by the static audit. Real scores are likely 15-20 points higher than reported for Workflows, Action Buttons, and MCP Tool Wiring.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- ADR-131: AI hub platform hardening (prior hardening round)
- Audit report: `plugins/dev/skills/frontend/augur/data/hardening-reports/ai_20260225.yaml`
- Audit timestamp: 2026-02-25T00:22:54.585240

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-148: AI Hub Hardening**.

Read the full ADR: `docs/decisions/ADR-148-ai-hardening.md`

### Offload Protocol (ADR-054)

Before dispatching each step, check if it can be offloaded to a cheap CLI:

1. Read offload config: `cat config/system/llm.yaml` -> look for `offload:` section
2. If `offload.enabled: true` AND the step's tier is `low`:
   ```bash
   python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py \
     --task "STEP DESCRIPTION" \
     --files "TARGET_FILE_1,TARGET_FILE_2" \
     --context-files "REFERENCE_FILE_FOR_PATTERNS" \
     --work-dir $(pwd)
   ```
3. Review the JSON output
4. Record the verdict (accept / fix / escalate)
5. If `offload.enabled: false` OR tier is `medium`/`high` -> do the step yourself

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-148-ai-hardening", description="Implementing ADR-148: AI Hub Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-148-ai-hardening", name="{role}",
        model="{tier-model}", prompt="You are '{{role}}' on the {team_name} team.
        Read your profile: .claude/agents/{{role}}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-148-ai-hardening`

#### Phase 1: Wow Effect & Critical Infrastructure
**Strategy**: PARALLEL-then-PIPELINE

**Group A** (parallel — no file overlap):

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Implement Wow Effect — Live Agent Health Arena: Per-agent probe progress bars, animated badge transitions (unknown→testing→healthy/degraded/offline), collapsible GlassCard audit results panel with structured table, circular 10s countdown with pulse + "Live" badge | `plugins/ai/skills/ai_bridge/dashboard/agents/page.tsx`, `plugins/ai/skills/ai_bridge/augur/data/actions/` |
| 1.2 | frontend | medium | Fix UI Compliance (31→90): GlassCard wrappers, `glass-panel p-6` root, loading skeletons, error boundaries — 10 findings across agents, knowledge/*, overview | `plugins/ai/skills/knowledge/dashboard/`, `plugins/ai/skills/install/dashboard/`, `plugins/ai/skills/mcp-app-factory/dashboard/` | Chains: `ui_quality_audit`, `redesign_page` |
| 1.3 | devops | medium | Fix MCP Tool Wiring (2→90) + Workflows (0→90) + Action Buttons (0→90): Register all action YAMLs in each skill's dashboard.yaml, add `mcp_tool:` field to action YAMLs, add workflow chains (agent-test→audit→report, reindex→search-verify, Install discover→evaluate→approve→install) | `plugins/ai/skills/ai_bridge/dashboard.yaml`, `plugins/ai/skills/knowledge/dashboard.yaml`, `plugins/ai/skills/install/dashboard.yaml`, `plugins/ai/skills/mcp-app-factory/dashboard.yaml`, `plugins/ai/skills/scraper/dashboard.yaml` |

**Group B** (after Group A — depends on UI changes):

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.4 | frontend | medium | Fix Performance (34→90): Code-split 5 large pages (agents 475L, schedules 641L, knowledge/index, knowledge/ocr, install). Extract heavy components into lazy-loaded client components. Target: no page.tsx > 200 lines | `plugins/ai/skills/ai_bridge/dashboard/agents/page.tsx`, `plugins/ai/skills/ai_bridge/dashboard/schedules/page.tsx`, `plugins/ai/skills/knowledge/dashboard/index/page.tsx`, `plugins/ai/skills/knowledge/dashboard/ocr/page.tsx`, `plugins/ai/skills/install/dashboard/page.tsx` |
| 1.5 | frontend | medium | Wire action buttons to Overview (quick actions), Tools (sync/auto-config), Knowledge (reindex/search), Install (discover/evaluate) pages using consistent GlassCard action areas. Buttons must reference action YAMLs registered in 1.3 | `plugins/ai/skills/ai_bridge/dashboard/`, `plugins/ai/skills/knowledge/dashboard/`, `plugins/ai/skills/install/dashboard/` |

#### Phase 2: Sub-Skill Integration & Data Gaps
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Memory tab deduplication: Rename ai_bridge "memory" tab to "agent-memory" in dashboard.yaml and tab registry. Update all cross-references | `plugins/ai/skills/ai_bridge/dashboard.yaml`, `plugins/ai/skills/ai_bridge/dashboard/memory/` |
| 2.2 | developer | medium | Scraper hardening: Replace hardcoded values in 3 pages (jobs, sources, settings) with real API fetching. Implement real API routes for /api/ai/scraper/*. Wire scraper output→Knowledge indexing pipeline | `plugins/ai/skills/scraper/dashboard/`, `plugins/ai/skills/scraper/` |
| 2.3 | developer | medium | Fix User Value (33→90): Create `plugins/ai/skills/ai_bridge/augur/data/` directory for persisted data (agent configs, test results, audit reports). Wire Overview to aggregate stats from all sub-skill APIs instead of hardcoded arrays | `plugins/ai/skills/ai_bridge/dashboard/page.tsx`, `plugins/ai/skills/ai_bridge/augur/data/` |
| 2.4 | developer | low | Fix API stubs: Implement real backend for 3 stub routes — `/api/ai/knowledge/health` (MCP health check), `/api/ai/knowledge/projects/[id]` (project data fetch), `/api/ai/install/health` (install service check) | `src/app/api/ai/knowledge/health/route.ts`, `src/app/api/ai/knowledge/projects/[id]/route.ts`, `src/app/api/ai/install/health/route.ts` |

#### Phase 3: Polish & Cross-Hub
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Fix Page Coverage (71→90): Replace mock data in remaining pages. Implement or remove 6 stub pages (Setup wizard, Create, Audit, Templates, Migrate, Terminal) — implement if MCP tool exists, remove if no backend | `plugins/ai/skills/ai_bridge/dashboard/`, `plugins/ai/skills/mcp-app-factory/dashboard/` |
| 3.2 | developer | medium | Fix Cross-Hub Connectivity (70→90): Add shared service imports for agent metrics (/observe) and config (/admin). Wire Install "Install"→MCP App Factory create-plugin delegation. Wire Knowledge search→Install discoveries. Overview→sub-skill stats aggregation | `plugins/ai/skills/ai_bridge/dashboard/`, `plugins/ai/skills/install/dashboard/`, `plugins/ai/skills/knowledge/dashboard/` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/ai in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all mcp_tool refs in dashboard.yaml against mcp/__init__.py registered tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

**Dimension targets** (all >= 90/100 on re-audit):
- [ ] Wow Effect: 65 → 90+ (Live Agent Health Arena demo-ready)
- [ ] UI Compliance: 31 → 90+ (GlassCard, loading states, error boundaries)
- [ ] MCP Tool Wiring: 2 → 90+ (all action YAMLs registered with `mcp_tool:` refs)
- [ ] Performance: 34 → 90+ (no page.tsx > 200 lines, all large pages code-split)
- [ ] User Value: 33 → 90+ (data directory, real data fetching, persisted outputs)
- [ ] Workflows: 0 → 90+ (all 5+ actions registered, 3 workflow chains wired)
- [ ] Action Buttons: 0 → 90+ (buttons on Overview, Tools, Knowledge, Install pages)
- [ ] Page Coverage: 71 → 90+ (no mock data, stub pages implemented or removed)
- [ ] Cross-Hub Connectivity: 70 → 90+ (shared service imports, cross-links wired)
- [ ] API Completeness: 93 → 95+ (3 stub health endpoints implemented)

**Sub-skill integration:**
- [ ] Memory tab collision resolved (ai_bridge "memory" → "agent-memory")
- [ ] Scraper pages use real data (no hardcoded values)
- [ ] Scraper→Knowledge indexing pipeline wired
- [ ] Install "Install" delegates to MCP App Factory create-plugin
- [ ] Knowledge search surfaces Install discoveries
- [ ] All 4 sub-skills use consistent GlassCard + action button patterns

**Structural:**
- [ ] All phases executed (Phase 1 → Phase 2 → Phase 3 → Verification)
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Browser validation: page renders in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in dashboard.yaml resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] Every skill with `dashboard/` has a `dashboard.yaml` manifest (required for mount-plugins discovery)
- [ ] No structural integrity issues (`structural_issues` in audit report is empty)
- [ ] ADR-148 status updated to Accepted
