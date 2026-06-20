# UI Skill Architecture — Post-Migration Dashboard Redesign

**Date:** 2026-03-23
**Status:** Draft
**Scope:** Dashboard UI ownership, skill merging, coupling model, recovery

## Problem

The ADR-426/430 skills migration moved 188 skills from `plugins/` to `skills/`, deleting the `plugins/` directory. This left 344 dashboard UI files lost (recoverable from git) and 79 pre-rendered pages orphaned in `apps/dashboard/lib/plugin-pages/` with no source-of-truth. The mount system references `plugins/ui/pages/` which no longer exists. Custom pages will break after the next build.

Additionally, the root `package.json` and `node_modules/` (660 dirs) serve a single workspace package (`apps/dashboard/`), adding unnecessary boilerplate to the Python-focused project root.

## Decisions

### 1. Four Locations

All dashboard content maps to exactly one of four locations:

| Location | Role | Rule |
|----------|------|------|
| `apps/dashboard/` | Next.js shell — framework, build scripts, generated routes, node_modules | Don't author UI here |
| `skills/dashboard/` | UI skill — source of truth for all authored dashboard content | Edit here |
| `get_vault_dir()/dashboard/` | User data — preferences, saved layouts, custom themes | Runtime state |
| `apps/dashboard/node_modules/` | Third-party packages — React, Next.js, shadcn, etc. | Inside apps/ only |

**Eliminated:** Root `package.json`, root `node_modules/`, `pnpm-workspace.yaml`. The dashboard is a standalone Next.js project inside `apps/dashboard/`, not a pnpm workspace.

**API routes:** `apps/dashboard/app/api/` stays in the shell. These are MCP proxy routes (catch-all pattern per ADR-260) — infrastructure, not authored content. Any skill-scoped API routes must be audited for MCP-compliance; non-compliant routes should be converted to MCP proxy calls or moved to `skills/dashboard/`.

**Hub identity:** `skills/dashboard/` is a cross-hub skill — it does not belong to any single hub. Its SKILL.md uses `x-augur-hub: system` (the infrastructure hub). The hub alignment check in `mount-plugins.ts` Phase 3b is updated to skip alignment validation when `x-augur-hub: system` — system-hub skills are infrastructure and exempt from bundle-hub matching. This is the only skill with this exemption.

### 2. Three UI Layers

The original four-layer model (browse, autopages, blocks, custom pages) collapses to three. Blocks are not a separate layer — they are an internal implementation detail of autopages.

| Layer | Scope | Who decides what's shown | Where it lives |
|-------|-------|-------------------------|---------------|
| **Browse / Discovery** | All 188 skills | Central — reads SKILL.md metadata | `skills/dashboard/framework/browse/` |
| **Autopages** (includes blocks) | Most skills | Skill pulls — declares blocks, actions, data sources in SKILL.md | `skills/dashboard/framework/autopage/` |
| **Custom Pages** | ~60 pages, cross-skill | Page pulls — consumes MCP tools from any skill | `skills/dashboard/pages/{hub}/{page}/` |

**Key finding:** Of the 79 "custom pages" in `lib/plugin-pages/`, 12 are three-line `SkillAutoPage` wrappers (`return <SkillAutoPage skillId="..." />`). These are not custom pages — they're autopages with route aliases and become unnecessary when the mount system renders autopages directly.

### 3. Coupling Model

Skills and the UI skill are loosely coupled through MCP tool names — the only contract.

**Skills expose capabilities:**
- MCP tools (data sources)
- Block declarations in SKILL.md `x-augur-config.contributions.blocks[]` (for autopages)
- Actions (IDE dispatch)
- Page route declarations in `x-augur-dashboard-pages`

**UI skill consumes:**
- Custom pages call MCP tools freely from any skill
- Autopages render blocks declared in SKILL.md
- No direct imports between skills

**Mount system gates on skill presence:**
- For each installed skill with `x-augur-dashboard-pages`: look for matching page in `skills/dashboard/pages/{hub}/{page}/`
- If found: mount the custom page
- If not found: render autopage from SKILL.md metadata (fallback)
- If skill removed: SKILL.md gone → page not mounted → page file stays dormant in UI skill at zero cost

**Direction of control:**
- Autopages: skill pulls (skill's SKILL.md defines what it wants)
- Custom pages: page pulls (page decides which MCP tools to consume, can be cross-skill)

### 4. Merged UI Skill

`skills/dashboard/` absorbs four existing skills into one:

| Source | What it brings | MCP tools |
|--------|---------------|-----------|
| `lib/plugin-pages/` (recovery) | ~60 real custom pages + page components | 0 |
| `skills/mcp-app-factory/` | Plugin create/audit/migrate/import | 19 |
| `skills/frontend/` | Design system audit, component discovery | 4 |
| `skills/page-builder/` | Template viewer, page composition | ~5 |
| git recovery (`dist/plugins/`) | 344 deleted UI files to evaluate | 0 |

The merged `SKILL.md` combines all metadata, actions, MCP tools, and page declarations.

### 5. Node Modules Inside apps/dashboard/

Root workspace boilerplate eliminated:
- Root `package.json` (was just `pnpm --filter dashboard` proxy)
- Root `node_modules/` (660 dirs hoisted for one package)
- `pnpm-workspace.yaml` (one-entry workspace)
- Root `pnpm-lock.yaml`

`apps/dashboard/` becomes a standalone Next.js project with its own `package.json` and `node_modules/`. The `/dev-build` command handles path resolution.

## Directory Layout

```
skills/dashboard/
├── SKILL.md                    # merged: UI + app-factory + frontend + page-builder
├── pages/                      # all custom pages, organized by hub
│   ├── career/
│   │   ├── pipeline/page.tsx
│   │   ├── interview/page.tsx
│   │   └── ...
│   ├── life/
│   │   ├── finance/page.tsx
│   │   ├── attention/page.tsx
│   │   └── ...
│   ├── brain/
│   │   ├── knowledge/page.tsx
│   │   ├── ai_bridge/page.tsx
│   │   └── ...
│   ├── adaptive/
│   │   ├── auto-vault-hygiene/page.tsx
│   │   ├── auto-skill-quality/skill-scores/page.tsx
│   │   └── ...
│   ├── command/
│   │   ├── daemon/page.tsx
│   │   ├── workflows/page.tsx
│   │   └── ...
│   └── studio/
│       ├── factory/page.tsx
│       └── ...
├── framework/                  # autopage + blocks (merged), browse, page-builder
│   ├── autopage/               # SkillAutoPage + block renderers + block types
│   ├── browse/                 # skill discovery UI
│   └── page-builder/           # template composition
├── components/                 # shared: GlassCard, DashboardWidget, chat, agents...
├── lib/                        # hooks, stores, MCP client, types, utils
└── scripts/                    # app-factory MCP tools (Python)

apps/dashboard/                 # thin Next.js shell
├── app/                        # generated catch-all routes
│   ├── {hub}/[[...slug]]/      # dynamic routes per hub
│   ├── api/                    # MCP proxy routes
│   ├── layout.tsx              # root layout
│   └── page.tsx                # home page
├── scripts/                    # mount-plugins.ts, generators
├── next.config.ts              # turbopack.root and outputFileTracingRoot updated
├── tsconfig.json               # see "TypeScript Configuration" below
├── package.json                # standalone (no workspace)
└── node_modules/               # contained here, not at root
```

### TypeScript Configuration

The `@/` alias in `apps/dashboard/tsconfig.json` must resolve to `skills/dashboard/` (two directories up, then into `skills/dashboard/`). Required changes:

```jsonc
{
  "compilerOptions": {
    "baseUrl": "../..",                    // repo root
    "paths": {
      "@/*": ["skills/dashboard/*"]        // resolves to ../../skills/dashboard/*
    }
  },
  "include": [
    "../../skills/dashboard/**/*.ts",
    "../../skills/dashboard/**/*.tsx",
    "app/**/*.ts",
    "app/**/*.tsx",
    "scripts/**/*.ts"
  ]
}
```

`next.config.ts` must also be updated:
- Remove `outputFileTracingRoot: workspaceRoot` (no workspace to trace)
- Update `turbopack.root` to repo root (already set to `path.resolve(__dirname, "../..")`)
- The `externalDir: true` setting (already present) allows imports from outside `apps/dashboard/`

### Mount System Changes

The current `mount-plugins.ts` hardcodes `plugins/ui/pages/` as the source and `plugins/ui/manifest.yaml` for route declarations. Both are replaced:

- **Page source:** `skills/dashboard/pages/{hub}/{page}/` replaces `plugins/ui/pages/{hub}/{page}/`. Same directory structure, new root.
- **Route declarations:** Eliminated. The mount system discovers pages by scanning `skills/dashboard/pages/` directories and cross-referencing against installed skills' `x-augur-dashboard-pages` in their SKILL.md. No separate manifest file.
- **Functions affected:** `collectManifestPages` (remove — no manifest.yaml), `collectConventionPages` (new source: `skills/dashboard/pages/` replacing `plugins/ui/pages/`), `buildHubRegistries` (update source), `generateRegistries` (update import paths to `@/pages/{hub}/{page}/`)
- **Watch mode:** In `startWatchMode`, add an explicit `fsWatch` on `skills/dashboard/pages/` (recursive) alongside the existing per-skill `augur/dashboard/` watchers. This is a new watch target, not a glob pattern change.

## Recovery Plan

1. **Recover** — `git checkout` deleted pages from `dist/plugins/` pre-deletion commit. Evaluate 344 files for relevance.
2. **Create `skills/dashboard/`** — Scaffold SKILL.md (merged), `pages/`, `framework/`, `components/`, `lib/`.
3. **Move pages** — `lib/plugin-pages/` → `skills/dashboard/pages/`. Remove AUTO-GENERATED markers. Rewrite import paths: `@/lib/plugin-pages/{hub}/{skill}/` references become `@/pages/{hub}/{skill}/`. Promote to source-of-truth.
4. **Remove autopage wrappers** — The 12 three-line `SkillAutoPage` stubs become unnecessary. Mount system renders autopage directly when no custom page exists.
5. **Update tsconfig** — Set `baseUrl: "../.."` (repo root), update `paths` so `@/*` maps to `skills/dashboard/*`, extend `include` to cover `../../skills/dashboard/**/*.ts{,x}`. See "TypeScript Configuration" section.
6. **Update next.config.ts** — Remove `outputFileTracingRoot` (no workspace hoisting). Keep `turbopack.root` at repo root. Verify `externalDir: true` is present.
7. **Update mount system** — Replace `plugins/ui/pages/` source path with `skills/dashboard/pages/`. Remove `collectManifestPages` (no manifest.yaml). Update `collectConventionPages` path. Add `skills/dashboard/pages/**` to watch mode glob.
8. **Merge skills** — Absorb `skills/mcp-app-factory/`, `skills/frontend/`, `skills/page-builder/` into `skills/dashboard/`. Combine SKILL.md files. Set `x-augur-hub: system` with cross-hub exemption.
9. **Audit API routes** — Review `apps/dashboard/app/api/` for skill-scoped routes. Confirm all use MCP proxy pattern. Convert any direct `fs`/`spawn` calls.
10. **Eliminate root workspace** — Remove root `package.json`, `pnpm-workspace.yaml`. Move `pnpm-lock.yaml` to `apps/dashboard/`. Run `pnpm install` inside `apps/dashboard/`. Update `/dev-build` path resolution.
11. **Verify** — Build dashboard, confirm all pages render, all MCP tools register, all blocks resolve. Test hot-reload on page changes in `skills/dashboard/pages/`.

## Key Constraints

- **No direct imports between skills** — MCP tool name is the only contract. Imports within `skills/dashboard/` (e.g., a page importing a shared component) are intra-skill, not cross-skill.
- **Regular skills never contain TSX** — All 187 non-dashboard skills expose capabilities via SKILL.md + MCP tools, never UI code. `skills/dashboard/` is the sole exception — it IS the UI layer, not a skill that contributes to it. This exception is architectural, not a workaround.
- **Mount system is the gatekeeper** — Only mounts pages whose declaring skill is installed
- **Custom pages are cross-skill** — A pipeline page can consume tools from career, interview, and resume skills
- **Dormant pages are zero cost** — If a skill is removed, its page stays in `skills/dashboard/` unmounted

## What This Replaces

- The deleted `plugins/{bundle}/skills/{skill}/augur/dashboard/` pattern
- The orphaned `apps/dashboard/lib/plugin-pages/` cache
- The broken `plugins/ui/pages/` mount target
- Three separate skills (`mcp-app-factory`, `frontend`, `page-builder`)
- Root pnpm workspace boilerplate for a single package
