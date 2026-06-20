---
status: Implemented
date: 2026-03-22
deciders:
  - Gursannikov
related:
  - ADR-177
  - ADR-266
hub: null
tags:
  - dashboard
  - performance
  - turbopack
  - nextjs
  - routing
superseded_by: null
---

# ADR-477: Turbopack Catch-All Routes for Dashboard Plugin Pages

## Context

The Augur dashboard dev server was consuming 3-5 GB RSS with 484% CPU under normal use. Root cause: Turbopack maintains a separate module graph per route, and 140 individually mounted `page.tsx` files (89% auto-generated from plugins via `mount-plugins.mjs`) caused Turbopack to track 140 live module graphs simultaneously.

Compounding factors:

- `start-dev.sh` set `--max-old-space-size=8192` (8 GB heap ceiling), allowing V8 GC to defer until 5+ GB RSS rather than collecting early
- `turbopack.root` pointed at the monorepo workspace root, so Turbopack watched the entire tree
- The top 5 pages were 918-1529 lines each (`ai_bridge`: 1529, `daemon`: 1092, `reading-list`: 1019, `workbench`: 950, `learning`: 918), inflating per-page compile cost
- 46 `loading.tsx` and 25 `layout.tsx` files existed in hub subdirectories — all passthrough stubs that added route surface area with no functional value
- `mount-plugins.mjs` operated by file-copying full source files into `apps/dashboard/app/{hub}/{path}/page.tsx`, creating a large mirrored tree of routes that Turbopack had to track

`AUGUR_DEV_HUBS` existed as a partial mitigation but is not a solution since the user works across all hubs.

## Decision

Replace 140 individually mounted `page.tsx` files with 6 hub-level optional catch-all routes (`[[...slug]]/page.tsx`) backed by auto-generated per-hub registries. Split the top 5 oversized pages into focused sub-pages. Reduce the Node.js heap ceiling from 8 GB to 4 GB.

### Catch-All Route Structure

Each hub gets a single `apps/dashboard/app/{hub}/[[...slug]]/page.tsx` (optional catch-all — handles both bare `/brain` and deep `/brain/knowledge/memory` paths). The catch-all reads the slug, looks up the component in an auto-generated `registry.ts`, and renders it via `next/dynamic`. A module-level `DynamicCache` map prevents component reference recreation on re-render.

### Registry Generation

`mount-plugins` now generates one `registry.ts` per hub mapping slug paths to lazy import functions pointing directly at plugin source files. The file-copy step is eliminated. Registry regenerates only on page add/delete events; content edits flow through Turbopack natively via the import path in the registry.

### Page Splits

| Page | Before | Split into |
|------|--------|-----------|
| `ai_bridge` | 1529 lines | `agents`, `providers`, `sync` sub-pages |
| `daemon` | 1092 lines | `self-heal` extracted (~240 lines) |
| `reading-list` | 1019 lines | `articles`, `books`, `notes`, `import` sub-pages |
| `workbench` | 950 lines | `tools`, `audit` sub-pages; advisor section retained |
| `learning` | 918 lines | `courses`, `knowledge`, `guard`, `habits`, `report` sub-pages |

### Heap Ceiling

`start-dev.sh` heap reduced from `--max-old-space-size=8192` (8 GB) to `4096` (4 GB), allowing V8 GC to collect at ~2-3 GB rather than deferring until 5+ GB RSS.

### Tab Registry Validation

`generate-tab-registry.ts` previously validated tabs by checking for mounted `page.tsx` files on disk. Updated to check source files at their plugin paths or registry entries — the same source of truth used by `mount-plugins`.

## Consequences

### Positive

- Dev server RSS dropped ~90%: 3-5 GB settled to 326 MB
- Turbopack route entries reduced from ~140 to ~25 (6 catch-alls + ~19 native routes) — 82% reduction
- `mount-plugins` output reduced from 140+ copied files to 12 files (6 catch-all templates + 6 registries)
- HMR for content edits works natively — no file-copy step means Turbopack watches sources directly
- Startup parse cost: 6 catch-all files + 6 registries instead of 140 files (100-1500 lines each)
- Largest single page reduced from 1529 lines to ~400 lines

### Negative

- First visit to a page incurs ~50-200ms dynamic import cost (vs. instant when pre-compiled). Subsequent visits are instant via module cache.
- Hub landing redirect changes from server-side `redirect()` to client-side `router.replace()` in the catch-all, introducing a one-frame flash. Can be resolved by moving hub landing redirects to `next.config.ts` rewrites in a follow-up.

### Neutral

- 46 passthrough `loading.tsx` stubs replaced by `dynamic()` `loading` prop — equivalent skeleton behavior, fewer files
- 25 passthrough `layout.tsx` stubs removed — `<>{children}</>` passthroughs had no functional impact
- Deep linking and back-button behavior unchanged — URL paths are identical, catch-all resolves the same slugs
- Production builds unaffected — `dynamic()` without `ssr: false` renders synchronously on the server

## Alternatives Considered

### Dynamic Mount Stubs

Generate stub `page.tsx` files that re-export from plugin source rather than copying content. Rejected: still creates 140 route entries — Turbopack still maintains 140 module graphs. Does not address the core problem.

### Multi-Zone Split (Separate Next.js App Per Hub)

Split the dashboard into 6 independent Next.js applications, one per hub. Rejected: major operational complexity — 6 dev servers, cross-zone navigation requires full-page reloads, shared state becomes difficult, deployment complexity multiplies. Disproportionate to the problem.

### Client-Side Tab Routing

Replace Next.js route-per-page with a single-page React state machine. Rejected: loses Next.js routing — no deep linking, no back button, no browser history, no SSR. Breaks the URL-based navigation contract that the rest of the system depends on.

## References

- Spec: `docs/superpowers/specs/2026-03-22-turbopack-catchall-routes-design.md`
- Plan: `docs/superpowers/plans/2026-03-22-turbopack-catchall-routes.md`
- ADR-177: Tab registry validation (affected by mount model change)
- ADR-266: `fs`-exempt pattern for streaming/binary routes (unaffected — catch-all is standard routing)

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - "apps/dashboard/app/{hub}/**/{path}/page.tsx -> apps/dashboard/app/{hub}/[[...slug]]/page.tsx (per hub)"
    - "apps/dashboard/app/{hub}/**/{path}/loading.tsx -> removed (replaced by dynamic() loading prop)"
    - "apps/dashboard/app/{hub}/**/{path}/layout.tsx -> removed (passthrough stubs)"
  apis_changed: []
  patterns_deprecated:
    - "mount-plugins file-copy: copying page.tsx source files into hub subdirectories"
    - "140-route flat mount model: one Next.js route per plugin page"
    - "tab registry validation against mounted page.tsx existence on disk"
  files_affected:
    - "apps/dashboard/app/brain/[[...slug]]/page.tsx"
    - "apps/dashboard/app/brain/[[...slug]]/registry.ts"
    - "apps/dashboard/app/career/[[...slug]]/page.tsx"
    - "apps/dashboard/app/career/[[...slug]]/registry.ts"
    - "apps/dashboard/app/command/[[...slug]]/page.tsx"
    - "apps/dashboard/app/command/[[...slug]]/registry.ts"
    - "apps/dashboard/app/life/[[...slug]]/page.tsx"
    - "apps/dashboard/app/life/[[...slug]]/registry.ts"
    - "apps/dashboard/app/studio/[[...slug]]/page.tsx"
    - "apps/dashboard/app/studio/[[...slug]]/registry.ts"
    - "apps/dashboard/app/adaptive/[[...slug]]/page.tsx"
    - "apps/dashboard/app/adaptive/[[...slug]]/registry.ts"
    - "scripts/mount-plugins.mjs"
    - "apps/dashboard/scripts/generate-tab-registry.ts"
    - "start-dev.sh"
```
