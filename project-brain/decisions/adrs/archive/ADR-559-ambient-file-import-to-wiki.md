---
status: Implemented
date: '2026-04-20'
deciders:
- Gur Sannikov
related:
- ADR-004
- ADR-404
- ADR-478
- ADR-545
- ADR-561
hub: brain
tags:
- ingest
- wiki
- rag
- ambient-import
- documents
superseded_by: null
implemented_date: '2026-04-15'
implementation_commits:
- b2f4545246
- 5b72c0b2ba
- 9d35d1fdac
---

# ADR-559: Ambient File Import To Wiki

## Context

Augur could already index vault files, documents, skills, pages, and wiki pages, but the user experience still did not feel ambient. Dropping or creating a file in a normal Augur-owned location did not reliably carry that item through the product loop: detect, prioritize, compile into the wiki, relocate safely, reindex, and stamp compile state.

A dedicated inbox-style import model was also the wrong center of gravity for Stage 1. The normal owned surfaces should be enough for file-backed import, while connector-backed sources need a later source model because they do not have local relocation semantics.

## Decision

Implement Stage 1 ambient import as a file-backed pipeline over normal Augur-owned surfaces:

- `vault/`
- `documents/`
- `skills/`
- Augur repo pages under `skills/*/augur/pages/*.yaml` and `skills/*/augur/dashboard/*`

The pipeline reuses RAG as the indexed-source inventory instead of adding a second import registry. Fresh detections are prioritized for wiki compilation, then relocated only inside their owning surface. After relocation, the affected RAG category is reindexed so the source inventory can feed the wiki compiler.

Current implementation note: ADR-561 replaced the original RAG-backed wiki backlog and `wiki_targets` restamping mechanism with a concept-first compiler. Ambient import now prepares concept extraction batches from detected source descriptors instead of writing RAG compile state.

The public MCP surface is:

- `ambient-import-status`: inspect fresh Stage 1 detections and eligible concept extraction sources.
- `ambient-import-cycle`: run one scan, prepare a concept extraction batch, relocate within the owning surface when safe, and reindex affected sources.

## Consequences

Positive:

- Normal owned folders become practical intake surfaces.
- Fresh file-backed sources can jump ahead of lower-priority source inventory material.
- The wiki compiler and RAG index remain the central knowledge pipeline.
- Relocation is constrained to the source ownership surface, preventing cross-root moves.

Negative:

- File relocation means ambient import must be conservative about surface classification.
- The worker couples ingest, concept-batch preparation, RAG reindex, and relocation behavior, so tests need to cover the whole loop.

Neutral:

- Connector-backed sources are intentionally out of scope for Stage 1.
- The wiki remains compiled output and is not itself an ambient import root.

## Implementation Evidence

Key implementation files:

- `skills/ingest/scripts/ambient_import_surfaces.py`
- `skills/ingest/scripts/ambient_import_relocator.py`
- `skills/ingest/scripts/ambient_import_worker.py`
- `skills/ingest/scripts/tracked_folder_scanner.py`
- `skills/ingest/scripts/wiki_concept_compiler.py`
- `skills/ingest/scripts/wiki_concept_state.py`
- `skills/ingest/scripts/wiki_source_inventory.py`
- `skills/ingest/scripts/mcp/ingest_tools.py`
- `skills/ingest/SKILL.md`
- `skills/rag/scripts/unified_indexer.py`

Representative tests:

- `skills/ingest/augur/tests/test_ambient_import_surfaces.py`
- `skills/ingest/augur/tests/test_ambient_import_relocator.py`
- `skills/ingest/augur/tests/test_ambient_import_worker.py`
- `skills/ingest/augur/tests/test_tracked_folder_scanner.py`
- `skills/ingest/augur/tests/test_wiki_concept_compiler.py`
- `skills/ingest/augur/tests/test_wiki_concept_state.py`
- `skills/ingest/augur/tests/test_wiki_source_inventory.py`
- `skills/ingest/augur/tests/test_ingest_tools.py`
- `skills/rag/augur/tests/test_unified_indexer.py`

## Alternatives Considered

### Dedicated Import Registry

Rejected. RAG already owns indexed-source metadata and freshness. A parallel registry would duplicate source truth and create synchronization debt.

### Dedicated Inbox Folder

Rejected for Stage 1. The intended experience is ambient import from normal Augur-owned folders, not forcing users into a staging inbox.

### Cross-Root Auto-Routing

Rejected. Files can be renamed or moved only within their current ownership surface. Moving from vault to documents, documents to repo, or repo to vault changes ownership and requires explicit user intent.

## References

Absorbed transient artifacts:

- `docs/superpowers/specs/2026-04-15-ambient-file-import-to-wiki-design.md`
- `docs/superpowers/plans/2026-04-15-ambient-file-import-to-wiki.md`

## Impact Manifest

```yaml
paths_renamed: []
apis_changed:
  - skills/ingest/scripts/mcp/ingest_tools.py: registers ambient-import-status and ambient-import-cycle
  - skills/ingest/scripts/ambient_import_worker.py: prioritizes detected sources for concept extraction batches
  - skills/rag/scripts/unified_indexer.py: supports documents reindexing for ambient moves
patterns_deprecated:
  - file-backed import only through inbox-style routing
files_affected:
  - skills/ingest/scripts/ambient_import_surfaces.py
  - skills/ingest/scripts/ambient_import_relocator.py
  - skills/ingest/scripts/ambient_import_worker.py
  - skills/ingest/scripts/tracked_folder_scanner.py
  - skills/ingest/scripts/wiki_concept_compiler.py
  - skills/ingest/scripts/wiki_concept_state.py
  - skills/ingest/scripts/wiki_source_inventory.py
  - skills/ingest/scripts/mcp/ingest_tools.py
  - skills/rag/scripts/unified_indexer.py
```
