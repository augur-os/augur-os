---
status: Implemented
date: '2026-02-13'
deciders:
- Gur Sannikov
related:
- ADR-012 (Community Package Extraction)
- ADR-018 (Plugin Self-Containment)
- ADR-020 (Bundle Structure)
- ADR-040 (Portable Plugin Template)
hub: null
tags:
- plugin
- page
- hardening
superseded_by: null
---

# ADR-095: Plugin Page Hardening

## Context

The current plugin management page (`PluginsTab.tsx` in Settings) provides basic enable/disable toggling and Python dependency installation, but falls short of a real plugin lifecycle manager:

1. **Install/Uninstall are stubs** — The MCP tools `install-plugin` and `uninstall-plugin` exist but delegate to `registry.install_plugin()` / `registry.uninstall_plugin()` which don't actually download or delete plugin files from disk. The dashboard UI has no install/uninstall buttons at all.

2. **No export per plugin** — The `export-skill-plugin` MCP tool exists but only works for crew skills and is not surfaced in the plugin UI. Users cannot release/share individual plugins from the dashboard.

3. **Rebuild is manual** — After toggling plugins, the user sees a yellow "Rebuild Required" notice telling them to run `npm run build` manually. There's no rebuild button, no progress indicator, and no test validation.

4. **Disable doesn't unmount** — `plugin_state.json` marks plugins as disabled, and `mount-plugins.ts` skips disabled plugins during build, but there's no feedback loop — the user has to rebuild manually to actually remove the disabled plugin's routes.

5. **No dependency tree** — Plugins can depend on each other (e.g., `career` needs `knowledge` for RAG search, `lifestyle` uses `channels` for notifications). Currently `dashboard.yaml` has no dependency declaration, `plugin_state.json` has no dependency enforcement, and users can disable a plugin that other enabled plugins depend on.

### Current Plugin Lifecycle (Broken)

```
Install:   registry.install_plugin() → updates registry only, no file download
Uninstall: registry.uninstall_plugin() → updates registry only, no file deletion
Enable:    plugin_state.json[id] = true → no rebuild
Disable:   plugin_state.json[id] = false → no rebuild
Export:    export-skill-plugin MCP tool → crew skills only, not in UI
Build:     mount-plugins.ts → reads plugin_state.json, mounts enabled only
```

## Decision

### 1. Real Install/Uninstall

**Install** downloads a plugin from a source (git URL, local path, or tarball) into `plugins/{bundle}/skills/{name}/` and registers it in `plugin_state.json` as enabled.

**Uninstall** removes the plugin directory from `plugins/` and removes its entry from `plugin_state.json`. Core plugins (shipped with the repo) cannot be uninstalled — only user-installed plugins.

#### Install Flow
```
Source (git URL / local path / tarball)
  → Download/extract to plugins/{bundle}/skills/{name}/
  → Validate SKILL.md exists
  → Read dashboard.yaml for hub ID
  → Add to plugin_state.json as enabled
  → Trigger auto-rebuild (see section 3)
```

#### Uninstall Flow
```
Plugin ID
  → Check not a core plugin (core plugins ship with repo)
  → Check no other enabled plugins have "required" dependency on it
  → Remove plugin directory from plugins/
  → Remove from plugin_state.json
  → Remove mounted files from src/dashboard/app/{hubId}/
  → Trigger auto-rebuild (see section 3)
```

**Files to create/modify**:
- `src/mcp/augur_mcp/domain/plugins.py` — implement real file operations in `install_plugin_tool` and `uninstall_plugin_tool`
- `src/dashboard/app/api/plugins/install/route.ts` — new API route for install
- `src/dashboard/app/api/plugins/uninstall/route.ts` — new API route for uninstall
- `src/dashboard/app/settings/tabs/PluginsTab.tsx` — add Install/Uninstall buttons

### 2. Export Per Plugin

Every plugin gets an "Export" action in the plugin card UI. Clicking it runs the export pipeline:

1. Read `SKILL.md`, `dashboard.yaml`, and skill directory structure
2. Package into a distributable format (tarball or zip)
3. Generate a `plugin.json` manifest with metadata, version, dependencies
4. Save to `dist/plugins/{name}-{version}.tar.gz`
5. Show download link in UI

The existing `export-skill-plugin` MCP tool and `skill_exporter.py` script are extended to work for all bundles (not just crew) and exposed via a dashboard API route.

**Files to create/modify**:
- `plugins/ai/skills/mcp-app-factory/scripts/skill_exporter.py` — extend to support all bundles
- `src/mcp/augur_mcp/infrastructure/config.py` — update `export-skill-plugin` to accept any bundle
- `src/dashboard/app/api/plugins/export/route.ts` — new API route
- `src/dashboard/app/settings/tabs/PluginsTab.tsx` — add Export button per plugin card

### 3. Auto-Rebuild with Progress

After any state change (enable, disable, install, uninstall), the system automatically triggers a rebuild with user confirmation:

#### Flow
```
State change detected
  → Show confirmation dialog: "Rebuild dashboard to apply changes?"
  → User confirms
  → Show progress animation (spinner with stage labels)
  → Stage 1: Remount plugins (mount-plugins.ts)
  → Stage 2: Build dashboard (next build)
  → Stage 3: Run tests (npm run test -- --passWithNoTests)
  → Show result: success/failure with logs
```

#### UI Component
A `RebuildDialog` component that:
- Shows a modal with progress stages
- Streams build output via SSE (Server-Sent Events)
- Displays success/failure state with expandable log output
- Auto-dismisses on success after 3 seconds

**Files to create/modify**:
- `src/dashboard/app/settings/components/RebuildDialog.tsx` — new component (source in plugin)
- `src/dashboard/app/api/plugins/rebuild/route.ts` — new SSE endpoint that runs mount + build + test
- `src/dashboard/app/settings/tabs/PluginsTab.tsx` — integrate RebuildDialog, remove static "Rebuild Required" notice

### 4. Disable Behavior Hardening

When a plugin is disabled:
- Its files **stay on disk** in `plugins/{bundle}/skills/{name}/`
- `plugin_state.json[id]` is set to `false`
- Auto-rebuild triggers (section 3), which causes `mount-plugins.ts` to skip the disabled plugin
- The plugin's routes, API endpoints, and lib mounts are removed from `src/dashboard/`
- The plugin's MCP tools are excluded from tool loading (already handled by `mcp_tool_groups.yaml`)

When re-enabled:
- `plugin_state.json[id]` is set to `true`
- Auto-rebuild re-mounts the plugin
- All routes and tools become available again

This is already mostly correct in code — the hardening is:
1. Adding auto-rebuild to the toggle flow (instead of manual rebuild notice)
2. Ensuring `cleanPluginMounts()` in `mount-plugins.ts` properly cleans up disabled plugin directories

**Files to modify**:
- `src/dashboard/scripts/mount-plugins.ts` — add explicit cleanup of disabled plugins (currently only cleans symlinks and `.plugin-mount` directories, should also clean directories of newly-disabled plugins)
- `src/dashboard/app/settings/tabs/PluginsTab.tsx` — replace "Rebuild Required" notice with auto-rebuild

### 5. Plugin Dependency Tree

#### Declaration Format

Each plugin declares its dependencies in `dashboard.yaml`:

```yaml
# dashboard.yaml
version: "1"
hub:
  id: career
  title: Career Hub
  subtitle: Job search and career management
  icon: Briefcase

dependencies:
  required:
    - knowledge    # career cannot function without RAG search
    - ai_bridge    # career needs AI bridge for resume analysis
  optional:
    - channels     # if enabled, career can send notifications
    - apple        # if enabled, career syncs with Apple Calendar
```

**Two dependency modes**:

| Mode | Behavior |
|------|----------|
| `required` | Plugin **cannot be enabled** unless all required dependencies are also enabled. If user enables this plugin and a required dep is disabled, system prompts to enable the dep too. If user disables a required dep, system warns about dependents and either blocks or cascades disable. |
| `optional` | Plugin works without the dependency, but some features are degraded. UI shows an info badge: "Install X to enable Y feature". No blocking behavior. |

#### Dependency Resolution

A new `DependencyResolver` class handles:

1. **Forward resolution**: Given a plugin, what does it need?
2. **Reverse resolution**: Given a plugin, what depends on it?
3. **Transitive resolution**: If A requires B and B requires C, enabling A requires C too
4. **Cycle detection**: Prevent circular dependencies
5. **Enable cascade**: When enabling a plugin with required deps, prompt user to enable all missing deps
6. **Disable protection**: When disabling a plugin that others require, warn and optionally cascade-disable dependents

#### UI Integration

Each plugin card shows:
- **Dependency badge**: "Requires: knowledge, ai_bridge" (for required deps)
- **Optional badge**: "Enhanced by: channels, apple" (for optional deps)
- **Dependent badge**: "Required by: lifestyle, content" (reverse lookup)

When toggling:
- **Enable with missing required deps**: Dialog listing missing deps with "Enable all" button
- **Disable with active dependents**: Dialog listing affected plugins with "Disable all" or "Cancel"

#### Dependency API

```
GET /api/plugins/dependency-tree
  → Returns full dependency graph for visualization

GET /api/plugins/{id}/dependencies
  → Returns { required: [...], optional: [...], requiredBy: [...] }
```

**Files to create/modify**:
- `plugins/*/skills/*/dashboard.yaml` — add `dependencies:` section to plugins that have cross-plugin dependencies
- `src/dashboard/lib/dependency-resolver.ts` — new module for dependency resolution logic
- `src/dashboard/app/api/plugins/dependency-tree/route.ts` — new API route for full tree
- `src/dashboard/app/settings/tabs/PluginsTab.tsx` — dependency badges and cascade dialogs
- `src/dashboard/scripts/mount-plugins.ts` — validate dependency satisfaction before mounting
- `src/mcp/augur_mcp/domain/plugins.py` — dependency validation in toggle/install/uninstall tools

#### Initial Dependency Map

Based on codebase analysis, the initial `required` and `optional` declarations:

| Plugin | Required | Optional |
|--------|----------|----------|
| career | knowledge, ai_bridge | channels, apple, google-workspace |
| health | knowledge | apple, wearables, channels |
| finance | knowledge | google-workspace |
| content | knowledge, ai_bridge | channels, linkedin-writer |
| lifestyle | knowledge | channels, apple, home-automation |
| eisenhower | — | apple, channels |
| home-automation | — | channels |
| venture-augur | knowledge, ai_bridge | finance |
| client-ai-consulting | knowledge, ai_bridge | — |
| client-smb-design | knowledge, ai_bridge | — |
| client-terminal-automation | knowledge | — |
| observer | daemon | — |
| executor | — | — |
| router | executor | — |
| swarm | executor, router | ai_bridge |
| developer | knowledge | — |
| validator | knowledge | — |
| frontend | knowledge | — |
| devops | knowledge | daemon |
| mcp-app-factory | knowledge, developer | — |
| advisor | knowledge | — |

## Consequences

### Positive

- Plugin install/uninstall actually works — users can download community plugins and remove them
- Export enables plugin sharing without manual file juggling
- Auto-rebuild removes the error-prone manual `npm run build` step
- Dependency tree prevents broken states where a required plugin is disabled
- Optional dependencies enable graceful degradation
- The dependency graph visualization gives users visibility into plugin relationships

### Negative

- Every `dashboard.yaml` across 30+ plugins needs a `dependencies:` section (but many will be empty)
- Auto-rebuild adds latency to toggle operations (~30-60s for build)
- Dependency resolution adds complexity to enable/disable logic
- Transitive dependency chains could surprise users ("enabling X also enables A, B, C")

### Neutral

- Core plugins remain non-uninstallable — this is by design
- The export format (tarball) is simple and doesn't require a package registry
- SSE for build progress is standard Next.js pattern

## Implementation Order

```
Phase 1: Dependency System (Foundation)
├── Step 1: Add dependencies to dashboard.yaml schema
├── Step 2: Create DependencyResolver class
├── Step 3: Add dependency API routes
└── Step 4: Populate initial dependency declarations

Phase 2: Auto-Rebuild (Core UX)
├── Step 5: Create rebuild SSE API route
├── Step 6: Create RebuildDialog component
└── Step 7: Integrate into PluginsTab

Phase 3: Install/Uninstall (Lifecycle)
├── Step 8: Implement real file operations in MCP tools
├── Step 9: Create install/uninstall API routes
├── Step 10: Add UI buttons and dialogs
└── Step 11: Wire dependency validation into install/uninstall

Phase 4: Export (Distribution)
├── Step 12: Extend skill_exporter.py for all bundles
├── Step 13: Create export API route
└── Step 14: Add export button to plugin cards

Phase 5: Disable Hardening (Polish)
├── Step 15: Update mount-plugins.ts cleanup logic
└── Step 16: Replace manual rebuild notice with auto-rebuild

Phase 6: Verification
├── Step 17: Run all tests
├── Step 18: Verify dependency cascade in UI
└── Step 19: Test full lifecycle: install → enable → disable → uninstall
```

## Alternatives Considered

### Alternative 1: Package Registry (npm-style)

Build a central registry service where plugins are published and discovered.

**Rejected**: Over-engineering for a personal system. Tarball export + git URL install is sufficient. A registry can be added later if community adoption grows.

### Alternative 2: Hot Reload Instead of Rebuild

Use Next.js dynamic imports and runtime plugin loading to avoid full rebuilds.

**Rejected**: Next.js App Router doesn't support dynamic route registration at runtime. Plugins need to be mounted as filesystem routes at build time. The rebuild approach is simpler and more reliable.

### Alternative 3: Flat Dependency List (No Required/Optional Split)

All dependencies are required — no optional mode.

**Rejected**: Many plugin integrations are "nice to have" (e.g., career + channels for notifications). Forcing required dependencies would create unnecessary coupling and make the system harder to configure.

## References

- ADR-012: Community Package Extraction
- ADR-018: Plugin Self-Containment
- ADR-020: Bundle Structure (crew, services, apps, orchestrator)
- ADR-040: Portable Plugin Template Standard
- `src/dashboard/app/settings/tabs/PluginsTab.tsx` — current plugin UI
- `src/dashboard/scripts/mount-plugins.ts` — build-time plugin mounting
- `src/dashboard/lib/plugin-state.ts` — plugin state reader
- `src/mcp/augur_mcp/domain/plugins.py` — MCP plugin tools
- `config/system/plugin_state.json` — plugin enabled/disabled state
- `plugins/ai/skills/mcp-app-factory/scripts/skill_exporter.py` — existing export script

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-095: Plugin Page Hardening**.

Read the full ADR: `docs/decisions/ADR-095-plugin-page-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-095-plugin-hardening", description="Implementing ADR-095: Plugin Page Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-095-plugin-hardening", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-095-plugin-hardening team.
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

**Team name**: `adr-095-plugin-hardening`

#### Phase 1: Dependency System (Foundation)
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Add `dependencies` schema to `dashboard.yaml` type definitions in mount-plugins.ts (DashboardYaml interface). Add `required: string[]` and `optional: string[]` fields | `src/dashboard/scripts/mount-plugins.ts` |
| 1.2 | developer | medium | Create `DependencyResolver` class: forward/reverse/transitive resolution, cycle detection, enable cascade, disable protection. Unit tests included | `src/dashboard/lib/dependency-resolver.ts`, `src/dashboard/lib/dependency-resolver.test.ts` |
| 1.3 | developer | medium | Create dependency tree API route (`GET` returns full graph, `GET ?pluginId=X` returns single plugin deps). Create individual plugin dependency API | `src/dashboard/app/api/plugins/dependency-tree/route.ts` |
| 1.4 | developer | low | Populate `dependencies:` section in dashboard.yaml for all 30+ plugins using the dependency map from the ADR | `plugins/consulting/skills/*/dashboard.yaml`, `plugins/ai/skills/*/dashboard.yaml`, `plugins/dev/skills/*/dashboard.yaml`, `plugins/orchestration/skills/*/dashboard.yaml` |

#### Phase 2: Auto-Rebuild (Core UX)
**Strategy**: PIPELINE (depends on Phase 1)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create rebuild SSE API route: runs mount-plugins + next build + npm test in sequence, streams progress events via Server-Sent Events | `src/dashboard/app/api/plugins/rebuild/route.ts` |
| 2.2 | frontend | medium | Create `RebuildDialog` component: modal with progress stages, SSE streaming, success/failure display, expandable log output, auto-dismiss on success. Source in settings plugin dir | `plugins/ai/skills/ai_bridge/augur/settings/components/RebuildDialog.tsx` (or appropriate plugin source location) |
| 2.3 | frontend | medium | Integrate RebuildDialog into PluginsTab: trigger after toggle/install/uninstall, remove static "Rebuild Required" yellow notice | `src/dashboard/app/settings/tabs/PluginsTab.tsx` |

#### Phase 3: Install/Uninstall (Lifecycle)
**Strategy**: PARALLEL (depends on Phase 1)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Implement real file operations in `install_plugin_tool`: git clone / extract tarball to `plugins/{bundle}/skills/{name}/`, validate SKILL.md, register in plugin_state.json | `src/mcp/augur_mcp/domain/plugins.py` |
| 3.2 | developer | medium | Implement real file operations in `uninstall_plugin_tool`: check not core plugin, check no required dependents, delete plugin directory, remove from plugin_state.json | `src/mcp/augur_mcp/domain/plugins.py` |
| 3.3 | developer | medium | Create install/uninstall API routes for dashboard: install accepts source URL/path, uninstall accepts plugin ID | `src/dashboard/app/api/plugins/install/route.ts`, `src/dashboard/app/api/plugins/uninstall/route.ts` |
| 3.4 | frontend | medium | Add Install button (opens dialog for source URL/path input) and Uninstall button (with confirmation dialog, disabled for core plugins) to PluginsTab plugin cards | `src/dashboard/app/settings/tabs/PluginsTab.tsx` |

#### Phase 4: Export (Distribution)
**Strategy**: PIPELINE (depends on Phase 3)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Extend `skill_exporter.py` to support all bundles (apps, services, orchestrator), not just crew. Generate plugin.json manifest with dependencies from dashboard.yaml | `plugins/ai/skills/mcp-app-factory/scripts/skill_exporter.py` |
| 4.2 | developer | medium | Update `export-skill-plugin` MCP tool to accept bundle parameter, resolve skill path for any bundle | `src/mcp/augur_mcp/infrastructure/config.py` |
| 4.3 | developer | medium | Create export API route: triggers export, returns download path | `src/dashboard/app/api/plugins/export/route.ts` |
| 4.4 | frontend | low | Add Export button to each plugin card in PluginsTab, shows download link after export completes | `src/dashboard/app/settings/tabs/PluginsTab.tsx` |

#### Phase 5: Disable Hardening (Polish)
**Strategy**: PARALLEL (depends on Phase 2)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer | medium | Update `mount-plugins.ts` to explicitly clean up directories of newly-disabled plugins during mount (compare enabled list vs mounted directories) | `src/dashboard/scripts/mount-plugins.ts` |
| 5.2 | frontend | medium | Add dependency badges to plugin cards (required, optional, requiredBy). Add cascade enable/disable confirmation dialogs when toggling plugins with dependencies | `src/dashboard/app/settings/tabs/PluginsTab.tsx` |

#### Phase 6: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 6.1 | validator | low | Run `npm run build` in `src/dashboard/` — verify clean build |
| 6.2 | validator | low | Run `npm run test` in `src/dashboard/` — verify all tests pass |
| 6.3 | validator | low | Run `pytest tests/src/` — verify Python tests pass |
| 6.4 | validator | low | Verify dependency cascade: enable career, check knowledge auto-prompted. Disable knowledge, check career warns |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`, `npm run test`)
- [ ] No orphaned files or broken references
- [ ] Dependency declarations exist in all plugin dashboard.yaml files
- [ ] Install/uninstall actually creates/removes files on disk
- [ ] Export works for all 4 bundles (apps, services, crew, orchestrator)
- [ ] Auto-rebuild triggers after every state change
- [ ] ADR status updated to "Accepted" or "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-095-plugin-page-hardening.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
