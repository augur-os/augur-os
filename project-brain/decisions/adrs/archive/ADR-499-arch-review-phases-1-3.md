---
id: ADR-499
title: Architecture Review Phases 1-3 Implementation
status: Implemented
date: 2026-03-24
deciders:
- Gur Sannikov
tags:
- architecture
- vault-elimination
- remote-execution
- plugin-tools
- rag
related:
- ADR-466
---

# ADR-499: Architecture Review Phases 1-3 Implementation

## Context

The Q1 2026 architecture review identified items beyond the 6 quick fixes in ADR-466. Phases 1-3 cover vault elimination (moving agent-rules.md from vault to repo), remote execution wiring (useActionRunner remote dispatch), plugin tool loading fixes (lazy loading with status banners), and RAG pipeline unification (consolidating duplicate indexers).

## Decision

Implement 3 independent phases plus sub-items:
- **Phase 1a**: Vault elimination — move `agent-rules.md` from vault to `docs/agent-topics/`, update sync_agents constants
- **Phase 1b**: Wire remote execution — add remote dispatch mode to `useActionRunner`, settings UI for endpoint config
- **Phase 2**: Plugin tool loading fix — lazy load in `plugin_tools.py`, add `get-plugin-load-status` MCP tool, consumer banners
- **Phase 3**: RAG pipeline unification — consolidate `rag_indexer.py` into `unified_indexer.py`, single entry point

Phases 4-5 (discovery consolidation, agent tiers) were scoped separately as larger refactors.

## Consequences

### Positive
- Agent rules version-controlled in repo, not scattered in vault
- Remote execution enables cloud-hosted agent dispatch
- Plugin tool failures surface as clear UI banners instead of silent empty states

### Negative
- Remote execution introduces network dependency and auth complexity

## References

- Plan: `docs/superpowers/plans/2026-03-20-arch-review-phases-1-3.md`
- Spec: `docs/superpowers/specs/2026-03-20-arch-review-remaining-items-design.md`
