---
status: Implemented
date: '2026-03-13'
deciders:
- User
- Codex
related:
- ADR-176 (Adaptive Loop Engine)
- ADR-200 (Auto-Command Protocol)
- ADR-405 (Adaptive Loop Effectiveness Overhaul)
hub: null
tags:
- adaptive
- loop
- convergence
- automation
- observability
superseded_by: null
---

# ADR-412: Adaptive Loop Adaptivity and Convergence

## Context

ADR-405 improved the loop engine by adding scan health, clearer trust display, and stronger execution semantics. After additional full-cycle work on the live system, a new pattern emerged: the loops can now reach clean runs, but they still waste too much time and budget before converging.

The main failure mode is no longer "the loops do nothing." The main failure mode is "the loops are not adaptive enough about what to do next."

This session exposed seven concrete gaps:

1. Scanner defects are still discovered late and often masquerade as repo debt.
2. Upstream fixes can invalidate downstream categories, but the engine waits until the next cycle to settle.
3. Runtime and environment artifacts are sometimes counted as persistent repo issues.
4. Successful maintenance work is still represented too much like actionable debt.
5. Categories repeatedly rescan the repo instead of focusing on hotspots.
6. Duplicate scanner logic across adaptive and daemon variants drifts apart.
7. Low-trust recurring categories do not infer that their own scanner logic is the problem.

Examples observed in the repository:

- `auto-stale-routes` used the obsolete `src/dashboard` root instead of `apps/dashboard`
- `auto-stale-paths` mixed documentation drift with executable/config drift
- `auto-skill-md` repeatedly churned valid underscore-based skill IDs such as `ai_bridge`
- `auto-test-mcp` imported the repo-local `mcp` package instead of the installed dependency
- `auto-mcp-hygiene` broke when its report path lived outside the repo root
- `auto-perf-profile` treated live `.next/dev` runtime state as repo debt
- `reindex-project` and `reindex-rag` went stale immediately after `auto-skill-md` mutated `SKILL.md`

The current engine needs a stronger model for:

- what counts as actionable debt
- how to infer root cause
- when to patch loop code instead of scanning the repo again
- how to reuse shared repo knowledge
- how to settle dependent categories in one cycle

## Decision

### 1. Pending means unresolved actionable repo debt only

The engine will distinguish between:

- actionable repo defects
- maintenance work
- environment/runtime observations
- scanner defects
- manual report-only debt
- broken categories

Only unresolved actionable repo defects count toward pending totals.

Successful rebuilds, report refreshes, reindexing, and cache cleanup do not count as pending after they succeed.

### 2. Every finding must carry root-cause metadata

Each issue emitted by a category must include:

- `kind`
- `root_cause_type`
- `fingerprint`
- `fixability`

`root_cause_type` values should include at least:

- `repo_bug`
- `scanner_bug`
- `env_runtime`
- `generated_artifact`
- `manual_debt`
- `unknown`

`fingerprint` must be stable across runs so recurrence can be measured precisely.

### 3. The executor will support causal dependency reruns

The engine will maintain a dependency graph between categories.

If a category mutates files or artifacts that feed another category, the downstream category must be rerun in the same cycle before the final pending summary is computed.

This applies especially to chains like:

- `auto-skill-md` → `reindex-project`
- `auto-skill-md` → `reindex-rag`
- `auto-markdowns` → `reindex-rag`
- future seed or code-generation categories that invalidate test or hardening scans

### 4. Recurring low-trust categories enter self-repair mode

If a category shows recurring fingerprints, low trust, or a high ratio of scanner-defect or broken outcomes, the engine must change strategy from "scan the repo" to "repair the category."

Self-repair mode means:

1. inspect the category module, shared helper, tests, and latest report artifact
2. patch scanner assumptions or fix logic
3. add or update regression tests
4. rerun the category immediately

The engine must treat self-repair as a first-class adaptive strategy, not as an ad hoc human intervention.

### 5. The engine will build one shared repo snapshot per cycle

At cycle start, the engine will construct a shared snapshot containing:

- dashboard roots
- discovered skills
- route inventories
- API route inventories
- augur.yaml declarations
- MCP tool inventories
- external data roots
- generated/mirrored surfaces
- active runtime state
- git dirty files

Categories should consume this snapshot instead of re-discovering the same inventory independently.

### 6. Execution becomes two-phase

The engine will run in two phases:

#### Phase A: cheap classification

Build shared inventory and identify:

- changed areas
- recurring fingerprints
- dirty dependency edges
- hotspots
- categories that need deep scans

#### Phase B: targeted deep execution

Run deep scans and fixes only where evidence suggests yield:

- recently changed areas
- recurring hotspots
- downstream invalidations
- categories with recent failures or scanner defects

### 7. Hotspot concentration guides depth

When findings cluster in one subtree, module family, or error family, the next run should zoom into that hotspot instead of repeating broad repo scans.

The engine should persist:

- `hot_paths`
- `hot_patterns`
- `dominant_root_cause`

and use them to prioritize the next cycle.

### 8. Runtime-aware classification is mandatory

The engine must distinguish live runtime state from persistent repo debt.

Examples include:

- active Next dev output in `.next/dev`
- running dev-server lock files
- external vault/cache/log roots
- reachable but dynamic external services

These should be classified as `environment` or ignored when healthy, not counted as actionable repo debt.

### 9. Command evolution may mutate loop strategy

`command-evolution` will expand beyond documentation improvements and may propose or apply low-risk loop strategy mutations, such as:

- dependency edges
- path-root corrections
- ignore-list refinements
- maintenance vs actionable reclassification
- shared-library extraction recommendations
- scan-scope narrowing or widening

These mutations must be evidence-backed and regression-tested when auto-applied.

### 10. Trust will reward convergence, not activity

Trust must rise when categories:

- reduce recurring actionable fingerprints
- stay clean after their own fixes
- stop producing scanner defects
- converge dependent reruns in one cycle

Trust must not rise merely because a category:

- generated a report
- rebuilt an index
- observed healthy runtime state
- returned an empty shallow scan

### 11. Shared logic should be extracted for duplicated categories

Where daemon and adaptive categories duplicate the same logic, the implementation should move into a shared library with thin wrappers.

This is required to reduce divergence and repeated fixes.

## Consequences

### Positive

- pending totals become honest and actionable
- loops converge faster within a single cycle
- fewer cycles are wasted on false positives and scanner defects
- scan time and token use decrease through shared inventory reuse
- categories become capable of adapting their own behavior, not just their difficulty

### Negative

- protocol and executor complexity increases
- categories need richer issue metadata
- the trust ledger becomes more sophisticated
- rollout requires careful migration of existing auto-commands

### Neutral

- not every category needs full self-repair or hotspot logic on day one
- rollout may start with a subset of loops and categories
- some report-only categories will remain report-only, but their output semantics will be clearer

## Implementation Direction

Implementation will proceed in four phases:

### Phase 1: Semantics and convergence

1. split actionable vs maintenance/environment outcomes
2. add root-cause typing and fingerprints
3. add dependency reruns
4. compute pending from unresolved actionable debt only

### Phase 2: Self-adaptation

1. add self-repair mode for recurring low-trust categories
2. update trust scoring to reward issue decay and convergence
3. extend `command-evolution` with strategy mutations

### Phase 3: Performance

1. add shared repo snapshot
2. implement two-phase execution
3. add hotspot-first deepening
4. introduce explicit scan budgets

### Phase 4: Consolidation

1. extract shared implementations for duplicated categories
2. centralize common runtime/path heuristics
3. expand regression coverage for loop-self fixes

## References

- 2026-03-13-adaptive-loop-adaptivity-design.md
- ADR-176-adaptive-loop-engine.md
- ADR-200-ops-loops-auto-commands-separation.md
- ADR-405-adaptive-loop-effectiveness-overhaul.md
