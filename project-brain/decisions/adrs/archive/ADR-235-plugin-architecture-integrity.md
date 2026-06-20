---
status: Implemented
date: '2026-03-05'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- plugin
- architecture
- integrity
superseded_by: null
---

# ADR-235: Plugin Architecture Integrity

**Related ADRs**: ADR-163 (Plugin Decentralization), ADR-218 (Primary Skill Split Mount), ADR-200 (Adaptive Loop Engine)

## Context

AI agents building Augur routinely violate the decentralized plugin architecture (CLAUDE.md Rule #1, ADR-163). An audit revealed violations across 5 categories:

1. **Hub misalignment** — 3 plugins live in `plugins/ai/` but serve admin/dev hubs via `contributes_to`. The `install` and `page-builder` skills are in the `ai` bundle but contribute to `admin`. The `mcp-app-factory` skill is in `ai` but contributes to `dev`.

2. **Redirect sprawl** — 66 redirect-only `page.tsx` files exist: 22 plugin sources in `ai_bridge/augur/dashboard/` that redirect `/ai/*` to other hubs, plus 44 mounted copies in `src/dashboard/app/ai/` and `src/dashboard/app/ai/ai_bridge/`. These were created as compatibility stubs when pages moved cross-hub instead of moving the plugin itself.

3. **Duplicate route pairs** — 55 files across 5 hubs (career, finance, health, home, lifestyle) where pages are mounted at BOTH `/{hub}/{subpage}/` and `/{hub}/{skill}/{subpage}/`. Caused by `mountPrimaryDashboard()` in `copier.ts` copying subdirectories to both hub root and skill path per ADR-218.

4. **Centralized config** — ~1500 lines of per-plugin data in central config files instead of plugin `augur.yaml`:
   - `src/dashboard/config/page-skills.yaml` (621 lines)
   - `config/dashboard/mcp_tool_groups.yaml` (200+ lines)
   - `config/dashboard/app_mode.yaml` (~100 lines)
   - `config/dashboard/mcp_tools.yaml` (~170 lines skill-specific)
   - `config/system/plugin_state.json` (~50 entries)
   - `config/notes/*.txt` (2 files)

5. **No enforcement** — No lint checks or agent instructions prevent agents from creating these violations.

## Decision

### Phase 1: Hub Realignment + Redirect Cleanup (Immediate)

**Move 3 misaligned plugins** to their correct hub bundles:

| Plugin | From | To |
|--------|------|----|
| install | `plugins/ai/skills/install/` | `plugins/admin/skills/install/` |
| page-builder | `plugins/ai/skills/page-builder/` | `plugins/admin/skills/page-builder/` |
| mcp-app-factory | `plugins/ai/skills/mcp-app-factory/` | `plugins/dev/skills/mcp-app-factory/` |

All 3 plugins are fully self-contained with zero cross-dependencies. No `augur.yaml` path updates needed — all use relative paths, and `contributes_to` already matches the target hub.

**Delete 22 redirect-only source pages** from `plugins/ai/skills/ai_bridge/augur/dashboard/` (audit, catalog, create, import, install/*, mcp-app-factory/*, migrate, page-builder/*, registry, schedules, templates, terminal, tools).

**Delete 44 mounted redirect stubs** from `src/dashboard/app/ai/` and `src/dashboard/app/ai/ai_bridge/`.

**Rebuild** mount artifacts via `npm run mount-plugins`.

### Phase 2: Fix Duplicate Route Pairs

**Modify `mountPrimaryDashboard()`** in `src/dashboard/scripts/mount/copier.ts` to split directory handling:

- **Support directories** (`tabs`, `components`, `hooks`, `lib` — already in `HUB_ROOT_SUPPORT_DIRS`) → mount to hub root ONLY. These serve relative imports from `page.tsx`.
- **Page directories** (everything else) → mount to skill path ONLY. These are routable at `/{hub}/{skill}/{page}/`.

This eliminates the duplicate route pairs while preserving both the hub root overview page (with its relative imports) and the skill-scoped subpage routing.

### Phase 3: Decentralize Config (Incremental)

Migrate centralized config files to plugin `augur.yaml` declarations + assembly scripts. Each migration follows the same pattern as `assembled_hubs.json`: plugins declare data in their own `augur.yaml`, an assembly script generates the centralized format.

Priority order:
1. `config/notes/*.txt` → plugin `augur/data/notes/` (trivial, immediate)
2. `src/dashboard/config/page-skills.yaml` → `contributions.pages` in augur.yaml (needs assembly script)
3. `config/dashboard/mcp_tool_groups.yaml` → `mcp.tool_groups` in augur.yaml (needs assembly script)
4. `config/dashboard/app_mode.yaml` → `mcp.app_tools` in augur.yaml
5. `config/dashboard/mcp_tools.yaml` → skill-specific tool categories in augur.yaml
6. `config/system/plugin_state.json` → `state.enabled` in augur.yaml

Items 2–6 each require their own ADR for the migration pattern.

### Phase 4: Prevention (Ships with Phase 1)

**Lint check — hub alignment**: Add to `plugin_lint.py` `scan()` function. For each `plugins/{bundle}/skills/{skill}/augur.yaml`, verify `contributes_to` matches `{bundle}`. Severity: HIGH. No auto-fix (moves are too risky for automation).

**Agent instructions**: Add Critical Rule #11 to `agent-rules.md` (source for CLAUDE.md): "A plugin's `contributes_to` MUST match its bundle directory. Cross-hub contribution is not allowed. Move the plugin instead." Add "Hub Alignment Rules" section to `SKILLS.md` agent topic.

## Consequences

### Positive

- Plugin ownership is unambiguous — bundle directory = hub assignment
- AI agents have clear rules preventing future hub misalignment
- 66 redirect-only pages removed, reducing route confusion and build time
- 55 duplicate route files removed, eliminating ghost routes
- Lint check catches violations before they accumulate
- Path to fully decentralized config (Phase 3) is defined

### Negative

- Bookmarked URLs at `/ai/install`, `/ai/page-builder`, `/ai/mcp-app-factory` will 404 after redirect removal
- Phase 3 config migrations are substantial work (5 separate ADRs)
- Phase 2 mount script change requires testing across all 5 affected hubs

### Neutral

- Mount script `mountPrimaryDashboard()` logic changes but the public behavior (pages routable at `/{hub}/{skill}/{page}/`) is preserved
- AI bridge plugin retains its legitimate pages (agents, integrations, providers, setup, etc.) — only redirect stubs are removed

## Alternatives Considered

### Alternative 1: Keep plugins in ai/ and formalize cross-hub contribution

Keep plugins where they are, add a `contributes_to` cross-hub pattern as a legitimate architectural choice, and document it.

**Rejected** because: Cross-hub contribution makes plugin ownership ambiguous. When an agent sees `plugins/ai/skills/install/`, it assumes the skill is part of the AI hub. The `contributes_to: admin` field is an indirect override that agents frequently miss. Moving the plugin makes ownership self-evident from the filesystem.

### Alternative 2: Re-route plugins back to ai hub

Change `contributes_to` to `ai` so the plugins mount under `/ai/install`, `/ai/page-builder`, etc.

**Rejected** because: These skills functionally belong to admin and dev. Install is a system administration tool. Page-builder is an admin dashboard builder. MCP-app-factory is a developer tool. Routing them under `/ai/` would confuse users navigating the dashboard.

## References

- ADR-163: Plugin Decentralization
- ADR-218: Primary Skill Split Mount (explains the duplicate route mechanism)
- ADR-200: Adaptive Loop Engine (plugin_lint runs as part of hardening loop)
- Design doc: `docs/plans/2026-03-05-plugin-architecture-integrity-design.md`
- Implementation plan: `docs/plans/2026-03-05-plugin-architecture-integrity-impl.md`

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "plugins/ai/skills/install/"
      to: "plugins/admin/skills/install/"
      scope: "plugins/ai/skills/install/**"
    - from: "plugins/ai/skills/page-builder/"
      to: "plugins/admin/skills/page-builder/"
      scope: "plugins/ai/skills/page-builder/**"
    - from: "plugins/ai/skills/mcp-app-factory/"
      to: "plugins/dev/skills/mcp-app-factory/"
      scope: "plugins/ai/skills/mcp-app-factory/**"
  patterns_deprecated:
    - grep: "plugins/ai/skills/install"
      replacement: "plugins/admin/skills/install"
    - grep: "plugins/ai/skills/page-builder"
      replacement: "plugins/admin/skills/page-builder"
    - grep: "plugins/ai/skills/mcp-app-factory"
      replacement: "plugins/dev/skills/mcp-app-factory"
  files_affected:
    - glob: "plugins/ai/skills/ai_bridge/augur/dashboard/*/page.tsx"
    - glob: "src/dashboard/app/ai/*/page.tsx"
    - glob: "src/dashboard/app/ai/ai_bridge/*/page.tsx"
    - glob: "src/dashboard/scripts/mount/copier.ts"
    - glob: "plugins/observability/skills/daemon/scripts/ops/plugin_lint.py"
    - glob: "plugins/ai/skills/ai_bridge/augur/data/agent-topics/SKILLS.md"
    - glob: "plugins/ai/skills/ai_bridge/augur/data/agent-rules.md"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-235-plugin-integrity`

### Phase 1: Hub Realignment
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | `git mv plugins/ai/skills/install/ plugins/admin/skills/install/` | `plugins/ai/skills/install/**` |
| 1.2 | developer | low | `git mv plugins/ai/skills/page-builder/ plugins/admin/skills/page-builder/` | `plugins/ai/skills/page-builder/**` |
| 1.3 | developer | low | `git mv plugins/ai/skills/mcp-app-factory/ plugins/dev/skills/mcp-app-factory/` | `plugins/ai/skills/mcp-app-factory/**` |
| 1.4 | developer | low | Commit all 3 moves | — |

### Phase 2: Redirect Cleanup
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Delete 22 redirect-only source pages from ai_bridge plugin | `plugins/ai/skills/ai_bridge/augur/dashboard/*/page.tsx` |
| 2.2 | developer | medium | Delete 44 mounted redirect stubs from src/dashboard/app/ai/ | `src/dashboard/app/ai/*/page.tsx`, `src/dashboard/app/ai/ai_bridge/*/page.tsx` |
| 2.3 | developer | low | Run `npm run mount-plugins`, verify mounts, commit | `src/dashboard/app/**` |

### Phase 3: Fix Duplicate Routes
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | high | Modify `mountPrimaryDashboard()` — support dirs to hub root only, page dirs to skill path only | `src/dashboard/scripts/mount/copier.ts:637-649` |
| 3.2 | developer | low | Run `mount-plugins:clean && mount-plugins`, verify duplicates gone | `src/dashboard/app/**` |
| 3.3 | validator | medium | TypeScript check — fix any broken relative imports | `src/dashboard/**` |

### Phase 4: Prevention
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Add hub alignment scanner to `plugin_lint.py` `scan()` + test | `plugins/observability/skills/daemon/scripts/ops/plugin_lint.py`, `tests/test_ops_plugin_lint_hub.py` |
| 4.2 | developer | low | Add Hub Alignment Rules section to SKILLS.md | `plugins/ai/skills/ai_bridge/augur/data/agent-topics/SKILLS.md` |
| 4.3 | developer | low | Add Critical Rule #11 to agent-rules.md, regenerate CLAUDE.md | `plugins/ai/skills/ai_bridge/augur/data/agent-rules.md`, `CLAUDE.md` |

### Phase 5: Config Decentralization (notes only)
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer | low | Move `config/notes/*.txt` to plugin data dirs | `config/notes/`, `plugins/consulting/skills/client-smb-design/augur/data/notes/`, `plugins/professional/skills/venture-augur/augur/data/notes/` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | medium | Run TypeScript build, verify no errors |
| V.2 | validator | low | Run `plugin_lint.py scan` — verify 0 hub misalignments |
| V.3 | validator | low | Verify no redirect stubs remain under `src/dashboard/app/ai/` |
| V.4 | validator | low | Verify no duplicate route dirs exist for career/finance/health/home/lifestyle |
| V.5 | architect | low | Grep for stale `plugins/ai/skills/install` references across codebase |

### Completion Criteria
- [ ] All 3 plugins moved to correct hub bundles
- [ ] 66 redirect-only pages deleted (22 sources + 44 mounted)
- [ ] 55 duplicate route files eliminated via mount script fix
- [ ] Hub alignment lint check passes with 0 violations
- [ ] CLAUDE.md Rule #11 and SKILLS.md Hub Alignment section added
- [ ] TypeScript build passes
- [ ] `config/notes/` files moved to plugin data dirs
- [ ] ADR status updated to Implemented
