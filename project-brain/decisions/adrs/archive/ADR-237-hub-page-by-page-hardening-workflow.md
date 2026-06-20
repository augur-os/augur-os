---
status: Implemented
date: '2026-03-05'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- hub
- page
- page
- hardening
- workflow
superseded_by: null
---

# ADR-237: Hub Page-by-Page Hardening Workflow

## Context

Hub hardening is currently inconsistent. Pages are reviewed in different orders, duplicate detection is incomplete, and refactor planning is often done at hub level without page-specific evidence.

This creates three recurring problems:

- Valuable pages are changed or removed without enough usage context.
- Duplicate pages remain because comparisons are not done systematically.
- Refactor plans are broad and hard to execute because they are not tied to each page decision.

The first live run on the AI hub also showed a second problem: aggressive cross-hub page moves quickly become skill ownership changes (not just UI cleanup). That creates high migration risk and can violate plugin self-containment if done without dedicated skill-level ADRs.

## Decision

Adopt a strict page-by-page hardening workflow for a selected hub.

Adopt an execution policy for implementation:

## Internal-Merge-First Policy

1. Fix critical wiring issues first (broken APIs, broken actions, empty/stub-only pages).
2. Prefer merges and simplification inside the same skill/hub before any skill move.
3. For cross-hub duplication, prefer composition/reuse first (shared components/API contracts) while keeping current skill ownership.
4. Skill moves are out of scope for this hardening pass; keep ownership in AI and refocus internally.
5. No redirect-based cleanup for page deduplication in this workflow pass; resolve by canonical implementation and route cleanup.

### Workflow

1. User provides one hub link.
2. System scans the hub and discovers all routable pages.
3. For each page, run a guided interview before any refactor decision:
   - How the page is used in practice
   - Whether the page is valuable
   - Whether it duplicates another page
   - If duplicated, which page is the canonical/better one
4. Based on answers, generate a page-specific refactor plan with explicit actions (`keep`, `merge`, `remove`, `rename`, `move`, `simplify`) and rationale.
5. Continue to the next page until all discovered pages are processed.
6. Produce a final hub hardening plan that consolidates all page decisions in implementation order.

### Output Requirements

- Every page must end with a concrete decision and next action.
- Duplicate decisions must name both pages and the chosen canonical page.
- The final hub plan must include ordered execution steps and risk notes.
- Cross-hub moves are out of scope in pass 1; if discovered, mark them as future risks without executing ownership changes.

## Critical Issues Gate (Must Pass First)

Before any page removal or merge is finalized, these checks must pass:

1. Action/API wiring correctness (no dead buttons, no stale endpoint paths).
2. Namespace consistency for routes and APIs (no mixed legacy/current prefixes in live UI paths).
3. Duplicate-route handling must be implementation-level (not redirect-only).
4. Stub pages must either gain live data wiring or be merged into a working canonical page.

## AI Hub Application (Pass 1)

To reduce architecture churn, the AI hub hardening pass uses internal merges first:

1. Keep skill ownership unchanged in pass 1 (`ai_bridge`, `knowledge`, `rag`, `scraper` stay in `plugins/ai/skills/`).
2. Merge duplicate integrations surfaces by making one canonical UI and reusing it, without moving the owning skill yet.
3. Merge Knowledge + RAG page surfaces internally, while keeping `rag` as a backend/control-plane skill in this pass.
4. Keep Knowledge Memory inside AI and refocus it on:
   - AI clients memory state (agent/client-specific memory visibility)
   - Augur memory files and related memory artifacts
5. Keep scraper in AI for pass 1; improve wiring and merge internal scraper pages before any observability skill move.
6. Keep services/workflows in AI hub for pass 1 and refocus them to the canonical internal workflows/service management experience.

## Consequences

### Positive

- Hardening becomes deterministic and auditable.
- Duplicate detection improves because every page is explicitly compared.
- Refactor plans become execution-ready because each action is tied to one page.
- Lower migration risk by minimizing immediate skill moves.
- Preserves plugin self-containment while still reducing UI duplication.

### Negative

- The process takes longer upfront than ad hoc hardening.
- Requires user participation for page-level context questions.
- Some architecture debt may remain because this pass intentionally avoids ownership moves.

### Neutral

- Does not force skill moves in the first hardening pass.
- Can be run incrementally on one hub at a time.

## Alternatives Considered

### Alternative 1: Hub-level review only (no page interview loop)

Rejected because it misses usage context and leads to low-confidence removals and merges.

### Alternative 2: Fully automated hardening without user Q&A

Rejected because page value and practical usage are domain-specific and cannot be inferred reliably from file structure alone.

### Alternative 3: Immediate cross-hub page/skill moves during first pass

Rejected because it mixes UI cleanup with architectural migration, increasing breakage risk and violating self-contained ownership unless each move is separately analyzed.

## References

- ADR-163: Plugin Decentralization
- ADR-235: Plugin Architecture Integrity
- docs/references/agents-page-design-pattern.md
- [Implementation Plan](../plans/2026-03-05-ai-hub-page-by-page-hardening-plan.md)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `/write-adr`. Edit if needed before running.

**Team name**: `adr-237-hub-hardening-loop`

### Phase 1: Hub Discovery + Critical Gate
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Accept one hub link and resolve hub root | `src/dashboard/app/{hub}/**` |
| 1.2 | developer | medium | Enumerate all routable pages for that hub | `src/dashboard/app/{hub}/**/page.tsx` |
| 1.3 | validator | medium | Validate action/API wiring and namespace consistency before refactors | `src/dashboard/app/**`, `src/dashboard/app/api/**` |

### Phase 2: Page Interview Loop
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | For each page, ask usage/value/duplicate/canonical questions | Session output only |
| 2.2 | architect | medium | Convert answers into a page-specific decision with skill-impact tag (`none/split/move`) | Session output only |
| 2.3 | developer | low | Append page decision to hub hardening ledger | `docs/plans/*hub-hardening*.md` |

### Phase 3: Internal Merges (Pass 1)
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | high | Execute internal merges and simplification inside existing skills first | `plugins/{bundle}/skills/{skill}/**` |
| 3.2 | validator | medium | Verify no redirect-only dedupe and no broken actions/endpoints | `src/dashboard/app/**`, `src/dashboard/app/api/**` |

### Phase 4: Consolidated Plan + Internal Refocus
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | architect | medium | Merge decisions into ordered implementation plan focused on internal merges/refocus | `docs/plans/*hub-hardening*.md` |
| 4.2 | architect | low | Add explicit internal refocus tasks for AI services/workflows and memory surfaces | `docs/plans/*hub-hardening*.md` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Confirm no discovered page is missing from the final plan |
| V.2 | architect | low | Confirm duplicate merge/remove decisions identify canonical targets |
| V.3 | validator | low | Confirm skill ownership stayed self-contained for pass 1 |

### Completion Criteria
- [ ] Hub link accepted and resolved
- [ ] All hub pages discovered
- [ ] Guided interview completed for each page
- [ ] Per-page refactor decision recorded
- [ ] Critical issues gate passed
- [ ] Internal merges completed without mandatory skill moves
- [ ] AI services/workflows and memory surfaces refocused internally
- [ ] Final ordered hub refactor plan produced
