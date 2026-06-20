---
description: Rebuild the master project index of skills, pages, actions, commands, and ADRs
context: current
agent: general-purpose
visibility: ops
---

# /reindex-project

Runs `project_indexer.py` to rebuild the master catalog of all skills, hub
pages, actions, slash commands, and ADRs into
`~/Library/Application Support/Augur/rag/project-index.yaml`.

## What it does

- **Scan**: Always returns a single issue — the project index needs refreshing
  each nightly cycle to reflect any new or modified plugins.
- **Fix**: Executes `skills/knowledge/scripts/project_indexer.py`
  which writes the updated catalog to the centralized RAG directory.

## Usage

Run automatically by the daemon at `tier: 0` (`trigger: nightly`) in the
`knowledge-enrichment` loop. Can also be invoked manually via `/routines`.

## Protocol

Implements the `OpsCommand` protocol (`scan-fix`). Dry run is supported —
pass `dry_run=True` to skip the indexer invocation.

## Implementation

`skills/ai/scripts/ops/project_index.py`
