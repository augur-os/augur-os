# Dev-Loops Codex Migration Design

**Date:** 2026-04-12
**Status:** Draft
**Depends on:** `docs/superpowers/specs/2026-04-12-scheduled-agent-observability-design.md`, `skills/daemon/commands/dev-loops.md`, `config/system/adaptive_loops.yaml`

## Summary

Augur should stop owning scheduled `dev-loops` batch execution. After migration, the daemon keeps only fast local sensing and immediate remediation, while Codex becomes the native scheduler for every slower scheduled loop run. This includes all nightly loop families and all slower queue-drain or validation jobs. Augur remains the observability surface and later control plane.

The migration must be grounded in the live adaptive loop registry, not only in `skills/daemon/config.yaml`, because the live system currently exposes `83` auto-commands across `14` loop families while daemon config only declares a subset of those commands explicitly.

The final architecture is:

- daemon owns only:
  - fast local `self-heal`
  - event capture / queue append
- Codex owns:
  - every nightly loop family
  - every slower scheduled drain or validation job
- Augur Browse shows both daemon-local and Codex-native execution with explicit ownership

Every Codex-owned schedule in this migration program must run with `Runs in = Local`.

## Goals

- Remove daemon ownership of all nightly `dev-loops` execution.
- Remove daemon ownership of all slower scheduled drain jobs.
- Keep only fast local sensing and immediate remediation in the daemon.
- Move scheduled reasoning work to Codex-native local automations.
- Make the migration source of truth a canonical manifest derived from the live loop inventory.
- Keep `run --all` available only as a manual maintenance workflow, never as a scheduled trigger.

## Non-Goals

- Moving fast local `self-heal` sensing out of the daemon.
- Supporting remote or cloud execution for migrated loop jobs.
- Replacing Augur observability with Codex UI.
- Defining phase-two reassignment actions between clients in this design.

## Current Reality

The live adaptive loop engine currently reports:

- `83` auto-commands
- `14` loop families

Live loop families:

- `auto-agent-digest`
- `code-quality`
- `command-evolution`
- `duplication`
- `file-organizer`
- `hardening`
- `knowledge-enrichment`
- `observability`
- `page-health`
- `self-heal`
- `skill-quality`
- `skill-standards`
- `testing`
- `ui-quality`

Daemon config currently shows only part of that landscape. This means migration cannot be safely planned from daemon config alone.

## Architecture Boundary

### Daemon

The daemon remains responsible only for low-latency local behavior:

- `self-heal-fast`
  - fast runtime log scanning
  - immediate local remediation
  - local retry / backoff behavior
- event capture / queue writing
  - record command-execution events
  - append work to queues for slower downstream processing

The daemon must not own any nightly scheduled work after this migration.

The daemon must not own any slower scheduled drain jobs after this migration.

### Codex

Codex becomes the owner of all scheduled reasoning work:

- every nightly loop family
- every slower drain job
- every slower validation job

Codex jobs are native automations, observable in Augur Browse, and always run in local execution mode.

### Augur

Augur remains:

- the observability plane
- the normalized registry / manifest source
- the future control plane for reassignment and migration operations

## Local-Only Execution Requirement

Every migrated Codex schedule in this program must run locally.

Required fields for every Codex-owned unit:

- `client: codex`
- `runs_in: local`
- `workspace: ~/Projects/Augur`

Cutover is blocked if a Codex automation is created in any non-local execution mode.

This rule applies to:

- nightly jobs
- drain jobs
- validation jobs

## Loop Split Model

Migration unit is not just `loop`. It is:

- `loop + trigger + owner + cadence`

This matters because some current loop families are mixed and must be split before final cutover.

### Keep In Daemon

#### `self-heal-fast`

- owner: `daemon`
- mode: `continuous`
- purpose: immediate local healing

#### `event-capture`

- owner: `daemon`
- mode: `event-driven`
- purpose: append and maintain local work queues for slower Codex-owned jobs

### Move To Codex

#### Nightly families

- `testing`
- `code-quality`
- `hardening`
- `knowledge-enrichment-nightly`
- `skill-standards`
- `skill-quality`
- `observability`
- `duplication`
- `ui-quality`
- `auto-agent-digest`
- `file-organizer`
- `page-health`
- `self-heal-nightly-validate`

#### Non-nightly slower drains

- `command-evolution-drain`
- `knowledge-enrichment-drain`

## Mixed Loop Splits

### `self-heal`

Current logical family must become:

- `self-heal-fast`
  - daemon-owned
  - short local poll cadence
- `self-heal-nightly-validate`
  - Codex-owned
  - nightly scheduled validation

### `command-evolution`

Current logical family must become:

- daemon event capture
  - immediate queue append only
- `command-evolution-drain`
  - Codex-owned
  - scheduled queue-drain reasoning job

### `knowledge-enrichment`

Current logical family must become:

- `knowledge-enrichment-nightly`
  - Codex-owned
  - weekly/nightly scheduled maintenance
- `knowledge-enrichment-drain`
  - Codex-owned
  - scheduled queue drain / follow-up work

## Recommended Cadence Map

`weekly nightly` in this section means one local Codex automation per loop family, scheduled once per week on its assigned night. It does not mean the same loop runs every night.

### Daemon-owned

- `self-heal-fast`
  - keep current short local cadence
- event capture / queue append
  - immediate / event-driven

### Codex-owned nightly

- `testing`
  - weekly nightly
- `code-quality`
  - weekly nightly
- `hardening`
  - weekly nightly
- `knowledge-enrichment-nightly`
  - weekly nightly
- `skill-standards`
  - weekly nightly
- `skill-quality`
  - weekly nightly
- `observability`
  - weekly nightly
- `duplication`
  - weekly nightly
- `ui-quality`
  - weekly nightly
- `auto-agent-digest`
  - weekly nightly
- `file-organizer`
  - weekly nightly
- `page-health`
  - weekly nightly
- `self-heal-nightly-validate`
  - nightly

### Codex-owned non-nightly

- `command-evolution-drain`
  - every `10-15` minutes
- `knowledge-enrichment-drain`
  - hourly

These are defaults, not permanent constants. Cadence tuning happens per unit without collapsing back into `run --all`.

The implementation plan must assign an explicit local wall-clock schedule to each Codex unit. The initial recommended weekly distribution is:

- Sunday: `testing`
- Monday: `code-quality`
- Tuesday: `hardening`
- Wednesday: `knowledge-enrichment-nightly`
- Thursday: `skill-standards`
- Friday: `skill-quality`
- Saturday: `observability`, `duplication`, `ui-quality`, `auto-agent-digest`, `file-organizer`, `page-health`

`self-heal-nightly-validate` remains nightly because it is a lightweight validation pass rather than a heavier loop family batch.

## Canonical Migration Manifest

There must be one canonical manifest covering the full migration inventory. It must be generated from the live registry and then maintained as the cutover source of truth.

Each row represents one executable unit.

Required fields:

- `id`
- `loop`
- `mode`
- `source_commands`
- `current_owner`
- `target_owner`
- `client`
- `runs_in`
- `cadence`
- `workspace`
- `prompt`
- `depends_on`
- `cutover_state`
- `browse_title`

Example shape:

```yaml
- id: codex-dev-loop-hardening
  loop: hardening
  mode: nightly
  source_commands:
    - auto-page-mounts
    - auto-security-scan
    - auto-stale-paths
    - auto-code-health
  current_owner: daemon
  target_owner: codex
  client: codex
  runs_in: local
  cadence: weekly-nightly
  workspace: ~/Projects/Augur
  prompt: /dev-loops run hardening
  depends_on: []
  cutover_state: planned
  browse_title: Hardening
```

## Concrete Target Units

### Daemon-owned

- `self-heal-fast`
- `event-capture`

### Codex-owned nightly

- `codex-dev-loop-testing`
- `codex-dev-loop-code-quality`
- `codex-dev-loop-hardening`
- `codex-dev-loop-knowledge-enrichment-nightly`
- `codex-dev-loop-skill-standards`
- `codex-dev-loop-skill-quality`
- `codex-dev-loop-observability`
- `codex-dev-loop-duplication`
- `codex-dev-loop-ui-quality`
- `codex-dev-loop-auto-agent-digest`
- `codex-dev-loop-file-organizer`
- `codex-dev-loop-page-health`
- `codex-dev-loop-self-heal-validate`

### Codex-owned drains

- `codex-command-evolution-drain`
- `codex-knowledge-enrichment-drain`

## Prompt Conventions

Nightly loop prompts should remain explicit and simple:

- `/dev-loops run testing`
- `/dev-loops run code-quality`
- `/dev-loops run hardening`
- `/dev-loops run skill-standards`
- `/dev-loops run observability`

Drain prompts should express drain semantics explicitly:

- `/dev-loops run command-evolution --drain`
- `/dev-loops run knowledge-enrichment --drain`
- `/dev-loops run self-heal --validate`

`/dev-loops run --all` remains manual-only. It must never appear in the scheduled migration manifest.

## Migration Phases

### Phase 1: Inventory And Normalize

- generate the canonical manifest from the live registry
- classify every executable unit by `loop + trigger + owner + cadence`
- mark current owner and target owner

### Phase 2: Split Mixed Loops

- split `self-heal`
- split `command-evolution`
- split `knowledge-enrichment`

No final ownership migration happens until those splits are explicit.

### Phase 3: Create Codex-Native Local Schedules

Create one Codex automation for each target unit.

Every created automation must have:

- stable automation id
- local execution mode
- explicit workspace
- observable native metadata
- stable prompt

### Phase 4: Dual-Observe, Single-Execute

Before daemon ownership is removed for any unit:

- Augur Browse must show the Codex automation
- daemon skip logic must be active for that unit
- prompt / schedule / status must be readable from Browse

If both daemon and Codex still execute the same unit, the unit is `dual-owned` and cutover is blocked.

### Phase 5: Remove Daemon Nightly Ownership

Once all nightly units are Codex-observable and daemon skip logic is active:

- remove daemon nightly triggers entirely
- keep daemon only for `self-heal-fast` and event capture

## Cutover Gates

### Per-unit gate

A unit is eligible for daemon ownership removal only when:

- Codex schedule exists
- `runs_in = local`
- Browse shows `source=codex`
- prompt/body is readable
- cadence is visible
- status is visible
- daemon skip logic is active for that unit

### Global completion gate

Migration is complete only when:

- no loop with `trigger=nightly` remains daemon-owned
- no slower scheduled drain remains daemon-owned
- daemon owns only:
  - `self-heal-fast`
  - event capture / queue append

## Risks

- daemon config does not fully represent the live loop registry
- some mixed loops may hide additional trigger modes or queue semantics
- Codex drain cadence may initially be too slow for some queues
- daemon and Codex may temporarily both appear to own the same unit
- prompt drift may make a Codex job observable but behaviorally incorrect

## Failure Handling

- if a Codex job exists but is failing, do not silently return scheduled ownership to daemon
- mark the unit as `configured-unhealthy`
- if both daemon and Codex are active for one unit, mark `dual-owned`
- if a drain cadence is too slow, tune that unit rather than reintroducing `run --all`
- if a loop family lacks a stable split boundary, keep it `cutover_state=blocked`

## Success Criteria

- daemon owns no nightly jobs
- daemon owns no slower scheduled drain jobs
- daemon owns only fast local continuous behavior and event capture
- every Codex-owned unit appears in Browse with:
  - source
  - schedule
  - status
  - prompt/body
  - workspace
  - local execution semantics
- `run --all` is manual-only
- one canonical migration manifest covers the full live loop inventory
