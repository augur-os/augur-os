---
status: Implemented
date: '2026-02-13'
deciders:
- Gur Sannikov
related:
- ADR-039 (CLI Integration)
- ADR-046 (Crew Orchestration Bridge)
- ADR-054 (Offloading)
- ADR-063 (MCP Implementation Hardening)
- ADR-084 (Self-Heal)
hub: null
tags:
- cli
- agent
- live
- testing
superseded_by: null
---

# ADR-092: CLI Agent Live Testing

## Context

The AI bridge supports 13 adapters (7 CLI agents, 4 IDE adapters, 1 SDK, 1 local LLM) but health checks today are **shallow**:

| Current Check | What It Actually Tests |
|---------------|----------------------|
| `detect()` | `shutil.which(cli_command)` — binary exists in PATH |
| `ensure_config()` | MCP config JSON is syntactically correct |
| `health_check()` | Combines detection + `render_intent()` command generation |
| `ide_integration_health.py` | Orchestrates the above per adapter |

**None of these actually invoke the CLI.** A binary can exist in PATH but be broken (wrong version, expired auth, missing runtime deps, MCP server unreachable). The current system reports "healthy" for agents that can't actually run.

### Specific gaps

1. **No live execution** — never actually runs `kimi`, `claude`, `codex` etc.
2. **No MCP round-trip** — never verifies the agent can connect to the Augur MCP server and call a tool
3. **No auth validation** — never checks if API keys / tokens are valid
4. **No version compatibility** — never checks if installed CLI version is compatible
5. **No response quality** — never verifies the agent produces coherent output
6. **No network connectivity** — never checks if the agent can reach its API endpoint
7. **No latency measurement** — no baseline for how long agent responses take

### Current agent inventory

| Agent | CLI Command | Type |
|-------|-------------|------|
| Claude Code | `claude` | CLI |
| Kimi CLI | `kimi` | CLI |
| Codex CLI | `codex` | CLI |
| Copilot CLI | `copilot` | CLI |
| Cursor CLI | `cursor-agent` | CLI |
| Juls | `juls` | CLI |
| OpenCode | `opencode` | CLI |
| Cursor IDE | (app) | IDE |
| VS Code Copilot | (app) | IDE |
| Antigravity | (app) | IDE |
| Claude Desktop | (app) | IDE |
| Claude SDK | (library) | SDK |
| Ollama | `ollama` | Local |

## Decision

Implement a **live test framework** for CLI agents that actually executes each agent and validates the full communication stack. Expose it as `/client-test <agent>` slash command and as an MCP tool.

### 1. Live Test Protocol

Each live test runs a **graduated probe sequence** — fast checks first, expensive checks last, with early-exit on failure:

```
Level 0: Binary Check       (< 1s)   — CLI exists, is executable, correct version
Level 1: Auth Check          (< 2s)   — API key/token is valid, not expired
Level 2: MCP Handshake       (< 5s)   — Agent can discover and connect to Augur MCP server
Level 3: Tool Invocation     (< 10s)  — Agent calls `health` MCP tool, gets valid response
Level 4: Round-Trip          (< 30s)  — Agent receives a prompt, processes it, returns structured output
Level 5: Quality Gate        (< 30s)  — Response matches expected format and content (optional)
```

### 2. Test Script: `client_live_test.py`

**Location**: `plugins/ai/skills/ai_bridge/scripts/client_live_test.py`

**Interface**:
```bash
# Test single agent
python3 plugins/ai/skills/ai_bridge/scripts/client_live_test.py --agent kimi

# Test all installed agents
python3 plugins/ai/skills/ai_bridge/scripts/client_live_test.py --all

# Specific level only
python3 plugins/ai/skills/ai_bridge/scripts/client_live_test.py --agent claude --level 3

# JSON output (for CI/dashboard)
python3 plugins/ai/skills/ai_bridge/scripts/client_live_test.py --agent kimi --json

# Quick mode (levels 0-2 only, no LLM calls)
python3 plugins/ai/skills/ai_bridge/scripts/client_live_test.py --agent kimi --quick

# Verbose (show full agent output)
python3 plugins/ai/skills/ai_bridge/scripts/client_live_test.py --agent kimi --verbose
```

**Output format**:
```json
{
  "agent": "kimi_cli",
  "cli_command": "kimi",
  "timestamp": "2026-02-13T10:30:00Z",
  "overall": "pass",
  "duration_ms": 4200,
  "levels": {
    "0_binary": {"pass": true, "duration_ms": 50, "details": {"version": "1.2.3", "path": "/usr/local/bin/kimi"}},
    "1_auth": {"pass": true, "duration_ms": 800, "details": {"provider": "moonshot", "expires": "2026-03-01"}},
    "2_mcp_handshake": {"pass": true, "duration_ms": 1200, "details": {"tools_discovered": 45}},
    "3_tool_invocation": {"pass": true, "duration_ms": 900, "details": {"tool": "health", "response_valid": true}},
    "4_round_trip": {"pass": true, "duration_ms": 1250, "details": {"prompt": "echo test", "response_length": 42}},
    "5_quality_gate": {"pass": null, "duration_ms": 0, "details": {"skipped": "not requested"}}
  }
}
```

### 3. Per-Agent Test Implementations

Each CLI adapter in `adapters/` gets a new method `live_test(level: int) -> dict` on the base class `CliAgentAdapter`. Agent-specific commands are defined per adapter since CLIs differ:

| Agent | Level 0 | Level 1 | Level 2-3 | Level 4 |
|-------|---------|---------|-----------|---------|
| Claude Code | `claude --version` | `claude --print-api-key-status` | `claude --mcp` invoke health | `claude -p "echo test"` |
| Kimi CLI | `kimi --version` | `kimi info` | `kimi mcp` invoke health | `kimi -p "echo test"` |
| Codex CLI | `codex --version` | `codex auth status` | `codex mcp` invoke health | `codex -p "echo test"` |
| OpenCode | `opencode --version` | `opencode auth` | MCP config check | `opencode -p "echo test"` |
| Copilot CLI | `copilot --version` | `copilot auth status` | N/A (no MCP) | `copilot -p "echo test"` |
| Juls | `juls --version` | `juls auth` | MCP config check | `juls -p "echo test"` |

Each agent defines its specific commands via an abstract method:

```python
# In cli_agent_base.py
@abstractmethod
def get_live_test_commands(self) -> dict[str, list[str]]:
    """Return CLI commands for each test level.

    Returns:
        Dict mapping level names to command args lists.
        Example: {"version": ["--version"], "auth": ["info"], "mcp": ["mcp", "list-tools"]}
    """
```

### 4. MCP Self-Test Tool

A new Augur MCP tool `client-test` that can be invoked from any agent:

```python
# In MCP tool registry
@tool("client-test")
def client_test(agent: str = "all", level: int = 4, quick: bool = False) -> dict:
    """Run live test against a CLI agent or all agents."""
```

This means any agent (including the one being tested) can trigger a test of another agent — enabling cross-agent validation.

### 5. Slash Command: `/client-test`

**Location**: `plugins/ai/skills/ai_bridge/augur/agent-workflows/client-test.md`

Synced to all IDEs via `sync_agents.py`.

**Usage**:
```bash
/client-test kimi          # Test kimi with full probe (levels 0-4)
/client-test claude --quick # Test claude, levels 0-2 only (no LLM calls)
/client-test --all          # Test all installed agents
/client-test kimi --level 3 # Test kimi up to MCP tool invocation
/client-test --report       # Run all and generate markdown report
```

**Workflow**: The slash command invokes the `client_live_test.py` script, displays results in a formatted table, and optionally writes a report to `runtime/diagnostics/client-test-{timestamp}.json`.

### 6. Test Results Storage

**Location**: `runtime/diagnostics/`

```
runtime/diagnostics/
├── client-test-latest.json         # Symlink to most recent full run
├── client-test-2026-02-13.json     # Daily snapshot
└── client-test-history/            # Rolling 30-day history
```

The dashboard Settings > AI > Integrations tab (`IntegrationsTab.tsx`) will read from the API endpoint to show live test status with pass/fail badges per agent.

### 7. Additional Test Coverage Areas

Beyond the core protocol, the live test should also probe:

| Test Area | What It Validates | Level |
|-----------|------------------|-------|
| **Config drift** | Agent's MCP config matches what `sync_agents.py` would generate | 2 |
| **Rules sync** | Agent instructions file (CLAUDE.md, .cursorrules, etc.) matches canonical `agent-rules.md` hash | 0 |
| **Workflow sync** | Slash command files match canonical versions | 0 |
| **Memory sync** | Agent's MEMORY.md matches canonical `docs/memory/MEMORY.md` hash | 0 |
| **Token budget** | Agent respects context limits (doesn't load 200K+ context) | 4 |
| **Timeout resilience** | Agent responds within expected latency (5s for simple, 30s for complex) | 4 |
| **Error recovery** | Agent handles malformed MCP response gracefully | 4 |
| **Concurrent access** | Two agents can use MCP server simultaneously without deadlock | 5 |
| **File write safety** | Agent writes to expected paths, doesn't touch files outside workspace | 4 |
| **Idempotency** | Running the same prompt twice produces consistent results | 5 |

### 8. Dashboard API Endpoint

**Location**: `plugins/ai/skills/ai_bridge/augur/api/client-test/route.ts`

```typescript
// GET /api/hub/ai/client-test?agent=kimi
// GET /api/hub/ai/client-test?all=true
// Returns JSON with test results
```

### 9. Integration with Existing Systems

| System | Integration |
|--------|-------------|
| **Nightly CI** | `/nightly` runs `--all --quick` (levels 0-2) as part of health sweep |
| **Self-Heal (ADR-084)** | Failed live test emits `self_heal_event` for auto-remediation |
| **Offload (ADR-054)** | Live test validates offload target agents are actually responsive before dispatching |
| **Observe Hub** | Test results feed into observability dashboard |
| **cli-smoke-test chain** | Existing chain upgraded to call `client_live_test.py` instead of manual checks |

## Consequences

### Positive

- **Real confidence**: Health status reflects actual agent capability, not just binary presence
- **Fast debugging**: `/client-test kimi` immediately shows exactly where the failure is (auth? MCP? network?)
- **Cross-agent validation**: Any agent can test any other agent via MCP tool
- **Offload safety**: Verify offload targets work before wasting tokens
- **Nightly regression**: Catch agent breakage (version updates, expired keys) automatically
- **Config drift detection**: Rules/workflows/memory sync issues caught before they cause subtle bugs

### Negative

- **API cost**: Level 4+ tests consume tokens on each agent's LLM provider
- **Latency**: Full test suite takes 30-60s per agent (mitigated by `--quick` mode)
- **Auth secrets**: Test script needs access to agent API keys/tokens (already available in env)
- **CLI differences**: Each agent has different command syntax — maintenance burden for `get_live_test_commands()`

### Neutral

- Existing `health_check()` method remains unchanged (shallow check still useful for fast polling)
- IDE adapters (Cursor, VS Code, Antigravity) are out of scope for now — they require GUI automation

## Implementation Order

```
Phase 1: Core Framework
├── Step 1: Add live_test() and get_live_test_commands() to CliAgentAdapter base class
├── Step 2: Implement get_live_test_commands() for each CLI adapter (7 adapters)
└── Step 3: Create client_live_test.py orchestration script

Phase 2: MCP & Slash Command (depends on Phase 1)
├── Step 4: Register `client-test` MCP tool
├── Step 5: Create /client-test slash command workflow
└── Step 6: Sync to all IDEs via sync_agents.py

Phase 3: Integration (depends on Phase 1)
├── Step 7: Create runtime/diagnostics/ storage and history rotation
├── Step 8: Add API endpoint for dashboard consumption
├── Step 9: Wire into nightly CI (--all --quick)
└── Step 10: Emit self_heal_event on failure (ADR-084 integration)

Phase 4: Verification (depends on Phases 1-3)
├── Step 11: Run live test against all installed agents
└── Step 12: Validate slash command works from Claude Code
```

## Alternatives Considered

### Alternative 1: Extend Existing `health_check()` Method

Add live execution to the existing `health_check()` in `cli_agent_base.py`.

**Rejected because**: Health checks are called frequently (dashboard polling, routing decisions) and must be fast (<1s). Live tests take 5-30s and cost API tokens. Mixing fast polling with slow probing creates latency spikes.

### Alternative 2: External Test Harness (pytest-based)

Use pytest to run live tests as part of the test suite in `tests/`.

**Rejected because**: Live tests depend on external services (API endpoints, installed CLIs) and can't run in CI without credentials. They belong in the operational tooling (`scripts/`), not the test suite. However, the framework should still be testable via mocked adapters in pytest.

### Alternative 3: Docker-Based Isolated Testing

Spin up containers with each CLI agent for hermetic testing.

**Rejected because**: Overkill for a personal system. The agents are already installed locally. Docker adds complexity without proportional benefit. Revisit if Augur becomes multi-user.

## References

- `plugins/ai/skills/ai_bridge/augur/cli_agent_base.py` — Base adapter with current health_check()
- `plugins/ai/skills/ai_bridge/augur/ide_health.py` — Health engine orchestrator
- `plugins/ai/skills/ai_bridge/scripts/ide_integration_health.py` — Existing health script
- `plugins/observability/skills/daemon/scripts/self_heal_self_test.py` — Pattern reference for self-test scripts
- `plugins/ai/skills/mcp-app-factory/chains/cli-smoke-test.yaml` — Existing smoke test chain
- ADR-084 (Self-Heal) — Event emission pattern
- ADR-054 (Offloading) — Offload target validation

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-092: CLI Agent Live Testing**.

Read the full ADR: `docs/decisions/ADR-092-cli-agent-live-testing.md`

### Offload Protocol (ADR-054)

Before dispatching each step, check if it can be offloaded to a cheap CLI:

1. Read offload config: `cat config/system/llm.yaml` → look for `offload:` section
2. If `offload.enabled: true` AND the step's tier is `low`:
   ```bash
   python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py \
     --task "STEP DESCRIPTION" \
     --files "TARGET_FILE_1,TARGET_FILE_2" \
     --context-files "REFERENCE_FILE_FOR_PATTERNS" \
     --work-dir $(pwd)
   ```
3. Review the JSON output — check `success`, `files_changed`, and `diff` fields
4. Record the verdict:
   - Accept (diff is correct): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict accept`
   - Fix (you patched the output): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict fix`
   - Escalate (offload failed, you did it yourself): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict escalate`
5. If `offload.enabled: false` OR tier is `medium`/`high` → do the step yourself as normal

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-092-client-live-test", description="Implementing ADR-092: CLI Agent Live Testing")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-092-client-live-test", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-092 team.
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

**Team name**: `adr-092-client-live-test`

#### Phase 1: Core Framework
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Add `live_test(level)` method and `get_live_test_commands()` abstract method to `CliAgentAdapter`. Implement graduated probe logic (levels 0-4) with subprocess execution, timeout handling, and structured result dict. | `plugins/ai/skills/ai_bridge/augur/cli_agent_base.py` |
| 1.2 | developer | low | Implement `get_live_test_commands()` for all 7 CLI adapters: `claude_code.py`, `kimi_cli.py`, `codex_cli.py`, `copilot_cli.py`, `cursor_cli.py`, `juls.py`, `opencode.py`. Use each CLI's actual flags (--version, auth status, mcp list, -p). | `plugins/ai/skills/ai_bridge/augur/claude_code.py`, `plugins/ai/skills/ai_bridge/augur/kimi_cli.py`, `plugins/ai/skills/ai_bridge/augur/codex_cli.py`, `plugins/ai/skills/ai_bridge/augur/copilot_cli.py`, `plugins/ai/skills/ai_bridge/augur/cursor_cli.py`, `plugins/ai/skills/ai_bridge/augur/juls.py`, `plugins/ai/skills/ai_bridge/augur/opencode.py` |
| 1.3 | developer | medium | Create `client_live_test.py` orchestration script with argparse (--agent, --all, --level, --quick, --json, --verbose), result aggregation, and formatted table output. Pattern: `plugins/observability/skills/daemon/scripts/self_heal_self_test.py`. | `plugins/ai/skills/ai_bridge/scripts/client_live_test.py` |

#### Phase 2: MCP & Slash Command
**Strategy**: PARALLEL (depends on Phase 1)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Register `client-test` MCP tool in ai_bridge MCP handler. Args: `agent: str`, `level: int`, `quick: bool`. Calls `client_live_test.py` and returns JSON. | `plugins/ai/skills/ai_bridge/scripts/ai_bridge_manage_tools_catalog.py` (or equivalent MCP tool registration file) |
| 2.2 | devops | low | Create `/client-test` slash command workflow markdown. Usage: `/client-test <agent> [--quick] [--level N] [--all] [--report]`. | `plugins/ai/skills/ai_bridge/augur/agent-workflows/client-test.md` |
| 2.3 | devops | low | Run `sync_agents.py --workflows` to distribute `/client-test` to all IDE command dirs. Verify it appears in `.claude/skills/`, `.cursor/workflows/`, etc. | Run: `python3 plugins/ai/skills/ai_bridge/scripts/sync_agents.py --workflows` |

#### Phase 3: Integration
**Strategy**: PARALLEL (depends on Phase 1)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | devops | low | Create `runtime/diagnostics/` directory structure. Add rotation logic to `client_live_test.py` (keep 30 days, symlink `client-test-latest.json`). | `plugins/ai/skills/ai_bridge/scripts/client_live_test.py` (extend) |
| 3.2 | developer | medium | Create API route `plugins/ai/skills/ai_bridge/augur/api/client-test/route.ts` that calls the Python script and returns JSON results. | `plugins/ai/skills/ai_bridge/augur/api/client-test/route.ts` |
| 3.3 | devops | low | Wire `client_live_test.py --all --quick` into the nightly workflow. Add call in nightly chain or nightly script. | `plugins/dev/skills/devops/data/chains/nightly.yaml` (or equivalent) |
| 3.4 | developer | low | On live test failure, emit `self_heal_event` with category `agent_health`, severity based on level failed. Pattern: `self_heal_self_test.py`. | `plugins/ai/skills/ai_bridge/scripts/client_live_test.py` (extend) |

#### Phase 4: Verification
**Strategy**: PIPELINE (depends on Phases 1-3)

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 4.1 | validator | low | Run `python3 plugins/ai/skills/ai_bridge/scripts/client_live_test.py --all --quick` and verify output format is valid JSON, all installed agents return results |
| 4.2 | validator | low | Run `npm run build` in `src/dashboard/` — verify no build errors from new API route |
| 4.3 | validator | low | Verify `/client-test` slash command file exists in `.claude/skills/client-test/` after sync |

### Completion Criteria
- [ ] `live_test()` method on `CliAgentAdapter` with levels 0-4
- [ ] All 7 CLI adapters implement `get_live_test_commands()`
- [ ] `client_live_test.py` runs with --agent, --all, --quick, --json flags
- [ ] `client-test` MCP tool registered and callable
- [ ] `/client-test` slash command synced to all IDEs
- [ ] Results stored in `runtime/diagnostics/`
- [ ] API endpoint returns test results for dashboard
- [ ] Nightly CI includes quick client test
- [ ] `npm run build` passes
- [ ] ADR status updated to Accepted

### How to Run
```bash
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-092-cli-agent-live-testing.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
