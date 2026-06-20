---
date: 2026-05-16
status: Draft
adr: ADR-758
deciders:
  - gsannikov
related:
  - ADR-727
  - ADR-743
  - ADR-744
  - ADR-755
  - ADR-756
  - ADR-757
---

# Routines Unification — Design

> Design spec for **ADR-758**. Companion to `docs/adrs/ADR-758-routines-unification.md`. **Read the ADR Status section first** — this spec assumes the four implementation gates pass.

## Goal

Collapse the two parallel surfaces (auto-loops and dream) into one **Routines** mechanism. After this ADR ships: one slash command (`/routines`), one declarative discovery (`x-augur-routine:` SKILL.md blocks), one Codex projection method, one status surface — across both `tiered` and `inline-session` execution models.

The execution models stay genuinely different (an inline-session prompt is not the same shape as a tiered scan/fix loop). What unifies is the *registry, surface, projection, and status* layer above them.

## Pre-Convergence State (assumes ADR-755+756+757 Implemented)

```
shared-vault/skills/
├── dream/                         # ADR-744 — inline-session execution
│   ├── SKILL.md                   # x-augur-mcp-tools: dream-*
│   ├── commands/dream.md          # the routine prompt
│   ├── assets/seeds/codex-dream-schedules.yaml
│   └── scripts/...                # dream-* tools, projection.py
├── routine-codebase/              # ADR-756 — tiered execution
│   ├── SKILL.md                   # x-augur-commands: auto-test-build, auto-test-lint, ...
│   └── scripts/...                # *_ops.py per auto-command
├── routine-platform/              # ADR-756 — tiered execution
├── routine-vault/                 # ADR-756 — tiered execution
├── routine-coverage/              # ADR-756 — tiered execution
├── routine-security/              # ADR-756 — tiered execution
└── daemon/
    ├── assets/seeds/codex-dev-loop-schedules.yaml   # centralized auto-loop schedules (residue)
    └── scripts/
        ├── routine_orchestrator/  # ADR-755 — orchestrator + ledger_view
        └── adaptive_loop_executor.py  # legacy entry, mostly a shim post-755

shared-vault/skills/ai/scripts/sync_agents/adapters/codex.py:
  _sync_dev_loop_automations()    # reads centralized seed
  _sync_dream_automations()       # reads dream/assets/seeds/codex-dream-schedules.yaml
```

Two surfaces, two seeds, two adapter methods, two slash commands.

## Post-Convergence Target

```
shared-vault/skills/
├── dream/                         # routine id="dream", execution=inline-session
│   ├── SKILL.md                   # gains x-augur-routine: block
│   ├── commands/dream.md          # unchanged
│   ├── assets/seeds/routine-schedule.yaml  # renamed from codex-dream-schedules.yaml
│   └── scripts/...                # unchanged
├── routine-codebase/              # routines: testing, code-quality, wiring
│   ├── SKILL.md                   # gains x-augur-routine: block per loop category
│   ├── assets/seeds/routine-schedule.yaml  # moved from centralized yaml
│   └── scripts/...                # unchanged
├── routine-platform/              # routines: hardening (platform parts), observability
│   └── (same shape)
├── routine-vault/                 # routines: knowledge-enrichment, vault-hygiene
│   └── (same shape)
├── routine-coverage/              # routines: hub-coverage, skill-usage
│   └── (same shape)
├── routine-security/              # routines: security-scan
│   └── (same shape)
└── daemon/
    └── scripts/
        ├── routine_orchestrator/  # unchanged + new registry.py
        │   └── registry.py         # NEW: walks all skills with x-augur-routine
        └── adaptive_loop_executor.py  # shim → delegates to /routines run <id>

shared-vault/skills/ai/scripts/sync_agents/adapters/codex.py:
  _sync_routine_automations()     # ONE method; walks the registry
```

One surface (`/routines`), one registry (the walker over `x-augur-routine` blocks), one projection method, one status surface. `/dev-loops` and `/dream` are documented aliases for one release cycle.

## The `x-augur-routine` Block

A new SKILL.md frontmatter field declared by every routine-providing skill. Schema:

```yaml
x-augur-routine:
  # Required fields
  id: testing                    # flat namespace — used as `/routines run <id>`
  execution: tiered              # tiered | inline-session
  policy: adaptive               # adaptive | oneshot | observability-only
  callable: scripts/orchestrator_entry.py   # for tiered; commands/dream.md for inline-session
  hub: command                   # for Browse placement
  # Optional fields
  loop: testing                  # legacy loop name (auto-loops); preserves trust state keying
  description: "Test + build verification routine"
  fan_out_threshold: 8           # tiered routines only
  budget_max_turns: 20           # subagent budget
```

A skill can declare multiple routines:

```yaml
# In routine-codebase/SKILL.md
x-augur-routines:                # plural; list of routine declarations
  - id: testing
    execution: tiered
    policy: adaptive
    callable: scripts/testing_orchestrator.py
    loop: testing
  - id: code-quality
    execution: tiered
    policy: adaptive
    callable: scripts/code_quality_orchestrator.py
    loop: code-quality
  - id: wiring
    execution: tiered
    policy: adaptive
    callable: scripts/wiring_orchestrator.py
    loop: wiring
```

(Per-skill `x-augur-routines:` accepts a list; singular `x-augur-routine:` accepts a dict — both supported by the registry walker for ergonomic flexibility.)

The legacy `x-augur-commands:` block (per-auto-command declarations from the old `loop-*` skills, migrated as-is by ADR-756) is preserved for backwards compatibility — the orchestrator still reads it to discover individual auto-commands within a routine. `x-augur-routine:` declares the *routine wrapper*; `x-augur-commands:` lists the *individual scan/fix units* the orchestrator dispatches.

## The Registry

New module: `shared-vault/skills/daemon/scripts/routine_orchestrator/registry.py`.

Public API:

```python
def list_routines() -> list[Routine]:
    """Walk every shared-vault/skills/*/SKILL.md and collect x-augur-routine
    declarations. Returns a flat list keyed by routine id."""

def get_routine(routine_id: str) -> Routine:
    """Resolve one routine by id. Raises RoutineNotFound if absent."""

def dispatch(routine_id: str, **kwargs) -> RoutineResult:
    """Top-level entry: resolve the routine, pick the runner based on
    execution model (tiered → orchestrator; inline-session → render the
    prompt in the current session), apply the policy gate, return result."""
```

The registry is read-only — declarations live in SKILL.md, registry just discovers them. No central registry file; the source of truth is per-skill SKILL.md blocks (per Rule #2).

## Slash Command Surface

New canonical command: `/routines` (project to clients via the existing command projection in `sync_agents`).

Verbs:

| Verb | Purpose |
|---|---|
| `/routines list` | All registered routines + their declared execution model + policy |
| `/routines status [<id>]` | Latest runs from the ledger; filter to one routine if `<id>` given |
| `/routines run <id>` | Invoke a routine in the current session (via `registry.dispatch`) |
| `/routines report <id> [--date YYYY-MM-DD]` | Render the most recent (or dated) report for a routine |
| `/routines schedule <id>` | Print the Codex automation TOML that would be projected for this routine (debugging surface) |

Aliases for one release cycle:

| Alias | Translates to |
|---|---|
| `/dev-loops run X` | `/routines run X` (X is a loop name like `testing`, `hardening`) |
| `/dev-loops status` | `/routines status` |
| `/dev-loops history` | `/routines status --history-limit 20` |
| `/dream` | `/routines run dream` |
| `aug dream status` | `aug routine status dream` |

The alias commands print a one-line deprecation notice ("Use `/routines run X` instead — `/dev-loops run X` retires after release X.Y") on every invocation.

## Codex Projection Unification

The Codex adapter today has two methods (post-ADR-755 + ADR-744):

```python
# In shared-vault/skills/ai/scripts/sync_agents/adapters/codex.py
def _sync_dev_loop_automations(self): ...
def _sync_dream_automations(self): ...
```

Collapse into one:

```python
def _sync_routine_automations(self):
    """Walk every skill with x-augur-routine declarations + a
    routine-schedule.yaml; emit one Codex automation per declared schedule
    binding. Replaces the two prior methods."""
    for routine in registry.list_routines():
        seed_path = routine.skill_root / "assets" / "seeds" / "routine-schedule.yaml"
        if not seed_path.is_file():
            continue  # routine has no scheduled binding; user invokes manually
        self._sync_codex_seed(seed_path, label=routine.id)
```

The existing `_sync_codex_seed` shared helper (added in ADR-744 work) stays as the materialization primitive — it's already generic.

The centralized `shared-vault/skills/daemon/assets/seeds/codex-dev-loop-schedules.yaml` is dismantled — each routine's schedule entries migrate to its owning skill's `assets/seeds/routine-schedule.yaml`.

## Status Surface Unification

Today (post-757):
- `aug dream status` reads ledger jobs with `kind=dream` via `dream_status.py`
- `/dev-loops status` reads ledger jobs (post-757) via the `ledger_view.py` translator

New canonical surface: `/routines status` and `aug routine status [<id>]`.

Both read the ADR-757 `ledger_view.read_recent_runs(routine_id=<id>, limit=...)` API. Output groups by routine id; each entry shows execution model + policy + state + duration + last-N history.

`aug dream status` and `/dev-loops status` stay as aliases that translate to `aug routine status dream` / `aug routine status` for one release cycle.

## Migration Mechanism

For each routine-providing skill:

1. Add `x-augur-routine:` (or `x-augur-routines:` plural) block to SKILL.md declaring the skill's routines.
2. If the skill has scheduled bindings: move its entries out of `shared-vault/skills/daemon/assets/seeds/codex-dev-loop-schedules.yaml` into the skill's own `assets/seeds/routine-schedule.yaml`. For dream: rename `codex-dream-schedules.yaml` → `routine-schedule.yaml`.

For the Codex adapter:

3. Add `_sync_routine_automations` method that walks the registry. Add it to `generate_mcp_config()` alongside the existing per-method calls.
4. Once verified working in one release cycle, remove the legacy `_sync_dev_loop_automations` + `_sync_dream_automations` calls.

For the slash command surface:

5. Project the new `/routines` command via the existing command projection in `sync_agents`. Add `routine.md` under `shared-vault/skills/daemon/commands/`.
6. Keep `/dev-loops` and `/dream` commands as alias documents that translate verbs in their CLI dispatch.

For the status surface:

7. Implement `routines status` in the registry-backed CLI.
8. Update `aug dream status` and `/dev-loops status` to delegate to the unified surface.

## Open Design Questions

1. **Dream directory rename to `routine-dream/`?** Recommended: NO. Registry-level identity via `x-augur-routine: { id: dream }` achieves conceptual unification without the migration cost of touching capability_exposure / sync_agents / MCP registrations / CLI. The directory name is just storage.

2. **`/dev-loops` deprecation timeline.** Recommended: keep aliases for **one full release cycle** post-ADR-758 implementation. Track via a deprecation warning printed on every alias invocation; retire in a follow-up ADR-759 (if ever needed; could be a small slash-command-cleanup ADR).

3. **Flat routine id namespace vs hierarchical.** Recommended: flat. Routine ids are `testing`, `hardening`, `dream`, ... with no `<skill>.<routine>` prefix. Easier to type, simpler to project, matches how loop names work today. Collision risk: two skills declaring the same routine id. Mitigation: registry walker errors out on duplicate ids; convention enforces uniqueness.

4. **What about the `loop` field in routine declarations?** Recommended: preserve it for backwards compatibility. Trust state file (ADR-743 / post-755 `routine_orchestrator/trust.py`) keys by `loop.category` — the `loop:` field lets the orchestrator look up the right trust state for a routine even after the routine has a new `id`. For most routines, `id == loop`. For some, they might differ (e.g. `id: skill-standards-evening`, `loop: skill-standards`).

5. **Should inline-session routines also support adaptive policy?** Recommended: defer. The adaptive trust+difficulty model assumes a category-level scan/fix loop. Inline-session routines like dream don't have a "category" in that sense — the routine runs as one unit. Allowing `policy: adaptive` for inline-session routines is an open extension; not required for the convergence work.

## Risks

- **Premature unification before dream prod evidence.** Mitigated by the Status section's gate: 10+ ledger-visible dream runs required.
- **Routine id collisions.** Two skills declaring the same id breaks the registry. Mitigation: registry walker fails loud on duplicates; convention documented in SKILL.md template.
- **Alias maintenance burden.** Keeping `/dev-loops` and `/dream` working as aliases for one release cycle requires the alias dispatcher to stay in sync with the canonical command. Mitigation: aliases are thin translation shims, not full re-implementations.
- **`x-augur-routine` field competing with `x-augur-commands`.** Both coexist (one declares the routine wrapper; one declares the individual auto-commands within a routine). Risk of confusion. Mitigation: SKILL.md template + ADR-758 docs make the distinction explicit; lint rule (deferred) could enforce the contract.

## What Does NOT Change

- ADR-755 orchestrator internals (`routine_orchestrator/orchestrator.py`, `scan_phase.py`, `bucket_planner.py`, `subagent_dispatch.py`, etc.) — preserved exactly.
- ADR-756 `routine-*` skill organization — preserved.
- ADR-757 ledger schema, supervisor sweep, `ledger_view.py` translator — preserved.
- Dream's `commands/dream.md` routine prompt — unchanged.
- Dream's 9 `dream-*` MCP tools + their CLI surface — unchanged.
- ADR-743 job ledger file format — unchanged.
- The `protocol: scan-fix` declarative discovery for individual auto-commands — unchanged.
- The trust algorithm (`routine_orchestrator/trust.py`) — unchanged.
- Per-routine report file paths and formats — unchanged.

The unification is **strictly at the registry / surface / projection / status layer**. Below that, nothing changes.
