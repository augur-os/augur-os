---
status: Implemented
date: 2026-03-23
deciders:
  - Gur Sannikov
related: [426, 430, 260, 163]
hub: system
tags: [dashboard, ui, skills, architecture, pages, tsconfig]
superseded_by: null
---

# ADR-483: UI Skill Architecture

## Context

ADR-426/430 migrated 188 skills from `plugins/` to `skills/`, deleting the `plugins/` directory. This orphaned 344 dashboard UI files (recoverable from git) and left 79 pre-rendered pages in `apps/dashboard/lib/plugin-pages/` with no source-of-truth. The mount system still referenced `plugins/ui/pages/` which no longer existed — custom pages would break on the next build.

Separately, the root `package.json` and `node_modules/` (660 hoisted dirs) existed only to serve a single workspace package (`apps/dashboard/`), adding unnecessary boilerplate to a Python-focused project root.

## Decision

### 1. `skills/dashboard/` is the single source of truth for all authored dashboard UI

Four locations with strict roles:

| Location | Role |
|----------|------|
| `apps/dashboard/` | Next.js shell — framework, generated routes, build scripts |
| `skills/dashboard/` | UI skill — all authored pages, components, lib |
| `get_vault_dir()/dashboard/` | User data — preferences, saved layouts |
| `apps/dashboard/node_modules/` | Third-party packages — contained here only |

`skills/dashboard/` carries `x-augur-hub: system` and is exempt from hub-alignment validation in `mount-plugins.ts`. It is the only system-hub exemption.

### 2. Three UI layers (blocks merged into autopages)

The four-layer model collapses to three — blocks are an internal detail of autopages, not a separate layer:

| Layer | Scope | Coupling direction |
|-------|-------|--------------------|
| Browse / Discovery | All skills | Central reads SKILL.md metadata |
| Autopages (incl. blocks) | Most skills | Skill pulls — declares blocks in SKILL.md |
| Custom Pages | ~60 cross-skill pages | Page pulls — consumes MCP tools from any skill |

12 three-line `SkillAutoPage` wrappers discovered in `lib/plugin-pages/` are classified as autopage aliases, not custom pages, and eliminated.

### 3. Loose coupling via MCP tool names only

Skills expose: MCP tools, block declarations in `x-augur-config.contributions.blocks[]`, actions, and page route declarations in `x-augur-dashboard-pages`. The UI skill consumes via MCP tool names — no direct imports between skills. Mount system gates page mounting on the declaring skill being installed; orphaned page files are dormant at zero cost.

### 4. `skills/dashboard/` absorbs three separate skills

`skills/mcp-app-factory/`, `skills/frontend/`, and `skills/page-builder/` are merged into `skills/dashboard/`. Their SKILL.md metadata, MCP tools, actions, and page declarations are combined into a single merged SKILL.md.

### 5. Root pnpm workspace eliminated

Root `package.json`, `pnpm-workspace.yaml`, root `pnpm-lock.yaml`, and root `node_modules/` are removed. `apps/dashboard/` becomes a standalone Next.js project. `/dev-build` handles path resolution.

### 6. Dual tsconfig paths

`apps/dashboard/tsconfig.json` sets `baseUrl: "../.."` (repo root) and `paths: { "@/*": ["skills/dashboard/*"] }`. The `include` array covers `../../skills/dashboard/**/*.ts{,x}`. `next.config.ts` removes `outputFileTracingRoot`, keeps `turbopack.root` at repo root, and retains `externalDir: true` for out-of-tree imports.

## Consequences

### Positive
- Single source-of-truth for all dashboard UI eliminates the orphaned `lib/plugin-pages/` cache
- Mount system discovers pages by scanning `skills/dashboard/pages/` — no separate manifest file
- Dormant pages (skill removed) incur zero cost — no mount, no build artifact
- Three redundant skills consolidated into one
- Root boilerplate eliminated: 660 hoisted node_modules dirs gone from project root

### Negative
- `@/` imports in all pages must be re-resolved after tsconfig path change
- Mount system requires updates: remove `collectManifestPages`, update `collectConventionPages` source path, add watch on `skills/dashboard/pages/`
- Any agent/CI that ran `pnpm install` at root must update to `pnpm install` inside `apps/dashboard/`

### Neutral
- Regular skills still never contain TSX — `skills/dashboard/` is the sole exception, and this exception is architectural
- API routes (`apps/dashboard/app/api/`) stay in the shell as MCP proxy infrastructure (ADR-260 catch-all pattern)

## Alternatives Considered

### Keep `lib/plugin-pages/` as source-of-truth
Rejected: it was always an auto-generated cache, not a source. Promoting it would entrench the workaround.

### Per-skill UI directories (`plugins/{bundle}/skills/{skill}/augur/dashboard/`)
The original pattern from before ADR-426. Rejected: deleted by the migration; reintroducing it requires re-adding `plugins/` which was explicitly removed. Cross-skill pages also can't live in a per-skill directory.

### Separate `skills/ui/` skill (not merged)
Rejected: having mcp-app-factory, frontend, and page-builder as separate skills creates fragmented ownership of what is a single concern — the dashboard UI layer.

## References

- Source spec: `docs/superpowers/specs/2026-03-23-ui-skill-architecture-design.md`
- ADR-426: Skills Migration (Claude Code-mastered skills)
- ADR-430: Plugin migration cost and schedule
- ADR-260: MCP proxy catch-all routes
- ADR-163: Plugin decentralization

## Impact Manifest

```yaml
skills_merged:
  - skills/mcp-app-factory/  → skills/dashboard/
  - skills/frontend/         → skills/dashboard/
  - skills/page-builder/     → skills/dashboard/

files_added:
  - skills/dashboard/SKILL.md
  - skills/dashboard/pages/{hub}/{page}/page.tsx  # ~60 pages recovered/moved

files_removed:
  - package.json               # root workspace proxy
  - pnpm-workspace.yaml
  - pnpm-lock.yaml             # root-level
  - node_modules/              # 660 hoisted dirs

files_modified:
  - apps/dashboard/tsconfig.json  # baseUrl + paths + include
  - apps/dashboard/next.config.ts  # remove outputFileTracingRoot
  - apps/dashboard/scripts/mount-plugins.ts  # new page source + watch target

patterns_deprecated:
  - plugins/ui/pages/  # replaced by skills/dashboard/pages/
  - apps/dashboard/lib/plugin-pages/  # was cache, now eliminated
  - root pnpm workspace  # single-package workspace boilerplate
```
