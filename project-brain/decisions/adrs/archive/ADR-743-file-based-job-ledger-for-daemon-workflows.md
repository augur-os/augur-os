---
status: Implemented
date: 2026-05-13
deciders:
  - gsannikov
related:
  - ADR-744
hub: command
tags:
  - daemon
  - jobs
  - reliability
  - autoloops
  - crash-safety
superseded_by: null
spec_file: 2026-05-14-file-based-job-ledger-design.md
plan_file: 2026-05-14-file-based-job-ledger.md
---

# ADR-743: File-Based Job Ledger for Daemon Workflows

## Status

Implemented.

## Context

Augur's `daemon` skill and the auto-loop catalog schedule work via macOS launchd / Windows Task Scheduler. Individual loop runs have logs but no **durable per-job state ledger**. A loop that crashes mid-run leaves no inspectable record of which phase it was in; restart logic depends on log-tail heuristics.

A reference implementation (gbrain) uses a Postgres-backed "Minions" queue with a `pending → running → complete | failed` state machine and crash-safe replay. The pattern is excellent; the Postgres dependency is wrong for Augur — embedded databases conflict with the **file-first, human-readable, transparent** principle that anchors Augur's vision.

## Decision

Build a **file-based** job ledger using append-only JSONL files under `get_runtime_dir()/jobs/`. The ledger gives every loop and dispatched workflow a durable, inspectable, crash-safe state record. **No SQLite. No PGLite. No embedded database.** Every state transition is a single appended JSONL line that the user can `cat` and read.

Concretely:

1. Each job has a directory `get_runtime_dir()/jobs/<job-id>/` containing:
   - `meta.json` — submitter, loop name, args, declared timeout
   - `events.jsonl` — append-only state transitions, one JSON object per line:
     ```json
     {"t": "2026-05-13T10:00:00Z", "state": "running", "phase": "scan", "pid": 12345, "msg": "started"}
     ```
   - `output/` — captured stdout/stderr per phase if the loop emits files
2. **State machine**: `pending → running → (complete | failed | timeout | cancelled)`. The *current state* of any job is the `state` field of the **last** valid JSONL line.
3. **Heartbeat**: long-running jobs append `{"state": "running", "heartbeat": true, ...}` at a configured interval. The supervisor marks jobs `timeout` when heartbeat lapses past threshold.
4. **Supervisor loop** scans `jobs/` on daemon start and on cadence, surfaces stuck/orphaned jobs, optionally resubmits per loop policy.
5. New MCP tools: `jobs-submit`, `jobs-list`, `jobs-detail`, `jobs-replay`, `jobs-cancel`. Surface defaults to CLI per surface-decision-matrix; `jobs-list` may opt in to MCP via dashboard.
6. **Retention**: jobs in terminal state older than 30 days move to `get_runtime_dir()/jobs/_archive/` as gzipped JSONL (`<job-id>.events.jsonl.gz` + `meta.json`). Archive is rebuildable from logs in extremis; ledger is the source of truth while live.
7. All loop runners get a thin wrapper that opens the ledger, writes `running`, runs the loop, writes `complete` or `failed`. Existing loops do not need to change their internal logic.

## Non-Goals

- **No embedded database of any kind.** Plain files only. The whole point is transparency: `cat events.jsonl` shows the entire history of a job.
- No distributed execution. Single-machine local.
- No replacement of launchd / Task Scheduler. The ledger lives **below** the scheduler — schedulers fire loops; loops write to the ledger.
- No replay of side effects. Replay re-runs a loop from scratch; the ledger only records what happened.
- No structured query language. The ledger is grep-friendly JSONL; richer querying lives behind MCP tools, never in a query engine.

## Consequences

- New durable state directory under `get_runtime_dir()/jobs/` (off-vault, off-repo, platform-appropriate).
- Every auto-loop gains a per-run inspectable record.
- Dashboard `/dev` browse category gains a job inspector card (powered by `jobs-list`).
- Crash recovery has a real story: supervisor reads events.jsonl tail and acts.
- Unblocks ADR-744 (dream cycle phases each become recorded ledger entries).
- Operates within Rule #2 (data separation): code in `src/`, ledger in runtime dir, never in repo or vault.

## Related

- ADR-744 (dream cycle consumes the ledger)
- daemon skill architecture (`architecture-daemon.md`)
