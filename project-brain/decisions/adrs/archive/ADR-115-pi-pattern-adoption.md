---
status: Implemented
date: '2026-02-18'
deciders:
- Gur Sannikov
- Claude
related:
- ADR-005 (MCP Execution Gateway)
- ADR-007 (Chain Orchestration)
- ADR-025 (Remote Providers)
- ADR-028 (Two-Layer Memory)
- ADR-030 (Unified AI Bridge)
- ADR-046 (Crew Orchestration Bridge)
- ADR-054 (Swarm Offloading)
- ADR-060 (External Execution Mode)
- ADR-106 (LLM-Assisted Retry)
hub: null
tags:
- selective
- pattern
- adoption
- agent
- toolkit
superseded_by: null
---

# ADR-115: Selective Pattern Adoption from Pi Agent Toolkit

## Context

[Pi](https://github.com/badlogic/pi-mono) (badlogic/pi-mono) is a TypeScript AI agent toolkit (13k stars, MIT license, v0.52.12) with a layered architecture: `pi-ai` (unified LLM API for 15+ providers), `pi-agent-core` (stateful agent runtime with steering), `pi-coding-agent` (terminal coding assistant), and supporting plugins for TUI, web UI, Slack bot, and GPU pod deployment.

Pi is **not a candidate for wholesale integration** — it explicitly rejects MCP (conflicting with ADR-005), has no multi-agent orchestration (Augur already has Agent Teams via ADR-046), and is TypeScript-only (Augur's automation backbone is Python). However, three specific engineering patterns from Pi address confirmed gaps in Augur:

### Current Gaps

| Gap | Current State | Impact |
|-----|--------------|--------|
| **LLM provider abstraction** | `ai_bridge/lib/client.py` supports 3 client types (`OpenAICompatibleClient`, `CommandLLMClient`, `BridgedIdeClient`) with hardcoded cost estimation via URL pattern matching. No streaming. | Adding a new provider requires a new adapter class. Cost tracking is fragile. No real-time token monitoring. |
| **Mid-chain steering** | `chain_executor.py` supports resume from checkpoint but no mid-execution interrupts, user approval gates, or dynamic parameter injection. | Long-running chains can't be paused, redirected, or injected with new context mid-flight. |
| **Session branching/compaction** | Sessions are linear JSONL in `runtime/session-checkpoints/`. No branching, no context summarization, no cross-session search. | Long sessions overflow context windows. Multi-agent team sessions can't track parallel execution paths. |

### Pi's Solutions

1. **`pi-ai`**: Unified API across 15+ providers with automatic model discovery, per-model cost tracking, streaming with granular events, cross-provider context handoffs, and TypeBox schema validation for tools.

2. **Agent loop steering**: Nested loop architecture (outer: follow-ups, inner: tool cycles) with a steering mechanism that can interrupt mid-tool-execution with priority messages, plus a follow-up queue for post-completion injection.

3. **Session tree branching**: JSONL sessions with tree-based history (navigate/fork), automatic compaction (summarize older messages when approaching context limits), and branch summarization.

## Decision

Adopt three patterns from Pi as **Python-native reimplementations** within Augur's existing architecture. No Pi plugins are imported — these are pattern ports, not dependency additions.

### Component 1: Unified Provider Registry

**Problem**: `ai_bridge/lib/client.py` uses URL pattern matching for cost estimation, has no streaming, and adding providers requires new client classes.

**Solution**: Create a declarative provider registry (`config/system/providers.yaml`) and a unified `LLMRouter` class that replaces the current `create_llm_client()` factory.

**Inspired by**: Pi's `pi-ai` package — provider-agnostic API with per-model pricing and streaming events.

#### Actions

1. **Create** `config/system/providers.yaml` — Declarative provider definitions:
   ```yaml
   providers:
     anthropic:
       api: anthropic-messages
       models:
         claude-opus-4-6:
           input_cost_per_1m: 15.00
           output_cost_per_1m: 75.00
           context_window: 200000
           supports_tools: true
           supports_vision: true
           supports_streaming: true
         claude-sonnet-4-6:
           input_cost_per_1m: 3.00
           output_cost_per_1m: 15.00
           context_window: 200000
           supports_tools: true
           supports_vision: true
           supports_streaming: true
         claude-haiku-4-5:
           input_cost_per_1m: 0.80
           output_cost_per_1m: 4.00
           context_window: 200000
           supports_tools: true
           supports_vision: false
           supports_streaming: true
       auth: api_key
       env_var: ANTHROPIC_API_KEY
     openai:
       api: openai-responses
       models:
         gpt-4.1:
           input_cost_per_1m: 2.00
           output_cost_per_1m: 8.00
           context_window: 1047576
           supports_tools: true
           supports_vision: true
           supports_streaming: true
       auth: api_key
       env_var: OPENAI_API_KEY
     glama:
       api: openai-compatible
       base_url: https://glama.ai/api/gateway/openai/v1
       models: auto_discover
       auth: api_key
       env_var: GLAMA_API_KEY
     ollama:
       api: openai-compatible
       base_url: http://localhost:11434/v1
       models: auto_discover
       auth: none
   ```

2. **Create** `plugins/ai/skills/ai_bridge/augur/provider_registry.py` — Registry that loads `providers.yaml`, resolves models to providers, and provides cost lookup:
   - `ProviderRegistry.from_yaml(path)` — load config
   - `registry.resolve(model_name)` — returns provider + model config
   - `registry.estimate_cost(model, input_tokens, output_tokens)` — accurate pricing
   - `registry.list_models(filters)` — query by capability (tools, vision, streaming)

3. **Create** `plugins/ai/skills/ai_bridge/augur/llm_router.py` — Unified router replacing `create_llm_client()`:
   - `LLMRouter(registry, llm_config)` — initialize with provider registry + `llm.yaml` tier config
   - `router.complete(messages, model, tools, stream)` — unified completion API
   - `router.stream(messages, model, tools)` — yields `StreamEvent` objects (text_delta, tool_call_delta, usage_update)
   - Automatic fallback: if primary provider fails, try next provider with same model
   - Built-in usage tracking: tokens, cost, latency per call — written to `runtime/stats/llm-usage.jsonl`

4. **Modify** `plugins/ai/skills/ai_bridge/augur/client.py` — Deprecate `create_llm_client()` in favor of `LLMRouter`. Keep backward-compatible wrapper during migration.

5. **Modify** `config/system/llm.yaml` — Add `default_provider` field and per-tier provider override:
   ```yaml
   default_provider: anthropic
   model_tiers:
     low:
       model: claude-haiku-4-5
       provider: anthropic  # optional override
     medium:
       model: claude-sonnet-4-6
     high:
       model: claude-opus-4-6
   ```

#### Files Created/Modified

| Action | File |
|--------|------|
| Create | `config/system/providers.yaml` |
| Create | `plugins/ai/skills/ai_bridge/augur/provider_registry.py` |
| Create | `plugins/ai/skills/ai_bridge/augur/llm_router.py` |
| Modify | `plugins/ai/skills/ai_bridge/augur/client.py` |
| Modify | `config/system/llm.yaml` |
| Create | `plugins/ai/skills/ai_bridge/tests/test_provider_registry.py` |
| Create | `plugins/ai/skills/ai_bridge/tests/test_llm_router.py` |

### Component 2: Chain Steering and Approval Gates

**Problem**: `chain_executor.py` runs linearly with no mechanism to pause, redirect, or inject context mid-execution.

**Solution**: Add a steering protocol to the chain executor — priority message injection, per-step approval gates, and dynamic parameter override.

**Inspired by**: Pi's `agent-loop.ts` nested loop with steering interrupts and follow-up queue.

#### Actions

1. **Create** `plugins/orchestration/skills/executor/scripts/steering.py` — Steering protocol:
   ```python
   class SteeringSignal:
       CONTINUE = "continue"
       PAUSE = "pause"          # Checkpoint and wait for user
       REDIRECT = "redirect"    # Skip to different step
       INJECT = "inject"        # Add context, then continue
       ABORT = "abort"          # Stop chain gracefully

   class SteeringController:
       def __init__(self, state: ExecutionState):
           self.state = state
           self.signal_file = state.checkpoint_dir / "steering.json"
           self.followup_queue: list[dict] = []

       def check_signal(self) -> SteeringSignal:
           """Called between steps. Reads steering.json for external signals."""

       def inject_context(self, key: str, value: Any):
           """Add/override parameters available to subsequent steps."""

       def queue_followup(self, step_id: str, message: str):
           """Queue a message to inject after current step completes."""

       def request_approval(self, step_summary: str) -> bool:
           """Block until user approves via steering.json or stdin."""
   ```

2. **Modify** `plugins/orchestration/skills/executor/scripts/chain_executor.py` — Integrate steering:
   - Before each step: `controller.check_signal()` — honor pause/redirect/abort
   - After each step: process `followup_queue` — inject queued messages as additional context
   - New chain YAML field: `approval_required: true` on steps that need human sign-off
   - New CLI flag: `--interactive` enables approval gates; default is autonomous
   - Steering file: `runtime/session-checkpoints/{chain_id}/steering.json` — external processes (dashboard, CLI) can write signals

3. **Modify** `plugins/orchestration/skills/executor/scripts/execution_state.py` — Add steering state:
   - `state.injected_params` — dynamic overrides added via steering
   - `state.followup_queue` — pending follow-up messages
   - `state.approval_log` — timestamped record of approvals/rejections

4. **Create** dashboard hook: `plugins/orchestration/skills/executor/api/steering/route.ts` — API route for dashboard to write steering signals (pause, redirect, inject) to the steering file.

#### Files Created/Modified

| Action | File |
|--------|------|
| Create | `plugins/orchestration/skills/executor/scripts/steering.py` |
| Modify | `plugins/orchestration/skills/executor/scripts/chain_executor.py` |
| Modify | `plugins/orchestration/skills/executor/scripts/execution_state.py` |
| Create | `plugins/orchestration/skills/executor/api/steering/route.ts` |
| Create | `plugins/orchestration/skills/executor/tests/test_steering.py` |

### Component 3: Session Tree Branching and Compaction

**Problem**: Sessions are linear. Long sessions overflow context. No branching for multi-agent parallel work.

**Solution**: Replace linear session checkpoints with a tree-structured JSONL format supporting branch/fork, navigation, and automatic compaction.

**Inspired by**: Pi's `sessions.ts` — JSONL tree with branch navigation and automatic summarization.

#### Actions

1. **Create** `plugins/ai/skills/knowledge/lib/session_tree.py` — Tree-structured session storage:
   ```python
   class SessionNode:
       id: str
       parent_id: str | None
       timestamp: datetime
       entry_type: Literal["message", "tool_call", "tool_result", "summary", "branch_point"]
       content: dict
       children: list[str]  # child node IDs

   class SessionTree:
       def __init__(self, session_id: str, storage_dir: Path):
           self.nodes: dict[str, SessionNode] = {}
           self.current_node_id: str | None = None

       def append(self, entry_type, content) -> SessionNode:
           """Add node as child of current node."""

       def branch(self, label: str) -> str:
           """Create branch point, return new branch ID."""

       def switch_branch(self, branch_id: str):
           """Navigate to a different branch."""

       def merge_branches(self, branch_ids: list[str], strategy: str):
           """Merge parallel branches (concat, summarize, or pick-best)."""

       def get_linear_history(self, from_node: str = None) -> list[SessionNode]:
           """Walk from root to current node (for context building)."""

       def compact(self, max_tokens: int, summarizer: Callable) -> int:
           """Summarize older nodes when approaching token limit.
           Returns tokens freed. Replaces N old nodes with 1 summary node."""

       def save(self):
           """Persist to JSONL in storage_dir."""

       @classmethod
       def load(cls, session_id: str, storage_dir: Path) -> "SessionTree":
           """Load from JSONL."""
   ```

2. **Create** `plugins/ai/skills/knowledge/lib/compaction.py` — Context compaction strategies:
   - `summarize_messages(messages, llm_router, max_summary_tokens)` — LLM-based summarization of older context
   - `token_budget_compaction(tree, budget, llm_router)` — automatic compaction when approaching limit
   - `branch_summarization(tree, branch_id, llm_router)` — summarize a completed branch into one node

3. **Modify** `plugins/observability/skills/observe/scripts/list_sessions.py` — Add tree-aware display:
   - Show branch structure with indentation
   - Display compaction history (how many nodes summarized)
   - New flag: `--tree` for visual branch display

4. **Modify** `plugins/ai/skills/knowledge/augur/memory/daily_logger.py` — Use `SessionTree` instead of flat append for daily log entries.

5. **Create** `runtime/sessions/` directory structure:
   ```
   runtime/sessions/
   ├── {session-id}/
   │   ├── tree.jsonl        # Session tree nodes
   │   ├── meta.json         # Session metadata (created, last_active, branch_count)
   │   └── compaction.log    # Record of compaction events
   ```

#### Files Created/Modified

| Action | File |
|--------|------|
| Create | `plugins/ai/skills/knowledge/lib/session_tree.py` |
| Create | `plugins/ai/skills/knowledge/lib/compaction.py` |
| Modify | `plugins/observability/skills/observe/scripts/list_sessions.py` |
| Modify | `plugins/ai/skills/knowledge/augur/memory/daily_logger.py` |
| Create | `plugins/ai/skills/knowledge/tests/test_session_tree.py` |
| Create | `plugins/ai/skills/knowledge/tests/test_compaction.py` |

## Consequences

### Positive

- **Provider coverage**: Declarative registry makes adding providers a YAML edit, not code. Auto-discovery for OpenAI-compatible endpoints.
- **Accurate cost tracking**: Per-model pricing from `providers.yaml` replaces fragile URL pattern matching.
- **Streaming support**: `LLMRouter.stream()` enables real-time token monitoring for dashboard and cost gates.
- **Chain flexibility**: Steering + approval gates enable interactive chains, dashboard-controlled pauses, and mid-flight course corrections.
- **Context efficiency**: Compaction prevents token overflow in long sessions. Estimated 40-60% context savings on sessions >50 messages.
- **Multi-agent session tracking**: Branch/merge in session tree naturally maps to Agent Teams parallel work.
- **No new dependencies**: All three components are Python-native reimplementations. No Pi plugins imported.

### Negative

- **Migration effort**: Existing `create_llm_client()` callers (chain_executor, offload_dispatcher, all adapters) need updating.
- **Compaction quality**: LLM-based summarization may lose important details. Needs careful prompt engineering and opt-out per session.
- **Steering complexity**: Adding pause/inject to chain executor increases state machine complexity. More failure modes to test.
- **Two config files**: `llm.yaml` (tier config) + `providers.yaml` (provider definitions) — must stay synchronized.

### Neutral

- ADR-005 (MCP gateway) is unaffected — these components sit behind MCP, not alongside it.
- ADR-046 (crew orchestration) benefits from session branching but doesn't require changes.
- ADR-054 (offloading) continues to work — `LLMRouter` replaces the client underneath, offload logic stays the same.

## Implementation Order

```
Phase 1: Provider Registry (no dependents)
├── Step 1.1: Create providers.yaml with Anthropic, OpenAI, Glama, Ollama definitions
├── Step 1.2: Create provider_registry.py with model resolution and cost lookup
├── Step 1.3: Create llm_router.py with complete() and stream() APIs
├── Step 1.4: Write tests for registry and router
└── Step 1.5: Update llm.yaml with default_provider field

Phase 2: Chain Steering (depends on Phase 1 for LLM router in approval gates)
├── Step 2.1: Create steering.py with SteeringController
├── Step 2.2: Integrate steering into chain_executor.py
├── Step 2.3: Update execution_state.py with steering state fields
├── Step 2.4: Create dashboard steering API route
└── Step 2.5: Write tests for steering protocol

Phase 3: Session Tree (depends on Phase 1 for LLM router in compaction)
├── Step 3.1: Create session_tree.py with tree CRUD and branch/merge
├── Step 3.2: Create compaction.py with summarization strategies
├── Step 3.3: Update list_sessions.py for tree-aware display
├── Step 3.4: Update daily_logger.py to use SessionTree
└── Step 3.5: Write tests for session tree and compaction

Phase 4: Verification
├── Step 4.1: Run full test suite
├── Step 4.2: Verify backward compatibility (old create_llm_client still works)
└── Step 4.3: Verify no stale path references
```

## Alternatives Considered

### Alternative 1: Import Pi's `pi-ai` Package Directly

Use `@mariozechner/pi-ai` as an npm dependency for the provider layer.

**Rejected because**:
- Augur's automation is Python-based; importing a TS package means Node.js as a required runtime dependency for LLM calls
- Pi explicitly rejects MCP — no alignment with ADR-005
- Pre-1.0 package with single primary maintainer — API stability risk
- Would create a TypeScript island in a Python automation ecosystem

### Alternative 2: Full Pi Framework Integration

Replace Augur's chain executor and session system with Pi's agent-core and coding-agent plugins.

**Rejected because**:
- Pi has no multi-agent orchestration (Augur has Agent Teams, swarm bridge, crew orchestration)
- Pi's tool set is fixed (7 built-in tools) vs Augur's dynamic MCP tool registry
- Would require rewriting 200+ Python scripts and 20+ YAML chains in TypeScript
- Pi's extension model is incompatible with Augur's plugin self-containment (ADR-018)

### Alternative 3: Do Nothing — Keep Current Implementation

Continue with existing `client.py`, linear chains, and flat sessions.

**Rejected because**:
- Cost tracking via URL pattern matching is actively fragile (breaks when providers change endpoints)
- Chain executor's inability to pause/steer blocks interactive workflow use cases (dashboard-driven chains)
- Linear sessions will increasingly overflow context as Augur sessions grow longer with more tools
- All three gaps are confirmed by codebase analysis, not hypothetical

## References

- [Pi Mono repository](https://github.com/badlogic/pi-mono) — Source of patterns (not dependencies)
- ADR-005: MCP Execution Gateway — Augur's tool integration standard (unaffected)
- ADR-007: Chain Orchestration — Current chain architecture (extended by Component 2)
- ADR-025: Remote Providers — Provider registry concept (realized by Component 1)
- ADR-028: Two-Layer Memory — Memory architecture (extended by Component 3)
- ADR-030: Unified AI Bridge — Context algorithm (provider registry complements)
- ADR-046: Crew Orchestration — Agent Teams (benefits from session branching)
- ADR-054: Swarm Offloading — Offload pipeline (uses LLM router underneath)
- ADR-060: External Execution — Chain executor modes (steering extends)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-115: Selective Pattern Adoption from Pi Agent Toolkit**.

Read the full ADR: `docs/decisions/ADR-115-pi-pattern-adoption.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-115-pi-patterns", description="Implementing ADR-115: Selective Pattern Adoption from Pi Agent Toolkit")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-115-pi-patterns", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-115 team.
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

**Team name**: `adr-115-pi-patterns`

#### Phase 1: Provider Registry
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Create `providers.yaml` with Anthropic, OpenAI, Glama, Ollama provider definitions and per-model pricing | `config/system/providers.yaml` |
| 1.2 | developer | medium | Create `provider_registry.py` — load YAML, resolve models, cost lookup, capability queries | `plugins/ai/skills/ai_bridge/augur/provider_registry.py` |
| 1.3 | developer | medium | Create `llm_router.py` — unified `complete()` and `stream()` APIs with fallback, usage tracking to `runtime/stats/llm-usage.jsonl` | `plugins/ai/skills/ai_bridge/augur/llm_router.py` |
| 1.4 | validator | medium | Write tests for provider_registry and llm_router — model resolution, cost calculation, streaming events, fallback behavior | `plugins/ai/skills/ai_bridge/tests/test_provider_registry.py`, `plugins/ai/skills/ai_bridge/tests/test_llm_router.py` |
| 1.5 | developer | low | Update `llm.yaml` with `default_provider` field and per-tier provider override. Add backward-compatible wrapper in `client.py` | `config/system/llm.yaml`, `plugins/ai/skills/ai_bridge/augur/client.py` |

#### Phase 2: Chain Steering
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create `steering.py` — SteeringController with signal checking, context injection, follow-up queue, approval gates via `steering.json` | `plugins/orchestration/skills/executor/scripts/steering.py` |
| 2.2 | developer | medium | Integrate steering into `chain_executor.py` — check signals between steps, process follow-up queue, honor `approval_required` YAML field, add `--interactive` flag | `plugins/orchestration/skills/executor/scripts/chain_executor.py` |
| 2.3 | developer | low | Update `execution_state.py` — add `injected_params`, `followup_queue`, `approval_log` fields with serialization | `plugins/orchestration/skills/executor/scripts/execution_state.py` |
| 2.4 | developer | medium | Create dashboard steering API route — POST endpoint to write steering signals (pause, redirect, inject, abort) | `plugins/orchestration/skills/executor/api/steering/route.ts` |
| 2.5 | validator | medium | Write steering tests — signal file parsing, approval gates, follow-up queue ordering, chain interruption/resume | `plugins/orchestration/skills/executor/tests/test_steering.py` |

#### Phase 3: Session Tree
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Create `session_tree.py` — SessionNode, SessionTree with append, branch, switch_branch, merge_branches, get_linear_history, save/load JSONL | `plugins/ai/skills/knowledge/lib/session_tree.py` |
| 3.2 | developer | medium | Create `compaction.py` — LLM-based summarization, token budget compaction, branch summarization using LLMRouter from Phase 1 | `plugins/ai/skills/knowledge/lib/compaction.py` |
| 3.3 | developer | low | Update `list_sessions.py` — add `--tree` flag for branch visualization, show compaction history | `plugins/observability/skills/observe/scripts/list_sessions.py` |
| 3.4 | developer | medium | Update `daily_logger.py` — use SessionTree for structured logging instead of flat append | `plugins/ai/skills/knowledge/augur/memory/daily_logger.py` |
| 3.5 | validator | medium | Write session tree and compaction tests — branch/merge, JSONL round-trip, compaction token savings, linear history extraction | `plugins/ai/skills/knowledge/tests/test_session_tree.py`, `plugins/ai/skills/knowledge/tests/test_compaction.py` |

#### Phase 4: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 4.1 | validator | low | Run full test suite: `pytest` for Python, `npm run build` for TypeScript. Verify no regressions. |
| 4.2 | validator | low | Verify backward compatibility — old `create_llm_client()` callers still work via wrapper |
| 4.3 | architect | medium | Verify ADR-115 intent matches implementation — review all created files against ADR spec |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest`, `npm run build`)
- [ ] No orphaned files or broken references
- [ ] `providers.yaml` has at least 4 providers defined
- [ ] `LLMRouter.stream()` yields `StreamEvent` objects
- [ ] Chain steering works with `--interactive` flag
- [ ] Session tree supports branch/fork/merge operations
- [ ] Compaction reduces token count by >30% on test data
- [ ] ADR status updated to "Accepted" or "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-115-pi-pattern-adoption.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
