---
status: Implemented
date: '2026-03-04'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- dev
- hardening
superseded_by: null
---

# ADR-223: Dev Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 93/100 | 12% | good | - |
| 2 | Page Coverage | 100/100 | 10% | good | - |
| 3 | API Completeness | 100/100 | 12% | good | - |
| 4 | MCP Tool Wiring | 85/100 | 10% | needs-work | 17 actions have mcp_tool field (API-wrapped pattern) |
| 5 | Performance | 87/100 | 10% | needs-work | Large page (389 lines): /dev/advisor/analytics |
| 6 | User Value | 100/100 | 15% | good | 89 real data files found across 5/5 skills |
| 7 | Workflows | 87/100 | 8% | needs-work | 26/27 actions are functionally executable (18 autonomous,... |
| 8 | Cross-Hub Connectivity | 100/100 | 5% | good | Links to 3 other hubs: /admin, /ai, /health |
| 9 | Action Buttons | 98/100 | 8% | good | 26/27 actions are fully-wired |
| 10 | Wow Effect | 100/100 | 10% | good | Best candidate: Audit Chains |

**Composite Score**: 95/100 (production-ready)

## Wow Effect: Audit Chains

> Audit chain execution and correctness

**Score**: 100/100

**Score breakdown**: static evidence 40/100 + runtime bonus 60 = 100/100

**Demo Flow**:
1. User clicks 'Audit Chains'
2. Action executes via the configured fast-action backend
3. UI confirms completion with updated data/view state

**Expected visible output**: Audit chain execution and correctness

**Current state**: 28 candidate actions/workflows evaluated with runtime verification
**Gap to demo-ready**: Runtime verified — polish the demo narrative and visible output for stakeholder walkthroughs

**Cross-hub leverage**: Pulls data from admin, ai, health

**Other candidates**:
- Memory Audit (40/100, fast_action)
- Refresh Telemetry (40/100, fast_action)
- Skill Health Score (40/100, fast_action)
- System Optimization (40/100, fast_action)

**Priority**: Execute in Phase 2, after Phase 1 consolidation/repatriation gates pass.

## Context

Automated hardening audit of **Dev** (http://localhost:3000/dev) on 2026-03-04.
Composite score: **95/100**.

All dimensions are scoring 70 or above. This hub is in good shape
and only needs targeted polish.

## Decision

Implement hardening in 3 phases, ordered by severity and user impact.

User-selected scope: **All Phases**.

### Phase 1: Page Consolidation & Repatriation

- Build an explicit ownership map for all current `/dev` routes and tabs (`/dev`, `/dev/advisor/analytics`, `/dev/developer/tools`, `/dev/developer/apis`, `/dev/frontend/audit`, `/dev/validator/compliance`)
- Consolidate `/dev` overview so it remains devops operations-first and does not accumulate generic or cross-domain actions
- Repatriate non-dev or weakly related pages/actions to their owning plugins/hubs; keep only explicitly dev-owned surface area in the `/dev` hub
- Add cross-hub links from `/dev` to any repatriated destinations to preserve discoverability
- If no repatriation candidates are found, record a no-op decision with rationale in the ownership matrix and keep routes unchanged

### Phase 2: Wow Effect & Critical Gaps

**Wow Effect** (current: 100/100):
- Best candidate: Audit Chains
- Description: Audit chain execution and correctness
- UI evidence: surfaced in 1 hub source files

### Phase 3: Polish & Performance

**MCP Tool Wiring** (current: 85/100):
- 17 actions have mcp_tool field (API-wrapped pattern)
- 6/7 source files have MCP/API tool calls
- MCP module registered with 27 tools

**Performance** (current: 87/100):
- Large page (389 lines): /dev/advisor/analytics
- No code splitting for large page: /dev/advisor/analytics
- Large page (708 lines): /dev/developer/apis

**Workflows** (current: 87/100):
- 26/27 actions are functionally executable (18 autonomous, 8 IDE-assisted)
- 1/27 actions are YAML-only with no working backend
- 2 chain workflow(s) found for this hub

## User Notes

Focus on /dev page consolidation and repatriate non-dev or weakly related surface area to owning plugins/hubs.

## Implementation Verification

Implementation completed on **2026-03-04** with worktree-local runtime verification.

- Final hardening audit (runtime-verified): `plugins/dev/skills/frontend/augur/data/hardening-reports/dev_20260304_post_impl_worktree_stabilized.yaml`
  - Composite: **97/100**
  - MCP Tool Wiring: **90/100**
  - Performance: **100/100**
  - Workflows: **90/100**
  - Wow Effect: **100/100**
  - Structural issues: **[]**
- Audit executed with worktree-scoped environment (`AUGUR_ROOT/AUGUR_CORE/AUGUR_USER`) to avoid cross-repo path bleed from global shell defaults.
- Ownership/repatriation artifact: `docs/exec-plans/2026-03-04-dev-route-ownership-matrix.md`
- Browser validation (Playwright MCP): `/dev` + dev subpages rendered with **0 console errors**.
- Wow demo evidence (Audit Chains surface):
  - Before: `runtime-dev-audit-chains-before.png`
  - After: `runtime-dev-audit-chains-after.png`
- Additional runtime evidence:
  - `runtime-dev-overview.png`
  - `runtime-dev-analytics.png`

## Consequences

### Positive

- Dev hub upgraded with standardized hardening across 4 scored dimensions plus explicit page consolidation scope
- Phase 2 preserves and validates the wow-effect demo flow
- Killer demo use case identified: Audit Chains

### Negative

- Requires implementation effort across 4 dimensions
- Some dimensions may require runtime testing (performance, cross-hub connectivity)

### Neutral

- Existing working features remain untouched
- Audit report stored for trend tracking

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065).
No manual alternatives were evaluated.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- Audit report: `dev` hub audit
- Audit timestamp: 2026-03-04T22:25:26.310207

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed: []
  patterns_deprecated:
    - grep: "page:\\s*/dev\\b"
      replacement: "Reserve /dev bindings for devops-owned overview actions; move unrelated actions to owner routes or document explicit exception."
  files_affected:
    - glob: "plugins/dev/skills/*/augur.yaml"
    - glob: "plugins/dev/skills/*/augur/data/actions/*.yaml"
    - glob: "plugins/dev/skills/*/augur/dashboard/**/*.tsx"
    - glob: "plugins/*/skills/*/augur.yaml"
    - glob: "docs/exec-plans/*dev*ownership*matrix*.md"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-223: Dev Hardening**.

Read the full ADR: `docs/decisions/ADR-223-dev-hardening.md`

User-selected scope: **All Phases**.
Execution focus: consolidate `/dev` pages and repatriate non-dev surface area to owning plugins/hubs.

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

1. **Create team**: `TeamCreate(team_name="adr-221-dev-hardening", description="Implementing ADR-223: Dev Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-221-dev-hardening", name="{role}",
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

**Team name**: `adr-221-dev-hardening`

#### Phase 1: Page Consolidation & Repatriation
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | architect | medium | Build `/dev` route ownership matrix and define keep/move decisions per tab/page/action based on plugin ownership | `plugins/dev/skills/*/augur.yaml`, `plugins/dev/skills/*/augur/dashboard/**`, `plugins/dev/skills/frontend/augur/data/hardening-reports/dev_20260304_local.yaml` |
| 1.2 | developer | medium | Consolidate `/dev` overview scope: keep devops operational controls on `/dev`, move advisor/developer/frontend/validator controls to their owning subpages | `plugins/dev/skills/advisor/augur/data/actions/*.yaml`, `plugins/dev/skills/developer/augur/data/actions/*.yaml`, `plugins/dev/skills/devops/augur/dashboard/page.tsx` |
| 1.3 | frontend | medium | Repatriate non-dev pages/actions to owning hubs/plugins and add cross-hub navigation fallbacks from `/dev` | `plugins/*/skills/*/augur.yaml`, `plugins/*/skills/*/augur/dashboard/**`, `plugins/dev/skills/devops/augur/dashboard/page.tsx` |

#### Phase 2: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

Dependency: complete Phase 1 and merge results before starting.

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | high | Preserve Wow Effect (100/100) with live demo validation: Best candidate: Audit Chains | `plugins/dev/skills/advisor/augur/dashboard`, `plugins/dev/skills/developer/augur/dashboard`, `plugins/dev/skills/devops/augur/dashboard` |

#### Phase 3: Polish & Performance
**Strategy**: PARALLEL

Dependency: complete Phase 2 and merge results before starting.

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | devops | low | Fix MCP Tool Wiring (85/100): 17 actions have mcp_tool field (API-wrapped pattern) | `plugins/dev/skills/advisor/augur/mcp/__init__.py`, `plugins/dev/skills/developer/augur/mcp/__init__.py`, `plugins/dev/skills/devops/augur/mcp/__init__.py` |
| 3.2 | frontend | medium | Fix Performance (87/100): Large page (389 lines): /dev/advisor/analytics | `plugins/dev/skills/advisor/augur/dashboard/analytics/page.tsx`, `plugins/dev/skills/developer/augur/dashboard/apis/page.tsx`, `plugins/dev/skills/developer/augur/dashboard/tools/page.tsx` |
| 3.3 | developer | medium | Fix Workflows (87/100): 26/27 actions are functionally executable (18 autonomous,... | `plugins/dev/skills/advisor/augur/data/actions`, `plugins/dev/skills/advisor/augur/data/chains`, `plugins/dev/skills/developer/augur/data/actions` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/dev in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all `mcp_tool` refs in `augur.yaml` and `augur/data/actions/*.yaml` against the current MCP tool registry/exposed server tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [x] `/dev` ownership matrix exists at `docs/exec-plans/2026-03-04-dev-route-ownership-matrix.md` and includes columns: route, current owner, keep/move decision, target route, rationale
- [x] Every action using `page: /dev` outside `plugins/dev/skills/devops` is either moved to an owning route or explicitly listed in the ownership matrix with no-op rationale
- [x] `/dev` overview UI is limited to devops operational controls, and any exception is documented in the ownership matrix
- [x] Repatriated surfaces (if any) have discoverability links from `/dev` to new owner locations
- [x] Wow Effect maintained at >= 95/100 with a verified live demo flow
- [x] Wow candidate is confirmed in hub UI source (action label/id binding), not manifest-only
- [x] Wow demo includes before/after screenshots showing visible output
- [x] MCP Tool Wiring improved from 85/100 to >= 90
- [x] Performance improved from 87/100 to >= 90
- [x] Workflows improved from 87/100 to >= 90
- [x] All phases executed
- [x] All tests pass (`pytest tests/`, `npm run build`)
- [x] Browser validation: page renders in Chrome MCP with zero console errors
- [x] MCP validation: all tool references in `augur.yaml` and `augur/data/actions/*.yaml` resolve to registered tools
- [x] No orphaned files or broken references
- [x] Every skill with dashboard contributions has an `augur.yaml` manifest (required for discovery and mount)
- [x] No structural integrity issues (`structural_issues` in audit report is empty)
- [x] ADR-223 status updated to Accepted
