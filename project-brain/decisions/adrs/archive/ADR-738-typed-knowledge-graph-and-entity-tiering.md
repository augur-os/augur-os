---
status: Implemented
date: 2026-05-13
deciders:
  - gsannikov
related:
  - ADR-571
  - ADR-731
  - ADR-739
  - ADR-740
  - ADR-742
hub: brain
tags:
  - knowledge
  - graph
  - wiki
  - ingest
  - retrieval
superseded_by: null
spec_file: 2026-05-14-typed-knowledge-graph-design.md
plan_file: 2026-05-14-typed-knowledge-graph.md
---

# ADR-738: Typed Knowledge Graph Layer and Entity Tiering for the Wiki

## Status

Implemented.

## Context

The wiki and memory subsystems extract relationships dynamically from `[[wikilinks]]` via `extract_relationships()` and `RelationshipIndex` (per current SKILLS.md guidance). These relationships are **untyped** — a link from page A to page B says nothing about *why* they are related.

A reference second-brain system (gbrain, MIT) running in a Y Combinator production deployment with ~17K pages, ~4K people, ~700 companies demonstrated that **typed, deterministic edges** (`attended`, `works_at`, `invested_in`, `founded`, `advises`) extracted at write time, with **zero LLM calls**, enable precision queries that vector search alone cannot answer (e.g. "who works at Acme?", "who founded a Series-A company in 2024?").

This aligns with Augur's stated principle that "reasoning is scarce, execution is cheap" and with Rule #19 (MCP tools own atomic ops; deterministic work belongs out of the LLM path).

## Decision

Introduce a typed-edge layer that runs deterministically on every wiki/note write. Typed edges and tier metadata live in **vault frontmatter** (human-readable, transparent, file-first). A derived, rebuildable graph index cache lives under `get_cache_dir()/graph/` as JSONL. **No embedded database is introduced.**

Concretely:

1. Edge types are declared in `config/system/graph_edges.yaml` and are extensible by user/skill.
2. Extraction logic lives in a new `shared-vault/skills/graph/` skill (hub: `brain`) or, if simpler, as a subsystem under `shared-vault/skills/ingest/`.
3. On every wiki/note write, the extractor runs over the file body and writes typed edges to entity frontmatter under `_edges:` per ADR-571 (leading `_` keys are system-managed).
4. Entity tier (1–3) is computed deterministically from edge count and source-type diversity and stored in `_tier:` frontmatter. Tier thresholds initially:
   - Tier 1: ≥10 inbound mentions across ≥3 source types
   - Tier 2: ≥3 inbound mentions
   - Tier 3: everything else
5. New MCP tools: `graph-extract`, `graph-query`, `graph-stats`, `entity-tier-recompute`. All default to CLI per surface-decision-matrix; opt-in to MCP exposure only when dashboard or agent flows justify it.
6. The cache JSONL is rebuildable from frontmatter at any time; deletion is non-destructive.

## Non-Goals

- No LLM-based extraction. The whole point is determinism and zero token cost. LLM-aided relationship discovery, if ever wanted, is a separate ADR.
- No graph database. No Neo4j, no SQLite graph extensions, no embedded store.
- No replacement of untyped `[[wikilinks]]` discovery. Typed edges **augment** the existing relationship index; both coexist.
- No cross-vault federation. Local vault only.

## Consequences

- New skill (or subsystem) with extractor, MCP tools, and tests.
- Wiki pages and entity notes gain `_edges:` and `_tier:` frontmatter, written via `merge_system_user()` (ADR-571).
- `unified-search` (ADR-739) can boost Tier-1 entities; `wiki-update` and dream cycle (ADR-744) can prioritize Tier-1 refresh.
- Retrieval eval harness (ADR-742) gains a graph-query benchmark axis.
- Compiled-truth + timeline pattern (ADR-740) can cite typed edges as evidence.

## Related

- ADR-571 (vault frontmatter system-managed keys)
- ADR-731 (memory synthesis / wiki compounding)
- ADR-739 (hybrid search consumes the graph)
- ADR-740 (timeline cites typed edges)
- ADR-742 (eval harness validates graph queries)
