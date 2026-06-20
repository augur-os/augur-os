---
status: Superseded
date: '2026-01-31'
deciders:
- Augur Core Team
related:
- ADR-030 (Unified AI Bridge)
- ADR-046 (Claude Code Crew Orchestration Bridge)
hub: null
tags:
- claude
- code
- native
- capabilities
- adr
superseded_by: null
---

# ADR-031: Claude Code Native Capabilities for ADR Implementation

> **Note**: This ADR has been superseded by ADR-046, which implements the crew orchestration bridge including subagent profiles, chain commands, hooks integration, and swarm presets for Claude Code. The native capabilities described here are now covered by ADR-046's 5-phase implementation.

## Context

The `/implement-adr` skill supports two modes:
- `--native`: Uses Claude Code native features
- `--orchestrator`: Uses Augur chain-based orchestration

Investigation revealed that Claude Code 2.1+ has **11 native capabilities** not yet utilized in native mode. This ADR documents these features and mandates their integration.

## Decision

### Implement All Claude Code 2.1+ Native Features

| Feature | Description | Integration |
|---------|-------------|-------------|
| **Background Agents** | Async tasks surviving session | Run test suites in background |
| **Built-in: /explore** | Codebase analysis subagent | Analyze ADR dependencies first |
| **Built-in: /plan** | Task planning subagent | Generate workstream breakdown |
| **Task Tool** | Parallel batching with queue | Batch workstreams with parallelism |
| **Hooks: PostToolUse** | Auto-run after edits | Lint/test after file changes |
| **Hooks: PreToolUse** | Validate before tool runs | Block dangerous operations |
| **Hooks: SessionStart** | Load context on start | Inject ADR context |
| **Hooks: SubagentStart/Stop** | Monitor lifecycle | Track subagent progress |
| **Skill-Scoped Hooks** | Frontmatter hooks | Per-skill automation |
| **Agent Swarm** | Dependency graph + spawn | Auto-parallelize ADR sections |
| **Model Selection** | Per-task model choice | Opus for planning, Sonnet for code |

### Skill-Scoped Hooks Configuration

Add to SKILL.md frontmatter:
```yaml
---
name: implement-adr
hooks:
  SessionStart:
    - command: "echo 'ADR Implementation Mode Active'"
  PostToolUse:
    - matcher: { tool: "write_file", pattern: "*.ts" }
      command: "npm run lint --fix $file"
    - matcher: { tool: "write_file", pattern: "*.py" }
      command: "ruff check --fix $file"
  SubagentStop:
    - command: "echo 'Subagent completed: $subagent_name'"
---
```

### Workflow with Native Features

```
1. /implement-adr ADR-030 --native
   ↓
2. Use /explore to analyze codebase
   ↓
3. Use /plan to generate workstreams from ADR
   ↓
4. Dispatch Agent Swarm with dependency graph
   ↓
5. Each subagent runs with PostToolUse hooks
   ↓
6. Background Agent runs full test suite
   ↓
7. RALPH loop on failures
   ↓
8. Verify against ADR Testing section
```

### Model Selection Strategy

| Phase | Model | Rationale |
|-------|-------|-----------|
| Explore/Analyze | Sonnet | Fast codebase scan |
| Plan/Design | Opus | Deep reasoning for architecture |
| Implement | Sonnet | Fast coding |
| Debug (RALPH) | Opus | Complex problem-solving |
| Test/Verify | Haiku | Quick validation |

## Testing & Verification

### Unit Tests
| Test | Expected Result |
|------|-----------------|
| `test_explore_subagent` | Codebase analysis results returned |
| `test_plan_subagent` | Workstream breakdown generated |
| `test_background_agent` | Tests run async, results captured |
| `test_posttooluse_hook` | Lint runs after file edit |
| `test_agent_swarm` | Dependency graph respected |

### Use Cases

**UC-1: PostToolUse Hook Fires**
```
1. Subagent edits src/app.ts
2. PostToolUse hook triggers
3. npm run lint --fix runs automatically
4. Lint errors fixed before continuing
```

**UC-2: Background Agent for Tests**
```
1. Start test suite as Background Agent
2. Continue implementing next workstream
3. Background Agent reports completion
4. Review test results without blocking
```

**UC-3: Model Selection Per Phase**
```
1. /explore phase uses Sonnet (fast)
2. /plan phase switches to Opus (deep)
3. Implementation returns to Sonnet
```

## Consequences

### Positive
- Maximizes Claude Code capabilities
- Automatic linting/testing via hooks
- True parallelism with Agent Swarm
- Non-blocking test execution
- Optimal model usage per task

### Negative
- Only works in Claude Code 2.1+
- Requires client version check
- Hooks may slow down execution
- Model switching adds complexity

## Mode Comparison: Native vs Orchestrator

| Capability | `--native` (Claude Code 2.1+) | `--orchestrator` (Augur) |
|------------|:-----------------------------:|:------------------------:|
| **Parallel Execution** | ✅ Agent Swarm + Task Tool | ✅ Chain parallel_group |
| **Dependency Graph** | ✅ Automatic (Agent Swarm) | ✅ Manual ($variable) |
| **Debugging** | ✅ RALPH loops | ⚠️ Retry policy |
| **Codebase Analysis** | ✅ `/explore` subagent | ⚠️ Manual grep/find |
| **Task Planning** | ✅ `/plan` subagent | ⚠️ Manual breakdown |
| **Background Tasks** | ✅ Background Agents | ❌ None |
| **Auto-Linting** | ✅ PostToolUse hooks | ⚠️ Manual step |
| **Validation** | ✅ PreToolUse hooks | ❌ None |
| **Model Selection** | ✅ Per-task (Opus/Sonnet) | ❌ Fixed |
| **Execution Trace** | ❌ None | ✅ Full audit trail |
| **Agent Health Check** | ❌ None | ✅ Registry-based |
| **API Provider Routing** | ❌ None | ✅ Multi-provider |

## Example: Dry Run Output

When running `/implement-adr --native ADR-030`, Claude Code receives:

```
🚀 ADR Implementation Mode Active (SessionStart hook)

## Phase 1: Codebase Analysis
Use /explore to scan: data/ai-bridge/, plugins/ai/skills/ai_bridge/

## Phase 2: Task Planning  
Use /plan to extract workstreams from ADR-030:

Workstream 1: Skills Migration (Independent)
Workstream 2: Per-Client Adapters (Depends on 1)
Workstream 3: Context Manager (Independent)
Workstream 4: Mode Detection (Depends on 3)
Workstream 5: MCP Config Generation (Independent)

## Phase 3: Agent Swarm Dispatch
PARALLEL: [Workstream 1, 3, 5]
SEQUENTIAL: [Workstream 2 after 1, Workstream 4 after 3]

## Phase 4: Background Agent for Tests
Dispatch: pytest tests/ (async, non-blocking)

## Phase 5: PostToolUse Hooks Active
*.py → ruff check --fix
*.ts → npm run lint --fix

## Phase 6: Verification from ADR Testing section
- [ ] test_skills_sync_claude
- [ ] test_skills_sync_windsurf
- [ ] UC-1 through UC-6 validation
```

## Related ADRs

- ADR-007: Chain Orchestration
- ADR-020: Unified Agent Execution
- ADR-030: Unified AI Bridge
