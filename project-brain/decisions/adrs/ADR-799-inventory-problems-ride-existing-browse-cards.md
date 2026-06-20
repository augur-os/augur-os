---
status: Implemented
date: 2026-06-05
deciders:
  - gsannikov
related:
  - ADR-490
  - ADR-797
  - ADR-798
hub: brain
tags:
  - browse
  - inventory
  - problem-tags
  - first-hour
  - chat-handoff
superseded_by: null
spec_file: 2026-06-04-first-hour-user-value-design.md
plan_file: 2026-06-04-first-hour-inventory-problems.md
---

# ADR-799: Inventory Problems Ride Existing Browse Cards

## Decision summary

AI artifact inventory problems are read-only metadata on existing Browse cards: problem badges, filters, detail-panel evidence, and chat action drafts all render from `BrowseItem.metadata` rather than from a new problem page, category, or dashboard-owned execution flow.

## Spec and plan

- [`docs/superpowers/specs/2026-06-04-first-hour-user-value-design.md`](../superpowers/specs/2026-06-04-first-hour-user-value-design.md)
- [`docs/superpowers/plans/2026-06-04-first-hour-inventory-problems.md`](../superpowers/plans/2026-06-04-first-hour-inventory-problems.md)

## Context

Inventory-only init is safe, but raw inventory records are not enough first-hour value. The user needs to see what looks wrong, filter to problems, inspect evidence, and ask chat for safe next steps without Augur mutating files by default.

Browse is already the discovery surface. Adding a separate "problems" page would split the user's attention and weaken the launch path. The dashboard should surface the signal where the artifact already appears.

## Decision

1. Problem signals are derived by the Python AI artifact inventory layer and attached as string metadata:
   - `problem_tags`
   - `problem_count`
   - `problem_summary`
   - `problem_evidence`
2. The problem taxonomy starts with conservative scanner and setup ids:
   - `permission_denied`
   - `unreadable`
   - `unknown_source`
   - `low_confidence`
   - `duplicate`
   - `stale_generated`
   - `conflicting_instruction`
   - `missing_mcp_config`
3. Browse cards render problem badges from metadata.
4. The existing Browse filters surface adds problem filters from card metadata.
5. The existing detail panel renders problem evidence from metadata.
6. The existing chat/action handoff creates a draft with artifact path, brain/project context, problem tags, evidence, and an explicit no-mutation approval gate.
7. Unknown future problem ids remain filterable and render as humanized labels.

## Non-Goals

- No separate problem dashboard for launch.
- No new `AI Artifacts` or `Problems` Browse category.
- No dashboard-side local script execution.
- No hidden dashboard LLM/API call.
- No automatic adoption, sync, rewrite, merge, delete, or projection.
- No content indexing by default for question answering.

## Implementation status

Implemented on `main`:

- `src/lib/ai_artifact_inventory.py` derives deterministic problem metadata.
- `src/mcp/augur_framework/tools/infrastructure/browse/index.py` preserves and merges fresh inventory problem metadata.
- `apps/dashboard/lib/browse/problems.ts` parses metadata, badges, evidence rows, filter options, and chat prompts.
- `apps/dashboard/lib/browse/cardModel.ts` adds card badges.
- `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx` filters by problem.
- `apps/dashboard/components/shared/BrowseDetailPanel.tsx` renders evidence and action handoff.

Relevant implementation commits include `6618180e3 feat(browse): filter inventory cards by problem`, `59b1584fd fix(browse): pass end-to-end build checks`, and `d0ca6194c fix(browse): make folder health badges legible and actionable`.

## Consequences

Positive:

- The first Browse screen can show value without asking the user to run cleanup.
- Problem evidence travels with the artifact, so cards, filters, details, and chat drafts stay aligned.
- Future problem ids can be added by backend metadata without redesigning Browse.

Tradeoffs:

- Metadata strings must stay compact and stable.
- Problem derivation must be conservative to avoid noisy first-hour warnings.
- Chat drafts can prepare next steps, but actual mutation remains a separate approved workflow.

## Verification

Required proof:

- Real AI artifact inventory records produce problem metadata when warnings, low confidence, duplicates, or missing MCP config are present.
- Browse cards show problem badges without replacing normal artifact metadata.
- Filters can narrow to one problem id.
- Detail panel evidence is readable.
- Chat draft includes artifact path, active folder context, problem evidence, and the no-mutation approval gate.

Current code evidence:

- `tests/unit/test_ai_artifact_inventory.py`
- `tests/mcp/test_browse_ai_artifact_inventory.py`
- `tests/dashboard/browse/problems.test.ts`
- `tests/dashboard/unit/browse-card-model.test.ts`
- `tests/dashboard/browse/BrowseToolbar.test.tsx`
- `tests/dashboard/browse/BrowseDetailPanel.test.tsx`
- `tests/dashboard/browse/itemActions.test.ts`

## Status notes

Implemented on 2026-06-05 as the read-only first-hour problem surface for inventory-backed Browse records.

## Related

- ADR-797: Fast launch is inventory-only folder init.
- ADR-798: Browse folder context is the primary multi-project switcher.
- ADR-490: Dashboard import architecture.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "inventory-backed BrowseItem metadata may include problem_tags/problem_count/problem_summary/problem_evidence"
  patterns_deprecated:
    - "separate dashboard-only problem stores for inventory artifacts"
    - "problem findings that bypass Browse cards"
  files_affected:
    - "src/lib/ai_artifact_inventory.py"
    - "src/mcp/augur_framework/tools/infrastructure/browse/index.py"
    - "apps/dashboard/lib/browse/problems.ts"
    - "apps/dashboard/lib/browse/cardModel.ts"
    - "apps/dashboard/app/(views)/browse/BrowseToolbar.tsx"
    - "apps/dashboard/components/shared/BrowseDetailPanel.tsx"
```
