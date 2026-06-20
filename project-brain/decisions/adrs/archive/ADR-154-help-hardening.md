---
status: Implemented
date: '2026-02-25'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- help
- center
- hardening
superseded_by: null
---

# ADR-154: Help Center Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 37/100 | 12% | critical | No GlassCard usage, no loading/error states |
| 2 | Page Coverage | 0/100 | 10% | critical | No tabs defined, flat skill list |
| 3 | API Completeness | 100/100 | 12% | good | 2 API routes with backend logic |
| 4 | MCP Tool Wiring | 0/100 | 10% | critical | Entirely passive — no MCP integration |
| 5 | Performance | 30/100 | 10% | critical | Runtime telemetry needed |
| 6 | User Value | 28/100 | 15% | critical | Read-only, no search or actions |
| 7 | Workflows | 0/100 | 8% | critical | No action workflows |
| 8 | Cross-Hub Connectivity | 20/100 | 5% | critical | No links to hub pages from skill cards |
| 9 | Action Buttons | 0/100 | 8% | critical | No interactivity beyond navigation |
| 10 | Wow Effect | 0/100 | 10% | critical | No search, filter, or grouping |

**Composite Score**: 24/100 (major-rebuild)

## Wow Effect: Skill Search + Filter

> Live search/filter across all skills with category badges, hub grouping, and instant results

**Current state**: Flat grid of skill cards with no search, no grouping, no filtering — and the registry API is broken so the page shows "No Documentation Found"

**Gap to demo-ready**: Fix registry API, add search input, client-side filtering, hub category badges, and grouped layout

**Priority**: This is the headline demo for the hardened Help Center.

## Context

The Help Center (`/help`) is a **core dashboard feature** at `src/dashboard/app/help/`, not a plugin-based hub. It aggregates documentation from all skills by fetching from `/api/registry` and linking to individual skill docs at `/help/[skill]`.

### Critical Blockers

1. **Registry API path bug** — `pythonRunner.ts:resolvePythonScriptPath('augur_cli.py')` resolves to `~/Projects/augur/augur_cli.py` instead of `~/Projects/Augur/scripts/augur_cli.py`. The function uses a hardcoded fallback `path.join(HOME, 'Projects', 'augur')` instead of importing `AUGUR_ROOT` from `paths.ts`. Additionally, `cliRunner.ts` passes `'augur_cli.py'` without the `scripts/` prefix.

2. **README.md coverage: 0/43 up-to-date** — A generator exists at `plugins/ai/skills/mcp-app-factory/scripts/generate_skill_readmes.py` but all 43 skill READMEs are stale or missing. The help page's `[skill]` route prioritizes README.md over SKILL.md.

3. **No hub grouping** — Skills are displayed in a flat alphabetical grid. Users want skills grouped by hub (Career, AI, Dev, etc.) with visual category badges.

### Issues Identified

**UI Compliance** (37/100):
- No GlassCard usage in either `/help` or `/help/[skill]`
- No loading states or error handling
- No interactive elements beyond navigation links

**Page Coverage** (0/100):
- No tabs — could have "All Skills", "By Hub", "Recently Updated"
- Only 2 pages (index + dynamic `[skill]`)

**MCP Tool Wiring** (0/100):
- No MCP integration — help is entirely read-only

**User Value** (28/100):
- No search/filter capability
- No skill metadata display (version, MCP tools count, commands count)
- No "try it" integration

**Cross-Hub Connectivity** (20/100):
- Skill cards don't link to their parent hub pages
- No hub icon/badge on skill cards

## Decision

Implement hardening in three phases. Help is a core dashboard feature, not a plugin — all edits target `src/dashboard/app/help/` and supporting files.

### Phase 1: Fix Blockers (must complete first)

| Step | Task | Files | Tier |
|------|------|-------|------|
| 1.1 | Fix `resolvePythonScriptPath` to import `AUGUR_ROOT` from `paths.ts` instead of hardcoded fallback | `src/dashboard/lib/server/pythonRunner.ts` | low |
| 1.2 | Fix CLI script path: `'augur_cli.py'` → `'scripts/augur_cli.py'` in cliRunner | `src/dashboard/lib/server/cliRunner.ts` | low |
| 1.3 | Run README generator to create/update all 43 skill READMEs | `plugins/ai/skills/mcp-app-factory/scripts/generate_skill_readmes.py` → all `plugins/*/skills/*/README.md` | low |
| 1.4 | Verify `/api/registry` returns skills after fix | Browser test: `fetch('/api/registry')` | low |

### Phase 2: UI + Structure (parallel)

| Step | Task | Files | Tier |
|------|------|-------|------|
| 2.1 | Add hub metadata to registry response — augment each skill with `hub_id`, `hub_icon`, `hub_category` from its `augur.yaml` | `src/dashboard/app/api/registry/route.ts` | medium |
| 2.2 | Redesign help index: group skills by hub, add search/filter bar, add hub category badges, use GlassCard components | `src/dashboard/app/help/page.tsx` (convert to client component with search state) | high |
| 2.3 | Improve skill detail page: add GlassCard wrapper, breadcrumb with hub link, loading skeleton, metadata sidebar (version, MCP tools, commands) | `src/dashboard/app/help/[skill]/page.tsx` | medium |
| 2.4 | Add cross-hub links: each skill card links to both `/help/{skill}` and `/{hub}`, hub section headers link to hub pages | `src/dashboard/app/help/page.tsx` | medium |

### Phase 3: Wow Effect + Polish

| Step | Task | Files | Tier |
|------|------|-------|------|
| 3.1 | Implement live search: client-side instant filter by skill name, description, hub, commands | `src/dashboard/app/help/page.tsx` | medium |
| 3.2 | Add skill count badges per hub section and total count in header | `src/dashboard/app/help/page.tsx` | low |
| 3.3 | Add "Jump to hub" action button — quick-navigate to any hub from help | `src/dashboard/app/help/page.tsx` | low |

### Phase 4: Verification

| Step | Task | Tier |
|------|------|------|
| V.1 | Browser validation: open `/help`, verify skills load grouped by hub, search works | low |
| V.2 | Click through 3-5 skill detail pages, verify README content renders | low |
| V.3 | Run `npm run build` to verify no TypeScript errors | low |
| V.4 | Run `python3 generate_skill_readmes.py --check` to verify READMEs are in sync | low |

## User Notes

Help should group skills by their parent hub (Career, AI, Dev, etc.) — not display as a flat list. Hub sections should be visually distinct with the hub icon and link to the hub page.

## Consequences

### Positive

- Help Center becomes the central documentation hub with live search and hub grouping
- All 43 skills get up-to-date README.md files generated from SKILL.md
- Registry API bug fixed — unblocks help page and any other consumers
- `pythonRunner.ts` path resolution fixed to use `AUGUR_ROOT` from canonical source

### Negative

- Help index page needs conversion from server component to client component for search state
- 43 README.md files added to git (auto-generated, but adds to repo size)

### Neutral

- Existing help page structure preserved (index + `[skill]` dynamic route)
- API completeness stays at 100/100

## Alternatives Considered

1. **Plugin-based help hub** — Could make help a plugin with `augur.yaml` and `dashboard.yaml`. Rejected: help is a system feature that aggregates across all plugins; making it a plugin creates circular dependency.
2. **Static site generation for docs** — Could pre-generate help pages at build time. Rejected: would lose real-time skill discovery and add build complexity.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- Audit report: `plugins/dev/skills/frontend/augur/data/hardening-reports/help_20260225.yaml`
- README generator: `plugins/ai/skills/mcp-app-factory/scripts/generate_skill_readmes.py`
- Key files: `src/dashboard/app/help/page.tsx`, `src/dashboard/app/help/[skill]/page.tsx`, `src/dashboard/lib/server/pythonRunner.ts`, `src/dashboard/lib/server/cliRunner.ts`

## Implementation Prompt

> Paste this into Claude Code to execute this ADR.

You are implementing **ADR-154: Help Center Hardening**.

Read the full ADR: `docs/decisions/ADR-154-help-hardening.md`

### Phase 1: Fix Blockers

1. **Fix pythonRunner.ts**: Import `AUGUR_ROOT` from `'../paths'` and use it in both `resolvePythonScriptPath()` and `getAugurPythonPath()` instead of the hardcoded `path.join(HOME, 'Projects', 'augur')` fallback.

2. **Fix cliRunner.ts line 9**: Change `resolvePythonScriptPath('augur_cli.py')` to `resolvePythonScriptPath('scripts/augur_cli.py')`.

3. **Generate all READMEs**: Run `python3 plugins/ai/skills/mcp-app-factory/scripts/generate_skill_readmes.py` to create/update all 43 skill README.md files.

4. **Verify**: Open `http://localhost:3000/help` — skills should now load.

### Phase 2: UI + Structure

5. **Augment registry API** (`src/dashboard/app/api/registry/route.ts`): For each skill in the response, add `hub_id` and `hub_icon` fields by reading the skill's `augur.yaml` → `contributes_to` and `hub.icon` fields.

6. **Redesign help index** (`src/dashboard/app/help/page.tsx`):
   - Convert to client component with search state
   - Group skills by hub with hub icon + hub name section headers
   - Add search input at the top that filters across name, description, hub
   - Each skill card: GlassCard, hub badge, description, command count
   - Hub section headers link to `/{hub_id}`
   - Empty state for search with "No matching skills"

7. **Improve skill detail** (`src/dashboard/app/help/[skill]/page.tsx`):
   - Wrap content in GlassCard
   - Add loading skeleton
   - Add hub breadcrumb link (← Hub Name)
   - Display metadata sidebar: version, command count, hub

8. **Cross-hub links**: Each skill card has a hub badge that links to `/{hub_id}`. Hub section headers are clickable.

### Phase 3: Polish

9. **Live search**: Instant client-side filter with debounce. Show match count. Highlight matching text.

10. **Counts**: Show total skill count in header, per-hub counts in section headers.

### Completion Criteria

- [ ] `/api/registry` returns skills (was broken)
- [ ] All 43 README.md files generated and up-to-date
- [ ] Help page groups skills by hub
- [ ] Search/filter works across all skills
- [ ] GlassCard UI compliance
- [ ] Cross-hub links from skill cards to hub pages
- [ ] `npm run build` passes
- [ ] `generate_skill_readmes.py --check` passes
