---
name: dream-routine
description: Use when designing or running a recurring agent reflection routine that reviews local knowledge state, proposes cleanup, and writes a report without owning scheduler or hosted LLM calls.
---

# Dream Routine

## Operating Contract

- Work from user-provided local knowledge folders, status reports, stale-item lists, or prior reflection reports.
- Use local CLIs and deterministic scripts for inventory, consistency checks, and report assembly when available.
- Do not call hosted model providers from scripts.
- Leave synthesis, prioritization, and cleanup recommendations to the active AI client.
- Keep platform-specific MCP, dashboard, runtime, and generated-client behavior in an adapter.

## Workflow

1. Inspect the local knowledge state, routine inputs, report targets, and dependency availability.
2. Produce deterministic local evidence, proposed cleanup records, or structured reflection reports.
3. Ask for approval before destructive cleanup, outbound publication, or changing scheduled behavior.
4. Report missing dependencies directly instead of fabricating reflection output.
