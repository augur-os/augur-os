---
status: Implemented
date: '2026-02-07'
deciders:
- Augur Core Team
related:
- ADR-046 (Crew Orchestration Bridge)
- ADR-050 (Crew Skill Consolidation)
hub: null
tags:
- crew
- skill
- sharpening
- score
- based
superseded_by: null
---

# ADR-051: Crew Skill Sharpening — Score-Based Refactoring & Consolidation

## Context

After ADR-046 generated Claude Code subagent profiles for all 12 crew skills and ADR-050 absorbed misplaced scripts, a score-based audit reveals significant variance in how much value each crew skill provides over a generic agent.

Scored on a 1-100 scale (practical Augur value vs generic agent replacement):

| Tier | Skill | Score | Issue |
|------|-------|-------|-------|
| **Top** | developer | 95 | Strong — 9 chain integrations, TDD/RALPH, safe deletion |
| **Top** | frontend | 90 | Strong — Liquid Glass standards, design registry, hub rules |
| **Top** | architect | 85 | Strong — vision alignment, drift detection, blueprint system |
| **Top** | security | 80 | Strong — three-phase audit, hook-based warnings, OWASP |
| **Top** | validator | 75 | Solid — Playwright scripts, flaky quarantine, CI sharding |
| **Mid** | devops | 72 | Good — adaptive growth, IDE audit, but generic overlap in standard ops |
| **Mid** | analyst | 60 | Moderate — eval harness is unique, but usage analysis is generic |
| **Mid** | mcp-app-factory | 55 | Specific but rare — plugin wizard used infrequently |
| **Low** | data-engineer | 45 | Augur is YAML/file-based, not DB-heavy. Developer can handle migrations. |
| **Low** | oss-manager | 40 | Periodic use (releases only). `gh` CLI covers 80% of capability. |
| **Low** | design-system | 30 | Data resource, not an agent. Frontend already consumes the registry. |
| **Low** | plugins | 10 | Stub — 4 lines of capability. Generic agent does the same thing. |

Goals:
1. Raise every surviving skill to 75+ by adding Augur-specific wiring
2. Eliminate or merge skills under 50 that don't justify a separate subagent profile
3. Reduce total crew count from 12 to 8 focused, high-value agents

## Decision

### Phase 1: Delete and Merge Low-Score Skills (10-45)

#### plugins (score: 10) → DELETE

**Rationale**: 4-line stub with zero modules, zero chain integrations, zero references. Its capabilities (install/uninstall/list/check deps) are standard CLI commands any agent can run.

**Action**:
- Delete `plugins/dev/skills/plugins/` entirely <!-- removed: capabilities folded into devops -->
- Remove from `sync_agents.py` subagent generation
- Remove `.claude/agents/plugins.md` profile
- Any chain steps referencing `plugins:*` redirect to `devops` (dependency management is devops territory)

#### design-system (score: 30) → MERGE into frontend

**Rationale**: design-system is a data resource (component registry, block templates), not an agent that acts. Frontend already consumes it via MCP tools (`list-ui-blocks`, `get-component-info`, `suggest-blocks`).

**Action**:
- Move design-system data (component-registry.yaml) → keep as src/lib data at `data/core/skills/frontend/`
- Move MCP tools (`list-ui-blocks`, `get-block-template`, `suggest-blocks`, `get-component-info`, `search-components`) into frontend's MCP namespace
- Add design system capabilities to frontend SKILL.md:
  - "Component registry management"
  - "Block template suggestions"
  - "Design token ownership"
- Delete design-system as a standalone skill <!-- merged into plugins/dev/skills/frontend/ -->
- Remove `.claude/agents/design-system.md` profile

#### oss-manager (score: 40) → MERGE into devops

**Rationale**: Repo health, releases, and community docs are operational tasks. oss-manager is only active during releases. Devops already handles "pipeline status", "deploy", and "health check" — release management fits naturally.

**Action**:
- Move modules (`release-management.md`, `community-standards.md`, `repo-health.md`) → `plugins/dev/skills/devops/modules/`
- Add to devops SKILL.md:
  - "Release management with semantic versioning"
  - "Repository health auditing"
  - "Community docs maintenance"
  - "GitHub stars tracking"
- Add devops commands: `/prepare release`, `/check repo health`, `/update community docs`
- Move chain integration (`check_repo_health` in `open_source_release`) to point to `devops`
- Delete oss-manager as a standalone skill <!-- merged into plugins/dev/skills/devops/ -->
- Remove `.claude/agents/oss-manager.md` profile

#### data-engineer (score: 45) → MERGE into developer

**Rationale**: Augur is YAML/file-based, not a database-heavy project. The migration safety protocol and schema docs are valuable but infrequent. Developer already handles data-adjacent work (9 chain integrations including `data_migration`).

**Action**:
- Move modules (`migration-patterns.md`, `backup-procedures.md`, `vector-optimization.md`) → `plugins/dev/skills/developer/modules/`
- Add to developer SKILL.md:
  - "Migration safety protocol (backup → rollback → dry-run → execute → verify)"
  - "Schema management for YAML data structures"
  - "Vector index optimization"
- Add developer commands: `/run migration`, `/backup data`, `/schema docs`
- Move chain integration (`manage_schema`, `run_migration` in `data_migration`) to point to `developer`
- Move `data-engineer` protected areas (production_data, audit_logs) into developer's protected_areas
- Delete data-engineer as a standalone skill <!-- merged into plugins/dev/skills/developer/ -->
- Remove `.claude/agents/data-engineer.md` profile

### Phase 2: Sharpen Mid-Score Skills (55-72) to 75+

#### analyst (60 → target 80)

**Problem**: Usage analysis and prompt optimization are generic. The eval harness is unique but underconnected.

**Improvements**:
- **Add Augur-specific analytics modules**:
  - `modules/skill-usage-analytics.md` — analyze which skills/chains are used most, cost per skill, token efficiency
  - `modules/session-analytics.md` — session length, tool call patterns, context window utilization
  - `modules/cost-analytics.md` — tier routing effectiveness, model cost breakdown per workflow
- **Connect to the daemon's telemetry**: analyst should consume `runtime/logs/` and produce actionable reports
- **Add chain integrations**:
  - `cost_report` action → weekly cost breakdown by skill/tier
  - `skill_health` action → which skills are never used, which are overloaded
- **Add unique Augur commands**:
  - `/analyze skill usage` — which crew skills deliver value
  - `/cost report` — token spend by tier, preset, agent
  - `/context health` — context window utilization patterns

#### mcp-app-factory (55 → target 75)

**Problem**: Deeply Augur-specific but used infrequently. When needed, it's irreplaceable.

**Improvements**:
- **Add continuous audit mode**: instead of manual-only, auto-audit on pre-commit hook when plugin files change
- **Add chain integration**: `plugin_compliance` chain that runs during `/nightly`
- **Add bulk operations**:
  - `/audit all plugins` → already exists but needs to surface in chain workflows
  - `/export all crew` → batch export for OSS publishing
- **Connect to devops**: when devops runs `/prepare release`, mcp-app-factory's compliance audit should be a gate
- **Add templates for common patterns**: skill-with-dashboard, skill-with-mcp, skill-with-chain templates that capture Augur conventions

#### devops (72 → target 82, after oss-manager merge)

**Problem**: Standard ops (install deps, health check) are generic. Unique features (adaptive growth, IDE audit) are strong but disconnected.

**Improvements (in addition to oss-manager merge)**:
- **Strengthen IDE integration audit**: currently just health check — add auto-fix for common issues (missing MCP configs, stale tool registrations)
- **Add Augur-specific monitoring**:
  - `modules/mcp-health-monitor.md` — monitor MCP server health, restart on failure
  - `modules/context-budget.md` — track context window usage across sessions, alert on exhaustion patterns
- **Add commands**:
  - `/mcp health` — check all MCP servers, restart dead ones
  - `/context budget` — current context utilization and recommendations
- **Connect adaptive growth to analyst**: devops generates backlog from commits, analyst scores priorities

### Phase 3: Harden Top-Score Skills (75-95)

#### developer (95 → maintain)

Already strong. Minor improvements:
- **Add cost awareness**: when spawned at different tiers, developer should report estimated token cost for the task
- **Strengthen safe deletion**: add integration with validator (auto-run tests after each deletion step)
- **Add RALPH loop metrics**: track iterations, success rate, common failure patterns

#### frontend (90 → maintain)

Already strong. Minor improvements:
- **After design-system merge**: own the component registry MCP tools, add `/suggest components` command
- **Add visual regression baseline management**: auto-update baselines after approved changes
- **Strengthen hub page validation**: auto-check new pages against hub rules before commit

#### architect (85 → maintain)

Already strong. Minor improvements:
- **Add ADR generation**: when architect identifies a significant decision, auto-generate ADR draft using `write-adr` skill format
- **Connect vision drift to analyst**: when drift detected, analyst quantifies the impact
- **Add dependency graph visualization**: module that maps skill-to-skill, chain-to-chain dependencies

#### security (80 → maintain)

Already strong. Minor improvements:
- **Add supply chain audit**: scan `requirements.txt` and `package.json` for known compromised plugins
- **Strengthen hook integration**: expand real-time patterns to catch more categories (SSRF, open redirect, prototype pollution)
- **Add post-incident learning**: after security finding is fixed, auto-generate pattern for future detection

#### validator (75 → target 80)

Solid but could be sharper:
- **Add cross-browser baseline management**: track Playwright baselines per browser, auto-flag regressions
- **Strengthen flaky test analytics**: connect quarantine data to analyst for trending (which tests flake most, which pages are fragile)
- **Add test generation suggestions**: when developer creates a new feature, validator suggests test cases based on component patterns

## Consequences

### Positive

- Crew reduces from 12 to 8 focused, high-value agents
- Every surviving agent scores 75+ (strong Augur-specific value)
- No orphaned capabilities — everything merges cleanly into natural homes
- Subagent profiles become leaner (8 files vs 12)
- Swarm presets unchanged — they only use the 7 core agents already
- Chain references simplified — fewer agent names to maintain

### Negative

- One-time migration effort across SKILL.md files, chain YAMLs, and sync_agents.py
- Merged skills (devops, developer, frontend) get larger SKILL.md files
- Git history for merged modules requires `git log --follow`

### Neutral

- Swarm presets unaffected (they use architect, security, analyst, validator, developer only)
- Generated `.claude/agents/` profiles regenerated automatically by sync_agents.py
- External users of the gist prompt already use the lean 7-agent version

## Final State

| Skill | Score | Type | Key Augur Differentiators |
|-------|-------|------|---------------------------|
| developer | 95 | executor | 9+ chains, TDD/RALPH, safe deletion, migration protocol (from data-engineer) |
| frontend | 90 | executor | Liquid Glass, design registry + MCP tools (from design-system), hub rules |
| architect | 85 | advisory | Vision alignment, drift detection, ADR generation, blueprint system |
| devops | 82 | executor | Adaptive growth, IDE audit, MCP health, release management (from oss-manager) |
| security | 80 | advisory | Three-phase audit, real-time hooks, supply chain scan |
| analyst | 80 | advisory | Skill usage analytics, cost reporting, eval harness, context health |
| validator | 80 | advisory | Playwright scripts, flaky quarantine, cross-browser baselines |
| mcp-app-factory | 75 | executor | Plugin wizard, compliance audit, code transforms, nightly gate |

8 agents. All 75+. Zero stubs.

## Implementation Order

```
Phase 1: Delete & Merge (low-score cleanup)
├── Step 1: Delete plugins skill
├── Step 2: Merge design-system → frontend
├── Step 3: Merge oss-manager → devops
└── Step 4: Merge data-engineer → developer

Phase 2: Sharpen mid-score (add Augur-specific wiring)
├── Step 5: Analyst — add skill usage, cost, context analytics
├── Step 6: MCP-app-factory — add continuous audit, nightly gate
└── Step 7: DevOps — add MCP health, context budget

Phase 3: Harden top-score (minor improvements)
├── Step 8: Developer — cost awareness, RALPH metrics
├── Step 9: Frontend — component registry ownership
├── Step 10: Architect — ADR generation, dependency graph
├── Step 11: Security — supply chain audit, expanded hooks
└── Step 12: Validator — cross-browser baselines, test suggestions

Phase 4: Regenerate artifacts
└── Step 13: Run sync_agents.py → 8 profiles, updated registry
```

## Alternatives Considered

### Alternative 1: Keep All 12, Just Improve Low Scores

Add Augur-specific wiring to all 12 skills. Rejected because plugins (10) and design-system (30) don't justify separate agent sessions — they add coordination overhead without proportional value. Fewer, sharper agents > more, thinner agents.

### Alternative 2: Aggressive Merge to 5 Agents

Merge analyst→architect, validator→developer, leaving only architect, developer, security, devops, frontend. Rejected because analyst and validator have distinct enough roles in chain workflows (analyst produces reports, validator runs tests) that merging them would create confused dual-purpose agents.

### Alternative 3: Replace Low Agents with Prompt Snippets

Instead of merging, delete low-score agents entirely and capture their unique knowledge as reference docs that other agents load on demand. Rejected because the modules (migration-patterns, release-management, component-registry) are better preserved as first-class capabilities within their new host agent than as orphaned reference files.

## References

- ADR-046: Claude Code Crew Orchestration Bridge
- ADR-050: Crew Skill Consolidation
- Crew skill ranking audit (this session, 2026-02-07)
- `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` — regenerates all profiles
