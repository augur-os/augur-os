---
status: Implemented
date: '2026-02-04'
deciders:
- Augur Team
related:
- ADR-007 (Chain Orchestration)
- ADR-020 (Local Agent Orchestration)
- ADR-029 (Plugin Architecture)
hub: null
tags:
- autonomous
- execution
- pipeline
superseded_by: null
---

# ADR-037: Autonomous Execution Pipeline

## Context

The Augur system had sophisticated orchestration infrastructure — chain executor, parallel executor, swarm coordinator, tier selector, chain planner — all production-ready. However, progress happened at single-human-pace: one chat session, one task at a time. When the operator was away from the computer, nothing ran. When present, only one AI stream was active.

Two structural bottlenecks prevented autonomous operation:

1. **No headless runner** — The engine could orchestrate, but no script existed to take a backlog task and execute it via Claude Code CLI without human interaction. The `runner_command` in nightly config was empty.
2. **No continuous daemon** — The nightly executor only ran in a 2-8 AM window when Mac was idle. No daytime processing existed. No 24/7 loop.

The nightly executor config had been disabled since December 2025, and the launchd service was stopped — despite the orchestration infrastructure being fully capable.

## Decision

Implement a three-layer autonomous execution pipeline that turns the Augur system from human-paced to AI-multiplied:

### Layer 1: Headless Task Runner

A script (`plugins/dev/skills/devops/scripts/headless_runner.py`) that autonomously executes a single backlog task:

1. Reads task markdown — extracts frontmatter and body
2. Creates an isolated git worktree: `git worktree add .worktrees/auto-{task-id} -b auto/{task-id}`
3. Constructs a structured prompt with task context
4. Executes via `claude --print --dangerously-skip-permissions` in subprocess
5. If changes produced: commits, pushes, creates a **draft PR** via `gh pr create --draft`
6. Updates task frontmatter with execution result
7. Cleans up worktree (keeps branch for PR)

Git worktree isolation is critical — it enables multiple parallel Claude Code instances without file conflicts.

### Layer 2: Continuous Executor Daemon

A persistent background daemon (`plugins/observability/skills/daemon/scripts/continuous_executor.py`) registered as a macOS launchd KeepAlive service (`com.augur.continuous`):

- Polls backlog every 5 minutes for tasks tagged `autonomous: true`
- Maintains a worker pool: `ProcessPoolExecutor(max_workers=3)`
- Each worker invokes `headless_runner.py` in its own worktree
- Exponential backoff when no tasks available
- Graceful shutdown on SIGTERM (finishes running tasks, stops accepting new ones)
- Hot-reloads config each cycle (allows runtime reconfiguration)

### Layer 3: Nightly Pipeline Integration

The existing nightly maintainer (`nightly_maintainer.py`) now includes task execution as step 5:

```
3 AM → analytics → archive → ingest → memory sync → execute backlog tasks → health check
```

The nightly executor uses ROI-based task scoring to prioritize: bugfixes first (lowest cost), then refactors, then features (highest cost). Tasks are claimed, executed via headless runner, and released on failure.

### Supporting: Morning Briefing

A daily summary generator (`plugins/dev/skills/devops/scripts/morning_briefing.py`) that reads overnight execution logs and produces a markdown briefing:

- Tasks completed and failed (with error reasons)
- Draft PRs created (with links)
- Current backlog status
- Written to `runtime/briefings/YYYY-MM-DD.md`

### Approval Tiers

All autonomous work flows through draft PRs. The human operator reviews and merges:

| Tier | Task Types | Approval |
|------|-----------|----------|
| Auto-merge (future) | TODO_CLEANUP, docs, test fixes | CI passes |
| Draft PR, human merge | Bugfixes, features, refactors | Review PR |
| Human-supervised | Architecture, new skills, security | Active session |

### Human Workflow Shift

The operator's role changes from "chat implementer" to "architect + reviewer":

| Activity | Mode |
|----------|------|
| Morning: read briefing, review/merge PRs | Review |
| 15-30 min: curate backlog, tag tasks `autonomous` | Planning |
| Daytime: architecture, supervised complex tasks | Strategic |
| Background (24/7): 3 parallel workers processing tasks | Automatic |
| 3 AM: full nightly pipeline | Automatic |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Backlog (Markdown)                     │
│         Tasks with frontmatter: status, priority,        │
│         autonomous: true/false, type, acceptance         │
└──────────────────┬──────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
   Continuous              Nightly
   Executor                Executor
   (24/7 daemon)           (3 AM window)
   max_parallel: 3         ROI-scored
        │                     │
        └──────────┬──────────┘
                   │
         ┌─────────┴─────────┐
         │  Headless Runner   │
         │                    │
         │ 1. Parse task      │
         │ 2. git worktree    │
         │ 3. claude --print  │
         │ 4. commit + push   │
         │ 5. gh pr --draft   │
         │ 6. update status   │
         │ 7. cleanup         │
         └─────────┬──────────┘
                   │
         ┌─────────┴─────────┐
         │   Draft PR on      │
         │   auto/{task-id}   │
         └─────────┬──────────┘
                   │
         Human reviews + merges
```

## Files

### New Files

| File | Purpose |
|------|---------|
| `plugins/dev/skills/devops/scripts/headless_runner.py` | Core autonomous execution — task parsing, worktree, Claude Code CLI, PR creation |
| `plugins/observability/skills/daemon/scripts/continuous_executor.py` | 24/7 daemon — parallel task processing with ProcessPoolExecutor |
| `plugins/dev/skills/devops/scripts/morning_briefing.py` | Daily summary of overnight autonomous work |
| `plugins/professional/skills/project-dev/data/tasks/config/continuous-execution.yaml` | Config: max_parallel, poll_interval, model, budget |

### Modified Files

| File | Change |
|------|--------|
| `plugins/professional/skills/project-dev/data/tasks/config/nightly-execution.yaml` | Enabled, set runner_command to headless_runner.py |
| `plugins/observability/skills/daemon/scripts/nightly_maintainer.py` | Added `run_nightly_executor()` as step 5 in pipeline |
| `plugins/observability/skills/daemon/scripts/service_healer.py` | Added `continuous_executor` to SERVICES dict; fixed project root detection |

### Existing Infrastructure Reused (No Changes)

| Component | Location |
|-----------|----------|
| Task selection + ROI scoring | `nightly_executor.py` + `task_utils.py` |
| Chain execution | `chain_executor.py` |
| Parallel step execution | `parallel_executor.py` |
| Swarm coordination | `swarm_executor.py` |
| Chain planning + modifiers | `chain_planner.py` |
| Model tier selection | `tier_selector.py` + `agent_tiers.yaml` |
| Execution state + checkpoints | `execution_state.py` |

## Configuration

### Nightly Execution (`nightly-execution.yaml`)

```yaml
enabled: true
window: { start: "02:00", end: "08:00" }
idle_minutes: 15
agent: "claude-code"
max_tasks: 5
claim_tasks: true
mark_in_progress: true
runner_command: "python3 {repo_root}/plugins/dev/skills/devops/scripts/headless_runner.py --task {task_path}"
runner_timeout_seconds: 3600
roi:
  enabled: true
  type_weights: { bugfix: 0, refactor: 1, feature: 3, research: 4 }
```

### Continuous Execution (`continuous-execution.yaml`)

```yaml
enabled: true
max_parallel: 3
poll_interval_seconds: 300
model: "sonnet"
max_budget_per_task: 5.0
task_filter: { autonomous: true }
```

### Task Frontmatter (Backlog Items)

```yaml
---
id: fix-api-timeout
status: ready
priority: high
type: bugfix
autonomous: true    # <-- enables pickup by continuous executor
---
# Fix API Timeout

## Objective
Fix the 30s timeout on /api/agents endpoint...

## Acceptance Criteria
- [ ] Timeout increased to 60s
- [ ] Tests pass
```

## launchd Services

| Service | Plist | Type |
|---------|-------|------|
| `com.augur.logmonitor` | KeepAlive daemon | Log monitoring |
| `com.augur.nightly` | Scheduled (3 AM) | Full nightly pipeline |
| `com.augur.continuous` | KeepAlive daemon | 24/7 task processing |

Managed via: `python3 plugins/observability/skills/daemon/scripts/service_healer.py [install|status|heal]`

## Consequences

### Positive

- Work happens 24/7 — not just during human sessions
- 3+ parallel AI streams instead of 1 sequential chat
- Draft PRs create a reviewable audit trail for all autonomous work
- Git worktree isolation prevents parallel execution conflicts
- ROI-based scoring ensures highest-value tasks execute first
- Morning briefing provides async handoff without manual checking
- Existing orchestrator infrastructure (chains, swarms, tiers) is now actually exercised

### Negative

- API costs increase with continuous autonomous execution ($5/task budget cap mitigates)
- Draft PRs accumulate if not reviewed regularly — requires discipline
- Claude Code `--dangerously-skip-permissions` bypasses safety checks in worktrees
- Worktrees consume disk space during parallel execution (cleaned up after PR creation)

### Neutral

- Human role shifts from implementer to architect + reviewer
- Backlog curation becomes a daily habit (tagging `autonomous: true`)
- The nightly executor still respects the 2-8 AM window and idle check — this is intentional for heavier tasks

## Alternatives Considered

### Alternative 1: API-Only Execution (Claude SDK)

Use the Anthropic Python SDK directly instead of Claude Code CLI. Rejected because:
- No file editing, tool use, or MCP access built in
- Would require reimplementing all Claude Code capabilities
- Claude Code `--print` mode provides the same non-interactive capability with full tool access

### Alternative 2: IDE Bridge Automation

Automate the existing IDE bridge (AppleScript paste to Cursor/VS Code). Rejected because:
- Requires an IDE to be open and focused
- User must click "Run" — not truly autonomous
- Fragile: depends on UI state, window positioning, focus

### Alternative 3: GitHub Actions for Execution

Run autonomous tasks as GitHub Actions workflows. Rejected because:
- No access to local MCP server or augur context
- Higher latency (VM spin-up per task)
- Limited to GitHub-hosted runner capabilities
- Better suited for CI/CD, not autonomous development

## Verification

1. Dry-run headless runner: `python3 headless_runner.py --task <path> --dry-run`
2. Verify services: `python3 service_healer.py status` → all 3 running
3. Test continuous executor: `python3 continuous_executor.py --once` → single poll cycle
4. Generate briefing: `python3 morning_briefing.py --date 2026-02-04`
5. End-to-end: tag a task `autonomous: true` with `status: ready` → verify PR appears within 5 minutes

## References

- ADR-007: Chain-Based Agent Orchestration
- ADR-020: Local Agent Orchestration
- ADR-029: Plugin Architecture Refactoring
- `plugins/orchestration/skills/executor/scripts/chain_executor.py` — chain execution engine
- `plugins/orchestration/skills/executor/scripts/parallel_executor.py` — parallel step execution
- `plugins/orchestration/skills/swarm/scripts/swarm_executor.py` — multi-agent coordination
- `plugins/orchestration/skills/executor/scripts/chain_planner.py` — intent analysis + modifiers
- `plugins/dev/skills/devops/scripts/nightly_executor.py` — ROI-based task selection
