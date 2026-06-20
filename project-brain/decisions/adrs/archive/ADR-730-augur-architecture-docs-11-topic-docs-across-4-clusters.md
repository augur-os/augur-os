---
status: Implemented
date: '2026-05-11'
deciders:
- gsannikov
related: []
hub: dev
tags:
- architecture
- documentation
- oss-release
- meta
superseded_by: null
spec_file: 2026-05-11-augur-architecture-docs-design.md
plan_file: 2026-05-11-augur-architecture-docs.md
---

# ADR-730: Augur Architecture Docs — 11 Topic Docs Across 4 Clusters

## Decision summary

Author 11 contributor-facing `docs/architecture-<topic>.md` files — matching the depth, voice, and inline-diagram format of the existing `architecture-overview.md` and `architecture-mcp-gateway.md` — grouped into 4 topical clusters (Storage & Knowledge: vault, wiki, memory; Skill Distribution:...

## Status notes

Spec + plan written 2026-05-11 in the same session via `/superpowers:brainstorming` + `/superpowers:writing-plans`. Two structural choices were made during brainstorming and are load-bearing for the rest of the work: - **Slicing — clustered (over per-doc or single-mega-spec).** Ten docs is too many for one design spec and too few for ten independent brainstorming cycles. Clustering by topical adjacency lets recurring decisions get made once. - **Relationship to `agent-topics/` — complement + drill-down link (over ignore or consolidate).** Consolidation would refactor the `sync_agents` projection pipeline that generates per-client instructions for five AI clients — too much blast radius for a documentation pass. The one-line "see also" pointer is additive and low-risk. Tasks 3, 5, 6, 8, 10 include ADR-discovery passes for topics where the spec did not pre-list governing ADRs (memory, sync-agents, capability-exposure, daemon, agents). These are not placeholders — they are instructions to discover specific ADR numbers at execution time. **Amendment 2026-05-11 — added `architecture-sdlc.md` to Cluster 4.** The user requested an additional doc covering Augur's internal SDLC (the spec → plan → ADR → index → auto-loops → testing/feedback → release pipeline) and the universal-change-record stance for ADRs (every non-trivial change goes through ADR, including features, website updates, and debugging sessions). Cluster 4 renamed from "Agent Coordination" to "Coordination & Process" to fit both `architecture-agents.md` and `architecture-sdlc.md`. Scope grew from 10 → 11 docs; impact manifest updated above. Spec §5.4 and plan Task 11 carry the new doc's section outline. Implemented 2026-05-12 in Windows session B2. The implementation added all 11 architecture docs, the four agent-topic drill-down pointers, and passed structural, ADR-reference, relative-link, Mermaid render, and command-example verification.
