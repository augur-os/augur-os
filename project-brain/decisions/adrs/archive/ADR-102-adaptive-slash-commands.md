---
status: Implemented
date: ''
deciders: []
related: []
hub: null
tags:
- adaptive
- slash
- commands
superseded_by: null
---

# ADR-102: Adaptive Slash Commands

## Context

Slash commands (`/implement-adr`, `/auto-fix`, `/sync`, `/ops`, etc.) are currently static. Their definitions (SKILL.md, chain YAML) don't evolve based on execution experience. This means:

1. **Repeated mistakes** - Same edge cases cause failures repeatedly
2. **No learning** - Successful patterns aren't captured back into the command
3. **Manual updates** - Improvements require human intervention
4. **Stale workflows** - Commands don't adapt to codebase changes

## Decision

Implement an **Adaptive Loop** that runs after every slash command execution:

```
┌─────────────────────────────────────────────────────────────┐
│                    ADAPTIVE SLASH COMMAND                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. EXECUTE                                                  │
│     └── Run command flow as defined                          │
│     └── Track metrics: steps, timing, failures, retries     │
│                                                              │
│  2. ANALYZE                                                  │
│     └── What went well? (fast paths, clean completions)      │
│     └── What went wrong? (errors, retries, missing steps)   │
│     └── What was missing? (edge cases, new patterns)        │
│                                                              │
│  3. IMPROVE                                                  │
│     └── Generate improvement suggestions                     │
│     └── Rank by impact (high/medium/low)                     │
│     └── Auto-apply safe improvements                         │
│     └── Queue human-review improvements                      │
│                                                              │
│  4. REWRITE                                                  │
│     └── Update SKILL.md with new learnings                    │
│     └── Update chain YAML with optimized steps               │
│     └── Log changes to runtime/command-evolution/            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Components

#### 1. Execution Tracker

Captures structured metrics during command execution:

```python
# runtime/command-evolution/{command_name}/executions/{timestamp}.json
{
  "command": "implement-adr",
  "started_at": "2026-02-15T10:00:00Z",
  "completed_at": "2026-02-15T10:45:00Z",
  "duration_seconds": 2700,
  "phases": [
    {
      "name": "Phase 1: Analysis",
      "status": "completed",
      "duration_seconds": 300,
      "steps": ["explore codebase", "parse ADR"],
      "issues": []
    },
    {
      "name": "Phase 3: Team Orchestration",
      "status": "retry",
      "duration_seconds": 1200,
      "steps": ["create team", "spawn teammates", "coordinate"],
      "issues": [
        {
          "step": "spawn teammates",
          "error": "Task tool timeout",
          "resolution": "Split into smaller subtasks",
          "retry_count": 2
        }
      ]
    }
  ],
  "metrics": {
    "files_read": 45,
    "files_written": 12,
    "tests_run": 23,
    "tests_passed": 21,
    "tests_failed": 2,
    "ralph_loops": 1,
    "token_usage": 125000
  },
  "outcome": "partial_success",
  "blockers": ["TypeScript build error in finance route"]
}
```

#### 2. Analysis Engine

Extracts patterns from execution:

```python
# plugins/ai/skills/ai_bridge/scripts/command_evolution.py

def analyze_execution(execution_log: dict) -> dict:
    """Analyze execution and extract improvement opportunities."""
    return {
        "success_patterns": [
            "Phase 0.5 worktree isolation prevented port collision",
            "Parallel team spawn reduced total time by 40%"
        ],
        "failure_patterns": [
            {
                "pattern": "Task tool timeout",
                "occurred_in": ["Phase 3.3"],
                "suggestion": "Add timeout hint: 'Use smaller subtasks for complex operations'"
            }
        ],
        "missing_steps": [
            {
                "after": "Phase 3.3",
                "suggestion": "Add health check: verify teammates spawned successfully before continuing"
            }
        ],
        "optimizations": [
            {
                "type": "cache",
                "suggestion": "Cache ADR parsing results for repeated runs"
            }
        ],
        "edge_cases": [
            {
                "trigger": "finance route TypeScript error",
                "suggestion": "Add Phase 6.5 pre-check: verify no existing TypeScript errors before implementation"
            }
        ]
    }
```

#### 3. Improvement Classifier

Determines which improvements can be auto-applied vs need review:

| Improvement Type | Auto-Apply | Reason |
|------------------|------------|--------|
| Add missing step | Yes | Reduces future failures |
| Add timeout hint | Yes | Non-breaking optimization |
| Cache suggestion | Yes | Performance improvement |
| Reorder phases | No | May break dependencies |
| Remove step | No | May be needed for edge cases |
| Change model tier | No | Cost/quality trade-off |

#### 4. SKILL.md Rewriter

Updates command definitions:

```yaml
# Runtime patch applied to SKILL.md
patch:
  target: plugins/ai/skills/ai_bridge/augur/skills/implement-adr/SKILL.md
  operation: insert_after
  anchor: "## Phase 3.3: Spawn Teammates"
  content: |
    
    ### Step 3.3.1: Verify Teammate Spawn (ADR-102)
    
    After spawning teammates, verify they started correctly:
    
    ```
    TaskList() → check all expected agents have active tasks
    If any teammate missing: respawn with exponential backoff (max 3 retries)
    ```
    
    This prevents coordination failures due to spawn errors.
    
    **Model**: Haiku (quick check)
```

#### 5. Chain YAML Optimizer

Updates workflow definitions:

```yaml
# Before
- name: developer
  action: implement_workstream_1
  parallel_group: impl

# After (adaptive update)
- name: developer
  action: implement_workstream_1
  parallel_group: impl
  timeout_hint: "Split into subtasks if exceeds 5 minutes"  # Added by adaptive loop
  cache_key: "adr_{number}_workstream_1"  # Added for efficiency
```

### Adaptive Loop Implementation

```python
# plugins/ai/skills/ai_bridge/scripts/adaptive_loop.py

async def run_adaptive_command(command_name: str, args: dict) -> dict:
    """Execute a slash command with adaptive improvement."""
    
    # 1. Load command definition
    skill_md = load_skill_definition(command_name)
    chain_yaml = load_chain_definition(command_name)
    
    # 2. Execute with tracking
    tracker = ExecutionTracker(command_name)
    result = await execute_command(skill_md, chain_yaml, args, tracker)
    
    # 3. Analyze execution
    analysis = analyze_execution(tracker.get_log())
    
    # 4. Generate improvements
    improvements = classify_improvements(analysis)
    
    # 5. Apply auto-safe improvements
    for imp in improvements.auto_apply:
        apply_improvement(skill_md, chain_yaml, imp)
        log_improvement(command_name, imp)
    
    # 6. Queue review-needed improvements
    for imp in improvements.needs_review:
        queue_for_review(command_name, imp)
    
    # 7. Commit changes
    if improvements.auto_apply:
        commit_skill_update(command_name, skill_md, chain_yaml)
    
    return {
        "execution_result": result,
        "improvements_applied": len(improvements.auto_apply),
        "improvements_queued": len(improvements.needs_review),
    }
```

### Directory Structure

```
runtime/
├── command-evolution/
│   ├── implement-adr/
│   │   ├── executions/
│   │   │   ├── 2026-02-15T10-00-00.json
│   │   │   └── 2026-02-15T14-30-00.json
│   │   ├── improvements/
│   │   │   ├── auto-applied/
│   │   │   │   └── 2026-02-15T10-45-00.yaml
│   │   │   └── queued/
│   │   │       └── 2026-02-15T10-45-00.yaml
│   │   └── evolution-log.md
│   ├── auto-fix/
│   ├── sync/
│   └── ops/
```

## Consequences

### Positive

1. **Continuous improvement** - Commands get better with each use
2. **Reduced repetition** - Same mistakes don't happen twice
3. **Knowledge capture** - Learnings encoded back into commands
4. **Adaptation** - Commands evolve with codebase changes

### Negative

1. **Complexity** - Additional infrastructure to maintain
2. **Non-determinism** - Command behavior changes over time
3. **Review overhead** - Some improvements need human approval
4. **Version control noise** - Frequent SKILL.md updates

### Mitigations

1. **Versioning** - Track SKILL.md versions with changelog
2. **Rollback** - Ability to revert to previous command definition
3. **Review queue** - Dashboard to approve/reject queued improvements
4. **Dry-run mode** - Preview improvements before applying

## Implementation Plan

### Phase 1: Infrastructure (Week 1)
- [ ] Create execution tracker
- [ ] Create runtime/command-evolution directory structure
- [ ] Implement analysis engine

### Phase 2: Adaptive Loop (Week 2)
- [ ] Implement improvement classifier
- [ ] Create SKILL.md rewriter
- [ ] Create chain YAML optimizer

### Phase 3: Integration (Week 3)
- [ ] Wrap existing slash commands with adaptive loop
- [ ] Add `/adaptive-review` command to review queued improvements
- [ ] Add `/adaptive-history` command to see evolution

### Phase 4: Monitoring (Week 4)
- [ ] Create evolution metrics dashboard
- [ ] Add rollback capability
- [ ] Add improvement approval workflow

## References

- ADR-054: Task Tool for Subagent Orchestration
- ADR-096: Progressive Disclosure via TODO_ Markers
- ADR-101: Worktree Isolation for Parallel Development
