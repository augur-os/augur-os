---
status: Implemented
date: '2026-01-24'
deciders:
- User
- Claude Agent
related: []
hub: null
tags:
- claude
- practices
- improvement
- plan
superseded_by: null
---

# ADR-019: Claude Practices Improvement Plan

## Context

A comparative analysis was conducted between the augur Claude/AI practices and multiple reference repositories to identify gaps and improvement opportunities:

1. **[everything-claude-code](https://github.com/affaan-m/everything-claude-code)** - Competition winner
2. **[oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode)** - 2.2k stars, parallel execution patterns
3. **[superpowers](https://github.com/obra/superpowers)** - 35.9k stars, agentic skills framework

### Current Augur Strengths

The augur already excels in several areas:

| Area | Implementation |
|------|----------------|
| Multi-IDE Distribution | Auto-generates to 6 IDEs from single source (`docs/agent-rules.md`) |
| MCP Architecture | Context-aware tool loading, 8 tool categories, page-specific tool groups |
| Mode System | Dev/Operation mode filtering reduces cognitive load |
| Context Personalization | `get-context` tool with preferences, verticals, RAG enrichment |
| Chain Orchestration | 25 YAML-defined multi-agent chains |
| ADR Documentation | 18+ Architecture Decision Records |
| Plugin Mounting | Build-time UI component mounting |
| Issue Tracking | In-code `TODO_` markers with CI scanning |
| Debugging Protocol | 4-phase protocol preventing fix loops |

### Identified Gaps

Analysis revealed the following missing capabilities:

| Gap | Description | Priority |
|-----|-------------|----------|
| Hooks System | Trigger-based automations on events | High |
| Checkpoint Command | Development savepoints for safe rollback | High |
| Verification Loop | Formal output validation cycle in chains | High |
| Context Window Management | Documented MCP/tool limits | Medium |
| Eval Harness | Testing framework for AI outputs | Medium |
| Build Error Resolver Agent | Specialized agent for build failures | Medium |
| Strategic Compact | Context compression for long sessions | Low |

## Decision

We will implement a phased improvement plan adopting best practices from the competition winner while preserving augur's architectural strengths.

### Phase 0: Factory Agent Deep Review & Hardening (FIRST)

Before implementing new patterns, conduct a systematic review and hardening of all augur factory agents against reference implementations. The goal is to ensure agents are optimized for the **local-first second brain** vision documented in `data/venture/strategy/vision.md`.

#### Context

Augur agents serve a different purpose than generic coding agents:

| Aspect | Generic Coding Agents | Augur Factory Agents |
|--------|----------------------|--------------------------|
| **Target** | Any codebase | Local edge "second brain" |
| **Philosophy** | Cloud-first, heavy deps | Unix philosophy, plain text |
| **Data** | Ephemeral, cloud-stored | Self-sovereign, git-trackable |
| **Architecture** | Monolithic | 3-layer (Reasoning → Execution → Ops) |
| **Control** | Autonomous | Human-centric with approval gates |

Agents must be hardened to embody these principles while adopting valuable patterns from reference implementations.

#### Reference Repositories for Phase 0

| Repository | Stars | Key Patterns to Evaluate |
|------------|-------|-------------------------|
| **[everything-claude-code](https://github.com/affaan-m/everything-claude-code)** | Winner | Hooks, checkpoints, verification loops |
| **[oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode)** | 2.2k | Parallel execution, swarm, ecomode, tiering |
| **[superpowers](https://github.com/obra/superpowers)** | 35.9k | TDD enforcement, subagent workflows, seven-stage cycle |

##### Superpowers Framework Highlights

The superpowers framework (35.9k stars) implements a rigorous seven-stage development workflow:

1. **Design Refinement** - Interactive questioning and spec creation before coding
2. **Isolated Workspace** - Git worktrees for parallel development
3. **Implementation Planning** - Bite-sized tasks (2-5 minutes each)
4. **Autonomous Execution** - Subagent-driven with two-stage code review
5. **Test-First Development** - Enforced RED-GREEN-REFACTOR cycles
6. **Inter-Task Review** - Catches issues by severity level
7. **Branch Completion** - Merge/PR decision logic

**Key Patterns to Adopt**:
| Pattern | Description | Augur Fit |
|---------|-------------|---------------|
| **Subagent-driven tasks** | Fresh agent instance per task, prevents plan deviation | Aligns with chain orchestration |
| **Two-stage review** | Spec compliance, then code quality | Enhance validator agent |
| **Evidence-based verification** | No success without proof | Aligns with Ralph pattern |
| **Composable skills** | Context-triggered, not explicitly invoked | Already implemented via MCP |
| **Bite-sized planning** | 2-5 minute task granularity | Add to planning phase |

#### 0.1 Agent Inventory & Mapping

**Augur Factory Agents (17 agents)**:

| Agent | Purpose | Reference Match |
|-------|---------|-----------------|
| **architect** | System design, blueprints, ADRs | ✅ architect.md |
| **developer** | Code implementation | ⚠️ Partial (refactor-cleaner) |
| **validator** | Testing, verification | ✅ e2e-runner.md |
| **security** | Security audits | ✅ security-reviewer.md |
| **frontend** | UI/UX patterns | ❌ No equivalent |
| **devops** | Infrastructure, CI/CD | ❌ No equivalent |
| **executor** | Task management, chains | ✅ planner.md |
| **librarian** | Documentation | ✅ doc-updater.md |
| **data-engineer** | Data schemas, migrations | ❌ No equivalent |
| **webapp-testing** | UI testing, screenshots | ✅ e2e-runner.md |
| **user-advocate** | UX improvements | ❌ No equivalent |
| **vision-keeper** | Architecture consistency | ❌ No equivalent |
| **experiment-tracker** | A/B tests, experiments | ❌ No equivalent |
| **structure-enforcer** | Code structure rules | ✅ refactor-cleaner.md |
| **oss-manager** | Git operations | ❌ No equivalent |
| **control** | System operations | ❌ No equivalent |
| **organizations** | Multi-org management | ❌ No equivalent |

**Reference Agents Without Augur Equivalent**:

| Reference Agent | Purpose | Action |
|-----------------|---------|--------|
| **build-error-resolver** | Surgical build fix | **CREATE** (already in Phase 2.3) |
| **code-reviewer** | Code review | **ENHANCE** validator |
| **tdd-guide** | TDD workflow | **CREATE** new chain/agent |

#### 0.2 Review Process (Per Agent)

For each agent, conduct the same analysis as the architect comparison:

```yaml
# Review template for each agent
agent_review:
  name: "{agent_name}"

  step_1_read_current:
    - Read plugins/orchestration/skills/{agent}/SKILL.md
    - Read any modules/ and references/
    - Document current capabilities

  step_2_read_reference:
    - Fetch reference agent from everything-claude-code
    - Document their patterns

  step_3_compare:
    dimensions:
      - exploration_depth: "How thorough is discovery?"
      - output_quality: "How actionable are outputs?"
      - token_efficiency: "Does it waste tokens on simple tasks?"
      - safety_guardrails: "Are there proper constraints?"
      - second_brain_alignment: "Does it fit local-first philosophy?"
    scoring: "Rate 1-10 for each dimension"

  step_4_harden:
    - Add tiering (low/medium/high) if beneficial
    - Add read-only mode for advisory agents
    - Add circuit breaker patterns
    - Add iron law verification
    - Align with Unix philosophy
    - Ensure plain-text outputs

  step_5_document:
    - Update SKILL.md with enhancements
    - Document in this ADR
```

#### 0.3 Second Brain Alignment Checklist

Each agent must pass these alignment checks:

| Check | Question | Required |
|-------|----------|----------|
| **Plain Text Output** | Does agent output human-readable formats (YAML, MD)? | ✅ |
| **Git-Trackable** | Are outputs diffable and versionable? | ✅ |
| **Local-First** | Does agent work fully offline? | ✅ |
| **Human Gates** | Are approval points defined for consequential actions? | ✅ |
| **Unix Composable** | Can output be piped to other tools? | ✅ |
| **Lightweight** | No heavy ML dependencies for basic operations? | ✅ |
| **Self-Sovereign** | No cloud requirements for core functionality? | ✅ |

#### 0.4 Agent Review Schedule

| Priority | Agent | Reference | Status |
|----------|-------|-----------|--------|
| **P0** | architect | architect.md | ✅ Reviewed (see comparison above) |
| **P0** | developer | refactor-cleaner.md | ⏳ Pending |
| **P0** | validator | e2e-runner.md | ⏳ Pending |
| **P0** | security | security-reviewer.md | ⏳ Pending |
| **P1** | executor | planner.md | ⏳ Pending |
| **P1** | librarian | doc-updater.md | ⏳ Pending |
| **P1** | frontend | (no reference) | ⏳ Pending |
| **P1** | webapp-testing | e2e-runner.md | ⏳ Pending |
| **P2** | devops | (no reference) | ⏳ Pending |
| **P2** | data-engineer | (no reference) | ⏳ Pending |
| **P2** | structure-enforcer | refactor-cleaner.md | ⏳ Pending |
| **P2** | user-advocate | (no reference) | ⏳ Pending |
| **P2** | vision-keeper | (no reference) | ⏳ Pending |
| **P3** | experiment-tracker | (no reference) | ⏳ Pending |
| **P3** | oss-manager | (no reference) | ⏳ Pending |
| **P3** | control | (no reference) | ⏳ Pending |
| **P3** | organizations | (no reference) | ⏳ Pending |

#### 0.5 New Agents to Create

Based on reference analysis:

| New Agent | Source | Purpose | Priority |
|-----------|--------|---------|----------|
| **build-error-resolver** | everything-claude-code | Surgical build error fix | High (P1) |
| **tdd-guide** | everything-claude-code | TDD workflow enforcement | Medium (P2) |
| **code-reviewer** | everything-claude-code | Dedicated review agent | Medium (P2) |

#### 0.6 Architect Review Summary (Completed)

| Dimension | Augur | Reference | Winner |
|-----------|-----------|-----------|--------|
| Exploration Depth | 9/10 | 7/10 | Augur |
| Output Quality | 10/10 | 6/10 | Augur |
| Token Efficiency | 3/10 | 9/10 | Reference |
| Safety Guardrails | 5/10 | 9/10 | Reference |
| **Overall** | **7.85/10** | **6.75/10** | **Augur** |

**Hardening Applied**:
- [ ] Add tiering (low/medium/high)
- [ ] Add read-only mode enforcement
- [ ] Add iron law verification
- [ ] Add circuit breaker (3 failures → re-evaluate)

#### 0.7 Expected Outcomes

After Phase 0 completion:

| Metric | Before | After |
|--------|--------|-------|
| Agents with tiering | 0 | 17 |
| Agents with read-only mode | 0 | 10+ (advisory agents) |
| Agents with circuit breaker | 0 | 17 |
| Token efficiency | Baseline | 30-50% improvement |
| Second brain alignment | Partial | 100% |

### Phase 1: High Priority (Implement After Phase 0)

#### 1.1 Hooks System

Add trigger-based automation hooks for pre/post events.

**Location**: `data/core/ide-integration/hooks/`

**Structure**:
```yaml
# hooks.yaml
version: "1.0"
hooks:
  pre-commit:
    - name: scan-markers
      run: python3 .github/scripts/scan_code_markers.py --summary
      on_failure: warn
    - name: lint-dashboard
      run: npm run lint --prefix src/dashboard
      on_failure: block

  post-chain:
    - name: update-manifest
      run: python3 .github/scripts/update_skill_manifest.py

  on-build-error:
    - name: notify-error
      run: python3 .github/scripts/notify_build_error.py

  on-test-failure:
    - name: capture-failure
      run: python3 .github/scripts/capture_test_failure.py
```

**Implementation Files**:
- `data/core/ide-integration/hooks/hooks.yaml` - Hook definitions
- `.github/scripts/hook_runner.py` - Hook execution engine
- `docs/agent-rules.md` - Documentation update

#### 1.2 Checkpoint Command

Add `/checkpoint` workflow for development savepoints.

**Location**: `data/core/ide-integration/workflows/checkpoint.md`

**Functionality**:
```markdown
## /checkpoint [name]

Creates a named development savepoint for safe experimentation.

### Actions:
1. Stash uncommitted changes (optional)
2. Create git tag: `checkpoint/{name}-{timestamp}`
3. Log to `runtime/checkpoints.yaml`
4. Display rollback command

### Rollback:
/checkpoint --restore [name]
```

**Implementation Files**:
- `data/core/ide-integration/workflows/checkpoint.md` - Workflow definition
- `.github/scripts/checkpoint_manager.py` - Checkpoint logic
- `runtime/checkpoints.yaml` - Checkpoint registry

#### 1.3 Verification Loop Pattern

Add formal verification to all code-producing chains.

**Pattern Definition**:
```yaml
# Add to chain schema
verification_loop:
  enabled: true
  max_iterations: 3
  steps:
    - name: build
      command: npm run build
      required: true
    - name: lint
      command: npm run lint
      required: true
    - name: test
      command: npm run test
      required: false
    - name: security
      command: npm audit --audit-level=high
      required: false
  on_failure:
    action: analyze_and_retry
    max_retries: 2
  on_success:
    action: continue_chain
```

**Chains to Update**:
- `feature_development.yaml`
- `bug_workflow.yaml`
- `code_review.yaml`
- `refactoring.yaml`

**Implementation Files**:
- `data/core/ide-integration/chains/_verification_loop.yaml` - Reusable pattern
- `plugins/orchestration/skills/executor/scripts/verification_runner.py` - Execution logic
- Update existing chains to include verification loop

### Phase 2: Medium Priority (Implement Second)

#### 2.1 Context Window Management Guidelines

Document explicit limits for MCP and tool configuration.

**Add to `docs/agent-rules.md`**:
```markdown
## Context Window Management

### MCP Limits (Prevents Context Exhaustion)

| Limit | Value | Rationale |
|-------|-------|-----------|
| Max configured MCPs | 20-30 | Beyond this, startup slows |
| Max enabled per session | 10 | Context window pressure |
| Max active tools | 80 | Tool descriptions consume tokens |
| Max tools per page | 30 | Already in mcp_tool_groups.yaml |

### Warning Signs
- Slow MCP initialization (>5s)
- Truncated context in responses
- Tool calls failing silently

### Mitigation
1. Use `mcp_tool_groups.yaml` to scope tools per page
2. Disable unused tool categories in `mcp_tools.yaml`
3. Use `/strategic-compact` for long sessions
```

**Implementation Files**:
- `docs/agent-rules.md` - Add section
- `.github/scripts/mcp_health_check.py` - Validate limits
- `config-data/mcp_tools.yaml` - Add comments with limits

#### 2.2 Eval Harness Skill

Create skill for testing prompts and agent outputs.

**Location**: `plugins/dev/skills/validator/` <!-- eval-harness removed; eval capabilities folded into validator -->

**Structure**:
```
eval-harness/
├── SKILL.md
├── BACKLOG.md
├── scripts/
│   ├── run_eval.py           # Execute evaluation suite
│   ├── generate_report.py    # Produce metrics report
│   ├── compare_runs.py       # A/B test comparison
│   └── test_case_runner.py   # Individual test execution
├── templates/
│   └── test_case.yaml        # Test case template
└── dashboard/
    └── tabs/
        └── EvalTab.tsx       # UI for viewing results
```

**Test Case Format**:
```yaml
# plugins/dev/skills/validator/augur/test_cases/prompt_quality.yaml  <!-- eval-harness removed -->
test_suite: prompt_quality
cases:
  - id: inbox-summarize-001
    prompt_id: dashboard.inbox.summarize
    input:
      items: ["Email 1 content", "Email 2 content"]
    expected:
      contains: ["summary", "action items"]
      max_tokens: 500
      tone: professional
    metrics:
      - relevance
      - conciseness
      - accuracy
```

**Implementation Files**:
- `plugins/dev/skills/validator/SKILL.md` <!-- eval-harness removed; eval capabilities folded into validator -->
- `plugins/dev/skills/validator/scripts/*.py`
- `plugins/dev/skills/validator/augur/test_cases/` <!-- eval-harness removed -->

#### 2.3 Build Error Resolver Agent

Add specialized agent for build failure resolution.

**Add to Agent Registry**:
```yaml
# In chain agent definitions
agents:
  build_error_resolver:
    specialization: build_failures
    description: Specialized agent for diagnosing and fixing build errors
    actions:
      - parse_error_output:
          description: Extract structured error info from build output
      - identify_root_cause:
          description: Determine underlying cause of failure
      - search_similar_fixes:
          description: Find similar errors and their resolutions
      - apply_fix:
          description: Implement the identified fix
      - verify_build:
          description: Confirm build succeeds after fix
    tools:
      - grep
      - read
      - edit
      - bash (npm/build commands only)
```

**Implementation Files**:
- `data/core/ide-integration/chains/_agents/build_error_resolver.yaml`
- Update `feature_development.yaml` to use this agent on build failures

### Phase 3: Low Priority (Implement Last)

#### 3.1 Strategic Compact Command

Add context compression for long sessions.

**Location**: `data/core/ide-integration/workflows/strategic-compact.md`

**Functionality**:
```markdown
## /strategic-compact

Compresses context for long sessions to prevent exhaustion.

### Actions:
1. Summarize completed work (max 200 words)
2. List active files (paths only, no content)
3. State current objective (1 sentence)
4. Archive intermediate outputs to runtime/
5. Present compressed context for continuation

### Output Format:
## Session Compact
**Completed**: [summary]
**Active Files**: [list]
**Current Goal**: [objective]
**Next Step**: [action]
```

**Implementation Files**:
- `data/core/ide-integration/workflows/strategic-compact.md`
- `.github/scripts/context_compressor.py`

### Phase 4: Orchestration Enhancements (From oh-my-claudecode Analysis)

A secondary analysis was conducted comparing augur orchestration with [oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) (2.2k stars), which implements sophisticated parallel execution patterns.

#### Key Findings

| Aspect | Augur Current | OMC Approach | Gap |
|--------|-------------------|--------------|-----|
| Execution Model | Sequential only | Parallel (Ultrapilot), Swarm, Pipeline | Critical |
| Token Efficiency | No optimization | Ecomode (30-50% savings) | Critical |
| Persistence | Autonomy gates | Ralph pattern (verification loops) | High |
| Cancellation | None | Graceful cancel-* commands | Medium |
| Progress Visibility | None | HUD statusline | Medium |

#### 4.1 Parallel Step Execution (Ultrapilot Pattern)

**Priority**: Critical

Add parallel execution capability to chains for 3-5x speedup on decomposable tasks.

**Schema Enhancement**:
```yaml
# Enhanced chain schema (backward compatible)
name: feature_development
execution_mode: ultrapilot  # NEW: sequential | ultrapilot | swarm
parallel_groups:            # NEW: steps that can run in parallel
  - group: exploration
    steps: [explore, security_scan]
    file_ownership:
      explore: ["src/**/*.ts", "!src/api/**"]
      security_scan: ["src/api/**", "config/**"]
  - group: implementation
    steps: [implement, write_tests]
    file_ownership:
      implement: ["src/components/**"]
      write_tests: ["tests/**"]
```

**Five-Phase Execution Model** (from OMC):
1. **Task Analysis**: Determine parallelizability (2+ independent subtasks with file boundaries)
2. **Decomposition**: Architect breaks task into parallel-safe components
3. **File Ownership**: Assign exclusive file sets per worker (no overlap)
4. **Parallel Execution**: Workers run simultaneously on assigned files
5. **Integration**: Sequential merge of outputs, resolve src/lib file conflicts

**Implementation Files**:
- `plugins/orchestration/skills/executor/scripts/parallel_executor.py` - Parallel execution engine
- `data/core/ide-integration/chains/_schema.json` - Add parallel schema fields
- `data/core/ide-integration/chains/_parallel_template.yaml` - Reusable pattern

#### 4.2 Ecomode (Model Tier Routing)

**Priority**: Critical

Route tasks to appropriate model tier for 30-50% token savings.

**Tier Definitions**:
```yaml
# config-data/model_tiers.yaml
tiers:
  low:
    model: haiku
    max_tokens: 4096
    use_cases:
      - simple_lookups
      - file_enumeration
      - basic_search
      - status_checks
    cost_multiplier: 0.1

  medium:
    model: sonnet
    max_tokens: 8192
    use_cases:
      - multi_file_analysis
      - moderate_refactoring
      - code_review
      - documentation
    cost_multiplier: 0.5

  high:
    model: opus
    max_tokens: 32768
    use_cases:
      - deep_architecture
      - cross_cutting_concerns
      - security_analysis
      - complex_debugging
    cost_multiplier: 1.0
```

**Complexity Detection**:
```python
def detect_complexity(task: str, context: dict) -> str:
    """Route to appropriate tier based on task complexity."""
    # LOW triggers
    if any(kw in task.lower() for kw in ["find", "list", "what is", "where is"]):
        return "low"

    # HIGH triggers
    if any(kw in task.lower() for kw in ["architect", "security", "refactor entire"]):
        return "high"

    # File count heuristic
    if context.get("affected_files", 0) > 10:
        return "high"
    elif context.get("affected_files", 0) > 3:
        return "medium"

    return "medium"  # Default
```

**Implementation Files**:
- `config-data/model_tiers.yaml` - Tier definitions
- `src/llm/tier_router.py` - Complexity detection and routing
- `src/llm/agent_router.py` - Integrate tier routing

#### 4.3 Swarm Execution Mode

**Priority**: High

Add N-worker swarm for bulk task processing.

**Swarm Configuration**:
```yaml
# In chain definition
execution_mode: swarm
swarm_config:
  min_workers: 2
  max_workers: 5  # Claude Code limit
  task_timeout: 300  # 5 minutes
  claiming: atomic  # Prevents duplicate work
  on_timeout: release_and_reassign
```

**Atomic Task Claiming**:
```python
class SwarmTaskPool:
    def claim_task(self, worker_id: str) -> Optional[Task]:
        """Atomically claim next available task."""
        with self.lock:
            for task in self.tasks:
                if task.status == "pending":
                    task.status = "claimed"
                    task.worker_id = worker_id
                    task.claimed_at = datetime.now()
                    return task
        return None

    def release_stale(self, timeout_seconds: int = 300):
        """Release tasks claimed > timeout ago."""
        cutoff = datetime.now() - timedelta(seconds=timeout_seconds)
        with self.lock:
            for task in self.tasks:
                if task.status == "claimed" and task.claimed_at < cutoff:
                    task.status = "pending"
                    task.worker_id = None
```

**Implementation Files**:
- `plugins/orchestration/skills/executor/scripts/swarm_executor.py` - Swarm execution
- `plugins/orchestration/skills/executor/scripts/task_pool.py` - Atomic task claiming

#### 4.4 Ralph Persistence Pattern

**Priority**: High

Enforce completion verification before any task is marked done.

**Iron Law Verification**:
```yaml
# Add to verification_loop pattern
ralph_verification:
  enabled: true
  iron_law: "No completion without fresh evidence"
  checks:
    - name: build_passes
      command: npm run build
      evidence: "Build output shows success"
    - name: tests_pass
      command: npm run test
      evidence: "All tests green"
    - name: no_regressions
      command: git diff --stat
      evidence: "Only expected files changed"
    - name: architect_approval
      agent: architect
      action: verify_completion
      required: true

  zero_tolerance:
    - no_scope_reduction
    - no_partial_completion
    - no_test_deletion
    - no_premature_stopping

  circuit_breaker:
    max_failures: 3
    action: architectural_re_evaluation
```

**Implementation Files**:
- `data/core/ide-integration/chains/_ralph_verification.yaml` - Pattern definition
- Update `verification_runner.py` to include Ralph checks

#### 4.5 Graceful Cancellation

**Priority**: Medium

Add ability to cancel running execution modes gracefully.

**Cancel Commands**:
```markdown
## /cancel

Gracefully cancel current execution.

### Variants:
- /cancel - Cancel current chain
- /cancel-ultrapilot - Cancel parallel execution
- /cancel-swarm - Cancel swarm workers

### Behavior:
1. Set abort flag in state file
2. Workers check flag between tasks
3. Complete current task (don't corrupt)
4. Cleanup state
5. Report partial progress
```

**Implementation Files**:
- `data/core/ide-integration/workflows/cancel.md` - Workflow definition
- `.github/scripts/cancel_manager.py` - Cancellation logic
- Update executors to check abort flag

#### 4.6 Progress HUD

**Priority**: Medium

Add real-time progress visibility to dashboard.

**HUD Components**:
```typescript
// Dashboard statusline showing:
interface HUDStatus {
  activeChain: string | null;
  currentStep: number;
  totalSteps: number;
  activeWorkers: number;  // For swarm/ultrapilot
  modelTier: 'low' | 'medium' | 'high';
  tokenUsage: {
    used: number;
    limit: number;
    percentage: number;
  };
  rateLimitStatus: {
    remaining: number;
    resetAt: Date;
  };
}
```

**Implementation Files**:
- `plugins/orchestration/skills/executor/dashboard/components/HUD.tsx` - HUD component
- `src/dashboard/app/api/hud/route.ts` - HUD data endpoint

### Phase 5: Agent Tiering Enhancement

Based on detailed comparison of augur architect vs OMC architect agents, implement tiered agent variants for all core agents.

#### Analysis Summary

| Dimension | Augur | OMC | Winner |
|-----------|-----------|-----|--------|
| Exploration Depth | 9/10 | 7/10 | Augur |
| Output Quality | 10/10 | 6/10 | Augur |
| Actionability | 9/10 | 5/10 | Augur |
| Token Efficiency | 3/10 | 9/10 | OMC |
| Safety Guardrails | 5/10 | 9/10 | OMC |

**Conclusion**: Augur agents are more capable but waste tokens on simple tasks. Adopt OMC's tiering while preserving augur's superior output quality.

#### 5.1 Tiered Agent Schema

**Enhanced SKILL.md Format**:
```yaml
---
name: architect
version: 0.4.0
tiers:
  low:
    model: haiku
    mode: advisory
    tools: [Read, Glob, Grep]
    max_files: 5
    use_cases:
      - "What does X do?"
      - "Find file containing Y"
      - "Simple code lookup"
    escalate_when:
      - cross_file_dependencies
      - architecture_questions
      - search_failures > 2

  medium:
    model: sonnet
    mode: advisory
    tools: [Read, Glob, Grep, Bash(analysis)]
    max_files: 20
    use_cases:
      - "Multi-file analysis"
      - "Moderate refactoring plan"
      - "Code review"
    escalate_when:
      - deep_architecture_needed
      - security_concerns
      - affected_files > 20

  high:
    model: opus
    mode: advisory  # or 'executor' for implementation
    tools: [Read, Glob, Grep, Bash(analysis), WebSearch]
    max_files: unlimited
    use_cases:
      - "Full architecture design"
      - "Cross-cutting concerns"
      - "Blueprint generation"
      - "External repo adaptation"

verification:
  iron_law: "No claims without file:line evidence"
  circuit_breaker:
    max_failures: 3
    action: architectural_re_evaluation

  read_only_mode:
    enabled: true  # Architect advises, doesn't implement
    exceptions: ["high tier with explicit implement request"]
---
```

#### 5.2 Agents to Tier

| Agent | Low Tier Use Cases | Medium Tier | High Tier |
|-------|-------------------|-------------|-----------|
| **architect** | File lookups, "what is X" | Multi-file analysis | Full blueprints |
| **developer** | Single-file fixes | Multi-file changes | Large refactors |
| **validator** | Single test run | Test suite | Full regression |
| **security** | Quick scan | Moderate audit | Deep analysis |
| **frontend** | Component lookup | Page audit | Full redesign |

#### 5.3 Automatic Tier Selection

```python
# src/llm/agent_tier_selector.py
def select_tier(agent: str, task: str, context: dict) -> str:
    """Select appropriate tier based on task complexity."""

    # Explicit tier request
    if "thorough" in task.lower() or "deep" in task.lower():
        return "high"
    if "quick" in task.lower() or "simple" in task.lower():
        return "low"

    # File count heuristic
    file_count = context.get("affected_files", 0)
    if file_count > 20:
        return "high"
    elif file_count > 5:
        return "medium"

    # Agent-specific heuristics
    if agent == "architect":
        if any(kw in task for kw in ["blueprint", "design", "architecture"]):
            return "high"
        if any(kw in task for kw in ["find", "locate", "what is"]):
            return "low"

    return "medium"  # Default
```

#### 5.4 Implementation Files

- `plugins/dev/skills/advisor/SKILL.md` - Add tiers section
- `plugins/dev/skills/developer/SKILL.md` - Add tiers section
- `plugins/dev/skills/validator/SKILL.md` - Add tiers section
- `src/llm/agent_tier_selector.py` - Tier selection logic
- `src/llm/agent_router.py` - Integrate tier selection
- `config-data/agent_tiers.yaml` - Global tier configuration

### Phase 6: Open Source Strategy & Package Extraction

Strategic decisions about extracting reusable components for upstream contribution and community adoption.

#### Context

After implementing Phases 1-5, the augur will have a sophisticated orchestration layer that could benefit the broader Claude Code community. Two key decisions must be made:

1. **Orchestration Plugin**: Should core agents + orchestration become a standalone plugin?
2. **MCP Package**: Should MCP logic become a public pip package or remain proprietary?

#### 6.1 Extract Core Agents + Orchestration as Standalone Plugin

**Priority**: Strategic (Post Phase 4-5)

**Goal**: Create `augur-orchestrator` as a standalone Claude Code plugin that can be:
- Used independently of the full augur
- Upstreamed to oh-my-claudecode or published separately
- Installed via npm (like OMC) or as a Claude Code plugin

**Components to Extract**:
```
augur-orchestrator/
├── package.json              # npm package definition
├── CLAUDE.md                 # Plugin entry point
├── README.md                 # Documentation
├── LICENSE                   # MIT or Apache 2.0
├── agents/
│   ├── architect.md          # Tiered architect agent
│   ├── architect-low.md
│   ├── architect-medium.md
│   ├── developer.md
│   ├── developer-low.md
│   ├── validator.md
│   ├── security.md
│   └── build-fixer.md
├── skills/
│   ├── ultrapilot/           # Parallel execution
│   ├── swarm/                # N-worker swarm
│   ├── ecomode/              # Model tier routing
│   ├── ralph/                # Persistence verification
│   ├── checkpoint/           # Development savepoints
│   └── cancel/               # Graceful cancellation
├── chains/
│   ├── _schema.json          # Chain definition schema
│   ├── feature_development.yaml
│   ├── bug_workflow.yaml
│   └── code_review.yaml
└── lib/
    ├── orchestrator.py       # Core orchestration engine
    ├── parallel_executor.py  # Ultrapilot implementation
    ├── swarm_executor.py     # Swarm implementation
    ├── tier_router.py        # Ecomode implementation
    └── task_pool.py          # Atomic task claiming
```

**Extraction Criteria**:
| Component | Extract? | Rationale |
|-----------|----------|-----------|
| Agent definitions | ✅ Yes | Generic, reusable |
| Chain orchestrator | ✅ Yes | Core value proposition |
| Parallel/Swarm executors | ✅ Yes | Key differentiator |
| Tier routing | ✅ Yes | Token savings benefit all |
| MCP gateway | ❓ Decide in 6.2 | Has proprietary aspects |
| Dashboard UI | ❌ No | Augur-specific |
| Plugin mounting | ❌ No | Augur-specific |
| Mode system | ❌ No | Augur-specific |

**Upstream Options**:

| Option | Pros | Cons |
|--------|------|------|
| **A: Contribute to OMC** | Large existing community (2.2k stars), established distribution | Must adapt to their patterns, less control |
| **B: Publish as separate package** | Full control, can maintain augur patterns | Need to build community from scratch |
| **C: Both** | Maximum reach | Maintenance burden of two codebases |

**Recommended**: Option B first (publish `augur-orchestrator`), then evaluate Option A based on community feedback.

**Publication Checklist**:
- [ ] Extract components to standalone repo
- [ ] Remove augur-specific dependencies
- [ ] Add comprehensive documentation
- [ ] Create example chains for common workflows
- [ ] Publish to npm (`npx augur-orchestrator`)
- [ ] Create GitHub releases with changelog
- [ ] Submit to Claude Code plugin directory (if exists)

#### 6.2 MCP Logic: Open Source vs Proprietary

**Priority**: Strategic (Requires Business Decision)

**Current State**:
```
plugins/augur-mcp/
├── src/augur_mcp/
│   ├── server.py           # MCP server entry point
│   ├── tools/              # Tool implementations
│   ├── domain/             # Business logic
│   │   ├── agent_mgmt.py   # Agent management
│   │   ├── chain_exec.py   # Chain execution
│   │   └── context.py      # Context injection
│   └── adapters/           # External integrations
└── pyproject.toml          # Package definition
```

**Decision Matrix**:

| Factor | Open Source (pip install) | Keep Proprietary |
|--------|---------------------------|------------------|
| **Community Growth** | High - others can contribute | Low - single maintainer |
| **Competitive Advantage** | Reduced - competitors can use | Preserved |
| **Maintenance Burden** | Shared with community | Full responsibility |
| **Integration Friction** | Low - standard pip install | Higher - manual setup |
| **Revenue Potential** | Indirect (consulting, hosting) | Direct (licensing) |
| **Bug Discovery** | Faster (more eyes) | Slower |
| **Feature Requests** | Community-driven | User-driven |

**Option A: Full Open Source**

Publish as `pip install augur-mcp`:

```python
# Anyone can use:
from augur_mcp import MCPServer, ChainExecutor, TierRouter

server = MCPServer(
    tools_config="mcp_tools.yaml",
    tier_routing=True
)
server.run()
```

**Pros**:
- Establishes augur as reference implementation
- Community contributions improve quality
- Positions you as thought leader

**Cons**:
- Competitors (including OMC) could adopt your patterns
- Support burden from community

**Option B: Open Source Core, Proprietary Extensions**

Split into two plugins:

```
augur-mcp-core (MIT License)
├── Basic MCP server
├── Tool registration
├── Simple chain execution
└── Standard tier routing

augur-mcp-pro (Proprietary)
├── Advanced orchestration patterns
├── Enterprise integrations
├── Priority support
└── Custom agent training
```

**Pros**:
- Core benefits community
- Premium features generate revenue
- Clear upgrade path

**Cons**:
- More complex to maintain
- Community may fork core and add premium features

**Option C: Keep Fully Proprietary**

MCP logic remains internal to augur only.

**Pros**:
- Full competitive advantage preserved
- No external support burden
- Complete control over roadmap

**Cons**:
- Slower development (no community)
- May become outdated vs open alternatives
- Harder to attract contributors

**Recommendation**: **Option B (Open Core)** - Release `augur-mcp-core` as open source, keep advanced orchestration as proprietary extension. This maximizes community benefit while preserving competitive advantage.

#### 6.3 Implementation Roadmap

```
Phase 6 Timeline (after Phases 4-5 complete):

Week 1-2: Component Audit
├── Identify all extractable components
├── Document dependencies between components
├── Define API boundaries
└── Create extraction plan

Week 3-4: Orchestrator Extraction
├── Create augur-orchestrator repo
├── Extract agent definitions
├── Extract chain executor
├── Extract parallel/swarm executors
└── Write documentation

Week 5-6: MCP Core Extraction
├── Define core vs pro boundary
├── Create augur-mcp-core package
├── Remove proprietary dependencies
├── Write API documentation
└── Create example implementations

Week 7-8: Publication
├── Publish npm package (orchestrator)
├── Publish pip package (mcp-core)
├── Create announcement blog post
├── Submit to relevant directories
└── Gather initial feedback

Ongoing: Community Management
├── Triage issues and PRs
├── Release updates
├── Evaluate upstream contributions to OMC
└── Monitor competitive landscape
```

#### 6.4 Success Metrics

| Metric | Target (6 months) |
|--------|-------------------|
| npm downloads (orchestrator) | 500+ |
| pip installs (mcp-core) | 300+ |
| GitHub stars | 200+ |
| Community PRs merged | 10+ |
| Upstream contributions accepted | 2+ |

### Phase 7: External MCP Integration

Integrate external MCP servers to enhance agent capabilities with web search, documentation, and API access.

#### Context

oh-my-claudecode uses external MCP servers (Exa, Context7, GitHub) to augment Claude's capabilities. Augur currently only uses the internal `exo` MCP server. Adding external MCPs can provide:
- Real-time web search with code-aware results
- Up-to-date library documentation
- Native GitHub API integration
- Enhanced web scraping capabilities

**Note**: Augur already uses **Brightdata** and **Firecrawl** for web scraping. The MCP selection must evaluate overlap and integration with these existing tools.

#### 7.1 MCP Candidates Evaluation

**DECISION REQUIRED**: During implementation, evaluate each candidate against existing tools.

| MCP Server | Purpose | Cost | Overlap with Existing |
|------------|---------|------|----------------------|
| **[Context7](https://github.com/upstash/context7)** | Library documentation | Free | None - new capability |
| **[Exa](https://exa.ai)** | AI code search | $49-449/mo | Partial with Brightdata |
| **[GitHub MCP](https://github.com/github/github-mcp-server)** | GitHub API | Free (PAT) | None - enhances `gh` CLI |
| **[Firecrawl MCP](https://github.com/anthropics/firecrawl-mcp)** | Web scraping | Already using | Direct integration |
| **[Brightdata MCP](https://docs.brightdata.com)** | Proxy/scraping | Already using | Direct integration |
| **[Brave Search](https://github.com/AmineDjeworksmiths/brave-search-mcp)** | Web search | Free tier | Alternative to Exa |
| **[Tavily](https://github.com/tavily-ai/tavily-mcp)** | Research search | Paid | Alternative to Exa |

#### 7.2 Evaluation Criteria

During implementation, evaluate each MCP against:

```yaml
# Evaluation template for each MCP
evaluation:
  capability_gap:
    question: "Does this fill a gap not covered by existing tools?"
    weight: 30%

  overlap_analysis:
    question: "How much does this overlap with Brightdata/Firecrawl?"
    weight: 20%
    considerations:
      - Can existing tool do this already?
      - Is MCP interface better than current integration?
      - Cost comparison

  agent_value:
    question: "Which agents benefit and how much?"
    weight: 25%

  cost_benefit:
    question: "Is the cost justified by productivity gain?"
    weight: 15%

  maintenance:
    question: "What's the maintenance burden?"
    weight: 10%
```

#### 7.3 Preliminary Recommendations

**Tier 1: Add Immediately (High Confidence)**

| MCP | Rationale | No Overlap |
|-----|-----------|------------|
| **Context7** | Free, unique capability (versioned docs), no existing equivalent | ✅ |
| **GitHub MCP** | Free, native API better than CLI parsing, enables agent autonomy | ✅ |

**Tier 2: Evaluate During Implementation**

| MCP | Evaluation Needed |
|-----|-------------------|
| **Exa** | Compare code search quality vs Brightdata. Is $49/mo justified? |
| **Firecrawl MCP** | Already using Firecrawl - is MCP interface better than current? |
| **Brightdata MCP** | Already using Brightdata - is MCP interface better than current? |

**Tier 3: Consider as Alternatives**

| MCP | When to Consider |
|-----|------------------|
| **Brave Search** | If Exa too expensive and need free alternative |
| **Tavily** | If doing heavy academic/research work |
| **DuckDuckGo** | Fallback for simple searches |

#### 7.4 Proposed MCP Configuration

```json
{
  "mcpServers": {
    "augur": {
      "comment": "Internal Augur MCP - chains, agents, context",
      "command": "<PYTHON_PATH>",
      "args": ["-m", "src/lib.mcp"],
      "cwd": "<REPO_ROOT>",
      "env": {
        "AUGUR_DATA_DIR": "<DATA_DIR>",
        "PYTHONPATH": "<REPO_ROOT>:<REPO_ROOT>/src/mcp"
      }
    },
    "context7": {
      "comment": "Up-to-date library documentation (FREE)",
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"]
    },
    "github": {
      "comment": "GitHub API for issues, PRs, repos (FREE with PAT)",
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN", "ghcr.io/github/github-mcp-server"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "<YOUR_PAT>"
      }
    },
    "exa": {
      "comment": "AI code search (EVALUATE: $49/mo vs Brightdata)",
      "command": "npx",
      "args": ["-y", "exa-mcp-server"],
      "env": {
        "EXA_API_KEY": "<YOUR_EXA_KEY>"
      },
      "enabled": false
    },
    "firecrawl": {
      "comment": "EVALUATE: MCP vs current integration",
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": {
        "FIRECRAWL_API_KEY": "<EXISTING_KEY>"
      },
      "enabled": false
    },
    "brightdata": {
      "comment": "EVALUATE: MCP vs current integration",
      "enabled": false
    }
  }
}
```

#### 7.5 Agent-MCP Routing

Define which agents should use which external MCPs:

| Agent | Internal (exo) | Context7 | GitHub | Exa | Firecrawl |
|-------|----------------|----------|--------|-----|-----------|
| **architect** | chains, context | library docs | repo analysis | code search | - |
| **developer** | chains, context | library docs | PR creation | - | - |
| **researcher** | chains | - | - | deep search | web scrape |
| **security** | chains | - | security advisories | CVE search | - |
| **executor** | chains, backlog | - | issue mgmt | - | - |
| **data-scientist** | chains | - | - | research | data scrape |

#### 7.6 Implementation Approach

```
Phase 7 Execution:

Step 1: Immediate Additions (No Evaluation Needed)
├── Add Context7 to mcp_config.template.json
├── Add GitHub MCP to mcp_config.template.json
├── Test with architect and developer agents
└── Document in agent-rules.md

Step 2: Evaluation Sprint
├── Set up Exa trial account
├── Compare Exa vs Brightdata for code search tasks
├── Compare Firecrawl MCP vs current Firecrawl integration
├── Compare Brightdata MCP vs current Brightdata integration
├── Document findings with cost/benefit analysis
└── Make go/no-go decision for each

Step 3: Integration
├── Add approved MCPs to config
├── Update agent routing to use new MCPs
├── Add MCP health monitoring to dashboard
└── Document MCP limits in context window guidelines
```

## Implementation Checklist

### Phase 0 (FIRST) - Factory Agent Deep Review & Hardening
- [ ] 0.1 P0 Agents (Core Factory)
  - [ ] **architect** - ✅ Reviewed, apply hardening
    - [ ] Add tiering (low/medium/high)
    - [ ] Add read-only mode enforcement
    - [ ] Add iron law verification
    - [ ] Add circuit breaker
  - [ ] **developer** - Review against refactor-cleaner.md
    - [ ] Fetch reference agent
    - [ ] Compare and score
    - [ ] Apply hardening patterns
    - [ ] Verify second brain alignment
  - [ ] **validator** - Review against e2e-runner.md
    - [ ] Fetch reference agent
    - [ ] Compare and score
    - [ ] Apply hardening patterns
    - [ ] Verify second brain alignment
  - [ ] **security** - Review against security-reviewer.md
    - [ ] Fetch reference agent
    - [ ] Compare and score
    - [ ] Apply hardening patterns
    - [ ] Verify second brain alignment
- [ ] 0.2 P1 Agents (Support Factory)
  - [ ] **executor** - Review against planner.md
  - [ ] **librarian** - Review against doc-updater.md
  - [ ] **frontend** - Review (no reference, self-harden)
  - [ ] **webapp-testing** - Review against e2e-runner.md
- [ ] 0.3 P2 Agents (Extended Factory)
  - [ ] **devops** - Self-harden
  - [ ] **data-engineer** - Self-harden
  - [ ] **structure-enforcer** - Review against refactor-cleaner.md
  - [ ] **user-advocate** - Self-harden
  - [ ] **vision-keeper** - Self-harden
- [ ] 0.4 P3 Agents (Specialized)
  - [ ] **experiment-tracker** - Self-harden
  - [ ] **oss-manager** - Self-harden
  - [ ] **control** - Self-harden
  - [ ] **organizations** - Self-harden
- [ ] 0.5 New Agents to Create
  - [ ] **build-error-resolver** - Create from reference
  - [ ] **tdd-guide** - Create from reference
  - [ ] **code-reviewer** - Create from reference (or enhance validator)
- [ ] 0.6 Second Brain Alignment Audit
  - [ ] Verify all agents output plain text (YAML/MD)
  - [ ] Verify all agents work offline
  - [ ] Verify human gates defined
  - [ ] Verify Unix composability
  - [ ] Document alignment scores

### Phase 1 (High Priority) - From everything-claude-code
- [ ] 1.1 Hooks System
  - [ ] Create `hooks.yaml` schema
  - [ ] Implement `hook_runner.py`
  - [ ] Add pre-commit hooks
  - [ ] Add post-chain hooks
  - [ ] Document in agent-rules.md
- [ ] 1.2 Checkpoint Command
  - [ ] Create workflow definition
  - [ ] Implement `checkpoint_manager.py`
  - [ ] Add runtime checkpoint registry
  - [ ] Test checkpoint/restore cycle
- [ ] 1.3 Verification Loop
  - [ ] Define reusable pattern YAML
  - [ ] Implement `verification_runner.py`
  - [ ] Update `feature_development.yaml`
  - [ ] Update `bug_workflow.yaml`
  - [ ] Update other applicable chains

### Phase 2 (Medium Priority) - From everything-claude-code
- [ ] 2.1 Context Window Guidelines
  - [ ] Add documentation section
  - [ ] Create health check script
  - [ ] Add limit comments to configs
- [ ] 2.2 Eval Harness Skill
  - [ ] Create skill structure
  - [ ] Implement core scripts
  - [ ] Create test case templates
  - [ ] Add sample test cases
- [ ] 2.3 Build Error Resolver Agent
  - [ ] Define agent YAML
  - [ ] Integrate into chains
  - [ ] Test with sample failures

### Phase 3 (Low Priority) - From everything-claude-code
- [ ] 3.1 Strategic Compact
  - [ ] Create workflow definition
  - [ ] Implement compressor script
  - [ ] Test with long session

### Phase 4 (Critical) - From oh-my-claudecode Orchestration
- [ ] 4.1 Parallel Step Execution (Ultrapilot)
  - [ ] Design parallel schema extension
  - [ ] Implement `parallel_executor.py`
  - [ ] Add file ownership tracking
  - [ ] Create integration/merge phase
  - [ ] Test with feature_development chain
- [ ] 4.2 Ecomode (Model Tier Routing)
  - [ ] Create `model_tiers.yaml` config
  - [ ] Implement `tier_router.py`
  - [ ] Add complexity detection
  - [ ] Integrate into agent_router.py
  - [ ] Measure token savings
- [ ] 4.3 Swarm Execution Mode
  - [ ] Implement `swarm_executor.py`
  - [ ] Create `task_pool.py` with atomic claiming
  - [ ] Add timeout and release logic
  - [ ] Test with bulk refactoring task
- [ ] 4.4 Ralph Persistence Pattern
  - [ ] Define `_ralph_verification.yaml`
  - [ ] Add iron law checks to verification_runner
  - [ ] Implement circuit breaker
  - [ ] Add architect approval gate
- [ ] 4.5 Graceful Cancellation
  - [ ] Create `/cancel` workflow
  - [ ] Implement `cancel_manager.py`
  - [ ] Add abort flag checking to executors
  - [ ] Test cancellation mid-chain
- [ ] 4.6 Progress HUD
  - [ ] Design HUD component
  - [ ] Create HUD API endpoint
  - [ ] Add real-time updates
  - [ ] Display in dashboard

### Phase 5 (High Priority) - Agent Tiering
- [ ] 5.1 Tiered Agent Schema
  - [ ] Define tier schema in SKILL.md format
  - [ ] Document tier use cases
  - [ ] Define escalation triggers
- [ ] 5.2 Implement Tiered Agents
  - [ ] Update architect SKILL.md with tiers
  - [ ] Update developer SKILL.md with tiers
  - [ ] Update validator SKILL.md with tiers
  - [ ] Update security SKILL.md with tiers
- [ ] 5.3 Automatic Tier Selection
  - [ ] Implement `agent_tier_selector.py`
  - [ ] Add complexity detection heuristics
  - [ ] Integrate into agent_router.py
- [ ] 5.4 Read-Only Mode Enforcement
  - [ ] Add mode flag to agent execution
  - [ ] Block write tools in advisory mode
  - [ ] Add override for explicit implementation requests

### Phase 6 (Strategic) - Open Source & Package Extraction
- [ ] 6.1 Extract Orchestrator as Standalone Plugin
  - [ ] Audit components for extraction
  - [ ] Create `augur-orchestrator` repo
  - [ ] Extract agent definitions (with tiers)
  - [ ] Extract chain executor and schema
  - [ ] Extract parallel/swarm executors
  - [ ] Remove augur-specific dependencies
  - [ ] Write comprehensive documentation
  - [ ] Create example chains for common workflows
  - [ ] Publish to npm
  - [ ] Create GitHub releases
- [ ] 6.2 MCP Logic Decision & Extraction
  - [ ] **DECISION REQUIRED**: Open Source vs Proprietary vs Open Core
  - [ ] If Open Core: Define core vs pro boundary
  - [ ] Create `augur-mcp-core` package (if applicable)
  - [ ] Remove proprietary dependencies from core
  - [ ] Write API documentation
  - [ ] Create example implementations
  - [ ] Publish to PyPI (if applicable)
- [ ] 6.3 Community & Upstream
  - [ ] Create announcement blog post
  - [ ] Submit to plugin directories
  - [ ] Evaluate contribution to oh-my-claudecode
  - [ ] Set up issue triage process
  - [ ] Monitor adoption metrics

### Phase 7 (Medium Priority) - External MCP Integration
- [ ] 7.1 Immediate Additions (No Evaluation Needed)
  - [ ] Add Context7 MCP to config (FREE - library docs)
  - [ ] Add GitHub MCP to config (FREE - native API)
  - [ ] Test with architect and developer agents
  - [ ] Document in agent-rules.md
- [ ] 7.2 Evaluation Sprint
  - [ ] **EVALUATE**: Exa vs Brightdata for code search
    - [ ] Set up Exa trial account
    - [ ] Run comparison tests
    - [ ] Document cost/benefit analysis
    - [ ] Make go/no-go decision
  - [ ] **EVALUATE**: Firecrawl MCP vs current integration
    - [ ] Compare MCP interface vs current usage
    - [ ] Document findings
    - [ ] Make go/no-go decision
  - [ ] **EVALUATE**: Brightdata MCP vs current integration
    - [ ] Compare MCP interface vs current usage
    - [ ] Document findings
    - [ ] Make go/no-go decision
- [ ] 7.3 Integration
  - [ ] Add approved MCPs to mcp_config.template.json
  - [ ] Update agent-MCP routing table
  - [ ] Add MCP health monitoring to dashboard
  - [ ] Update context window guidelines with MCP limits

## Consequences

### Positive

- **Automation**: Hooks system enables trigger-based workflows without manual intervention
- **Safety**: Checkpoints provide safe rollback points for experimentation
- **Quality**: Verification loops ensure code changes meet quality standards before proceeding
- **Visibility**: Context limits prevent silent failures from context exhaustion
- **Testing**: Eval harness enables systematic prompt/agent quality testing
- **Specialization**: Build error resolver improves fix accuracy and speed
- **Performance**: Parallel execution (Ultrapilot) provides 3-5x speedup for decomposable tasks
- **Scalability**: Swarm mode enables horizontal scaling for bulk operations
- **Cost Efficiency**: Ecomode tier routing saves 30-50% on token usage
- **Reliability**: Ralph pattern ensures no premature completion claims
- **Flexibility**: Agent tiering routes simple queries to cheap models, complex to capable ones
- **Community**: Open source plugins enable community contributions and faster bug discovery
- **Positioning**: Publishing establishes augur as reference implementation for Claude Code orchestration
- **Reach**: Standalone plugin can benefit users who don't need full augur
- **Documentation**: Context7 ensures agents use accurate, version-specific library docs
- **GitHub Native**: GitHub MCP enables autonomous issue/PR management without CLI parsing
- **Search Quality**: Exa provides code-aware search superior to generic web search (if adopted)

### Negative

- **Complexity**: Additional systems to maintain (parallel executor, swarm, tier router)
- **Learning Curve**: Team must learn new patterns and execution modes
- **Overhead**: Verification loops and Ralph checks add time to chain execution
- **Coordination**: Parallel execution requires careful file ownership management
- **Competitive Risk**: Open sourcing reduces proprietary advantage (mitigated by Open Core model)
- **Support Burden**: Community plugins require issue triage and PR review
- **Fragmentation Risk**: Standalone plugin may diverge from main augur

### Neutral

- Existing architecture remains unchanged; these are additive improvements
- Multi-IDE distribution continues to work as before
- MCP gateway architecture preserved
- Sequential execution remains the default; parallel is opt-in
- Open source decision is reversible (can always close-source future features)

## Alternatives Considered

### Alternative 1: Adopt Everything Wholesale

Copy all patterns from everything-claude-code directly.

**Rejected because**:
- Augur has stronger architecture in several areas
- Would lose MCP gateway, mode system, plugin mounting benefits
- Better to selectively adopt missing patterns

### Alternative 2: Build Custom Solutions

Design all improvements from scratch without reference.

**Rejected because**:
- Competition winner patterns are battle-tested
- Reinventing would take longer
- Community familiarity with established patterns

### Alternative 3: Defer All Improvements

Keep current system without changes.

**Rejected because**:
- Identified gaps are real productivity losses
- Hooks and verification loops are industry best practices
- Competitive disadvantage without these capabilities

## References

### External Repositories Analyzed
- [everything-claude-code](https://github.com/affaan-m/everything-claude-code) - Competition winner (hooks, checkpoints, verification)
- [oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) - 2.2k stars (parallel execution, swarm, ecomode, agent tiering)
- [superpowers](https://github.com/obra/superpowers) - 35.9k stars (TDD enforcement, subagent workflows, seven-stage development cycle, bite-sized task planning)

### External MCP Servers (Phase 7)
- [Context7](https://github.com/upstash/context7) - Free library documentation MCP
- [Exa](https://github.com/exa-labs/exa-mcp-server) - AI-powered code search ($49-449/mo)
- [GitHub MCP](https://github.com/github/github-mcp-server) - Native GitHub API integration
- [Firecrawl MCP](https://docs.firecrawl.dev) - Web scraping (evaluate vs current integration)
- [Brave Search MCP](https://github.com/AmineDjeworksmiths/brave-search-mcp) - Free web search alternative
- [Tavily MCP](https://github.com/tavily-ai/tavily-mcp) - Research-optimized search

### Existing Tools to Evaluate Against
- **Brightdata** - Current web scraping/proxy solution
- **Firecrawl** - Current web scraping solution

### Internal ADRs
- [ADR-005](./ADR-005-mcp-execution-gateway.md) - MCP Execution Gateway
- [ADR-007](./ADR-007-chain-orchestration.md) - Chain Orchestration
- [ADR-011](./ADR-011-app-mode.md) - App Mode System

### Key Implementation Files
- `plugins/orchestration/skills/executor/scripts/agent_orchestrator.py` - Current orchestrator
- `data/core/ide-integration/chains/` - Chain definitions
- `src/llm/agent_router.py` - Agent routing
- `docs/agent-rules.md` - Current agent instructions
- `config-data/mcp_tool_groups.yaml` - Current tool group limits

### Comparison Scores

| Agent | Augur Score | OMC Score | Winner |
|-------|-----------------|-----------|--------|
| Architect | 7.85/10 | 6.75/10 | Augur |

*Note: Augur wins on depth/output quality; OMC wins on token efficiency. Hybrid approach recommended.*
