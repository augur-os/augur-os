---
status: Implemented
date: '2026-02-22'
deciders:
- Project team
related:
- ADR-134 (Dispatch Escalation Pattern)
- ADR-130 (Action Button Dispatch Modes)
- ADR-106 (LLM-Assisted Retry)
- ADR-135 (Cowork Integration)
hub: null
tags:
- eliminate
- direct
- llm
- calls
- scripts
superseded_by: null
---

# ADR-137: Eliminate Direct LLM Calls from Scripts

## Context

Multiple Python scripts across the codebase make direct LLM API calls via `create_llm_client()` or raw HTTP requests (Ollama, OpenAI-compatible endpoints). This is architecturally wrong in two distinct scenarios:

1. **Scripts invoked from an agent session** (e.g. during `/merge`, from MCP tools, or as slash command implementations): The calling IDE agent IS the LLM — external dispatch wastes tokens, adds latency, and can route to the wrong model (e.g. Kimi instead of Claude due to hardcoded preferences).

2. **Scripts running headless** (daemon, cron, background services): These legitimately need LLM access outside of an interactive session, but should use a standardized dispatch pattern (CLI subprocess) rather than ad-hoc HTTP calls with bespoke retry/fallback logic.

ADR-135 step 7.5 exposed this when `classify_collateral.py` was calling Ollama/Kimi to classify files while running inside a Claude Code session that could do the classification inline. That script has been refactored to a 2-step context-gather + agent-inline pattern. This ADR addresses the remaining 6 scripts.

### Affected Scripts

| # | Script | LLM Pattern | Execution Context | Recommendation |
|---|--------|-------------|-------------------|----------------|
| 1 | `plugins/orchestration/skills/executor/scripts/backlog/refactor_backlog.py` | `create_llm_client()` → `client.generate_text()` | Standalone script, invoked manually | Agent-inline: 2-step context/route pattern |
| 2 | `plugins/orchestration/skills/executor/scripts/backlog/generate.py` | `create_llm_client()` → `client.generate_text()` with hardcoded OpenAI fallback | Standalone script, invoked manually | Agent-inline: wrap as slash command |
| 3 | `plugins/ai/skills/rag/scripts/search_engine.py` | `create_llm_client()` → `client.generate_json()` with circuit breaker + 5-retry exponential backoff | Library component called by RAG search pipeline | Keep as library; expose evaluation step via MCP tool; circuit breaker state stays in-process |
| 4 | `plugins/ai/skills/mcp-app-factory/scripts/skill_generation/source_extractor.py` | `create_llm_client()` → `client.generate_json()` with graceful fallback | Embedded in MCP app factory creation flow | Agent-inline: extraction is a one-shot analysis |
| 5 | `plugins/dev/skills/developer/scripts/run_prompt.py` | `create_llm_client()` → `client.generate_text()` via prompt registry | Called from MCP tool `run_intelligence_prompt()` via subprocess | Refactor MCP tool to pass prompt to agent instead of subprocess→LLM |
| 6 | `plugins/observability/skills/daemon/scripts/ai_self_healer.py` (`classify_issue()`) | CLI subprocess dispatch (`resolve_cli()` → `[cli, "--print", "-p", prompt]`) | Long-running daemon (background service) | Keep CLI dispatch; already correct pattern for headless. Ensure dynamic CLI resolution (done). |

### LLM Client Infrastructure

The scripts above use two LLM client libraries:

- **`src/llm/client.py`** + **`src/llm/config.py`**: Legacy client with `create_llm_client()`, `load_llm_config()`, `resolve_llm_profile()`. Used by scripts 1, 2, 4, 5.
- **`plugins/ai/skills/ai_bridge/augur/lib/client.py`**: Newer client with `OpenAICompatibleClient`, `CommandLLMClient`, `BridgedIdeClient`. Used by script 3. `BridgedIdeClient` is the correct agent-inline pattern.

After this refactoring, `src/llm/client.py` should have zero call sites and can be deprecated.

## Decision

### Phase 1: Agent-Inline Refactoring (Scripts 1, 2, 4)

Refactor to the 2-step pattern established in `classify_collateral.py`:

**Step 1 — Context mode**: Script gathers data, builds prompt, outputs JSON to stdout.
**Step 2 — Execute mode**: Script accepts the agent's response and performs the action.

The calling agent (or slash command/MCP tool) reads the context JSON, performs inline LLM reasoning (it IS the LLM), and feeds the result back.

```
# Example: backlog generation
python3 generate.py <agent> --mode context    → JSON {prompt, context, schema}
# Agent reasons inline
python3 generate.py <agent> --mode write --result '{...}'  → writes backlog file
```

### Phase 2: MCP Tool Consolidation (Script 5)

`run_prompt.py` is called from the MCP tool `run_intelligence_prompt()` which spawns a subprocess that creates its own LLM client. Refactor the MCP tool to:
1. Load the prompt template and apply variables
2. Return the assembled prompt to the calling agent
3. Let the agent execute the prompt inline

### Phase 3: RAG Search Evaluation (Script 3)

`search_engine.py` has the most complex LLM integration — circuit breaker, exponential backoff, JSON output parsing. Two options:

**Option A (Preferred)**: Keep the LLM evaluation in the library but make the client injectable. When called from an agent session, inject a `BridgedIdeClient`. When called headless, use the existing `OpenAICompatibleClient`. The circuit breaker stays in-process.

**Option B**: Split into search (no LLM) + evaluate (agent-inline). This loses the circuit breaker's session-level state but simplifies the architecture.

### Phase 4: Deprecate `src/llm/client.py`

Once scripts 1, 2, 4, 5 no longer import from `src/llm/`, mark the module as deprecated with a `TODO_CLEANUP` marker. Remove after one release cycle.

### Not Changed

- **`ai_self_healer.py`** (script 6): Already uses CLI subprocess dispatch, which is correct for a headless daemon. Dynamic CLI resolution was fixed separately (hardcoded `["claude", "kimi"]` → dynamic `_get_cli_candidates()` from `cli_agents.yaml`).
- **`plugins/ai/skills/ai_bridge/augur/lib/client.py`**: Infrastructure library — stays as-is. `BridgedIdeClient` is the reference implementation for agent-inline dispatch.

## Consequences

### Positive
- Scripts running inside agent sessions use the session's own LLM instead of making redundant external calls
- Eliminates model routing bugs (e.g. Kimi called instead of Claude due to Ollama model preferences)
- Reduces latency: no HTTP round-trip to Ollama/OpenAI when the agent can classify inline
- `src/llm/client.py` can be deprecated, reducing maintenance surface
- All CLI resolution uses dynamic discovery from `cli_agents.yaml` instead of hardcoded lists

### Negative
- 2-step pattern requires updating all callers (slash commands, MCP tools, workflows)
- RAG search evaluation refactoring (Phase 3) is non-trivial due to circuit breaker state
- Transition period where some scripts use old pattern and some use new

### Risks
- RAG search quality could degrade if the agent-inline evaluation path has different behavior than the tuned `generate_json()` path with temperature/max_tokens controls
- Scripts that currently work standalone (backlog tools) will require an agent session after refactoring — need to document the new invocation pattern

## Implementation Order

1. Scripts 1 + 2 (backlog tools) — low risk, isolated, good proof of concept
2. Script 4 (source_extractor) — medium risk, embedded in creation flow
3. Script 5 (run_prompt) — medium risk, MCP tool change
4. Script 3 (search_engine) — high complexity, defer to separate PR
5. Deprecate `src/llm/client.py` — after all call sites removed
