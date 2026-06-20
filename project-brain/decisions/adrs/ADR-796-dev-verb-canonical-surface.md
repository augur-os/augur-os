---
status: Implemented
date: 2026-06-04
deciders:
  - gsannikov
related:
  - ADR-601
  - ADR-770
  - ADR-741
hub: dev
tags:
  - commands
  - dev
  - surface-consolidation
  - documentation-drift
  - drift-guard
superseded_by: null
spec_file: null
plan_file: null
---

# ADR-796: `/dev <verb>` is the single canonical dev-command surface; standalone `/dev-*` aliases are retired

## Decision summary

The unified router `/dev <verb>` (build, merge, release, sync, debug, clean,
eval) is the **only** invokable dev-command surface. The standalone
`/dev-build`, `/dev-merge`, `/dev-debug`, `/dev-clean` aliases are retired: they
remain on disk **only** as dispatch-body files that the `/dev` router reads, and
must never be advertised, registered, or referenced as independent slash
commands. Every authoritative reference (CLAUDE.md, the platform-admin SKILL.md
command catalog, command-matrix docs) expresses these operations in `/dev <verb>`
form. The retirement is a **hard cut** (no transition-alias window), made safe by
auditing literal invocations first (M1) and kept from recurring by a **drift
guard** that extends the ADR-741 catalog audit.

The per-client generated copies of the body files (`.claude/agents/dev-*.md`,
`.codex/`, `.gemini/`, `.antigravity/`, `plugins/`) are the ADR-601/ADR-770
projection model working as designed and are **not** duplication to be removed —
they are regenerated outputs of the single source body.

## Context

The user invokes only `/dev <verb>`. Inspecting the tree surfaced an
inconsistency: the dev operations are exposed through **two** nominal surfaces.

What is already consolidated (the invokable layer):

- `.claude/commands/` exports exactly one dev command: `dev.md` (the router).
- All four alias body files carry `x-augur-export-command: false`; only
  `dev.md` carries `true`. So `/dev-build`, `/dev-merge`, `/dev-debug`,
  `/dev-clean` are **not** registered as invokable slash commands today.
- `dev.md` dispatches **by file path** (its table points at
  `commands/dev-build.md`, `commands/dev-merge.md`, …), not by re-invoking a
  command. The body files are therefore required as dispatch targets.

What still drifts (the advertisement layer) — the "mass and duplication" the
user observed:

1. **Catalog registration.** `project-brain/capabilities/skills/platform-admin/SKILL.md`
   still lists `dev-build`, `dev-clean`, `dev-debug`, `dev-merge` as
   `x-augur-commands` entries (`type: workflow`, `visibility: dev`). This is the
   source that re-advertises them as first-class commands downstream.
2. **CLAUDE.md.** The "Dev (7)" list (line ~204), the development-commands table
   (lines ~167/173/174), the dev-server note (line ~77), and rules 25/26/29 all
   name the standalone `/dev-*` forms.
3. **Docs/specs.** Reference counts in tracked source: `/dev-build` 53,
   `/dev-merge` 39, `/dev-debug` 15, `/dev-clean` 11 — most are dated design
   specs under `docs/superpowers/specs/` (historical record).

No ADR ever formally retired the aliases, so the catalog and instructions kept
treating them as live. The body files are still actively maintained (latest
`dev-merge.md` commit 2026-05-31), which is correct — they are the
implementation bodies, not separate commands.

## Decision

1. **Canonical surface.** `/dev <verb>` is the sole invokable dev-command
   surface. `dev.md` (`x-augur-export-command: true`) is the only exported dev
   command.
2. **Bodies, not commands.** `dev-build.md`, `dev-merge.md`, `dev-debug.md`,
   `dev-clean.md` (and `ai/commands/dev-sync.md`) remain on disk as router
   dispatch bodies. They keep `x-augur-export-command: false` and are never
   re-registered as standalone commands.
3. **Catalog reconciliation.** Remove the standalone `dev-build`, `dev-clean`,
   `dev-debug`, `dev-merge` entries from the platform-admin SKILL.md
   `x-augur-commands` block (or convert them to a non-command body marker if the
   schema requires the id to resolve a body). The router `dev` entry stays.
4. **Instruction reconciliation.** Rewrite every authoritative reference to the
   `/dev <verb>` form: CLAUDE.md "Dev (7)" list, the dev-commands table, the
   dev-server note, and rules 25/26/29 (e.g. "Full dev-merge covers vault" →
   "`/dev merge full` …"; "use `/dev-build`" → "use `/dev build`").
5. **Historical specs untouched.** Dated design docs under
   `docs/superpowers/specs/` are a historical record and are **not** rewritten;
   they describe decisions as made at the time. Only live/authoritative surfaces
   change.
6. **Generated outputs.** No generated client file is hand-edited. After the
   source changes, regeneration (sync_agents) is the mechanism that propagates;
   the per-client body copies legitimately persist because the router needs them.
7. **Drift guard (the durable fix).** Extend the ADR-741 `check-resolvable`
   catalog audit with one rule: a command `id` that is registered in
   `x-augur-commands`, carries `x-augur-export-command: false`, **and** is
   shadowed by a `/dev` router verb is a *retired-alias-still-advertised*
   finding and fails the check. This reuses existing audit infrastructure (no
   bespoke lint) and makes the exact drift that produced this ADR impossible to
   reintroduce silently. The audit also enumerates the M3 blast radius.

## Alternatives considered

- **Keep both surfaces intentionally** (status quo). Rejected: this *is* the
  state that produced the confusion — a catalog advertising commands that are
  not invokable. It satisfies none of the stated goals.
- **Reverse the direction** — promote the standalones, drop the router.
  Rejected: the export flags, the single `.claude/commands/dev.md` export, and
  actual usage already point at the router; reversing is a larger migration
  against the grain for no benefit.
- **Transition-alias window** — route `/dev-merge` to `/dev merge` with a
  "deprecated" notice for one release, then remove. Rejected: for a
  single-operator system, fix-forward is cheaper than maintaining two live
  surfaces across a deprecation window; the M3 audit already de-risks the hard
  cut.
- **Guard only, no cut** — add the lint, leave the catalog entries. Rejected:
  leaves the catalog/instruction lie in place; fails goals 1 and 2.
- **Inline all verb bodies into `dev.md`** to reduce file count. Rejected: the
  bodies are ~15KB each; inlining yields a 60–80KB router that is harder to read,
  edit, and hold in context — worse on the maintenance goal it tries to serve.

## Consequences

- One surface to learn, document, and eval. CLAUDE.md and the command catalog
  stop advertising commands that are not invokable.
- The catalog/instructions match the already-true export reality; the
  registration/export mismatch is removed.
- Rules 25, 26, 29 keep identical behavior — only the spelling of the command
  changes (`/dev-merge` → `/dev merge`). Hooks that pattern-match command text
  must be checked (see Verification) so a rule-29/36 guard does not key off the
  retired spelling.
- Body files stay maintained exactly as today; no implementation moves.
- Risk: if any automation, hook, or auto-loop literally shells `/dev-build` /
  `/dev-merge` as a registered command rather than reading the body, it must be
  repointed to `/dev <verb>`. The migration step (M1) audits this before any
  source edit lands.

## Migration plan

Listed in execution order; the audit gates the edits. Each step is
independently verifiable.

- **M1 — Behavior audit / blast radius (hard precondition).** Before any source
  edit: `rg` for `/dev-build`, `/dev-merge`, `/dev-debug`, `/dev-clean` across
  `config/`, hooks (`.claude/settings*.json`, `.githooks/`, hook scripts),
  `scripts/`, and auto-loop definitions. Classify each hit as a *doc mention*
  (safe) or a *literal command invocation* (must be repointed to `/dev <verb>`
  before the cut, or it breaks). Rule-29/36 PreToolUse guard patterns matching
  the old spelling are inventoried here. M2 does not start until the
  literal-invocation set is empty or repointed.
- **M2 — Catalog (source of advertisement).** Edit
  `project-brain/capabilities/skills/platform-admin/SKILL.md`: drop the four
  alias `x-augur-commands` entries; fix the command-matrix lines (~356, ~388)
  and the rollback note (~310) to `/dev merge`. Keep `dev` and the body-file
  links.
- **M3 — CLAUDE.md (load-bearing instructions).** Rewrite lines ~77, ~167,
  ~173, ~174, ~204 and rules 25/26/29 to `/dev <verb>` form. This is the
  generated projection of `project-brain/*` — edit the brain source, not the
  generated CLAUDE.md, then regenerate.
- **M4 — Drift guard.** Extend the ADR-741 `check-resolvable` audit with the
  retired-alias-still-advertised rule (Decision 7) plus a fixture/test proving
  a re-added alias entry fails the check. This is what makes the cleanup stick.
- **M5 — Regenerate.** Run the sanctioned sync (sync_agents / `/dev sync`) so
  every client's generated `dev.md`/agent bodies refresh from source. Do not
  hand-edit generated dirs (`.claude/agents`, `.codex`, `.gemini`,
  `.antigravity`, `plugins`, `build`).
- **M6 — Verify** (see below), then commit through `/dev merge`.

Out of scope: historical `docs/superpowers/specs/*` (left as-is per Decision 5);
the `.worktrees/fast-launch-onboarding/` copy (session-owned, rule 24).

## Verification

- `/dev`, `/dev build`, `/dev merge`, `/dev debug`, `/dev clean` all still
  resolve and run their existing bodies (real run, not a help dump).
- `.claude/commands/` still exports exactly one dev command (`dev.md`); no
  `dev-build.md`/`dev-merge.md` appears as an invokable command anywhere.
- `/commands` and the regenerated CLAUDE.md "Dev" list show `/dev` (+ routine
  surfaces) and **no** standalone `/dev-*` entries.
- `rg '/dev-(build|merge|debug|clean)'` returns only historical specs and
  generated body filenames — zero authoritative instruction or catalog hits.
- A rule-29 scenario (dashboard in a bad state) still routes correctly when the
  instruction says `/dev build` / `/dev debug`; the hook guard does not break.
- The extended ADR-741 audit passes on the cleaned tree, and a deliberately
  re-added alias `x-augur-commands` entry makes it **fail** (proves the guard
  actually guards, not just runs green).

## M1 audit result

Swept config/, scripts/, .githooks/, .claude/settings*.json for `/dev-(build|merge|debug|clean)`.
All hits are doc/reason-strings; zero literal command invocations — hard cut is safe.

- `.githooks/dashboard-shortcut-staged-scan.sh:4` — doc (comment: describes what the hook blocks, names /dev-build as the sanctioned alternative)
- `.githooks/dashboard-shortcut-staged-scan.sh:45` — doc (comment referencing dev-merge body path in example file list)
- `.githooks/dashboard-shortcut-staged-scan.sh:97` — doc (comment: instructs agents to use /dev-build instead)
- `.githooks/dashboard-shortcut-staged-scan.sh:101` — doc (comment: "Use /dev-build to rebuild and /dev-debug to diagnose")
- `.githooks/pre-commit:111` — doc (comment header: "Block dev-server shortcuts that bypass /dev-build (CLAUDE.md rule 29)")
- `scripts/hooks/dashboard-shortcut-patterns.sh:8` — doc (comment: "Always use /dev-build to rebuild and /dev-debug to diagnose")
- `scripts/hooks/dashboard-shortcut-patterns.sh:17` — doc (comment: "/dev-build owns cache cleanup")
- `scripts/hooks/dashboard-shortcut-patterns.sh:39` — doc (DSB_REASON string: human-readable message printed to the agent, not a command invocation)
- `scripts/hooks/run-hook.mjs:23` — doc (DASHBOARD_SHORTCUT_REASON string constant: human-readable message printed to the agent, not a command invocation)
- `config/dashboard/generated_surfaces.yaml:3` — doc (comment: "surfaces are regenerated by /dev-build, start-dev.sh, or …")
- `scripts/worktree-launch.sh:318` — doc (warn() call emitting human-readable message "run /dev-build before dashboard checks")

## Implementation outcome (scope broadened)

Building the drift guard against the real catalog revealed the drift was **not**
limited to the four `/dev-*` aliases — 15 commands were registered-but-not-invokable.
Investigation (per-command, evidence-backed) classified them, and the scope was
broadened with user approval:

- **13 retired** (catalog registration removed from SKILL.md + `capability_exposure.yaml`; body files kept as router dispatch targets): `dev-build`, `dev-clean`, `dev-debug`, `dev-merge`, `dev-sync` (→ `/dev`), `eval` (→ `/dev eval`), `note`, `save` (→ `/keep`), `sweep-stores` (→ `/sweep`), `ops-learn`, `ops-audit`, `ops-daemon` (→ `/routines ops …`), `routine` (→ `/routines`).
- **1 kept as a real command** (`skillify`, ADR-745): body set `x-augur-export-command: true`. It is reachable via its CLI/browse surfaces but is intentionally **not** part of the curated primary `.claude/commands` set (a tested invariant in `sync_agents/tests/test_adapter_lifecycle.py`); forcing it into that set was out of scope.
- **1 excluded from the guard** (`dream`): a tracked deprecated *routine* alias (`x-augur-deprecated`, invoked via `/routines run dream`). The guard now skips any command whose body declares `x-augur-deprecated` — intentional, tracked deprecations are not silent drift.
- **ops-daemon WIRE**: its 4-action daemon-lifecycle runbook was surfaced inline under `### /routines ops <verb>` in `daemon/commands/routines.md` so the detail is reachable post-retirement.

Drift guard (`check_resolvable.py` `_detect_retired_aliases`) result on the cleaned tree: `retired_aliases: 0` (was 14 after the dream exclusion), `stale_capability_entries: 0` (no findings converted), other categories unchanged. Generated surfaces regenerated via `sync_agents sync all`; `check` reports up to date. CLAUDE.md command lists now show Core (11) / Dev (2) / Ops (5).

Follow-up note: the authored command lists in `docs/agent-topics/WORKFLOWS.md` and the generated CLAUDE.md command lists are produced independently and can drift (observed for `/skillify` during this work). Reconciling them onto a single generated source is a candidate follow-up, not done here.
