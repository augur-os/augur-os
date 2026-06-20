---
status: Implemented
date: '2026-02-19'
deciders:
- Augur Team
related:
- ADR-109 (Filesystem-Driven Dashboard)
- ADR-105 (Hub-Driven Plugin Architecture)
- ADR-112 (Plugin Completeness)
- ADR-121 (Hub Ownership Validation)
- ADR-083 (Colocate Plugin Data)
- ADR-087 (Eliminate data/ Directory)
hub: null
tags:
- filesystem
- driven
- plugin
- lifecycle
- management
superseded_by: null
---

# ADR-122: Filesystem-Driven Plugin Lifecycle Management

## Context

Augur's core value proposition is that users can add, remove, and compose skills with zero friction — drop a folder, get a plugin. Today, several gaps undermine this:

1. **No detection of new skills**: When a user creates a new folder under `plugins/{bundle}/skills/`, nothing happens until they manually run `mount-plugins` and restart the dashboard. There is no guided onboarding for the new skill.

2. **No detection of deleted skills**: Removing a skill folder can leave orphan routes, stale nav entries, and broken dependency references that surface only at build time.

3. **Centralized enable/disable**: Plugin state lives in `config/system/plugin_state.json` (dashboard) and `config.yaml` `skills_state.disabled` list (Python). Two separate files, neither colocated with the plugin. This violates the self-containment principle (ADR-083) and makes it impossible to `git mv` a plugin between machines without also migrating config.

4. **No uninstall/archive**: The "Uninstall" button on the plugin page has no defined behavior. Users who want to remove a skill must manually delete files, with no recovery path.

5. **No bundle-level lifecycle**: Users cannot create or remove an entire hub by simply creating or deleting a directory — they must also update mount config and navigation.

6. **CLI-first users are unsupported**: All plugin management requires the web GUI. Users who prefer terminal workflows have no structured path for skill lifecycle operations.

These gaps make Augur's plugin system feel fragile and config-heavy instead of filesystem-native.

## Decision

We will implement a fully filesystem-driven plugin lifecycle where the filesystem IS the source of truth. No central configuration files for plugin state. Every plugin is self-contained.

### 1. Daemon Filesystem Watcher

A new daemon service `plugin_watcher.py` runs under the unified daemon (`plugins/observability/skills/daemon/scripts/unified_daemon.py`) with a 10-second polling interval.

**What it watches**:
- `plugins/*/skills/*/` — skill-level folders (creation, deletion, rename)
- `plugins/*/` — bundle-level folders (creation, deletion)

**How it detects changes**:
- Maintains a snapshot file at `runtime/plugin_watcher_snapshot.json` containing the last-known set of `{bundle}/{skill}` paths and their mtimes.
- Each poll cycle: scan filesystem, diff against snapshot, emit events for `skill_added`, `skill_removed`, `bundle_added`, `bundle_removed`.
- Snapshot is updated after events are processed.

**Event output**:
- Writes events to `runtime/plugin_events.json` (append-only, max 100 entries, FIFO).
- Each event: `{ type, bundle, skill?, timestamp, acknowledged: false }`.

### 2. GUI Magic Menu (Skill Wizard)

When the dashboard detects unacknowledged events in `runtime/plugin_events.json` (via polling API route `/api/plugin-events`):

**For `skill_added`**:
- Shows a toast notification: "New skill detected: `{skill}` in `{bundle}`"
- Notification button opens the **Skill Wizard** modal with options:
  - **Quick Setup**: Auto-generates minimal `dashboard.yaml`, `SKILL.md`, and a starter page. Runs `mount-plugins` to mount immediately.
  - **Configure Manually**: Opens the skill folder in the user's editor (respects ADR-114 editor settings).
  - **Ignore**: Dismisses; marks event as acknowledged.

**For `skill_removed`**:
- Shows a toast notification: "Skill removed: `{skill}` from `{bundle}`"
- Notification button opens the **Removal Wizard** modal:
  - Shows impacted dependencies (required/optional from other skills' `dashboard.yaml`).
  - **Clean Up**: Runs `mount-plugins --clean` to remove stale mounts. Updates nav.
  - **Undo**: If skill was archived (see Section 6), offers one-click restore.

**For `bundle_added`**:
- Shows toast: "New hub detected: `{bundle}`"
- Opens wizard that creates a minimal starter skill with `dashboard.yaml` (role: primary), a `SKILL.md`, and a "Start Here" overview page. Adds to nav automatically on next mount.

**For `bundle_removed`**:
- Shows toast: "Hub removed: `{bundle}` (N skills)"
- Opens removal wizard showing all skills that were in the bundle and their downstream dependencies.

### 3. TODO Markers for CLI Workflow

When the watcher detects a change, it also creates a TODO marker file alongside the event:

**For new skill**: Creates `plugins/{bundle}/skills/{skill}/TODO_NEWSKILL` with contents:
```
# New skill detected by Augur plugin watcher
# Created: {timestamp}
#
# This skill needs setup. Options:
# 1. Run /skill-setup {bundle}/{skill} to auto-generate scaffold
# 2. Create dashboard.yaml and SKILL.md manually
# 3. Delete this file to dismiss
#
# The dashboard will show a setup wizard for this skill until
# this TODO is resolved (file deleted or skill configured).
```

**For removed skill**: Creates `runtime/todos/TODO_SKILL_REMOVED_{bundle}_{skill}` with details about what was removed and impacted dependencies.

The nightly marker scanner (`scan_code_markers.py`) already picks up `TODO_*` files — these will appear in the daily report.

### 4. Notification Deduplication

- Once a TODO marker exists for a skill, the GUI will NOT re-notify for the same skill unless the folder's mtime changes (indicating the user modified it again).
- The acknowledgement flow:
  1. Watcher detects change → writes event + creates TODO
  2. GUI shows notification → user can open wizard or ignore
  3. Ignoring marks the event as `acknowledged: true` in `plugin_events.json`
  4. The TODO file persists until the user resolves it (configures the skill or deletes the TODO)
  5. If the user modifies the folder again (new files added), the watcher creates a fresh event (new timestamp) which triggers a new notification

### 5. Filesystem-Based Enable/Disable (Replaces Central Config)

**Disable a skill**: Create a `.disabled` marker file in the skill folder:
```
plugins/{bundle}/skills/{skill}/.disabled
```

**Disable an entire bundle**: Create `.disabled` in the bundle root:
```
plugins/{bundle}/.disabled
```

**Marker file contents** (optional, for human readability):
```
# Disabled by user on 2026-02-19T14:30:00Z
# Reason: Testing alternative skill
```

**Mount system integration**:
- `mount-plugins.ts` `discoverPlugins()` checks for `.disabled` file before processing each skill/bundle.
- `skill_registry.py` `_iter_skill_dirs()` checks for `.disabled` file and sets `disabled=True`.
- `plugin_tools.py` MCP tool discovery skips `.disabled` skills.

**Migration from centralized config**:
- One-time migration script reads `config/system/plugin_state.json` and `config.yaml` `skills_state.disabled`, creates corresponding `.disabled` files, then removes the old config entries.
- After migration, `plugin_state.json` and `config.yaml` `skills_state` section are no longer read for enable/disable state.

**GUI plugin page integration**:
- "Disable" button on plugin page → creates `.disabled` file in skill folder.
- "Enable" button → deletes `.disabled` file.
- Disabled skills appear grayed out in nav with a "disabled" badge.

### 6. Uninstall with Archive for Recovery

When a user clicks "Uninstall" on the plugin page for a skill:

1. The skill folder is moved (not deleted) to an archive directory:
   ```
   plugins/.archive/{bundle}/skills/{skill}/
   ```
2. Archive preserves the full folder structure including `dashboard/`, `api/`, `data/`, `scripts/`, `SKILL.md`, `dashboard.yaml`, etc.
3. A metadata file is created at `plugins/.archive/{bundle}/skills/{skill}/.archive-meta.json`:
   ```json
   {
     "archived_at": "2026-02-19T14:30:00Z",
     "original_path": "plugins/career/skills/resume-writer",
     "reason": "user_uninstall",
     "version": "1.0.0"
   }
   ```
4. Mount system runs cleanup to remove stale routes.
5. The watcher detects the removal and creates a `skill_removed` event.

**For bundle uninstall**:
- Entire bundle folder moves to `plugins/.archive/{bundle}/`.
- All skills within it are archived together.

**Recovery**:
- GUI "Archived Skills" section (under Settings/Plugins page) lists archived skills with a "Restore" button.
- Restore moves the folder back to its original path and triggers `skill_added` event.
- CLI: `mv plugins/.archive/{bundle}/skills/{skill} plugins/{bundle}/skills/{skill}` — the watcher detects it as a new skill.

### 7. Bundle-Level Lifecycle

**New bundle creation** (user creates `plugins/mytools/`):
1. Watcher detects new directory with no `skills/` subdirectory yet.
2. Waits one poll cycle (10s) to see if user is still setting up.
3. If `skills/` subdirectory appears, processes normally.
4. If no `skills/` after 2 cycles, creates a starter skill:
   ```
   plugins/mytools/skills/overview/
   ├── SKILL.md          (minimal frontmatter)
   ├── dashboard.yaml    (role: primary, hub.id: mytools)
   └── dashboard/
       └── page.tsx      ("Start Here" page with setup instructions)
   ```
5. Runs mount to add to nav immediately.

**Bundle deletion** (user deletes `plugins/mytools/`):
1. Watcher detects removal of all skills in the bundle.
2. Emits `bundle_removed` event.
3. Mount cleanup removes all routes and nav entries for the bundle.
4. Dependency checker runs — if any other skills declared `dependencies.required` referencing skills in this bundle, they are flagged with `TODO_BROKEN_DEP`.

### 8. Dependency Impact Handling

When a skill or bundle is removed (deleted or archived), the system checks all remaining skills' `dashboard.yaml` `dependencies` section:

- **`required` dependency broken**: The dependent skill's page shows a warning banner: "Required dependency `{skill}` is missing. Some features may not work." A `TODO_BROKEN_DEP` marker is created.
- **`optional` dependency broken**: No warning, no TODO. The dependent skill gracefully degrades (this is already the expected behavior per ADR-112).

This mirrors the existing behavior but adds proactive detection at removal time instead of waiting for build failures.

### 9. Integration with Mount System

The mount system (`mount-plugins.ts`) gains these checks in its discovery phase:

```
For each plugins/{bundle}/:
  ├── Skip if .disabled exists at bundle level
  ├── For each skills/{skill}/:
  │   ├── Skip if .disabled exists at skill level
  │   ├── Skip if no dashboard.yaml (not a dashboard skill)
  │   ├── Validate hub ownership (ADR-121)
  │   └── Mount normally
  └── After mounting: delete stale mounts for skills/bundles that no longer exist
```

### 10. API Routes

New API routes for the dashboard:

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/plugin-events` | GET | Poll for unacknowledged plugin events |
| `/api/plugin-events/acknowledge` | POST | Mark event as acknowledged |
| `/api/plugin-lifecycle/disable` | POST | Create `.disabled` file |
| `/api/plugin-lifecycle/enable` | POST | Remove `.disabled` file |
| `/api/plugin-lifecycle/uninstall` | POST | Move skill to archive |
| `/api/plugin-lifecycle/restore` | POST | Restore skill from archive |
| `/api/plugin-lifecycle/archive` | GET | List archived skills |
| `/api/plugin-lifecycle/scaffold` | POST | Generate minimal skill scaffold |

## Consequences

### Positive

- **Zero-config plugin management**: Drop a folder = get a plugin. Delete a folder = clean removal. No config files to edit.
- **Self-contained plugins**: Every piece of state (enabled, disabled, archived) lives in the plugin's own directory. `git clone` + `git mv` works perfectly.
- **CLI-first workflow**: TODO markers and folder operations give terminal users first-class support.
- **Safe uninstall**: Archive with one-click restore eliminates fear of losing work.
- **Bundle-level operations**: Creating a new hub is as simple as `mkdir plugins/mytools`.
- **Proactive dependency management**: Removal impact is shown before damage occurs.

### Negative

- **Daemon polling overhead**: 10-second filesystem polls add ~0.1% CPU. Acceptable for the responsiveness gained.
- **Migration required**: One-time migration from `plugin_state.json` and `config.yaml` to `.disabled` files.
- **Archive directory growth**: `plugins/.archive/` can grow unbounded. Nightly cleanup can prune archives older than 90 days.
- **Race conditions**: User modifying files while watcher processes events. Mitigated by snapshot-based diffing (not inotify).

### Neutral

- Existing `mount-plugins.ts` flow remains the same — we add pre-checks, not replace the pipeline.
- Existing `dashboard.yaml` schema unchanged — `.disabled` is a separate file, not a field.
- ADR-121 hub ownership validation runs as before — this ADR adds lifecycle events on top.

## Implementation Order

```
Phase 1: Filesystem Watcher
├── Step 1: Create plugin_watcher.py daemon service
├── Step 2: Implement snapshot diffing and event emission
└── Step 3: Register in unified_daemon.py service list

Phase 2: Filesystem-Based Disable (depends on Phase 1)
├── Step 4: Add .disabled check to mount-plugins.ts discoverPlugins()
├── Step 5: Add .disabled check to skill_registry.py _iter_skill_dirs()
├── Step 6: Add .disabled check to plugin_tools.py MCP discovery
├── Step 7: Write migration script from plugin_state.json → .disabled files
└── Step 8: Update plugin page Enable/Disable buttons to use .disabled files

Phase 3: Archive System (depends on Phase 2)
├── Step 9: Implement archive move logic (skill + bundle level)
├── Step 10: Create archive metadata and .archive-meta.json
├── Step 11: Implement restore logic
└── Step 12: Add "Archived Skills" section to Settings/Plugins page

Phase 4: GUI Wizard & Notifications (depends on Phase 1)
├── Step 13: Create /api/plugin-events polling route
├── Step 14: Build Skill Wizard modal component
├── Step 15: Build Removal Wizard modal component
├── Step 16: Build toast notification system for plugin events
└── Step 17: Wire notifications to wizard modals

Phase 5: TODO Markers & CLI Integration (depends on Phase 1)
├── Step 18: Emit TODO_NEWSKILL files on skill_added events
├── Step 19: Emit TODO_SKILL_REMOVED files on skill_removed events
├── Step 20: Create /skill-setup slash command for CLI scaffold
└── Step 21: Verify scan_code_markers.py picks up new TODO types

Phase 6: Bundle Lifecycle (depends on Phases 1-4)
├── Step 22: Implement bundle detection (new/removed) in watcher
├── Step 23: Auto-generate starter skill for new bundles
├── Step 24: Implement bundle-level archive
└── Step 25: Dependency impact checker for removals

Phase 7: Verification (depends on all)
├── Step 26: Run full test suite
├── Step 27: Verify mount-plugins with .disabled skills
├── Step 28: Verify archive/restore round-trip
├── Step 29: Run stale path scanner
└── Step 30: Update ADR status
```

## Token Cost Analysis

The implementation prompt maps every step to a model tier. Here is the cost impact of tiered model selection vs running everything on Opus.

### Step Distribution

| Tier | Model | Steps | Percentage of Work |
|------|-------|-------|--------------------|
| Low | Haiku ($0.25/$1.25 per M) | 14 | 46.7% |
| Medium | Sonnet ($3/$15 per M) | 16 | 53.3% |
| High | Opus ($15/$75 per M) | 0 | 0% (orchestrator only) |

### Cost Comparison (30 steps, ~690K total tokens)

| Approach | Cost | Savings |
|----------|------|---------|
| All Opus (naive) | $21.15 | — |
| Tiered (this ADR) | $4.68 | **$16.47 (78% saved)** |

### Why It Works

- **14 haiku steps** (file moves, marker creation, verification checks): 98.3% cheaper than Opus. These tasks are mechanical — model capability is irrelevant.
- **16 sonnet steps** (React components, migration scripts, watcher logic): 80% cheaper than Opus. Standard coding tasks where Sonnet matches Opus quality.
- **0 opus worker steps**: Opus reserved exclusively for orchestration (team lead), where broad context awareness matters. Orchestrator budget: ~$2.25.

The tier mapping is the critical design artifact. Without it, the same ADR execution costs 4.5x more with zero quality improvement.

## Alternatives Considered

### Alternative 1: inotify/FSEvents for real-time detection

Rejected because:
- Platform-specific (inotify on Linux, FSEvents on macOS, ReadDirectoryChangesW on Windows)
- Adds native dependency complexity
- 10-second polling is fast enough for human-scale operations (creating/deleting folders)
- Snapshot-based diffing is simpler, testable, and cross-platform

### Alternative 2: Keep centralized plugin_state.json, add watcher on top

Rejected because:
- Violates the self-containment principle — plugin state should live with the plugin
- Makes `git mv` of plugins between machines require config migration
- Two sources of truth (folder exists + config says enabled) create conflicts
- `.disabled` marker file is simpler, more portable, and needs no parsing

### Alternative 3: Use git hooks for plugin detection instead of daemon

Rejected because:
- Only detects changes at commit time, not at folder-creation time
- Users expect immediate feedback when they create a folder
- Not all Augur installations use git for plugin management

## References

- `src/dashboard/scripts/mount-plugins.ts` — Current mount pipeline
- `src/dashboard/lib/plugin-state.ts` — Current centralized plugin state
- `src/plugins/skill_registry.py` — Python skill discovery
- `plugins/observability/skills/daemon/scripts/unified_daemon.py` — Daemon service runner
- `config/system/plugin_state.json` — Current plugin state (to be migrated)
- `.github/scripts/scan_code_markers.py` — TODO marker scanner

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `/write-adr`. Edit if needed before running.

You are implementing **ADR-122: Filesystem-Driven Plugin Lifecycle Management**.

Read the full ADR: `docs/decisions/ADR-122-filesystem-driven-plugin-lifecycle.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-122-plugin-lifecycle", description="Implementing ADR-122: Filesystem-Driven Plugin Lifecycle Management")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-122-plugin-lifecycle", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-122 team.
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

**Team name**: `adr-122-plugin-lifecycle`

#### Phase 1: Filesystem Watcher
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create `plugin_watcher.py` daemon service — poll `plugins/*/skills/*/` every 10s, diff against snapshot, emit events to `runtime/plugin_events.json` | `plugins/observability/skills/daemon/scripts/plugin_watcher.py` |
| 1.2 | developer | low | Create snapshot schema and event schema (`runtime/plugin_watcher_snapshot.json`, `runtime/plugin_events.json`) with FIFO capping at 100 entries | `plugins/observability/skills/daemon/scripts/plugin_watcher.py` |
| 1.3 | devops | low | Register `plugin_watcher.py` in unified daemon service list as a persistent service with 10s interval | `plugins/observability/skills/daemon/scripts/unified_daemon.py` |

#### Phase 2: Filesystem-Based Disable
**Strategy**: PARALLEL (Steps 2.1-2.3 can run concurrently, then 2.4-2.5 sequentially)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Add `.disabled` file check to `discoverPlugins()` in mount-plugins.ts — skip skill if `{skillDir}/.disabled` exists, skip bundle if `{bundleDir}/.disabled` exists | `src/dashboard/scripts/mount-plugins.ts` |
| 2.2 | developer | medium | Add `.disabled` file check to `_iter_skill_dirs()` in skill_registry.py — set `disabled=True` if `.disabled` exists in skill or parent bundle dir | `src/plugins/skill_registry.py` |
| 2.3 | developer | low | Add `.disabled` file check to MCP plugin tool discovery — skip skills with `.disabled` | `src/mcp/augur_mcp/plugin_tools.py` |
| 2.4 | developer | medium | Write migration script `migrate_plugin_state.py` — reads `config/system/plugin_state.json` + `config.yaml` `skills_state.disabled`, creates `.disabled` files, removes old config entries | `src/scripts/migrate_plugin_state.py` |
| 2.5 | developer | medium | Update plugin page Enable/Disable buttons to create/delete `.disabled` files via new API route instead of writing to `plugin_state.json` | `src/dashboard/app/admin/settings/plugins/`, `src/dashboard/app/api/plugin-lifecycle/` |

#### Phase 3: Archive System
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Implement archive move logic — `POST /api/plugin-lifecycle/uninstall` moves skill folder to `plugins/.archive/{bundle}/skills/{skill}/`, creates `.archive-meta.json` | `src/dashboard/app/api/plugin-lifecycle/uninstall/route.ts` |
| 3.2 | developer | medium | Implement restore logic — `POST /api/plugin-lifecycle/restore` moves folder back from archive, triggers mount | `src/dashboard/app/api/plugin-lifecycle/restore/route.ts` |
| 3.3 | developer | medium | Implement bundle-level archive — moves entire bundle to `plugins/.archive/{bundle}/` | `src/dashboard/app/api/plugin-lifecycle/uninstall/route.ts` |
| 3.4 | developer | medium | Add "Archived Skills" section to Settings/Plugins page — lists archived skills from `plugins/.archive/` with Restore button | `plugins/admin/skills/settings/dashboard/plugins/` |

#### Phase 4: GUI Wizard & Notifications
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | low | Create `GET /api/plugin-events` route — reads `runtime/plugin_events.json`, returns unacknowledged events | `src/dashboard/app/api/plugin-events/route.ts` |
| 4.2 | developer | low | Create `POST /api/plugin-events/acknowledge` route — marks events as acknowledged | `src/dashboard/app/api/plugin-events/acknowledge/route.ts` |
| 4.3 | developer | medium | Build Skill Wizard modal component — Quick Setup (scaffold + mount), Configure Manually (open editor), Ignore | `src/dashboard/components/plugin-wizard/SkillWizard.tsx` |
| 4.4 | developer | medium | Build Removal Wizard modal component — shows dependency impact, Clean Up, Undo (if archived) | `src/dashboard/components/plugin-wizard/RemovalWizard.tsx` |
| 4.5 | developer | medium | Build toast notification system — polls `/api/plugin-events` every 15s, shows toasts, opens wizards | `src/dashboard/components/plugin-wizard/PluginEventNotifier.tsx` |
| 4.6 | developer | low | Create `POST /api/plugin-lifecycle/scaffold` route — generates minimal skill scaffold (dashboard.yaml, SKILL.md, starter page) | `src/dashboard/app/api/plugin-lifecycle/scaffold/route.ts` |

#### Phase 5: TODO Markers & CLI Integration
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer | low | Add TODO_NEWSKILL file creation to plugin_watcher.py on `skill_added` events — file created inside the new skill folder | `plugins/observability/skills/daemon/scripts/plugin_watcher.py` |
| 5.2 | developer | low | Add TODO_SKILL_REMOVED file creation to plugin_watcher.py on `skill_removed` events — file created in `runtime/todos/` | `plugins/observability/skills/daemon/scripts/plugin_watcher.py` |
| 5.3 | developer | medium | Create `/skill-setup` slash command — generates scaffold for a given `{bundle}/{skill}` path, removes TODO_NEWSKILL on completion | `plugins/ai/skills/ai_bridge/augur/skills/skill-setup/SKILL.md` |
| 5.4 | validator | low | Verify `scan_code_markers.py` picks up TODO_NEWSKILL and TODO_SKILL_REMOVED marker types | `.github/scripts/scan_code_markers.py` |

#### Phase 6: Bundle Lifecycle
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 6.1 | developer | medium | Add bundle-level detection to plugin_watcher.py — detect new/removed directories under `plugins/`, distinguish from skill-level changes | `plugins/observability/skills/daemon/scripts/plugin_watcher.py` |
| 6.2 | developer | medium | Auto-generate starter skill for new bundles — creates `skills/overview/` with minimal dashboard.yaml (role: primary), SKILL.md, and page.tsx | `plugins/observability/skills/daemon/scripts/plugin_watcher.py` |
| 6.3 | developer | medium | Implement dependency impact checker — on removal, scan all remaining skills' dashboard.yaml dependencies, flag broken required deps with TODO_BROKEN_DEP | `plugins/observability/skills/daemon/scripts/plugin_watcher.py` |

#### Final Phase: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run full test suite (`pytest tests/src/`, `npm run build`), verify no regressions |
| V.2 | validator | low | Test mount-plugins with `.disabled` skills — verify they are skipped in nav and routes |
| V.3 | validator | low | Test archive/restore round-trip — uninstall a skill, verify removal, restore, verify re-mount |
| V.4 | devops | low | Run stale path scanner: `python3 .github/scripts/scan_stale_paths.py --ci` |
| V.5 | architect | low | Verify ADR intent matches implementation, update ADR status to Implemented |

### Stale Path Scan (Conditional)

This ADR involves directory structure changes (new `.archive/` directory, `.disabled` files, migration away from `plugin_state.json`). The final verification MUST include:

```bash
python3 .github/scripts/scan_stale_paths.py --ci
```

### Token Usage Report (MANDATORY)

After all phases complete and before shutdown, the team lead MUST produce a **Token Usage Summary** saved to `runtime/adr-122-token-report.md` with this format:

```markdown
# ADR-122 Token Usage Report

## Execution Summary
- **Total steps executed**: N
- **Team members spawned**: N (list names + models)
- **Total duration**: Xm Ys

## Per-Agent Token Usage
| Agent | Model | Steps Completed | Input Tokens | Output Tokens | Estimated Cost |
|-------|-------|-----------------|--------------|---------------|----------------|
| developer | sonnet | N | ... | ... | $X.XX |
| devops | haiku | N | ... | ... | $X.XX |
| validator | haiku | N | ... | ... | $X.XX |
| orchestrator | opus | 1 (coordination) | ... | ... | $X.XX |

## Cost Comparison
| Approach | Estimated Cost |
|----------|---------------|
| All Opus (projected) | $X.XX |
| Tiered (actual) | $X.XX |
| **Actual savings** | **X% ($X.XX saved)** |

## Per-Phase Breakdown
| Phase | Steps | Strategy | Models Used | Notes |
|-------|-------|----------|-------------|-------|
| 1. Filesystem Watcher | 3 | PIPELINE | sonnet, haiku | ... |
| ... | ... | ... | ... | ... |

## Quality Notes
- Any steps where haiku/sonnet quality was insufficient and required rework: [list or "none"]
- Any steps where a cheaper model could have been used: [list or "none"]
```

**How to collect**: Each teammate reports token usage in their completion message to team lead. The team lead aggregates into the report. If exact token counts are unavailable, estimate based on conversation turns and average tokens per turn (~15K input + ~5K output per step).

This report will be used as real data for a LinkedIn post about tiered model cost savings. Make the numbers accurate.

### Completion Criteria
- [ ] Plugin watcher detects new/removed skills and bundles within 10s
- [ ] `.disabled` file in skill folder prevents mount, MCP registration, and nav inclusion
- [ ] `plugin_state.json` migrated to `.disabled` files, old config removed
- [ ] Uninstall moves to `plugins/.archive/` with metadata; restore works
- [ ] GUI shows toast notifications and wizard modals for plugin events
- [ ] TODO_NEWSKILL and TODO_SKILL_REMOVED markers are created and scannable
- [ ] Bundle creation auto-generates starter skill
- [ ] Dependency impact shown on skill/bundle removal
- [ ] All tests pass
- [ ] Stale path scanner clean
- [ ] ADR status updated to Implemented

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-122-filesystem-driven-plugin-lifecycle.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
