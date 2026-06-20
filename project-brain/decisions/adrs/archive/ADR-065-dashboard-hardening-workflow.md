---
status: Implemented
date: '2026-02-11'
deciders:
- Project team
related:
- ADR-047 (chatbot polish)
- ADR-052 (debugging efficiency)
- ADR-056 (plugin health sweep)
- ADR-061 (career hardening)
- ADR-064 (google workspace hardening)
hub: null
tags:
- dashboard
- hardening
- workflow
- automation
superseded_by: null
---

# ADR-065: Dashboard Hardening Workflow Automation

## Context

Dashboard hardening today is manual and ad-hoc. A developer decides a hub needs work, manually inspects pages, writes a hardening ADR by hand (ADR-061, ADR-064), then orchestrates the implementation. This process:

1. **Takes 2-4 hours** to audit a single hub — manually clicking through subpages, checking API routes, verifying MCP tool wiring, reviewing design compliance
2. **Is inconsistent** — each hardening ADR evaluates different dimensions; no standard checklist exists
3. **Misses cross-hub dependencies** — a career page linking to inbox or knowledge gets audited in isolation
4. **Has no "wow effect" analysis** — the killer demo use case per hub is never explicitly identified or prioritized
5. **Repeats boilerplate** — every hardening ADR re-derives the same team structure, chain references, and verification steps

Existing infrastructure is strong but disconnected:
- `rank_ui_visuals.py` scores UI quality (0-10)
- `pattern_compliance_audit.py` checks design system adherence
- `validate_dashboard.py` verifies API route / service alignment
- `batch_ui_audit.py` discovers routes but runs a generic chain
- Page telemetry (`page-telemetry.ts`) tracks load time, CLS, error rate, engagement
- Chrome MCP tools can screenshot, read DOM, inspect console errors

What's missing is a **single automated workflow** that: takes a URL, crawls the hub, evaluates all dimensions, scores them, and produces a ready-to-execute hardening ADR.

## Decision

### 1. The `/harden` Slash Command

Create a new slash command `/harden` that accepts a dashboard URL and produces a scored hardening ADR.

**Input**: `http://localhost:3000/career` (any hub root URL)
**Output**: `docs/decisions/ADR-NNN-{hub}-hardening.md` with embedded implementation prompt

**Flow**:
```
Developer pastes URL
    │
    ▼
Phase 1: Crawl & Discover
    │  Navigate to URL via Chrome MCP
    │  Discover all subpages (tabs from generated-registry.ts)
    │  Map: hub → skill → plugin → dashboard.yaml
    │
    ▼
Phase 2: Multi-Dimensional Audit
    │  For each subpage:
    │    ├─ Screenshot + DOM inspection
    │    ├─ Console error check
    │    ├─ Design compliance scan
    │    ├─ API route validation
    │    └─ MCP tool wiring check
    │  Cross-hub: link/connectivity analysis
    │  Wow Effect: identify the killer demo use case
    │
    ▼
Phase 3: Score & Rank
    │  Compute per-dimension scores (0-100)
    │  Compute composite hardening score
    │  Rank issues by severity × user-value impact
    │
    ▼
Phase 4: Generate Hardening ADR
    │  Fill ADR template with audit findings
    │  Map issues to implementation phases
    │  Assign agent roles and tiers
    │  Embed implementation prompt
    │
    ▼
Phase 5: Output
    Save ADR to docs/decisions/
    Print implementation prompt to chat
```

### 2. The Hardening Audit Dimensions (10 Dimensions)

Every hub gets evaluated on these 10 dimensions. Each scores 0-100 with a weight:

| # | Dimension | Weight | What It Evaluates |
|---|-----------|--------|-------------------|
| 1 | **UI Compliance** | 12% | GlassCard usage, color scheme, typography, spacing, no anti-patterns |
| 2 | **Page Coverage** | 10% | Every tab in dashboard.yaml has a working page.tsx (no 404s) |
| 3 | **API Completeness** | 12% | All API routes exist, service exports align, types match |
| 4 | **MCP Tool Wiring** | 10% | All `mcp://augur/*` refs in actions resolve to real MCP tools |
| 5 | **Performance** | 10% | Load time (<1s good), CLS (<0.1 good), error rate (<5%) |
| 6 | **User Value** | 15% | Engagement metrics, interaction rate, time-on-page, daily active usage |
| 7 | **Workflows** | 8% | Action buttons functional (modal/llm/fast flows), chains connected |
| 8 | **Cross-Hub Connectivity** | 5% | Links to other hubs work, data flows between hubs verified |
| 9 | **Action Buttons** | 8% | All dashboard.yaml actions rendered, clickable, and wired to backends |
| 10 | **Wow Effect** | 10% | Identified killer demo use case — the one flow that makes someone say "I need this" |

**Composite Score** = weighted sum of all 10 dimensions.

**Score interpretation**:
- **90-100**: Production-ready, no hardening needed
- **70-89**: Good foundation, targeted fixes needed
- **50-69**: Significant gaps, full hardening ADR warranted
- **< 50**: Major rebuild required, multiple phases

### 3. The Wow Effect Analysis

The "wow effect" is the single most impressive workflow a hub can demonstrate. The audit identifies it by:

1. **Scanning action buttons** — which actions have `flow: llm` (AI-powered) or complex modals?
2. **Evaluating data richness** — which pages show real aggregated data (not placeholder text)?
3. **Checking end-to-end flow** — can a user go from input → processing → visible result in one session?
4. **Cross-hub leverage** — does the flow pull data from multiple hubs (e.g., career pulls from knowledge + inbox)?

The wow effect gets its own section in the generated ADR:

```markdown
### Wow Effect: [Name of the killer use case]
**Flow**: [Step-by-step user journey]
**Current state**: [What works / what's broken]
**Gap to demo-ready**: [What needs to be built]
**Priority**: This is the first thing to implement in Phase 1.
```

### 4. Hardening ADR Generation Template

The generated ADR follows this structure (automated, not manual):

```
# ADR-NNN: {Hub Name} Hardening

## Audit Summary
| Dimension | Score | Status | Key Finding |
|-----------|-------|--------|-------------|
(10 rows, one per dimension)

Composite Score: XX/100

## Wow Effect: {Name}
(Identified killer use case with flow description)

## Context
(Auto-generated from audit findings — what's broken, what's missing)

## Decision
### Phase 1: Wow Effect & Critical Gaps (score < 50 dimensions)
### Phase 2: Completeness (score 50-69 dimensions)
### Phase 3: Polish & Performance (score 70-89 dimensions)

## Consequences
(Auto-derived from changes)

## Implementation Prompt
(Auto-generated with team structure, agent roles, tiers, chains)
```

### 5. Team Splitting Strategy in Generated ADRs

Each generated hardening ADR includes an implementation prompt that maps dimensions to agents:

| Dimension | Primary Agent | Tier | Chain Reference |
|-----------|--------------|------|-----------------|
| UI Compliance | frontend | medium | `ui_quality_audit`, `redesign_page` |
| Page Coverage | developer | medium | — |
| API Completeness | developer | medium | — |
| MCP Tool Wiring | devops | low | — |
| Performance | frontend | medium | — |
| User Value | architect | high | — (advisory: prioritization) |
| Workflows | developer | medium | `generate_delight` |
| Cross-Hub Connectivity | developer | medium | — |
| Action Buttons | frontend | medium | — |
| Wow Effect | developer + frontend | high | Custom per hub |

**Parallel strategy**: Dimensions without cross-dependencies run in parallel teams.
**Pipeline strategy**: Wow Effect (Phase 1) → Completeness (Phase 2) → Polish (Phase 3).

### 6. Implementation: New Files

| File | Purpose |
|------|---------|
| `plugins/dev/skills/frontend/scripts/dashboard_hardening_audit.py` | Core audit engine — crawl, score, rank |
| `plugins/dev/skills/frontend/scripts/generate_hardening_adr.py` | ADR generation from audit results |
| `plugins/dev/skills/frontend/chains/dashboard_hardening.yaml` | Chain definition for the full workflow |
| `.claude/skills/harden/SKILL.md` | `/harden` slash command definition |
| `plugins/dev/frontend/hardening-reports/` | Audit result storage (YAML) |

### 7. Integration with Existing Infrastructure

The audit engine delegates to existing scripts, not reinventing:

| Check | Delegated To | How |
|-------|-------------|-----|
| UI screenshots | Chrome MCP `screenshot` | Via `mcp__claude-in-chrome__computer` |
| Design compliance | `pattern_compliance_audit.py` | Direct Python import |
| UI scoring | `rank_ui_visuals.py` | Direct Python import |
| API validation | `validate_dashboard.py` | Subprocess call |
| Page discovery | `generated-registry.ts` parsing | Read + parse |
| MCP tool validation | `mcp_tools.yaml` cross-ref | YAML parse |
| Console errors | Chrome MCP `read_console_messages` | Via MCP |
| Performance | `page-telemetry.ts` data | Read from telemetry store |

## Implementation Order

```
Phase 1: Audit Engine
├── Step 1: Create dashboard_hardening_audit.py with crawl + discovery logic
├── Step 2: Implement 10-dimension scoring functions
├── Step 3: Add wow-effect detection heuristics
└── Step 4: Output structured YAML audit report

Phase 2: ADR Generator (depends on Phase 1)
├── Step 5: Create generate_hardening_adr.py
├── Step 6: Implement template filling from audit YAML
├── Step 7: Auto-generate implementation prompt section
└── Step 8: Auto-generate team splitting tables

Phase 3: Slash Command & Chain (depends on Phase 2)
├── Step 9: Create /harden SKILL.md with Chrome MCP integration
├── Step 10: Create dashboard_hardening.yaml chain definition
└── Step 11: Register in skills registry

Phase 4: Verification
├── Step 12: Run /harden against http://localhost:3000/career as smoke test
├── Step 13: Verify generated ADR matches quality of hand-written ADR-061
└── Step 14: Run /harden against 3 different hubs, compare outputs
```

## Consequences

### Positive

- **10x faster hub audits** — automated crawl + score replaces 2-4 hours of manual inspection
- **Consistent quality** — every hub evaluated on the same 10 dimensions with the same weights
- **Wow effect first** — every hardening ADR leads with the killer demo use case, ensuring user value drives priority
- **Ready-to-execute ADRs** — generated ADRs include implementation prompts with team structure, eliminating the manual prompt-writing step
- **Audit history** — YAML reports stored in `plugins/dev/frontend/hardening-reports/` enable trend tracking

### Negative

- **Chrome MCP dependency** — the audit requires a running dashboard (`npm run dev`) and Chrome MCP connection; headless mode not supported
- **Wow effect heuristics are subjective** — the algorithm identifies candidates but a human should confirm the choice
- **Generated ADRs need review** — automation produces a draft, not a final ADR; developer must read and adjust before executing

### Neutral

- Existing manual hardening ADRs (ADR-061, ADR-064) remain valid; this standardizes future ones
- The 10-dimension framework can be used manually even without the automation (as a checklist)
- No changes to existing audit scripts — the engine composes them, not replaces them

## Alternatives Considered

### Alternative 1: Extend batch_ui_audit.py

Add all 10 dimensions to the existing `batch_ui_audit.py` script instead of creating a new engine.

**Rejected** because: `batch_ui_audit.py` runs the `ui_quality_audit` chain per route (visual-only), and its architecture is "run chain per page." The hardening workflow needs cross-page analysis (connectivity, wow effect), hub-level scoring (not per-page), and ADR generation — fundamentally different scope.

### Alternative 2: Nightly Automated Hardening

Run the full hardening audit every night via nightly executor, automatically generating ADRs for hubs below score threshold.

**Rejected** because: Hardening ADRs require human judgment (wow effect confirmation, priority override, scope decisions). Automatic ADR generation without review would produce noise. Better to keep it developer-triggered via `/harden`.

### Alternative 3: Dashboard-Embedded Scoring Only

Add a "Hub Health" widget to each dashboard page showing the 10 dimensions, without ADR generation.

**Rejected** because: Scoring without actionable output is monitoring, not hardening. The value is in the generated ADR with team structure and implementation prompt. Scoring can be a future addition (Phase 2 of this ADR) but the primary deliverable is the workflow.

## References

- ADR-047: Chatbot polish & resilience (hardening pattern)
- ADR-052: Claude debugging efficiency (Chrome MCP, background dev servers)
- ADR-056: Plugin health sweep (compliance framework)
- ADR-061: Career hardening (manual hardening ADR example)
- ADR-064: Google workspace hardening (manual hardening ADR example)
- `plugins/dev/skills/frontend/scripts/rank_ui_visuals.py` — UI scoring
- `plugins/dev/skills/frontend/scripts/pattern_compliance_audit.py` — design compliance
- `plugins/dev/skills/frontend/scripts/batch_ui_audit.py` — batch route discovery
- `.github/scripts/validate_dashboard.py` — API route validation
- `plugins/dev/skills/frontend/references/design-standards.md` — design standards
- `src/dashboard/lib/services/page-telemetry.ts` — performance telemetry

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-065: Dashboard Hardening Workflow Automation**.

Read the full ADR: `docs/decisions/ADR-065-dashboard-hardening-workflow.md`

### Offload Protocol (ADR-054)

Before dispatching each step, check if it can be offloaded to a cheap CLI:

1. Read offload config: `cat config/system/llm.yaml` → look for `offload:` section
2. If `offload.enabled: true` AND the step's tier is `low`:
   ```bash
   python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py \
     --task "STEP DESCRIPTION" \
     --files "TARGET_FILE_1,TARGET_FILE_2" \
     --context-files "REFERENCE_FILE_FOR_PATTERNS" \
     --work-dir $(pwd)
   ```
3. Review the JSON output — check `success`, `files_changed`, and `diff` fields
4. Record the verdict:
   - Accept (diff is correct): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict accept`
   - Fix (you patched the output): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict fix`
   - Escalate (offload failed, you did it yourself): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict escalate`
5. If `offload.enabled: false` OR tier is `medium`/`high` → do the step yourself as normal

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-065-dashboard-hardening", description="Implementing ADR-065: Dashboard Hardening Workflow Automation")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-065-dashboard-hardening", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-065 team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-065-dashboard-hardening`

#### Phase 1: Audit Engine
**Strategy**: PIPELINE (steps build on each other)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create `dashboard_hardening_audit.py` — crawl hub URL, discover all subpages from `generated-registry.ts`, map hub→skill→plugin→dashboard.yaml | `plugins/dev/skills/frontend/scripts/dashboard_hardening_audit.py` |
| 1.2 | developer | medium | Implement 10-dimension scoring functions — delegate to existing scripts (`pattern_compliance_audit.py`, `validate_dashboard.py`, `rank_ui_visuals.py`), compute weighted composite score | `plugins/dev/skills/frontend/scripts/dashboard_hardening_audit.py` |
| 1.3 | developer | high | Add wow-effect detection — scan action buttons for `flow: llm`, evaluate data richness, check end-to-end flows, identify cross-hub leverage points | `plugins/dev/skills/frontend/scripts/dashboard_hardening_audit.py` |
| 1.4 | developer | low | Output structured YAML audit report to `plugins/dev/frontend/hardening-reports/{hub}_{date}.yaml` | `plugins/dev/skills/frontend/scripts/dashboard_hardening_audit.py` |

#### Phase 2: ADR Generator (depends on Phase 1)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create `generate_hardening_adr.py` — read audit YAML, fill ADR template sections (metadata, context, audit summary table, wow effect) | `plugins/dev/skills/frontend/scripts/generate_hardening_adr.py` |
| 2.2 | developer | medium | Implement team-splitting logic — map dimensions to agents/tiers, determine parallel vs pipeline phases, generate implementation prompt section | `plugins/dev/skills/frontend/scripts/generate_hardening_adr.py` |
| 2.3 | developer | low | Auto-number ADR — read `docs/decisions/` to find next available number, write ADR file | `plugins/dev/skills/frontend/scripts/generate_hardening_adr.py` |

#### Phase 3: Slash Command & Chain (depends on Phase 2)
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Create `/harden` SKILL.md — define the slash command that accepts a URL, orchestrates Chrome MCP crawl + audit engine + ADR generation | `.claude/skills/harden/SKILL.md`, `plugins/ai/ai_bridge/skills/harden/SKILL.md` |
| 3.2 | devops | low | Create `dashboard_hardening.yaml` chain — wire up audit engine + ADR generator as a chain for programmatic execution | `plugins/dev/skills/frontend/chains/dashboard_hardening.yaml` |
| 3.3 | devops | low | Register `/harden` in skills registry and sync via `sync_agents.py` | `data/ide-integration/registry.yaml` |

#### Phase 4: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | validator | low | Run `/harden http://localhost:3000/career` as smoke test — verify audit completes and ADR is generated | — |
| 4.2 | architect | medium | Compare generated ADR quality against hand-written ADR-061 — verify all 10 dimensions scored, wow effect identified, implementation prompt is executable | — |
| 4.3 | validator | low | Run all existing tests (`pytest tests/src/`, `npm run build` in `src/dashboard/`) — verify no regressions | — |

### Completion Criteria
- [ ] `dashboard_hardening_audit.py` scores all 10 dimensions for a given hub URL
- [ ] `generate_hardening_adr.py` produces a complete ADR from audit results
- [ ] `/harden` slash command works end-to-end: URL → audit → scored ADR → implementation prompt
- [ ] Generated ADR for `/career` includes wow effect, team splitting, and chain references
- [ ] Audit reports saved to `plugins/dev/frontend/hardening-reports/`
- [ ] All existing tests pass (`pytest tests/src/`, `npm run build`)
- [ ] ADR-065 status updated to Accepted

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-065-dashboard-hardening-workflow.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
