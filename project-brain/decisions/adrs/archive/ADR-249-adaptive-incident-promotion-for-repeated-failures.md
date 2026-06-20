---
status: Implemented
date: '2026-03-06'
deciders:
- Gur Sannikov
- Claude
related: []
hub: null
tags:
- adaptive
- incident
- promotion
- repeated
- failures
superseded_by: null
---

# ADR-249: Adaptive Incident Promotion for Repeated Failures

**Related ADRs**: ADR-102 (Adaptive Slash Commands), ADR-176 (Adaptive Loop Engine), ADR-181 (Adaptive Loops Consolidation), ADR-200 (Ops-Loops / Auto-Commands Separation), ADR-245 (Centralized Ops-Loops Issue Inventory), ADR-282 (Auto-Loop Consolidation)

## Context

The current adaptive loop stack records blockers and learnings, but it still treats most failures as isolated free-text strings. In practice this makes the system symptom-oriented:

- `plugins/ai/skills/ai_bridge/scripts/adaptive/execution_tracker.py` stores `blockers` and `learnings` as plain text with no durable incident identity.
- `plugins/ai/skills/ai_bridge/scripts/adaptive/analyze_execution.py` reduces recurring setup failures to generic advice such as "add an existence check" or "add a hint", even when the same root cause happens repeatedly across commands and worktrees.
- `plugins/ai/skills/ai_bridge/scripts/adaptive/adaptive_loop.py` can rewrite skills and chains, but it has no concept of cross-session recurrence, owner-path promotion, or incident deduplication.
- `scripts/worktree-launch.sh`, `wrap.sh`, `src/dashboard/scripts/start-dev.sh`, and `src/dashboard/lib/mcp/MCPBridge.ts` all participate in worktree/bootstrap/runtime startup, but they do not share one machine-readable preflight contract.
- Adaptive-growth reporting can generate backlog markdown, but it does not surface recurring incidents as first-class systemic debt.

The result is repeated environment failures that the system re-discovers instead of learning once and promoting to a root-cause fix:

- missing `runtime/` scaffolding in fresh worktrees
- missing shared `.venv`, `.venv-test`, or `src/dashboard/node_modules` in gitignored worktree state
- inherited `AUGUR_ROOT` drift back to the main repo
- MCP lock contention and port-collision issues
- worktree route/bootstrap drift that only shows up after startup or UI validation

Augur already has the right conceptual tools to fix this:

- ADR-102 introduced adaptive execution logs under `runtime/command-evolution/`
- ADR-176 and ADR-181 established the unified adaptive loop engine and post-execution triggering
- `TODO_` markers are the accepted in-place ownership mechanism for durable issues
- adaptive-growth APIs and backlog output already exist as the user-facing surface for systemic debt

What is missing is the promotion layer between "raw execution noise" and "root-cause action".

## Decision

We will add an incident normalization and promotion layer to the adaptive command stack, with v1 focused on infrastructure/worktree failures and a generic data model that later loops can reuse.

### 1. Introduce structured incidents in command evolution

Add a new incident layer under `plugins/ai/skills/ai_bridge/scripts/adaptive/` that sits between raw execution tracking and improvement generation.

Execution logs will gain a first-class `incidents` array. Each incident record will include:

- `fingerprint`
- `category`
- `severity`
- `owner_path`
- `first_seen_at`
- `last_seen_at`
- `occurrences`
- `commands`
- `worktrees`
- `sample_errors`
- `auto_heal_status`
- `verify_status`

The adaptive analyzer will stop treating known recurring setup failures as generic missing-file checks. Instead, it will classify them into stable incident fingerprints with explicit remediation policy and ownership metadata.

### 2. Ship v1 infra-first fingerprint rules

The first release will target the recurring worktree/bootstrap/runtime failures already observed in active use:

- missing `runtime/`
- missing shared `.venv`
- missing shared `.venv-test`
- missing `src/dashboard/node_modules`
- inherited `AUGUR_ROOT` drift
- MCP lock contention
- worktree port collision
- worktree route/bootstrap drift

This is intentionally narrower than a generic "all failures everywhere" redesign. The goal is to solve the most repetitive, user-visible setup failures first while using a generic enough incident schema that build, UI, and command failures can register their own fingerprints later.

### 3. Standardize startup with a shared preflight contract

All worktree/bootstrap entry points will use one shared bootstrap-plus-verify contract.

Initial adopters:

- `scripts/worktree-launch.sh`
- `wrap.sh`
- `src/dashboard/scripts/start-dev.sh`
- `src/dashboard/lib/mcp/MCPBridge.ts`

The contract must report:

- `checks`
- `repairs_applied`
- `verify_passed`
- `incidents_detected`

The preflight will verify:

- worktree marker presence
- runtime scaffolding
- shared env links
- dashboard dependency availability
- worktree-local `AUGUR_ROOT`
- worktree-local `AUGUR_RUNTIME`
- unique `MCP_PORT`
- unique MCP client identity

When a failure is safe to repair, the caller performs **Bootstrap + Verify**:

1. apply the repair
2. re-run verification
3. record the incident outcome as healed or unresolved

For v1 dashboard dependency repair, `.venv` and `.venv-test` may be shared from the main repo, but `src/dashboard/node_modules` must remain local to the active worktree. The safe repair for missing dashboard dependencies is a worktree-local install from the checked-in lockfile, not a cross-root symlink.

Unsafe failures stop execution and are recorded as unresolved incidents without improvisational fixes.

### 4. Promote repeated incidents to durable ownership

Incident promotion will be added to adaptive command execution and `/learn execute`.

Promotion thresholds:

- promote when the same fingerprint occurs `>=3` times in `7` days, or
- promote when the same fingerprint occurs across `>=2` commands or worktrees within `14` days

Promotion behavior:

- write one deduplicated `TODO_` marker at the incident owner path
- use `TODO_BUG(integration/high)` when the failure still impacts user-visible behavior after auto-heal
- use `TODO_CLEANUP` when the root cause is structural/tooling debt
- use `TODO_OUTDATED` when the problem is that docs or runbooks diagnose symptoms but do not prevent them

Owner-path resolution order for v1:

1. the executable bootstrap caller or owning module that can prevent recurrence
2. the shared helper/module that defines the failing behavior
3. the closest workflow/topic doc when no single code owner exists

If a single code owner cannot be identified, promotion attaches to the closest behavior-defining workflow or topic doc instead of scattering markers across incidental call sites.

### 5. Surface incidents in adaptive-growth reporting

Adaptive-growth reporting will become the first user-facing summary surface for systemic incidents.

`plugins/dev/skills/devops/scripts/adaptive_growth.py` and the existing setup/adaptive-growth APIs will expose:

- top recurring fingerprints
- unresolved promoted incidents
- promoted TODO markers already created

Response payloads will add:

- `recurringIncidents`
- `promotedTodos`

In v1, adaptive-growth is a reporting surface only. It reads promoted incident state and includes it in backlog/reporting output, but it is not a second incident engine and does not own recurrence logic.

### 6. Treat debugging docs as secondary, not primary, control

Existing runbooks such as `docs/agent-topics/DEBUGGING.md` remain valuable, but they are no longer the primary learning mechanism for repeated operational pain.

The new rule is:

- runbooks explain how to diagnose
- incidents explain what keeps repeating
- promotion decides where the root-cause ownership must live

## Consequences

### Positive

- Repeated setup failures become one tracked root cause instead of many loosely worded blockers.
- The system can distinguish transient one-offs from recurring operational debt.
- Worktree bootstrap becomes self-healing for safe cases and explicitly unresolved for unsafe cases.
- Durable ownership moves into `TODO_` markers at source-of-truth files instead of staying in runtime logs only.
- Adaptive-growth becomes more useful because it can show systemic operational debt, not just generic generated tasks.

### Negative

- The command-evolution stack becomes more complex: incident schema, aggregation, thresholds, and promotion logic all need tests and maintenance.
- False-positive fingerprinting can create noisy promotions if normalization is too broad.
- Some startup flows will become stricter because unresolved preflight failures must stop instead of silently limping forward.
- Adding owner-path logic introduces judgment about where a systemic problem "belongs".

### Neutral

- Existing `blockers` and `learnings` remain as human-readable summaries, but they are no longer the canonical input for recurrence logic.
- The incident model starts infra-first but is intended to be reused by other loops later.
- Runtime aggregation stays under `runtime/command-evolution/`; it does not replace plugin-owned source files as the real place to fix issues.

## Implementation Order

### Phase 1: Incident Data Model and Aggregation

1. Extend execution tracking to emit structured `incidents` alongside existing blocker and learning text.
2. Add incident normalization, fingerprint rules, and aggregated incident storage under `runtime/command-evolution/incidents/`.
3. Update analyzer logic so known fingerprints map to explicit remediation and promotion metadata instead of generic hints.

### Phase 2: Shared Preflight and Safe Auto-Heal

1. Define a shared preflight contract and helper implementation for bootstrap callers.
2. Integrate the contract into worktree launch, shell wrapper, dashboard startup, and MCP bridge startup.
3. Implement Bootstrap + Verify behavior for safe repairs and unresolved incident recording for unsafe failures.

### Phase 3: Promotion to TODO Ownership

1. Add recurrence thresholds and deduplicated promotion logic.
2. Integrate promotion into adaptive execution and `/learn execute`.
3. Resolve owner-path placement rules and fallback behavior for no-clear-owner cases.

### Phase 4: Adaptive-Growth and Reporting

1. Extend adaptive-growth generation to include recurring incidents and promoted TODOs.
2. Extend setup/adaptive-growth API responses to expose incident summaries directly.
3. Ensure recurring incidents show up in backlog/reporting flows without introducing a second central source of truth.

### Phase 5: Verification and Calibration

1. Add unit and integration coverage for normalization, aggregation, thresholds, and auto-heal verification.
2. Run worktree/bootstrap regression scenarios and MCP lock/port collision scenarios.
3. Calibrate fingerprint rules and thresholds to avoid TODO spam from one-off incidents.

## Alternatives Considered

### Alternative 1: Keep the current blocker/learning model and add more hints

Rejected. This preserves the symptom-oriented failure mode. Rephrasing repeated incidents as better hints still does not give them identity, ownership, thresholds, or cross-session memory.

### Alternative 2: Build a generic incident framework for every loop from day one

Rejected for v1. The schema can be generic, but the first shipping scope should be infra-first. Worktree/bootstrap/runtime failures are the highest-frequency operational pain and provide a smaller, testable target.

### Alternative 3: Auto-create ADRs for repeated incidents

Rejected. This is too heavy for recurring operational debt and duplicates the established `TODO_` ownership workflow. ADRs are for architectural decisions, not every repeated bootstrap failure.

### Alternative 4: Use a permanent centralized incident backlog file instead of owner-path markers

Rejected. Central inventory is useful for reporting, but it is a poor ownership mechanism. The system already uses `TODO_` markers to attach responsibility where the issue actually lives.

## References

- [ADR-102: Adaptive Slash Commands](ADR-102-adaptive-slash-commands.md)
- [ADR-176: Adaptive Loop Engine](ADR-176-adaptive-loop-engine.md)
- [ADR-181: Adaptive Loops Consolidation](ADR-181-adaptive-loops-consolidation.md)
- [ADR-200: Ops-Loops / Auto-Commands Separation](ADR-200-ops-loops-auto-commands-separation.md)
- [ADR-245: Centralized Ops-Loops Issue Inventory](ADR-245-ops-loops-centralized-issue-inventory-2026-03-05.md)
- ADR-246: Auto-Loop Consolidation
- `docs/plans/2026-02-28-adaptive-loops-consolidation-design.md`
- `docs/plans/2026-02-28-adaptive-loop-engine-plan.md`
- `docs/agent-topics/DEBUGGING.md`
- `docs/guides/markers.md`

## Impact Manifest

```yaml
impact:
  apis_changed:
    - function: "ExecutionTracker.save"
      module: "plugins.ai.skills.ai_bridge.scripts.adaptive.execution_tracker"
      breaking: false
    - function: "analyze_execution"
      module: "plugins.ai.skills.ai_bridge.scripts.adaptive.analyze_execution"
      breaking: false
    - function: "generate_tasks"
      module: "plugins.dev.skills.devops.scripts.adaptive_growth"
      breaking: false
  patterns_deprecated:
    - grep: "add_blocker\\(\"[^\"]+\"\\)"
      replacement: "Record structured incidents in addition to human-readable blockers"
    - grep: "Add pre-check to detect and handle:"
      replacement: "Normalize repeated failures into incident fingerprints with remediation policy"
  files_affected:
    - glob: "plugins/ai/skills/ai_bridge/scripts/adaptive/*.py"
    - glob: "plugins/ai/skills/ai_bridge/commands/ops-learn.md"
    - glob: "scripts/worktree-launch.sh"
    - glob: "wrap.sh"
    - glob: "src/dashboard/scripts/start-dev.sh"
    - glob: "src/dashboard/lib/mcp/MCPBridge.ts"
    - glob: "plugins/dev/skills/devops/scripts/adaptive_growth.py"
    - glob: "src/dashboard/app/api/setup/adaptive-growth/**/*.ts"
    - glob: "docs/agent-topics/DEBUGGING.md"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `/adr write`. Edit if needed before running.

**Team name**: `adr-249-incident-promotion`

### Phase 1: Incident Model
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | architect | medium | Define the incident schema, fingerprint taxonomy, thresholds, and owner-path rules for infra-first v1 | `plugins/ai/skills/ai_bridge/scripts/adaptive/*.py`, `docs/guides/markers.md` |
| 1.2 | developer | medium | Extend execution tracking and saved runtime artifacts to include structured incidents and aggregated incident state | `plugins/ai/skills/ai_bridge/scripts/adaptive/execution_tracker.py`, new incident helpers |
| 1.3 | developer | medium | Refactor analysis so known setup failures map to incident fingerprints and remediation metadata instead of generic hints | `plugins/ai/skills/ai_bridge/scripts/adaptive/analyze_execution.py`, `plugins/ai/skills/ai_bridge/scripts/adaptive/adaptive_loop.py` |

### Phase 2: Bootstrap and Verify
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | devops | medium | Define and implement the shared preflight/bootstrap+verify contract for worktree launch and shell startup | `scripts/worktree-launch.sh`, `wrap.sh` |
| 2.2 | developer | medium | Integrate the same preflight contract into dashboard startup and worktree path/runtime validation | `src/dashboard/scripts/start-dev.sh`, `src/dashboard/lib/paths.ts` |
| 2.3 | developer | medium | Integrate MCP startup checks and incident reporting for root drift, client identity, and lock/port contention | `src/dashboard/lib/mcp/MCPBridge.ts`, related MCP startup helpers |

### Phase 3: Promotion and Learning
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Add recurrence aggregation, threshold checks, and deduplicated TODO promotion logic | `plugins/ai/skills/ai_bridge/scripts/adaptive/*.py` |
| 3.2 | developer | low | Integrate promotion into `/learn execute` and align wording with TODO marker rules | `plugins/ai/skills/ai_bridge/commands/ops-learn.md`, related learn workflow files |
| 3.3 | architect | low | Update debugging and marker guidance so incident promotion is the primary root-cause path and docs act as runbooks | `docs/agent-topics/DEBUGGING.md`, `docs/guides/markers.md` |

### Phase 4: Reporting Surfaces
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Extend adaptive-growth generation with recurring incident and promoted TODO summaries | `plugins/dev/skills/devops/scripts/adaptive_growth.py` |
| 4.2 | developer | medium | Extend setup/adaptive-growth APIs to expose recurring incidents and promoted TODOs | `src/dashboard/app/api/setup/adaptive-growth/route.ts`, `src/dashboard/app/api/setup/adaptive-growth/summary/route.ts`, related adaptive-growth API routes |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run unit tests for fingerprint normalization, aggregation thresholds, and TODO dedupe |
| V.2 | validator | medium | Run integration scenarios for fresh worktree bootstrap, poisoned `AUGUR_ROOT`, missing env links, MCP lock contention, and port collision |
| V.3 | validator | low | Verify adaptive-growth responses include `recurringIncidents` and `promotedTodos` without breaking existing consumers |
| V.4 | architect | low | Verify the implementation solves repeated root causes rather than adding another layer of generic hints |

### Completion Criteria
- [ ] Execution logs persist structured incidents
- [ ] Aggregated incident state is recorded under `runtime/command-evolution/incidents/`
- [ ] Known infra/setup failures map to stable fingerprints
- [ ] Shared preflight contract is used by all v1 bootstrap callers
- [ ] Safe bootstrap failures auto-heal and re-verify
- [ ] Repeated incidents promote exactly one deduplicated TODO marker per owner path
- [ ] Adaptive-growth surfaces recurring incidents and promoted TODOs
- [ ] Unit and integration tests cover normalization, thresholds, and bootstrap scenarios
- [ ] ADR status updated to Accepted/Implemented after validation
