# Scheduled Agent Observability Design

**Date:** 2026-04-12
**Status:** Draft
**Depends on:** `docs/references/ai-client-execution-model.md`, `docs/references/agent-vs-mcp-checklist.md`

## Summary

Augur should become the observability surface for scheduled agent work across multiple AI clients without becoming the scheduler itself. Native scheduling remains in each client app where supported. Augur reads or imports those schedules, normalizes them into one entity shape, and exposes them in Browse with source tags, runtime metadata, and a detail panel for the full prompt and raw schedule fields.

Phase 1 focuses on read-only observability. It must support:

- `augur-internal` schedules and schedulable commands
- `codex` native automations
- `claude` native scheduled tasks

The system must show both native client schedules and Augur-owned internal schedules in the same browse surface while making ownership explicit.

## Goals

- Show scheduled agent executions from multiple sources in one browse surface.
- Preserve clear source ownership via tags such as `augur-internal`, `codex`, and `claude`.
- Support a compact table view with a detail panel for full prompt and raw metadata.
- Normalize native client schedules into one consistent entity shape.
- Make `dev-loops` migration visible loop-by-loop instead of as one opaque nightly job.

## Non-Goals

- Replacing native client schedulers in phase 1.
- Building schedule editing or migration actions in phase 1.
- Making Augur the control plane for moving schedules between agents in phase 1.
- Supporting every external client on day one. `cowork` and `minimax` remain schema-ready in phase 1, with adapters added in subsequent work.

## Product Shape

Augur gains a new browse entity type:

- `scheduled-executions`

Each row represents one observed or declared scheduled agent execution.

There are two high-level kinds:

- `native-schedule` — the schedule is owned by a client app such as Codex or Claude
- `internal-schedule` — Augur knows this command or loop is schedulable or currently internally triggered

There are three source families:

- `augur-internal`
- `native-client`
- `external-client`

Phase 1 uses these concrete sources:

- `augur-internal`
- `codex`
- `claude`

Future sources:

- `cowork`
- `minimax`

## Browse UX

### Table View

The main browse table stays compact and scan-friendly.

Each row shows:

- `title`
- `source`
- `schedule`
- `workspace`
- `status`
- `last_run_at`
- `next_run_at`

`source` is rendered as a visible tag:

- `augur-internal`
- `codex`
- `claude`
- additional sources when their adapters land, including `cowork` and `minimax`

### Detail Panel

Selecting a row opens a detail panel rather than expanding prompt text inline.

The detail panel shows:

- full prompt or command body
- raw native schedule field
- normalized human schedule summary
- source file path or native identifier
- model / agent / client metadata
- runtime metadata such as `last_run_at` and `next_run_at` when available
- warnings when schedule interpretation is uncertain

Examples of raw schedule fields:

- Codex: `rrule`
- Claude: `cronExpression`
- Augur internal: `trigger`, `nightly`, `continuous`, or command-level schedule metadata

## Normalized Entity Model

Each schedule row is normalized into one record shape.

```json
{
  "id": "claude:claude-second-brain-report",
  "title": "Claude Second Brain Report",
  "source": "claude",
  "kind": "native-schedule",
  "workspace": "~/Projects/Augur",
  "status": "active",
  "schedule_human": "Every Friday at 16:00 (raw value, timezone unverified)",
  "raw_schedule": {
    "type": "cron",
    "value": "0 16 * * 5"
  },
  "prompt_summary": "Run /wiki report --style demo",
  "prompt_body": "In the Augur repo, run `/wiki report --style demo` ...",
  "native_id": "claude-second-brain-report",
  "source_path": "~/Documents/Claude/Scheduled/claude-second-brain-report/SKILL.md",
  "model": "claude-opus-4-6",
  "last_run_at": null,
  "next_run_at": null,
  "warnings": [
    "Claude schedule interpretation is provisional until timezone semantics are verified."
  ]
}
```

Required fields:

- `id`
- `title`
- `source`
- `kind`
- `status`
- `prompt_summary`

Preferred when available:

- `workspace`
- `schedule_human`
- `raw_schedule`
- `prompt_body`
- `native_id`
- `source_path`
- `model`
- `last_run_at`
- `next_run_at`
- `warnings`

## Source Adapters

Phase 1 uses per-source adapters rather than one generic parser.

### Augur Internal Adapter

Purpose:

- expose commands and loop families that Augur currently owns or knows are schedulable
- surface legacy internal scheduling clearly during migration

Inputs:

- `skills/daemon/commands/dev-loops.md`
- daemon loop metadata from `SKILL.md` frontmatter and related command docs
- adaptive loop reports and journal under `get_runtime_dir()/adaptive/`
- existing daemon/task config where still relevant

Output behavior:

- emits `internal-schedule` rows
- can emit rows even if no external client owns the schedule yet
- includes observed runtime metadata when available from Augur logs or reports

### Codex Adapter

Purpose:

- expose native Codex automations with strong runtime metadata

Inputs:

- `~/.codex/automations/*/automation.toml`
- `~/.codex/sqlite/codex-dev.db`

Observed fields already available:

- `id`
- `name`
- `prompt`
- `status`
- `rrule`
- `cwds`
- `model`
- `reasoning_effort`
- `last_run_at`
- `next_run_at`

Output behavior:

- emits `native-schedule` rows
- considered strong / fully observed when both config and runtime state exist

### Claude Adapter

Purpose:

- expose native Claude scheduled tasks and their prompt files

Inputs:

- `~/Library/Application Support/Claude/local-agent-mode-sessions/**/scheduled-tasks.json`
- referenced task prompt files such as `~/Documents/Claude/Scheduled/<task>/SKILL.md`

Observed fields already available:

- `id`
- `cronExpression`
- `enabled`
- `filePath`
- `createdAt`
- `model`
- `userSelectedFolders`
- prompt body from the linked `SKILL.md`

Output behavior:

- emits `native-schedule` rows
- marks schedule interpretation as provisional until the cron/timezone mapping is verified against the Claude UI and actual runtime behavior

### Future Adapters

Schema-ready but not required in phase 1:

- `cowork`
- `minimax`

The browse model must not require schema changes to add these later.

## Concrete Examples

### Codex Example

`Update AGENTS.md` should appear as:

- `source=codex`
- `kind=native-schedule`
- prompt from Codex automation
- runtime timestamps from Codex DB

### Claude Example

`claude-second-brain-report` should appear as:

- `source=claude`
- `kind=native-schedule`
- prompt body from the Claude `SKILL.md`
- raw schedule from Claude `cronExpression`
- warning shown until schedule/timezone semantics are verified

### Augur Internal Example

Legacy `dev-loops nightly` should initially appear as:

- `source=augur-internal`
- `kind=internal-schedule`
- command metadata from Augur docs/config
- recent observed activity from adaptive journal/reports

This row is transitional and is removed for `dev-loops` once the loop family is fully migrated to split Codex jobs.

## `dev-loops` Migration Strategy

Do not migrate `/dev-loops run --all` as one native scheduled job.

That job is too opaque, too large in blast radius, and too hard to attribute when a run fails.

### Keep Separate Operational Classes

These are not part of the split nightly Codex migration:

- `self-heal` — continuous / frequent
- `command-evolution` — post-execution

### Split Nightly Loops into Separate Native Jobs

Each loop category becomes its own Codex-native scheduled execution:

- `testing`
- `code-quality`
- `hardening`
- `knowledge-enrichment`
- `skill-standards`
- `skill-quality`
- `observability`
- `duplication`
- `ui-quality`

### Recommended Weekly Cadence

- Sunday: `testing`
- Monday: `code-quality`
- Tuesday: `hardening`
- Wednesday: `knowledge-enrichment`
- Thursday: `skill-standards`
- Friday: `skill-quality`
- Saturday: `observability`, `duplication`, `ui-quality`

Benefits:

- easier failure attribution
- smaller execution surfaces
- easier loop-by-loop migration
- mixed ownership is visible in Browse during transition
- avoids one opaque "nightly everything" job

## Legacy Scheduling Policy

`augur-internal` remains a supported source type after the migration.

However:

- the legacy internal nightly path is retired specifically for `dev-loops`
- `dev-loops` nightly ownership moves to split Codex-native schedules
- other non-`dev-loops` internal schedules may remain supported and visible as `augur-internal`

This keeps the platform flexible without keeping `dev-loops` on a legacy nightly trigger.

## Migration Phases

### Phase 1: Observability

- add unified browse entity and UI
- ship adapters for `augur-internal`, `codex`, and `claude`
- show mixed ownership clearly
- no scheduling ownership change required to ship phase 1

### Phase 2: Loop-by-Loop Migration

- create separate Codex-native jobs for each split `dev-loops` nightly category
- mark migrated loop rows as `source=codex`
- retain legacy internal rows only for still-internal non-`dev-loops` schedules
- remove the legacy Augur nightly ownership path for `dev-loops`

## Cutover Rules

A `dev-loops` category can leave the legacy path only when Augur can observe:

- native schedule exists
- prompt or command body is readable
- workspace is known
- row appears independently in Browse
- native source metadata is sufficient for the user to inspect the schedule

Preferred but not strictly required for first cutover:

- `last_run_at`
- `next_run_at`

Codex jobs should satisfy the stronger standard with both config and runtime timestamps.

## Warning States

The UI must surface uncertainty explicitly.

Possible warning states:

- `dual-owned` — both internal and native ownership appear active for the same loop
- `configured-unverified` — native config exists but runtime verification is incomplete
- `schedule-unverified` — raw schedule found but timezone or interpretation is uncertain
- `stale-observation` — last successful adapter read is old and current source could not be refreshed

If a client adapter fails, Augur should prefer stale-but-visible rows with a warning rather than dropping the schedule from view.

## Testing

### Automated

- unit tests per adapter using real fixture shapes from Codex and Claude
- normalization tests so all adapters map into the same entity shape
- browse tests for:
  - source tags
  - compact rows
  - detail panel
  - warning states

### Manual

Verify against the known examples on this machine:

- Codex `Update AGENTS.md`
- Claude `claude-second-brain-report`
- Augur internal `dev-loops`

Manual checks:

- row appears with correct source tag
- detail panel shows full prompt or command body
- raw schedule field is visible
- workspace path is correct
- warning is shown when interpretation is uncertain

## End State

Augur becomes the observability and inspection surface for scheduled agent work across clients.

The scheduler remains native to each client where available.

`dev-loops` no longer runs as one internal nightly batch. Instead it is decomposed into separate Codex-native scheduled executions, each visible as its own row in Browse.

Legacy scheduling support stays in the platform for other internal schedules, but not for the `dev-loops` nightly family once migration is complete.
