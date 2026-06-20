---
status: Superseded
date: '2026-01-29'
deciders:
- Gur
related: []
hub: null
tags:
- plugin
- architecture
- refactoring
- bundle
- architecture
superseded_by: null
---

# ADR-029: Plugin Architecture Refactoring (4-Bundle Architecture)

**Supersedes**: Extends ADR-015-three-tier-plugin-architecture.md, ADR-022-plugin-standardization.md

## Context

The current plugin structure has grown organically to 29 chaotic bundles with unclear responsibilities. This creates confusion about:
- Where new skills should be placed
- Which bundle owns which capability
- How to find related functionality

**Key Insight**: Factory is CHAINS (use cases), not a bundle. The crew executes factory chains (plugin creation, refactoring, UI design).

## Decision

Restructure from 29 chaotic bundles to 4 clear bundles with distinct responsibilities.

### 1. New 4-Bundle Architecture

```
plugins/
├── crew/                    # WHO does work (team members)
│   └── skills/
│       ├── developer/           # Implements features
│       ├── validator/           # Tests & QA
│       ├── architect/           # Designs systems
│       ├── devops/              # Deploys & monitors
│       ├── security/            # Audits security
│       ├── data-engineer/       # Schema & migrations
│       ├── analyst/             # Merged: data-scientist + eval-harness
│       ├── frontend/     # UI creation & tokens
│       ├── design-system/       # UI component templates
│       └── mcp-app-factory/      # Plugin creation tools
│
├── orchestrator/            # HOW work is coordinated
│   └── skills/
│       ├── executor/            # Chain execution, parallel, state
│       ├── router/              # Tier selection, model routing
│       └── swarm/               # Multi-agent coordination
│
├── services/                # HORIZONTAL capabilities
│   └── skills/
│       ├── ai-bridge/           # LLM integration
│       ├── knowledge/           # RAG & docs
│       ├── capture/             # Voice memos, screenshots
│       └── channels/            # Notifications
│
└── apps/                    # VERTICAL domains (user life)
    └── skills/
        ├── career/              # Job search, interviews
        ├── health/              # Medical, fitness
        ├── finance/             # Budget, investments
        ├── lifestyle/           # Recipes, reading, travel
        ├── content/             # Social media, newsletters
        ├── venture-augur/       # Startup, investors
        └── ...                  # All other app bundles
```

### 2. Bundle Responsibilities

| Bundle | Question | Responsibility |
|--------|----------|---------------|
| **crew** | "Who does the work?" | Team members that operate on code (including plugin creation) |
| **orchestrator** | "How is work coordinated?" | Chain execution, routing, multi-agent |
| **services** | "What tools are available?" | Horizontal capabilities (LLM, knowledge, notifications) |
| **apps** | "What life domains?" | Vertical user applications |

**Note:** Factory is CHAINS (use cases), not a bundle. Plugin creation chains live in `crew/mcp-app-factory/chains/`.

### 3. Migration: What Moves Where

#### FROM `orchestrator/executor` → SPLIT:

| Component | Destination | Notes |
|-----------|-------------|-------|
| `agent_orchestrator.py` | `orchestrator/executor/` | Chain execution |
| `agent_tier_selector.py` | `orchestrator/router/` | Tier routing |
| `orchestrator_enhancements.py` | `orchestrator/executor/` | Parallel execution |
| `swarm_executor.py` | `orchestrator/swarm/` | Multi-agent |
| `ralph_persistence.py` | `orchestrator/executor/` | Rename to `execution_state.py` |
| Sprint planning scripts | **DELETE** | Outdated concept |
| Backlog scripts | **DELETE** | Each plugin has BACKLOG.md |
| GitHub sync scripts | **DELETE** | Not core functionality |

#### FROM `crew/` → CHANGES:

| Current Skill | Action | Notes |
|---------------|--------|-------|
| `frontend` | **KEEP** in crew | Creates UI components (factory = chains, not bundle) |
| `data-scientist` | **MERGE** into `analyst` | Metrics & analysis |
| `eval-harness` | **MERGE** into `analyst` | Agent evaluation |
| `oss-manager` | **DELETE** | Overlap with devops |
| `user-advocate` | **DELETE** | No clear purpose |
| `agent-manager` | **DELETE** | UI-only, minimal value |
| `security` | **RENAME** to `security` | Simpler |

#### FROM root bundles → CONSOLIDATE:

| Current | Destination |
|---------|-------------|
| `plugins/ai/` | `plugins/ai/skills/ai_bridge/` |
| `plugins/ai/` | `plugins/ai/skills/knowledge/` |
| `plugins/channels/` | `plugins/admin/skills/channels/` |
| `plugins/ai/` | `plugins/productivity/skills/apple/` |
| `plugins/career/` | `plugins/career/skills/career/` |
| `plugins/health/` | `plugins/health/skills/health/` |
| All other app bundles | `plugins/consulting/skills/{name}/` |

### 4. New `orchestrator` Bundle Structure

```
plugins/orchestration/
├── BUNDLE.md                    # Bundle overview
└── skills/
    ├── executor/                # Chain execution
    │   ├── SKILL.md
    │   ├── scripts/
    │   │   ├── chain_executor.py     # Was: agent_orchestrator.py
    │   │   ├── parallel_executor.py  # Was: orchestrator_enhancements.py
    │   │   └── execution_state.py    # Was: ralph_persistence.py
    │   └── lib/
    │       ├── chain_types.py
    │       └── execution_context.py
    │
    ├── router/                  # Tier & model routing
    │   ├── SKILL.md
    │   ├── scripts/
    │   │   └── tier_selector.py      # Was: agent_tier_selector.py
    │   └── config/
    │       └── tiers.yaml            # Tier definitions
    │
    └── swarm/                   # Multi-agent coordination
        ├── SKILL.md
        └── scripts/
            └── swarm_executor.py     # Keep name
```

### 5. New `analyst` Skill (Merged)

Combines `data-scientist` + `eval-harness`:

```
plugins/dev/skills/advisor/
├── SKILL.md
├── scripts/
│   ├── metrics/                 # From data-scientist
│   │   ├── usage_analyzer.py
│   │   └── performance_tracker.py
│   └── evaluation/              # From eval-harness
│       ├── agent_evaluator.py
│       └── benchmark_runner.py
└── modules/
    ├── metrics-analysis.md
    └── agent-evaluation.md
```

### 6. Files to DELETE

| File/Skill | Reason |
|------------|--------|
| `plan_sprint.py` | Outdated sprint concept |
| `prioritize_backlog.py` | Each plugin has BACKLOG.md |
| `triage_inbox.py` | No central inbox |
| `close_sprint.py` | Outdated sprint concept |
| `sync_backlog_to_github.py` | Not core functionality |
| `sync_repos.py` | Separate concern |
| `backlog_manager.py` | Plugin-level backlogs |
| `agent_backlog/` directory | Merge or delete |
| `batch_ui_audit.py` | Move to factory/frontend |
| `crew/oss-manager` | Overlap with devops |
| `crew/user-advocate` | No clear purpose |
| `crew/agent-manager` | UI-only, minimal value |
| Empty bundles | Clean up |

### 7. Chain Location: In Plugins (Discovered by Orchestrator)

**Decision:** Chains live in their owning plugin, orchestrator discovers them at runtime.

**Why:**
- Plugin is truly standalone (add/remove plugin = add/remove chains)
- No mounting complexity
- No build step for chains

**Plugin template update:**
```
plugins/{bundle}/skills/{skill}/
├── SKILL.md
├── scripts/
├── modules/
├── dashboard/           # UI (mounted to dashboard)
├── chains/              # Workflows (discovered by orchestrator)  <- NEW
│   └── {workflow}.yaml
└── mcp/
```

**Chain ownership by skill:**
```
plugins/dev/skills/developer/chains/
├── feature_development.yaml
└── bug_workflow.yaml

plugins/dev/skills/validator/chains/
├── code_review.yaml
└── qa_pipeline.yaml

plugins/dev/skills/validator/chains/
└── security_audit.yaml

plugins/career/skills/career/chains/
└── interview_prep.yaml

plugins/orchestration/skills/executor/patterns/
└── _verification_loop.yaml    # Shared patterns only
```

**Orchestrator discovery:**
```python
def discover_chains() -> list[Path]:
    return list(Path("plugins").glob("*/skills/*/chains/*.yaml"))
```

### 8. Data Directory Restructure

```
data/
├── crew/                        # Crew skill data (simplified)
│   ├── developer/
│   ├── validator/
│   ├── architect/
│   ├── devops/
│   ├── security/
│   ├── data-engineer/
│   └── analyst/
├── orchestrator/                # Orchestration runtime data
│   └── execution/               # Execution logs & state
├── services/
│   ├── ai-bridge/
│   ├── knowledge/
│   └── channels/
└── apps/
    ├── career/
    ├── health/
    └── ...
```

Note: Chains moved from `data/` to `plugins/` (in their owning skill).

### 9. Chain Migration Mapping

**Final chain destinations:**

| Chain | Current Location | New Location | Notes |
|-------|------------------|--------------|-------|
| **CREW** | | | |
| `feature_development` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/dev/skills/developer/chains/` | Developer workflow |
| `bug_workflow` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/dev/skills/developer/chains/` | Developer workflow |
| `code_review` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/dev/skills/validator/chains/` | Review workflow |
| `qa_pipeline` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/dev/skills/validator/chains/` | Testing workflow |
| `security_audit` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/dev/skills/validator/chains/` | Security workflow |
| `compliance_audit` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/dev/skills/validator/chains/` | SOC2/GDPR compliance |
| `incident_response` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/dev/skills/devops/chains/` | PICERL workflow |
| `data_migration` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/dev/skills/developer/chains/` | Migration workflow |
| `system_optimization` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/dev/skills/advisor/chains/` | Architecture refactoring |
| `open_source_release` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/dev/skills/devops/chains/` | Release workflow |
| **PLUGIN-FACTORY** | | | |
| `skill_refactoring` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/ai/skills/mcp-app-factory/chains/` | Plugin refactoring |
| `redesign_page` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/dev/skills/frontend/chains/` | UI redesign |
| `ui_quality_audit` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/dev/skills/frontend/chains/` | UI audit |
| `generate_delight` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/dev/skills/frontend/chains/` | UX personalization |
| **ORCHESTRATOR** | | | |
| `adaptive_growth_cycle` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/orchestration/skills/executor/chains/` | Self-improvement |
| `_verification_loop` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/orchestration/skills/executor/patterns/` | Shared pattern |
| **SERVICES** | | | |
| `knowledge_capture` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/ai/skills/knowledge/chains/` | Documentation |
| **APPS** | | | |
| `interview_prep` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/career/skills/career/chains/` | Career skill |
| `deal_pipeline` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/consulting/skills/client-ai-consulting/chains/` | Business skill |
| `investor_demo` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/professional/skills/venture-augur/chains/` | Venture skill |
| `product_launch` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/professional/skills/venture-augur/chains/` | Venture skill |
| `content_campaign` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | `plugins/career/skills/content/chains/` | Content skill |
| **DELETE** | | | |
| `sprint_execution` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | **DELETE** | Outdated sprint concept |
| `backlog_execution` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | **DELETE** | Outdated backlog concept |
| `new_feature` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | **DELETE** | Duplicate of feature_development |
| `experiment_lifecycle` | `plugins/ai/skills/ai_bridge/augur/ide-integration/chains/` | **DELETE** | Uses non-existent agents |

### 10. Migration Order

1. **Create bundle structure** (mkdir)
2. **Move orchestrator scripts** (git mv from executor)
3. **Delete outdated scripts** (sprint, backlog, sync)
4. **Move frontend to factory** (git mv)
5. **Create analyst skill** (merge data-scientist + eval-harness)
6. **Consolidate singleton bundles** (move to services/ and apps/)
7. **Delete empty bundles**
8. **Move chains to owning plugins** (git mv per chain mapping table)
9. **Delete deprecated chains** (sprint_execution, backlog_execution, new_feature, experiment_lifecycle)
10. **Update all imports** (grep + sed)
11. **Update dashboard references**
12. **Run tests**
13. **Update documentation**

## Implementation Status

### Completed
- [x] Directory restructure: `plugins/ai/skills/ai_bridge/` -> `src/`
- [x] Test migration: `tests/plugins/ai/skills/ai_bridge/` -> `tests/`
- [x] Updated all CI workflows for new paths
- [x] Updated all audit scripts for new paths
- [x] Updated jest.config.js for new test locations
- [x] Fixed all `plugins/ai/skills/ai_bridge/` references in plugin files

### Phase 6 (Completed)
- [x] Create 4-bundle structure
- [x] Move orchestrator scripts from executor
- [x] Consolidate singleton bundles into services/apps
- [x] Move chains to owning plugins
- [x] Delete deprecated skills and chains
- [x] Update dashboard registry
- [x] Full test pass

### Phase 7: External MCP Dependencies (Completed)
- [x] External MCP registry: `config/integrations/external_mcp_registry.yaml`
- [x] Env var secrets template: `config/integrations/.env.mcp.example`
- [x] `configure_mcp.py` extended with external MCP resolution
- [x] CLI flags: `--no-external`, `--list-external`, `--validate`
- [x] SKILL.md declarations: career→brightdata, knowledge→context7, developer→context7
- [x] Plugin dependencies guide updated with external MCP section
- [x] SKILL.md template updated with mcp_servers examples

## Acceptance Criteria

**Bundle Structure:**
- [x] 4 bundles created: crew, orchestrator, services, apps
- [x] All singleton bundles consolidated into appropriate bundle
- [x] Empty bundles deleted (plugins/data/ removed)

**Orchestrator Bundle:**
- [x] `executor` skill with chain execution
- [x] `router` skill with tier selection
- [x] `swarm` skill with multi-agent coordination
- [x] Sprint/backlog scripts migrated from project-manager

**Crew Bundle:**
- [x] `analyst` skill created (merged data-scientist + eval-harness)
- [x] `security` skill (renamed from security-engineer)
- [x] `frontend` skill (renamed from frontend-design)
- [x] `mcp-app-factory` skill (renamed from plugin-factory)
- [x] `oss-manager` skill (renamed from repo-manager)
- [x] `user-advocate` deleted (UX responsibilities merged into frontend)
- [x] `project-manager` deleted (migrated to orchestrator/executor)

**Services & Apps:**
- [x] All horizontal services in `services/`
- [x] All vertical apps in `apps/`

**Technical:**
- [x] All imports updated (global find/replace across 300+ files)
- [x] All dashboard references updated
- [x] All agent tests passing (15/15), build passes
- [x] Documentation updated

## Consequences

### Positive
- **Clear ownership**: Each bundle has a single responsibility
- **Discoverable**: Easy to find where functionality lives
- **Extensible**: Clear pattern for adding new skills
- **Self-contained**: Chains live with their owning skill

### Negative
- **Migration effort**: Many file moves and import updates
- **Temporary breakage**: Dashboard references need updating
- **Learning curve**: Team needs to learn new structure

### Mitigations
- Automated migration scripts
- Comprehensive import updates via grep/sed
- Clear documentation of new structure

## References

- ADR-015: Three-Tier Plugin Architecture
- [ADR-022: Plugin Standardization](./ADR-022-plugin-standardization.md)
- [ADR-019: Claude Practices Improvement Plan](./ADR-019-claude-practices-improvement-plan.md) (Phase 6)
