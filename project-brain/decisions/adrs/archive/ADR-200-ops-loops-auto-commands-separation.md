---
status: Implemented
date: '2026-03-03'
deciders:
- Gur Sannikov
related:
- ADR-176 (Adaptive Loop Engine)
- ADR-181 (Adaptive Loops Consolidation)
- ADR-178 (Decentralized Slash Command Discovery)
- ADR-163 (Config Decentralization)
- ADR-102 (Adaptive Slash Commands)
hub: null
tags:
- ops
- loops
- auto
- commands
- separation
superseded_by: null
---

# ADR-200: Ops-Loops / Auto-Commands Separation

## Context

The adaptive loop engine (ADR-176, ADR-181) runs 5 autonomous loops (self-heal, code-quality, hardening, knowledge-enrichment, command-evolution) with ~25 total categories. Each loop class has inline `scan()`/`fix()` methods baked into Python code. Separately, 14 standalone `ops-*` slash commands perform manual operations. When there's overlap (lint, stale paths, dependency audit), the two systems duplicate work with independent implementations.

Problems:
1. **No user-triggerable loop operations** — users cannot manually run a specific loop category (e.g., "just run the lint fix now")
2. **No shared implementation** — improvements to `ops-audit` don't benefit the hardening loop's dependency-audit category, and vice versa
3. **Naming confusion** — all commands share the `ops-*` prefix, making it impossible to distinguish daemon-managed from standalone operations
4. **Centralized loop config** — `config/system/adaptive_loops.yaml` defines all category-to-command mappings centrally, violating ADR-163 (plugin decentralization)
5. **Tight coupling** — the engine knows both WHEN to run and HOW to run things; changing an implementation requires editing daemon code

## Decision

### 1. Two-Layer Architecture: Orchestration vs Implementation

Separate concerns into two clean layers:

```
┌─────────────────────────────────────────────┐
│              ORCHESTRATION LAYER             │
│            (ops-loops / daemon)              │
│                                             │
│  Trust Ledger │ Budget Control │ Cadence     │
│  Difficulty   │ Promotion      │ Journal     │
│  Regression Guard │ Clean Scan Saturation    │
│                                             │
│  Knows WHEN and WHETHER to run things.       │
│  Never knows HOW to run things.              │
└──────────────────┬──────────────────────────┘
                   │ discover + call scan()/fix()
                   ▼
┌─────────────────────────────────────────────┐
│            IMPLEMENTATION LAYER             │
│            (auto-* commands)                │
│                                             │
│  auto-lint │ auto-format │ auto-markers     │
│  auto-heal │ auto-rag    │ auto-build       │
│                                             │
│  Each exposes: scan(ctx) → ScanResult       │
│                fix(ctx, issues) → FixResult  │
│                                             │
│  Knows HOW to do the work.                  │
│  Never knows about trust, budget, cadence.   │
└──────────────────────────────────────────────┘
```

Two execution paths to the same implementation:
1. **User**: `/auto-lint` → CLI loads Python module → calls `scan()` then `fix()` → prints summary
2. **Daemon**: engine resolves `auto-lint` → loads Python module → calls `scan(difficulty=N)` → trust-gates `fix()` → records to journal

### 2. Naming Convention: `auto-*` vs `ops-*`

- **`auto-*`** = Daemon-managed operations. The daemon decides when to run them based on trust, budget, and cadence. Users can also trigger them manually.
- **`ops-*`** = Standalone manual operations. Only triggered by the user.
- **`ops-loops`** = The orchestrator that manages all `auto-*` commands.

### 3. Scan/Fix Protocol

Every `auto-*` command implements this Python interface:

```python
@dataclass
class ScanResult:
    issues: list[dict]        # What was found (empty = clean scan)
    summary: str              # Human-readable description
    severity: str             # "info" | "warning" | "error"

@dataclass
class FixResult:
    success: bool             # Overall success
    actions: list[dict]       # What was done
    changes: list[str]        # File paths modified
    summary: str              # Human-readable description

@dataclass
class OpsContext:
    project_root: Path
    difficulty: int = 0       # 0-4, passed by orchestrator (ignored by CLI)
    dry_run: bool = False     # True = scan only, never fix
    verbose: bool = False     # True = detailed output for CLI

class OpsCommand(Protocol):
    name: str
    def scan(self, ctx: OpsContext) -> ScanResult: ...
    def fix(self, ctx: OpsContext, issues: list[dict]) -> FixResult: ...
```

The protocol module lives at `src/lib/ops_protocol.py` (shared infrastructure, like `src/config/paths.py`). All auto-command modules import from there. This avoids cross-plugin imports — the alternative of placing it inside any single plugin would force other plugins to depend on it, violating ADR-163.

Scan-only commands expose `scan()` but `fix()` returns a no-op FixResult.

**Engine flow change**: The current engine calls `loop.scan()` once per loop, getting actions across all categories, then filters by category. The new engine calls `scan()` per auto command (one auto command = one category). This simplifies the engine:

```
for auto_cmd in loop_commands:
    result = auto_cmd.scan(ctx)
    if result.issues and ledger.check_allowed(auto_cmd.name):
        fix_result = auto_cmd.fix(ctx, result.issues)
        verify_and_journal(fix_result)
```

Difficulty is passed by the orchestrator and interpreted by the implementation:

| Command | Difficulty 0 | Difficulty 2 | Difficulty 4 |
|---------|-------------|-------------|-------------|
| auto-lint | Auto-fixable only | Warnings | All errors |
| auto-markers | TODO_CLEANUP only | TODO_OUTDATED | TODO_BUG |
| auto-rag-reindex | Stale index check | Rebuild changed | Full reindex |
| auto-heal-imports | Import errors only | Config errors | Logic errors |

Note: `tier` (in loop config) controls promotion order — higher tiers unlock after lower tiers earn trust. `difficulty` (0–4) controls scan depth within a single command and escalates after consecutive successes. They are independent dimensions. Tiers above 4 (e.g., hardening's tier 5) are valid; difficulty is clamped to 0–4.

### 4. Decentralized Configuration (ADR-163 Compliant)

Each plugin declares its `auto-*` contributions in its own `augur.yaml`:

```yaml
# plugins/dev/skills/devops/augur.yaml
commands:
  - id: auto-lint
    type: workflow
    callable: scripts/ops/lint.py
    protocol: scan-fix
    loop:
      name: code-quality
      tier: 1
      trigger: nightly
```

The central `config/system/adaptive_loops.yaml` shrinks to engine-level settings only:

```yaml
engine:
  verify_command: "npx tsc --noEmit"
  journal_retention_days: 30
  nightly_time: "03:00"
loops:
  code-quality:
    budget: 15
  self-heal:
    budget: 5
  hardening:
    budget: 10
  knowledge-enrichment:
    budget: 15
  command-evolution:
    budget: 3
```

The engine assembles the full loop configuration at startup by scanning all `augur.yaml` files for `protocol: scan-fix` commands.

### 5. Engine Discovery

```python
def discover_auto_commands(project_root: Path) -> dict[str, AutoCommandEntry]:
    registry = {}
    for yaml_path in project_root.glob("plugins/*/skills/*/augur.yaml"):
        config = load_yaml(yaml_path)
        plugin_root = yaml_path.parent
        for cmd in config.get("commands", []):
            if cmd.get("protocol") == "scan-fix":
                module_path = plugin_root / cmd["callable"]
                loop_config = cmd.get("loop", {})
                registry[cmd["id"]] = AutoCommandEntry(
                    module=load_ops_module(module_path),
                    loop_name=loop_config.get("name"),
                    tier=loop_config.get("tier", 0),
                    trigger=loop_config.get("trigger", "nightly"),
                )
    return registry
```

### 6. Implementation File Layout

Shared protocol and dataclasses:

```
src/lib/
└── ops_protocol.py           # OpsCommand protocol + ScanResult/FixResult/OpsContext dataclasses
```

Each auto command's Python implementation lives alongside its markdown command in the owning plugin:

```
plugins/dev/skills/devops/
├── commands/
│   ├── auto-lint.md
│   ├── auto-format.md
│   ├── auto-markers.md
│   └── ...
├── scripts/ops/
│   ├── __init__.py
│   ├── lint.py
│   ├── format.py
│   ├── markers.py
│   └── ...

plugins/observability/skills/daemon/
├── commands/
│   ├── ops-loops.md          # Orchestrator (unchanged)
│   ├── auto-heal-imports.md
│   ├── auto-build-health.md
│   └── ...
├── scripts/ops/
│   ├── heal_imports.py
│   ├── build_health.py
│   └── ...

plugins/ai/skills/ai_bridge/
├── commands/
│   ├── auto-rag-reindex.md
│   ├── auto-descriptions.md
│   └── ...
├── scripts/ops/
│   ├── rag_reindex.py
│   ├── descriptions.py
│   └── ...
```

### 7. Full Command Map

#### Loop: self-heal (budget: 5)
| Category | auto command | Owner plugin |
|----------|-------------|-------------|
| import-fixes (tier 0) | auto-heal-imports | daemon |
| config-fixes (tier 1) | auto-heal-config | daemon |
| logic-fixes (tier 2) | auto-heal-logic | daemon |
| refactor-fixes (tier 3) | auto-heal-refactor | daemon |

#### Loop: code-quality (budget: 15)
| Category | auto command | Owner plugin |
|----------|-------------|-------------|
| scan-markers (tier 0) | auto-markers | devops |
| log-maintenance (tier 0) | auto-logs | devops |
| format (tier 0) | auto-format | devops |
| lint-autofix (tier 1) | auto-lint | devops |
| todo-cleanup (tier 2) | auto-todo-cleanup | devops |
| type-errors (tier 3) | auto-types | devops |
| todo-outdated (tier 4) | auto-todo-outdated | devops |

#### Loop: knowledge-enrichment (budget: 15)
| Category | auto command | Owner plugin |
|----------|-------------|-------------|
| rag-reindex (tier 0) | auto-rag-reindex | ai_bridge |
| project-index-rebuild (tier 0) | auto-project-index | ai_bridge |
| index-new-files (tier 1) | auto-index-new | ai_bridge |
| analytics-generation (tier 0) | auto-analytics | ai_bridge |
| fix-broken-indices (tier 2) | auto-fix-indices | ai_bridge |
| generate-descriptions (tier 3) | auto-descriptions | ai_bridge |
| create-data-files (tier 4) | auto-data-files | ai_bridge |

#### Loop: hardening (budget: 10)
| Category | auto command | Owner plugin |
|----------|-------------|-------------|
| build-health (tier 0) | auto-build-health | daemon |
| augur-yaml-lint (tier 0) | auto-yaml-lint | devops |
| stale-action-page (tier 0) | auto-stale-actions | devops |
| page-mount-check (tier 1) | auto-mount-check | devops |
| api-route-health (tier 2) | auto-api-health | devops |
| dependency-audit (tier 3) | auto-audit | devops |
| plugin-template-lint (tier 4) | auto-plugin-lint | devops |
| stale-path-scan (tier 5) | auto-stale-paths | devops |

#### Loop: command-evolution (budget: 3)
| Category | auto command | Owner plugin |
|----------|-------------|-------------|
| timeout-hints (tier 0) | auto-cmd-timeouts | ai_bridge |
| cache-keys (tier 1) | auto-cmd-cache | ai_bridge |
| missing-steps (tier 2) | auto-cmd-steps | ai_bridge |
| reorder-phases (tier 3) | auto-cmd-reorder | ai_bridge |
| remove-steps (tier 4) | auto-cmd-remove | ai_bridge |

#### Standalone ops commands (unchanged)
ops-daemon, ops-loops, ops-kill, ops-inspect, ops-perf, ops-memory, ops-sync, ops-docs, ops-debt, ops-refactor, ops-rollback, ops-tabs, ops-optimize

#### Retired
| Command | Replaced by |
|---------|------------|
| ops-hygiene | auto-plugin-lint + auto-stale-paths + auto-lint |
| ops-audit | auto-audit (renamed, now daemon-managed) |
| ops-plugin-lint | auto-plugin-lint (renamed, now daemon-managed) |

### 8. Error Handling

- **Missing auto command at startup**: Disable category, log warning, continue
- **Exception during scan()**: Catch, record failure in journal, trust penalty
- **Regression guard failure**: Revert changes, record failure, demote trust (unchanged)
- **Protocol versioning**: `protocol: scan-fix` can be versioned later if needed

## Consequences

**Positive**:
- Every loop operation is now user-triggerable via `/auto-*` commands
- Single implementation for both user and daemon paths eliminates duplication
- Clean naming distinction: `auto-*` (daemon-managed) vs `ops-*` (manual)
- Plugin-decentralized: each plugin owns its auto commands and loop config
- Engine becomes pure orchestration — easier to test, reason about, and extend
- Adding a new auto command requires only a plugin augur.yaml entry and a Python module

**Negative**:
- Large refactor: extracting ~25 categories from 5 loop classes into separate modules
- More files: ~28 new Python modules + ~28 new command markdown files
- Command namespace grows significantly (from ~14 ops to ~41 total)
- No backward compatibility — old loop classes and centralized config replaced entirely

**Neutral**:
- Trust system, budget control, journal, regression guard all unchanged in behavior
- Dashboard loops page continues to work, just shows the backing auto command name
- Existing standalone ops commands completely unaffected

## Implementation Order

```
Phase 1: Protocol & Infrastructure
├── Step 1: Create OpsCommand protocol + ScanResult/FixResult/OpsContext dataclasses
├── Step 2: Implement discover_auto_commands() in engine.py
├── Step 3: Modify engine run_category() to call discovered auto commands
└── Step 4: Shrink adaptive_loops.yaml to engine-level settings only

Phase 2: Extract Code-Quality Loop (proof-of-concept)
├── Step 5: Extract 7 code-quality categories into scripts/ops/ modules (devops plugin)
├── Step 6: Create 7 auto-* command markdown files
├── Step 7: Register in devops augur.yaml with callable + protocol + loop fields
└── Step 8: Remove inline scan/fix from code_quality.py

Phase 3: Extract Remaining Loops (PARALLEL — no deps between loops)
├── Step 9: Extract self-heal (4 categories → daemon plugin scripts/ops/)
├── Step 10: Extract hardening (8 categories → daemon + devops scripts/ops/)
├── Step 11: Extract knowledge-enrichment (7 categories → ai_bridge scripts/ops/)
└── Step 12: Extract command-evolution (5 categories → ai_bridge scripts/ops/)

Phase 4: Cleanup & Wiring
├── Step 13: Retire ops-hygiene, rename ops-audit → auto-audit, ops-plugin-lint → auto-plugin-lint
├── Step 14: Add /ops-loops registry sub-command
├── Step 15: Update dashboard loops page to show auto command per category
└── Step 16: Update CLAUDE.md command lists, run sync_agents.py

Phase 5: Verification
├── Step 17: Run tsc --noEmit, pytest, stale path scanner (parallel)
├── Step 18: Run 3+ auto commands manually to verify scan/fix protocol
├── Step 19: Verify engine discovers all ~28 auto commands at startup
├── Step 20: Verify trust state persists correctly across daemon restarts
├── Step 21: Verify architectural intent — no implementation in engine, no trust in auto commands
└── Step 22: Run npm run build (full production build)
```

## Alternatives Considered

### A: Shared ops library in devops plugin
All implementations in a single `plugins/dev/skills/devops/scripts/ops/` library. Both loops and commands import from it. Rejected because it creates a shared dependency that violates plugin self-containment (ADR-163). A daemon loop depending on a devops library creates implicit coupling.

### B: Ops commands own implementation, loops import across plugin boundaries
Each plugin owns its ops command Python file. Loops import from the command's plugin directory via `augur.yaml` callable field. Rejected in favor of Approach C because it still requires the centralized `adaptive_loops.yaml` to map categories to commands. Approach C decentralizes that mapping into per-plugin augur.yaml.

### C: Keep current architecture, just add user-facing wrappers
Add thin `/ops-*` wrapper commands that call the existing inline loop methods. Rejected because it perpetuates duplication — two codepaths to maintain, and improvements to wrappers don't flow to loops and vice versa.

## References

- ADR-176: Adaptive Loop Engine (foundation)
- ADR-181: Adaptive Loops Consolidation (absorbed 3 services into loops)
- ADR-178: Decentralized Slash Command Discovery (pattern for decentralized command registration)
- ADR-163: Config Decentralization (architectural principle)
- ADR-102: Adaptive Slash Commands (command evolution infrastructure)
- Design doc: `docs/plans/2026-03-03-ops-loops-commands-separation-design.md`

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "ops-audit"
      to: "auto-audit"
      scope: "plugins/*/skills/*/commands/, plugins/*/skills/*/augur.yaml"
    - from: "ops-plugin-lint"
      to: "auto-plugin-lint"
      scope: "plugins/*/skills/*/commands/, plugins/*/skills/*/augur.yaml"
    - from: "ops-hygiene"
      to: "auto-plugin-lint + auto-stale-paths + auto-lint"
      scope: "plugins/*/skills/*/commands/, docs/"
  apis_changed:
    - function: "run_category"
      module: "plugins.observability.skills.daemon.scripts.adaptive.engine"
      breaking: true
    - function: "scan / fix (inline methods)"
      module: "plugins.observability.skills.daemon.scripts.adaptive.loops.*"
      breaking: true
  patterns_deprecated:
    - grep: "class.*Loop.*BaseLoop"
      replacement: "Loop classes become thin; scan/fix extracted to auto-* command modules"
    - grep: "def scan\\(self.*category"
      replacement: "scan() now lives in scripts/ops/*.py modules, not loop classes"
  files_affected:
    - glob: "src/lib/ops_protocol.py"
    - glob: "plugins/observability/skills/daemon/scripts/adaptive/engine.py"
    - glob: "plugins/observability/skills/daemon/scripts/adaptive/discovery.py"
    - glob: "plugins/observability/skills/daemon/scripts/adaptive/loops/*.py"
    - glob: "plugins/observability/skills/daemon/scripts/adaptive_loop_executor.py"
    - glob: "config/system/adaptive_loops.yaml"
    - glob: "plugins/dev/skills/devops/augur.yaml"
    - glob: "plugins/dev/skills/devops/scripts/ops/*.py"
    - glob: "plugins/observability/skills/daemon/augur.yaml"
    - glob: "plugins/observability/skills/daemon/scripts/ops/*.py"
    - glob: "plugins/ai/skills/ai_bridge/augur.yaml"
    - glob: "plugins/ai/skills/ai_bridge/scripts/ops/*.py"
    - glob: "plugins/observability/skills/daemon/tests/test_adaptive_*.py"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-200: Ops-Loops / Auto-Commands Separation**.

Read the full ADR: `docs/decisions/ADR-200-ops-loops-auto-commands-separation.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-200-auto-commands", description="Implementing ADR-200: Ops-Loops / Auto-Commands Separation")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent name in the Execution Plan, spawn a teammate. Phase 3 requires 4 uniquely-named agents (`dev-self-heal`, `dev-hardening`, `dev-knowledge`, `dev-evolution`) to achieve true parallelism:
   ```
   Agent(subagent_type="general-purpose", team_name="adr-200-auto-commands", name="{agent-name}",
        model="{tier-model}", prompt="You are '{agent-name}' on the adr-200 team.
        Read your profile: .claude/agents/{role}.md (use 'developer' profile for dev-* agents)
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-200-auto-commands`

#### Phase 1: Protocol & Infrastructure
**Strategy**: PARALLEL then PIPELINE (1.1 ∥ 1.4, then 1.2, then 1.3)
**Agents**:

| Step | Agent | Tier | Depends on | Task | Files |
|------|-------|------|-----------|------|-------|
| 1.1 | developer | high | — | Create OpsCommand protocol, ScanResult/FixResult/OpsContext dataclasses in shared infrastructure module | `src/lib/ops_protocol.py` (new) |
| 1.2 | developer | high | 1.1 | Implement discover_auto_commands() — scan augur.yaml files for protocol: scan-fix, assemble loop categories from decentralized config. Add discover_auto_commands to engine's startup path | `plugins/observability/skills/daemon/scripts/adaptive/discovery.py` (extend existing) |
| 1.3 | developer | high | 1.2 | Modify engine.py: replace per-loop scan→filter→execute with per-auto-command scan→trust-gate→fix. Engine iterates discovered auto commands grouped by loop, calls scan() individually per category, then trust-gates fix() | `plugins/observability/skills/daemon/scripts/adaptive/engine.py` |
| 1.4 | devops | low | — | Shrink adaptive_loops.yaml to engine-level settings only (budgets, verify_command, nightly_time). Remove all category definitions — these move to per-plugin augur.yaml | `config/system/adaptive_loops.yaml` |

#### Phase 2: Extract Code-Quality Loop (Proof of Concept)
**Strategy**: PIPELINE (2.1 first, then 2.2 ∥ 2.3, then 2.4)
**Agents**:

| Step | Agent | Tier | Depends on | Task | Files |
|------|-------|------|-----------|------|-------|
| 2.1 | developer | medium | Phase 1 | Create `plugins/dev/skills/devops/scripts/ops/` directory. Extract 7 code-quality categories (scan-markers, log-maintenance, format, lint-autofix, todo-cleanup, type-errors, todo-outdated) from code_quality.py into individual Python modules implementing OpsCommand protocol. Each module imports from `src.lib.ops_protocol` | `plugins/dev/skills/devops/scripts/ops/__init__.py`, `markers.py`, `logs.py`, `format.py`, `lint.py`, `todo_cleanup.py`, `types.py`, `todo_outdated.py` |
| 2.2 | devops | low | 2.1 | Create 7 auto-* command markdown files for CLI usage | `plugins/dev/skills/devops/commands/auto-markers.md`, `auto-logs.md`, `auto-format.md`, `auto-lint.md`, `auto-todo-cleanup.md`, `auto-types.md`, `auto-todo-outdated.md` |
| 2.3 | devops | low | 2.1 | Register all 7 commands in devops augur.yaml with callable, protocol: scan-fix, and loop fields (name, tier, trigger) | `plugins/dev/skills/devops/augur.yaml` |
| 2.4 | developer | medium | 2.2, 2.3 | Remove inline scan/fix from code_quality.py — class becomes empty orchestration stub or is removed entirely | `plugins/observability/skills/daemon/scripts/adaptive/loops/code_quality.py` |

#### Phase 3: Extract Remaining Loops
**Strategy**: PARALLEL (no deps between loops — spawn 4 agents concurrently)
**Agents**:

| Step | Agent | Tier | Depends on | Task | Files |
|------|-------|------|-----------|------|-------|
| 3.1 | dev-self-heal | medium | Phase 2 | Create `plugins/observability/skills/daemon/scripts/ops/` dir. Extract self-heal: 4 categories from self_heal.py into modules. Create 4 command .md files. Register in daemon augur.yaml | `plugins/observability/skills/daemon/scripts/ops/__init__.py`, `heal_imports.py`, `heal_config.py`, `heal_logic.py`, `heal_refactor.py`, `plugins/observability/skills/daemon/commands/auto-heal-imports.md`, `auto-heal-config.md`, `auto-heal-logic.md`, `auto-heal-refactor.md`, `plugins/observability/skills/daemon/augur.yaml` |
| 3.2 | dev-hardening | medium | Phase 2 | Extract hardening: 8 categories. build-health → daemon scripts/ops/, remaining 7 → devops scripts/ops/. Create 8 command .md files. Register in both augur.yaml files | `plugins/observability/skills/daemon/scripts/ops/build_health.py`, `plugins/observability/skills/daemon/commands/auto-build-health.md`, `plugins/dev/skills/devops/scripts/ops/yaml_lint.py`, `stale_actions.py`, `mount_check.py`, `api_health.py`, `audit.py`, `plugin_lint.py`, `stale_paths.py`, `plugins/dev/skills/devops/commands/auto-yaml-lint.md`, `auto-stale-actions.md`, `auto-mount-check.md`, `auto-api-health.md`, `auto-audit.md`, `auto-plugin-lint.md`, `auto-stale-paths.md`, `plugins/dev/skills/devops/augur.yaml`, `plugins/observability/skills/daemon/augur.yaml` |
| 3.3 | dev-knowledge | medium | Phase 2 | Create `plugins/ai/skills/ai_bridge/scripts/ops/` dir. Extract knowledge-enrichment: 7 categories into modules. Create 7 command .md files. Register in ai_bridge augur.yaml | `plugins/ai/skills/ai_bridge/scripts/ops/__init__.py`, `rag_reindex.py`, `project_index.py`, `index_new.py`, `analytics.py`, `fix_indices.py`, `descriptions.py`, `data_files.py`, `plugins/ai/skills/ai_bridge/commands/auto-rag-reindex.md`, `auto-project-index.md`, `auto-index-new.md`, `auto-analytics.md`, `auto-fix-indices.md`, `auto-descriptions.md`, `auto-data-files.md`, `plugins/ai/skills/ai_bridge/augur.yaml` |
| 3.4 | dev-evolution | medium | Phase 2 | Extract command-evolution: 5 categories into ai_bridge scripts/ops/ modules. Create 5 command .md files. Register in ai_bridge augur.yaml | `plugins/ai/skills/ai_bridge/scripts/ops/cmd_timeouts.py`, `cmd_cache.py`, `cmd_steps.py`, `cmd_reorder.py`, `cmd_remove.py`, `plugins/ai/skills/ai_bridge/commands/auto-cmd-timeouts.md`, `auto-cmd-cache.md`, `auto-cmd-steps.md`, `auto-cmd-reorder.md`, `auto-cmd-remove.md`, `plugins/ai/skills/ai_bridge/augur.yaml` |

#### Phase 4: Cleanup & Wiring
**Strategy**: PARALLEL then PIPELINE (4.1 ∥ 4.2, then 4.3, then 4.4 ∥ 4.5)
**Agents**:

| Step | Agent | Tier | Depends on | Task | Files |
|------|-------|------|-----------|------|-------|
| 4.1 | devops | low | Phase 3 | Delete retired commands: `ops-hygiene.md`, `ops-audit.md` (or `ops-audit/`), `ops-plugin-lint/`. Delete gutted loop classes: `code_quality.py`, `self_heal.py`, `hardening.py`, `knowledge_enrichment.py`, `command_evolution.py`. Keep `base_loop.py` and `__init__.py` (base_loop becomes dead code but removing it is Phase 5 validation scope) | `plugins/dev/skills/devops/commands/ops-hygiene.md`, `plugins/dev/skills/devops/commands/ops-audit/`, `plugins/dev/skills/devops/commands/ops-plugin-lint/`, `plugins/observability/skills/daemon/scripts/adaptive/loops/code_quality.py`, `self_heal.py`, `hardening.py`, `knowledge_enrichment.py`, `command_evolution.py` |
| 4.2 | developer | medium | Phase 3 | Add `/ops-loops registry` sub-command to ops-loops.md showing all discovered auto commands and their loop assignments | `plugins/observability/skills/daemon/commands/ops-loops.md` |
| 4.3 | developer | medium | 4.1, 4.2 | Update adaptive_loop_executor.py to use discover_auto_commands() instead of manual loop registration. Remove _HealerAdapter and per-loop register_loop() calls | `plugins/observability/skills/daemon/scripts/adaptive_loop_executor.py` |
| 4.4 | devops | low | 4.3 | Run sync_agents.py to update CLAUDE.md command lists | Generated files |
| 4.5 | developer | medium | 4.3 | Update dashboard loops API route to include auto command name per category. Update existing engine tests to use the new protocol | `plugins/observability/skills/daemon/augur/api/loops/route.ts`, `plugins/observability/skills/daemon/tests/test_adaptive_*.py` |

#### Phase 5: Verification
**Strategy**: PARALLEL then PIPELINE (5.1 ∥ 5.2 ∥ 5.5, then 5.3 ∥ 5.4 ∥ 5.6 ∥ 5.7, then 5.8)
**Agents**:

| Step | Agent | Tier | Depends on | Task |
|------|-------|------|-----------|------|
| 5.1 | validator | low | Phase 4 | Run `npx tsc --noEmit` — verify TypeScript compiles |
| 5.2 | validator | low | Phase 4 | Run `pytest plugins/observability/skills/daemon/tests/` — verify engine tests pass |
| 5.3 | validator | low | 5.1, 5.2 | Run 3+ sample auto commands manually (`auto-lint`, `auto-markers`, `auto-build-health`) via CLI to verify scan/fix protocol works end-to-end |
| 5.4 | validator | low | 5.1, 5.2 | Verify engine startup discovers all ~28 auto commands from augur.yaml files — run discovery and assert count matches Section 7 command map |
| 5.5 | devops | low | Phase 4 | Run `python3 .github/scripts/scan_stale_paths.py --ci` — verify no stale references to retired commands (ops-hygiene, ops-audit, ops-plugin-lint) |
| 5.6 | architect | low | 5.3, 5.4 | Verify ADR-200 intent matches implementation: orchestration layer has zero implementation logic, auto commands have zero trust/budget awareness. Grep for violations |
| 5.7 | validator | low | 5.4 | Verify trust state persistence: run engine once (creates journal + ledger state), restart engine, confirm state survives restart and categories resume at correct trust levels |
| 5.8 | validator | low | 5.6, 5.7 | Run `npm run build` — full production build verification |

### Completion Criteria
- [ ] All phases executed (5 phases, 22 steps)
- [ ] All tests pass (`pytest`, `tsc --noEmit`, `npm run build`)
- [ ] No orphaned files or broken references
- [ ] Stale path scanner clean — zero references to ops-hygiene, ops-audit (old), ops-plugin-lint (old)
- [ ] Impact Manifest validated — zero stale references for renamed commands
- [ ] Engine discovers all ~28 auto commands at startup from decentralized augur.yaml
- [ ] 3+ auto commands work correctly when triggered manually via CLI
- [ ] Trust state persists across engine restarts
- [ ] Architectural boundary holds: engine has zero scan/fix logic, auto commands have zero trust/budget logic
- [ ] ADR status updated to "Accepted" or "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-200-ops-loops-auto-commands-separation.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
