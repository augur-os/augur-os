---
status: Implemented
date: '2026-01-27'
deciders:
- Augur Team
related: []
hub: null
tags:
- kernel
- minimal
- core
- architecture
superseded_by: null
---

# ADR-023: Kernel - Minimal Core Architecture

## Context

The Augur project follows Unix philosophy: small, composable tools that do one thing well. However, the current `src/` directory has grown to include:

- **68 Python scripts** in `.github/scripts/`
- **39 LLM integration files** in `src/llm/`
- **65+ UI components** in `src/dashboard/`
- Various modules, utilities, and infrastructure code

Many of these scripts are domain-specific tools that belong in plugins rather than core framework code. The name "src/lib" doesn't convey the critical nature of this code - it's not just "src/lib utilities" but the **plugins/ai/skills/ai_bridge** of the system.

### Current State

```
src/                          # Too broad - mixes plugins/ai/skills/ai_bridge and plugin concerns
├── scripts/                     # 68 files - many belong in plugins
│   ├── validate_*.py           # Kernel: validation framework
│   ├── audit_*.py              # Kernel: audit framework
│   ├── generate_*.py           # Kernel: registry generation
│   ├── skill_generator.py      # Plugin: belongs in factory
│   ├── sync_repos.py           # Plugin: belongs in crew
│   ├── ci_failure_analyzer.py  # Plugin: belongs in crew/devops
│   └── ...
├── config/                      # Kernel: path resolution, configuration
├── augur_logging/               # Kernel: centralized logging
├── plugins/                     # Kernel: plugin loader
├── llm/                         # Kernel: LLM infrastructure
├── dashboard/                   # Kernel: UI shell
└── modules/                     # Mixed: some plugins/ai/skills/ai_bridge, some plugin
```

### Problems

1. **Naming**: "src/lib" implies optional utilities, not critical infrastructure
2. **Bloat**: Scripts that should be plugin-owned live in src/lib
3. **Unclear boundaries**: Hard to know what's plugins/ai/skills/ai_bridge vs what's plugin-level
4. **Unix philosophy violation**: Kernel should be minimal, focused

## Decision

### 1. Rename `src/` → `src/`

The plugins/ai/skills/ai_bridge contains **only** essential framework code that:
- Is required for the system to boot
- Is used by ALL plugins (not just some)
- Defines contracts/interfaces between components
- Cannot be extracted without breaking the system

### 2. Kernel Contents (Minimal)

```
src/
├── config/                      # Path resolution, configuration
│   ├── paths.py                # Dynamic path system
│   ├── path_config.py          # 4-category config
│   └── mcp_tools.py            # Tool registry
├── augur_logging/               # Centralized logging
├── plugins/                     # Plugin loader/registry
├── llm/                         # LLM infrastructure (agent router, IDE adapters)
├── mcp/                         # MCP protocol infrastructure
├── boundaries/                  # Import guard validation
├── dashboard/                   # UI shell (Next.js app)
│   ├── components/             # Core UI components
│   ├── hooks/                  # Core hooks
│   ├── lib/                    # Utilities
│   └── app/                    # App shell (plugin content mounted here)
├── scripts/                     # ONLY framework scripts (~20)
│   ├── validate_*.py           # Validation framework
│   ├── audit_*.py              # Audit framework
│   ├── generate_registry.py    # Registry generation
│   ├── generate_instructions.py # IDE instructions
│   └── token_estimator.py      # Token estimation
├── modules/
│   └── retrospective.py        # Universal retrospective pattern
├── search/
│   └── ripgrep.py              # Search utility wrapper
├── reviews/                     # Review system types
├── skills/
│   └── registry.py             # Skill metadata
└── tests/                       # Kernel tests
```

### 3. Scripts Migration Map

#### Phase 1: Move to `plugins/ai/skills/mcp-app-factory/scripts/`

| Script | Purpose |
|--------|---------|
| `skill_generator.py` | Skill scaffolding |
| `generate_skill_readmes.py` | README generation |
| `generate_skill_ui.py` | UI scaffolding |
| `skill_porter.py` | Skill migration tool |
| `add_data_dir_to_dashboards.py` | Dashboard helper |

#### Phase 2: Move to `plugins/dev/skills/devops/scripts/`

| Script | Purpose |
|--------|---------|
| `dependency_tracker.py` | Dependency management |
| `ci_change_detector.py` | CI change detection |
| `ci_failure_analyzer.py` | CI failure analysis |
| `nightly_maintainer.py` | Scheduled maintenance |
| `service_healer.py` | Service recovery |
| `cleanup_processes.py` | Process cleanup |
| `cleanup_paths.py` | Path cleanup |
| `release.py` | Release automation |
| `migrate_to_monorepo.py` | Monorepo migration |

#### Phase 3: Move to `plugins/orchestration/skills/executor/scripts/`

| Script | Purpose |
|--------|---------|
| `sync_repos.py` | Git sync |
| `task_runner.py` | Task execution |
| `close_sprint.py` | Sprint closure |
| `sync_learnings.py` | Learning sync |
| `resolve_review.py` | Review resolution |
| `run_action_evals.py` | Action evaluation |
| `auto_sync_agent.py` | Auto sync |

#### Phase 4: Move to `plugins/observability/skills/daemon/scripts/` <!-- platform skill removed; functionality in daemon -->

| Script | Purpose |
|--------|---------|
| `configure_mcp.py` | MCP configuration |
| `ide_bridge.py` | IDE communication |
| `send_to_ide.py` | Send to IDE |
| `context_injector.py` | Context injection |

#### Phase 5: Move to `plugins/observability/skills/daemon/scripts/`

| Script | Purpose |
|--------|---------|
| `log_monitor.py` | Log monitoring |
| `monitor_buttons.py` | Button monitoring |

### 4. Kernel Scripts (Stay - ~20 files)

| Category | Scripts |
|----------|---------|
| **Validation** | `validate_structure.py`, `validate_boundaries.py`, `validate_file_placement.py`, `validate_dashboard.py`, `validate_budget.py` |
| **Audit** | `audit_paths.py`, `audit_data_separation.py`, `audit_logging.py`, `audit_git_hygiene.py` |
| **Registry** | `generate_registry.py`, `generate_list_registry.py`, `generate_instructions.py`, `generate_claude_config.py` |
| **Verification** | `verify_api_endpoints.py`, `verify_schema.py`, `check_runtime_gitignore.py`, `check_sizes.py` |
| **Utilities** | `slug_utils.py`, `yaml_utils.py`, `token_estimator.py`, `scan_code_markers.py` |

### 5. Import Path Changes

All imports change from:
```python
from src/lib.config.paths import get_project_root
from src/lib.augur_logging import get_entity_logger
```

To:
```python
from src.config.paths import get_project_root
from src.augur_logging import get_entity_logger
```

### 6. Implementation Sequence

1. **Create ADR** (this document)
2. **Rename directory**: `src/` → `src/`
3. **Update all imports** across codebase
4. **Move scripts** in phases (factory → crew → platform → daemon)
5. **Update CI/CD** pipelines and pre-commit hooks
6. **Update documentation** (CLAUDE.md, READMEs)
7. **Update IDE configurations** (.cursorrules, etc.)

## Consequences

### Positive

- **Clear naming**: "plugins/ai/skills/ai_bridge" conveys critical infrastructure
- **Minimal core**: Only essential code in plugins/ai/skills/ai_bridge
- **Unix philosophy**: Small, focused plugins/ai/skills/ai_bridge
- **Plugin ownership**: Domain tools owned by appropriate plugins
- **Easier navigation**: Clear boundaries between plugins/ai/skills/ai_bridge and plugins

### Negative

- **Breaking change**: All imports need updating
- **Migration effort**: Moving scripts requires updating references
- **Learning curve**: Team needs to understand new structure

### Neutral

- Plugins become more self-contained (good for modularity)
- Kernel becomes the "contract" between system components
- Clear criteria for "should this be in plugins/ai/skills/ai_bridge?"

## Migration Checklist

- [ ] Rename `src/` → `src/`
- [ ] Update all Python imports (`src/lib.` → `src.`)
- [ ] Update all TypeScript imports
- [ ] Update `CLAUDE.md` and `docs/agent-rules.md`
- [ ] Update `.cursorrules`, `.claude/settings.json`
- [ ] Update pre-commit hooks
- [ ] Update CI/CD workflows
- [ ] Move Phase 1 scripts (factory)
- [ ] Move Phase 2 scripts (crew/devops)
- [ ] Move Phase 3 scripts (orchestrator/executor)
- [ ] Move Phase 4 scripts (platform)
- [ ] Move Phase 5 scripts (daemon)
- [ ] Update plugin SKILL.md files
- [ ] Run full test suite
- [ ] Update path references in configs

## References

- ADR-014: Three-tier plugin architecture
- ADR-016: Monorepo migration
- ADR-022: Plugin standardization
- Unix Philosophy: https://en.wikipedia.org/wiki/Unix_philosophy
