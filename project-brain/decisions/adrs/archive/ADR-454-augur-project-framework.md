---
status: Implemented
date: 2026-03-19
deciders:
  - Gur Sannikov
related:
  - ADR-270
  - ADR-426
  - ADR-440
hub: null
tags:
  - architecture
  - multi-project
  - paths
  - plugins
superseded_by: null
---

# ADR-454: Augur Project Framework

## Context

Augur is a single-instance system — the monorepo IS "the project." There's no way to run multiple independent projects, each with their own plugins, data, and runtime. A developer starting a new project can't use Augur's infrastructure (skills, vault, dashboard, MCP tools) without inheriting all of Augur's domain skills (career, life, etc.).

The augur-os open-source repo needs to serve as a minimal template that developers clone to create new projects. Each clone should be fully self-contained with isolated paths, plugins, and daemons.

## Decision

### 1. Multi-project via multiple clones

Each Augur clone IS a project. The file system IS the isolation boundary. No project registry, no namespace nesting.

### 2. Project identity via project.yaml

Each clone has a `project.yaml` at the repo root with `name` (unique identifier, scopes all external paths), `port` (dashboard port), and `plugins` (lockfile of installed plugins with versions).

### 3. Unified base plugin

Consolidate augur, augur-system, and augur-marketplace into a single `augur` base plugin with 9 skills: onboard, daemon, discovery, file-manager, save, import, kill-augur, updater, skillstore. Everything else is opt-in.

### 4. augur-ops plugin (new)

Extract 8 operational skills from augur-system into a new opt-in `augur-ops` plugin: observe, metrics, ops-daemon, dev-loops, channels, remote-access, system-cleanup, workflows. The `augur-system` plugin name is retired.

### 5. Scoped external directories

All external paths derive from `get_project_name()` reading `project.yaml`: vault (`~/Vault/{name}/`), documents (`~/Documents/{name}/`), runtime, RAG, logs, cache, and LaunchAgent plists — all scoped by project name. Falls back to `"Augur"` for backward compatibility.

### 6. One daemon per clone

Each project runs its own daemon with scoped PID files, sockets, logs, and LaunchAgent plists. No global orchestrator.

### 7. Frontmatter-driven plugin install

Plugins are distribution units containing skills mastered by different clients. `augur install` reads `x-augur-master` frontmatter (claude-code, augur, codex, gemini) and routes each skill to the correct install location. Full copies per project (like node_modules).

### 8. UI is fully optional

Dashboard is an opt-in plugin. Browse experience is emergent from installed plugins. Each clone runs on its own port.

### 9. augur init CLI

`augur init myapp` clones augur-os, writes project.yaml, creates scoped external dirs, generates MCP config, and runs onboard. Manual path (clone + edit + onboard) is equivalent.

## Consequences

### Positive

- Developers can create new projects with Augur infrastructure without inheriting domain skills
- Each project is fully isolated — different plugin versions, separate data, independent daemons
- augur-os becomes a clean, minimal template for open-source adoption
- Base plugin is small (9 skills) — fast onboarding
- Existing Augur (Project0) keeps working unchanged — just add `project.yaml`

### Negative

- Plugin copies increase disk usage (each project has its own copy)
- No cross-project awareness — can't search across projects from one place
- Shell shortcuts need updating to accept project argument
- Multiple daemons consume more resources than a shared daemon

### Neutral

- path.py changes are backward-compatible (fallback to "Augur")
- Worktrees remain a within-project concern, separate from multi-project
- Env var overrides still work but are process-scoped (override all projects)

## Alternatives Considered

### Alternative 1: Shared plugin code with per-project config/data

Plugins installed once, all projects reference same code. Rejected because projects can't pin different versions and upgrading a plugin affects all projects.

### Alternative 2: Project namespace within single instance

Per-project vault paths (`~/Vault/Augur/projects/{id}/`), single daemon aware of all projects. Rejected for complexity — a project registry and namespace nesting adds coupling. Multiple clones is simpler and more Unix-like.

### Alternative 3: Global daemon managing multiple projects

Single daemon that discovers and manages all clones. Rejected because it couples projects and defeats the "each clone is independent" philosophy.

## References

- Design spec: `docs/superpowers/specs/2026-03-19-augur-project-framework-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-19-augur-project-framework.md`
- ADR-270: Data separation (code repo vs. vault vs. runtime state)
- ADR-426: Claude Code-mastered skills
- ADR-440: Open-source launch

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - "~/Vault/Augur/ → ~/Vault/{project_name}/"
    - "~/Documents/Augur/ → ~/Documents/{project_name}/"
    - "~/Library/Application Support/Augur/ → ~/Library/Application Support/{project_name}/"
    - "~/Library/Logs/Augur/ → ~/Library/Logs/{project_name}/"
    - "~/Library/Caches/Augur/ → ~/Library/Caches/{project_name}/"
  apis_changed:
    - "src/config/paths.py: all external path functions now derive from get_project_name()"
    - "PLUGIN_BUNDLES constant replaced with get_plugin_bundles() function"
  patterns_deprecated:
    - "augur-system plugin name → split into augur (base) + augur-ops (opt-in)"
    - "Hardcoded 'Augur' in path functions → get_project_name() from project.yaml"
    - "Hardcoded port 3000 in daemon scripts → get_project_port() from project.yaml"
    - "com.augur.daemon plist label → com.{name}.daemon"
  files_affected:
    - "src/config/paths.py"
    - ".claude/skills/*/SKILL.md (16 re-tagged)"
    - ".claude/skills/daemon/scripts/*.py"
    - "project.yaml (new)"
```

## Implementation Prompt

**Team name**: `adr-454-project-framework`

### Phase 1: Project Identity and Path Infrastructure
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | paths-dev | low | Create project.yaml at repo root (name: Augur, port: 3000) | `project.yaml` |
| 1.2 | paths-dev | medium | Add get_project_name(), get_project_port() with caching to paths.py | `src/config/paths.py`, `tests/unit/test_project_name.py` |
| 1.3 | paths-dev | medium | Replace hardcoded "Augur" in all external path functions with get_project_name() | `src/config/paths.py`, `tests/unit/test_scoped_paths.py` |
| 1.4 | paths-dev | medium | Replace PLUGIN_BUNDLES with get_plugin_bundles() dynamic function, update all importers | `src/config/paths.py`, `src/plugins/skill_registry.py`, `src/mcp/augur_mcp/*.py`, `tests/unit/test_dynamic_discovery.py` |

### Phase 2: Daemon Isolation
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | daemon-dev | medium | Scope plist labels by project name, replace hardcoded port 3000 with get_project_port() | `.claude/skills/daemon/scripts/service_healer.py`, `dashboard_monitor.py`, `cleanup_processes.py`, `notification_service.py`, `schedule_executor.py`, `insight_scanner.py` |
| 2.2 | daemon-dev | low | Parameterize plist template labels | `.claude/skills/daemon/assets/plists/*.template` |

### Phase 3: Plugin Restructuring
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | retag-dev | low | Re-tag 7 base skills from augur-system to augur + skillstore to augur | 8 SKILL.md files |
| 3.2 | retag-dev | low | Re-tag 8 ops skills from augur-system to augur-ops | 8 SKILL.md files |

### Phase 4: augur-os Template
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | template-dev | high | Rebase augur-os to latest Augur, strip to base plugin, create minimal CLAUDE.md | augur-os repo |
| 4.2 | template-dev | medium | Test dual-clone coexistence (path isolation, daemon independence) | validation |

### Phase 5: CLI and Documentation
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | cli-dev | medium | Build augur init CLI (clone, project.yaml, dirs, MCP config) | `.claude/skills/onboard/scripts/augur_init.py`, `tests/unit/test_augur_init.py` |
| 5.2 | docs-dev | low | Document multi-project shell shortcuts | `docs/references/shell-shortcuts.md` |

### Completion Criteria
- [ ] project.yaml exists at repo root with name: Augur, port: 3000
- [ ] All external paths scoped by get_project_name() — verified with tests
- [ ] PLUGIN_BUNDLES replaced with dynamic get_plugin_bundles()
- [ ] Daemon plists and ports scoped by project name
- [ ] 9 base skills tagged x-augur-plugin: augur
- [ ] 8 ops skills tagged x-augur-plugin: augur-ops
- [ ] Zero references to augur-system in SKILL.md frontmatter
- [ ] augur-os stripped to base template
- [ ] Two clones run simultaneously with isolated paths and daemons
- [ ] augur init creates a working project from augur-os template
- [ ] All phases executed
- [ ] All tests pass
- [ ] ADR status updated to Implemented
