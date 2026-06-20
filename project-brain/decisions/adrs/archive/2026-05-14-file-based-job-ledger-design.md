---
date: 2026-05-14
status: Draft
adr: ADR-743
deciders:
  - gsannikov
related:
  - ADR-744
---

# File-Based Job Ledger for Daemon Workflows — Design

> Design spec for **ADR-743**. Companion to the thin index ADR at
> `docs/adrs/ADR-743-file-based-job-ledger-for-daemon-workflows.md`.
> The implementation plan derived from this spec lives at
> `docs/superpowers/plans/2026-05-14-file-based-job-ledger.md`.

## Goal

Give every async run in Augur — adaptive loops, scheduled tasks, continuous
checks, healing cycles, and (when ADR-744 lands) client routines — a durable,
inspectable, crash-safe **run record**. A loop that dies mid-run today leaves
only log-tail heuristics; the ledger leaves an append-only `events.jsonl` that
`cat` reads end to end.

This borrows the **state-machine + crash-safe replay pattern** from gbrain's
Postgres "Minions" queue — but the Postgres dependency is rejected. The ledger
is plain files: one directory per job, one append-only JSONL of state
transitions.

## Non-Goals

Carried verbatim from ADR-743, reaffirmed:

- **No embedded database of any kind.** Plain files only. `cat events.jsonl`
  shows the entire history of a job.
- No distributed execution. Single-machine, local.
- **No replacement of launchd / Task Scheduler.** The ledger lives *below* the
  scheduler — schedulers fire runs; runs write to the ledger.
- **No replay of side effects.** Replay re-runs a loop from scratch; the ledger
  only records what happened.
- No structured query language. The ledger is grep-friendly JSONL; richer access
  is behind MCP tools, never a query engine.
- **No change to the Adaptive Loop Engine's learning state.** `runtime/adaptive/`
  (trust, difficulty, evolve queue) is orthogonal and stays exactly as it is —
  see "Relationship to the Adaptive Loop Engine".

## Relationship to the Adaptive Loop Engine

The Adaptive Loop Engine already keeps rich per-loop state under
`runtime/adaptive/`: `CategoryState` (trust, difficulty, commit verification, hot
paths, clean-scan streaks) and `LoopState` (budget, probation). That is
**learning state** — how the engine *adapts* over time.

The ledger is a different concern: a **run record** — what happened in *one*
execution, crash-safe. The two stay separate stores:

- `runtime/adaptive/` — learning state. Unchanged. The engine reads/writes it as
  it does today.
- `runtime/jobs/` — run records. New. Every executor (including the adaptive
  loop executor) emits a ledger job per run.

The adaptive engine **does not read** the ledger; the ledger **does not compute**
trust. The ledger is the single "what ran / what crashed" view *beneath* every
executor; the adaptive engine's learning loop sits *above* its own slice of that.

## Architecture

### Placement — `job_ledger/` subpackage in the `daemon` skill

The ledger is daemon infrastructure: it is consumed by the daemon's executors and
swept by the daemon's heartbeat. It lives as a focused subpackage in the `daemon`
skill (precedent: the skill's existing `adaptive/`, `monitor/`, `ops/`,
`self_heal/` subpackages). Decentralized per Rule #2 — daemon-owned config stays
in the daemon skill, not in `config/system/`.

```
shared-vault/skills/daemon/scripts/job_ledger/
  __init__.py
  job_record.py     # meta.json + events.jsonl shapes; current-state resolution
  ledger.py         # the run() context manager + state machine + append
  supervisor.py     # sweep: liveness, orphan marking, surfacing, opt-in resubmit
  retention.py      # 30-day terminal-job archive -> gzip
  mcp/
    __init__.py     # jobs-submit/list/detail/replay/cancel + `aug jobs` CLI
shared-vault/skills/daemon/augur/tests/
  test_job_record.py
  test_ledger.py
  test_supervisor.py
  test_retention.py
```

Config lives in the daemon skill's existing `config.yaml` under a `job_ledger:`
block (heartbeat threshold, retention days, resubmit allowlist) — daemon-internal
knobs, not user/skill-extensible, so not central config.

### Integration model — a context manager at each executor's dispatch point

Every executor wraps its per-run dispatch in one context manager:

```python
from job_ledger.ledger import run as ledger_run

with ledger_run(kind="loop", name="loop-hygiene", args={...}, timeout_s=600) as job:
    job.phase("scan")
    ...
    job.heartbeat()
    job.phase("fix")
    ...
# clean exit  -> appends {"state": "complete"}
# exception   -> appends {"state": "failed", ...} and RE-RAISES
```

This is the ADR's "thin wrapper" — but as ~3–4 explicit call sites (the
executors), **not** a decorator on every loop. The wrapped loop's own logic and
error handling are untouched; the context manager only *records*. Wired at:

- `adaptive_loop_executor.py` — per-loop dispatch
- `schedule_executor.py` — scheduled-task dispatch
- `continuous_executor.py` — continuous-check dispatch
- the healing cycles (`ai_self_healer.py` / `service_healer.py`) — per-heal-cycle
- ADR-744 client routines call `ledger_run` (or `jobs-submit`) directly — ADR-743
  only provides the surface; ADR-744 owns that wiring.

## Data Shapes

### `get_runtime_dir()/jobs/<job-id>/`

`<job-id>` = `<YYYYMMDD-HHMMSS-mmm>-<name-slug>` — sortable, readable, unique to
the millisecond. Example: `20260514-142233-901-loop-hygiene`.

| File            | Contents                                                                 |
|-----------------|--------------------------------------------------------------------------|
| `meta.json`     | `{job_id, kind, name, submitter, args, declared_timeout_s, created_at}`   |
| `events.jsonl`  | append-only state transitions, one JSON object per line                  |
| `output/`       | optional captured stdout/stderr per phase, when the run emits files       |

An `events.jsonl` line:

```json
{"t": "2026-05-14T14:22:34Z", "state": "running", "phase": "scan", "pid": 12345, "msg": "started"}
```

**Current state = the `state` field of the last *valid* JSONL line.** Resolution
is positional (last line wins), not timestamp-sorted — so wall-clock skew never
corrupts state resolution. Malformed lines are skipped by readers.

### State machine

```
pending ──▶ running ──▶ complete
                   ├──▶ failed
                   ├──▶ timeout
                   └──▶ cancelled
```

Terminal: `complete`, `failed`, `timeout`, `cancelled`. `pending` is written at
`__enter__` before the run starts; `running` immediately after. `phase` and
`heartbeat` events are all `state: running` with extra fields.

## The `run()` Contract

- `__enter__` — create `jobs/<job-id>/`, write `meta.json`, append `pending` then
  `running` (with `pid`). Return a `Job` handle.
- `job.phase(name)` — append `{state: running, phase: name}`.
- `job.heartbeat()` — append `{state: running, heartbeat: true}`. Long phases
  call this on a cadence so the supervisor can tell hung from slow.
- `job.log(msg)` — append `{state: running, msg: ...}`.
- `__exit__` — no exception → append `complete`. Exception → append
  `{state: failed, error: <type>, msg: <str>}` **and re-raise**. The ledger
  records; it never swallows. The loop's own error handling is unchanged.
- **Cooperative cancel** — `job.phase()` / `job.heartbeat()` check for a
  `cancel_requested` marker (written by `jobs-cancel`); if set they raise
  `JobCancelled`, which `__exit__` records as `cancelled`. No force-kill.
- **Ledger-write failure is non-fatal** — if the ledger cannot write (disk full,
  permissions), it logs WARN and lets the run proceed un-recorded. A broken
  ledger must never break loop execution (same principle as ADR-738's "graph
  failure never breaks a write").

## Supervisor

`supervisor.sweep()` scans `jobs/` for non-terminal jobs and resolves liveness:

1. **PID-liveness first** — the last `running` event carries `pid`. If the
   process is gone and state is still non-terminal → **orphaned crash**: append
   `{state: failed, reason: "orphaned"}`.
2. **Heartbeat-lapse + declared timeout** — if the PID is alive but the last
   heartbeat is older than the configured threshold *and* the run is past its
   `declared_timeout_s` → append `{state: timeout}`. The supervisor does **not**
   force-kill a live process (no destructive ops) — it records `timeout` and
   surfaces it.
3. **Surface** — every orphaned/timed-out/stuck job emits a notification event
   through the existing daemon notification pipeline.
4. **Resubmit** — **opt-in, off by default.** A loop name in the
   `job_ledger.resubmit_allowlist` (daemon `config.yaml`) is re-dispatched once;
   everything else is surface-only. Resubmitting a broken loop in a tight cycle
   is exactly the failure mode the allowlist guards against.

A tiny race exists — the supervisor could mark `timeout` just as a slow job
writes `complete`. Resolution: last-line-wins means `complete` (written after)
correctly supersedes, and the supervisor re-checks PID liveness immediately
before appending. Acceptable and self-correcting.

`unified_daemon.py` calls `supervisor.sweep()` at startup and on its heartbeat
cadence.

## Retention

`retention.archive()` moves jobs in a terminal state older than the configured
retention window (default 30 days) to `jobs/_archive/`:

- `events.jsonl` → `jobs/_archive/<job-id>.events.jsonl.gz` (gzipped)
- `meta.json` → `jobs/_archive/<job-id>.meta.json` (kept uncompressed — small,
  grep-friendly)
- `output/` → dropped (rebuildable in extremis from logs; the ledger is the
  source of truth only while live)

Retention runs on the supervisor's cadence (a cheap mtime scan). Archived jobs
stay listable by `jobs-list --archived`.

## MCP Tools

CLI-default per the surface-decision-matrix; `jobs-list` may opt into
MCP-via-dashboard later (a `/command` hub job-inspector card).

| Tool          | Purpose                                                                |
|---------------|------------------------------------------------------------------------|
| `jobs-submit` | Register + start a job (for dispatched workflows / manual / ADR-744)   |
| `jobs-list`   | List jobs — filter by `state`, `kind`, `since`, `--archived`           |
| `jobs-detail` | Full `events.jsonl` + `meta.json` for one job id                       |
| `jobs-replay` | Re-dispatch a job's loop from scratch — new job id, no side-effect replay |
| `jobs-cancel` | Write the `cancel_requested` marker for a running job (cooperative)    |

`config/system/capability_exposure.yaml` gains `mcp-tool:jobs-*` entries.

## Error Handling

- **Ledger-write failure** — non-fatal; logs WARN, run proceeds un-recorded.
- **Corrupt `events.jsonl` line** — readers skip malformed lines; current state
  is the last *valid* line.
- **Concurrent appends** — each job has a single writer (its own process);
  append-only, no intra-job locking needed. The supervisor only appends
  supervisor-authored marks, and re-checks PID liveness immediately before doing
  so. Last-line-wins makes the rare race self-correcting.
- **Clock skew** — current-state resolution is positional (last line), never
  timestamp-sorted, so skew cannot corrupt it.
- **Missing `meta.json`** (interrupted `__enter__`) — `jobs-list` flags the job
  dir as `incomplete`; the supervisor archives it after the retention window.

## Testing Strategy

Tests live in `shared-vault/skills/daemon/augur/tests/`, imported via
`importlib.util.spec_from_file_location` per the Augur skill-test convention.
TDD per the writing-plans skill — one focused test file per unit:

- `test_job_record.py` — `meta.json`/event shapes, current-state resolution,
  corrupt-line skip, terminal-state detection
- `test_ledger.py` — the `run()` context manager: enter writes pending+running,
  `phase`/`heartbeat`/`log` append correctly, clean exit → `complete`, exception
  → `failed` + re-raise, cooperative cancel → `cancelled`, ledger-write failure
  is non-fatal
- `test_supervisor.py` — PID-gone → `failed/orphaned`, heartbeat-lapse +
  declared-timeout → `timeout`, live process is never force-killed, surfacing
  emits a notification event, resubmit only for allowlisted loops
- `test_retention.py` — terminal jobs past the window archive to gzipped JSONL,
  `meta.json` kept uncompressed, fresh jobs untouched, idempotent

## Implementation Order

A near-linear pipeline; limited parallel fan-out.

1. **Job record + ledger core** — `job_record.py` (shapes, state resolution) and
   `ledger.py` (the `run()` context manager + state machine + append).
2. **Supervisor** — `supervisor.py` (sweep, PID + heartbeat liveness, orphan
   marking, surfacing, opt-in resubmit).
3. **Retention** — `retention.py` (30-day gzip archive).
4. **MCP tools + CLI** — `jobs-submit/list/detail/replay/cancel` + `aug jobs`;
   `capability_exposure.yaml` entries; `job_ledger:` config block in the daemon
   skill's `config.yaml`.
5. **Executor integration** — wrap `adaptive_loop_executor.py`,
   `schedule_executor.py`, `continuous_executor.py`, and the healing cycles in
   `ledger_run(...)`.
6. **Daemon heartbeat wiring** — `unified_daemon.py` calls `supervisor.sweep()`
   at startup and on cadence.
7. **Docs** — `architecture-daemon.md` gains a "Job Ledger" section; regenerate
   agent instructions via `sync_agents`.

Phases 1–4 are a sequential pipeline. Phases 5–6 touch the executors and
`unified_daemon.py` (shared files) and stay sequential. Phase 7 is docs.

## Consequences

- New `runtime/jobs/` durable-state directory (off-vault, off-repo,
  platform-appropriate via `get_runtime_dir()`).
- Every async run gains a per-run inspectable, crash-safe record — `cat
  jobs/<id>/events.jsonl` is the whole story.
- The daemon's `unified_daemon` heartbeat gains a `supervisor.sweep()` call.
- The `/command` hub Browse category can later gain a job-inspector card powered
  by `jobs-list` (ADR-738/Browse pattern — rides existing file cards).
- Crash recovery has a real story: PID + heartbeat liveness, orphan marking,
  opt-in resubmit.
- **Unblocks ADR-744** — each dream-cycle phase opens a job via `jobs-submit` and
  records phase start/heartbeat/completion against the ledger.
- The Adaptive Loop Engine's learning state is untouched — the ledger is purely
  additive.
- Operates within Rule #2 (data separation): code in the daemon skill, ledger in
  the runtime dir, never in repo or vault.
