---
status: Implemented
date: '2026-02-08'
deciders:
- User
- Claude
related: []
hub: null
tags:
- cross
- tool
- swarm
- offloading
superseded_by: null
---

# ADR-054: Cross-Tool Swarm Offloading

## Context

The `/implement-adr` workflow currently spawns all subagents through Claude Code, meaning every line of boilerplate, test scaffolding, and simple file creation burns expensive Claude tokens. This is wasteful — many implementation tasks (creating files from templates, writing straightforward tests, generating YAML configs, formatting, moves/deletes) do not require Claude-level reasoning.

The system already has multi-provider infrastructure:
- **CliAgentAdapter** base class with `detect()`, `render_intent()`, `inject_context()` methods
- **KimiCliAdapter** registered in the adapter registry, Kimi CLI v1.5 installed
- **Kimi CLI** supports one-shot execution: `kimi --print -y -p "prompt" -w /path --max-turns 3 --output-format text --final-message-only`
- **TierSelector** classifies tasks into FAST/STANDARD/DEEP tiers
- **Implementation Prompts** in ADRs already specify a tier (`low`/`medium`/`high`) per step

What is missing is the orchestration logic that routes `low`-tier tasks to the cheap CLI while keeping Claude as the orchestrator and reviewer.

**Cost impact**: A typical ADR implementation has 8-15 steps. Of those, 40-60% are mechanical (`low` tier). Offloading these to a free/cheap CLI could reduce per-ADR implementation cost by 30-50%.

## Decision

### 1. Offload Configuration

Add an `offload` section to `config/system/llm.yaml`:

```yaml
offload:
  enabled: true
  cli: kimi                          # CLI adapter name from registry
  cli_flags:                         # One-shot execution flags
    - "--print"                      # Non-interactive output
    - "-y"                           # Auto-approve file changes
    - "--output-format"
    - "text"
    - "--final-message-only"         # Only final response
    - "--max-turns"
    - "3"                            # Limit iterations
  model: null                        # null = CLI default, or override e.g. "kimi-k2.5"
  timeout_s: 300                     # 5 minute timeout per task
  max_retries: 1                     # Retry once on failure
  offloadable_tiers:                 # Which tiers get offloaded
    - low                            # Haiku-class: mechanical tasks
  review_mode: always                # always | on_failure | never
  fallback: claude                   # Fall back to Claude on failure
  context_budget_chars: 8000         # Max context passed to offload CLI
```

Provider-agnostic: change `cli: kimi` to `cli: codex` or any registered adapter.

### 2. Task Classification

Tasks are already classified by tier annotations in Implementation Prompts:

| Tier | Examples | Execution Target |
|------|----------|-----------------|
| `low` (haiku) | File moves, deletions, boilerplate, simple tests, config YAML, formatting | **Offload CLI** |
| `medium` (sonnet) | Module implementation, API routes, dashboard components, refactoring | **Claude Code** |
| `high` (opus) | Architecture, security audit, complex debugging, integration wiring | **Claude Code** |

No new classification system needed — the existing tier column in Implementation Prompts drives routing.

### 3. Offload Dispatcher

New script: `plugins/orchestration/skills/executor/scripts/offload_dispatcher.py`

**Core flow**:

```
1. Read offload config from llm.yaml
2. Detect CLI via adapter registry (shutil.which)
3. Record git HEAD (for diff isolation)
4. Build one-shot prompt: task + context files (capped at context_budget_chars)
5. Execute: subprocess.run([cli, *cli_flags, "-p", prompt, "-w", work_dir])
6. Capture: exit code, stdout, git diff since recorded HEAD
7. Return: JSON result {success, files_changed, diff, stdout_summary, duration_s}
```

**CLI interface**:

```bash
# Dispatch a task
python3 offload_dispatcher.py \
  --task "Create SKILL.md for the renderer skill" \
  --files "plugins/admin/skills/renderer/SKILL.md" \
  --context-files "plugins/dev/skills/developer/SKILL.md" \
  --work-dir /path/to/augur

# Health check
python3 offload_dispatcher.py --health

# Dry run (show command without executing)
python3 offload_dispatcher.py --dry-run --task "..." --work-dir /path

# Show offload metrics
python3 offload_dispatcher.py --metrics
```

**Context prompt template** sent to the offload CLI:

```markdown
# Task
{task_description}

# Project
Working directory: {work_dir}
Project: Augur (skills monorepo)

# Relevant Files
{for each context_file: filename + content, capped at context_budget_chars}

# Constraints
- Make ONLY the changes described above
- Do NOT modify files outside the listed scope
- Follow existing code patterns in the context files
- Use absolute imports, no hardcoded paths
```

### 4. Branch-Based Diff Isolation

`/implement-adr` will now create a fresh branch before any code changes (new Phase 0.5):

```bash
git checkout -b adr-NNN-impl
```

Before each offload dispatch, the dispatcher records `git rev-parse HEAD`. After the CLI finishes, `git diff <recorded-HEAD>` isolates exactly the offloaded changes. This works cleanly because all work happens on the dedicated branch.

### 5. Review Loop

Claude ALWAYS reviews offloaded work before proceeding. The review protocol:

```
1. Offload CLI executes task → modifies files
2. Dispatcher captures git diff of changes
3. Claude reads the diff and reviews against:
   a. Original task description
   b. Existing code patterns
   c. Quick lint/build check if applicable
4. Verdict:
   a. ACCEPT → proceed to next step
   b. FIX → Claude fixes issues in-place (no re-offload)
   c. ESCALATE → Claude does the whole task itself (offload failed)
```

When verdict is `fix`, Claude corrects the output itself rather than re-dispatching. This avoids infinite loops and leverages Claude's superior reasoning for corrections.

### 6. Implement-ADR Integration

Two changes to `data/ai-bridge/skills/implement-adr/SKILL.md`:

**a) New Phase 0.5: Create implementation branch**

Before any code changes:
```bash
git checkout -b adr-{number}-impl
```

**b) Modified Phase 3: Agent Swarm Dispatch with Offloading**

Before dispatching each step from the Implementation Prompt:

1. Read offload config: `config/system/llm.yaml` → `offload` section
2. If `offload.enabled` and step tier is in `offload.offloadable_tiers`:
   - Run: `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --task "step description" --files "target files" --context-files "reference files" --work-dir $PROJECT_ROOT`
   - Review the JSON output + git diff
   - If acceptable → proceed to next step
   - If not acceptable → do the task yourself as a Claude subagent
3. If not offloadable → dispatch as normal Claude subagent (existing behavior)

### 7. Cost Tracking

The dispatcher writes metrics to `runtime/offload-metrics.json`:

```json
{
  "total_dispatched": 5,
  "accepted": 4,
  "fixed_by_claude": 1,
  "escalated": 0,
  "total_offload_time_s": 62.3,
  "cli_name": "kimi",
  "last_run": "2026-02-08T14:30:00"
}
```

The implement-adr final summary includes offload statistics.

## Consequences

### Positive

- 30-50% reduction in Claude API token usage for ADR implementations
- Higher quality: Claude reviews everything, catching mistakes from cheaper models
- Provider-agnostic: works with any CLI supporting one-shot prompt execution
- Graceful degradation: if offload CLI unavailable or fails, Claude handles directly
- No changes to Claude Code itself — purely Augur config and scripts
- Implementation branches improve git hygiene for all ADR work

### Negative

- Added complexity in the dispatch/review loop
- Offloaded tasks take longer wall-clock time (subprocess + review) vs direct Claude
- Context passing capped at 8000 chars — complex tasks with deep context may fail
- Review step adds some Claude tokens (reading diffs) — net savings depend on success rate

### Neutral

- Reuses existing CliAgentAdapter infrastructure and tier annotations
- No new pip dependencies
- Kimi CLI already installed and registered

## Alternatives Considered

### Alternative 1: API-based offloading (call OpenRouter/Glama directly)

Route cheap tasks to a cheap API endpoint instead of a CLI tool. Rejected because:
- Requires API key management and billing
- Cannot modify files directly (need to parse responses and apply changes)
- CLI tools like Kimi handle file operations and project context natively
- CLI approach is simpler and leverages existing adapter infrastructure

### Alternative 2: Per-subagent model switching within Claude Code

Use Claude Code's model flag to switch between Claude and a cheap model mid-session. Rejected because:
- Claude Code does not support per-subagent model selection externally
- Would require changes to Claude Code itself (design constraint violation)

### Alternative 3: Static code generators for boilerplate

Use cookiecutter/Yeoman for mechanical tasks. Rejected because:
- Templates are rigid and require maintenance
- Many "mechanical" tasks still need context-awareness
- AI offloading handles the long tail of semi-mechanical tasks

## References

- `plugins/ai/skills/ai_bridge/augur/kimi_cli.py` (Kimi adapter)
- `plugins/ai/skills/ai_bridge/augur/cli_agent_base.py` (CliAgentAdapter base)
- `plugins/orchestration/skills/executor/scripts/chain_executor.py` (`_run_process` pattern)
- `plugins/orchestration/skills/router/scripts/tier_selector.py` (tier classification)
- `data/ai-bridge/skills/implement-adr/SKILL.md` (Phase 3: Agent Swarm Dispatch)
- `data/ai-bridge/skills/write-adr/SKILL.md` (tier annotations in Implementation Prompts)
- `config/system/llm.yaml` (LLM config)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-054: Cross-Tool Swarm Offloading**.

Read the full ADR: `docs/decisions/ADR-054-cross-tool-swarm-offloading.md`

### Phase 1: Configuration
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Add `offload` section to llm.yaml | `config/system/llm.yaml` |

### Phase 2: Offload Dispatcher
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create offload_dispatcher.py with dispatch, health, metrics, dry-run CLI | `plugins/orchestration/skills/executor/scripts/offload_dispatcher.py` |

### Phase 3: Skill Updates
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Add Phase 0.5 (branch creation) + offload dispatch to implement-adr Phase 3 | `data/ai-bridge/skills/implement-adr/SKILL.md` |
| 3.2 | developer | low | Add offload tier guidance to write-adr SKILL.md | `data/ai-bridge/skills/write-adr/SKILL.md` |

### Final Phase: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `python3 offload_dispatcher.py --health` — verify CLI detection |
| V.2 | validator | low | Run `python3 offload_dispatcher.py --dry-run --task "test" --work-dir /tmp` — verify command building |
| V.3 | validator | low | Run `pytest tests/src/` — no regressions |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria
- [ ] `offload` section in llm.yaml is valid YAML
- [ ] `offload_dispatcher.py` detects Kimi CLI and builds one-shot commands
- [ ] implement-adr SKILL.md includes Phase 0.5 + offload dispatch in Phase 3
- [ ] write-adr SKILL.md notes offload-eligible tiers
- [ ] All existing tests pass
- [ ] ADR status updated to Accepted
