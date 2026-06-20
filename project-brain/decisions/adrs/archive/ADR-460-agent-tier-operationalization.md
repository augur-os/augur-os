---
status: Implemented
date: 2026-03-20
deciders:
  - Gur Sannikov
related:
  - ADR-020
  - ADR-426
  - ADR-096
  - ADR-046
hub: null
tags:
  - agents
  - subagents
  - model-routing
  - tiers
  - safety
  - performance
superseded_by: null
---

# ADR-460: Agent Tier Operationalization — Adaptive Model Routing for Subagents

## Context

All 14 Claude Code subagents are currently generated as advisory-only with `mode: advisory`, `tools: [Read, Glob, Grep]`, and empty `tiers: {}`. The three-tier system (fast/standard/deep mapped to haiku/sonnet/opus) is defined in `SubagentProfile` but never populated from SKILL.md. This creates two concrete problems:

1. **Agents that should write code cannot.** Developer, devops, and dev-merge agents are generated with read-only tools despite their executor role. Every task requiring file edits falls back to the parent agent.
2. **No model differentiation exists.** Every task uses sonnet regardless of complexity. Simple lookups that haiku could handle in milliseconds consume full sonnet context. Deep architectural reviews that need opus reasoning are under-served.

The `SubagentProfile` dataclass already has the `tiers` field, and `sync_agents.py` already generates `.claude/agents/{name}.md` files. The infrastructure exists — what's missing is the declaration format, the generation pipeline, the routing logic, and the feedback loop.

## Decision

Implement four subsystems that together operationalize the agent tier system.

### Subsystem 1: SKILL.md Agent Declaration (`x-augur-agent`)

Each agent-class skill declares its full capability profile in SKILL.md frontmatter via a new `x-augur-agent` block:

```yaml
x-augur-agent:
  role: executor          # executor | advisor | orchestrator
  specialization: "code generation and refactoring"
  default-model: sonnet
  tiers:
    fast:
      model: haiku
      tools: [Read, Glob, Grep]
      context-budget: 32000
      cost-multiplier: 0.1
      appropriate-for:
        - simple lookups
        - file existence checks
        - pattern searches
      inappropriate-for:
        - multi-file edits
        - architectural decisions
    standard:
      model: sonnet
      tools: [Read, Edit, Write, Glob, Grep, Bash]
      context-budget: 128000
      cost-multiplier: 1.0
      appropriate-for:
        - feature implementation
        - bug fixes
        - test writing
      inappropriate-for:
        - cross-system refactoring
    deep:
      model: opus
      tools: [Read, Edit, Write, Glob, Grep, Bash]
      context-budget: 200000
      cost-multiplier: 5.0
      appropriate-for:
        - architectural refactoring
        - complex debugging
        - cross-system changes
      inappropriate-for:
        - simple lookups
  safety:
    max-file-edits-per-run: 20
    max-file-creates-per-run: 5
    max-bash-commands-per-run: 30
    banned-paths:
      - "**/.env*"
      - "**/credentials*"
      - "**/secrets*"
    require-confirmation:
      - "config/**"
      - "CLAUDE.md"
    banned-operations:
      - "git push --force"
      - "rm -rf /"
  escalation:
    auto-escalate-on:
      - "3 consecutive failures at current tier"
      - "context budget exceeded"
      - "task complexity score > 0.8"
    escalation-path: fast -> standard -> deep -> parent
    max-escalations-per-task: 2
    cooldown: 300  # seconds before re-attempting lower tier
```

Skills without `x-augur-agent` default to: `role: advisor`, `default-model: sonnet`, `tools: [Read, Glob, Grep]`, `tiers: {}`, no safety overrides, no escalation.

### Subsystem 2: Generator Pipeline (`sync_agents` changes)

Four phases, run in sequence by `sync_agents.py`:

**Phase 1 — Parse.** Extract `x-augur-agent` from each agent-class SKILL.md frontmatter. Validate against a JSON schema stored at `src/config/schemas/agent-profile.schema.json`. Report validation errors with file path and field name. Skills without `x-augur-agent` get defaults.

**Phase 2 — Generate agent files.** Write `.claude/agents/{name}.md` with:
- `mode` derived from `role` (executor/orchestrator -> `code`, advisor -> `advisory`)
- `model` from `default-model`
- `tools` from the default tier's tool list
- Safety constraints embedded in the system prompt as behavioral rules
- Context management instructions derived from `context-budget`
- Escalation rules embedded as conditional instructions

**Phase 3 — Generate registry.** Write `src/generated/registry.json` at schema version `2.0` with full capability manifest:
- All fields from `x-augur-agent` per agent
- Tier details including model, tools, cost-multiplier
- Safety and escalation configuration
- Performance stubs (populated later by the ledger)
- Backward-compatible: v1.0 consumers see flat `mode`/`model`/`tools` fields at the top level

**Phase 4 — Drift detection.** `sync_agents.py --check` compares generated output against existing files. Non-zero exit if drift detected. Suitable for CI and pre-commit hooks.

### Subsystem 3: Tier Router

**Phase 1 (this ADR): Static routing.** The caller specifies the tier explicitly. Three entry points:

1. **Parent agent dispatch** — When spawning a subagent via `Agent` tool, the parent includes a `tier` parameter derived from task analysis (keyword signals, file count, scope).
2. **`useActionRunner` dispatch** — Dashboard actions specify tier in action metadata (`augur.yaml` action definition includes `tier: fast|standard|deep`).
3. **Default fallback** — If no tier specified, use `default-model` from the agent's profile.

Static routing rules:
- Actions tagged `quick-check`, `lookup`, `search` route to `fast`
- Actions tagged `implement`, `fix`, `build`, `test` route to `standard`
- Actions tagged `refactor`, `architect`, `debug-complex` route to `deep`

**Phase 2 (future ADR): Adaptive routing.** After the performance ledger accumulates 50+ completed tasks per agent, a lightweight classifier (logistic regression on task signals) predicts the optimal tier. Requires a separate ADR when the data is available.

### Subsystem 4: Performance Ledger

**Storage:** `~/Library/Application Support/Augur/state/agents/performance.json`

**Per-task record:**
```json
{
  "id": "uuid",
  "timestamp": "ISO-8601",
  "agent": "developer",
  "tier": "standard",
  "model": "sonnet",
  "tokens_in": 45000,
  "tokens_out": 3200,
  "duration_seconds": 12.4,
  "files_edited": 3,
  "files_created": 0,
  "outcome": "success",
  "task_signals": ["implement", "single-file"],
  "escalated_from": null
}
```

**Aggregates** (computed on write, stored alongside records):
```json
{
  "agent": "developer",
  "tier": "standard",
  "total_tasks": 142,
  "success_rate": 0.93,
  "avg_tokens": 38000,
  "avg_duration_seconds": 11.2,
  "last_updated": "ISO-8601"
}
```

**Collection points:**
- `useActionRunner` completion callback writes the record
- PTY output parsing extracts token counts and duration from Claude Code subagent output
- Escalation events create linked records (original + escalated)

**Maintenance:**
- Nightly compaction: records older than 30 days are rolled into aggregates and deleted
- Compaction runs as a daemon task via the existing nightly schedule
- File size cap: 10MB, oldest records evicted first if exceeded

**Dashboard observability:**
- Enhanced `/api/agents/telemetry` endpoint exposes aggregates
- Per-agent success rate, cost breakdown, tier distribution charts

### Agent Classification

| Agent | Role | Default Tier | Default Model | Tools |
|---|---|---|---|---|
| developer | executor | standard | sonnet | Read, Edit, Write, Glob, Grep, Bash |
| devops | executor | standard | sonnet | Read, Edit, Write, Glob, Grep, Bash |
| dev-build | executor | standard | sonnet | Read, Edit, Write, Glob, Grep, Bash |
| dev-merge | executor | standard | sonnet | Read, Edit, Write, Glob, Grep, Bash |
| dev-debug | orchestrator | standard | sonnet | Read, Edit, Write, Glob, Grep, Bash, Agent |
| dev-rollback | executor | standard | sonnet | Read, Edit, Write, Glob, Grep, Bash |
| dev-test | executor | standard | sonnet | Read, Edit, Write, Glob, Grep, Bash |
| dev-adr | executor | standard | sonnet | Read, Edit, Write, Glob, Grep, Bash |
| frontend | executor | standard | sonnet | Read, Edit, Write, Glob, Grep, Bash |
| mcp-app-factory | executor | standard | sonnet | Read, Edit, Write, Glob, Grep, Bash |
| test-client | executor | standard | sonnet | Read, Edit, Write, Glob, Grep, Bash |
| advisor | advisor | standard | sonnet | Read, Glob, Grep |
| test-ui | advisor | standard | sonnet | Read, Glob, Grep |
| validator | advisor | deep | opus | Read, Glob, Grep |

### Backward Compatibility

- **Skills without `x-augur-agent`** default to advisory/sonnet/[Read, Glob, Grep] — identical to current behavior.
- **`registry.json` schema version 2.0** includes a top-level `schema_version` field. Consumers that don't check version see the same flat fields at the top level (mode, model, tools). New fields (tiers, safety, escalation, performance) are additive.
- **Generated `.claude/agents/*.md` files** remain valid Claude Code agent definitions. The mode/model/tools fields are standard Claude Code features. Safety and escalation rules are embedded as natural-language instructions in the system prompt — Claude Code processes them as behavioral guidance, not as a proprietary schema.

## Consequences

### Positive

- Agents can actually perform their intended function — executors get write tools, orchestrators get the Agent tool
- Cost optimization — haiku for simple lookups (~10x cheaper), opus only when justified by task complexity
- Safety boundaries prevent runaway agents — file edit limits, banned paths, confirmation gates
- Performance data enables future adaptive routing with real evidence
- Escalation paths prevent stuck agents — automatic tier promotion on repeated failure
- Full observability via performance ledger and dashboard telemetry

### Negative

- More complex `sync_agents` pipeline — four phases instead of one, JSON schema validation, drift detection
- SKILL.md frontmatter grows significantly for agent-class skills (mitigated by sensible defaults and JSON schema documentation)
- Performance ledger adds disk I/O on every task completion (mitigated by append-only writes and nightly compaction)

### Risks

- **Executor agents with write access can cause damage.** Mitigated by: safety constraints in agent profile (max edits, banned paths, banned operations), Claude Code's built-in permission system (user confirmation for destructive operations), and escalation cooldowns that prevent rapid-fire retries.
- **Tier router makes wrong choice in static phase.** Mitigated by: explicit tier override always available, escalation path promotes automatically on failure, and static phase is intentionally conservative (defaults to standard).
- **Performance ledger data quality.** PTY parsing for token counts is fragile. Mitigated by: graceful handling of missing data (record with null token fields is still valid), and dashboard telemetry degrades gracefully to showing only available fields.

## Alternatives Considered

### Alternative 1: Hardcoded Agent Profiles in `sync_agents.py`

Define all agent capabilities directly in the generator script. Rejected: violates the plugin decentralization principle (CLAUDE.md Critical Rule #2). Agent capabilities should live with the skill, not in a central script.

### Alternative 2: Runtime Model Selection via MCP Tool

Add an MCP tool that dynamically selects the model at task dispatch time. Rejected: adds latency to every agent invocation, requires MCP server to be running for agent generation, and conflates generation-time configuration with runtime behavior.

### Alternative 3: Skip Tiers, Just Fix Tools

Only fix the tools assignment (give executors write tools) without implementing the tier system. Rejected: solves the immediate pain but misses the cost optimization and adaptive routing opportunity. The tier infrastructure is needed for Phase 2 adaptive routing.

### Alternative 4: External Config File for Agent Profiles

Store agent profiles in `config/agents/*.yaml` separate from SKILL.md. Rejected: creates a second source of truth for agent capabilities. SKILL.md is already the canonical skill definition — agent profiles belong there.

## References

- ADR-020: Local Agent Orchestration — original subagent architecture
- ADR-426: Client-Native Skill Mastering — `.claude/skills/` structure
- ADR-096: Progressive Disclosure Agent Instructions — agent instruction layering
- ADR-046: Claude Code Crew Orchestration Bridge — team coordination patterns
- `SubagentProfile` dataclass: `src/agents/profiles.py` (or equivalent in sync_agents)
- `sync_agents.py`: current generator script

## Implementation Prompt

**Team name**: `adr-460-agent-tiers`

### Phase 1: Schema and Declaration
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create JSON schema for `x-augur-agent` validation | `src/config/schemas/agent-profile.schema.json` |
| 1.2 | developer | medium | Add `x-augur-agent` frontmatter to all 14 agent SKILL.md files per classification table | `.claude/skills/*/SKILL.md`, `plugins/*/skills/*/SKILL.md` |
| 1.3 | dev-test | low | Validate all SKILL.md files parse correctly against schema | — |

### Phase 2: Generator Pipeline
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | high | Phase 1-2: Parse `x-augur-agent`, generate agent .md files with correct mode/model/tools/safety/escalation | `src/scripts/sync_agents.py` |
| 2.2 | developer | high | Phase 3: Generate registry.json v2.0 with full capability manifest | `src/scripts/sync_agents.py`, `src/generated/registry.json` |
| 2.3 | developer | medium | Phase 4: Implement `--check` drift detection mode | `src/scripts/sync_agents.py` |
| 2.4 | dev-test | medium | Unit tests for all four phases | `src/tests/test_sync_agents.py` |

### Phase 3: Performance Ledger
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Ledger module: record, aggregate, compaction | `src/agents/performance_ledger.py` |
| 3.2 | developer | medium | Wire useActionRunner completion to ledger | `apps/dashboard/lib/action-runner.ts` |
| 3.3 | developer | low | Nightly compaction task registration in daemon | `.claude/skills/daemon/scripts/nightly_tasks.py` |
| 3.4 | frontend | medium | Dashboard telemetry endpoint and agent performance charts | `apps/dashboard/app/api/agents/telemetry/route.ts` |

### Phase 4: Static Tier Router
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Router module: resolve tier from explicit param, action metadata, keyword signals | `src/agents/tier_router.py` |
| 4.2 | developer | medium | Wire router into parent agent dispatch and useActionRunner | `src/agents/dispatch.py`, `apps/dashboard/lib/action-runner.ts` |
| 4.3 | dev-test | medium | Integration tests: routing decisions, escalation flow, safety constraint enforcement | `src/tests/test_tier_router.py` |

### Phase 5: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | dev-test | medium | Run `sync_agents.py`, verify all 14 agents generate with correct mode/tools | — |
| 5.2 | dev-test | medium | Run `sync_agents.py --check`, verify drift detection works | — |
| 5.3 | validator | deep | End-to-end: dispatch a task to an executor agent, verify it can write files, verify ledger records the outcome | — |

### Completion Criteria

- [ ] All 14 agent SKILL.md files have valid `x-augur-agent` frontmatter
- [ ] `agent-profile.schema.json` validates all declarations
- [ ] `sync_agents.py` generates agent files with correct mode (code/advisory), model, and tools
- [ ] `registry.json` v2.0 contains full tier/safety/escalation data per agent
- [ ] `sync_agents.py --check` returns non-zero on drift
- [ ] Executor agents (developer, devops, dev-merge, etc.) have write tools (Edit, Write, Bash)
- [ ] Advisor agents (advisor, test-ui) remain read-only
- [ ] Validator agent defaults to opus/deep tier
- [ ] Performance ledger records task completions with token/duration/outcome data
- [ ] Nightly compaction runs and respects 30-day retention
- [ ] Dashboard `/api/agents/telemetry` returns per-agent performance aggregates
- [ ] Static tier router resolves tier from action metadata and keyword signals
- [ ] Escalation promotes tier after 3 consecutive failures
- [ ] Safety constraints are enforced (banned paths, max edits) in generated agent prompts
- [ ] Backward compatibility: skills without `x-augur-agent` generate identical to current output
- [ ] ADR status updated to Implemented
