---
status: Implemented
date: '2026-02-24'
deciders:
- Augur Team
related:
- ADR-126 (Generic Plugin Template Refactor)
- ADR-130 (Action Button Dispatch Modes)
- ADR-138 (Chain Reference Cleanup)
hub: null
tags:
- agent
- instruction
- drift
- action
- yaml
superseded_by: null
---

# ADR-143: Agent Instruction Drift and Action YAML Migration

## Context

New Claude sessions consistently revert to old chain-based patterns despite ADR-126/130 migrating chains to action YAMLs months ago. The root cause is **stale agent-facing instruction files** — the documents that every new session loads still describe the pre-migration architecture.

### The Session Drift Loop

1. Agent reads `CLAUDE.md` (entry point) → sees `/orch-chain` in Orch commands
2. Agent reads `SKILLS.md` → told to "Check for relevant chains" in `plugins/orchestration/skills/executor/augur/chains/`
3. Agent reads `WORKFLOWS.md` → sees "when using chains" guidance
4. Agent looks for chain YAML files → finds nothing → confused about orchestration
5. Falls back to prior knowledge → uses old patterns (creates chains, prompts/ dirs)
6. **Next session repeats steps 1-5** because instructions are never updated

### Scope of Stale References

**Agent instruction files (12 files)** — loaded by every new session:

| Priority | File | Stale Content |
|----------|------|---------------|
| P1 | `CLAUDE.md` (via `agent-rules.md`) | Lists `/orch-chain`, references "using chains" |
| P1 | `agent-topics/SKILLS.md` | "Check for relevant chains" + stale directory path |
| P1 | `agent-topics/WORKFLOWS.md` | "when using chains" + chain execution guidance |
| P2 | `agent-topics/CONTEXT.md` | "Check for relevant chains" |
| P2 | `agent-topics/AGENTS.md` | "modifying chains" in dev mode description |
| P3 | `agent-workflows/orch-chain.md` | Entire file describes nonexistent chain system |
| P3 | `agent-workflows/ops-optimize.md` | 5 chain refs in search/analysis targets |
| P3 | `agent-workflows/ops-refactor.md` | Chain YAML as refactor targets |
| P3 | `agent-workflows/ops-inspect.md` | "chains" as observable dimension |
| P4 | `agent-workflows/focus.md` | Chains as discoverable automation |
| P4 | `agent-workflows/ops-docs.md` | "New skills or chains" |
| P4 | `agent-workflows/ops-plugin-lint.md` | `chains/` as banned root-level entry |

**Action YAML fields (319 instances in 36 files)** — old `flow`/`mode`/`promptOverride` fields not migrated to `dispatch`:

36 `augur.yaml` files across all hubs still use the pre-ADR-130 schema. The dashboard action system reads both formats via a compatibility shim, but the old fields mislead agents into thinking the old system is active.

**Dead chain code (9 files)** — MCP tools, executor, bridge all reference nonexistent files:

| File | Issue |
|------|-------|
| `src/mcp/augur_mcp/chains/__init__.py` | Registers broken `list-chains`, `execute-chain`, `list-action-buttons` |
| `src/mcp/augur_mcp/chains/tools.py` | Reads from `.agent/chains/` (broken symlink), `config/action_buttons.yaml` (deleted) |
| `src/mcp/augur_mcp/chains/models.py` | Defines models for defunct tools |
| `plugins/orchestration/skills/executor/scripts/chain_executor.py` | Scans nonexistent `chains/*.yaml` |
| `plugins/ai/skills/ai_bridge/augur/lib/chain_bridge.py` | Scans nonexistent `chains/*.yaml` |
| `.agent/chains` symlink | Broken — target doesn't exist |
| `config/mcp_tool_groups.yaml` (CHAIN group) | References unimplemented tools |
| `config/agents/agent_contexts.yaml` (`current_chain`) | Injects nonexistent chain context |
| `scripts/augur_cli.py` (`chain` subparser) | Routes to broken executor |

## Decision

### Phase 1: Agent Instruction Cleanup (stops the drift loop)

Update all 12 agent-facing instruction files to replace chain references with the post-migration two-layer pattern:

- **SKILL.md** = orchestration (workflows, steps, MCP calls, conditionals)
- **`augur/data/actions/*.yaml`** = trigger metadata (button label, dispatch mode, page, agents)

Specific changes:
- Replace "Check for relevant chains" → "Check `augur/data/actions/` for action YAMLs and `SKILL.md` for workflow definitions"
- Replace "when using chains" → "when using action dispatch"
- Replace `/orch-chain` description → describe action YAML + dispatch system
- Rewrite `orch-chain.md` → document action discovery pattern
- Update all search/analysis targets from `chains/*.yaml` → `augur/data/actions/*.yaml`

After edits, run `sync_agents.py --all` to regenerate `CLAUDE.md` from updated `agent-rules.md`.

### Phase 2: Action YAML Field Migration (319 instances, 36 files)

Batch-migrate old fields to new `dispatch` field across all `augur.yaml` files:

| Old Fields | New `dispatch` Value |
|---|---|
| `flow: direct` or no flow/mode | `fire` |
| `flow: direct` + `mode: operation` | `oneshot` |
| `flow: escalation` or `mode: ide` | `ide` |
| `flow: confirm` or `mode: modal` | `modal` |

Implementation: Python migration script that:
1. Reads each `augur.yaml`
2. For each action entry with `flow`/`mode`/`promptOverride`, maps to `dispatch`
3. Removes old fields, adds `dispatch`
4. Preserves all other fields and formatting

### Phase 3: Dead Chain Code Removal

Remove or rewrite the 9 files containing dead chain code:
- Delete `.agent/chains` broken symlink
- Remove chain tool registrations from MCP (or rewrite to scan action YAMLs)
- Remove `CHAIN` tool group from `mcp_tool_groups.yaml`
- Remove `current_chain` context from `agent_contexts.yaml`
- Remove `chain` subparser from `augur_cli.py`

### Phase 4: Prompt Consolidation (per ADR-138 Phase 3)

Migrate 15 `prompts/*.md` files into their respective `SKILL.md` as `## Workflow:` sections. This completes ADR-126's intent of SKILL.md as the single orchestration home.

## Consequences

**Positive:**
- New sessions immediately understand the current architecture — no more drift to old patterns
- Single source of truth for orchestration (SKILL.md) and trigger metadata (action YAML)
- Dead code removed — no more confusion from scanning nonexistent files
- Action YAMLs use consistent `dispatch` field — compatibility shim can be removed

**Negative:**
- 36 augur.yaml files modified — risk of formatting issues
- Agents with memorized old patterns from prior sessions need a fresh start
- Any external tooling reading `flow`/`mode` fields needs updating

## Implementation Order

```
Phase 1: Agent Instruction Cleanup          ← HIGHEST IMPACT, do first
├── 12 doc files (PARALLEL edits)
└── sync_agents.py --all

Phase 2: Action YAML Migration              ← PARALLEL with Phase 1
├── Write migration script
├── Run on 36 augur.yaml files
└── Remove compatibility shim

Phase 3: Dead Chain Code Removal            ← After Phases 1-2
├── 9 code files (PARALLEL deletes/rewrites)
└── Verify MCP tool registry clean

Phase 4: Prompt Consolidation               ← After Phase 3
├── 15 prompt files → SKILL.md (PIPELINE, one skill at a time)
├── Update 15 action YAMLs (remove prompt_file)
└── Delete empty prompts/ directories

Verification:
├── grep for chains/*.yaml refs (should be zero outside docs/decisions/)
├── grep for flow:/mode:/promptOverride: in augur.yaml (should be zero)
├── npm run build (dashboard compiles)
├── pytest tests/ (no regressions)
└── sync_agents.py --all (clean regeneration)
```

## References

- [ADR-126: Generic Plugin Template Refactor](ADR-126-generic-plugin-template-refactor.md) — established SKILL.md as orchestration home
- [ADR-130: Action Button Dispatch Modes](ADR-130-action-button-dispatch-modes.md) — unified chains into action dispatch system
- [ADR-138: Chain Reference Cleanup](ADR-138-chain-reference-cleanup-and-prompt-consolidation.md) — identified ghost references and prompt fragmentation
