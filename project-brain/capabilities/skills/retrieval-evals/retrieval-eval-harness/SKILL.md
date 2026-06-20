---
name: retrieval-eval-harness
description: Use when defining JSONL retrieval eval datasets, replaying local query judgments, calculating retrieval metrics, or writing file-first eval reports.
---

# Retrieval Eval Harness

## Operating Contract

- Work from user-provided local JSONL datasets, judgment files, retrieval outputs, or eval reports.
- Use local CLIs and deterministic scripts for replay, scoring, and report generation when available.
- Do not call hosted model providers from scripts.
- Leave relevance judgment design, dataset curation, and interpretation of metric tradeoffs to the active AI client.
- Keep platform-specific MCP, dashboard, runtime, and generated-client behavior in an adapter.

## Workflow

1. Inspect the local eval inputs, schema shape, metric requirements, and dependency availability.
2. Produce deterministic local evidence, metric output, or structured file-first reports.
3. Ask for approval before destructive edits, outbound result sharing, or overwriting baseline reports.
4. Report missing dependencies directly instead of fabricating eval output.
