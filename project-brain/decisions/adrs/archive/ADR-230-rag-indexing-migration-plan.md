---
status: Implemented
date: '2026-02-20'
deciders:
- Engineering Team
related:
- ADR-127-human-readable-rag-indexing.md
hub: null
tags:
- phased
- rag
- indexing
- migration
- plan
superseded_by: null
---

# ADR-230: Phased RAG Indexing Migration Plan

## Context

With the recent unification of our RAG engine into `plugins/ai/skills/rag` (defined in ADR-127), we now possess the mechanical tools to rapidly index any plugin in the system via `rag_indexer.py` (which powers symbol extraction, directory summarization, and markdown chunking). However, running this new indexing logic indiscriminately across the entire monorepo could expose unforeseen bugs, generate massive API costs, or create incorrect summarizations due to edge cases in specific plugins.

We need a controlled, phased migration plan to roll out RAG indexing plugin-by-plugin to catch bugs early, refine the prompts, and ensure the system behaves predictably before enabling it globally.

## Decision

We will adopt a three-tiered "Pilot, Evaluate, Scale" migration strategy for indexing all plugins using the new RAG system.

### Phase 1: Single Plugin Pilot (The Learner Loop)
We will begin by targeting exactly ONE high-value plugin (e.g., `plugins/ai/skills/ai_bridge`).
- **Action**: Run the `rag_indexer.py` against this single plugin.
- **Action**: Analyze the output (`symbols.yaml`, `_index.md`, and chunked markdown files) for any bugs, token limits, or inaccuracies.
- **Action**: Fix any identified issues in the `rag` engine scripts and rerun the indexer on the pilot plugin until it reaches zero known bugs and 100% stability.

### Phase 2: Secondary Plugin Evaluation (The Edge Case Loop)
Once Phase 1 is stable, we select a second distinct plugin (e.g., `plugins/dev/skills/developer`).
- **Action**: Run the indexer on this second plugin without modifying the engine.
- **Action**: Evaluate the results to identify distinct edge cases not caught in Phase 1 (e.g., novel folder structures or extreme file sizes).
- **Action**: Fix any new bugs and iterate until this secondary plugin is also flawlessly indexed.

### Phase 3: Full Simultaneous Rollout (The Scale Loop)
With confidence established across two distinct plugin archetypes, we remove the constraints.
- **Action**: Execute a batched indexing run orchestrator to index all remaining plugins (`plugins/dev/*` and `plugins/ai/*`) simultaneously.
- **Action**: Verify the final global index structure is intact and comprehensive.

## Consequences

**Positive**:
- Protects the wider codebase from runaway LLM indexing costs during early bug discovery.
- Allows the RAG team to tune the summarization prompts and symbol extraction logic iteratively.
- Guarantees the stability of the core engine before demanding high throughput.

**Negative**:
- Slows down the immediate availability of full-system RAG capabilities.
- Requires manual oversight during Phases 1 and 2.

**Neutral**:
- The RAG data structure remains localized per plugin as designed in ADR-127.

## Implementation Order

```
Phase 1: Pilot Plugin (ai_bridge)
├── Step 1: Execute `run_indexer` targeting `plugins/ai/skills/ai_bridge`
├── Step 2: Manually audit generated artifacts for correctness
└── Step 3: Implement engine fixes and loop until stable

Phase 2: Secondary Evaluation (developer) (depends on Phase 1)
├── Step 4: Execute `run_indexer` targeting `plugins/dev/skills/developer`
├── Step 5: Audit artifacts for new edge cases
└── Step 6: Implement fixes and loop until stable

Phase 3: Global Rollout (depends on Phase 2)
└── Step 7: Execute a bulk indexing script targeting all remaining plugins
```

## Alternatives Considered

1. **Big Bang Migration (All at once)**: Rejected. Running the indexer everywhere immediately makes it nearly impossible to isolate bugs to specific file types or structures, and drastically risks wasting LLM tokens on bad prompts.
2. **Opt-in per Plugin**: Rejected. We want RAG available globally; making it opt-in spreads the migration timeline out indefinitely and creates an inconsistent developer experience.

## References

- ADR-127-human-readable-rag-indexing.md

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-230: Phased RAG Indexing Migration Plan**.

Read the full ADR: `docs/decisions/ADR-230-rag-indexing-migration-plan.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-129-rag-migration", description="Implementing ADR-230: Phased RAG Indexing Migration Plan")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-129-rag-migration", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-129 team.
        Read your profile: .claude/agents/{role}.md
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

**Team name**: `adr-129-rag-migration`

#### Phase 1: Pilot Plugin
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Target indexer script exclusively on `plugins/ai/skills/ai_bridge`. Audit the `symbols.yaml` and `_index.md` outputs. Detect and fix any bugs in `plugins/ai/skills/rag/scripts/*`. Loop this process until stable. | `plugins/ai/skills/rag/scripts/*` |

#### Phase 2: Secondary Evaluation
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | high | Target indexer script on a second plugin (`plugins/dev/skills/developer`). Audit outputs for novel edge cases. Fix bugs in the RAG scripts and loop until stable. | `plugins/ai/skills/rag/scripts/*` |

#### Phase 3: Global Rollout
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | devops | low | Construct and execute a script that loops over all remaining subdirectories inside `plugins/dev/*` and `plugins/ai/*` to run the indexer concurrently. | `plugins/ai/skills/rag/scripts/rag_indexer.py` |

#### Final Phase: Verification
**Strategy**: PIPELINE
**Agents**:
| Step | Agent | Tier | Task |
|------|-------|------|------|
| 4.1 | validator | low | Run all RAG tests, verify no regressions |
| 4.2 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest plugins/ai/skills/rag/tests/`)
- [ ] No orphaned files or broken references
- [ ] ADR status updated to "Accepted" or "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-230-rag-indexing-migration-plan.md

# Option 2: Paste this prompt into Claude Code
```
