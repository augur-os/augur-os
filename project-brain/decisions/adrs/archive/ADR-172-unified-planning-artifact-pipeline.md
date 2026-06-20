---
status: Implemented
date: '2026-02-27'
deciders:
- Gur Sannikov
related:
- ADR-171 (bidirectional plugin sync — triggered this discovery)
- ADR-098 (unified command output)
- ADR-102 (adaptive slash commands)
hub: null
tags:
- unified
- planning
- artifact
- pipeline
superseded_by: null
---

# ADR-172: Unified Planning Artifact Pipeline

## Context

Augur has two disconnected planning pipelines that produce overlapping artifacts:

**Pipeline A** (superpowers plugins — external, cannot modify):
```
/brainstorming → docs/plans/YYYY-MM-DD-<topic>-design.md
      → /writing-plans → docs/plans/YYYY-MM-DD-<feature>-plan.md
            → /executing-plans (or /subagent-driven-development)
```

**Pipeline B** (Augur-native — project-owned):
```
/write-adr → docs/decisions/ADR-NNN-<slug>.md (with embedded implementation prompt)
      → /implement-adr (creates agent team, executes phases)
```

When both pipelines run for the same feature (as happened with ADR-171), three artifacts are produced with heavily overlapping content:

| Artifact | Source | Overlap with ADR |
|----------|--------|-----------------|
| `docs/plans/*-design.md` | `/brainstorming` | Context + Decision sections (architecture, components, data flow, alternatives) |
| `docs/plans/*-plan.md` | `/writing-plans` | Implementation Prompt section (phases, steps, file paths, agent roles) |
| `docs/decisions/ADR-NNN.md` | `/write-adr` | Contains ALL of the above plus consequences, impact manifest, references |

**Quantified waste**: ADR-171 produced 1,728 lines across 3 files. The design doc (145 lines) is a subset of the ADR's Context+Decision. The plan (520 lines) overlaps with the ADR's Implementation Prompt. ~40% of total output is redundant.

**Root cause**: The two pipelines have no integration point. `/brainstorming` hard-codes its terminal state as "invoke writing-plans" — it never considers that `/write-adr` might absorb its output. `/write-adr` rebuilds architecture from scratch even when brainstorming already explored it.

**Claude Code best practices alignment**: Official documentation recommends **explore → plan → implement** with subagents and task coordination. Skills should be reference material or task instructions, not choreographed pipelines producing sequential artifacts. The industry standard (RFC/ADR process) uses ONE canonical document per decision.

## Decision

Unify the two pipelines into a single flow where the **ADR is always the single source of truth** and brainstorming output is a transient exploration phase, not a permanent artifact.

### Component 1: Unified Flow Definition

```
Phase 1: Explore (/brainstorming)
  └─ Q&A, 2-3 approaches, user approval
  └─ Output: transient design draft (docs/plans/*-design.md)
  └─ Terminal state: invoke /write-adr (not /writing-plans)

Phase 2: Decide (/write-adr)
  └─ Absorbs brainstorming's design draft if it exists
  └─ Output: docs/decisions/ADR-NNN.md (canonical artifact)
  └─ Cleans up transient design draft after absorption

Phase 3: Detail (optional /writing-plans)
  └─ Only when ADR implementation prompt needs TDD-granular tasks
  └─ Output: docs/plans/*-plan.md (references ADR, not design doc)
  └─ Header includes: "Implements ADR-NNN"

Phase 4: Execute (/implement-adr OR /executing-plans)
  └─ Primary: /implement-adr (reads ADR prompt section)
  └─ Alternative: /executing-plans (reads detailed plan)
```

### Component 2: Modify /write-adr Skill

**Action**: Update `plugins/ai/skills/ai_bridge/augur/data/skills/write-adr/SKILL.md`

Add a new **Phase 0: Check for existing brainstorming output** before the current Phase 1:

```markdown
## Phase 0: Absorb Brainstorming (Conditional)

Before gathering context, check if brainstorming already ran for this feature:

1. Scan `docs/plans/` for recent `*-design.md` files (within last 24h or matching topic keywords)
2. If found:
   - Read the design doc
   - Skip Phase 1 (gather context) — brainstorming already explored the codebase
   - Skip Phase 2 Section 2 (Context) questions — absorb the design doc's architecture, approaches, and decisions directly into the ADR's Context and Decision sections
   - Proceed to Phase 2 Section 3 (Consequences) and beyond
3. If not found:
   - Proceed with standard Phase 1 (gather context) and Phase 2 (write ADR) as normal
4. After the ADR is written and committed:
   - Delete the transient design doc
   - Log: "Absorbed design doc into ADR-NNN, removed transient artifact"
```

### Component 3: Artifact Lifecycle Convention

Add to `CLAUDE.md` critical rules or `docs/agent-topics/WORKFLOWS.md`:

```markdown
## Planning Artifact Convention (ADR-172)

**Single source of truth**: The ADR is the canonical artifact for any architectural decision.

**Transient artifacts**: Files in `docs/plans/*-design.md` produced by `/brainstorming` are transient drafts. They are:
- Absorbed into the ADR by `/write-adr` Phase 0
- Deleted after absorption
- Never referenced by other artifacts after the ADR exists

**Optional detail**: Files in `docs/plans/*-plan.md` produced by `/writing-plans` are optional TDD-granular execution guides. They:
- Include header: "Implements ADR-NNN" with a reference to the ADR
- Are only created when the ADR's Implementation Prompt section needs more granular task breakdown
- Are the execution guide; the ADR remains the decision record

**Artifact hierarchy**:
1. ADR (always exists, canonical) — `docs/decisions/ADR-NNN.md`
2. Plan (optional, references ADR) — `docs/plans/YYYY-MM-DD-*-plan.md`
3. Design draft (transient, deleted after ADR absorbs) — `docs/plans/YYYY-MM-DD-*-design.md`
```

### Component 4: Modify /brainstorming Terminal State

The `/brainstorming` skill is external (superpowers plugin) and cannot be modified directly. However, the Augur bridge can override behavior via:

**Option A**: Add a project-level CLAUDE.md instruction that overrides brainstorming's hard-coded terminal state:

```markdown
## Brainstorming Override (ADR-172)

After /brainstorming completes and saves its design doc:
- If the work warrants an ADR (architectural decision, multi-file change, new capability):
  invoke /write-adr instead of /writing-plans
- If the work is a simple feature (single file, no architectural implications):
  invoke /writing-plans as brainstorming instructs
```

**Option B**: Create a thin wrapper skill `/design` that calls brainstorming then routes to the appropriate next step.

**Recommended**: Option A — minimal change, works immediately, no new skill needed.

### Component 5: Plan File Header Convention

**Action**: When `/writing-plans` runs after an ADR exists, its output must reference the ADR:

```markdown
# [Feature Name] Implementation Plan

> **Implements**: ADR-NNN — [ADR Title]
> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans

**Goal:** [from ADR Decision section]
**Architecture:** [from ADR Decision section]
```

This is enforced via a CLAUDE.md instruction since the writing-plans skill is external.

## Consequences

### Positive

- **One canonical artifact per decision** — aligns with industry RFC/ADR standards
- **~40% reduction in redundant output** — design doc content absorbed, not duplicated
- **Clearer artifact lifecycle** — transient vs canonical vs optional is explicit
- **Claude Code aligned** — follows explore → plan → implement pattern
- **No external plugin modifications required** — uses CLAUDE.md overrides for superpowers skills
- **Backwards compatible** — existing ADRs and plans are unaffected

### Negative

- **CLAUDE.md override may be fragile** — superpowers plugin updates could change brainstorming's behavior, making the override stale
- **24h heuristic for design doc detection** is imprecise — could miss design docs from longer brainstorming sessions or pick up unrelated ones
- **Developers must remember the convention** — no automated enforcement (yet)

### Neutral

- External plugins (superpowers) remain unmodified — this is a project-level adaptation
- Existing `docs/plans/` directory retains its purpose for optional detailed plans
- `/implement-adr` and `/executing-plans` both remain valid execution paths

## Implementation Order

```
Phase 1: Convention & Documentation
├── Step 1.1: Add "Planning Artifact Convention" to WORKFLOWS.md
├── Step 1.2: Add "Brainstorming Override" to CLAUDE.md critical rules
└── Step 1.3: Add plan file header convention to CLAUDE.md

Phase 2: Modify /write-adr Skill
├── Step 2.1: Add Phase 0 (absorb brainstorming) to write-adr SKILL.md
├── Step 2.2: Add design doc cleanup logic (delete after absorption)
└── Step 2.3: Update Phase 2 to skip redundant context gathering when design absorbed

Phase 3: Clean Up ADR-171 Artifacts
├── Step 3.1: Delete docs/plans/2026-02-27-bidirectional-plugin-sync-design.md (transient)
├── Step 3.2: Update docs/plans/2026-02-27-bidirectional-plugin-sync-plan.md header to reference ADR-171
└── Step 3.3: Verify ADR-171 is self-contained (no broken references to deleted design doc)

Phase 4: Verification
├── Step 4.1: Run sync_agents.py to regenerate write-adr skill across IDEs
└── Step 4.2: Verify CLAUDE.md changes propagate to all adapters
```

## Alternatives Considered

### Alternative A: Modify Superpowers Plugins Directly

Fork the superpowers plugin and change brainstorming's terminal state to route to `/write-adr`. Change writing-plans to check for existing ADRs.

**Rejected because**: Superpowers is an external plugin maintained by Anthropic. Forking creates a maintenance burden and loses upstream improvements. CLAUDE.md overrides achieve the same effect without forking.

### Alternative B: Create a Unified /design-to-adr Skill

Single skill that combines brainstorming + write-adr into one flow. No separate invocations.

**Rejected because**: Over-engineering. The existing skills work well individually — the problem is coordination, not capability. A CLAUDE.md convention and Phase 0 absorption in write-adr solve the coordination problem without replacing working skills.

### Alternative C: Keep All Three Artifacts

Accept the duplication as documentation at different abstraction levels: design (intent), ADR (decision), plan (execution).

**Rejected because**: Violates DRY principle. The design doc adds no information beyond what the ADR contains. Maintenance cost of keeping three artifacts in sync exceeds the value of separate abstraction levels.

## References

- ADR-171: Bidirectional plugin sync — case study that exposed this duplication
- ADR-098: Unified command/skill output — precedent for consolidating duplicate outputs
- ADR-102: Adaptive slash commands — self-improving skill pattern
- Claude Code best practices: explore → plan → implement with subagents
- Industry RFC/ADR standards: one canonical document per decision
- `plugins/ai/skills/ai_bridge/augur/data/skills/write-adr/SKILL.md` — primary modification target
- `docs/agent-topics/WORKFLOWS.md` — convention documentation target

## Impact Manifest

```yaml
impact:
  files_affected:
    - glob: "plugins/ai/skills/ai_bridge/augur/data/skills/write-adr/SKILL.md"
    - glob: "docs/agent-topics/WORKFLOWS.md"
    - glob: "plugins/ai/skills/ai_bridge/augur/data/agent-rules.md"
  patterns_deprecated:
    - grep: "docs/plans/.*-design\\.md"
      replacement: "Transient artifact — absorbed into ADR by /write-adr Phase 0"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-172: Unified Planning Artifact Pipeline**.

Read the full ADR: `docs/decisions/ADR-172-unified-planning-artifact-pipeline.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-172-artifact-pipeline", description="Implementing ADR-172: Unified Planning Artifact Pipeline")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-172-artifact-pipeline", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-172-artifact-pipeline team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion
6. **Dependencies**: PIPELINE phases → use task blocking
7. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-172-artifact-pipeline`

#### Phase 1: Convention & Documentation
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Add "Planning Artifact Convention (ADR-172)" section to WORKFLOWS.md — document artifact hierarchy (ADR canonical, plan optional, design transient), lifecycle rules, and header conventions | `docs/agent-topics/WORKFLOWS.md` |
| 1.2 | developer | low | Add "Brainstorming Override (ADR-172)" to agent-rules.md critical rules section — after brainstorming, route to /write-adr for architectural work, /writing-plans for simple features | `plugins/ai/skills/ai_bridge/augur/data/agent-rules.md` |

#### Phase 2: Modify /write-adr Skill
**Strategy**: PIPELINE (depends on Phase 1)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Add Phase 0 (Absorb Brainstorming) to write-adr SKILL.md — scan docs/plans/ for recent *-design.md, if found: read it, skip Phase 1 context gathering, absorb architecture/approaches into ADR Context+Decision, delete design doc after ADR committed. Include 24h recency heuristic and keyword matching. | `plugins/ai/skills/ai_bridge/augur/data/skills/write-adr/SKILL.md` |
| 2.2 | developer | low | Update Phase 2 of write-adr to note: "If Phase 0 absorbed a design doc, the Context section is pre-populated — focus on Consequences, Alternatives, and Implementation Order" | `plugins/ai/skills/ai_bridge/augur/data/skills/write-adr/SKILL.md` |

#### Phase 3: Clean Up ADR-171 Artifacts
**Strategy**: PIPELINE (depends on Phase 2)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | devops | low | Delete `docs/plans/2026-02-27-bidirectional-plugin-sync-design.md` (transient artifact now absorbed into ADR-171) | `docs/plans/2026-02-27-bidirectional-plugin-sync-design.md` |
| 3.2 | devops | low | Update `docs/plans/2026-02-27-bidirectional-plugin-sync-plan.md` header to add: `> **Implements**: ADR-171 — Bidirectional Claude Plugin Sync` | `docs/plans/2026-02-27-bidirectional-plugin-sync-plan.md` |
| 3.3 | devops | low | Remove reference to design doc from ADR-171 References section (line: `Design doc: docs/plans/2026-02-27-bidirectional-plugin-sync-design.md`) | `docs/decisions/ADR-171-bidirectional-plugin-sync.md` |

#### Phase 4: Sync & Verification
**Strategy**: PIPELINE (depends on Phase 3)

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | devops | low | Run `python plugins/ai/skills/ai_bridge/scripts/sync_agents.py --all` to regenerate write-adr skill and CLAUDE.md across all IDEs |
| V.2 | validator | low | Verify write-adr SKILL.md contains Phase 0 (absorb brainstorming) |
| V.3 | validator | low | Verify CLAUDE.md contains brainstorming override convention |
| V.4 | validator | low | Verify ADR-171 has no broken references to deleted design doc |
| V.5 | devops | low | Update ADR-172 status from Proposed to Implemented |

### Completion Criteria
- [ ] All phases executed
- [ ] WORKFLOWS.md contains artifact lifecycle convention
- [ ] agent-rules.md contains brainstorming override
- [ ] write-adr SKILL.md contains Phase 0 (absorb brainstorming)
- [ ] ADR-171 design doc deleted, plan updated with ADR reference
- [ ] sync_agents.py regenerated all IDE outputs
- [ ] ADR-172 status updated to Implemented

### How to Run
```
# Option 1: Use /implement-adr
/implement-adr docs/decisions/ADR-172-unified-planning-artifact-pipeline.md

# Option 2: Paste this prompt into Claude Code
```
