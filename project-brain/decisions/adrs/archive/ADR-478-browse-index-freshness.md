---
title: Browse Index Freshness Indicators
status: Implemented
date: 2026-03-22
deciders: <user>
related:
- ADR-102
- ADR-404
hub: command
---

# ADR-478: Browse Index Freshness Indicators

## Context

The `/browse` page displays data from RAG indexes (`~/Library/Application Support/Augur/rag/{category}/`). Each index entry contains an `indexed_at` timestamp, but this information is never surfaced to users. When indexes go stale (e.g., skills index last rebuilt 5 days ago), the page shows "0 skills" with no explanation — users cannot tell whether data is current, aging, or missing.

**Problems:**
1. No freshness indicator — users don't know when data was last indexed
2. Stale indexes silently show empty/outdated results
3. No quick way to trigger a reindex from the browse page
4. Category tabs give no visual hint about which categories have fresh vs stale data

## Decision

### 1. Backend: Return `last_indexed` in browse API response

Modify `browse_index_impl()` in `src/mcp/augur_mcp/infrastructure/browse/index.py` to aggregate the `indexed_at` field from RAG entries and return it as a top-level `last_indexed` ISO timestamp in the JSON response. Use the most recent `indexed_at` across all entries in the category. For live-scan categories (integrations, agents, prompts, scripts, etc.) that don't use RAG indexes, return the current timestamp.

**Response shape change:**
```json
{
  "items": [...],
  "count": 42,
  "last_indexed": "2026-03-17T00:34:50.866359+00:00"
}
```

### 2. UI: Freshness banner below category bar

Add a compact freshness indicator strip between the category bar and the hub filter pills in `page.tsx`. Shows:
- "Indexed {relative time}" (e.g., "Indexed 5 days ago") with absolute date/time on hover
- Color-coded: green (< 1 day), amber (1-7 days), red (> 7 days)
- A "Reindex" button that dispatches `/search reindex {category}` via `useActionRunner`

### 3. UI: Category health dot on tabs

Add a small colored dot (4px) next to each category label in the OverflowBar. The dot color reflects the freshness of that category's index. This requires fetching freshness metadata for all categories, which is done via a lightweight endpoint or cached client-side after the first category load.

**Approach:** Store `last_indexed` per category in `useBrowseState` as fetched. For un-fetched categories, show no dot. Once a category is visited, its freshness is cached and the dot appears.

## Consequences

**Positive:**
- Users can immediately see whether browse data is current
- One-click reindex from the browse page
- Visual scanning of category health via dot badges

**Negative:**
- Slight increase in API response payload (one timestamp field)
- Category dots only populate after visiting each category (acceptable trade-off vs fetching all categories upfront)

**Neutral:**
- No changes to RAG index format — reads existing `indexed_at` field

## Implementation Order

### Phase 1: Backend (browse_index_impl)
1. In `browse_index_impl()`, compute `max(indexed_at)` across entries
2. Return `last_indexed` in JSON response
3. For live-scan tools (`list_integrations_impl`, `list_agents_impl`, etc.), return current ISO timestamp

### Phase 2: Frontend — Freshness banner
1. Parse `last_indexed` from API response in `useBrowseState`
2. Add freshness banner component between category bar and hub pills
3. Wire "Reindex" button to `useActionRunner` dispatching `/search reindex {category}`

### Phase 3: Frontend — Category health dots
1. Track `lastIndexed` per category in state
2. Render dot in OverflowBar category tabs
3. Use `getStalenessLevel()` from `lib/timestamps.ts` for color

## Alternatives Considered

1. **Auto-reindex on page load** — Rejected: too expensive, RAG reindex can take 30+ seconds
2. **Full diagnostic panel per category** — Deferred: useful but scope creep for initial implementation
3. **Server-side freshness endpoint for all categories** — Rejected: adds complexity; client-side caching after first visit is simpler

## References

- `src/mcp/augur_mcp/infrastructure/browse/index.py` — browse_index_impl
- `apps/dashboard/app/(views)/browse/page.tsx` — browse page
- `apps/dashboard/lib/timestamps.ts` — getStalenessLevel utility
- `.claude/skills/rag/scripts/index_reader.py` — RAG index reader
