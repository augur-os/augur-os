---
x-augur-export-command: true
---
# /a-loops

Unified command surface for Augur loops. A loop is recurring AI-orchestrated
work declared by a skill with `x-augur-routine` or `x-augur-routines` frontmatter.

## Usage

```text
# The loop name is the command — names any loop directly:
/a-loops <loop-name>          # e.g. /a-loops inbox-triage, /a-loops hardening
/a-loops <goal-name>          # e.g. /a-loops harden  (a curated multi-loop bundle)

# Explicit verbs (escape hatches):
/a-loops list
/a-loops status [routine-id]
/a-loops run <routine-id>
/a-loops report <routine-id>
/a-loops schedule [routine-id]
/a-loops goal [goal-id]
/a-loops all                  # parallel scan-triage + capped fan-out (orchestrator loops)
```

Naming a loop runs it with the right loop-engineering treatment for its kind — orchestrator loops as a single-loop goal (isolated worktree, subagent fixes, verified checkpoints), prompt loops as an in-session prompt. You never need `run`/`goal`/`--catalog-loop`; they remain for explicit control.

CLI equivalent:

```bash
# The loop name is the command:
aug a-loops <loop-name>
aug a-loops <goal-name>

# Explicit verbs:
aug a-loops list
aug a-loops status [routine-id]
aug a-loops run <routine-id>
aug a-loops report <routine-id>
aug a-loops schedule [routine-id]
aug a-loops goal [goal-id]
```

## Verbs

| Verb | Purpose |
|---|---|
| `list` | Show every declared loop as a grouped table (PROMPT vs ORCHESTRATOR) with kind, runner, owning skill, and trust, plus a "how to run" footer. Add `--json` for raw machine output. |
| `status` | Show recent ledger-derived runs for one loop or the full registry. |
| `run` | Dispatch one loop through its declared execution model. |
| `report` | Show recent report artifacts for a loop-owned report directory. |
| `schedule` | Show client schedule seed bindings from each owning skill. |
| `goal` | Run or list concrete goal proofs; `--suggest` and `--catalog-loop` expose ADR-792 catalog goals. |
| `all` | Scan-triage every orchestrator loop, then fan out capped-parallel single-loop goal runs (own worktree each) only for loops with findings. In-session; bare CLI `aug a-loops all` fails fast (use `--dry-run` for the plan). |

## Goal Mode (ADR-792)

`/a-loops goal` without flags lists concrete goal proofs such as
`demo-readiness`. `aug a-loops goal demo-readiness` runs deterministic proof
steps and writes a runtime report.

`/a-loops goal --suggest` assesses live project debt across loops and
presents ranked catalog goal suggestions. `/a-loops goal <goal-id>
--catalog-loop` runs a catalog goal to convergence independently of further user
interaction. Built-in catalog goals: `harden`, `clean`, `harden-and-clean`.

**Catalog-loop is an inline-session loop (ADR-793).** The catalog-loop
(`goal-loop`) is an `inline-session` loop: the AI client is the invoker and
drives the loop using seven atomic goal-* MCP ops. Bare-CLI
`aug a-loops goal <id> --catalog-loop` **fails fast** — the `uv run` subprocess
has no Task tool. Run `/a-loops goal <id> --catalog-loop` in-session, which
renders the inline-session prompt.

The seven atomic ops the client calls during a catalog-loop run:

| Op | Purpose |
|---|---|
| `goal-worktree` | Create/reuse the isolated `goal/<id>-<stamp>` worktree for this run. |
| `goal-scan-loop` | Run one scan-fix-verify iteration of a named loop within the goal worktree. |
| `goal-record-bucket` | Verify the worktree after a bucket fix and commit a verified checkpoint (no commit on red). |
| `goal-loop-status` | Return the loop convergence verdict (converged / stalled / exhausted / continue). |
| `goal-escalate` | Move residual unresolved findings to the escalation queue. |
| `goal-drain-backlog` | Pull pending escalated findings into the active goal run for resolution. |
| `goal-consume-finding` | Mark a single finding as consumed (resolved or deferred) in the goal ledger. |

When you (the AI client) run a picked goal:

1. Confirm a native AI-client session is active. Catalog loop mode requires it, and that
   is exactly what drains the no-session escalation backlog the nightly daemon
   cannot touch.
2. Run `/a-loops goal <goal-id> --catalog-loop` (in-session). It renders the
   inline-session prompt; the client creates an isolated
   `<repo>/.worktrees/goal/<id>-<stamp>` worktree off the **current** branch
   (never main), then drives each loop in the goal's ordered plan
   (test/build before hygiene) to converge / stall / exhaust using the
   `goal-*` atomic ops above.
3. Each loop commits **only verified checkpoints** (the orchestrator's verify
   gate). Stalled or exhausted residual findings go to the escalation queue —
   never dropped.
4. Do **not** merge. End at "branch ready + report" and surface the branch for
   the user to review via `/dev-merge`.
5. Report honestly: per-loop convergence, totals, and residual — never "all
   clean" when a loop stalled or exhausted.

Flags: `--suggest`, `--catalog-loop`, `--stamp <s>` (branch stamp; default UTC
timestamp), `--max-iterations N` (whole-run budget), `--loop-cap N`
(per-loop iteration cap), and `--suggest-timeout-seconds N`.

## Execution Models

`tiered` loops dispatch through the ADR-755 routine orchestrator and require a
native AI-client session for agentic runs. Use `aug a-loops scan-only --loop <id>`
for deterministic scanner-only execution.

`inline-session` loops render their command prompt into the current session.
Dream is the first inline-session loop. The catalog-loop (`goal-loop`, ADR-793)
is the second: the AI client drives the loop and uses its own Agent/Task tool as
the invoker, calling the seven `goal-*` atomic ops directly. Bare-CLI invocation
of `--catalog-loop` fails fast because the `uv run` subprocess context provides
no Task tool.

## Extended Dispatch (Consolidation)

### /a-loops goal [goal-id]

Run a bounded, in-session goal loop over existing loop and demo proof
surfaces. This is the surface for "set goal: prepare demo" after a merge. The
Python runner performs deterministic checks and writes runtime reports; the
active AI client owns the semantic edit loop by reading `next_actions`, patching
code/docs/skills when needed, and rerunning until the status is `ready`,
`stalled`, or `exhausted`.

Current goal:

- `demo-readiness` (aliases: `prepare demo`, `first demo`, `demo`) runs:
  1. demo readiness (`demo_ready.py ready`)
  2. demo smoke (`demo_ready.py smoke`)
  3. project compounding proof (`dev_merge_demo_proof.py --com --skillify --compound-review`)

Examples:

```text
/a-loops goal
/a-loops goal demo-readiness
/a-loops goal demo-readiness --max-iterations 3
/a-loops goal demo-readiness --compound-proposal-json <runtime-proposal-json>
```

CLI equivalent:

```bash
aug a-loops goal
aug a-loops goal demo-readiness
aug a-loops goal demo-readiness --max-iterations 3
aug a-loops goal demo-readiness --compound-proposal-json <runtime-proposal-json>
```

Agent contract:

1. Run `aug a-loops goal demo-readiness --max-iterations 1`.
2. If status is `ready`, report the JSON and Markdown runtime artifacts.
3. If status is `needs_agent_action`, inspect `next_actions` and the failed
   check output. Make the smallest code/docs/skill fix in the current worktree,
   or write the requested compound proposal JSON from the evidence artifact.
4. Rerun the same goal command. Repeat until `ready`, `stalled`, or `exhausted`.
5. Never call the goal ready from tests alone; cite the real check outputs and
   runtime report path.

### /a-loops all

Run **all orchestrator (tiered) loops in parallel** — cheap scan-triage first,
then a capped-parallel fan-out of single-loop goal runs only for the loops that
have findings. This is an **inline-session** command (the AI client is the
invoker and spawns the fix-subagents). Bare-CLI `aug a-loops all` fails fast;
`aug a-loops all --dry-run` prints the triage plan only.

Scope is the 14 orchestrator loops; `dream`/`inbox-triage` (prompt loops) and
`goal-loop` (the driver) are excluded.

Flags: `--dry-run` (triage only), `--cap N` (default 6, clamped to worktree
headroom), `--include a,b` / `--exclude a,b`, `--max-iterations N`, `--loop-cap N`.

Phases 1 and 3 are also available as atomic CLI verbs — deterministic,
non-mutating, and callable without an in-session client:
`aug a-loops goal-fanout-plan` (triage) and `aug a-loops goal-fanout-report`
(rollup). Both follow the same pattern as the other `goal-*` ops. A returned
`safe_cap: 0` means the worktree registry is full — queue all loops; launch
as slots free rather than refusing.

When you (the AI client) run `/a-loops all`:

1. **Triage** — call `goal-fanout-plan` (apply `--include`/`--exclude`/`--cap`).
   It returns `loops_with_work`, `per_loop_counts`, `skipped_clean`, and
   `safe_cap`. Print the plan. If `--dry-run`, stop here.
2. **Fan out** — for each loop in `loops_with_work`, dispatch a subagent, at most
   `safe_cap` concurrently (queue the rest). Each subagent drives **one** loop to
   convergence in its **own** worktree exactly like a single-loop goal:
   `goal-worktree <loop>` → repeat (`goal-scan-loop` → spawn the returned bucket
   fix-subagents → `goal-record-bucket` per bucket → `goal-loop-status`) until
   `converged`/`no_op`/`stalled`/`exhausted`, honoring `--max-iterations`/`--loop-cap`.
   Pass `goal-loop-status` the running `committed_count` (verified checkpoints
   landed) and `out_of_scope_count` (sum of each scan's `out_of_worktree`) so it
   can return `no_op` — a loop whose fingerprint went empty ONLY because every
   finding was out of scope and nothing was committed — instead of a false
   `converged`. Push residuals with `goal-escalate`. Commit only verified
   checkpoints. Do **not** merge.
2b. **Run in-place loops (ADR-818 phase 2)** — the plan also returns
   `in_place_loops` (loops the worktree fan-out excludes because they act on the
   live vault/runtime/external state) and `in_place_surfaces` (`{loop: surface}`).
   These are NOT fanned out into worktrees. For each, call
   `goal-run-inplace --loop <loop> --surface <surface>`, which drives the daemon
   engine against the live target with surface-tiered guardrails: `runtime`
   aggressively auto-applies via the loop's own sanctioned tools (no git commit);
   `repo` commits to the code repo; `vault` is **gated on ADR-816** (the
   cross-machine write lock) and currently scans + escalates only (no auto-commit)
   so it cannot race the nightly daemon / another machine. Collect each
   `{loop, surface, mechanical_applied, escalated, gated_on}` for the rollup.
3. **Aggregate** — collect each loop's `{loop, verdict, branch, residual,
   committed_checkpoints, out_of_scope}` and call `goal-fanout-report` to write the
   rollup. Surface every branch for `/dev-merge`. Report per-loop verdicts honestly
   — never "all clean" if any loop stalled/exhausted/failed OR merely no-op'd
   (0 commits, out-of-scope-only). If a driver subagent finishes but returns
   nothing, still include a stub `{loop, branch, unreported: true}` (or `null`):
   `goal-fanout-report` reconstructs that loop's verdict from its worktree
   (checkpoint commits, clean/dirty, branch) and marks it
   `unreported (reconstructed)` or `unknown` rather than dropping it or claiming
   success.

This reuses the single-loop goal machinery per loop; `/a-loops all` only adds the
triage + capped fan-out + aggregate layer.

### /a-loops scan <category>

Run daemon scan-fix operations manually. This absorbs all 76 auto-* commands
that previously ran as standalone daemon operations.

Categories map to loop groups in the adaptive loop engine:
- `lint` -> auto-lint, auto-format
- `tests` -> auto-test-pytest, auto-test-build, auto-test-dashboard, etc.
- `quality` -> auto-ui-quality, auto-code-health, auto-doc-freshness
- `skill` -> auto-skill-enhance, auto-skill-structure, auto-skill-migrate, etc.
- `security` -> auto-security-scan
- `index` -> reindex-rag, reindex-project, auto-index-notes
- `vault` -> auto-vault-hygiene, auto-frontmatter-lint, auto-markdowns
- `all` -> run all scan categories

Execution: call the routine orchestrator with the specified category filter.

### /a-loops ops <verb>

Operational commands (absorbs former ops-* standalone commands):
- `daemon` -> manage daemon lifecycle (start, stop, restart, status, heal)

  **CRITICAL**: Never run `unified_daemon.py start` directly — spawns inside Claude Code's process tree and prevents the self-healer from working.

  Actions (entrypoint: `python project-brain/capabilities/skills/daemon/scripts/service_healer.py`):
  - **status**: `service_healer.py status` + `unified_daemon.py status` — reports OS service registration and daemon internal state.
  - **install/start**: `service_healer.py install` — registers the background service via `launchd` (macOS) or Task Scheduler (Windows).
  - **stop/restart/uninstall**: use the platform service manager (see `references/launchd-usage.md` / `references/windows-task-usage.md`); `service_healer.py uninstall` removes the registration.
  - **heal**: `service_healer.py heal` — re-applies paths if the project moved; re-run install afterward to refresh the platform manager.

  Default action when no verb is specified: **status**.
- `audit` -> audit context usage across agents
- `memory` -> sync session memory across agents, curate daily logs
- `learn` -> extract learnings from thread, persist to memory + docs

### /a-loops <engine-verb>

Adaptive-loop-engine operator verbs pass through to
`project-brain/capabilities/skills/daemon/scripts/adaptive_loop_executor.py` (which accepts
both subcommand and `--flag` forms). These are the successors to the retired
`/dev-loops` operator subcommands:

- `heal [--fix]` -> diagnose and repair broken runtime/trust state
- `configure <loop> --budget N` -> set a loop's per-cycle fix budget
- `promote [<loop> <category>]` -> re-enable a demoted category, reset immediate trust/difficulty
- `reset` -> reset trust state only (preserves lifetime stats)
- `disable <loop>` -> stop scheduling a loop
- `diagnose` -> report trust/structural findings without fixing
- `registry` / `manifest` -> alias of `list` (declared loops / schedule manifest)
- `history` -> alias of `status` (ledger-derived run history)
- `pending [--create-adr]` -> show pending escalations (also `aug a-loops pending-escalations`)

Execution: dispatch the verb and its arguments to `adaptive_loop_executor.py`.

## Alias Window

`/dream` remains available during the ADR-758 transition period.
New automation and operator workflows should use `/a-loops`.
