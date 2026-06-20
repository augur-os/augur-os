---
status: Implemented
date: '2026-02-10'
deciders:
- Gur Sannikov
- Claude
related:
- ADR-046 (Claude Code Crew Orchestration Bridge)
- ADR-054 (Cross-Tool Swarm Offloading)
- ADR-031 (Claude Code Native Capabilities
- superseded)
- ADR-030 (Unified AI Bridge)
hub: null
tags:
- external
- execution
- mode
- orchestrator
superseded_by: null
---

# ADR-060: External Execution Mode for Orchestrator

## Context

ADR-046 established a powerful orchestration bridge that converts Augur's crew profiles, chain YAML workflows, and swarm presets into Claude Code-native artifacts: `.claude/agents/`, `.claude/commands/swarm.md`, `.claude/commands/chain.md`. These artifacts rely on Claude Code-specific primitives -- the Task tool for spawning subagents, TeamCreate/SendMessage for Agent Teams, and `.claude/commands/` for slash command discovery.

This creates a two-tier experience:

| CLI Environment | Swarm/Chain Access | UX |
|---|---|---|
| **Claude Code** | Full native orchestration (Agent Teams, Task tool, hooks) | `/swarm code-review`, `/chain feature_development` |
| **Cursor, Kimi, Codex, Windsurf, Copilot, OpenCode** | Manual Python invocation only | `python3 chain_executor.py --execute code_review --input "..." --mode cli` |

The Python orchestrator (`chain_executor.py` with 3 modes: `ide`, `cli`, `remote`) and `swarm_executor.py` provide the execution logic for all CLIs, but the gap is a UX and discovery layer. Users in non-Claude CLIs must know the exact Python command, flags, and chain names. There are no swarm presets surfaced, no slash commands, and no adapter-specific workflow instructions.

Additionally, even Claude Code users sometimes want to bypass native mode:
- **Cost savings**: Force execution through the cheaper Python orchestrator + offload pipeline (ADR-054) instead of burning Claude tokens on Task tool subagents
- **Testing**: Verify that the external execution path works correctly before deploying to other CLIs
- **Fallback**: When Claude Code native primitives have issues (experimental Agent Teams bugs, model routing problems)

ADR-031 originally defined `--native` vs `--orchestrator` flags (now superseded by ADR-046). This ADR introduces the inverse: `--external`, which forces the Python orchestrator path regardless of whether native primitives are available.

### Current Infrastructure Inventory

The following infrastructure already exists and will be leveraged:

1. **sync_agents.py** (`plugins/ai/skills/ai_bridge/scripts/sync_agents.py`) -- already syncs rules, workflows, and skills to 9+ IDE clients (Claude Code, Cursor, Windsurf, Copilot, Gemini, OpenCode, Codex, Antigravity, Kimi). It generates `.cursorrules`, `.cursor/workflows/`, `.windsurfrules`, `.opencode/commands/`, etc.

2. **CliAgentAdapter registry** (`plugins/ai/skills/ai_bridge/augur/registry.py`) -- 13 registered adapters with `detect()`, `render_intent()`, `inject_context()`, `health_check()` methods. Each adapter knows how to check if its CLI is installed and how to format commands.

3. **offload_dispatcher.py** (`plugins/orchestration/skills/executor/scripts/offload_dispatcher.py`) -- dispatches low-tier tasks to cheap CLIs (Kimi by default). Has `OffloadConfig.from_yaml()`, subprocess execution, result capture, metrics tracking.

4. **chain_executor.py** (`plugins/orchestration/skills/executor/scripts/chain_executor.py`) -- full chain execution engine with `--mode ide|cli|remote`, autonomy gating, offload integration, state persistence, and parallel step detection.

5. **swarm_executor.py** (`plugins/orchestration/skills/swarm/scripts/swarm_executor.py`) -- SwarmExecutor class with PARALLEL/PIPELINE/BROADCAST/DIVIDE strategies and COORDINATOR/VOTE/MERGE/PRIORITY consensus modes.

6. **swarm_bridge.py** (`plugins/ai/skills/ai_bridge/augur/swarm_bridge.py`) -- 7 SWARM_PRESETS with strategy/consensus/tier/teams_mode metadata. Currently only generates Claude Code slash commands.

7. **Augur MCP server** (`src/mcp/`) -- cross-IDE MCP tools accessible from any CLI that supports MCP (Kimi, Cursor, OpenCode all have MCP support configured by their respective adapters).

## Decision

Introduce an "external execution mode" that surfaces swarm and chain orchestration to all CLIs through three complementary channels: (1) generated IDE-specific workflow files, (2) MCP tools accessible cross-IDE, and (3) an `--external` flag for Claude Code users.

### 1. External Mode Configuration

Add an `external` section to `config/system/llm.yaml`, adjacent to the existing `offload` section:

```yaml
external:
  enabled: true
  preferred_cli: auto              # auto | kimi | codex | cursor | opencode
  execution_mode: cli              # ide | cli | remote (maps to chain_executor --mode)
  auto_offload: true               # Use ADR-054 offload for low-tier steps
  timeout_s: 600                   # Global timeout for external execution
  result_format: markdown          # markdown | json | plain
  fallback_to_native: true         # If external fails in Claude Code, retry with native
```

`preferred_cli: auto` uses `ide_detector.py` to find the best available CLI. The priority order: the current session's CLI (if not Claude Code), then Kimi (cheapest), Codex, Cursor, OpenCode.

### 2. The `--external` Flag

Add `--external` as a top-level flag recognized by both the generated Claude Code slash commands and the Python orchestrator.

**In Claude Code slash commands** (`/swarm`, `/chain`): When `$ARGUMENTS` contains `--external`, the command markdown instructs Claude to bypass Task tool/Agent Teams and instead shell out to the Python orchestrator:

```bash
# Instead of using Task tool:
python3 plugins/orchestration/skills/swarm/scripts/swarm_executor.py \
  --preset code-review \
  --input "$ARGUMENTS" \
  --mode cli

# Instead of using Task tool for chains:
python3 plugins/orchestration/skills/executor/scripts/chain_executor.py \
  --execute feature_development \
  --input "$ARGUMENTS" \
  --mode cli
```

**In chain_executor.py**: Add `--external` as an alias that sets `--mode=cli` and enables offload dispatch:

```python
parser.add_argument(
    "--external",
    action="store_true",
    help="Force external execution mode (Python orchestrator + offload). "
         "Inverse of Claude Code native mode."
)
```

When `--external` is set: `mode` defaults to `cli`, offload is enabled regardless of `llm.yaml` config, and results are formatted for terminal output.

**Relationship to `--native`** (from ADR-031, now superseded):

| Flag | Behavior | When to Use |
|---|---|---|
| *(default in Claude Code)* | Native mode: Task tool, Agent Teams | Standard Claude Code usage |
| `--external` | Python orchestrator: chain_executor.py, swarm_executor.py | Cost savings, testing, non-Claude CLIs |
| `--mode remote` | Python orchestrator with direct LLM API calls | Fully autonomous, no IDE session |

### 3. Generated Workflow Files for External CLIs

Extend `sync_agents.py` to generate swarm and chain orchestration instructions for non-Claude adapters. Currently, only Claude Code gets `sync_swarm_commands()` and `sync_chain_commands()`. This ADR adds equivalent generation for each adapter that supports workflow files.

**New methods on BaseAdapter**:

```python
class BaseAdapter:
    def sync_external_orchestration(self) -> None:
        """Generate swarm/chain workflow instructions for this IDE. Override per adapter."""
        pass
```

**Per-adapter generation**:

| Adapter | Generated File(s) | Content |
|---|---|---|
| CursorAdapter | `.cursor/workflows/swarm.md`, `.cursor/workflows/chain.md` | Cursor workflow markdown with bash execution blocks |
| WindsurfAdapter | `.windsurf/workflows/augur-swarm.md`, `.windsurf/workflows/augur-chain.md` | Windsurf workflow format |
| CopilotAdapter | `.github/skills/orchestration.md` | Combined swarm+chain reference |
| OpenCodeAdapter | `.opencode/commands/swarm.md`, `.opencode/commands/chain.md` | OpenCode command format |
| GeminiAdapter | `.gemini/workflows/orchestration.md` | Gemini workflow format |

Each generated file will contain:
- A preset/chain listing table (same data as Claude Code's commands)
- Bash commands to execute each preset/chain via the Python orchestrator
- MCP tool alternatives (if the CLI supports MCP)
- Context file references for the agent profiles

### 4. MCP Orchestration Tools

Register three new MCP tools on the augur MCP server (they work from any CLI that connects to the augur MCP):

| MCP Tool | Description | Implementation |
|---|---|---|
| `swarm-execute` | Execute a swarm preset by name | Calls `swarm_executor.py --preset {name} --input {input}` via subprocess |
| `chain-execute` | Execute a named chain | Calls `chain_executor.py --execute {name} --input {input} --mode cli` |
| `orchestrator-presets` | List available swarm presets and chains | Returns JSON listing from `swarm_bridge.get_swarm_presets()` + `chain_bridge.scan_chains()` |

These tools go in `src/mcp/augur_mcp/tools/settings/orchestration.py` (the `settings/` subdirectory already handles configuration and admin tools including chains per the `__init__.py` comments).

The tools use subprocess dispatch (same pattern as `offload_dispatcher.py`) to keep the MCP server lightweight. Execution happens in a child process with timeout.

### 5. Swarm Executor CLI Enhancement

`swarm_executor.py` currently only exposes a Python API (`SwarmExecutor.execute(task)`). Add a CLI entry point:

```python
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", required=True, help="Swarm preset name")
    parser.add_argument("--input", required=True, help="Task description")
    parser.add_argument("--mode", choices=["ide", "cli", "remote"], default="cli")
    parser.add_argument("--external", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
```

The CLI entry point maps preset names to `SwarmConfig` objects from `SWARM_PRESETS`, executes the swarm, and outputs results in the requested format.

### 6. IDE Detection and Auto-Routing

When `preferred_cli: auto`, the system uses this detection cascade:

```
1. Check AUGUR_EXTERNAL_CLI env var (explicit override)
2. Check running session IDE via ide_detector.py
3. If current IDE is Claude Code → use offload CLI (kimi by default)
4. If current IDE is something else → use current IDE's CLI for execution
5. Fallback: kimi → codex → cursor → opencode → error
```

Detection reuses the existing `CliAgentAdapter.detect()` method from each adapter, which calls `shutil.which()` on the CLI command name.

### 7. Graceful Fallback Chain

```
External execution requested
    ↓
Check preferred CLI availability (detect())
    ↓ available          ↓ not available
Execute via              Try next CLI in priority
Python orchestrator      ↓ all failed
    ↓                    ↓
Success?                 fallback_to_native: true?
    ↓ yes    ↓ no           ↓ yes          ↓ no
Return    Retry w/           Execute via     Return error
result    next CLI            native mode    with CLI
                             (Claude Code)   install hints
```

### 8. Slash Command Update for `--external`

Modify the generated `/swarm` and `/chain` commands (in `swarm_bridge.py` and `chain_bridge.py`) to detect `--external` in `$ARGUMENTS`:

```markdown
## Execution Mode Detection

If `$ARGUMENTS` contains `--external`:
1. Do NOT use Task tool or Agent Teams
2. Instead, run via Bash:
   python3 plugins/orchestration/skills/swarm/scripts/swarm_executor.py \
     --preset {preset-name} --input "{remaining arguments}" --mode cli
3. Display the output to the user

Otherwise, proceed with native execution (Agent Teams or Task Tool).
```

This is a documentation-level change to the generated markdown -- no runtime Python changes needed in the bridge.

### Implementation Order

```
Phase 1: Configuration + CLI flags      ← Foundation
    ↓
Phase 2: swarm_executor.py CLI entry    ← Required by all downstream
    ↓
Phase 3: MCP orchestration tools        ← Cross-IDE bridge
Phase 4: sync_agents.py extensions      ← IDE-specific workflow files
    (Phases 3 & 4 parallel)
    ↓
Phase 5: Slash command --external support ← Claude Code UX
    ↓
Phase 6: Verification
```

## Consequences

### Positive

- Every CLI gets access to swarm presets and chain workflows, not just Claude Code
- `--external` flag gives Claude Code users an escape hatch for cost savings or debugging
- MCP tools provide the most universal bridge (any CLI with MCP support gets orchestration)
- Reuses 100% of existing infrastructure (adapters, executors, offload, bridge)
- Generated workflow files mean zero setup for end users -- `sync_agents.py --all` handles everything
- Python orchestrator + offload pipeline can be significantly cheaper than Claude Code native mode

### Negative

- External mode lacks the true parallelism of Claude Code's Task tool (Python subprocess is sequential per swarm step, though parallel within a PARALLEL strategy via asyncio)
- More generated files to maintain across 9 IDE targets
- External mode cannot leverage Agent Teams peer-to-peer communication (falls back to Python orchestrator's simpler coordination)
- MCP tool execution adds subprocess overhead compared to native Task tool invocation

### Neutral

- Claude Code's native mode remains the default and preferred path -- `--external` is opt-in
- Python orchestrator's 3 existing modes (`ide`, `cli`, `remote`) are unchanged; `--external` is syntactic sugar for `--mode cli` with offload enabled
- Existing offload configuration in `llm.yaml` continues to work as-is
- Adapter detection and health check infrastructure is unchanged

## Alternatives Considered

### Alternative 1: MCP-Only Approach (No Generated Files)

Rely exclusively on MCP tools (`swarm-execute`, `chain-execute`) for all non-Claude CLIs. Rejected because:
- Not all CLIs have MCP configured (some users skip MCP setup)
- MCP tools require the augur MCP server to be running
- Generated workflow files provide discoverable documentation even without MCP
- Bash-based execution works universally regardless of MCP support

### Alternative 2: CLI Wrapper Script

Create a standalone `augur` CLI binary that wraps chain_executor.py and swarm_executor.py. Rejected because:
- Adds a new binary to maintain and distribute
- The existing Python scripts already provide full CLI access
- Generated workflow files provide the discovery layer without a new binary
- Would duplicate argument parsing already in chain_executor.py

### Alternative 3: Transpile Claude Code Commands to Other Formats

Convert `.claude/commands/swarm.md` into equivalent formats for each IDE at a higher fidelity (e.g., Cursor workflows with conditional logic). Rejected because:
- Each IDE has different workflow capabilities -- no common feature set
- Claude Code commands use Task tool instructions that have no equivalent in other IDEs
- Simpler to generate bash-based commands that work everywhere

## References

- `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` -- artifact generation pipeline
- `plugins/ai/skills/ai_bridge/augur/swarm_bridge.py` -- swarm preset definitions and command generation
- `plugins/ai/skills/ai_bridge/augur/chain_bridge.py` -- chain-to-command converter
- `plugins/ai/skills/ai_bridge/augur/registry.py` -- adapter registry (13 CLIs)
- `plugins/ai/skills/ai_bridge/augur/cli_agent_base.py` -- CliAgentAdapter base class
- `plugins/orchestration/skills/executor/scripts/chain_executor.py` -- chain execution engine
- `plugins/orchestration/skills/swarm/scripts/swarm_executor.py` -- swarm coordination
- `plugins/orchestration/skills/executor/scripts/offload_dispatcher.py` -- cheap CLI dispatch
- `config/system/llm.yaml` -- LLM and offload configuration
- `src/mcp/augur_mcp/tools/` -- MCP tool registration

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-060: External Execution Mode for Orchestrator**.

Read the full ADR: `docs/decisions/ADR-060-external-execution-mode.md`

**Team name**: `adr-060-external-mode`

### Phase 1: Configuration and CLI Flags
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Add `external` section to `config/system/llm.yaml` with `enabled`, `preferred_cli`, `execution_mode`, `auto_offload`, `timeout_s`, `result_format`, `fallback_to_native` fields | `config/system/llm.yaml` |
| 1.2 | developer | medium | Add `--external` flag to `chain_executor.py` argparse. When set, force `mode=cli` and enable offload. Add external mode detection logic | `plugins/orchestration/skills/executor/scripts/chain_executor.py` |

### Phase 2: Swarm Executor CLI Entry Point
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Add CLI `__main__` block to `swarm_executor.py` with `--preset`, `--input`, `--mode`, `--external`, `--dry-run`, `--json` flags. Map preset names to `SWARM_PRESETS`, execute, format output | `plugins/orchestration/skills/swarm/scripts/swarm_executor.py` |
| 2.2 | validator | low | Test: `python3 swarm_executor.py --preset code-review --input "test" --dry-run` should list agents and strategy without executing | `plugins/orchestration/skills/swarm/scripts/swarm_executor.py` |

### Phase 3: MCP Orchestration Tools
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Create `orchestration.py` in MCP tools with `swarm-execute`, `chain-execute`, `orchestrator-presets` tools. Use subprocess dispatch pattern from offload_dispatcher.py | `src/mcp/augur_mcp/tools/settings/orchestration.py` |
| 3.2 | developer | low | Register orchestration tools in `tools/__init__.py` and `tools/settings/__init__.py` | `src/mcp/augur_mcp/tools/__init__.py`, `src/mcp/augur_mcp/tools/settings/__init__.py` |

### Phase 4: Sync Agents Extensions
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Add `sync_external_orchestration()` method to `BaseAdapter` in `sync_agents.py`. Implement for CursorAdapter (`.cursor/workflows/swarm.md`, `.cursor/workflows/chain.md`) | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |
| 4.2 | developer | medium | Implement `sync_external_orchestration()` for WindsurfAdapter, CopilotAdapter, OpenCodeAdapter, GeminiAdapter. Generate IDE-specific workflow files with bash commands and MCP alternatives | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |
| 4.3 | developer | medium | Add `generate_external_swarm_markdown()` and `generate_external_chain_markdown()` functions to `swarm_bridge.py` and `chain_bridge.py` respectively. These generate bash-based workflow content (not Claude Code Task tool instructions) | `plugins/ai/skills/ai_bridge/augur/swarm_bridge.py`, `plugins/ai/skills/ai_bridge/augur/chain_bridge.py` |

### Phase 5: Slash Command --external Support
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer | low | Add "Execution Mode Detection" section to `swarm_preset_to_command_markdown()` and `generate_swarm_meta_command()` in `swarm_bridge.py`. When `$ARGUMENTS` contains `--external`, instruct Claude to use Bash instead of Task tool | `plugins/ai/skills/ai_bridge/augur/swarm_bridge.py` |
| 5.2 | developer | low | Add equivalent `--external` detection section to chain command generation in `chain_bridge.py` | `plugins/ai/skills/ai_bridge/augur/chain_bridge.py` |
| 5.3 | developer | low | Run `python3 plugins/ai/skills/ai_bridge/scripts/sync_agents.py --all` to regenerate all artifacts | (generated files) |

### Final Phase: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `python3 plugins/orchestration/skills/swarm/scripts/swarm_executor.py --preset code-review --input "test" --dry-run` -- verify CLI output |
| V.2 | validator | low | Run `python3 plugins/orchestration/skills/executor/scripts/chain_executor.py --list` -- verify chains still list correctly |
| V.3 | validator | low | Run `python3 plugins/ai/skills/ai_bridge/scripts/sync_agents.py --check` -- verify all generated files are consistent |
| V.4 | validator | low | Verify `.cursor/workflows/swarm.md` and `.cursor/workflows/chain.md` exist and contain bash execution instructions |
| V.5 | validator | low | Run `pytest tests/src/` -- no regressions |
| V.6 | architect | low | Verify ADR intent matches implementation: external mode works for non-Claude CLIs, `--external` flag bypasses native mode in Claude Code |

### Completion Criteria
- [ ] `external` section in `llm.yaml` is valid YAML
- [ ] `--external` flag accepted by `chain_executor.py` and `swarm_executor.py`
- [ ] `swarm_executor.py` has working CLI entry point with `--preset` flag
- [ ] MCP tools `swarm-execute`, `chain-execute`, `orchestrator-presets` registered and functional
- [ ] `sync_agents.py --all` generates workflow files for Cursor, Windsurf, Copilot, OpenCode, Gemini
- [ ] Generated workflow files contain correct bash commands referencing Python orchestrator
- [ ] `/swarm code-review --external` in Claude Code correctly shells out to Python orchestrator
- [ ] All existing tests pass
- [ ] ADR status updated to Accepted
