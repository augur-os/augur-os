---
name: wiki
x-augur-type: domain
x-augur-group: brain
x-augur-release: mvp
x-augur-license: MIT
description: Concept-first wiki engine that compounds ingested content into durable knowledge pages. Use when scanning wiki sources, updating concept pages, running compounding batches, reading wiki structure, checking wiki status, or running wiki queries.
x-augur-requires-platform: true
x-augur-mcp-tools:
- wiki-report-data
- wiki-rewrite-candidates
- wiki-queries-list
- wiki-queries-read
- wiki-queries-write
- wiki-queries-seed-defaults
- wiki-queries-run
---

# Wiki

Concept-first wiki engine that compounds source cards into durable,
linked knowledge pages.

## Scope

Use this skill when the work is about the wiki compounding pipeline:
scanning source inventory, extracting concepts, writing concept pages,
running batched updates, generating wiki reports, reading wiki structure,
or executing wiki queries.

The wiki engine reads source cards (written by `ingest`) from the RAG
directory, maintains compiler state in the runtime wiki directory, and
writes compiled concept pages to the vault wiki directory.

## Workflow

Step 1. Identify the wiki operation: status check, source scan, concept
batch, report generation, query run, or structural lint.

Step 2. Select the canonical surface:
- `scripts/wiki_status.py` for aggregated operational status.
- `scripts/wiki_scanner.py` for source inventory scanning.
- `scripts/wiki_concept_compiler.py` for concept extraction batches.
- `scripts/wiki_maintenance.py` + `scripts/wiki_maintenance_ops.py` for
  structural lint and rewrite operations.
- `scripts/mcp/wiki_tools.py` for MCP tool registration and CLI bridge.
- `scripts/mcp/wiki_queries_tools.py` for query registry MCP tools.

Step 3. Preserve all source fingerprints and compiler state. Use the
configured path helpers for wiki, compiled-wiki, and runtime-wiki
directories rather than hardcoded paths.

Step 4. After writes, verify the relevant wiki surface (status, list,
search) reflects the updated artifact.

## References

- `scripts/mcp/` for tool names and request/response contracts.
- `augur/tests/test_wiki*.py` for expected engine behavior.
- `assets/seeds/wiki-schema/` for page-type and entity-type schemas.
- `assets/templates/wiki-page.md` for the wiki page template.
- `assets/seeds/queries-defaults.yaml` for default query seeds.
