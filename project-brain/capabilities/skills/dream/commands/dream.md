---
description: "[DEPRECATED - use /routines run dream] Alias for the cross-client overnight synthesis routine during the ADR-758 transition."
visibility: user
x-augur-export-command: false
x-augur-deprecated: true
x-augur-deprecated-in-favor-of: routines
---

# /dream

> **Retired primary surface:** `/dream` is no longer exported to primary AI
> clients. Use `/routines run dream` instead.

**DEPRECATED legacy alias** - use `/routines run dream` for new workflows.
This source doc remains for history and non-primary routing during the ADR-758
transition.

Augur's **Dream Cycle** — a coordinated overnight pass that compounds the
second brain on a regular cadence (ADR-744). Authored once in Augur,
projected as a scheduled routine into every supported AI client by
`sync_agents`. Augur owns no scheduling and makes no LLM call — Rule
#11/#19 enforced by construction.

The routine alternates **deterministic MCP calls** (zero LLM cost) with
**inline judgment** (no Augur LLM call; the client reasons in its own
session). Every phase opens a job against the ADR-743 ledger. Failure of one
deterministic phase does **not** block subsequent deterministic phases.

## Phase 0 — Open the run

Submit one umbrella job against the ADR-743 ledger:

```
jobs-submit kind=dream name=dream-cycle
```

Capture the returned `job_id`; pass it forward so every per-phase emission
ties back to one run. Heartbeat the job between phases.

## Phase 1 — Orphan candidates (deterministic)

```
dream-orphans
```

Records flagged pages: zero inbound graph edges (ADR-738) AND fewer than
`max_timeline_entries` timeline entries (ADR-740). Flag-only — never deletes.
Surface counts to the phase result; the user (or a later judgment phase)
decides whether to merge, prune, or leave alone.

## Phase 2 — Dead citations (deterministic)

```
dream-dead-citations
```

Records timeline `_source:` URIs that resolve to nothing across the three
schemes (`vault://`, `source-card://`, `graph://`). Flag-only. The user
typically fixes these by editing the citing page's timeline or by re-running
ingest to recompute the URI.

## Phase 3 — Cache GC (deterministic)

```
dream-cache-gc
```

Filesystem GC of rebuildable index caches under `get_cache_dir()` past the
retention threshold (skill-local `config.yaml: cache_gc.retention_days`,
default 30 days). Allowlist-scoped — never walks the whole cache root.

## Phase 4 — Entity-tier recompute (deterministic, **delegated**)

```
entity-tier-recompute
```

This is **ADR-738's** tool — not a dream tool. The routine calls it directly;
dream owns no wrapper. Recomputes `_entity_tier` across every entity in the
graph cache.

## Phase 5 — Compiled-truth refresh (judgment, inline)

```
dream-stale-pages
```

Returns pages whose compiled truth lags the newest timeline `_at:`. For each
flagged page, the client reads recent timeline entries via the `wiki-*` MCP
tools and **proposes** an updated compiled-truth section. ADR-740 forbids
automatic compiled-truth writes — a proposal is the *only* legitimate output.

## Phase 6 — Pattern extraction (judgment, inline)

The client surveys recent ingestions (via `wiki-*` and the source-card
listing) and proposes **new wiki seeds** for concepts that have surfaced
multiple times without their own page. No deterministic tool here; the
proposal is a list of seed slugs + one-line motivations.

## Phase 7 — Wiki concept merging (judgment, inline)

```
dream-merge-candidates
```

Returns high-similarity wiki page pairs (similarity delegated to ingest's
`wiki_concept_merge` predicate). For each pair, the client reviews and
proposes a merge (or rejects). The merge itself goes through the user's
normal proposal-review flow — never autonomous.

## Phase 8 — Write the report

```
dream-report-write --phase-results-json '<consolidated phase results>'
```

Consolidates every phase's result (counts, flagged items, proposals, errors)
into `<documents>/reports/dream/<YYYY-MM-DD>.md`. Idempotent within a day —
re-running overwrites.

## Phase 9 — Close the run

Mark the umbrella job complete in the ADR-743 ledger. Print the report path
so the user can open it.

```
dream-status
```

Shows the just-completed run + a bounded history of prior runs.

## Failure handling

- **A deterministic phase fails** — log to the run's phase results with
  state `failed` and the error string; continue with the next phase. The
  report renders the failed phase with its error so nothing is hidden.
- **A judgment phase produces a weak proposal** — fine; the proposal is
  human-reviewed and rejected, no harm.
- **The routine is interrupted mid-run** — the ADR-743 supervisor marks the
  orphaned job; the next run starts fresh.

## Activation

The routine is **client-scheduled**, not Augur-scheduled:

- **Codex** — auto-activated from
  `project-brain/capabilities/skills/dream/assets/seeds/routine-schedule.yaml`
  (the Codex adapter materializes it during `sync_agents sync agents all`).
- **Claude Code** — one-time `/schedule /dream` after `sync_agents` projects
  the slash command.
- **Gemini / other clients with a native routine surface** — equivalent
  one-time registration.
- **Cursor / Copilot** — no native routine surface; run `/dream` manually
  when desired (graceful degradation).

Augur never calls a scheduling API. The client's own scheduling surface
owns the cron.
