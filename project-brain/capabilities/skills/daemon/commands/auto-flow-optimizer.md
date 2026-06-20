---
description: Detect dispatch mode mismatches across actions
visibility: ops
---

# auto-flow-optimizer

Analyze action dispatch configurations for mode mismatches (e.g. `fire` for
actions that need LLM, `ide` for simple CRUD).
Daemon-managed (hardening loop, tier 5).

Note: RAG coverage gaps are handled by auto-rag-reindex (knowledge-enrichment loop).

## Scan

- **d0+**: Checks all action YAML `dispatch:` fields against description keywords
  to detect mismatches (LLM-suggesting descriptions with `fire` dispatch, or
  simple operations using `ide`/`chat` dispatch)

## Fix

Generates `docs/generated/flow-optimizer-report.md` with dispatch mismatch
table. Does not auto-modify dispatch modes — changes require manual review
due to behavioral impact.
