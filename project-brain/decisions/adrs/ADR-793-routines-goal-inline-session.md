---
status: Accepted
date: 2026-05-31
deciders:
  - gsannikov
related:
  - ADR-792
  - ADR-755
  - ADR-758
hub: dev
tags:
  - routines
  - automation
  - self-heal
  - goal-command
  - inline-session
superseded_by: null
spec_file: 2026-05-31-routines-goal-invoker-bridge-design.md
plan_file: null
---

# ADR-793: Routines Goal Catalog-Loop Becomes an Inline-Session Routine

## Decision summary

Convert the routines goal catalog-loop from a Python subprocess dispatch model to an `inline-session` execution model (ADR-758). The AI client drives the convergence loop in-session and uses its own Agent/Task tool as the invoker; bare-CLI `aug routine goal <id> --catalog-loop` run outside a session fails fast with instructive guidance.

## Context

ADR-792 shipped the routines goal catalog-loop assuming an in-session run could dispatch semantic fixes through the existing `subagent_dispatch` module. This assumption is incorrect.

The run path is a `uv run` Python **subprocess** with no access to the parent client's Task tool. In `project-brain/capabilities/skills/daemon/scripts/routine_orchestrator/subagent_dispatch.py`, the module-global `_TASK_INVOKER` (line ~33) is never assigned anywhere in the goal path. The dispatch function `_dispatch_claude_code` (~lines 121–123) raises `NoSessionAvailable("claude-code Task invoker is not installed")` whenever `_TASK_INVOKER` is `None`. The goal CLI path in `daemon/scripts/mcp/__init__.py` — specifically `_routine_catalog_goal_payload` — builds `orchestrate=lambda loop: ro.orchestrate_run(loop, session=session)` with no `task_invoker` argument, so every attempt to dispatch a semantic fix hits this branch.

A subprocess fundamentally cannot call back into the parent client's Task tool. As a result, `--catalog-loop` loops can only raise `NoSessionAvailable` errors, never dispatch fixes. The escalation backlog that ADR-792 intended to drain cannot be drained by this path; findings accumulate further.

The precedent for the right fix is the `dream` skill: `dream/SKILL.md` declares `execution: inline-session` and explicitly notes "makes no Augur LLM call" — the AI client itself is the execution engine, calling atomic CLI/MCP ops between spawning its own fix subagents. ADR-758 formalises this as the `inline-session` execution model.

## Decision

Convert the catalog-loop to an **inline-session** routine following the ADR-758 model.

1. **Execution model:** The AI client drives the convergence loop entirely in-session. It uses its own native Agent/Task tool as the subagent invoker — no Python code ever calls back into a Task tool. This is the same execution model used by the `dream` skill.

2. **Atomic CLI surface:** The ADR-755 spine (scan, mechanical fix, bucket plan, verify+commit, escalate, status) is exposed as discrete `aug routine goal-*` CLI operations that the client calls between spawning its own fix subagents. These operations are pure, side-effect-bounded, and callable from any shell — they do not attempt dispatch themselves.

3. **Fast-fail for bare-shell invocations:** `aug routine goal <id> --catalog-loop` invoked in plain shell (no active AI client session / no Task tool) fails immediately with a clear error explaining that this routine requires an inline session and pointing to the correct invocation path.

4. **Backlog drain first:** When the inline-session prompt starts, it drains the existing `NoSessionAvailable` escalation backlog before scanning for fresh findings — fulfilling ADR-792's original motivation without relying on the broken subprocess dispatch path.

5. **No interim headless option:** No `claude -p` or other headless-`claude` wrapper is shipped as an interim dispatch path. The inline-session model is the full solution.

## Consequences

**Positive:**
- Root-cause fix: no Python code calls back into a Task tool, so `NoSessionAvailable` cannot occur in the goal path.
- Rule-19 aligned: the agent orchestrates; MCP/CLI ops are atomic. This mirrors the proven pattern from the `dream` skill.
- Reuses the entire ADR-755 spine (scan, mechanical fix, bucket plan, verify+commit, escalate, status) — no new orchestration primitives required.
- Escalation backlog is drained correctly because the AI client session is present from the start of the run.

**Negative / Risks:**
- Loop control flow moves from a Python `while` loop into the rendered inline-session prompt. Convergence honesty now depends on the `goal-loop-status` op's outputs being accurate and useful (rules 8 and 34).
- `subagent_dispatch._TASK_INVOKER` and `_dispatch_claude_code` become dead code for the goal path. They are retained for tiered/headless/test uses and marked `TODO_CLEANUP` for a future sweep when those uses are confirmed absent or migrated.
- Bare `--catalog-loop` shell invocations that previously silently errored now fail fast and visibly — a better user experience, but a breaking change for any scripted callers.

## Amendments to ADR-792

ADR-792 claimed that "an in-session run always has an active session, which means `NoSessionAvailable` errors cannot occur." That claim is true for session *detection* but false for *dispatch* — because the run path is a subprocess, the session is detected but the Task invoker is never wired, so dispatch still raises `NoSessionAvailable`. This ADR corrects that premise and provides the fix.

## References

- Design spec: `docs/superpowers/specs/2026-05-31-routines-goal-invoker-bridge-design.md` — full behavioral specification, atomic op surface, and inline-session prompt contract.
- ADR-792 — goal command this ADR amends; the catalog-loop premise is corrected here.
- ADR-755 — routine orchestrator spine reused by the inline-session loop.
- ADR-758 — inline-session execution model; `dream` skill is the precedent implementation.
