---
status: Implemented
date: '2026-02-28'
deciders:
- Project team
related:
- ADR-163 (Config Decentralization)
- ADR-165 (Decentralized Skill Navigation Discovery)
- ADR-126 (Generic Plugin Template)
- ADR-174 (Skill & Command Consolidation)
- ADR-175 (Command Naming Alignment)
- ADR-053 (Slash Command Restructure)
- ADR-171 (Bidirectional Plugin Sync)
hub: null
tags:
- decentralized
- slash
- command
- discovery
superseded_by: null
---

# ADR-178: Decentralized Slash Command Discovery

## Context

All 40 slash command workflows and 17 rich skills are centralized in a single plugin: `plugins/ai/skills/ai_bridge/augur/data/`. This includes commands like `/dev-build`, `/ops-daemon`, `/test-ui`, `/post`, `/rag`, and `/save` — commands that clearly belong to other plugins (`dev/devops`, `observability/daemon`, `dev/frontend`, `career/content`, `ai/rag`, `admin/file-manager`).

This violates **Critical Rule #1** (plugin decentralization). The current structure means:
- Editing the devops workflow requires navigating to the ai_bridge plugin
- Adding a new command for a plugin requires touching ai_bridge, not the plugin itself
- Plugin self-containment is broken — a plugin cannot ship with its own commands
- The ai_bridge skill has become a monolithic command registry (57 files across `agent-workflows/` and `skills/`)

The precedent is already established. ADR-163 decentralized MCP tool config from centralized YAML into per-plugin `augur.yaml`. ADR-165 decentralized navigation from hardcoded lists into `augur.yaml` nav declarations. ADR-126 established the plugin template with `contributions` sections in `augur.yaml`. This ADR applies the same proven pattern to slash commands.

## Decision

### 1. Add `contributions.commands` to augur.yaml

Each plugin declares its commands in its own `augur.yaml`:

```yaml
# plugins/dev/skills/devops/augur.yaml
contributions:
  commands:
  - id: dev-build
    type: workflow          # 'workflow' = simple .md, 'skill' = rich SKILL.md
    visibility: dev
    description: "Clean caches, rebuild UI, validate pages, or quick-reload the dev server"
  - id: dev-debug
    type: skill
    visibility: dev
    description: "A rigorous 6-phase debugging protocol with autonomous visibility"
```

**Fields:**
- `id` (required): Command name (without `/` prefix)
- `type` (required): `workflow` or `skill`
- `visibility` (required): `core`, `dev`, `ops`, `test`, `orch`, or `hidden`
- `description` (required): Short description (max 80 chars, displayed in `/commands`)
- `alias` (optional): Alternative name (e.g., `dev_build` for `dev-build`)

### 2. Command file convention

Commands live inside the declaring plugin at a conventional path:

```
plugins/{bundle}/skills/{skill}/
├── commands/                    # NEW: command definitions
│   ├── dev-build.md            # type: workflow — simple markdown
│   ├── dev-debug/              # type: skill — rich multi-phase
│   │   └── SKILL.md
│   └── dev-merge.md
├── augur.yaml                   # declares contributions.commands
└── ...
```

**Rules:**
- `type: workflow` → `commands/{id}.md` (simple markdown with optional frontmatter)
- `type: skill` → `commands/{id}/SKILL.md` (rich SKILL.md format)
- Frontmatter in the .md files is **informational only** — `augur.yaml` is the source of truth for visibility, description, and alias (eliminates dual-source-of-truth issues from ADR-053)

### 3. Update discovery pipeline

**A. `discovery.py` — new `scan_distributed_commands()` function**

```python
def scan_distributed_commands(project_root: Path) -> list[dict]:
    """Scan all augur.yaml files for contributions.commands declarations.

    Returns list of command dicts with keys:
    - id, type, visibility, description, alias
    - source_path: absolute path to the .md or SKILL.md file
    - plugin: "{bundle}/{skill}" identifier
    """
```

This function:
1. Iterates `plugins/*/skills/*/augur.yaml`
2. Reads `contributions.commands` from each
3. Resolves `source_path` using the convention: `{skill_dir}/commands/{id}.md` or `{skill_dir}/commands/{id}/SKILL.md`
4. Validates the file exists (warns if missing)
5. Returns merged list sorted by visibility category then name

**B. `sync_agents.py` — update `_iter_all_commands()`**

Replace the current hardcoded dual-source scan with:

```python
def _iter_all_commands(skills_dir: Path) -> list[tuple[str, str, str, bool]]:
    # 1. Distributed commands from augur.yaml (all plugins)
    distributed = scan_distributed_commands(PROJECT_ROOT)

    # 2. Remaining ai_bridge commands (not yet migrated)
    ai_bridge_workflows = scan_workflows(SOURCE_WORKFLOWS)
    ai_bridge_skills = scan_ai_bridge_skills(SOURCE_SKILLS)

    # 3. Merge: distributed takes priority over ai_bridge fallback
    # (allows gradual migration — a command in augur.yaml shadows ai_bridge)
```

This enables **gradual migration** — commands can be moved one plugin at a time, and the old location is shadowed by the new declaration.

**C. `generate_registry.py` — update `scan_workflows()`**

Same pattern: scan distributed commands first, fall back to ai_bridge for unmigrated commands.

### 4. Command ownership mapping

| Commands | Target Plugin | Reason |
|----------|---------------|--------|
| `/dev-build`, `/dev-debug`, `/dev-export`, `/dev-fix`, `/dev-merge`, `/dev-retro`, `/dev-review`, `/dev-tidy` | `dev/devops` | Development lifecycle commands |
| `/ops-audit`, `/ops-debt`, `/ops-docs`, `/ops-hygiene`, `/ops-refactor`, `/ops-rollback`, `/ops-tabs` | `dev/devops` | Devops maintenance commands |
| `/ops-plugin-lint`, `/ops-optimize`, `/auto-fix` | `dev/devops` | Plugin tooling (skills) |
| `/test-client`, `/test-coverage`, `/test-adr` | `dev/validator` | Test execution commands |
| `/test-nightly` | `dev/validator` | Nightly test suite (skill) |
| `/test-ui` | `dev/frontend` | Browser UI testing |
| `/ops-daemon`, `/test-heal`, `/ops-loops` | `observability/daemon` | Daemon lifecycle commands |
| `/ops-inspect`, `/ops-kill` | `observability/observe` | System observability |
| `/ops-perf` | `observability/observe` | Performance profiling |
| `/danit`, `/post` | `career/content` | Content pipeline commands |
| `/rag` | `ai/rag` | RAG index management |
| `/save` | `admin/file-manager` | Asset management (skill) |
| `/import`, `/notion-import`, `/skill-setup` | `admin/updater` | Admin tooling (skills) |
| `/harden` | `admin/updater` | Skill auditing (skill) |
| `/adr`, `/write-adr`, `/implement-adr` | `dev/devops` | ADR management |
| `/ask`, `/commands`, `/focus`, `/guide`, `/learn`, `/onboard`, `/ops-memory`, `/ops-sync` | `ai/ai_bridge` | **Stays** — core agent infrastructure |
| `/orch-audit`, `/orch-dispatch` | `ai/ai_bridge` | **Stays** — orchestration infrastructure |
| `/adaptive-history`, `/adaptive-review` | `ai/ai_bridge` | **Stays** — adaptive command system |

**~35 commands move** to their natural plugins. **~12 commands stay** in ai_bridge (true agent/orchestration infrastructure).

### 5. Assembled output

At sync time, `sync_agents.py` produces the same outputs as today:
- `.claude/skills/{command-name}.md` — per-command skill files
- `CLAUDE.md` — tiered command listing
- IDE adapter files (`.cursorrules`, `AGENTS.md`, etc.)

The assembled output is **identical** to today — only the source changes. No downstream consumer needs modification.

## Consequences

### Positive
- Plugins become truly self-contained: add a command = add it to the plugin, not ai_bridge
- ai_bridge shrinks from 57 command files to ~12 (its own infrastructure commands)
- New plugin scaffolding (`/skill-setup`) can include a `commands/` directory
- Gradual migration: shadow-based priority means commands move one at a time with zero downtime
- Follows the proven `contributions.*` pattern from ADR-163/165/126

### Negative
- `sync_agents.py` scan time increases slightly (reads all augur.yaml, not one directory)
- During migration period, commands exist in two places (old location + new declaration)
- Discovery debugging requires checking augur.yaml across plugins, not one folder

### Neutral
- All generated outputs (`.claude/skills/`, `CLAUDE.md`, IDE configs) remain unchanged
- Command naming (ADR-175), visibility tiers (ADR-053), and alias system are preserved
- The adaptive command system (ADR-102) works the same — it reads from assembled registry

## Implementation Order

```
Phase 1: Discovery Infrastructure
├── Step 1: Add scan_distributed_commands() to discovery.py
├── Step 2: Update _iter_all_commands() in sync_agents.py to merge distributed + fallback
└── Step 3: Update scan_workflows() in generate_registry.py

Phase 2: Migrate dev/devops commands (16 commands — largest batch)
├── Step 4: Create plugins/dev/skills/devops/commands/ directory
├── Step 5: Move 16 workflow .md files + 4 skill directories
├── Step 6: Add contributions.commands to plugins/dev/skills/devops/augur.yaml
└── Step 7: Remove moved files from ai_bridge, verify shadow resolution

Phase 3: Migrate remaining plugins (19 commands across 7 plugins)
├── Step 8: Move observability commands (daemon, observe — 6 commands)
├── Step 9: Move career/content commands (danit, post — 2 commands)
├── Step 10: Move ai/rag command (rag — 1 command)
├── Step 11: Move admin commands (save, import, notion-import, skill-setup, harden — 5 commands)
├── Step 12: Move dev/validator commands (test-client, test-coverage, test-adr, test-nightly — 4 commands)
└── Step 13: Move dev/frontend command (test-ui — 1 command)

Phase 4: Cleanup and Verification
├── Step 14: Delete emptied ai_bridge/augur/data/agent-workflows/ and skills/ directories for migrated commands
├── Step 15: Update ops-plugin-lint to validate contributions.commands declarations
└── Step 16: Run sync_agents.py --check, verify identical output
```

## Alternatives Considered

### A. Keep commands centralized, add symlinks from plugins

**Rejected**: Symlinks break on Windows, complicate git, and don't achieve real decentralization. Plugins still can't ship their own commands.

### B. Move commands but keep discovery centralized (hardcoded path list)

**Rejected**: Replacing one hardcoded path with many hardcoded paths. Doesn't scale with new plugins and violates the auto-discovery principle from ADR-163/165.

### C. Use augur.yaml `commands:` at top level instead of `contributions.commands`

**Rejected**: The `contributions` namespace is the established pattern for cross-cutting declarations (pages, actions, commands). Breaking convention for commands would be inconsistent.

## References

- [ADR-163: Config Decentralization](ADR-163-config-decentralization.md) — established the `augur.yaml` assembly pattern
- [ADR-165: Decentralized Skill Navigation Discovery](ADR-165-decentralized-skill-nav-discovery.md) — nav declarations in augur.yaml
- ADR-126: Generic Plugin Template — plugin structure with `contributions`
- [ADR-174: Skill & Command Consolidation](ADR-174-skill-command-consolidation.md) — reduced 54→37 commands
- [ADR-175: Command Naming Alignment](ADR-175-command-naming-alignment.md) — established naming conventions
- [ADR-053: Slash Command Restructure](ADR-053-slash-command-restructure.md) — visibility tiers
- ADR-171: Bidirectional Plugin Sync — sync_agents.py architecture

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "plugins/ai/skills/ai_bridge/augur/data/agent-workflows/"
      to: "plugins/*/skills/*/commands/"
      scope: "plugins/ai/skills/ai_bridge/scripts/, src/dashboard/scripts/"
    - from: "plugins/ai/skills/ai_bridge/augur/data/skills/"
      to: "plugins/*/skills/*/commands/"
      scope: "plugins/ai/skills/ai_bridge/scripts/"
  apis_changed:
    - function: _iter_all_commands
      module: plugins.ai.skills.ai_bridge.scripts.sync_agents
      breaking: false  # signature unchanged, sources expanded
    - function: scan_workflows
      module: src.dashboard.scripts.generate_registry
      breaking: false  # return shape unchanged
  patterns_deprecated:
    - grep: "SOURCE_WORKFLOWS.*agent-workflows"
      replacement: "scan_distributed_commands(PROJECT_ROOT)"
    - grep: "SOURCE_SKILLS.*data/skills"
      replacement: "scan_distributed_commands(PROJECT_ROOT)"
  files_affected:
    - glob: "plugins/ai/skills/ai_bridge/augur/lib/discovery.py"
    - glob: "plugins/ai/skills/ai_bridge/scripts/sync_agents.py"
    - glob: "src/dashboard/scripts/generate_registry.py"
    - glob: "plugins/dev/skills/devops/augur.yaml"
    - glob: "plugins/observability/skills/daemon/augur.yaml"
    - glob: "plugins/observability/skills/observe/augur.yaml"
    - glob: "plugins/career/skills/content/augur.yaml"
    - glob: "plugins/ai/skills/rag/augur.yaml"
    - glob: "plugins/admin/skills/file-manager/augur.yaml"
    - glob: "plugins/admin/skills/updater/augur.yaml"
    - glob: "plugins/dev/skills/validator/augur.yaml"
    - glob: "plugins/dev/skills/frontend/augur.yaml"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-178: Decentralized Slash Command Discovery**.

Read the full ADR: `docs/decisions/ADR-178-decentralized-slash-command-discovery.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-178-cmd-decentralize", description="Implementing ADR-178: Decentralized Slash Command Discovery")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-178-cmd-decentralize", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-178 team.
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

**Team name**: `adr-178-cmd-decentralize`

#### Phase 1: Discovery Infrastructure
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Add `scan_distributed_commands()` to discovery.py — reads all `augur.yaml` files, extracts `contributions.commands`, resolves source paths, validates files exist | `plugins/ai/skills/ai_bridge/augur/lib/discovery.py` |
| 1.2 | developer | medium | Update `_iter_all_commands()` in sync_agents.py to call `scan_distributed_commands()` first, then fall back to ai_bridge `agent-workflows/` and `skills/` for unmigrated commands. Distributed commands take priority (shadow) | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |
| 1.3 | developer | medium | Update `scan_workflows()` in generate_registry.py to include distributed command sources alongside ai_bridge fallback | `src/dashboard/scripts/generate_registry.py` |

#### Phase 2: Migrate dev/devops commands (largest batch)
**Strategy**: PARALLEL (steps 2.1 and 2.2 can run concurrently)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | low | Create `plugins/dev/skills/devops/commands/` directory. Move 12 workflow .md files from ai_bridge `agent-workflows/`: dev-build, dev-debug, dev-export, dev-fix, dev-merge, dev-retro, dev-review, dev-tidy, ops-audit, ops-debt, ops-docs, ops-hygiene, ops-refactor, ops-rollback, ops-tabs, adr | `plugins/dev/skills/devops/commands/*.md`, `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/` |
| 2.2 | developer | low | Move 4 skill directories from ai_bridge `skills/`: ops-audit, ops-optimize, ops-plugin-lint, ops-refactor, auto-fix. Create `commands/{id}/SKILL.md` structure in devops | `plugins/dev/skills/devops/commands/*/SKILL.md`, `plugins/ai/skills/ai_bridge/augur/data/skills/` |
| 2.3 | devops | medium | Add `contributions.commands` section to `plugins/dev/skills/devops/augur.yaml` declaring all 16+ commands with correct id, type, visibility, description | `plugins/dev/skills/devops/augur.yaml` |
| 2.4 | devops | low | Remove moved files from ai_bridge. Run `python3 plugins/ai/skills/ai_bridge/scripts/sync_agents.py --check` to verify output is identical | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/`, `plugins/ai/skills/ai_bridge/augur/data/skills/` |

#### Phase 3: Migrate remaining plugins
**Strategy**: PARALLEL (each plugin migration is independent)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | low | Migrate observability commands: Move ops-daemon, ops-loops, test-heal to `plugins/observability/skills/daemon/commands/`. Move ops-inspect, ops-kill, ops-perf to `plugins/observability/skills/observe/commands/`. Update both augur.yaml files | `plugins/observability/skills/daemon/`, `plugins/observability/skills/observe/` |
| 3.2 | developer | low | Migrate career/content commands: Move danit, post to `plugins/career/skills/content/commands/`. Update augur.yaml | `plugins/career/skills/content/` |
| 3.3 | developer | low | Migrate ai/rag command: Move rag to `plugins/ai/skills/rag/commands/`. Update augur.yaml | `plugins/ai/skills/rag/` |
| 3.4 | developer | low | Migrate admin commands: Move save skill to `plugins/admin/skills/file-manager/commands/`. Move import, notion-import, skill-setup, harden skills to `plugins/admin/skills/updater/commands/`. Update augur.yaml files | `plugins/admin/skills/file-manager/`, `plugins/admin/skills/updater/` |
| 3.5 | developer | low | Migrate dev/validator commands: Move test-client, test-coverage workflows + test-adr, test-nightly skills to `plugins/dev/skills/validator/commands/`. Update augur.yaml | `plugins/dev/skills/validator/` |
| 3.6 | developer | low | Migrate dev/frontend command: Move test-ui to `plugins/dev/skills/frontend/commands/`. Update augur.yaml | `plugins/dev/skills/frontend/` |
| 3.7 | developer | low | Move write-adr, implement-adr, adaptive-history, adaptive-review skills + adr workflow to `plugins/dev/skills/devops/commands/` (ADR management is devops). Update augur.yaml | `plugins/dev/skills/devops/` |

#### Phase 4: Cleanup and Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | devops | low | Delete emptied directories under ai_bridge (migrated workflows and skills). Verify only ~12 ai_bridge commands remain (ask, commands, focus, guide, learn, onboard, ops-memory, ops-sync, orch-audit, orch-dispatch) | `plugins/ai/skills/ai_bridge/augur/data/` |
| 4.2 | devops | low | Add `contributions.commands` to `plugins/ai/skills/ai_bridge/augur.yaml` for the remaining ai_bridge commands | `plugins/ai/skills/ai_bridge/augur.yaml` |
| 4.3 | devops | medium | Update ops-plugin-lint to validate `contributions.commands` declarations: check required fields, verify source file exists, warn on duplicate command ids across plugins | Linting scripts |
| 4.4 | validator | low | Run `python3 plugins/ai/skills/ai_bridge/scripts/sync_agents.py --all` and diff output against pre-migration snapshot. Verify identical `.claude/skills/` output, identical `CLAUDE.md` command listing | All generated files |
| 4.5 | validator | low | Run all tests: `pytest tests/src/`, `npm run build`. Verify no regressions | Test suite |
| 4.6 | devops | low | Run stale path scanner: `python3 .github/scripts/scan_stale_paths.py --ci`. Fix any HIGH-risk phantom paths referencing old ai_bridge command locations | Stale path report |
| 4.7 | architect | low | Verify ADR-178 intent matches implementation: distributed commands discovered correctly, no regressions in IDE sync, gradual migration shadow works | Code review |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] No orphaned files or broken references
- [ ] Stale path scanner clean
- [ ] Impact Manifest validated — zero stale references for old ai_bridge command paths in active code
- [ ] `sync_agents.py --check` shows identical output to pre-migration
- [ ] ADR status updated to "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-178-decentralized-slash-command-discovery.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
