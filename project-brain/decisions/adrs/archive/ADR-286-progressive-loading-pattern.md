---
status: Implemented
date: '2026-03-08'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- progressive
- loading
- pattern
- external
- system
superseded_by: null
---

# ADR-286: Progressive Loading Pattern for External System Pages

## Context

Dashboard pages that connect to external systems (Philips Hue, Sonos, Google APIs, financial services) block all rendering until every API call completes. The `/home` page, for example, fires 3 parallel MCP-backed fetches (lights, speakers, scenes) and shows a monolithic skeleton until all resolve — typically 2-5 seconds.

Current problems:
1. **All-or-nothing rendering** — if lights respond in 500ms but speakers take 3s, nothing renders until 3s
2. **Basic skeletons** — static `animate-pulse` gray boxes with no visual richness
3. **No retry logic** — transient MCP/network failures show a full-page error requiring manual retry
4. **No caching** — navigating away and back triggers full re-fetch with skeleton flash
5. **Aggressive polling bugs** — 500ms and 2000ms polling intervals marked as TODO_BUG cause CPU/network churn

These issues affect multiple pages: `/home`, `/finance`, `/productivity/google-workspace/calendar`, `/health/wearables/watch`.

## Decision

Introduce a reusable progressive loading system with three primitives:

### 1. `useProgressiveData` hook (`src/dashboard/hooks/useProgressiveData.ts`)

- Accepts a config object mapping section keys to `{ fetcher, ttl, retries }`
- Fires all fetches in parallel, resolves each independently
- Returns per-section state: `{ data, isLoading, error, isStale, retry }`
- Auto-retry with exponential backoff (1s → 2s → 4s, max 3 attempts)
- Stale-while-revalidate: serves cached data immediately on re-mount, refetches in background
- In-memory `Map` cache with configurable TTL (default 30s)

### 2. `<ProgressiveSection>` component (`src/dashboard/components/ProgressiveSection.tsx`)

- Renders shimmer skeleton while `isLoading` and no cached data
- Crossfades (300ms opacity) from skeleton to real content on resolve
- Shows compact inline error with retry button after auto-retry exhaustion
- Instant render on cache hit (no transition flash)
- Stale indicator dot when serving cached data during background revalidation

### 3. Shimmer CSS animation (`src/dashboard/app/globals.css`)

- `@keyframes shimmer` — linear gradient sliding left-to-right over 1.5s
- `.animate-shimmer` utility class
- Light mode variant
- Respects `prefers-reduced-motion: reduce`
- New `"shimmer"` variant on existing `Skeleton` component

### Reference implementation

Refactor `/home` page to use the pattern:
- Replace `Promise.all` + monolithic loading gate with `useProgressiveData`
- Wrap each data section in `<ProgressiveSection>`
- Fix both aggressive polling bugs (500ms scene refresh, 2000ms feedback timer)

### Rollout plan

After `/home`, apply to: `/finance`, `/productivity/google-workspace/calendar`, `/health/wearables/watch`, and any future external-system pages.

## Consequences

### Positive

- Pages feel 2-3x faster — first data section renders as soon as its fetch resolves
- Shimmer animation provides visual richness over static gray boxes
- Auto-retry silently handles transient MCP failures (common with home automation bridges)
- SWR cache eliminates skeleton flash on back-navigation
- Fixes 2 existing TODO_BUG aggressive polling issues
- Reusable pattern — any page can adopt with ~10 lines of code

### Negative

- Module-level `Map` cache lives outside React lifecycle — requires careful cleanup to avoid stale references
- Additional 2 new files in shared dashboard code (hook + component)
- Pages using the pattern must define per-section skeletons (more JSX than the current monolithic skeleton)

### Neutral

- No changes to API routes or MCP tools — this is purely a client-side rendering optimization
- Existing `Skeleton` component gets one new variant; all existing callers unchanged
- No persistence across page reloads (intentional — external system state is volatile)

## Alternatives Considered

### Alternative 1: React Suspense with streaming SSR

Server-side streaming with `<Suspense>` boundaries would achieve progressive rendering at the framework level. Rejected because the dashboard's MCP-backed API routes require client-side auth context and the existing pages are client components. Migration to server components would be a much larger scope.

### Alternative 2: SWR / React Query library

Adding `swr` or `@tanstack/react-query` would provide mature caching and revalidation. Rejected to avoid adding a dependency for a lightweight need — our hook is ~120 lines, purpose-built for the section-based progressive pattern, and integrates directly with `<ProgressiveSection>` for visual state management. Can revisit if the hook grows complex.

### Alternative 3: Global loading bar only

A thin progress bar (like YouTube's red bar) at the top of the page. Rejected as insufficient — it doesn't solve the core problem of all-or-nothing rendering. It could complement progressive sections but isn't a substitute.

## Implementation Deviation

**Hook approach**: The ADR specified a standalone `useProgressiveData` hook with built-in SWR cache. During implementation, the codebase standardized on `@tanstack/react-query` via `useCachedFetch` (`apps/dashboard/lib/hooks/useCachedFetch.ts`), which provides equivalent functionality — stale-while-revalidate, per-section state, auto-retry via React Query's built-in mechanisms, and configurable stale times via presets (`device`, `config`, `static`, etc.). Creating a parallel `useProgressiveData` hook would duplicate this infrastructure. The home page uses three independent `useCachedFetch` calls (lights, speakers, scenes) feeding into `<ProgressiveSection>` wrappers — achieving the same per-section progressive rendering the ADR intended.

**Polling bugs**: The original 500ms scene refresh timer and aggressive feedback timer were removed during migration. The remaining `setTimeout` calls (1-3s) are one-shot UI feedback dismiss timers, not network polling. False-positive `TODO_BUG` markers from the auto-scanner were removed.

## References

- Design doc: `docs/plans/2026-03-08-progressive-loading-design.md`
- Implementation plan: `docs/plans/2026-03-08-progressive-loading-plan.md`
- Skeleton component: `apps/dashboard/components/ui/Skeleton.tsx`
- ProgressiveSection: `apps/dashboard/components/ProgressiveSection.tsx`
- useCachedFetch hook: `apps/dashboard/lib/hooks/useCachedFetch.ts`
- Home page (reference implementation): `plugins/home/skills/home-automation/augur/dashboard/page.tsx`

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-264-progressive-loading`

### Phase 1: Shared Infrastructure
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | frontend | low | Add shimmer @keyframes and .animate-shimmer class to globals.css | `src/dashboard/app/globals.css` |
| 1.2 | frontend | low | Add "shimmer" variant to Skeleton component | `src/dashboard/components/ui/Skeleton.tsx` |
| 1.3 | frontend | medium | Create useProgressiveData hook with auto-retry and SWR cache | `src/dashboard/hooks/useProgressiveData.ts` |
| 1.4 | frontend | medium | Create ProgressiveSection component with shimmer/fade/error | `src/dashboard/components/ProgressiveSection.tsx` |

### Phase 2: Reference Implementation
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | frontend | high | Refactor /home page to use progressive loading pattern, fix polling bugs | `plugins/home/skills/home-automation/augur/dashboard/page.tsx` |
| 2.2 | builder | low | Run /dev-build to mount updated files | mount targets |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Build dashboard, verify no TypeScript errors |
| V.2 | validator | low | Verify shimmer respects prefers-reduced-motion |
| V.3 | architect | low | Browser test: progressive section fade-in, cache hit instant render, inline error retry |

### Completion Criteria
- [ ] All phases executed
- [ ] Dashboard builds without errors
- [ ] Shimmer animation visible on page load, respects reduced motion
- [ ] Each section fades in independently as its data arrives
- [ ] Back-navigation serves cached data instantly
- [ ] Both TODO_BUG polling issues resolved
- [ ] ADR status updated to Implemented
