---
status: Accepted
date: 2026-05-31
deciders:
  - gsannikov
related:
  - ADR-755
hub: dev
tags:
  - routines
  - automation
  - self-heal
  - goal-command
superseded_by: null
spec_file: 2026-05-31-routines-goal-command-design.md
plan_file: null
---

# ADR-792: Routines Goal Command

## Decision summary

Add `/routines goal [<goal-id>]` (CLI `aug routine goal`), an in-session autonomous driver that picks a harden/clean goal and runs the ADR-755 routine orchestrator to convergence or budget exhaustion, operating in an isolated worktree and ending at "branch ready + report" for user-controlled merge.

## Context

The ADR-755 deterministic scan layer runs reliably — the self-heal loop logs approximately 17,681 cycles and approximately 2,863 consecutive clean cycles. However, the autonomous fix layer is effectively gated. In live `trust_state.json`, `auto-self-heal` sits at `trust=0.0975`, `total_commits=0`, `total_fixes=0`, `strategy="scan"`: it scans continuously but never commits a fix unattended.

Semantic findings raise `NoSessionAvailable` and pile up in the escalation queue (14-day TTL) waiting for a human session. There is no entrypoint that states a goal and drives routines to convergence unattended. The result is a gap between the scanner's proven reliability and the autonomous fix layer's unrealized potential: findings accumulate faster than they are resolved.

## Decision

Add `/routines goal [<goal-id>]` as an in-session self-loop command. The command:

1. Assesses live scan state from the existing scan_phase and orchestrate_run surfaces.
2. Presents ranked goal suggestions derived from the current escalation queue and recent scan findings; the user selects one (or passes `<goal-id>` to skip the menu).
3. Creates an isolated `goal/<id>-<stamp>` worktree branched off the current branch — never off main — so work is always segregated from the user's active session and from main.
4. Runs the existing orchestrator autonomously: scan → fix → verify → commit, looping until the stop condition is met.
5. Stop conditions: clean scan (converged), no progress for N consecutive iterations, or budget exhausted (token/time cap).
6. Commits only verified checkpoints; does not auto-merge. Residual findings that cannot be resolved are escalated to the existing queue.
7. Ends with a "branch ready + report" summary: what was fixed, what remains, and the worktree branch name for the user to merge via `/dev-merge`.

The command reuses scan_phase, orchestrate_run, escalation_queue, trust, and budget primitives from ADR-755 without replacing them. An in-session run always has an active session, which means `NoSessionAvailable` errors cannot occur — this directly drains the escalation backlog that has accumulated under the headless loop.

## Consequences

**Positive:**
- Closes the gap between the proven scan layer and the unrealized autonomous fix layer, enabling full harden/clean cycles on demand.
- Drains the `NoSessionAvailable` escalation backlog by executing in a session that is always present.
- Reuses the proven ADR-755 routine orchestrator spine (scan, orchestrate, escalation, trust, budget) — no new orchestration primitives required.
- Worktree isolation means in-progress goal work cannot corrupt the user's active session or main.
- The "branch ready + report" contract gives the user full merge authority — no unilateral changes land in main.

**Negative / Risks:**
- Bounded by existing scanner coverage: goal runs cannot fix findings the scanner does not detect.
- Long-running goals require explicit budget caps (token and time); without them, a session could run unboundedly on a large finding set.
- Worktree proliferation: every goal run creates a `goal/<id>-<stamp>` worktree; cleanup discipline is required to avoid stale worktree accumulation over time.

## Amendment (ADR-793)

The original decision stated that an in-session run always has an active session, so `NoSessionAvailable` errors cannot occur. This was accurate for session *detection* (the in-client session is always present) but false for *dispatch*: the catalog-loop ran `--catalog-loop` via a `uv run` subprocess which has no Agent/Task tool, making the Task invoker unavailable and causing `NoSessionAvailable` at dispatch time.

ADR-793 corrects this by converting the catalog-loop to an `inline-session` routine (`goal-loop`) where the AI client itself is the invoker. The `uv run` subprocess is no longer in the dispatch path. Seven atomic `goal-*` MCP ops replace the Python Task invoker for the catalog-loop; the client calls these ops directly to drive the loop. Bare-CLI `aug routine goal <id> --catalog-loop` now fails fast rather than attempting a subprocess dispatch with no invoker.

## References

- Design spec: `docs/superpowers/specs/2026-05-31-routines-goal-command-design.md` — full behavioral specification, state machine, and interface contract.
- ADR-755 — routine orchestrator this command drives; `/routines goal` supplements but does not replace ADR-755 primitives.
- ADR-793 — converts catalog-loop to inline-session routine; governs the `goal-loop` routine and its seven atomic ops.
