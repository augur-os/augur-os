---
x-augur-export-command: true
---
# /routines

Unified command surface for Augur routines. A routine is recurring AI-orchestrated
work declared by a skill with `x-augur-routine` or `x-augur-routines` frontmatter.

## Usage

```text
/routines list
/routines status [routine-id]
/routines run <routine-id>
/routines report <routine-id>
/routines schedule [routine-id]
/routines goal [goal-id]
```

CLI equivalent:

```bash
aug routine list
aug routine status [routine-id]
aug routine run <routine-id>
aug routine report <routine-id>
aug routine schedule [routine-id]
aug routine goal [goal-id]
```

## Verbs

| Verb | Purpose |
|---|---|
| `list` | Show every declared routine, execution model, policy, skill owner, and callable. |
| `status` | Show recent ledger-derived runs for one routine or the full registry. |
| `run` | Dispatch one routine through its declared execution model. |
| `report` | Show recent report artifacts for a routine-owned report directory. |
| `schedule` | Show client schedule seed bindings from each owning skill. |
| `goal` | Run or list concrete goal proofs; `--suggest` and `--catalog-loop` expose ADR-792 catalog goals. |

## Goal Mode (ADR-792)

`/routines goal` without flags lists concrete goal proofs such as
`demo-readiness`. `aug routine goal demo-readiness` runs deterministic proof
steps and writes a runtime report.

`/routines goal --suggest` assesses live project debt across routine loops and
presents ranked catalog goal suggestions. `/routines goal <goal-id>
--catalog-loop` runs a catalog goal to convergence independently of further user
interaction. Built-in catalog goals: `harden`, `clean`, `harden-and-clean`.

**Catalog-loop is an inline-session routine (ADR-793).** The catalog-loop
(`goal-loop`) is an `inline-session` routine: the AI client is the invoker and
drives the loop using seven atomic goal-* MCP ops. Bare-CLI
`aug routine goal <id> --catalog-loop` **fails fast** — the `uv run` subprocess
has no Task tool. Run `/routines goal <id> --catalog-loop` in-session, which
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
2. Run `/routines goal <goal-id> --catalog-loop` (in-session). It renders the
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

`tiered` routines dispatch through the ADR-755 routine orchestrator and require a
native AI-client session for agentic runs. Use `aug routine scan-only --loop <id>`
for deterministic scanner-only execution.

`inline-session` routines render their command prompt into the current session.
Dream is the first inline-session routine. The catalog-loop (`goal-loop`, ADR-793)
is the second: the AI client drives the loop and uses its own Agent/Task tool as
the invoker, calling the seven `goal-*` atomic ops directly. Bare-CLI invocation
of `--catalog-loop` fails fast because the `uv run` subprocess context provides
no Task tool.

## Extended Dispatch (Consolidation)

### /routines goal [goal-id]

Run a bounded, in-session goal loop over existing routine and demo proof
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
/routines goal
/routines goal demo-readiness
/routines goal demo-readiness --max-iterations 3
/routines goal demo-readiness --compound-proposal-json <runtime-proposal-json>
```

CLI equivalent:

```bash
aug routine goal
aug routine goal demo-readiness
aug routine goal demo-readiness --max-iterations 3
aug routine goal demo-readiness --compound-proposal-json <runtime-proposal-json>
```

Agent contract:

1. Run `aug routine goal demo-readiness --max-iterations 1`.
2. If status is `ready`, report the JSON and Markdown runtime artifacts.
3. If status is `needs_agent_action`, inspect `next_actions` and the failed
   check output. Make the smallest code/docs/skill fix in the current worktree,
   or write the requested compound proposal JSON from the evidence artifact.
4. Rerun the same goal command. Repeat until `ready`, `stalled`, or `exhausted`.
5. Never call the goal ready from tests alone; cite the real check outputs and
   runtime report path.

### /routines scan <category>

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

### /routines ops <verb>

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

### /routines <engine-verb>

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
- `registry` / `manifest` -> alias of `list` (declared routines / schedule manifest)
- `history` -> alias of `status` (ledger-derived run history)
- `pending [--create-adr]` -> show pending escalations (also `aug routine pending-escalations`)

Execution: dispatch the verb and its arguments to `adaptive_loop_executor.py`.

## Alias Window

`/dream` remains available during the ADR-758 transition period.
New automation and operator workflows should use `/routines`.
