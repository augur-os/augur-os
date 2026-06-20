---
status: Implemented
date: '2026-02-20'
deciders:
- Augur Team
related:
- ADR-122 (Filesystem-Driven Plugin Lifecycle)
- ADR-128 (Contribution-Based Hub Assembly)
- ADR-105 (Hub-Driven Plugin Architecture)
- ADR-112 (Plugin Completeness)
hub: null
tags:
- per
- skill
- config
- files
- linux
superseded_by: null
---

# ADR-230: Per-Skill .config Files (Linux-Style Plugin Configuration)

## Context

Augur's plugin enablement mechanism is unnecessarily complex and fragile:

1. **Centralized state file doesn't match runtime behavior**: `config/system/plugin_state.json` has 47 entries all set to `true`, yet 7 hubs are effectively disabled. The file tracks skill-level names (`"ai_bridge": true`) but NOT hub IDs (`"ai"`, `"productivity"`). Discovery code (`mount-plugins.ts`, `generate-tab-registry.ts`) must check both `isPluginEnabled(hub.id)` AND `isPluginEnabled(skillId)` — hub IDs missing from the file return `false`, which is how hubs get disabled. This implicit "missing = disabled" semantic is confusing and error-prone.

2. **Three separate mechanisms for plugin state**:
   - `config/system/plugin_state.json` — centralized JSON with boolean flags (47 entries)
   - `.disabled` marker files — ADR-122 added checks in mount-plugins but no files exist yet
   - `.newskill` marker files — planned but not implemented

   Three ways to express the same concept (is this skill active?) means three things to keep in sync.

3. **No per-skill user configuration**: Skills have no standard place for user-local settings. If a user wants to configure a skill differently (e.g., polling interval, API keys, feature flags), there's no convention — each skill invents its own approach.

4. **`plugin_state.json` violates self-containment**: The state for 47 plugins lives in one external file. You can't `git clone` a skill and have it bring its own config. Moving a skill between machines requires editing a central file.

5. **No dependency resolution state**: `augur.yaml` declares dependencies (`required: [knowledge, ai_bridge]`) but there's no runtime record of whether those dependencies are satisfied. The system discovers failures at mount time, not at config time.

Linux solved this decades ago: package definitions live in the package (`/usr/share/`), user config lives alongside or in `/etc/`. Each service has its own config file. We should do the same.

## Decision

Replace `plugin_state.json` and all marker files (`.disabled`, `.newskill`) with a single per-skill `.config` YAML file that lives in each skill directory.

### 1. The `.config` File

Every skill directory MAY contain a `.config` file:

```
plugins/{hub}/skills/{skill}/.config
```

**Schema**:

```yaml
# .config — per-skill runtime configuration
# This file is gitignored (user-local state).
# augur.yaml is the tracked skill definition.

# Enable/disable this skill (replaces plugin_state.json entry + .disabled marker)
enabled: true

# Skill lifecycle status (replaces .newskill marker)
# Values: new | stable | deprecated | archived
status: stable

# User-local settings (skill-specific, no fixed schema)
settings:
  polling_interval: 30
  max_results: 100

# Dependency resolution cache (auto-populated by discovery)
# Skills should NOT manually edit this section.
resolved_deps:
  knowledge: true
  ai_bridge: true
  channels: false    # optional, not installed
  last_checked: "2026-02-20T10:30:00Z"
```

**Rules**:
- `.config` is **gitignored** — it's user-local state, like Linux `/etc/` configs
- If `.config` doesn't exist → skill is **enabled** with **stable** status (sensible defaults, zero config)
- If `.config` exists with `enabled: false` → skill is disabled
- `augur.yaml` remains the tracked skill definition (author-written, version-controlled)
- `.config` is YAML (not JSON) to match `augur.yaml` and allow comments

### 2. Hub-Level `.config`

Hub directories MAY also have a `.config`:

```
plugins/{hub}/.config
```

```yaml
# Hub-level config — disables the entire hub
enabled: true
status: stable
```

If a hub `.config` has `enabled: false`, all skills in that hub are disabled regardless of their individual `.config`.

### 3. Discovery Changes

All discovery code reads `.config` instead of `plugin_state.json`:

**`mount-plugins.ts`** (already has `.disabled` checks from ADR-122):
- Replace `isDisabled()` check with `readSkillConfig()` → check `enabled` field
- Remove `isPluginEnabled()` calls that hit `plugin_state.json`

**`generate-tab-registry.ts`**:
- Replace `isPluginEnabled(hub.id)` and `isPluginEnabled(skillId)` with `readHubConfig()` and `readSkillConfig()`

**`plugin-state.ts`**:
- Rewrite `isPluginEnabled()` to scan `.config` files instead of reading `plugin_state.json`
- Or deprecate entirely — callers read `.config` directly

**`skill_registry.py`** (Python side):
- Replace `plugin_state.json` reads with `.config` YAML reads
- `_iter_skill_dirs()` checks `.config` for `enabled: false`

**`plugin_tools.py`** (MCP):
- Skip skills where `.config` has `enabled: false`

### 4. Migration

A one-time migration script converts the current state:

```python
# scripts/migrate_to_skill_configs.py

# 1. Read plugin_state.json
# 2. For each entry set to true:
#    - Find the skill directory
#    - Create .config with enabled: true, status: stable
# 3. For skills NOT in plugin_state.json:
#    - Create .config with enabled: false (they were implicitly disabled)
# 4. For hub IDs not in plugin_state.json (ai, productivity, etc.):
#    - Create hub-level .config with enabled: false
# 5. Delete plugin_state.json
# 6. Delete any .disabled marker files
# 7. Delete any .newskill marker files
```

### 5. Dashboard API Changes

Existing enable/disable API routes update `.config` instead of `plugin_state.json`:

| Route | Old Behavior | New Behavior |
|-------|-------------|-------------|
| `POST /api/plugin-lifecycle/enable` | Write `plugin_state.json` | Set `enabled: true` in skill `.config` |
| `POST /api/plugin-lifecycle/disable` | Write `plugin_state.json` | Set `enabled: false` in skill `.config` |
| `GET /api/plugins` | Read `plugin_state.json` | Scan `.config` files |

### 6. Settings UI Integration

The Settings/Skills page shows `.config` state per skill:
- Toggle switch for enabled/disabled → writes `.config`
- Status badge (new/stable/deprecated) → reads `.config`
- Per-skill settings section → reads/writes `settings` from `.config`

### 7. Dependency Resolution

On `npm run mount-plugins` or dashboard startup, the system:

1. Reads each skill's `augur.yaml` → extracts `dependencies.required` and `dependencies.optional`
2. Checks which skills are enabled (via `.config`)
3. Writes `resolved_deps` section into each skill's `.config`
4. Skills with unmet `required` dependencies get a warning in the dashboard

This gives users visibility into dependency state without a centralized resolver.

### 8. .gitignore Addition

```gitignore
# Per-skill config (user-local state)
plugins/**/.config
```

## Consequences

### Positive

- **One mechanism instead of three**: `.config` replaces `plugin_state.json` + `.disabled` + `.newskill`
- **Self-contained skills**: Config travels with the skill directory — `git mv`, `cp -r`, `zip` all work
- **Linux-familiar pattern**: Developers already understand `/etc/` style config
- **Future-proof**: `settings` section gives skills a standard place for user configuration
- **Dependency visibility**: `resolved_deps` shows what's connected without running mount-plugins
- **Simple discovery**: `enabled: false` in a YAML file is obvious to anyone reading the directory
- **Comments in config**: YAML supports comments, JSON doesn't — users can annotate why something is disabled

### Negative

- **Migration required**: One-time script to convert `plugin_state.json` → per-skill `.config` files
- **File scatter**: 47 `.config` files instead of 1 JSON file (but each is ~5 lines and collocated with its skill)
- **Discovery slightly slower**: Must read N files instead of 1 — mitigated by caching in `plugin-state.ts`

### Neutral

- `augur.yaml` schema unchanged — `.config` is additive, not a replacement
- mount-plugins flow stays the same — only the "is this enabled?" check changes
- ADR-122 `.disabled` check in mount-plugins becomes the `.config` check (same code path, different file)

## Implementation Order

```
Phase 1: Core Infrastructure
├── Step 1: Create .config schema and reader utility (TypeScript + Python)
├── Step 2: Add plugins/**/.config to .gitignore
└── Step 3: Create migration script (plugin_state.json → .config files)

Phase 2: Discovery Integration (depends on Phase 1)
├── Step 4: Update mount-plugins.ts — replace isDisabled() + isPluginEnabled() with .config reader
├── Step 5: Update generate-tab-registry.ts — replace isPluginEnabled() calls
├── Step 6: Update plugin-state.ts — rewrite to scan .config files
├── Step 7: Update skill_registry.py — replace plugin_state.json reads
└── Step 8: Update plugin_tools.py — replace plugin_state.json reads

Phase 3: Dashboard Integration (depends on Phase 2)
├── Step 9: Update enable/disable API routes to write .config
├── Step 10: Update Settings/Skills page to show .config state
└── Step 11: Add per-skill settings section to skill detail page

Phase 4: Dependency Resolution (depends on Phase 2)
├── Step 12: Implement dependency resolver — scan augur.yaml deps, check enabled state, write resolved_deps
└── Step 13: Show dependency status in dashboard skill cards

Phase 5: Cleanup & Migration (depends on all)
├── Step 14: Run migration script
├── Step 15: Delete plugin_state.json
├── Step 16: Remove .disabled/.newskill marker file checks (consolidated into .config)
└── Step 17: Remove old plugin-state.ts centralized loader code

Phase 6: Verification (depends on all)
├── Step 18: Run full test suite
├── Step 19: Verify mount-plugins with .config enabled/disabled
├── Step 20: Verify generate-tab-registry produces correct sidebar
├── Step 21: Run stale path scanner
└── Step 22: Update ADR status
```

## Alternatives Considered

### Alternative 1: Extend augur.yaml with an `enabled` field

Add `enabled: true/false` directly to the tracked `augur.yaml`.

Rejected because:
- `augur.yaml` is version-controlled — enable/disable is user-local state that shouldn't be committed
- Merge conflicts when different machines have different skills enabled
- Mixes skill definition (what it IS) with runtime config (how user configured it)
- Linux separates package manifests from `/etc/` config for this exact reason

### Alternative 2: Keep plugin_state.json but add hub IDs

Fix the immediate problem by adding hub IDs (`"ai": false`, `"productivity": false`) to `plugin_state.json`.

Rejected because:
- Still centralized — doesn't solve self-containment
- Still requires keeping the file in sync with filesystem changes
- Doesn't provide per-skill settings or dependency state
- Patch fix, not an architecture fix
- We'd still need marker files for status (new/deprecated)

### Alternative 3: Use environment variables for skill config

Skills read `AUGUR_SKILL_{NAME}_ENABLED=true` from environment.

Rejected because:
- 47+ environment variables is unmanageable
- No persistence across sessions without shell profile edits
- Can't express structured config (settings, deps)
- Doesn't collocate with the skill

## References

- `config/system/plugin_state.json` — Current centralized state (to be eliminated)
- `src/dashboard/lib/plugin-state.ts` — Current `isPluginEnabled()` implementation
- `src/dashboard/scripts/mount-plugins.ts` — Already has `.disabled` checks (ADR-122)
- `src/dashboard/scripts/generate-tab-registry.ts` — Hub filtering with `isPluginEnabled()`
- `src/plugins/skill_registry.py` — Python skill discovery
- `src/mcp/augur_mcp/plugin_tools.py` — MCP tool discovery
- ADR-122: Filesystem-Driven Plugin Lifecycle (introduced `.disabled` concept)
- ADR-128: Contribution-Based Hub Assembly (introduced hub assembly + filtering)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-230: Per-Skill .config Files**.

Read the full ADR: `docs/decisions/ADR-230-per-skill-config-files.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-129-skill-config", description="Implementing ADR-230: Per-Skill .config Files")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-129-skill-config", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-129 team.
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

**Team name**: `adr-129-skill-config`

#### Phase 1: Core Infrastructure
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create `.config` YAML schema, TypeScript reader (`readSkillConfig()`, `readHubConfig()`, `isSkillEnabled()`), and Python reader (`read_skill_config()`) with caching | `src/dashboard/lib/skill-config.ts`, `src/plugins/skill_config.py` |
| 1.2 | devops | low | Add `plugins/**/.config` to `.gitignore` | `.gitignore` |
| 1.3 | developer | medium | Create migration script — reads `plugin_state.json`, creates `.config` per skill, creates hub-level `.config` for disabled hubs, handles missing hub IDs (ai, productivity, etc.) | `scripts/migrate_to_skill_configs.py` |

#### Phase 2: Discovery Integration
**Strategy**: PARALLEL (Steps 2.1-2.5 can run concurrently)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Update mount-plugins.ts — replace `isDisabled()` + `isPluginEnabled()` with `readSkillConfig()` / `readHubConfig()` checks | `src/dashboard/scripts/mount-plugins.ts` |
| 2.2 | developer | medium | Update generate-tab-registry.ts — replace `isPluginEnabled(hub.id)` and skill checks with `.config` reader | `src/dashboard/scripts/generate-tab-registry.ts` |
| 2.3 | developer | medium | Rewrite plugin-state.ts — `isPluginEnabled()` now scans `.config` files instead of `plugin_state.json`, maintain backward-compat API | `src/dashboard/lib/plugin-state.ts` |
| 2.4 | developer | medium | Update skill_registry.py — `_iter_skill_dirs()` reads `.config` for `enabled: false` | `src/plugins/skill_registry.py` |
| 2.5 | developer | low | Update plugin_tools.py — skip skills where `.config` has `enabled: false` | `src/mcp/augur_mcp/plugin_tools.py` |

#### Phase 3: Dashboard Integration
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Update enable/disable API routes to read/write `.config` YAML instead of `plugin_state.json` | `src/dashboard/app/api/plugin-lifecycle/enable/route.ts`, `src/dashboard/app/api/plugin-lifecycle/disable/route.ts` |
| 3.2 | developer | medium | Update Settings/Skills page — show `.config` state, toggle writes `.config` | `src/dashboard/app/settings/skills/` |
| 3.3 | developer | low | Update `GET /api/plugins` route to scan `.config` files | `src/dashboard/app/api/plugins/route.ts` |

#### Phase 4: Dependency Resolution
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Implement dependency resolver — scan `augur.yaml` deps, check enabled state via `.config`, write `resolved_deps` into each skill's `.config` | `src/dashboard/lib/dependency-resolver.ts` |
| 4.2 | developer | low | Show dependency badges on skill cards in Settings/Skills page | `src/dashboard/app/settings/skills/` |

#### Phase 5: Cleanup & Migration
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | devops | low | Run migration script to generate all `.config` files | `scripts/migrate_to_skill_configs.py` |
| 5.2 | devops | low | Delete `config/system/plugin_state.json` | `config/system/plugin_state.json` |
| 5.3 | developer | low | Remove `.disabled` / `.newskill` marker file checks — consolidated into `.config` reader | `src/dashboard/scripts/mount-plugins.ts` |
| 5.4 | developer | low | Remove old `loadPluginState()` / `getPluginStateFile()` code from `plugin-state.ts` | `src/dashboard/lib/plugin-state.ts` |

#### Final Phase: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run full test suite (`pytest tests/src/`, `npm run build`), verify no regressions |
| V.2 | validator | low | Verify mount-plugins with `.config` enabled/disabled skills — correct sidebar, correct routes |
| V.3 | validator | low | Verify generate-tab-registry shows only enabled hubs |
| V.4 | devops | low | Run stale path scanner: `python3 .github/scripts/scan_stale_paths.py --ci` |
| V.5 | architect | low | Verify ADR intent matches implementation, update ADR status |

### Stale Path Scan (Conditional)

This ADR removes `plugin_state.json` and changes how discovery code resolves plugin state. The final verification MUST include:

```bash
python3 .github/scripts/scan_stale_paths.py --ci
```

### Completion Criteria
- [ ] `.config` reader works in TypeScript and Python with caching
- [ ] `mount-plugins.ts` uses `.config` instead of `plugin_state.json` / `.disabled`
- [ ] `generate-tab-registry.ts` uses `.config` for hub filtering
- [ ] `plugin_state.json` deleted, all state migrated to per-skill `.config` files
- [ ] Enable/disable dashboard UI writes `.config` files
- [ ] Dependency resolver populates `resolved_deps` in `.config`
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Stale path scanner clean
- [ ] ADR status updated to Implemented

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-230-per-skill-config-files.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
