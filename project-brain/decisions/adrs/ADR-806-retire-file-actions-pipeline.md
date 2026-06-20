---
status: Accepted
date: 2026-06-09
deciders:
  - gsannikov
related:
  - ADR-130
  - ADR-143
  - ADR-162
  - ADR-263
  - ADR-805
hub: null
tags:
  - actions
  - browse
  - cleanup
  - skills
superseded_by: null
spec_file: 2026-06-09-augur-category-action-refactor-design.md
plan_file: 2026-06-09-actions-p1-delete-dead-pipeline.md
---

# ADR-806: Retire the FILE-actions pipeline

## Decision summary

The `{skill}/augur/actions/*.md` "FILE-actions" pipeline is dead weight and is removed.
A 2026-06-09 trace found 59 such files (58 empty `*-overview` stubs); their only consumer
was the Browse "Actions" tab, whose Run button injects the bare action id as a no-op CLI
prompt and never reads the file body/`dispatch`/`tool`. The orphaned `list-action-buttons`
MCP tool and the WebMCP `actions.*` tools glob an empty `assets/**/actions/*.md` directory.

This ADR supersedes ADR-130 (Action Button Dispatch Modes), ADR-143 (Action YAML Migration),
ADR-162 (Action Type Consolidation), and ADR-263 (Standardized Markdown Action Instructions)
for the `.md` FILE-actions surface. The canonical "skill button → AI agent" mechanism is the
unified `{skill}/augur/actions.yaml` declaration (ADR to follow, Plan 2), consumed by the
existing Browse-card baker and `useActionRunner` dispatch.

The `execute-fast-action` MCP tool and the daemon scheduler are intentionally retained here;
their migration onto the unified model is Plan 2.

## Status notes

Implemented by `docs/superpowers/plans/2026-06-09-actions-p1-delete-dead-pipeline.md`.

## Related

- ADR-130, ADR-143, ADR-162, ADR-263 (superseded for the FILE-actions surface)
- ADR-805 (native-first skillify — skills as the unit)
