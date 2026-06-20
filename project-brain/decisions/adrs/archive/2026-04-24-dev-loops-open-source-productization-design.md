---
title: Dev-Loops Open Source Productization Design
date: 2026-04-24
status: proposed
approach: release-gate-productization
---

# Dev-Loops Open Source Productization Design

## Summary

Dev-loops should be productized against a fresh open-source install, not a maintainer machine that already has Augur state, generated client exports, and a configured private vault.

The release goal is simple: a new user can clone Augur, bootstrap it, configure or create a vault, and run `/dev-loops` without private path warnings, generated-client noise, destructive git behavior, or advertised commands that do nothing.

This design uses a release gate as the organizing model. Each blocker below is ranked by whether it prevents dev-loops from safely maintaining a new user's project and vault after open-source release.

## Scope

This productization pass covers:

- `/dev-loops` CLI behavior and help surface
- adaptive loop discovery and registry output
- Codex/native schedule manifest truthfulness
- daemon versus Codex ownership reporting
- repo and vault maintenance loops
- fresh-install path handling
- destructive rollback safety
- release smoke verification

This pass does not implement dashboard UI polish or a new scheduler control plane. It can expose existing health data in clearer text output, but the primary deliverable is a safe and truthful command/runtime surface.

## Open Source Release Gate

A fresh open-source install passes when:

1. `python skills/daemon/scripts/adaptive_loop_executor.py status` runs without private-path warnings or generated-client missing-module noise.
2. `python skills/daemon/scripts/adaptive_loop_executor.py registry` reports the real loop inventory from canonical skill sources only.
3. `python skills/daemon/scripts/adaptive_loop_executor.py manifest` reports local Codex/native schedule units with accurate owner and cutover state.
4. `python skills/daemon/scripts/adaptive_loop_executor.py report --days 1` works before any historical journal exists.
5. A missing vault is treated as first-run setup state, not as a broken maintainer machine.
6. Repo/vault loops use `src.config.paths` helpers and the configured project root, not private path assumptions or directory-name guesses.
7. Dev-loops does not run `git reset --hard`, broad `git checkout -- .`, or any equivalent destructive cleanup against user work.
8. Every public `/dev-loops` subcommand either performs useful work or is hidden from the public help/usage table.
9. A focused smoke test proves the above in a temporary clone fixture with no generated client exports and no existing vault.

## Ranked Fix List

### 1. Stop Scanning Generated Client Export Directories

Failure mode: fresh or maintainer checkouts with `.gemini/skills`, `.opencode/skills`, or `.codex/skills` exports produce pages of missing-module warnings before `status` and `registry` output. Generated client exports are packaging surfaces, not canonical loop source.

Fix shape:

- Add a canonical loop-source discovery helper that returns repo `skills/` plus active vault user skills when appropriate.
- Keep `get_all_client_skill_dirs()` for Browse and cross-client inventory, but do not use it for adaptive loop callable discovery.
- Update adaptive discovery tests so generated local client exports can exist without being loaded as loop modules.

Verification:

- Create temporary `.gemini/skills` and `.opencode/skills` generated wrappers with callable paths that do not exist.
- Run `registry` and assert no missing-module warnings from generated export directories.
- Assert the expected loop count still comes from repo skills.

### 2. Make Scheduler Ownership Truthful And Actionable

Failure mode: current output says nightly loops are daemon-owned while migration artifacts say Codex/native schedules are planned. New users cannot tell whether dev-loops is actually maintaining anything on schedule.

Fix shape:

- Define one source of truth for schedule ownership and cutover state.
- Keep daemon-owned continuous `self-heal-fast`.
- Mark slow nightly/drain jobs as one of `not-installed`, `installed`, `active`, or `disabled`, based on real local automation state where available.
- Update `status` and `manifest` so owner/cutover fields do not claim daemon ownership for jobs intended to run through Codex/native schedules.

Verification:

- Unit-test manifest rows for `runs_in: local`, owner, mode, and cutover state.
- Smoke-test `status` with no installed schedules and with a fixture installed schedule.

### 3. Replace Public Stub Commands With Real Operations Or Hide Them

Failure mode: `/dev-loops enable`, `disable`, `configure`, `promote`, `diagnose`, `history`, and `reset` are in public usage but print `Not yet implemented`. That is not acceptable for an open-source maintenance tool.

Fix shape:

- Implement low-risk state commands first:
  - `enable <loop>`
  - `disable <loop>`
  - `configure <loop> --budget N`
  - `history [loop]`
  - `reset <loop>`
- Hide or mark design-gated commands that need more semantics:
  - `promote`
  - `diagnose --fix`
- Ensure `--help` remains non-executing.

Verification:

- CLI tests for each implemented command against a temporary runtime dir.
- Help/usage snapshot test that no public command prints `Not yet implemented`.

### 4. Productize Vault First-Run Behavior

Failure mode: default config points at maintainer-like local paths and runtime discovery emits warnings such as configured vault not found. New users need a setup-state result, not a scary runtime warning.

Fix shape:

- Treat missing vault as first-run state with a clear next action.
- Ensure vault path resolution uses `project.yaml`, environment overrides, and `src.config.paths` consistently.
- Avoid hardcoded private paths in shipped config and reports.
- Add a safe create/attach path for the vault if it does not exist.

Verification:

- Fresh temp project with no vault: `status`, `registry`, and `report` pass and show setup guidance.
- Temp project with configured vault: repo/vault loops use that vault.
- No `~` or maintainer-specific path appears in fresh-install command output.

### 5. Remove Destructive Git Rollback From Automated Fix Paths

Failure mode: LLM escalation rollback can run `git reset --hard` and broad `git checkout -- .`. In an open-source repo, this can erase a user's unrelated local work.

Fix shape:

- Before any auto-fix escalation, capture an explicit worktree snapshot of changed files.
- Only revert files that were created or modified by the auto-fix attempt.
- If unrelated local changes exist in touched paths, block and report instead of reverting.
- Prefer worktree isolation for multi-loop runs and enforce it for `run --all` and autonomous cycles.

Verification:

- Test with pre-existing dirty files unrelated to an LLM attempt.
- Simulate a failed auto-fix and assert unrelated dirty files remain unchanged.
- Assert no `git reset --hard` or broad checkout is present in dev-loop rollback code.

### 6. Fix Repo/Vault Sync Path Resolution

Failure mode: repo sync currently discovers the project root by walking until a directory named `Augur`. That breaks renamed clones, forks, and arbitrary open-source checkout names.

Fix shape:

- Replace directory-name walking with `ctx.project_root` and `src.config.paths` helpers.
- Resolve the vault repo through the configured vault helper, not by reading YAML through an inferred root.
- Keep repo and vault sync actions separate in reports and fixes.

Verification:

- Temp project named something other than `Augur` still resolves the configured vault.
- Vault-only dirty state does not trigger project push.
- Project-only dirty state does not mutate the vault.

### 7. Add A Fresh-Install Dev-Loops Smoke Test

Failure mode: existing tests cover many internals, but there is no single proof that a new open-source user can run the basic `/dev-loops` lifecycle.

Fix shape:

- Add a focused smoke test or script that builds a temporary project fixture with:
  - repo `skills/`
  - no generated client exports
  - no existing runtime state
  - no existing vault
- Run `status`, `registry`, `manifest`, and `report`.
- Then add generated client export dirs and prove adaptive discovery still ignores them.

Verification:

- `uv run pytest <new smoke test>`.
- The smoke output is concise and free of generated-client warnings.

### 8. Clarify Release Docs And Help Text

Failure mode: docs still mix maintainer workflow, daemon internals, Codex migration notes, and user-facing commands. New users need a short contract: what dev-loops maintains, what it will not touch, and how to verify it is active.

Fix shape:

- Add an open-source section to `/dev-loops` docs:
  - first-run behavior
  - vault setup
  - scheduler ownership
  - safe git behavior
  - smoke verification command
- Keep deeper implementation details in references.

Verification:

- Docs mention no private paths.
- Public command table matches implemented behavior.

## Architecture

The productized architecture should have three clear boundaries.

Canonical loop sources are repo `skills/` and active vault user skills. Generated client exports are consumer surfaces and must not be loaded as executable loop modules.

The daemon owns only fast local sensing and event capture. Slow scheduled reasoning and maintenance jobs are Codex/native local automations, and their installed state must be observable.

Vault and repo maintenance loops operate through path helpers and explicit configured roots. They do not infer roots from directory names and do not treat a missing vault as a fatal runtime defect.

## Data Flow

`/dev-loops status` loads config, runtime state, journal history, adaptive registry metadata, and schedule installation status. It renders a truthful current-state table.

`/dev-loops registry` scans canonical skill sources only, validates callable modules, groups commands by loop, and reports missing callables only from canonical sources.

`/dev-loops manifest` derives schedule units from metadata, resolves workspace paths for the current checkout, and annotates each unit with local execution and cutover state.

Repo/vault maintenance loops receive `OpsContext.project_root`, resolve external paths through `src.config.paths`, and report project and vault actions separately.

## Error Handling

Missing vault becomes `setup-required`, not a scary warning.

Generated client export callable drift is ignored by adaptive loop discovery because those paths are not source of truth.

Unimplemented commands are not public. If a command cannot safely run, it exits with a clear non-zero message and next action.

Auto-fix rollback is file-scoped. If the engine cannot prove which files it owns, it reports `verification-failed-blocked` rather than cleaning the worktree.

## Testing

Testing should cover both internals and the fresh-user path:

- unit tests for canonical discovery source filtering
- unit tests for schedule ownership and cutover state
- CLI tests for implemented state commands
- rollback-safety tests with pre-existing dirty files
- repo/vault path-resolution tests in a renamed temp checkout
- a fresh-install smoke test for `status`, `registry`, `manifest`, and `report`

The release should not be declared ready until the smoke test passes without maintainer-specific paths or generated-client warning noise.

## Non-Goals

- Building a new dashboard control plane
- Implementing remote/cloud scheduled execution
- Replacing Codex-native local automations
- Running all adaptive loops as part of the release smoke test
- Supporting destructive cleanup of active user worktrees
