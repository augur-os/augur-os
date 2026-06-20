---
status: Implemented
date: '2026-03-10'
deciders:
- '@gsannikov'
related: []
hub: null
tags:
- usecachedfetch
- migration
- hardening
superseded_by: null
---

# ADR-269: useCachedFetch Migration Hardening

## Context

The useCachedFetch migration (ADR-267, commits 7631cd2ce + 31fc0cb37 + cec76d073) replaced ~180 raw `useEffect+fetch` patterns with the React Query hook family and fixed 15 API 404s. Three hardening tasks remain:

1. **Intentional skip markers** — A handful of files were deliberately not migrated (SSE streams, complex chat components). These lack comments explaining why, which means future maintainers or auto-loops will repeatedly flag them as missed migrations.

2. **Anti-pattern auto-loop guard** — The adaptive engine's code-health and refactor loops could re-flag these intentional skips as violations. The loops need a way to recognize approved exceptions so they don't generate noise or attempt unwanted migrations.

3. **404 route scanning** — The manual 187-endpoint scan that found 15 broken routes should be an auto-loop so new 404s are caught as routes are added or renamed.

## Decision

### 1. Add `INTENTIONAL_SKIP(adr-269)` markers to unmigrated files

For each file intentionally kept on raw fetch/SSE, add a comment at the fetch site:

```typescript
// INTENTIONAL_SKIP(adr-269): SSE stream — not a REST GET, React Query doesn't apply
```

**Files to annotate** (chat/streaming components):
- `plugins/ai/skills/ai_bridge/augur/dashboard/components/AgentBubble.tsx`
- `plugins/ai/skills/ai_bridge/augur/dashboard/components/ChatBubbleView.tsx`
- `plugins/ai/skills/ai_bridge/augur/dashboard/components/ChatViewPanels.tsx`
- Any other file using `EventSource`, `ReadableStream`, or SSE patterns for data

### 2. Teach adaptive loops to respect `INTENTIONAL_SKIP` markers

Update `auto-code-health` and `auto-refactor` loop logic:
- Before flagging a raw `useEffect+fetch` pattern as a violation, check for an `INTENTIONAL_SKIP` marker on or near the flagged line.
- If found, skip the finding silently (do not report it, do not attempt a fix).
- If a user explicitly requests migration of a marked file, the marker is removed as part of the migration.

This is NOT a blanket suppression — it requires an ADR reference (`adr-NNN`) so the reason is traceable.

### 3. Add `auto-stale-routes` loop for 404 scanning

Create a new auto-loop that:
1. Extracts all URL strings passed to `useCachedFetch`, `useCachedPoll`, `useCachedMutation`, `useAction`, `useCachedSearch` via grep.
2. Resolves each URL to a `src/dashboard/app/api/` route file (static path mapping, no HTTP needed).
3. Reports any URL with no matching `route.ts` as a finding.
4. Runs nightly alongside existing auto-loops.

**Location**: `plugins/dev/skills/devops/augur/data/loops/auto-stale-routes.yaml` + scanner script.

## Consequences

### Positive

- No more false-positive migration flags from auto-loops on intentionally skipped files
- New 404s caught automatically before users hit them at runtime
- Clear audit trail (ADR reference in every skip marker)

### Negative

- Small maintenance overhead for the new auto-loop scanner script

### Neutral

- `INTENTIONAL_SKIP` convention can be reused by future ADRs for other pattern migrations

## Implementation Prompt

**Team name**: `adr-269-usecachedfetch-hardening`

### Phase 1: Skip Markers
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Add `INTENTIONAL_SKIP(adr-269)` comments to SSE/streaming files that were not migrated | `plugins/ai/skills/ai_bridge/augur/dashboard/components/AgentBubble.tsx`, `ChatBubbleView.tsx`, `ChatViewPanels.tsx` |
| 1.2 | developer | low | Grep for any other raw `useEffect` + `fetch(` patterns in `plugins/` and `src/dashboard/` that lack `useCachedFetch` — add skip markers if intentional, migrate if missed | All plugin dashboard files |

### Phase 2: Loop Guards
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Update auto-code-health loop to skip findings near `INTENTIONAL_SKIP` markers | Loop config + scanner script |
| 2.2 | developer | medium | Update auto-refactor loop with same guard | Loop config + scanner script |

### Phase 3: Route Scanner Loop
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Create `auto-stale-routes` loop definition YAML | `plugins/dev/skills/devops/augur/data/loops/auto-stale-routes.yaml` |
| 3.2 | developer | medium | Write scanner script that greps hook URLs and checks for matching route.ts files | `plugins/dev/skills/devops/scripts/scan_stale_routes.py` |
| 3.3 | tester | low | Run scanner against current codebase — expect 0 findings (all 404s already fixed) | — |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Verify skip markers exist on all intentionally unmigrated files |
| V.2 | validator | low | Verify auto-loops respect markers (dry-run with a test file) |
| V.3 | validator | low | Verify route scanner reports 0 findings on current codebase |

### Completion Criteria
- [ ] All SSE/streaming files have `INTENTIONAL_SKIP(adr-269)` markers
- [ ] Auto-loops skip marked files without reporting
- [ ] `auto-stale-routes` loop runs and finds 0 broken routes
- [ ] ADR status updated to Implemented
