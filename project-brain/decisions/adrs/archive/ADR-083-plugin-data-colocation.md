---
status: Implemented
date: '2026-02-12'
deciders:
- Core team
related:
- ADR-002 (data separation)
- ADR-016 (monorepo migration)
- ADR-018 (plugin self-containment)
hub: null
tags:
- colocate
- plugin
- data
- plugin
- code
superseded_by: null
---

# ADR-083: Colocate Plugin Data With Plugin Code

## Context

Every plugin currently stores its data in a **shadow directory** under `plugins/{bundle}/{skill}/`, mirroring the code structure at `plugins/{bundle}/skills/{skill}/`. This means every skill lives in two places:

```
plugins/dev/skills/frontend/                    ← code (scripts, dashboard, SKILL.md)
plugins/dev/frontend/hardening-reports/     ← data (generated outputs, configs)
```

The `plugins/` tree has grown to **847 files across 267 directories (64 MB)**, spanning all four bundles:

| Bundle | Files |
|--------|-------|
| apps | 288 |
| crew | 212 |
| orchestrator | 242 |
| services | 104 |

### Problems

1. **Split identity**: A skill's "complete state" requires looking in two unrelated directory trees. Developers must mentally map `plugins/dev/skills/frontend/` ↔ `plugins/dev/frontend/`.

2. **Contradicts self-containment (ADR-018)**: ADR-018 says plugins own their dependencies via local `requirements.txt`. But a plugin's data — its most important runtime artifact — lives in an entirely different tree.

3. **Confusing naming**: `plugins/` sounds like it contains plugins, not data. New contributors consistently misunderstand the structure.

4. **Path resolution overhead**: `get_skill_data_dir("frontend")` must auto-discover the bundle name by scanning all `plugins/*/skills/` directories, then construct a path into an entirely different tree (`plugins/dev/frontend/`). This is fragile and slow.

5. **Export/portability friction**: Exporting a plugin (via `skill_exporter.py`) requires collecting files from two trees and rewriting `plugins/` references in the output.

6. **Stale mirror**: The `plugins/` structure drifts from `plugins/` — bundle names differ (`crew` vs `crew/skills`), skill renames leave orphaned data dirs, and there's no automated validation that the two trees stay in sync.

### What lives in `plugins/` today

| Category | Examples | Count (est.) |
|----------|----------|------|
| Generated reports | hardening-reports, audits, complexity-reports | ~100 |
| User data | career profiles, finance records, recipes, job-analyzer | ~300 |
| Operational state | daemon insights, usage stats, notifications | ~50 |
| Skill configs | config.yaml, rules.yaml | ~50 |
| Agent workflows | ai_bridge skills, workflows, prompts | ~100 |
| Misc (retrospectives, designs, templates) | Various | ~200 |

## Decision

**Move plugin data from `plugins/{bundle}/{skill}/` into `plugins/{bundle}/skills/{skill}/data/`**, making each plugin directory the single source of truth for its code AND data.

### New Structure

```
plugins/dev/skills/frontend/
├── SKILL.md
├── scripts/
├── dashboard/
├── data/                              ← NEW: colocated data
│   ├── hardening-reports/
│   │   ├── home_20260212.yaml
│   │   └── knowledge_20260212.yaml
│   ├── design-system/
│   └── screenshots/
└── requirements.txt
```

### What moves

All contents of `plugins/{bundle}/{skill}/` move to `plugins/{bundle}/skills/{skill}/data/`.

### What stays in `data/`

Cross-cutting concerns that don't belong to any single plugin:

| Directory | Purpose | Stays because |
|-----------|---------|---------------|
| `config/` | System-level configuration | Shared across all plugins |
| `data/runtime/` | Logs, cache, temp | Ephemeral, not plugin-specific |
| `data/memory/` | Canonical memory store | Cross-cutting knowledge system |
| `data/ide-integration/` | IDE registry data | Shared agent infrastructure |

### Path Resolution Changes

Update `get_skill_data_dir()` in `src/config/paths.py`:

```python
# BEFORE
def get_skill_data_dir(skill_name: str) -> Path:
    bundle = get_skill_bundle(skill_name)
    return get_user_data_base() / "plugins" / bundle / skill_name

# AFTER
def get_skill_data_dir(skill_name: str) -> Path:
    bundle = get_skill_bundle(skill_name)
    return get_project_root() / "plugins" / bundle / "skills" / skill_name / "data"
```

Also deprecate `get_plugin_data_dir()` and `get_operations_dir()` which reference the old structure.

### Migration Script

Create `src/scripts/migrate_plugin_data.py`:

1. For each directory in `plugins/{bundle}/{skill}/`:
   - Map to `plugins/{bundle}/skills/{skill}/data/`
   - Create target `data/` dir if missing
   - Move all files preserving directory structure
   - Verify source is empty, then remove
2. Update all hardcoded `plugins/` references in Python/TypeScript
3. Remove empty `plugins/` tree
4. Update `data/README.md` to reflect new structure

### Agent Rules Update

Update `plugins/ai/ai_bridge/agent-rules.md`:

```markdown
# BEFORE
- plugins/{bundle}/{skill}/ = Skill data (mirrors plugins/ structure)

# AFTER
- plugins/{bundle}/skills/{skill}/data/ = Skill data (colocated with code)
- data/ = Cross-cutting data only (config, runtime, memory, ide-integration)
```

## Consequences

### Positive

- **True self-containment**: A skill's complete state lives in ONE directory. `ls plugins/dev/skills/frontend/` shows everything.
- **Simpler path resolution**: `get_skill_data_dir()` resolves within the same tree as `get_skill_code_dir()`. No cross-tree mapping needed.
- **Portable plugins**: Exporting a plugin is `cp -r plugins/{bundle}/skills/{skill}/` — done. No second tree to collect from.
- **No mirror drift**: Renaming a skill automatically moves its data too. No orphaned `plugins/old-name/` dirs.
- **Cleaner `data/`**: `data/` shrinks from 5 top-level concerns to 4, all truly cross-cutting (config, runtime, memory, ide-integration).
- **Reduced cognitive load**: One mental model — "everything about skill X is in `plugins/.../X/`".

### Negative

- **Migration effort**: 847 files across 267 directories must be moved and all references updated. ~30 Python scripts reference `plugins/` or `get_skill_data_dir()`.
- **Git history disruption**: File moves break `git log --follow` for affected files.
- **`plugins/` gets heavier**: Plugin directories now contain data files (YAML, reports), increasing their size. `plugins/` will grow by ~64 MB.
- **Code/data boundary blurs in the filesystem**: While still separated by subdirectory (`data/` inside each skill), the visual separation of `plugins/` = code and `data/` = data is weakened.

### Neutral

- ADR-002 is **partially superseded**: The principle of separating code from data remains valid, but the implementation changes from "separate directory trees" to "separate subdirectories within the same tree". The monorepo migration (ADR-016) already moved in this direction.
- `.gitignore` patterns may need updates if any `plugins/` entries exist.
- `data/README.md` needs rewriting to reflect the reduced scope of `data/`.

## Implementation Order

```
Phase 1: Path Infrastructure
├── Step 1: Update get_skill_data_dir() in src/config/paths.py
├── Step 2: Deprecate get_plugin_data_dir() and get_operations_dir()
└── Step 3: Add get_skill_data_dir() tests for new paths

Phase 2: Migration Script (depends on Phase 1)
├── Step 4: Write src/scripts/migrate_plugin_data.py
├── Step 5: Dry-run migration, verify file counts match
└── Step 6: Execute migration

Phase 3: Reference Updates (depends on Phase 2)
├── Step 7: Update all Python scripts using plugins/ paths
├── Step 8: Update all TypeScript/dashboard references
├── Step 9: Update agent-rules.md and CLAUDE.md
├── Step 10: Update data/README.md and plugins/README.md
└── Step 11: Update SKILL.md files that reference data dirs

Phase 4: Cleanup (depends on Phase 3)
├── Step 12: Remove empty plugins/ tree
├── Step 13: Update .gitignore if needed
└── Step 14: Update audit_paths.py to validate new structure

Phase 5: Verification (depends on Phase 4)
├── Step 15: Run full test suite (pytest + npm run build + npm run test)
├── Step 16: Verify all skills can resolve their data dirs
└── Step 17: Verify no orphaned references to plugins/
```

## Alternatives Considered

### Alternative 1: Flatten `data/` by Category

Instead of mirroring plugins, organize data by type: `data/reports/`, `configs/`, `data/user-content/`.

**Rejected because**:
- Loses the plugin association — "whose report is this?" requires metadata
- Creates a different kind of sprawl (by type instead of by skill)
- Still requires cross-referencing between `plugins/` and `data/`
- Harder to export a single plugin

### Alternative 2: Keep Mirror But Add Symlinks

Add symlinks from `plugins/{bundle}/skills/{skill}/data` → `plugins/{bundle}/{skill}/`.

**Rejected because**:
- Symlinks break on Windows and some CI systems
- Adds complexity without reducing the two-tree problem
- Git handles symlinks inconsistently
- Doesn't simplify exports or path resolution

### Alternative 3: Keep Current Structure With Stricter Validation

Add CI checks to ensure `plugins/` stays in sync with `plugins/`.

**Rejected because**:
- Addresses the symptom (drift) but not the root cause (split identity)
- Adds more infrastructure to maintain the mirror
- Doesn't improve self-containment or portability
- 847 files across two trees is the problem, not the lack of validation

## References

- [ADR-002: Data Separation](ADR-002-data-separation.md) — original two-repo design (partially superseded by this ADR)
- [ADR-016: Monorepo Migration](ADR-016-monorepo-migration.md) — consolidated repos, paved the way for colocation
- ADR-018: Plugin Self-Containment — philosophy this ADR extends to data
- `src/config/paths.py` — current path resolution (lines 279–305, 442–456)
- `data/README.md` — current data directory rules

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-083: Colocate Plugin Data With Plugin Code**.

Read the full ADR: `docs/decisions/ADR-083-plugin-data-colocation.md`

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

1. **Create team**: `TeamCreate(team_name="adr-083-data-colocation", description="Implementing ADR-083: Colocate Plugin Data With Plugin Code")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-083-data-colocation", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-083 team.
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

**Team name**: `adr-083-data-colocation`

#### Phase 1: Path Infrastructure
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Update `get_skill_data_dir()` to resolve to `plugins/{bundle}/skills/{skill}/data/` instead of `plugins/{bundle}/{skill}/` | `src/config/paths.py` |
| 1.2 | developer | medium | Deprecate `get_plugin_data_dir()` and `get_operations_dir()` with warnings pointing to new `get_skill_data_dir()` | `src/config/paths.py` |
| 1.3 | developer | medium | Update/add tests for new path resolution | `tests/src/test_paths.py` |

#### Phase 2: Migration Script
**Strategy**: PIPELINE (depends on Phase 1)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Write migration script that moves all files from `plugins/{bundle}/{skill}/` to `plugins/{bundle}/skills/{skill}/data/`, preserving directory structure. Include dry-run mode. | `src/scripts/migrate_plugin_data.py` |
| 2.2 | developer | low | Run dry-run and verify file counts match (847 files, 267 dirs) | N/A (execution only) |
| 2.3 | developer | low | Execute migration | N/A (execution only) |

#### Phase 3: Reference Updates
**Strategy**: PARALLEL (depends on Phase 2)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Update all Python scripts that hardcode `plugins/` paths — grep for `plugins` and `get_plugin_data_dir` across `plugins/**/*.py` and `src/**/*.py` | `plugins/dev/skills/frontend/scripts/dashboard_hardening_audit.py`, `plugins/dev/skills/frontend/scripts/generate_hardening_adr.py`, `plugins/ai/skills/mcp-app-factory/scripts/skill_exporter.py`, `plugins/productivity/skills/apple/scripts/inbox.py`, `plugins/ai/skills/ai_bridge/scripts/sync_agents.py`, `plugins/ai/skills/ai_bridge/augur/discovery.py`, `plugins/ai/skills/knowledge/augur/memory/unified_search.py` |
| 3.2 | developer | medium | Update TypeScript/dashboard references to `plugins/` in API routes and components | `src/dashboard/**/*.ts`, `src/dashboard/**/*.tsx`, `plugins/**/api/**/*.ts` |
| 3.3 | devops | low | Update `plugins/ai/ai_bridge/agent-rules.md` (now at `plugins/ai/skills/ai_bridge/augur/agent-rules.md`) and regenerate CLAUDE.md | `plugins/ai/skills/ai_bridge/augur/agent-rules.md`, `CLAUDE.md` |
| 3.4 | devops | low | Update `data/README.md` and `plugins/README.md` to reflect new structure | `data/README.md`, `plugins/README.md` |
| 3.5 | devops | low | Update SKILL.md files that reference their own data dirs | `plugins/**/SKILL.md` |

#### Phase 4: Cleanup
**Strategy**: PIPELINE (depends on Phase 3)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | devops | low | Remove empty `plugins/` tree after verifying all files moved | `plugins/` |
| 4.2 | devops | low | Update `.gitignore` if any `plugins/` patterns exist | `.gitignore` |
| 4.3 | developer | medium | Update `audit_paths.py` to validate new structure — reject references to `plugins/` | `.github/scripts/audit_paths.py` |

#### Phase 5: Verification
**Strategy**: PIPELINE (depends on Phase 4)
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 5.1 | validator | low | Run `pytest tests/src/` — verify path tests pass |
| 5.2 | validator | low | Run `npm run build` and `npm run test` in `src/dashboard/` |
| 5.3 | validator | low | Grep entire repo for orphaned `plugins/` references |
| 5.4 | validator | low | Verify each skill can resolve `get_skill_data_dir()` to a real directory |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`, `npm run test`)
- [ ] No orphaned files or broken references to `plugins/`
- [ ] Every `plugins/{bundle}/skills/{skill}/data/` dir exists with migrated content
- [ ] `plugins/` directory no longer exists
- [ ] ADR status updated to "Accepted"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-083-plugin-data-colocation.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
