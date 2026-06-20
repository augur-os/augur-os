---
status: Implemented
date: 2026-05-21
deciders:
  - gsannikov
related: [ADR-754, ADR-768, ADR-769, ADR-770, ADR-771]
hub: brain
tags: [brain, dashboard, federation, memory, onboarding]
superseded_by: null
spec_file: 2026-05-21-brain-ui-federation-memory-review-design.md
plan_file: 2026-05-21-brain-ui-federation-memory-review.md
---

# ADR-772: Brain UI Federation And Memory Review

> **ADR-772 is an index file.** The substantive design and implementation steps
> live in the linked spec + plan. This file carries pointers, status, and a
> one-line decision summary.

## Decision summary

Expose registered/discovered brains, projection status, federated brain badges,
and reviewed memory promotion in the dashboard.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-21-brain-ui-federation-memory-review-design.md`](../superpowers/specs/2026-05-21-brain-ui-federation-memory-review-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-21-brain-ui-federation-memory-review.md`](../superpowers/plans/2026-05-21-brain-ui-federation-memory-review.md)

## Status notes

Accepted 2026-05-21. This phase should run after ADR-771 so UI behavior reflects
the final projection and write-routing model.

**Partial implementation 2026-05-21 (Tasks 1–4 of the plan).** Built on the
ADR-769 foundation ahead of ADR-770/771, scoped to read-side discovery and
federation:

- **Task 1 — Brain discovery API:** `src/lib/brain_path.py` (path→brain_id
  resolver), `src/lib/brain_discovery.py` (snapshot engine), and core MCP tools
  `brain-discovery` + `brain-init` (`src/mcp/augur_core/tools/core/brain_discovery.py`).
- **Task 2 — Settings/onboarding UI:** `/brain/settings` page
  (`apps/dashboard/features/pages/brain/settings/page.tsx`, declared in
  `knowledge/SKILL.md`) — registered/detected brains, per-brain index + git
  state, per-client projection status, and an `augur init` action.
- **Task 3 — Federated `brain_id`:** attached to unified-search, wiki-list,
  hub/skill vault-note, and Browse-index records.
- **Task 4 — Filters + focus:** Browse brain badge + detail row (rule 32), brain
  bucket filter (All/Personal/Current project/Team), and focus mode.

Verified in a real browser on `localhost:3004` against the real personal brain
(358 records; 4 client projections) — see commit trailers.

**Implemented 2026-05-21 (Tasks 5–6).** With ADR-771 write routing landed, the
memory review product shipped and ADR-772 is now **Implemented**:

- **Task 5 — Memory review product:** core engine `src/lib/memory_review.py`
  (candidate model + fingerprint, runtime staging/rejection store under
  `<runtime>/memory_review/<brain_id>/`, queue classification, and
  approve/reject/submit). Approved entries are written through the ADR-771
  destination selector (`resolve_write_target().memory_dir/entries`), so they
  land in the active brain's canonical memory dir today
  (`<personal-root>/memory/entries`) and follow ADR-770 forward to
  `<root>/knowledge/memory/entries` with no path hardcoding. MCP tools
  `memory-review-queue/approve/reject/submit`
  (`src/mcp/augur_core/tools/core/memory_review.py`) inject the client-native
  candidates (mirroring `brain-discovery`'s projection injection).
- **Review gate is canonical:** per the spec's deprecation of "memory as an
  unreviewed raw client import", `sync_agents` (`_feed_memory_review_queue`) and
  `memory_sync.py` no longer auto-promote raw client memory; they feed the review
  queue. Approve/reject is the only path into canonical brain memory. The
  per-adapter `sync_memory()` projections (ADR-771) still push *approved*
  canonical memory back to clients, so cross-client compounding is preserved.
  `memory_assembler.assemble()` is retained as an explicit library/migration
  utility but is no longer on the sync path.
- **Task 5 UI:** `/brain/memory-review`
  (`apps/dashboard/features/pages/brain/memory-review/page.tsx`, declared in
  `knowledge/SKILL.md`) — the interactive review console (rule-32 sanctioned
  manager surface): pending candidate cards with Approve/Reject, pending/
  promoted/rejected counts, and the canonical entries path.
- **Task 6 — Verification:** real-data + browser. The queue resolved the real
  personal brain (34 client-native summaries, all detected as already-promoted)
  on `localhost:3003`; a submitted candidate showed **pending → Approve →
  canonical entry written** to `~/Projects/Au-vault/memory/
  entries/`, confirmed in a real browser with zero console errors. (Demo entries
  were removed afterward; promotion is the user's call via the gate.)

## Related

- ADR-771: Client projections and write routing.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "dashboard/MCP brain discovery and projection-status APIs"
    - "record models include brain_id where federated"
  patterns_deprecated:
    - "memory as an unreviewed raw client import"
    - "unbadged cross-brain record lists"
  files_affected:
    - "apps/dashboard brain/settings/discovery surfaces"
    - "Browse and search record transforms"
    - "knowledge memory review tools"
    - "tests/dashboard and MCP brain discovery tests"
```

## Implementation Prompt

To execute this ADR, run:

```text
/adr implement ADR-772
```
