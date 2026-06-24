---
description: Rebuild centralized RAG indexes for all skills with plugin-local or vault-backed markdown content
context: current
agent: general-purpose
visibility: ops
---

# /reindex-rag

Walks skill roots plus vault-backed data for markdown content, runs
`rag_indexer.py` on each stale skill, stages the resulting centralized RAG
output under `~/Library/Application Support/Augur/rag/{bundle}/{skill}/`, and produces a
single batched git commit for all updated skills.

## What it does

- **Scan**: Compares markdown content in each skill root plus its vault data
  against the centralized RAG output. Returns one issue per stale skill.
- **Fix**: Runs `skills/rag/scripts/rag_indexer.py <skill_path>` via
  subprocess (uses built-in checksum change detection — unchanged skills are
  skipped automatically). Stages the centralized RAG directory for each skill
  and commits all at once at the end.

## Usage

Run automatically by the daemon at `tier: 0` (`trigger: nightly`) in the
`knowledge-enrichment` loop. Can also be invoked manually via `/a-loops`.

## Protocol

Implements the `OpsCommand` protocol (`scan-fix`). Dry run is supported —
pass `dry_run=True` to scan without running the indexer or writing any changes.

## Implementation

`skills/ai/scripts/ops/rag_reindex.py`
