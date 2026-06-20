---
description: Coordinate multi-agent execution, backlog dispatch, and chain-based workflows.
visibility: core
---

# /orchestration

Use when coordinating parallel agent work, backlog dispatch, or sequential chain execution.

## What It Covers

- team-based execution for independent tasks
- chain-based execution for ordered dependencies
- backlog-driven dispatch for queued work
- progress monitoring, review, and integration

## Dispatch Modes

- default interactive subagent dispatch
- `--preset team` for predefined swarm patterns
- `--review` to inspect and integrate prior offloaded work

## Guidance

- use teams when tasks are independent
- use chains when one step must wait for another
- assign validator-style work separately from implementation work
- keep orchestration as the canonical owner for dispatch-style workflows

## Usage

```bash
/orchestration
```
