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

# ADR-598: Track 1 Doc Extractor Extraction

## Context

The cross-client bundle architecture migration (Track 1) starts with the document-extractor skill because it has the smallest blast radius (4 importers). The skill's `scripts/` directory hosts four library files (`extractor.py`, `ollama_client.py`, `tesseract_ocr.py`, `audio_extractor.py`) that are imported via `sys.path` injection plus bareword `from extractor import ...` from at least three external skills (rag, knowledge, file-manager) and the bundle's own MCP wrapper.

The bareword imports rely on per-call-site `sys.path.insert(...)` of `skills/document-extractor/scripts/`, which makes the import surface fragile and invisible to the architecture test (its regex requires `from skills.<X>.<rest>`). One latent bug was discovered during planning: `skills/rag/scripts/ocr_extractor.py` imports `extract_document` (which does not exist; only `extract` exists), and the surrounding `try/except ImportError` silently swallows the failure — the code path has been broken since the rename.

The skill bundle's MCP tool surface (`scripts/mcp/`) and metadata stay; only the library code moves.

## Decision

Use rename-via-overlap across six sequential PRs to relocate the four library files from `skills/document-extractor/scripts/` to `src/lib/extraction/`:

- PR 1 (additive): copy four files verbatim to `src/lib/extraction/`, fix the lazy `from tesseract_ocr import` sibling reference inside `extractor.py` to use the new package path, write `__init__.py` re-exporting `extract`, `ExtractionResult`, `detect_available_tier`, `merge_llm_results`, add smoke tests at `tests/lib/extraction/`, and update the skill's own tests to import from the new path.
- PR 2: migrate rag's two consumers (`document_understanding.py`, `ocr_extractor.py`) — also fix the `extract_document` → `extract` latent bug.
- PR 3: migrate knowledge's `tools_summarize.py`.
- PR 4: migrate file-manager's three sys.path-inject sites in `tools_organize.py` to a single module-top import.
- PR 5: migrate document-extractor's own MCP wrapper (`tools_extract.py`).
- PR 6: delete the four skill-side library files; remove the now-dead `("document-extractor", "ai")` allowlist entry from the architecture test.

## Consequences

### Positive
- All consumers use clean Python imports from `src.lib.extraction` instead of sys.path-injected bareword imports.
- The latent `extract_document` bug in `ocr_extractor.py` is fixed during migration.
- The architecture test's `("document-extractor", "ai")` allowlist entry is retired.
- The bundle's MCP tool surface keeps a clean dependency on the canonical library, like every other consumer.

### Negative
- Six sequential commits with consumer migration in lockstep; intermediate states exist where both paths resolve.
- `src/lib/extraction/ollama_client.py` retains a `from skills.ai.augur.lib import get_llm_client` (`src → skill`) coupling until Track 1 / Library 5 (`ai` extraction) lands. This is acceptable migration scaffolding because the architecture test only catches `skill → skill` and `src → vault-skill`.

### Neutral
- The skill's `conftest.py` may retain harmless dead `sys.path` setup until PR 6 cleanup.

## Alternatives Considered

### Alternative 1: Keep sys.path injection as the canonical pattern
Rejected. Bareword imports are invisible to architecture tests, broke once already (`extract_document` rename), and contradict standard Python packaging.

### Alternative 2: One-shot move with all six changes in a single commit
Rejected. Six PRs mean each change is reviewable in isolation, intermediate states stay green, and rollback granularity is preserved.

## References
- Plan: docs/superpowers/plans/2026-04-29-track1-doc-extractor-extraction.md
- Spec (Layer 1): docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md
- Spec (Layer 4 / Track 1): docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md
