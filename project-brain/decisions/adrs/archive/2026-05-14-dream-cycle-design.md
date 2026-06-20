---
date: 2026-05-14
status: Draft
adr: ADR-744
deciders:
  - gsannikov
related:
  - ADR-670
  - ADR-727
  - ADR-731
  - ADR-738
  - ADR-740
  - ADR-743
---

# Dream Cycle — Cross-Client Overnight Synthesis Routine — Design

> Design spec for **ADR-744**. Companion to the thin index ADR at
> `docs/adrs/ADR-744-dream-cycle-overnight-synthesis-auto-loop.md`.
> The implementation plan derived from this spec lives at
> `docs/superpowers/plans/2026-05-14-dream-cycle.md`.

## Goal

A coordinated overnight synthesis pass that compounds the second brain on a
regular cadence. Authored **once** in Augur, projected as a scheduled routine
into every supported AI client. The routine runs in the client's *own* session
on the client's *own* schedule: it calls Augur MCP tools for deterministic
phases, reasons inline for judgment phases, records every phase as a job in the
ADR-743 ledger, and emits a human-readable report. Augur owns no scheduling and
makes no LLM call — Rule #11/#19 enforced by construction.

## Dependency Sequencing — this is the capstone

ADR-744 builds directly on three slate ADRs and is implemented **last**:

- **ADR-738** — `entity-tier-recompute` and inbound-edge counts (orphan detection)
- **ADR-740** — the `## Timeline` (citation-fixing, stale detection) and the
  compiled-truth proposal flow
- **ADR-743** — the job ledger (`jobs-submit`) every phase records against

This spec is written against those ADRs' *interfaces*; implementation waits for
all three. The dream skill degrades gracefully if a dependency is absent (see
Error Handling) so partial-slate states never hard-break it.

## Non-Goals

Carried from ADR-744, reaffirmed:

- **No Augur-side scheduling.** The client's routine system owns the cron.
  `launchd` / Task Scheduler keep scheduling *other* auto-loops; the dream cycle
  specifically delegates scheduling to the client.
- **No direct LLM calls from Augur** — enforced by construction; the client runs
  the routine in its own session and owns the LLM context.
- **No autonomous destructive operations.** Orphans, dead citations, and merges
  are *proposals*; the user confirms before any delete/merge.
- **No mutation of compiled-truth without approval** (ADR-740 enforces this).
- **No replacement of existing hygiene/quality loops** — dream is additive,
  focused on knowledge compounding.
- **No cloud routine execution** — the routine runs on the user's laptop in the
  user's client session.

## Architecture

### Placement — new `dream/` skill

A dedicated `shared-vault/skills/dream/` skill (hub: command) owns the routine,
the genuinely-new `dream-*` tools, config, the report, and the cross-client
projection. It **delegates** deterministic phases to sibling tools rather than
reimplementing them — it orchestrates, it does not duplicate.

```
shared-vault/skills/dream/
  SKILL.md
  config.yaml              # phase order, retries, skips, thresholds (skill-internal)
  commands/dream.md        # the routine — projected per client
  scripts/
    __init__.py
    bootstrap_paths.py
    aggregators.py         # dream-orphans, dream-stale-pages, dream-merge-candidates
    dead_citations.py      # dream-dead-citations
    dream_report.py        # dream-report-write, dream-last-report
    cache_gc.py            # dream-cache-gc — thin delegate to `cache-control`
    dream_status.py        # dream-status — reads the ADR-743 ledger
    projection.py          # NEW sync_agents artifact class — per-client routine
    mcp/
      __init__.py          # all dream-* MCP tools + `aug dream` CLI
  augur/
    tests/
```

**Config placement:** ADR-744's body says `config/system/dream.yaml`. Dream
config (phase order, retries, skips, thresholds) is **skill-internal** — only the
dream routine reads it — so per Rule #2 it lives in the dream skill's
`config.yaml`, not central config. (Same reasoning as ADR-743's job-ledger config
and ADR-739's RRF placement.) The ADR body is corrected when `spec_file:` is
wired.

### Phases — deterministic (MCP, zero-LLM) vs judgment (inline, client's LLM)

**Deterministic phases** — the routine calls these MCP tools; no token cost:

| Phase                  | Tool                                | Owner / delegation                          |
|------------------------|-------------------------------------|---------------------------------------------|
| Orphan cleanup         | `dream-orphans`                     | dream — aggregates ADR-738 inbound edges + ADR-740 timeline counts |
| Citation fixing        | `dream-dead-citations`              | dream — scans ADR-740 timeline `_source:` URIs for dead targets    |
| Stale-cache GC         | `dream-cache-gc`                    | dream — **thin delegate** to the `cache-control` capability        |
| Entity tiering recompute | *(no dream tool)* `entity-tier-recompute` | **delegated directly** to ADR-738's graph skill — the routine calls it, dream owns no wrapper |

ADR-744's tool list named `dream-tier-recompute`; this spec corrects that — it is
a *delegation* to ADR-738's `entity-tier-recompute`, not a new dream tool.

**Judgment phases** — run inline in the client's session, no Augur LLM call:

| Phase                  | Supporting tool                     | What the client does                        |
|------------------------|-------------------------------------|---------------------------------------------|
| Compiled-truth refresh | `dream-stale-pages`                 | reads recent ADR-740 timeline entries, emits a compiled-truth *proposal* (never a write) |
| Pattern extraction     | *(reads recent ingestions)*         | proposes new wiki seeds                      |
| Wiki concept merging   | `dream-merge-candidates`            | reviews high-similarity pairs (delegates similarity to ingest's `wiki_concept_merge`), proposes merges |

### The routine — `commands/dream.md`

A multi-step prompt: deterministic-phase MCP calls interleaved with inline
judgment prompts. Authored once. Every phase wraps its work in `jobs-submit`
(ADR-743) so phase start / heartbeat / completion land in the ledger. Phase
order, retries, and skips come from the dream skill's `config.yaml`. A
deterministic phase failing does **not** block subsequent deterministic phases.

### Cross-client projection — `projection.py` (the genuinely-new infrastructure)

A new `sync_agents` artifact class: **scheduled routine per client**. Follows the
existing `codex-dev-loop-schedules` precedent (`codex.py` already materializes
schedule seeds for Codex dev-loops). For each supported client, `projection.py`
writes a per-client routine artifact:

- **Codex** — a schedule-seed entry (like `codex-dev-loop-schedules.yaml`),
  auto-discovered by the Codex runtime — activates with no user step.
- **Claude Code** — the routine projected as a command/skill; activation is a
  documented one-time `/schedule` registration (sync_agents is a Python script —
  it cannot call `CronCreate`; it projects files, the user activates once).
- **Gemini** — the equivalent native routine surface, or the documented step.
- **Cursor / Copilot** — graceful degradation: a "run dream now" command the user
  fires manually (no native routine surface).

Projection is idempotent — re-running `sync_agents` updates the routine *content*;
the schedule *registration* persists. Augur projects files; it never owns the
cron and never calls a scheduling API.

## Report

`dream-report-write` consolidates phase results into
`get_documents_dir()/reports/dream/<YYYY-MM-DD>.md` — a human-readable report
linking every proposal into the user's normal proposal-review flow.
`dream-last-report` returns the most recent one. (`get_documents_dir()` resolves
to `Au-docs/`; `reports/` already exists.)

## MCP Tools

CLI-default per the surface-decision-matrix; the routine calls them in-session.

| Tool                   | Purpose                                                          |
|------------------------|------------------------------------------------------------------|
| `dream-orphans`        | Wiki pages with no inbound edges + low timeline count (flag only) |
| `dream-dead-citations` | Timeline entries whose `_source:` URI resolves to nothing        |
| `dream-stale-pages`    | Pages whose compiled truth is stale vs. recent timeline activity |
| `dream-merge-candidates` | High-similarity page pairs (delegates to ingest merge machinery) |
| `dream-cache-gc`       | Purge rebuildable caches past retention — delegates to `cache-control` |
| `dream-report-write`   | Write the consolidated dream report                              |
| `dream-last-report`    | Return the most recent dream report                              |
| `dream-status`         | Current/last dream-run status — reads the ADR-743 ledger         |
| `dream-config`         | Read/show the dream skill's `config.yaml`                        |

`config/system/capability_exposure.yaml` gains `mcp-tool:dream-*` entries.

## Error Handling

- **A deterministic phase fails** — logged, recorded `failed` in the ledger;
  subsequent deterministic phases still run (ADR: failure does not block).
- **A judgment phase produces a weak proposal** — it is a *proposal*; the user
  rejects it; no autonomous write means no harm.
- **A dependency (ADR-738/740/743) is absent** — the phase that needs it is
  skipped with a clear "requires ADR-NNN" note in the report; the dream cycle is
  resilient to partial-slate state and never hard-breaks.
- **The client has no native routine surface** — graceful degradation to a manual
  "run dream now" command (Cursor / Copilot).
- **`dream-report-write` fails** — logged; the run's ledger still carries every
  phase result, so the run is not lost.
- **The routine is interrupted mid-run** — the ADR-743 ledger's supervisor marks
  the orphaned job; the next run starts fresh (no side-effect replay).

## Testing Strategy

Tests live in `shared-vault/skills/dream/augur/tests/`, imported via
`importlib.util.spec_from_file_location` per the Augur skill-test convention.
TDD per the writing-plans skill — one focused test file per unit:

- `test_aggregators.py` — `dream-orphans` / `dream-stale-pages` /
  `dream-merge-candidates` against fixture vaults; flag-only, never deletes
- `test_dead_citations.py` — dead `source-card://` / `vault://` / `graph://` URI
  detection over fixture timeline entries
- `test_dream_report.py` — report rendering, `dream-report-write` /
  `dream-last-report`, proposal links
- `test_dream_status.py` — reads the ADR-743 ledger correctly; handles a missing
  ledger gracefully
- `test_projection.py` — per-client artifact generation: a Codex schedule-seed
  entry, a Claude Code routine doc, graceful degradation for a client with no
  routine surface; idempotent re-projection

## Implementation Order

ADR-744 is implemented **after** ADR-738/740/743 land.

1. **Skill scaffold** — `SKILL.md`, `config.yaml`, `bootstrap_paths.py`, the
   directory tree.
2. **Aggregators** — `aggregators.py` (`dream-orphans`, `dream-stale-pages`,
   `dream-merge-candidates`) and `dead_citations.py` (`dream-dead-citations`).
3. **Report** — `dream_report.py` (`dream-report-write`, `dream-last-report`).
4. **Status + config + cache-gc** — `dream_status.py` (ledger read),
   `dream-config`, `cache_gc.py` (delegate to `cache-control`).
5. **MCP tools + CLI** — wire every `dream-*` tool + `aug dream` +
   `capability_exposure.yaml` entries.
6. **The routine doc** — `commands/dream.md`: deterministic phase calls + inline
   judgment prompts, each phase wrapped in `jobs-submit`.
7. **Cross-client projection** — `projection.py` + the new `sync_agents` artifact
   class + per-client adapters (Codex seed, Claude Code routine doc, graceful
   degradation).
8. **Docs** — `docs/architecture-daemon.md` gains a "compounding routines"
   section distinguishing Augur-scheduled auto-loops from client-scheduled
   routines; regenerate agent instructions; correct the ADR-744 body
   (`config/system/dream.yaml` → skill-local; `dream-tier-recompute` → delegation).

Phases 1–5 are a sequential pipeline. Phase 6 needs the tools from 2–5. Phase 7
is the novel projection infrastructure. Phase 8 is docs + the ADR body correction.

## Consequences

- New `shared-vault/skills/dream/` skill — routine, `dream-*` tools, config,
  report, and the cross-client projection.
- `sync_agents` gains a new artifact class: **scheduled routine per client** —
  the daemon's role for dream shrinks to MCP entry points + ledger; no
  daemon-side scheduling logic for dream.
- New report directory `get_documents_dir()/reports/dream/`.
- `architecture-daemon.md` gains a "compounding routines" section.
- The dream cycle delegates: tier-recompute → ADR-738 graph, concept-merge →
  ingest, cache-gc → `cache-control`. It orchestrates; it owns only the routine,
  the genuinely-new aggregator/report/status/projection logic, and its config.
- Cross-client parity by construction: a new client routine feature works under
  the dream cycle as soon as `projection.py` gets that client's adapter.
- ADR-742's eval harness can A/B compare retrieval before/after dream cycles.
- ADR-744's body is corrected: `config/system/dream.yaml` is skill-local config,
  and `dream-tier-recompute` is a delegation to ADR-738, not a new tool.
