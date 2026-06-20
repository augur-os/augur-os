---
status: Implemented
date: 2026-04-27
deciders:
  - gsannikov
related:
  - ADR-171
  - ADR-219
  - ADR-430
  - ADR-553
hub: ai
tags:
  - sync-agents
  - adapters
  - worktree
  - copilot
  - verification
superseded_by: null
---

# ADR-565: Adapter Output Contract Split — Cleanup vs Verification

## Context

`scripts/worktree_preflight.py` enforces a "sync_outputs" gate when the
`worktree` profile runs. The verifier asks each active adapter for the set of
paths it owns and requires every one to materialize on disk. Before this ADR
the verifier called `BaseAdapter.get_managed_files()`, treating that list as
the verification contract.

`get_managed_files()` is in fact the **cleanup** contract — it lists every path
Augur could ever write under that adapter, and is consumed by
`adapter.cleanup()` to delete stale artifacts when the adapter is disabled
(see ADR-219). Treating it as the verification contract conflates two
different questions:

1. "Which paths do we *own* (and may delete on cleanup)?" — `get_managed_files`
2. "Which paths *will this sync run actually produce* given the active flags
   and project state?" — previously implicit, asserted via `get_managed_files`

The conflation produced a hard regression for the Copilot adapter:

- `CopilotAdapter.get_managed_files()` declares seven paths. Tracing every
  writer across `engine.py`, `skill_sync.py`, `discovery.py`, and `copilot.py`
  showed that:
  - Two paths (`.github/copilot-instructions.md`, `.github/instructions/`)
    are produced unconditionally when `do_rules` / `do_skill_exports` run.
  - One path (`.github/copilot-memory.md`) requires `do_memory=True` AND
    `docs/memory/MEMORY.md` to exist as a source.
  - Three paths (`.github/agents/`, `.github/skills/`, `.github/copilot/`)
    are populated only via `distribute_imported_agents` inside the
    `if effective_plugins:` block of `sync_all`. After ADR-430 deleted the
    `augur.yaml` plugin overlap declarations, `discovery.resolve_overlaps()`
    became a permanent no-op stub returning `[]`, so
    `distribute_imported_agents` is never called with anything to distribute.
    These three paths therefore have **no live producer** under the current
    architecture.
  - One path (`.github/prompts/`) has no producer anywhere — `_sync_prompt_stubs`
    only writes Codex prompt directories.

- `WORKTREE_SYNC_BOOTSTRAP_CODE` in `worktree_preflight.py` ran
  `sync_all(do_memory=False, do_plugins=False, do_vaults=False)`. That
  intentionally suppressed memory and plugin sync, so even the producer-backed
  Copilot paths could not materialize.

- `_sync_output_ready` required directories to be **non-empty**. Even the
  rare case where `distribute_imported_agents` ran but produced zero
  Copilot-targeted writes would leave an empty dir and fail verification.

End state: every `worktree-launch.sh` invocation reported
`verify_passed: false` with `missing-sync-outputs` listing
`.github/agents`, `.github/copilot`, `.github/copilot-memory.md`,
`.github/prompts`, `.github/skills`. Worktree creation appeared to fail to
the user even though the on-disk worktree was perfectly usable.

GitHub Copilot is a primary integration target for Augur's customer
strategy, so neither "disable the Copilot adapter" nor "live with the noisy
gate" was acceptable.

## Decision

Split the adapter contract into two distinct methods:

### `get_managed_files() -> list[str]` — cleanup contract (unchanged)

Lists every path the adapter owns. Used by `adapter.cleanup()` and by
ADR-219's stale-file removal when the adapter is disabled. Conservative: it
should include paths whose producers are currently dormant, so cleanup can
still scrub stale artifacts left over from earlier producer versions.

### `get_required_outputs(project_root, *, do_rules, do_subagents, do_memory, do_plugins, do_skill_exports, do_prompt_exports, do_command_exports) -> list[str]` — verification contract (new)

Returns the subset of managed paths the adapter is contractually expected
to produce given the active sync flags AND the current project state.
Default implementation on `BaseAdapter` returns `[]` so existing adapters
opt in incrementally — they remain non-verified but cleanup still works.

Implementations inspect `project_root` for preconditions (file existence,
config declarations) and only return paths whose producer would actually
run. This makes the contract honest: "here is what a sync run with these
flags on this project will produce."

`CopilotAdapter` implements the contract as:

- always (when `do_rules`): `.github/copilot-instructions.md`
- always (when `do_skill_exports`): `.github/instructions/`
- when `do_memory` AND `project_root/docs/memory/MEMORY.md` exists:
  `.github/copilot-memory.md`
- the three plugin-distribution paths are intentionally absent from
  required outputs until a real producer exists. A code comment in
  `adapters/copilot.py` documents the no-op-stub state of
  `discovery.resolve_overlaps` and tells the next maintainer where to add
  the precondition check when a producer is reintroduced.
- `.github/prompts/` is similarly absent — no producer exists.

### Verifier and bootstrap changes

- `worktree_preflight._repo_local_sync_output_paths()` now calls
  `adapter.get_required_outputs(project_root, **WORKTREE_SYNC_FLAGS)`
  instead of enumerating `get_managed_files()`.
- `WORKTREE_SYNC_BOOTSTRAP_CODE` is now `sync_all(do_vaults=False)` —
  `do_plugins` and `do_memory` are enabled. `do_vaults` stays off because
  vault sync is global and would race between worktrees.
- `WORKTREE_SYNC_FLAGS` is a module-level dict mirroring the bootstrap's
  active flags, so the verifier and bootstrap stay coupled and a future
  change to one forces the other.
- `_sync_output_ready` relaxed to accept existing-but-empty directories —
  required-vs-optional is now decided by `get_required_outputs`, not by
  filesystem heuristics.

## Consequences

### Positive

- Worktree creation reports `verify_passed: true` against the same project
  state that previously failed. Copilot customers get coherent `.github/*`
  outputs in every worktree.
- The contract split is honest: `get_managed_files` answers "what do we
  own?" and `get_required_outputs` answers "what does this sync run
  guarantee to produce?". Neither method has to lie to satisfy the other.
- Adding a new adapter (Cursor, Windsurf, future IDEs) only requires
  implementing `get_required_outputs()` once it becomes customer-critical.
  Until then it inherits the empty default and is non-verified — explicit
  rather than silently broken.
- The verifier's profile-flag set (`WORKTREE_SYNC_FLAGS`) is co-located
  with the bootstrap flags it mirrors, so drift between the two is hard
  to introduce accidentally.
- Documents the dead-producer state of `.github/agents/`,
  `.github/skills/`, `.github/copilot/`, and `.github/prompts/` in code,
  surfacing the underlying gap (no Copilot plugin distribution since
  ADR-430) instead of hiding it behind a silently-failing gate.

### Negative

- Two methods to keep in sync per adapter rather than one. Adapter authors
  must remember to update both when introducing a new producer.
- `get_required_outputs` requires per-adapter project-state inspection
  (file existence, config probes), which adds a small amount of I/O to
  the verifier compared to a pure "does this path exist on disk?" check.
- Existing adapters (ClaudeCode, Cursor, Codex, Gemini, Windsurf,
  OpenCode, Antigravity, Cline, ClaudeDesktop, Kimi, GeminiPlugin) now
  inherit the empty default and are not under verification. This is
  better than the previous false-success-or-failure-by-luck behaviour but
  means their producers can regress without the gate noticing — until
  someone implements `get_required_outputs` for them.

### Neutral

- `.github/prompts/` remains in `CopilotAdapter.get_managed_files()` for
  cleanup hygiene even though no producer exists. If a future user
  manually drops files there, cleanup will still scrub them when the
  adapter is disabled.
- The worktree preflight's other incidents (`worktree/root/env-drift`,
  `worktree/bootstrap/missing-venv-test`) are unchanged. Both are
  non-blockers under the `worktree` profile and out of scope here.

## Alternatives Considered

### Alternative 1: Disable the Copilot adapter

Set `copilot.enabled: false` in `config/agents/ide_integrations.yaml`. The
verifier would skip its managed paths entirely and the gate would pass.
Rejected because Copilot is a primary integration target for Augur
customers — disabling it to satisfy an internal contract bug solves the
gate at the cost of the product.

### Alternative 2: Hand-extend `OPTIONAL_REPO_LOCAL_SYNC_OUTPUTS`

Add the unproducible Copilot paths to the existing
`OPTIONAL_REPO_LOCAL_SYNC_OUTPUTS` set in `worktree_preflight.py`.
Rejected because that set was intended for adapter-agnostic optional
outputs (e.g. `.codex/prompts`, `.gemini/memory`); growing it with
Copilot-specific entries leaks adapter knowledge into the verifier and
recreates the same coupling problem the contract split eliminates.
Adapter authors would have to remember to update a central allowlist as
well as their own adapter — exactly the design we want to avoid.

### Alternative 3: Force every adapter's producers to actually run during the worktree bootstrap

Make the bootstrap responsible for ensuring every managed path
materializes — for example, by touching empty directories for paths
without producers, or by stubbing `distribute_imported_agents` to always
write empty placeholders. Rejected because the verifier would then assert
fictional outputs and the gate would lose its diagnostic value: a missing
path could mean "real regression" or "the bootstrap didn't bother to
touch it this time", and you can't tell which.

### Alternative 4: Treat `get_managed_files` as authoritative and rewrite all adapters to keep it perfectly aligned with the active producers

Tighten `get_managed_files` so it already excludes any path whose producer
is currently dormant. Rejected because that breaks the cleanup
contract — paths from an earlier producer version would no longer be
scrubbed when the adapter is disabled, leaving stale `.github/copilot/*`
files behind across the rest of the customer base.

## References

- Commit `9fc94cbff` — `fix(worktree): align preflight contract with what
  sync actually produces` (initial implementation: `BaseAdapter`,
  `CopilotAdapter`, `worktree_preflight.py`).
- Commit `63bcdd9b9` — unrelated security fix shipped in the same
  push window.
- ADR-219 — adapter `enabled` gating, source of the cleanup contract that
  `get_managed_files` must continue to satisfy.
- ADR-171 — Phase 3 bidirectional plugin sync, the original intent for
  `.github/agents/` / `.github/skills/` / `.github/copilot/`
  distribution.
- ADR-430 — skill migration that retired the `augur.yaml` plugin overlap
  declarations, turning `discovery.resolve_overlaps` into a permanent
  no-op stub and orphaning the Copilot plugin-distribution producer.
- ADR-553 — Gemini extension support, an example of the kind of new
  adapter that benefits from the explicit `get_required_outputs`
  contract.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "BaseAdapter.get_required_outputs(project_root, **sync_flags) — new method, default returns []"
    - "WORKTREE_SYNC_BOOTSTRAP_CODE — now sync_all(do_vaults=False); previously also disabled do_memory and do_plugins"
    - "worktree_preflight._repo_local_sync_output_paths — now consumes get_required_outputs, not get_managed_files"
    - "worktree_preflight._sync_output_ready — directories no longer required to be non-empty"
  patterns_deprecated:
    - "Treating get_managed_files() as the verification contract"
  files_affected:
    - skills/ai/scripts/sync_agents/adapters/base.py
    - skills/ai/scripts/sync_agents/adapters/copilot.py
    - scripts/worktree_preflight.py
```

## Implementation

The decision shipped in `9fc94cbff` (and a follow-up tightening in the
same session). The change touched three files, added 92 lines, and
removed 17. Verification: `python3 scripts/worktree_preflight.py --root
<worktree> --profile worktree --repair` returns `verify_passed: true`
with `sync_outputs.ok=true`.

### Follow-up work (not blocking)

- Implement `get_required_outputs` for the other active adapters
  (ClaudeCode, Cursor, Codex, Gemini, Windsurf, OpenCode, etc.) so they
  come under verification too. File these as separate ADRs or tasks when
  each adapter becomes customer-critical.
- When a real producer for Copilot plugin distribution returns (e.g. a
  successor to the ADR-430-retired `augur.yaml` overlaps mechanism),
  reintroduce `.github/agents/`, `.github/skills/`, `.github/copilot/`
  in `CopilotAdapter.get_required_outputs` with an appropriate
  `project_root` precondition check.
- Implement or formally retire `.github/prompts/` distribution. The path
  has no producer anywhere in the codebase today.
