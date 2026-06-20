---
status: Implemented
date: '2026-02-22'
deciders:
- Augur Team
related:
- ADR-126 (Generic Plugin Template Refactor)
- ADR-130 (Action Button Dispatch Modes)
- ADR-046 (Chain-to-Command Bridge)
- ADR-085 (RAG Three-Tier Index)
hub: null
tags:
- chain
- reference
- cleanup
- prompt
- consolidation
superseded_by: null
---

# ADR-138: Chain Reference Cleanup and Prompt Consolidation

## Context

ADR-126 established that all workflow orchestration moves from `chains/*.yaml` into SKILL.md using Claude's native markdown patterns. ADR-130 unified the chain/action systems under a single `dispatch` field with distributed action YAMLs. Both ADRs were implemented — **zero chain YAML files exist on disk** (`find plugins -path "*/chains/*.yaml"` returns empty).

However, the migration left behind **three categories of technical debt**:

### Problem 1: Ghost Chain References (15+ files)

Code, scripts, and agent-facing documentation still reference `plugins/*/skills/*/chains/*.yaml` as if chain YAML files exist. This causes agents to repeatedly search for nonexistent files, report "0 chains found", and miss the actual orchestration surface (SKILL.md workflows + action YAMLs).

**Live code** (executes but finds 0 files every time):
- `chain_executor.py` — `load_chains_from_yaml()` scans `plugins/*/skills/*/chains/*.yaml`
- `chain_bridge.py` — `scan_chains()` rglobs `chains/*.yaml`
- `project_indexer.py` — RAG indexer scans `chains/*.yaml` for chain metadata
- `generate_chain_index.py` — CI script generates empty chain index

**MCP tools** (broken or stale):
- `src/mcp/augur_mcp/chains/tools.py` — `list_chains_impl()` reads from `.agent/chains/` (broken symlink); `execute_chain_impl()` imports from `plugins/core/skills/executor` (stale path, should be `plugins/orchestration`); `list_action_buttons_impl()` reads from eliminated `config/action_buttons.yaml`
- `src/mcp/augur_mcp/infrastructure/chains_ext.py` — chain extension module

**Agent-facing docs** (directly causes recurring agent confusion):
- `ops-optimize.md` — references `chains/*.yaml` in 5 places
- `orch-chain.md` — says content is "auto-generated from chain YAML files"
- `chain-metadata/README.md` — documents discovery pattern `plugins/*/skills/*/chains/*.yaml`
- `architecture.md` — states "orchestrator discovers chains by scanning `chains/*.yaml`"

**ADRs** (historical — not changed, but listed for awareness):
- ADR-022, ADR-029, ADR-046, ADR-085, ADR-110 reference `chains/*.yaml`

### Problem 2: Prompt Directory Fragmentation

ADR-126 intended all orchestration to live in SKILL.md. ADR-130 correctly separated trigger metadata (action YAML) from orchestration, but during implementation, a `prompts/` directory pattern emerged as a third location for agent instructions.

Current state — orchestration lives in **three places**:

| Location | Purpose (intended) | Count | Example |
|----------|-------------------|-------|---------|
| SKILL.md `## Workflow:` sections | Multi-step MCP orchestration (ADR-126) | 17 skills | `developer/SKILL.md § Auto Fix Markers` |
| `prompts/*.md` files | Agent instructions for `ide`-dispatched actions | 15 files | `developer/prompts/fix-bug.md` (64 lines) |
| Inline `prompt:` in action YAML | Short single-purpose instructions | 28 actions | `prompt: "Draft a professional reply..."` |

The `prompts/` directory is **not in ADR-126's design**. An agent looking for "how to fix bugs" must check SKILL.md, then `prompts/fix-bug.md`, then the action YAML — three locations for what should be one.

### Problem 3: MCP Chain Module is Vestigial

The `src/mcp/augur_mcp/chains/` module (tools.py, models.py, \_\_init\_\_.py) was the MCP interface to the old chain system. Post ADR-130:
- `list_chains` always returns `{"chains": [], "count": 0}` (broken symlink to `.agent/chains/`)
- `execute_chain` imports from stale path `plugins/core/skills/executor` (should be `plugins/orchestration`)
- `list_action_buttons` reads from eliminated `config/action_buttons.yaml`

The dashboard already discovers actions via its own API (`/api/actions/route.ts` walking `augur/data/actions/*.yaml`). The MCP chain tools are dead code.

## Decision

### Part 1: Eliminate All Ghost Chain References

Remove or update every reference to `plugins/*/skills/*/chains/*.yaml` across live code, MCP tools, and agent-facing documentation.

**Action — Live code (4 files)**:

| File | Change |
|------|--------|
| `plugins/orchestration/skills/executor/scripts/chain_executor.py` | Remove `load_chains_from_yaml()` function (lines ~1048-1097) and `get_all_chains()` wrapper (lines ~1100-1105). Replace with action YAML discovery: scan `plugins/*/skills/*/augur/data/actions/*.yaml`. Update the legacy dict removal comment (lines ~1108-1113) to reflect the new reality. |
| `plugins/ai/skills/ai_bridge/augur/lib/chain_bridge.py` | Update `scan_chains()` to scan action YAMLs at `plugins/*/skills/*/augur/data/actions/*.yaml` instead of `chains/*.yaml`. Update the bridge's output generation to work with action YAML schema (id, label, dispatch, prompt/prompt_file). |
| `plugins/ai/skills/knowledge/scripts/project_indexer.py` | Update chain metadata scanner (lines ~178-180) to index action YAMLs at `plugins/*/skills/*/augur/data/actions/*.yaml` instead of `chains/*.yaml`. |
| `.github/scripts/generate_chain_index.py` | Update to scan action YAMLs, or delete if the chain index is no longer consumed anywhere. |

**Action — MCP tools (deprecate)**:

| File | Change |
|------|--------|
| `src/mcp/augur_mcp/chains/tools.py` | `list_chains_impl()`: rewrite to scan `plugins/*/skills/*/augur/data/actions/*.yaml` and return action metadata. `execute_chain_impl()`: fix stale import path from `plugins/core` to `plugins/orchestration`. `list_action_buttons_impl()`: rewrite to scan distributed action YAMLs instead of eliminated central `config/action_buttons.yaml`. |
| `src/mcp/augur_mcp/chains/models.py` | Update `ExecuteChainInput` model if needed for action-based execution. |
| `src/mcp/augur_mcp/infrastructure/chains_ext.py` | Update or remove chain extension registration. |

**Action — Agent-facing docs (4 files)**:

| File | Change |
|------|--------|
| `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/ops-optimize.md` | Replace all 5 references to `chains/*.yaml` with `augur/data/actions/*.yaml`. Update Phase 1 resolution, Phase 3 Dimension 3 analysis, Phase 5 Step 4 scan, and Key Files table. |
| `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/orch-chain.md` | Rewrite: chains are now action YAMLs. Update discovery pattern and auto-generation source description. |
| `plugins/ai/skills/ai_bridge/augur/data/ide-integration/chain-metadata/README.md` | Mark as DEPRECATED with pointer to action YAMLs, or delete entirely. |
| `plugins/professional/skills/venture-augur/augur/data/strategy/architecture.md` | Update line 396: "orchestrator discovers actions at runtime by scanning `plugins/*/skills/*/augur/data/actions/*.yaml`" |

**Action — Broken symlink**:

| Path | Change |
|------|--------|
| `.agent/chains` | Delete broken symlink (target `../data/crew/ide-integration/chains` doesn't exist) |

### Part 2: Consolidate Prompts into SKILL.md

Migrate the 15 `prompts/*.md` files into their respective skill's SKILL.md as `## Workflow:` sections, completing ADR-126's intent.

**Before** (3 locations):
```
plugins/dev/skills/developer/
├── SKILL.md                          ← has Workflow: Auto Fix Markers
├── prompts/
│   ├── fix-bug.md                    ← 64-line debug protocol (orphaned from SKILL.md)
│   ├── code-review.md
│   ├── execute-task.md
│   ├── refactor-code.md
│   ├── verify-test.md
│   └── write-tests.md
└── augur/data/actions/
    └── fix-bug.yaml                  ← prompt_file: prompts/fix-bug.md
```

**After** (2 locations — SKILL.md for orchestration, action YAML for trigger metadata):
```
plugins/dev/skills/developer/
├── SKILL.md                          ← has ALL workflows including Fix Bug, Code Review, etc.
└── augur/data/actions/
    └── fix-bug.yaml                  ← references skill (no prompt_file needed)
```

**Migration per file**:

For each of the 15 `prompts/*.md` files:
1. Read the prompt file content
2. Add it as a `## Workflow: {Name}` section in the skill's SKILL.md
3. Update the action YAML: remove `prompt_file: prompts/{name}.md`, add `skill_workflow: {workflow-name}` or simply let the skill's SKILL.md be the implicit instruction source (the `dispatch: ide` + `agents: [developer]` already tells the agent which skill to load)
4. Delete the `prompts/*.md` file
5. Delete the `prompts/` directory if empty

**Files to migrate** (grouped by skill):

| Skill | Prompt Files | Target SKILL.md |
|-------|-------------|-----------------|
| `plugins/dev/skills/developer` | fix-bug.md, code-review.md, execute-task.md, refactor-code.md, verify-test.md, write-tests.md | `plugins/dev/skills/developer/SKILL.md` |
| `plugins/dev/skills/advisor` | analyze-usage-patterns.md, triage-backlog.md | `plugins/dev/skills/advisor/SKILL.md` |
| `plugins/dev/skills/frontend` | enhance-dashboard.md | `plugins/dev/skills/frontend/SKILL.md` |
| `plugins/ai/skills/knowledge` | analyze-knowledge-gaps.md, smart-search.md | `plugins/ai/skills/knowledge/SKILL.md` |
| `plugins/career/skills/career` | analyze-job.md, prepare-interview.md | `plugins/career/skills/career/SKILL.md` |
| `plugins/professional/skills/venture-augur` | analyze-metrics.md, generate-campaign.md | `plugins/professional/skills/venture-augur/SKILL.md` |

**Action YAML update pattern**:

```yaml
# Before
id: fix-bug
label: Fix Bug
dispatch: ide
prompt_file: prompts/fix-bug.md    # ← external file, third location

# After
id: fix-bug
label: Fix Bug
dispatch: ide
# Orchestration lives in SKILL.md § Workflow: Fix Bug
# Agent loads skill context via agents: [developer] → reads developer/SKILL.md
```

**Inline prompt actions (28) are left as-is.** Short inline prompts in action YAMLs (`prompt: "Draft a reply..."`) are trigger instructions, not orchestration. They don't violate ADR-126 because they're single-step dispatch hints, not multi-step workflows.

### Part 3: Update Action Schema

Update the central action schema to document the new pattern and deprecate `prompt_file`:

| File | Change |
|------|--------|
| `plugins/ai/skills/ai_bridge/augur/data/action-schema.yaml` | Add `prompt_file` to a `deprecated_fields` section with note: "Orchestration belongs in SKILL.md workflow sections (ADR-126). Use inline `prompt:` for short dispatch hints only." |

### Part 4: Documentation Pattern Update

Establish the canonical two-layer pattern in agent-facing documentation so future agents don't recreate the fragmentation:

**Pattern: Action YAML is trigger metadata, SKILL.md is orchestration**

```
┌─────────────────────────────────────────────┐
│ SKILL.md                                     │
│ ├── ## Workflow: Fix Bug                     │  ← orchestration (steps, MCP calls,
│ │   ### Step 1: Reproduction                 │     conditionals, error handling)
│ │   ### Step 2: Investigation                │
│ │   ### Step 3: Fix Implementation           │
│ │   ### Step 4: Validation                   │
│ ├── ## Workflow: Code Review                 │
│ └── ## Workflow: Write Tests                 │
└─────────────────────────────────────────────┘
                    ▲
                    │ agent reads SKILL.md when activated
                    │
┌─────────────────────────────────────────────┐
│ augur/data/actions/fix-bug.yaml              │
│ ├── id: fix-bug                              │  ← trigger metadata (which button,
│ ├── label: Fix Bug                           │     which page, which dispatch mode)
│ ├── dispatch: ide                            │
│ ├── page: /workshop                          │
│ └── agents: [developer]                      │
└─────────────────────────────────────────────┘
```

**Rule**: Action YAMLs MUST NOT contain multi-step orchestration. If an action needs more than a 1-2 sentence `prompt:`, the orchestration belongs in the skill's SKILL.md as a `## Workflow:` section.

Update these agent instruction files with the pattern:

| File | Change |
|------|--------|
| `plugins/ai/skills/ai_bridge/augur/data/agent-topics/SKILLS.md` | Add section: "Action YAMLs are trigger metadata. Orchestration lives in SKILL.md workflow sections. Never create `prompts/` directories." |
| `plugins/ai/skills/ai_bridge/augur/data/agent-topics/ARCHITECTURE.md` | Update chain/action discovery section to reference action YAMLs at `augur/data/actions/*.yaml` |

## Consequences

**Positive:**
- Agents stop searching for nonexistent `chains/*.yaml` files — the #1 recurring confusion
- Orchestration has exactly one home: SKILL.md (ADR-126's original intent, fully realized)
- Action YAMLs are clean trigger metadata — no orchestration logic leaking in
- MCP chain tools either work correctly or are removed — no more broken symlinks and stale paths
- New skills follow a clear two-layer pattern: SKILL.md for orchestration, action YAML for buttons

**Negative:**
- 15 prompt files must be migrated into SKILL.md — mechanical but time-consuming
- Any external tooling that reads `prompts/` directories needs updating
- `chain_executor.py` changes may affect chain execution if any code paths still depend on YAML loading

**Neutral:**
- ADR documents (022, 029, 046, 085, 110) are historical snapshots and are NOT updated — they document what was true at the time
- Inline `prompt:` in action YAMLs remains valid for short dispatch hints
- The `execute-chain` MCP tool name is kept for backward compatibility but reimplemented to work with action YAMLs

## Implementation Order

```
Phase 1: Ghost Reference Elimination (PARALLEL — no dependencies between files)
├── Step 1.1: Update chain_executor.py — remove load_chains_from_yaml, add action YAML discovery
├── Step 1.2: Update chain_bridge.py — scan action YAMLs instead of chains
├── Step 1.3: Update project_indexer.py — index action YAMLs instead of chains
├── Step 1.4: Update or delete generate_chain_index.py
├── Step 1.5: Fix MCP chain tools — update paths, discovery, broken symlinks
├── Step 1.6: Delete .agent/chains broken symlink

Phase 2: Agent Doc Updates (PARALLEL — no dependencies between files)
├── Step 2.1: Update ops-optimize.md — replace chain refs with action YAML refs
├── Step 2.2: Rewrite orch-chain.md — action-based discovery
├── Step 2.3: Delete or deprecate chain-metadata/README.md
├── Step 2.4: Update architecture.md — action YAML discovery pattern
├── Step 2.5: Update SKILLS.md agent topic — add two-layer pattern rule
├── Step 2.6: Update ARCHITECTURE.md agent topic — action YAML discovery

Phase 3: Prompt Consolidation (PIPELINE — one skill at a time to verify)
├── Step 3.1: Migrate developer prompts (6 files) into developer/SKILL.md
├── Step 3.2: Migrate advisor prompts (2 files) into advisor/SKILL.md
├── Step 3.3: Migrate frontend prompts (1 file) into frontend/SKILL.md
├── Step 3.4: Migrate knowledge prompts (2 files) into knowledge/SKILL.md
├── Step 3.5: Migrate career prompts (2 files) into career/SKILL.md
├── Step 3.6: Migrate venture-augur prompts (2 files) into venture-augur/SKILL.md
├── Step 3.7: Update all 15 action YAMLs — remove prompt_file field
├── Step 3.8: Delete empty prompts/ directories
├── Step 3.9: Update action-schema.yaml — deprecate prompt_file

Phase 4: Verification (PIPELINE)
├── Step 4.1: Run stale path scanner: python3 .github/scripts/scan_stale_paths.py --ci
├── Step 4.2: Grep for remaining chains/*.yaml references (should be zero outside docs/decisions/)
├── Step 4.3: Grep for remaining prompts/ references in action YAMLs (should be zero)
├── Step 4.4: Verify MCP tools work: list-chains returns action data, execute-chain resolves correctly
├── Step 4.5: Run sync_agents.py --all and verify generated files are clean
├── Step 4.6: npm run build — verify dashboard compiles
└── Step 4.7: pytest tests/ — verify no test regressions
```

## Alternatives Considered

### Alternative 1: Keep prompts/ as a valid pattern alongside SKILL.md

**Argument**: The `prompts/` directory provides separation of concerns — SKILL.md describes the skill, prompt files describe specific task instructions.

**Rejected because**: This is exactly the three-location fragmentation problem. ADR-126 explicitly chose SKILL.md as the single orchestration home because Claude natively understands markdown workflow steps. A separate `prompts/` directory undermines progressive disclosure — when an agent loads the skill, it should find everything in SKILL.md, not have to chase references to external files.

### Alternative 2: Delete MCP chain tools entirely instead of rewriting

**Argument**: If chains are dead, remove the MCP tools completely.

**Rejected because**: The `execute-chain` tool name may be referenced in external integrations or saved workflows. Better to keep the interface but rewrite the implementation to work with action YAMLs — preserves backward compatibility while fixing the broken internals. If no consumers are found during implementation, deletion is acceptable.

### Alternative 3: Only fix documentation, leave code as-is

**Argument**: The code "works" (returns empty results gracefully), so only fix the docs that mislead agents.

**Rejected because**: Dead code that scans for nonexistent files is a maintenance trap. Every future developer who reads `load_chains_from_yaml()` will assume chain YAMLs exist somewhere. The code should reflect reality.

## References

- [ADR-126: Generic Plugin Template Refactor](ADR-126-generic-plugin-template-refactor.md) — established SKILL.md as orchestration home
- [ADR-130: Action Button Dispatch Modes](ADR-130-action-button-dispatch-modes.md) — unified chains into action system
- [ADR-046: Chain-to-Command Bridge](ADR-046-claude-code-crew-orchestration-bridge.md) — original chain-to-slash-command conversion (now superseded)
- [ADR-085: RAG Three-Tier Index](ADR-085-rag-three-tier-index.md) — indexes chain metadata (needs update to index actions)
- [Claude Code SKILL.md Standard](https://docs.anthropic.com/en/docs/claude-code/skills) — Anthropic's open standard for skill definitions

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "plugins/*/skills/*/chains/"
      to: "plugins/*/skills/*/augur/data/actions/"
      scope: "src/, plugins/, .github/, config/"
    - from: "prompts/"
      to: "SKILL.md § Workflow sections"
      scope: "plugins/*/skills/*/prompts/"
    - from: ".agent/chains"
      to: "(deleted — broken symlink)"
      scope: ".agent/"
    - from: "config/action_buttons.yaml"
      to: "plugins/*/skills/*/augur/data/actions/*.yaml"
      scope: "src/mcp/"
    - from: "plugins/core/skills/executor"
      to: "plugins/orchestration/skills/executor"
      scope: "src/mcp/"
  patterns_deprecated:
    - grep: "chains/\\*\\.yaml"
      replacement: "augur/data/actions/*.yaml"
    - grep: "load_chains_from_yaml|scan_chains.*chains"
      replacement: "scan action YAMLs from augur/data/actions/"
    - grep: "prompt_file:"
      replacement: "Orchestration in SKILL.md workflow sections"
    - grep: "\\.agent.*chains"
      replacement: "(deleted)"
  files_affected:
    - glob: "plugins/orchestration/skills/executor/scripts/chain_executor.py"
    - glob: "plugins/ai/skills/ai_bridge/augur/lib/chain_bridge.py"
    - glob: "plugins/ai/skills/knowledge/scripts/project_indexer.py"
    - glob: ".github/scripts/generate_chain_index.py"
    - glob: "src/mcp/augur_mcp/chains/tools.py"
    - glob: "src/mcp/augur_mcp/chains/models.py"
    - glob: "src/mcp/augur_mcp/infrastructure/chains_ext.py"
    - glob: "plugins/ai/skills/ai_bridge/augur/data/agent-workflows/ops-optimize.md"
    - glob: "plugins/ai/skills/ai_bridge/augur/data/agent-workflows/orch-chain.md"
    - glob: "plugins/ai/skills/ai_bridge/augur/data/ide-integration/chain-metadata/README.md"
    - glob: "plugins/professional/skills/venture-augur/augur/data/strategy/architecture.md"
    - glob: "plugins/ai/skills/ai_bridge/augur/data/agent-topics/SKILLS.md"
    - glob: "plugins/ai/skills/ai_bridge/augur/data/agent-topics/ARCHITECTURE.md"
    - glob: "plugins/ai/skills/ai_bridge/augur/data/action-schema.yaml"
    - glob: "plugins/*/skills/*/prompts/*.md"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-138: Chain Reference Cleanup and Prompt Consolidation**.

Read the full ADR: `docs/decisions/ADR-138-chain-reference-cleanup-and-prompt-consolidation.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-138-chain-cleanup", description="Implementing ADR-138: Chain Reference Cleanup and Prompt Consolidation")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-138-chain-cleanup", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-138 team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases → spawn all at once. PIPELINE phases → use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` → haiku, `medium` → sonnet, `high` → opus

### Execution Plan

**Team name**: `adr-138-chain-cleanup`

#### Phase 1: Ghost Reference Elimination
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Remove `load_chains_from_yaml()` and `get_all_chains()` from chain_executor.py. Replace with action YAML discovery scanning `plugins/*/skills/*/augur/data/actions/*.yaml`. Keep `execute_chain()` function working but sourcing from action YAMLs. | `plugins/orchestration/skills/executor/scripts/chain_executor.py` |
| 1.2 | developer | medium | Update `scan_chains()` in chain_bridge.py to scan `plugins/*/skills/*/augur/data/actions/*.yaml` instead of `chains/*.yaml`. Update output generation for action YAML schema. | `plugins/ai/skills/ai_bridge/augur/lib/chain_bridge.py` |
| 1.3 | developer | low | Update chain metadata scanner in project_indexer.py to index action YAMLs at `plugins/*/skills/*/augur/data/actions/*.yaml`. | `plugins/ai/skills/knowledge/scripts/project_indexer.py` |
| 1.4 | developer | low | Update `generate_chain_index.py` to scan action YAMLs. If the generated index is not consumed anywhere, delete the script. | `.github/scripts/generate_chain_index.py` |
| 1.5 | developer | medium | Fix MCP chain tools: (a) `list_chains_impl` — scan action YAMLs instead of `.agent/chains/`; (b) `execute_chain_impl` — fix stale import from `plugins/core` to `plugins/orchestration`; (c) `list_action_buttons_impl` — scan distributed action YAMLs instead of `config/action_buttons.yaml`. Update models.py and chains_ext.py as needed. | `src/mcp/augur_mcp/chains/tools.py`, `src/mcp/augur_mcp/chains/models.py`, `src/mcp/augur_mcp/infrastructure/chains_ext.py` |
| 1.6 | devops | low | Delete broken `.agent/chains` symlink. Verify with `ls -la .agent/chains`. | `.agent/chains` |

#### Phase 2: Agent Doc Updates
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Update ops-optimize.md: replace all 5 `chains/*.yaml` references with `augur/data/actions/*.yaml`. Update Phase 1 target resolution to check action YAMLs. Update Phase 3 Dimension 3 to analyze action YAML dependencies instead of chain steps. Update Phase 5 Step 4 chain parallelism scan to action analysis. Update Key Files table. | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/ops-optimize.md` |
| 2.2 | developer | medium | Rewrite orch-chain.md: update discovery description to reference action YAMLs. Document that "chains" are now action buttons with `dispatch: ide` that trigger SKILL.md workflows. | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/orch-chain.md` |
| 2.3 | devops | low | Delete `chain-metadata/README.md` and directory if empty, or mark as DEPRECATED with pointer: "Chain YAMLs migrated to action YAMLs (ADR-130) and SKILL.md workflows (ADR-126). See `plugins/*/skills/*/augur/data/actions/`." | `plugins/ai/skills/ai_bridge/augur/data/ide-integration/chain-metadata/README.md` |
| 2.4 | developer | low | Update architecture.md line 396: replace "orchestrator discovers chains at runtime by scanning `plugins/*/skills/*/chains/*.yaml`" with "orchestrator discovers actions at runtime by scanning `plugins/*/skills/*/augur/data/actions/*.yaml`. Orchestration logic lives in each skill's SKILL.md workflow sections." | `plugins/professional/skills/venture-augur/augur/data/strategy/architecture.md` |
| 2.5 | developer | medium | Add section to SKILLS.md agent topic: "## Action vs Orchestration Pattern" — Action YAMLs are trigger metadata (button label, dispatch mode, page). Orchestration belongs in SKILL.md `## Workflow:` sections. Never create `prompts/` directories. If an action needs multi-step instructions, add a Workflow section to SKILL.md. | `plugins/ai/skills/ai_bridge/augur/data/agent-topics/SKILLS.md` |
| 2.6 | developer | low | Update ARCHITECTURE.md agent topic: replace any chain discovery references with action YAML pattern `plugins/*/skills/*/augur/data/actions/*.yaml`. | `plugins/ai/skills/ai_bridge/augur/data/agent-topics/ARCHITECTURE.md` |

#### Phase 3: Prompt Consolidation
**Strategy**: PIPELINE (one skill at a time to verify each migration)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Migrate 6 prompt files into developer/SKILL.md as `## Workflow:` sections: fix-bug.md → `## Workflow: Fix Bug`, code-review.md → `## Workflow: Code Review`, execute-task.md → `## Workflow: Execute Task`, refactor-code.md → `## Workflow: Refactor Code`, verify-test.md → `## Workflow: Verify Test`, write-tests.md → `## Workflow: Write Tests`. Read each prompt file, convert to SKILL.md workflow section with `### Step N:` substeps, add to SKILL.md before the Chain Integration section. Delete prompt files and `prompts/` dir. | `plugins/dev/skills/developer/SKILL.md`, `plugins/dev/skills/developer/prompts/*.md` |
| 3.2 | developer | medium | Migrate 2 prompt files into advisor/SKILL.md: analyze-usage-patterns.md → `## Workflow: Analyze Usage Patterns`, triage-backlog.md → `## Workflow: Triage Backlog`. Delete prompt files and `prompts/` dir. | `plugins/dev/skills/advisor/SKILL.md`, `plugins/dev/skills/advisor/prompts/*.md` |
| 3.3 | developer | low | Migrate 1 prompt file into frontend/SKILL.md: enhance-dashboard.md → `## Workflow: Enhance Dashboard`. Delete prompt files and `prompts/` dir. | `plugins/dev/skills/frontend/SKILL.md`, `plugins/dev/skills/frontend/prompts/*.md` |
| 3.4 | developer | medium | Migrate 2 prompt files into knowledge/SKILL.md: analyze-knowledge-gaps.md → `## Workflow: Analyze Knowledge Gaps`, smart-search.md → `## Workflow: Smart Search`. Delete prompt files and `prompts/` dir. | `plugins/ai/skills/knowledge/SKILL.md`, `plugins/ai/skills/knowledge/prompts/*.md` |
| 3.5 | developer | medium | Migrate 2 prompt files into career/SKILL.md: analyze-job.md → `## Workflow: Analyze Job`, prepare-interview.md → `## Workflow: Prepare Interview`. Delete prompt files and `prompts/` dir. | `plugins/career/skills/career/SKILL.md`, `plugins/career/skills/career/prompts/*.md` |
| 3.6 | developer | medium | Migrate 2 prompt files into venture-augur/SKILL.md: analyze-metrics.md → `## Workflow: Analyze Metrics`, generate-campaign.md → `## Workflow: Generate Campaign`. Delete prompt files and `prompts/` dir. | `plugins/professional/skills/venture-augur/SKILL.md`, `plugins/professional/skills/venture-augur/prompts/*.md` |
| 3.7 | developer | low | Update all 15 action YAMLs that had `prompt_file:` — remove the `prompt_file` field. The agent already loads SKILL.md via the `agents:` field. | `plugins/*/skills/*/augur/data/actions/*.yaml` (15 files) |
| 3.8 | devops | low | Verify all `prompts/` directories are deleted. Run: `find plugins -type d -name prompts` — should return empty. | All plugins |
| 3.9 | developer | low | Update action-schema.yaml: add `prompt_file` to deprecated_fields with note: "Orchestration belongs in SKILL.md workflow sections (ADR-126, ADR-138)." | `plugins/ai/skills/ai_bridge/augur/data/action-schema.yaml` |

#### Phase 4: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 4.1 | validator | low | Run stale path scanner: `python3 .github/scripts/scan_stale_paths.py --ci` |
| 4.2 | validator | low | Grep for remaining ghost references: `grep -r "chains/\*.yaml" plugins/ src/ .github/ --include="*.py" --include="*.ts" --include="*.md" \| grep -v docs/decisions/` — should be zero |
| 4.3 | validator | low | Grep for remaining prompt_file refs: `grep -r "prompt_file:" plugins/*/skills/*/augur/data/actions/*.yaml` — should be zero |
| 4.4 | validator | low | Verify no `prompts/` directories remain: `find plugins -type d -name prompts` — should be empty |
| 4.5 | devops | low | Run `python3 plugins/ai/skills/ai_bridge/scripts/sync_agents.py --all` and verify generated files are clean |
| 4.6 | validator | low | Run `cd src/dashboard && npm run build` — verify dashboard compiles |
| 4.7 | validator | low | Run `pytest tests/` — verify no test regressions |
| 4.8 | architect | low | Verify ADR intent: read ADR-126 Part 2, ADR-130 chain migration section, and ADR-138. Confirm implementation matches the two-layer pattern (SKILL.md for orchestration, action YAML for trigger metadata). |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/`, `npm run build`)
- [ ] No orphaned files or broken references
- [ ] Stale path scanner clean
- [ ] Impact Manifest validated — zero stale references for `chains/*.yaml`, `prompts/`, `.agent/chains`, `config/action_buttons.yaml`, `plugins/core/skills/executor`
- [ ] Zero `prompt_file:` references in action YAMLs
- [ ] Zero `prompts/` directories in plugins
- [ ] ADR status updated to "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-138-chain-reference-cleanup-and-prompt-consolidation.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
