---
status: Implemented
date: 2026-04-29
deciders:
  - Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
---

# ADR-599: Track 1 Knowledge Memory Extraction

## Context

Track 1 / Library 2 of the cross-client bundle architecture migration extracts the knowledge skill's memory subsystem (11 .py files at `skills/knowledge/scripts/mcp/memory/`) to `src/lib/knowledge/`. The subsystem provides `DailyLogger`, `MemoryStore`, `MemoryCurator`, `UnifiedSearcher`, `MemorySearcher`, `MemoryEntry`, `SearchMode`, profile generator helpers, and the `_index/_iterative/_ripgrep/_types` mixins.

External surface is small but cross-cutting: `src/mcp/augur_mcp/core/ask_retention.py` imports `DailyLogger`, augur-core's `test_ask_retention.py` patches the `DailyLogger` symbol via 3 string targets, and 4 internal bundle MCP-tool wrappers use relative `from .memory import ...`. Knowledge's own tests also import from the legacy module path.

Internal sibling imports inside the 11 memory files are all relative (`from .X`, `from ._X`), so they continue to work unchanged after relocation.

## Decision

Use rename-via-overlap across five sequential PRs to relocate the 11 memory files to `src/lib/knowledge/`:

- PR 1 (additive): copy 11 files verbatim, write `__init__.py` re-exporting the public API, add smoke tests at `tests/lib/knowledge/`. Both old and new paths work.
- PR 2: migrate `ask_retention.py` (line 255) and update augur-core's three `@patch` target strings from `"skills.knowledge.scripts.mcp.memory.DailyLogger"` to `"src.lib.knowledge.DailyLogger"`.
- PR 3: migrate the four bundle MCP wrappers (`tools_memory.py`, `tools_memory_core.py`, `tools_memory_dashboard.py`, `rag_search.py`) — replace `from .memory import ...` with `from src.lib.knowledge import ...`. Tighten the `SearchMode` import to its actual module (`_types`) instead of `search.py`'s re-export.
- PR 4: migrate knowledge's own tests (`test_knowledge.py` and any sibling test files plus mock patch target strings).
- PR 5: delete `skills/knowledge/scripts/mcp/memory/`.

## Consequences

### Positive
- The memory subsystem is reachable via clean Python imports from `src.lib.knowledge` for all consumers.
- The bundle's tool wrappers consume the canonical library like every other client.
- Tests exercise the canonical implementation; mock patch targets follow the canonical module path.
- Internal mixin imports remain relative and survive the move unchanged.

### Negative
- Five sequential commits with internal MCP wrapper migration in lockstep.
- The only `(*, knowledge)` allowlist entry is `("knowledge", "rag")` (knowledge consuming rag); it is unaffected by this library and retires only when Library 4 (rag) extracts.

### Neutral
- The skill bundle keeps its MCP tool surface (`tools_memory*`, `tools_rag*`, `rag_*`, etc.) and standalone scripts (`batch_index`, `manage_*`).

## Alternatives Considered

### Alternative 1: Keep memory subsystem inside the knowledge skill
Rejected. External consumers (`ask_retention.py`) belong in `src/`, and the memory subsystem is library code, not capability-bundle code.

### Alternative 2: Use absolute imports with a compatibility shim
Rejected. Compatibility shims violate Critical Rule 14 (prefer canonical cleanup). Rename-via-overlap completes the migration without redirects.

## References
- Plan: docs/superpowers/plans/2026-04-29-track1-knowledge-memory-extraction.md
- Spec (Layer 1): docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md
- Spec (Layer 4 / Track 1): docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md
