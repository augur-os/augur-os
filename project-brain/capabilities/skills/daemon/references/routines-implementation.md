## Implementation

### Release Gate Architecture

The public routines surface is release-gated against a fresh open-source clone. The command lifecycle must work before any maintainer runtime state, local schedules, generated client wrappers, or vault history exists.

The core boundaries are:

- canonical discovery reads repo `skills/` and the configured vault `skills/` only
- scheduled loop ownership is rendered from loop metadata plus local Codex automation state
- project and vault maintenance resolve roots through `src.config.paths`
- LLM rollback operates on owned paths only and fails closed on pre-existing user work
- `registry`, `status`, `manifest`, and `report --days 1` form the fresh-install smoke contract

The configured vault can be missing on first run. That is setup-required state, not a broken checkout, and command output should avoid maintainer-specific local paths.

Run the release smoke test with:

```bash
uv run pytest project-brain/capabilities/skills/daemon/augur/tests/test_dev_loops_open_source_smoke.py -q
```

### Registry

1. Call `discover_auto_commands(project_root)` from `project-brain/capabilities/skills/daemon/scripts/adaptive/discovery.py`
2. Call `group_by_loop(registry)` to group by loop name
3. For each loop, display auto-command name, tier, trigger, owner plugin, and module path
4. Show summary totals for auto-commands, loops, and per-loop membership

Discovery deliberately ignores client wrapper output folders. Missing callables in those folders are packaging drift, not adaptive loop source failures.

### Status

1. Read `config/system/adaptive_loops.yaml`
2. Read `~/Library/Application Support/Augur/state/adaptive/trust_state.json`
3. Read ADR-743 job records from `~/Library/Application Support/Augur/state/jobs/` through the ADR-757 ledger view
4. Render loop status, budgets, trust, and recent activity

Loops default to enabled unless explicitly disabled in config.

### Run

Use `AdaptiveLoopEngine.run_auto_cycle()` for all loop execution. The engine and discovery code both live under `project-brain/capabilities/skills/daemon/scripts/adaptive/`.

For `--all`, dispatch one background agent per enabled loop, collect the reports, then run the post-run git inspection from `run_inspection.py`. If `--evolve` is present, also generate evolve analysis from the same inspection data.

### Fix Quality Escalation

The fix pipeline now distinguishes three finding bands:

- `mechanical`
  - no wiki/ADR context
  - direct auto-fix path
- `local-semantic`
  - local code/docs first
  - targeted context only when intent is unclear
- `structural`
  - broad or ownership-affecting change
  - design gate written before implementation

The helper modules live in:

- `project-brain/capabilities/skills/daemon/scripts/adaptive/engine_quality.py`
- `project-brain/capabilities/skills/daemon/scripts/adaptive/engine_context.py`
- `project-brain/capabilities/skills/daemon/scripts/adaptive/engine_design_gate.py`

Structural findings can now produce richer outcomes than plain `report-only`:

- `design-written`
- `blocked-needs-design`
- `context-insufficient`
- `design-gated-fixed`

These outcomes propagate through `reporting.py`, `loop_reporter.py`, and `run_inspection.py` so broad fixes stop being misreported as generic manual debt.

### Autonomous cycles

When `--cycles N` is present, the agent runs a self-improving loop rather than just repeating scans:

```
for cycle in 1..N:
  1. run --all --evolve
  2. parse evolve output (broken scanners, report-only fixable, gate deferrals, manual items)
  3. act on findings in priority order:
     a. fix broken scanners (import errors, missing deps)
     b. upgrade report-only fix() to produce code changes
     c. fix wrong issue kinds causing unnecessary structural gates
     d. execute concrete manual instructions from evolve output
     e. run heal --fix if trust-stuck or failed categories detected
  4. commit inter-cycle fixes: "fix(adaptive): <description>"
  5. if no actionable items remain → stop early (unless --force)
```

The key difference from a naive re-run: between cycles, the agent reads the evolve recommendations and actually implements them (upgrading scanners, fixing issue classification, addressing manual items). Each cycle should produce fewer findings than the previous one. If cycle N has the same output as cycle N-1, the agent is stuck and should stop.

Stop-early conditions (skip remaining cycles):
- All categories clean or maintenance-only
- All remaining issues are blocked (user-modified, ADR-443)
- No new findings compared to previous cycle (plateau)

Override with `--force` to always run all N cycles regardless.

### Heal

Use `heal_detect()` and `investigate_finding()` from `project-brain/capabilities/skills/daemon/scripts/adaptive/heal.py` to detect and investigate loop failures, structural idleness, and trust-stuck categories.

## Scheduler Ownership

- `self-heal-fast` remains daemon-owned (`continuous` / daemon health remediation)
- daemon captures post-execution events locally, but the scheduled `command-evolution` drain is Codex-owned
- daemon captures enrichment inputs locally, but the scheduled `knowledge-enrichment` drain is Codex-owned
- nightly loop families are owned by split Codex-native schedules
- each routine owner's canonical Codex schedule lives in its skill-local
  `assets/seeds/routine-schedule.yaml`

`manifest` resolves the local installation state for each Codex schedule. Rows that have no local automation file report `not-installed`; disabled managed automations report `disabled`; active managed automations report `active`.

### Rollback Safety

LLM escalation captures the pre-dispatch HEAD, git status, and dirty path content before launching the external client. On failure, it reverts only committed LLM-owned paths and removes only newly introduced untracked files. If an LLM touches a path that was dirty before dispatch, the loop engine restores pre-dispatch dirty content when possible, refuses to report success, and leaves enough diagnostics for manual recovery.

Commit verification no longer reconstructs a baseline by checking out the whole tree or stashing user work. Without a cached baseline, a failing verify command fails closed by reverting the auto-fix commit.

### History / review

The history and queued-review surfaces are backed by the adaptive command-evolution state under `~/Library/Application Support/Augur/state/command-evolution/`.
