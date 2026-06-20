---
status: Implemented
date: 2026-05-16
deciders:
  - gsannikov
related:
  - ADR-176
  - ADR-181
  - ADR-216
  - ADR-405
  - ADR-412
  - ADR-444
  - ADR-614
  - ADR-727
  - ADR-743
  - ADR-744
hub: command
tags:
  - auto-loops
  - adaptive-engine
  - subagents
  - llm-dispatch
  - architecture
superseded_by: null
spec_file: 2026-05-16-auto-loop-runner-modernization-design.md
plan_file: 2026-05-16-auto-loop-runner-modernization.md
---

# ADR-755: Auto-Loop Runner Modernization — Agent-Orchestrated Subagent Execution

## Status

Implemented on 2026-05-16.

The ADR-755 Phase 2 cutover is live for `loop-docs/auto-frontmatter-lint`: the command carries `x-augur-runner: orchestrator`, `adaptive_loop_executor.py` routes marked command fix phases through `routine_orchestrator.orchestrator.fix_one_command()`, and unmarked commands remain on the legacy path. The implementation ships the `routine_orchestrator/` package, `aug routine` CLI surface, trust-ledger re-export, pending-escalation queue, and daemon documentation updates. Verification covered full daemon tests (`1057 passed`), generated-agent drift checks, CLI queue readback, and a real hardening-loop scan over 21 commands that confirmed `auto-frontmatter-lint` is registered on the real repo with no remaining frontmatter findings.

## Context

Auto-loops are Augur's only production scheduled-recurring-work mechanism. The current runtime (ADR-176/181/216/405/412/444, materialized in `shared-vault/skills/daemon/scripts/adaptive/`) has an architectural drift: ADR-444's LLM escalation path uses `build_headless_cmd` (`src/lib/llm_retry.py:206`) to spawn a **fresh CLI subprocess per fix attempt**. That was the only available primitive when ADR-444 shipped, because the daemon launched loops with no available session. Reality moved on: loops are session-launched in practice — manual from a Claude Code / Codex session, or fired by a Codex automation that opens its own session. The headless-subprocess model now solves a problem that no longer exists and *costs* real context loss + zero parallelism + no subagent isolation.

A code-grounded audit (`docs/superpowers/specs/2026-05-16-auto-loop-runner-modernization-design.md` §"Architectural Reality Today") also confirms three other things:

- `launchd` / Task Scheduler only keep the daemon supervisor alive; they do not fire loops.
- Today's `/dev-loops run X` runs auto-commands sequentially in the calling session — no subagent fan-out. One auto-command's LLM escalation blocks the next.
- The scan-first design, the trust/difficulty/reward algorithm, the finding-band classification, and the `protocol: scan-fix` declarative discovery are all valuable and correct. The drift is in the dispatch mechanism alone.

The recent Dream Cycle work (ADR-744) introduced the right shape for AI-native execution: deterministic MCP calls interleaved with judgment phases that run in the *active client's* session. Auto-loops should adopt that shape — not by becoming Dream, but by rebuilding their dispatch around the same agent-orchestrated MCP execution model.

## Decision

Replace the auto-loop runner's LLM dispatch with **agent-orchestrated subagent execution**:

1. **New module** `shared-vault/skills/daemon/scripts/routine_orchestrator/` — sibling to `adaptive/`, not a replacement. Owns scan dispatch, bucket planning, mechanical-fix application, subagent fan-out, escalation-queue handling, and orchestration of the whole run.

2. **Subagent fan-out, two levels.** Top-level: one subagent per loop (5–8 for `/auto-loops all`). Second-level: when a loop's bucket count exceeds a threshold (default 8), the loop subagent spawns grandchild subagents per bucket. Below the threshold, the loop subagent dispatches sequentially in its own context to avoid spawn overhead.

3. **Native subagent surfaces only.** No headless CLI subprocesses. The orchestrator dispatches via the active client's native subagent primitive (Claude Code `Task`, Codex equivalent, Gemini equivalent). Cursor / Copilot and other clients without a subagent surface degrade to sequential inline execution in the calling session.

4. **Pure-Python deterministic path preserved.** `scan_phase.py` + `fix_phase_mechanical.py` are session-agnostic. CI runners, cron jobs, and bare Python scripts can run scan + mechanical fixes with no AI client present (`aug routine scan-only --loop X`).

5. **Pending-escalation queue.** When the deterministic path finds local-semantic findings but no session is present, those findings queue to `get_runtime_dir()/jobs/_escalations/pending.jsonl` with a 14-day TTL. The next session-bound orchestrator run picks them up before its own scan phase. Bridges the no-session and session-bound paths cleanly.

6. **Trust + reward algorithm extracted unchanged.** `routine_orchestrator/trust.py` and `routine_orchestrator/reward.py` extract the pure-algorithm logic from `adaptive/trust_state.py` — same calculations, same state file path, same file format. The legacy engine and the new orchestrator share the same trust state file during the phased migration, so partial-migration states stay coherent.

7. **Per-auto-command opt-in via frontmatter.** Each `auto-*.md` gets a one-line `x-augur-runner: orchestrator` marker during its cutover. Absent the marker, the legacy `adaptive_loop_executor.py` path runs. This makes the migration safely incremental — one auto-command at a time, reversible at any point by removing the marker.

8. **Phase 4 retirement.** Once every auto-command has the marker, `_dispatch_llm_fix` + the auto-loop's use of `build_headless_cmd` are deleted. `adaptive_loop_executor.py` becomes a thin shim that delegates to the orchestrator while preserving the `/dev-loops` CLI surface. `build_headless_cmd` itself is **kept** — other callers outside the auto-loop engine still use it (verified in the spec).

## Non-Goals (deferred to follow-up ADRs)

- **Skill consolidation.** The 11 `loop-*` skills stay as-is. ADR-756 collapses them into 4–5 `routine-*` skills by concern.
- **`journal.jsonl` deprecation.** Real consumers exist outside the adaptive engine (`mcp/_loops.py`, `ops/heal_validate.py`); migrating them is ADR-757's scope.
- **`/dev-loops` rename.** Slash command name stays. Naming unification is ADR-758.
- **Dream cycle integration as a registered routine subtype.** Dream is pre-prod; integration waits for Dream production evidence + ADR-758.
- **Augur-side scheduling beyond what `launchd` / Codex automations already provide.** No new scheduler.
- **Runner rewrites for the adaptive trust / difficulty / reward algorithms.** Extracted and re-used unchanged.

## Consequences

- **Real parallelism.** `/auto-loops all` cuts wall time dramatically — top-level fan-out runs 5–8 loops concurrently; second-level fan-out parallelizes within heavy loops.
- **Continuous context for fixes.** Subagents have the calling session's loaded skills, project context, and MCP tools (filtered by allowlist). Fixes are more likely to be correct than today's context-stripped subprocess.
- **Pure-Python CI path stays clean.** "Lint at 3am via cron with no AI client" still works. Only the LLM escalation requires a session, which matches operational reality.
- **Pending-escalation queue.** Bridges no-session deterministic runs to session-bound LLM runs. Today there's no bridge — a CI-time finding either gets a headless CLI fired immediately (no human to review) or gets lost.
- **Cross-client subagent semantics differ.** Claude Code's `Task` is stable; Codex / Gemini equivalents may have different timeout / context-window / tool-allowlist semantics. Phase 1 validates on Claude Code first; other clients ship in Phase 2 with their own validation gates. Cursor / Copilot degrade to sequential inline (slower, but works).
- **Two-engine concurrency during Phases 2–3** (some auto-commands on orchestrator, others on legacy). Shared trust state file — file-lock semantics must be verified in Phase 1 (mitigation called out in the spec).
- **No skill churn, no rename, no observability rework in this ADR.** Migration risk concentrated on one mechanism at a time. Follow-up ADRs build on a stable orchestrator.
- **Sets up follow-ups cleanly.** Skill consolidation (756), observability merge (757), and Routines unification (758) all become tractable once the dispatch model is fixed. The reverse order would have been pure churn.

## Alternatives Considered

1. **Keep the headless CLI; just add subagent fan-out as a wrapper.** Rejected — leaves the architectural drift in place; every fan-out subagent would still spawn a subprocess and lose context. Doesn't solve the problem; just adds parallelism on top of the wrong primitive.

2. **Full unification with Dream into a "Routines" mechanism in one ADR.** Rejected (this was my original draft, deleted before this ADR was written). The unification ADR tried to land runner-rewrite + skill-collapse + journal-deprecation + naming-change in one decision. Too many concurrent variables. Phased ADRs (755 → 756 → 757 → 758) ship each decision on its own merits and revertable independently.

3. **Retire the adaptive engine entirely; rebuild auto-loops as inline-session multi-phase prompts (Dream-style).** Rejected — throws away the trust+difficulty+reward calculations (load-bearing across all loops) and the per-auto-command `scan()` + finding-band classification (token-saving design that lets us only ever invoke LLM for `LOCAL_SEMANTIC` findings). The right move is to keep the algorithm and rebuild the dispatch around it.

4. **Replace `build_headless_cmd` globally (not just for auto-loops).** Rejected — out of scope; `build_headless_cmd` has other callers (oneshot dispatch in other paths) that don't have the same drift. Surgical replacement for the auto-loop's use only.

## Related

- ADR-176 (Adaptive Loop Engine — original design)
- ADR-181 (Adaptive Loops Consolidation)
- ADR-216 (Adaptive Loop Executor Configuration)
- ADR-405 (Adaptive Loop Effectiveness Overhaul)
- ADR-412 (Adaptive Loop Adaptivity and Convergence)
- ADR-444 (Engine-Level LLM Escalation for Adaptive Loops — the load-bearing reason this ADR is needed)
- ADR-614 (Scheduled Agent Observability)
- ADR-727 (Background Routines — Unified Discovery and Browse Category)
- ADR-743 (File-Based Job Ledger — orchestrator's observability substrate)
- ADR-744 (Dream Cycle — the architectural shape this ADR borrows from for AI-native dispatch)
- **Follow-up ADR-756** — Loop-skill consolidation (`loop-*` → `routine-*` by concern)
- **Follow-up ADR-757** — Observability consolidation (`journal.jsonl` retirement)
- **Follow-up ADR-758** (deferred — needs Dream production evidence) — Routines unification (one registry, one mental model, naming finalization)

---

## Implementation

Run `/adr implement ADR-755` from the intended active worktree. The slash command reads this ADR's `plan_file` (`docs/superpowers/plans/2026-05-16-auto-loop-runner-modernization.md`), reuses the current linked Augur worktree when invoked from one, creates a new implementation worktree only when invoked from the main checkout, and executes the plan via `superpowers:subagent-driven-development` with native Team primitives for the parallel-safe clusters identified in the plan's Parallelism Map.

The plan is TDD-decomposed (failing test first, then implementation, then commit per task). Cluster A is 7 parallel-safe teammates. Wave 4 (CLI + routing patch + docs) is 3 parallel-safe teammates. Everything else is sequential by dependency.

---
