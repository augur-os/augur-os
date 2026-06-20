---
status: Implemented
date: '2026-02-06'
deciders:
- Augur Core Team
related:
- ADR-030 (Unified AI Bridge)
- ADR-007 (Chain Orchestration)
- ADR-020 (Unified Agent Execution)
hub: null
tags:
- claude
- code
- crew
- orchestration
- bridge
superseded_by: null
---

# ADR-046: Claude Code Crew Orchestration Bridge

**Implemented**: 2026-02-07
**Supersedes**: ADR-031 (Claude Code Native Capabilities)

## Context

The ai-bridge skill currently syncs static artifacts (CLAUDE.md, slash commands, MCP configs) to 9 IDE clients via `sync_agents.py`. Separately, the crew bundle provides 13 specialized agent skills with tiered capabilities and safety constraints, and the orchestrator bundle provides chain execution, intelligent routing, and swarm coordination.

These two systems operate in parallel but do not talk to each other:

| What exists | What's missing |
|---|---|
| ai-bridge syncs rules, slash commands, MCP configs to 9 IDEs | No subagent profiles generated from crew SKILL.md |
| 13 crew skills with tiering, safety, iron laws | Not exposed as Claude Code Task tool subagents |
| Chain YAML workflows (21+ chains) | Not converted to slash commands that use subagents |
| Augur hook system (6 events) | No SubagentStart/Stop, no crew safety hooks in Claude Code |
| Swarm executor (4 strategies, 5 presets) | Not bridged to Claude Code's parallel Task tool |
| Router/tier-selector | Not mapped to Claude Code per-task model selection |

Claude Code supports native orchestration primitives — the Task tool for spawning subagents with model selection, hooks for lifecycle events (including SubagentStart/SubagentStop), and parallel execution. By bridging these to our crew/orchestrator system, we get true agent orchestration without a separate Python runtime.

## Decision

Extend `sync_agents.py` to generate Claude Code-native orchestration artifacts from existing crew SKILL.md and chain YAML sources. Five phases, each building on the prior.

### Phase 1: Crew Subagent Profiles ✅

Parse each crew SKILL.md frontmatter (tiers, safety, mode) and generate `.claude/agents/{skill}.md` — a subagent profile that Claude Code's Task tool can invoke with the right model, tool allowlist, and system prompt.

**Tier-to-model mapping** (from `tier_selector.py`):
| Crew Tier | Capability | Claude Model | Mode |
|---|---|---|---|
| low | fast | haiku | advisory only |
| medium | balanced | sonnet | advisory or executor |
| high | reasoning | opus | full access |

**Advisory vs Executor**:
- Advisory profiles (architect, security, analyst, validator, design-system, oss-manager, plugins): `Read/Glob/Grep` only, explicit "You MUST NOT modify files" constraint
- Executor profiles (developer, frontend, devops, data-engineer, mcp-app-factory): Full tool access, iron law + protected areas as constraints

**Available Tiers section**: Each profile includes an "Available Tiers" section showing all tier options with their model and mode, so callers can override the default tier when spawning via the Task tool.

**Project Context injection**: Agent profiles include a "Project Context" section extracted from `data/ai-bridge/agent-rules.md`, providing the monorepo structure tree and key conventions (path resolution, code style, plugin mounting). This gives subagents project awareness without requiring them to read CLAUDE.md.

**Generated artifacts**:
```
.claude/agents/
  architect.md          # advisory, sonnet default, Read/Glob/Grep only
  developer.md          # executor, sonnet default, +Edit/Bash
  frontend.md           # executor, sonnet default, +Edit/Bash
  validator.md          # advisory, sonnet default, Read/Glob/Grep/Bash(test)
  security.md           # advisory, sonnet default, Read/Glob/Grep/Bash(scan)
  analyst.md            # advisory, sonnet default, Read/Glob/Grep
  devops.md             # executor at high tier, sonnet default
  data-engineer.md      # executor, sonnet default
  design-system.md      # advisory, Read/Glob/Grep
  mcp-app-factory.md    # executor, sonnet default
  oss-manager.md        # advisory, Read/Glob/Grep
  plugins.md            # advisory, Read/Glob/Grep
  registry.json         # Manifest with all subagent metadata
```

**Implementation**:
- `plugins/ai/skills/ai_bridge/augur/subagent_profile.py` — `SubagentProfile` dataclass with `to_agent_markdown(tier, project_context)` method
- `plugins/ai/skills/ai_bridge/augur/crew_parser.py` — Parses crew SKILL.md into `SubagentProfile` objects
- `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` — `sync_subagents()` generates all profile files + registry.json

### Phase 2: Chain-to-Command Bridge ✅

Scan chain YAML files from `plugins/*/skills/*/chains/*.yaml`, analyze step dependencies, and generate `.claude/commands/chain-{name}.md` slash commands that instruct Claude Code to spawn Task tool subagents in the correct order with data handoffs.

**Per-step model selection** (integrating router keywords):
```
explore_codebase → sonnet     (fast scan)
design/blueprint → opus       (deep reasoning)
implement_feature → sonnet    (standard coding)
security_audit → opus         (thorough analysis)
verify_changes → haiku        (quick validation)
```

**Parallel group detection**: Reuses dependency analysis from `parallel_executor.py` to identify which chain steps can be spawned as concurrent subagents.

**Generated**: `.claude/commands/chain-{name}.md` (23 chain commands)

**Implementation**:
- `plugins/ai/skills/ai_bridge/augur/chain_bridge.py` — `ChainCommand` dataclass, YAML-to-command converter, dependency analyzer, keyword-to-tier routing

### Phase 3: Hooks Integration ✅

Extend the Augur hook system with `SubagentStart` and `SubagentStop` events. Generate Claude Code hook configurations from crew safety rules:

```yaml
hooks:
  PreToolUse:
    - matcher: { agent: "architect", tool: "Edit|Write" }
      action: BLOCK
      message: "Architect is advisory-only"
    - matcher: { agent: "developer", path: "src/auth/*" }
      action: BLOCK
      message: "Protected area. Requires explicit approval."
  SubagentStart:
    - handler: crew_lifecycle_tracker
  SubagentStop:
    - handler: crew_result_aggregator
```

**Bidirectional event mapping**:
| Augur Event | Claude Code Hook | Direction |
|---|---|---|
| PreToolUse | PreToolUse | Augur→CC (safety gating) |
| PostToolUse | PostToolUse | CC→Augur (telemetry) |
| SessionStart | SessionStart | CC→Augur (context loading) |
| Stop | Stop | CC→Augur (checkpoint) |
| SubagentStart (NEW) | SubagentStart | CC→Augur (lifecycle tracking) |
| SubagentStop (NEW) | SubagentStop | CC→Augur (result aggregation) |

**Implementation**:
- `plugins/ai/skills/ai_bridge/augur/crew_hooks.py` — Crew-specific hook handlers (safety gating, lifecycle tracking, result aggregation)
- `plugins/ai/skills/ai_bridge/augur/events.py` — Extended with `SubagentStart`, `SubagentStop` events

### Phase 4: Swarm Bridge ✅

Map Augur's swarm strategies to Claude Code Task tool patterns, with dual execution mode support (Task Tool + Agent Teams).

**Strategy mapping**:
| Augur Strategy | Claude Code Pattern |
|---|---|
| PARALLEL | Spawn N subagents simultaneously in one message |
| PIPELINE | Spawn sequentially, each receives prior output |
| BROADCAST | Same as PARALLEL, identical input to all |
| DIVIDE | Coordinator subagent splits task, then spawns per-subtask |

**Consensus mapping**:
| Consensus Mode | Implementation |
|---|---|
| MERGE | Concatenate outputs with agent section headers |
| COORDINATOR | Final subagent synthesizes all results |
| VOTE | Count output categories, report majority |
| PRIORITY | Return first successful result |

**Tier-based model routing**: Each preset and agent has a `tier` field that enforces model consistency:
- `low` → haiku (read-only analysis, ~10x cheaper than opus)
- `medium` → sonnet (standard work)
- `high` → opus (deep reasoning)

Read-only presets (code-review, codebase-analysis, documentation) use all-haiku agents. Implementation presets (feature-development, bug-fix) use mixed tiers matching task complexity.

**Agent Teams integration** (requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`): Each swarm command generates two execution paths:
1. **Agent Teams (Preferred)**: Natural language prompt spawning peer-to-peer teammates with debate/collaborative/pipeline modes. Teammates are explicitly instructed to read their `.claude/agents/{name}.md` crew profile before starting work.
2. **Task Tool (Fallback)**: Traditional subagent spawning via multiple Task tool calls.

**Teams modes**:
| Mode | Behavior |
|---|---|
| collaborative | Teammates share findings, challenge disagreements, merge reports |
| debate | Teammates actively try to disprove each other, defend with evidence |
| pipeline | Sequential handoff via messages, each teammate builds on prior output |

**Generated**: `.claude/commands/swarm-{preset}.md` (6 files)

| Preset | Strategy | Agents | Tiers | Teams Mode |
|---|---|---|---|---|
| code-review | PARALLEL | developer + validator + security | all low | collaborative |
| feature-development | PIPELINE | architect → developer → validator | high/medium/low | pipeline |
| security-audit | PARALLEL | security + validator | high/medium | debate |
| documentation | PIPELINE | analyst → developer | all low | pipeline |
| bug-fix | PIPELINE | developer → validator | medium/low | pipeline |
| codebase-analysis | PARALLEL | security + analyst + developer | all low | debate |

**Implementation**:
- `plugins/ai/skills/ai_bridge/augur/swarm_bridge.py` — `SWARM_PRESETS`, strategy/consensus/teams mapping, `swarm_preset_to_command_markdown()`, `_generate_teams_prompt()`

### Phase 5: Cross-MCP Crew Tools ✅

Expose crew dispatch as MCP tools for cross-session delegation:

| MCP Tool | Description |
|---|---|
| `crew-dispatch` | Dispatch a task to a specific crew skill |
| `crew-list` | List available crew skills with capabilities |
| `crew-status` | Check dispatched task status |
| `chain-execute` | Execute a named chain |
| `chain-status` | Check chain execution status |
| `swarm-execute` | Execute a swarm preset |

Shared state at `runtime/crew-state.json`.

**Implementation**:
- `plugins/ai/skills/ai_bridge/mcp/models.py` — Pydantic models for MCP tool inputs/outputs
- `plugins/ai/skills/ai_bridge/mcp/tools.py` — MCP tool implementations
- `plugins/ai/skills/ai_bridge/mcp/__init__.py` — Tool registration

### Implementation Order

```
Phase 1 (Subagent Profiles)  ← Foundation, no deps           ✅
    |
    v
Phase 2 (Chain Commands)     ← Needs subagent refs           ✅
Phase 3 (Hooks)              ← Needs crew safety rules       ✅
    |                           (Phases 2 & 3 parallel)
    v
Phase 4 (Swarm Bridge)       ← Needs subagents + commands    ✅
    |
    v
Phase 5 (Cross-MCP)          ← Needs everything above        ✅
```

### Key Design Principles

1. **Generate, don't runtime-bridge**: `sync_agents.py` generates static files Claude Code reads natively. No runtime Python process needed.
2. **SKILL.md is the single source of truth**: No separate subagent config. Parser reads SKILL.md frontmatter directly.
3. **Python orchestrator remains for non-Claude IDEs**: chain_executor.py, swarm_executor.py stay as canonical for Cursor, Windsurf, etc.
4. **Advisory agents get hard blocks**: PreToolUse hooks physically block Edit/Write for advisory agents.
5. **Router integration**: Per-step model selection uses the same keyword-to-tier logic from `tier_selector.py`.
6. **Crew profiles flow into swarms**: Both Task Tool and Agent Teams paths load `.claude/agents/{name}.md` profiles, ensuring iron laws, safety constraints, and project context are inherited by every subagent.
7. **Cost-aware defaults**: Read-only presets default to all-haiku (cheapest), reserving opus for reasoning-heavy tasks only.

## Implementation Details

### Files Created

| File | Purpose |
|---|---|
| `plugins/ai/skills/ai_bridge/augur/subagent_profile.py` | `SubagentProfile` dataclass with markdown generation |
| `plugins/ai/skills/ai_bridge/augur/crew_parser.py` | SKILL.md frontmatter → SubagentProfile parser |
| `plugins/ai/skills/ai_bridge/augur/chain_bridge.py` | Chain YAML → slash command converter |
| `plugins/ai/skills/ai_bridge/augur/swarm_bridge.py` | Swarm strategy → Task tool / Agent Teams mapping |
| `plugins/ai/skills/ai_bridge/augur/crew_hooks.py` | Crew-specific hook handlers |
| `plugins/ai/skills/ai_bridge/mcp/models.py` | MCP tool Pydantic models |
| `plugins/ai/skills/ai_bridge/mcp/tools.py` | MCP tool implementations |
| `plugins/ai/skills/ai_bridge/mcp/__init__.py` | MCP tool registration |
| `tests/unit/ai_bridge/test_crew_bridge.py` | 84 tests covering all phases |

### Files Modified

| File | Changes |
|---|---|
| `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` | Added `sync_subagents()`, enhanced `sync_workflows()`, project context loading |
| `plugins/ai/skills/ai_bridge/augur/events.py` | Added `SubagentStart`, `SubagentStop` events |
| `plugins/ai/skills/ai_bridge/mcp/server.py` | Registered orchestration MCP tools |

### Generated Artifacts

```
.claude/
├── agents/
│   ├── architect.md         # 12 crew skill profiles
│   ├── developer.md         #   with Available Tiers,
│   ├── frontend.md          #   Project Context, iron laws,
│   ├── validator.md         #   tool allowlists, and
│   ├── security.md          #   safety constraints
│   ├── analyst.md
│   ├── devops.md
│   ├── data-engineer.md
│   ├── design-system.md
│   ├── mcp-app-factory.md
│   ├── oss-manager.md
│   ├── plugins.md
│   └── registry.json        # Agent manifest
├── commands/
│   ├── chain-*.md           # 23 chain commands
│   ├── swarm-code-review.md
│   ├── swarm-feature-development.md
│   ├── swarm-security-audit.md
│   ├── swarm-documentation.md
│   ├── swarm-bug-fix.md
│   └── swarm-codebase-analysis.md
└── settings.json            # Agent Teams enabled
```

### Test Coverage

84 tests across these test classes:
- `TestSubagentProfile` — Profile dataclass, markdown generation, tiers, tools
- `TestCrewParser` — SKILL.md parsing, frontmatter extraction
- `TestChainBridge` — Chain YAML conversion, dependency analysis, model routing
- `TestSwarmBridge` — Preset validation, strategy/consensus mapping
- `TestAgentTeamsIntegration` — Teams mode, prompt generation, crew profile loading
- `TestProjectContextInjection` — Context extraction, placement, edge cases
- `TestAvailableTiersSection` — Tier display, default marking, placement
- `TestTierBasedModelRouting` — Tier consistency enforcement across all presets

## Consequences

### Positive

- Every crew skill becomes directly invocable as a Claude Code subagent with proper model selection
- Chain YAML workflows automatically become Claude Code slash commands
- Iron laws and safety constraints enforced through Claude Code's native hook system
- Swarm strategies get true parallelism through the Task tool
- Agent Teams enable peer-to-peer debate and collaboration between subagents
- Subagents inherit project context automatically (no CLAUDE.md re-reading needed)
- Cost savings: read-only presets at ~10x cheaper using haiku vs opus
- `sync_agents.py` remains the single pipeline — all artifacts stay synchronized
- Non-Claude IDEs unaffected — Python orchestrator continues to work

### Negative

- Only works with Claude Code (other IDEs fall back to Python orchestrator)
- Increases `sync_agents.py` complexity significantly
- Generated artifacts need version pinning as Claude Code evolves
- More files to manage in `.claude/` directory
- Agent Teams feature is experimental and requires opt-in flag

### Neutral

- Python-based chain_executor.py and swarm_executor.py remain as canonical for non-Claude IDEs
- Crew SKILL.md format does not change; only consumers expand
- Existing slash commands and MCP configs unchanged

## Alternatives Considered

### Alternative 1: Python-Only Orchestration (Status Quo+)

Keep crew orchestration entirely in Python (chain_executor.py, swarm_executor.py) and have Claude Code call them via Bash. Rejected because Claude Code's native Task tool provides true parallelism, model selection, and subagent isolation that Python subprocess chains cannot match.

### Alternative 2: MCP-Only Approach

Expose everything through MCP tools and skip Claude Code native features. Rejected because MCP tool calls are sequential and lack subagent isolation and model selection. MCP remains important for cross-session delegation (Phase 5) but insufficient as the sole orchestration mechanism.

### Alternative 3: Standalone Orchestration Daemon

Build a separate orchestration daemon that both Claude Code and Python call into. Rejected because it adds operational complexity and doesn't leverage Claude Code's built-in primitives. The existing daemon skill handles enough background work.

## References

- ADR-030: Unified AI Bridge with Context Switch Algorithm
- ADR-031: Claude Code Native Capabilities (superseded by this ADR)
- ADR-007: Chain Orchestration
- ADR-020: Unified Agent Execution
- ADR-037: Autonomous Execution Pipeline
- `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` — Canonical artifact generator
- `plugins/ai/skills/ai_bridge/augur/subagent_profile.py` — SubagentProfile dataclass
- `plugins/ai/skills/ai_bridge/augur/crew_parser.py` — SKILL.md parser
- `plugins/ai/skills/ai_bridge/augur/chain_bridge.py` — Chain-to-command converter
- `plugins/ai/skills/ai_bridge/augur/swarm_bridge.py` — Swarm strategy bridge
- `plugins/ai/skills/ai_bridge/augur/crew_hooks.py` — Crew hook handlers
- `plugins/orchestration/skills/executor/scripts/chain_executor.py` — Chain execution engine
- `plugins/orchestration/skills/swarm/scripts/swarm_executor.py` — Swarm coordinator
- `plugins/orchestration/skills/router/scripts/tier_selector.py` — Tier routing
