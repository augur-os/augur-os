---
status: Implemented
date: 2026-05-11
deciders:
  - gsannikov
related:
  - ADR-642
  - ADR-722
  - ADR-727
  - ADR-728
  - ADR-729
hub: brain
tags:
  - memory
  - wiki
  - compounding
  - consolidation
  - context-injection
  - dashboard
  - browse
  - mcp
  - llm-synthesis
superseded_by: null
spec_file: 2026-05-11-memory-synthesis-consolidation-design.md
plan_file: 2026-05-11-memory-synthesis-consolidation.md
---

# ADR-731: Memory Synthesis Consolidation — Wiki Compounding as the Single Engine + User-Configurable Query Registry

> **ADR-731 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Make the wiki compounding engine the single auto-synthesis engine in Augur. Introduce a user-configurable wiki query registry at `vault/wiki/queries.yaml` seeded with 4 defaults (`profile-human-api`, `active-projects`, `recent-decisions`, `knowledge-gaps`). Retire the deterministic regex `profile_generator.py` pipeline; the `profile-human-api` query replaces it via LLM synthesis with structured H2 sections that match `context_injector`'s existing field set (Role, Expertise, Communication Style, Success Criteria, Context Gaps, Evidence, Source Basis). Move the profile from `runtime/memory/HUMAN_API.md` to `vault/wiki/profile-human-api.md`. Add `/brain/wiki` dashboard page (query CRUD + manual refresh) and a `memory` Browse category at journey_order=5 in journey_group=knowledge. Big-bang cutover in one PR with an in-PR A/B test asserting field-set equivalence before `context_injector` swaps to the new parser. No sub-tabs anywhere — verified by scanning all 12 Accepted ADRs and their linked specs/plans.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-11-memory-synthesis-consolidation-design.md`](../superpowers/specs/2026-05-11-memory-synthesis-consolidation-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-11-memory-synthesis-consolidation.md`](../superpowers/plans/2026-05-11-memory-synthesis-consolidation.md) — 31 tasks across 9 checkpoints (C1 registry foundation, C2 query runner, C3 5 MCP tools, C4 seed defaults + A/B equivalence test, C5 consumer migration, C6 dashboard, C7 Browse category, C8 retirement, C9 final integration). TDD discipline; the A/B test in Task 14 is the only hot-path safety gate before `context_injector` swaps.

## Status notes

Spec + plan written 2026-05-11 in the same session via `/superpowers:brainstorming` + `/superpowers:writing-plans`. Workflow: full audit → mapped 11 memory-adjacent surfaces (spec §4) → identified 6 overlaps → chose wiki engine as the single synthesis mechanism (Option 3 hybrid: LLM synthesis with structured H2 sections preserving the consumer interface). Browse expansion is +1 only (`memory` card); `wiki-queries` deliberately not in Browse since they're configuration not content. Migration is big-bang in one PR per spec §9.

Load-bearing claim: the A/B equivalence test in plan Task 14 must pass before plan Task 15 (the `context_injector` parser swap) executes. That ordering is the only consumer-safety gate.

Tangential session finding (already fixed, not part of this ADR's scope): the `/adr` post-write hook lacked a central-JSON upsert step, causing ADR-730 to drift out of `adrs-index.json`. Fixed via new `.github/scripts/adr_upsert_live.py` and an updated hook contract in `shared-vault/skills/augur-core/commands/adr.md`. This ADR (ADR-731) is the first to land via the corrected hook chain.

Ready to implement via `/adr implement ADR-731`.

## Related

- ADR-642 — Central ADR JSON index (the "single source of truth" precedent this ADR mirrors for `queries.yaml`)
- ADR-722 — Setup Completeness Widget (milestone 6 "Set wiki compounding queries" anticipated this work; ADR-731 ships that feature)
- ADR-727 — Background Routines (informs the manual-refresh-only decision; no daemon-scheduled regeneration in v1)
- ADR-728 — Browse Page Lifecycle Ordering (adds `memory` Browse category at journey_order=5 in journey_group=knowledge, following ADR-728's reservation pattern)
- ADR-729 — Voice Profile Personalization Journey (the user-authored half of `/brain/profile`; ADR-731 is the auto-derived half; both coexist as separate cards)

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - "runtime/memory/HUMAN_API.md -> vault/wiki/profile-human-api.md (LLM-synthesized replacement)"
  apis_changed:
    - "New MCP tools: wiki-queries-list, wiki-queries-read, wiki-queries-write, wiki-queries-run, wiki-queries-seed-defaults"
    - "memory-profile-regenerate becomes a thin wrapper that calls wiki-queries-run profile-human-api (tool name + capability-exposure entry unchanged)"
    - "knowledge-memory-profile + knowledge-memory-workspace-open: file_id='profile'/'report' resolution updates from runtime/memory/HUMAN_API.md to vault/wiki/profile-human-api.md (public contract unchanged)"
    - "context_injector parser: YAML frontmatter -> H2 sections; same field set (Role, Expertise, Communication Style, Success Criteria, Context Gaps, Evidence, Source Basis)"
  patterns_deprecated:
    - "Deterministic regex extraction in src/lib/knowledge/profile_generator.py (retired)"
    - "YAML-frontmatter profile shape in HUMAN_API.md (replaced by H2-section markdown in profile-human-api.md)"
  files_affected:
    - "shared-vault/skills/ingest/scripts/wiki_query_registry.py (NEW)"
    - "shared-vault/skills/ingest/scripts/wiki_query_runner.py (NEW)"
    - "shared-vault/skills/ingest/scripts/wiki_query_sources/ (NEW directory — 7 source adapters)"
    - "shared-vault/skills/ingest/scripts/mcp/wiki_queries_tools.py (NEW)"
    - "shared-vault/skills/ingest/assets/seeds/queries-defaults.yaml (NEW)"
    - "shared-vault/skills/ingest/scripts/mcp/wiki_tools.py (registers wiki_queries_tools)"
    - "shared-vault/skills/ingest/SKILL.md (adds /brain/wiki to x-augur-dashboard-pages)"
    - "shared-vault/skills/knowledge/scripts/mcp/tools_memory_core.py (memory-profile-regenerate becomes thin shim)"
    - "shared-vault/skills/knowledge/scripts/mcp/tools_memory_profile.py (path resolution for profile/report file_ids)"
    - "src/mcp/augur_shared/context_injector.py (parser swap to H2 sections)"
    - "src/lib/knowledge/profile_generator.py (DELETED)"
    - "src/lib/human_api_profile_parser.py (DELETED — consumers absorbed parsing into context_injector)"
    - "apps/dashboard/features/pages/brain/wiki/page.tsx (NEW)"
    - "apps/dashboard/features/pages/brain/wiki/hooks.ts (NEW)"
    - "apps/dashboard/features/pages/brain/wiki/types.ts (NEW)"
    - "apps/dashboard/features/pages/brain/wiki/components/QueryCard.tsx (NEW)"
    - "apps/dashboard/features/pages/brain/wiki/components/QueryEditor.tsx (NEW)"
    - "apps/dashboard/features/pages/brain/profile/components/HumanApiProfile.tsx (refactored data source)"
    - "apps/dashboard/features/pages/brain/profile/components/HumanApiProfileSection.tsx (refactored render shape)"
    - "apps/dashboard/features/pages/brain/profile/hooks.ts (new return shape)"
    - "apps/dashboard/features/pages/brain/profile/types.ts (new profile shape)"
    - "apps/dashboard/lib/browse/types.ts (adds `memory` Browse category at journey_order=5)"
    - "apps/dashboard/lib/browse/transforms.ts (memory category transform)"
    - "config/system/capability_exposure.yaml (5 new MCP tool entries)"
    - "tests/wiki/test_query_registry.py (NEW)"
    - "tests/wiki/test_query_runner.py (NEW)"
    - "tests/wiki/sources/ (NEW directory — adapter tests)"
    - "tests/packages/augur-mcp/test_wiki_queries_tools.py (NEW)"
    - "tests/migration/test_human_api_field_set_equivalence.py (NEW — deleted after migration lands)"
    - "tests/dashboard/features/pages/brain/wiki/ (NEW directory)"
    - "shared-vault/skills/knowledge/augur/tests/test_profile_generator.py (DELETED)"
    - "tests/test_human_api_profile_parser.py (DELETED)"
```
