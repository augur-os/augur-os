---
status: Implemented
date: 2026-03-21
deciders:
  - Gur Sannikov
related:
  - ADR-001
  - ADR-005
  - ADR-006
  - ADR-038
  - ADR-084
  - ADR-087
  - ADR-105
  - ADR-109
  - ADR-129
  - ADR-163
  - ADR-270
  - ADR-426
  - ADR-430
  - ADR-450
  - ADR-462
hub: null
tags:
  - architecture
  - review
  - tech-debt
  - hardening
superseded_by: null
---

# ADR-466: Architecture Review Q1 2026 — System-Wide Audit and Tech Debt Remediation

## Context

A full architecture review of the Augur system was conducted on 2026-03-21, covering all five layers: Python backend, Next.js dashboard, plugin system, daemon/self-heal, and config/infrastructure. The review identified architectural strengths, confirmed pattern adherence, and surfaced tech debt and inconsistencies that need remediation.

### System Scale at Time of Review

| Metric | Value |
|--------|-------|
| Total skills | 139 |
| Skills with MCP tools | 58 |
| ADRs | 316 (283 implemented, 18 superseded, 4 accepted, 4 deprecated) |
| API routes (proxy) | 329 static + 38 dynamic |
| Daemon services | 11 |
| Adaptive loop categories | 10 |
| IDE/CLI agents supported | 8 |
| CI workflows | 10 |
| Config namespaces | 7 |
| Block types | 17 |

### Architecture Summary

The system comprises five layers:

1. **Dashboard** (Next.js 16, React 19, Tailwind 4) — Universal catch-all API proxy (367→1 route consolidation), 17-type block system, WebMCP browser-side tool registration, TanStack Query with 6 cache tier presets, Zustand for client state.

2. **MCP Server** (FastMCP, Python, stdio/SSE) — 4-group tool registration (core, domain, infrastructure, self-update), `KERNEL_AVAILABLE` compat layer for standalone/monorepo duality, `mcp_tool_interceptor` for correlation IDs, context-aware tool visibility filtering.

3. **Plugin System** — 139 skills across 6 hubs, SKILL.md frontmatter as single source of truth (ADR-430), 6-phase build-time mount pipeline, skills can live in any client-native folder (`.claude/skills/`, `.codex/prompts/`, `.gemini/skills/`, plugin cache) or in `plugins/{bundle}/skills/{skill}/`.

4. **Daemon** — Single parent + 11 persistent child services, self-heal pipeline (emit→scan→route→fix), adaptive loop engine with 10 categories and budgeted execution.

5. **Config** — 7 namespaces (ADR-087), external state/logs/cache per ADR-270, multi-agent model abstraction (fast/standard/deep across 7 clients).

### Strengths Confirmed

- **Genuine decentralization** — Adding a skill requires zero central file edits. `assembled-hubs.json` is fully generated.
- **Catch-all proxy** — 461→23 route files; adding an endpoint is a 5-line config entry.
- **ADR discipline** — 316 decisions with 89.6% implementation rate.
- **Standalone/monorepo duality** — `KERNEL_AVAILABLE` compat layer cleanly gates monorepo-specific code.
- **Self-heal resilience** — `emit_heal_event()` never raises, uses atomic file ops, has retention rotation.
- **Cache tier presets** — 6 volatility classes mapped to appropriate TanStack Query stale times.

## Decision

Remediate the identified tech debt in 6 targeted fixes, ordered by impact and dependency.

### Fix 1: Unify Path Resolution (High Priority)

**Problem**: `src/config/paths.py` and `src/mcp/augur_mcp/config.py` implement overlapping path logic. `config.py` hardcodes `"Augur"` as the project name while `paths.py` reads `project.yaml`. Any rename or multi-tenant deployment breaks one or the other.

**Fix**: Extract a shared `AugurPaths` base module consumed by both. The standalone mode should read the same `project.yaml` (or accept a fallback constant) rather than maintaining a parallel implementation.

**Files**:
- `src/config/paths.py` — refactor to export reusable path primitives
- `src/mcp/augur_mcp/config.py` — delegate to shared primitives, remove duplication
- `src/mcp/augur_mcp/compat.py` — update bridge logic

### Fix 2: Consolidate SkillMetadata (High Priority)

**Problem**: Three separate `SkillMetadata` definitions exist across `skill_discovery.py`, `interfaces/skill_registry.py`, and `skill_registry.py` (compat re-export). Runtime conversion happens at every `list_skills()`/`resolve_skill()` call.

**Fix**: Make `SkillRecord` from `skill_discovery.py` the single canonical type. Update the `SkillRegistry` ABC to use it. Remove the MCP-layer `SkillMetadata` and its conversion logic.

**Files**:
- `src/plugins/skill_discovery.py` — canonical `SkillRecord` (no changes)
- `src/mcp/augur_mcp/interfaces/skill_registry.py` — use `SkillRecord` directly
- `src/mcp/augur_mcp/adapters/filesystem_registry.py` — remove conversion
- `src/mcp/augur_mcp/compat.py` — remove SkillMetadata bridge
- `src/plugins/skill_registry.py` — update re-export

### Fix 3: Move Scan Targets to State (Medium Priority)

**Problem**: `config/system/self_heal.yaml` accumulates `discovered_scan_targets` at runtime — config being mutated as state violates ADR-087's "no runtime data in config" rule.

**Fix**: Move `discovered_scan_targets` to `~/Library/Application Support/Augur/state/self_heal/scan_targets.yaml`. Keep static routing rules in `config/system/self_heal.yaml`. Update daemon's `log_monitor.py` and `adaptive_loop_executor.py` to read from state dir.

**Files**:
- `config/system/self_heal.yaml` — remove `discovered_scan_targets` section
- `.claude/skills/daemon/scripts/log_monitor.py` — read targets from state dir
- `.claude/skills/daemon/scripts/adaptive_loop_executor.py` — same
- `src/config/paths.py` — add `get_self_heal_state_dir()` if needed

### Fix 4: Add ESLint Rule for spawn/exec (Medium Priority)

**Problem**: ESLint blocks `fs` imports in API routes (ADR-453) but doesn't block `child_process`, `spawn`, `exec`, or `node-pty` — subprocess execution paths remain open.

**Fix**: Extend the existing `no-restricted-imports` ESLint rule to cover `child_process`, `node:child_process`, and `node-pty` in `app/api/**` files. Add `// @spawn-exempt: <reason>` escape hatch consistent with the existing `@fs-exempt` pattern.

**Files**:
- `apps/dashboard/.eslintrc.json` or equivalent ESLint config
- Any API routes with legitimate spawn usage — add exemption comments

### Fix 5: Platform Guard for Apple Daemon Services (Medium Priority)

**Problem**: `note_watcher` and `note_ingest` daemon services reference Apple-specific scripts and paths but have no platform guard. On non-macOS systems, these will fail at startup.

**Fix**: Gate both services behind `sys.platform == 'darwin'` in `unified_daemon.py`'s service list construction.

**Files**:
- `.claude/skills/daemon/scripts/unified_daemon.py` — conditional service registration

### Fix 6: Fix HMR Interval Leaks (Low Priority)

**Problem**: `TODO_BUG` markers in `MCPBridge.handleDisconnect()` and `mount-plugins.ts` flag `setInterval` without `globalThis` guards and unbounded `Map`/`Set` in watcher mode. These leak on HMR reloads in development.

**Fix**: Add `globalThis` singleton guards for intervals in `MCPBridge`. Add cleanup/bound limits for module-level collections in `mount-plugins.ts`.

**Files**:
- `apps/dashboard/lib/mcp/connection.ts` — `globalThis` interval guard
- `apps/dashboard/scripts/mount-plugins.ts` — collection bounds

## Consequences

### Positive

- Path resolution becomes single-source-of-truth across standalone and monorepo modes
- SkillMetadata consolidation eliminates per-call conversion overhead and reduces confusion
- Config/state separation restores ADR-087 compliance
- Spawn/exec ESLint rule closes an enforcement gap alongside the existing `fs` rule
- Platform guards prevent daemon crashes on non-macOS systems
- HMR leak fixes improve developer experience

### Negative

- Fix 1 (path unification) may require updating standalone pip package consumers
- Fix 2 (SkillMetadata consolidation) is a breaking change for any external code importing from `interfaces/skill_registry.py`

### Neutral

- The review confirms that documentation about plugin locations (`plugins/` and client-native folders) is architecturally correct — both paths are valid and supported by the mount pipeline
- No changes needed to the catch-all proxy, block system, or hub assembly — these are architecturally sound

## Alternatives Considered

### Alternative 1: Full Plugin Relocation

Move all 139 skills from `.claude/skills/` to `plugins/{bundle}/skills/{skill}/` to match the `ARCHITECTURE.md` bundle model more closely.

Rejected: Both locations are architecturally valid per ADR-426. The mount pipeline supports both. Forcing a relocation would be churn with no user-facing benefit.

### Alternative 2: Rewrite MCP Server Without Standalone Mode

Remove the `KERNEL_AVAILABLE` compat layer and always require the full monorepo.

Rejected: Standalone mode enables pip-installable distribution and simpler testing. The compat layer works; it just needs shared path primitives instead of duplicated logic.

## References

- ADR-001: Three-Layer Architecture
- ADR-005: MCP as Execution Gateway
- ADR-006: Local-First Architecture
- ADR-084: Unix fail-fast self-heal events
- ADR-087: Config namespace elimination of `data/`
- ADR-109: Filesystem-driven dashboard
- ADR-163: Config decentralization
- ADR-270: External directory layout
- ADR-426: Claude Code-mastered skills
- ADR-430: SKILL.md frontmatter as source of truth
- ADR-450: Template-driven dashboard with UI plugin extraction
- ADR-453: Dashboard vault decoupling + prevention gates

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-466-arch-review-fixes`

### Phase 1: Path Unification + SkillMetadata Consolidation
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Extract shared path primitives from `paths.py`, update `augur_mcp/config.py` to delegate instead of duplicate. Verify standalone mode still works. | `src/config/paths.py`, `src/mcp/augur_mcp/config.py`, `src/mcp/augur_mcp/compat.py` |
| 1.2 | developer | high | Make `SkillRecord` the single canonical type. Update `SkillRegistry` ABC, remove MCP-layer `SkillMetadata`, eliminate conversion in `filesystem_registry.py`. | `src/plugins/skill_discovery.py`, `src/mcp/augur_mcp/interfaces/skill_registry.py`, `src/mcp/augur_mcp/adapters/filesystem_registry.py`, `src/mcp/augur_mcp/compat.py`, `src/plugins/skill_registry.py` |

### Phase 2: Config/State Separation + ESLint + Platform Guards
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Move `discovered_scan_targets` from `self_heal.yaml` to state dir. Update daemon readers. | `config/system/self_heal.yaml`, `.claude/skills/daemon/scripts/log_monitor.py`, `.claude/skills/daemon/scripts/adaptive_loop_executor.py` |
| 2.2 | developer | medium | Add `child_process`/`node-pty` to ESLint `no-restricted-imports` for `app/api/**`. Add `@spawn-exempt` pattern. | ESLint config, API routes with legitimate spawn usage |
| 2.3 | developer | low | Gate `note_watcher` and `note_ingest` behind `sys.platform == 'darwin'` in daemon service list. | `.claude/skills/daemon/scripts/unified_daemon.py` |

### Phase 3: HMR Leak Fixes + Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Add `globalThis` interval guards in MCPBridge, bound collections in mount-plugins watcher. | `apps/dashboard/lib/mcp/connection.ts`, `apps/dashboard/scripts/mount-plugins.ts` |
| 3.2 | validator | medium | Run full test suite: pytest, npm test, tsc, npm run build. Verify no regressions. | All test files |

### Completion Criteria
- [ ] `src/mcp/augur_mcp/config.py` delegates to shared path primitives (no duplicated resolution)
- [ ] Single `SkillRecord` type used across all modules (zero `SkillMetadata` conversion calls)
- [ ] `config/system/self_heal.yaml` contains only static routing rules (no runtime-accumulated data)
- [ ] ESLint blocks `child_process`/`spawn` imports in API routes
- [ ] Apple daemon services skipped on non-macOS platforms
- [ ] No `TODO_BUG` markers for HMR interval leaks remain
- [ ] All existing tests pass
- [ ] ADR status updated to Implemented
