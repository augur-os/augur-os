---
status: Implemented
date: '2026-03-07'
deciders:
- User
- Claude
related: []
hub: null
tags:
- adaptive
- loop
- effectiveness
- overhaul
superseded_by: null
---

# ADR-405: Adaptive Loop Effectiveness Overhaul

**Related ADRs**: ADR-176 (Adaptive Loop Engine), ADR-200 (Auto-Command Protocol), ADR-256 (Heal Command)

## Context

The adaptive loop engine (ADR-176) runs 8 loops with 49 auto-commands across nightly, continuous, and post-execution triggers. After 9 nightly cycles, the system has fundamental effectiveness problems that destroy user trust:

### Problem 1: Loops report "all clean" on a dirty codebase

Most auto-commands' `scan()` returns empty issues. The engine treats this as a "clean scan" and awards trust credit. But empty scan ≠ healthy — it means the scanner is too shallow, broken, or not using difficulty to go deeper.

Evidence: 25 of 49 categories have 0.0 trust after 9 cycles. They scan, find nothing, get tiny clean-scan credit (0.02), hit saturation after 3 clean scans, and stall permanently. The project is early-stage with hundreds of real issues — the scanners aren't looking.

### Problem 2: Scan exceptions are silent

When `scan()` throws an exception (e.g., `No such file: 'python'`, `'str' has no attribute 'get'`), the engine logs it as a failure but the overall loop cycle reports success. The scan error is buried in journal entries. Four auto-commands ran broken for 7+ nightly cycles before a human manually investigated. The loops never self-healed their own scanners.

### Problem 3: Trust numbers are opaque

Trust values like `0.114157619136` are meaningless to users. There's no way to see what changed after a run. The user can't tell if loops are improving or stagnant without reading raw JSON.

### Problem 4: Difficulty is decorative

The engine tracks difficulty (0-4) and passes it via `ctx.difficulty`, but almost no auto-command uses it. All commands scan at the same depth regardless of difficulty level. There's no contract requiring commands to scan deeper at higher difficulty.

### Problem 5: Clean scan credit creates false progress

`CLEAN_SCAN_TRUST_INCREMENT = 0.02` awards trust for finding nothing. After 3 clean scans, credit saturates — but the damage is done: a broken scanner that always returns empty gets 0.06 trust for free. Combined with the fact that `scan()` exceptions return to the `continue` path (line 361), a scanner that crashes gets a failure record but the loop still shows "success" overall.

### Problem 6: No parallel execution

All loops run sequentially in a single process writing to a shared `trust_state.json`. Running 8 loops takes ~150s. Parallel execution requires file locking or process-level isolation (worktrees), neither of which exists.

## Decision

### 1. Scan Health Contract

Every `scan()` must return a `ScanResult` with a new `health` field indicating scanner confidence:

```python
@dataclass
class ScanResult:
    issues: list[dict] = field(default_factory=list)
    summary: str = ""
    severity: Severity = "info"
    health: ScanHealth = "verified"  # NEW

ScanHealth = Literal["verified", "degraded", "broken"]
```

- `verified` — Scanner ran to completion, checked all expected targets
- `degraded` — Scanner ran but couldn't check everything (e.g., dashboard not running)
- `broken` — Scanner encountered errors that prevent meaningful results

**Engine behavior change**:
- `health="broken"` → treat as failure, record `record_failure()`, do NOT award clean-scan credit
- `health="degraded"` → do NOT award clean-scan credit, log warning
- `health="verified"` with empty issues at difficulty 0 → accept as baseline clean, escalate difficulty to 1, do NOT award trust credit (shallow scan proves nothing)
- `health="verified"` with empty issues at difficulty > 0 → genuine clean scan, award credit
- `scan()` exception → `health="broken"` automatically (no code change needed — already records failure)

**Files**: `src/lib/ops_protocol.py` (ScanResult), `plugins/observability/skills/daemon/scripts/adaptive/engine.py` (run_auto_cycle lines 363-366)

### 2. Difficulty-Aware Scanning Contract

Each auto-command MUST define what it scans at each difficulty level. Add `DIFFICULTY_SPEC` to the protocol:

```python
# In each auto-command module:
DIFFICULTY_SPEC = {
    0: "Surface check — file existence, basic structure",
    1: "Content check — validate file contents, find obvious issues",
    2: "Deep check — cross-reference, find inconsistencies",
    3: "Exhaustive — check every file, validate every reference",
    4: "Expert — suggest improvements, find subtle issues",
}
```

Engine changes:
- `scan()` returning empty at difficulty 0 → no credit, escalate difficulty to 1 (consistent with Decision 1)
- `scan()` returning empty at difficulty > 0 with `health="verified"` → award clean-scan credit
- `scan()` returning empty at difficulty > 0 without `health="verified"` → no credit, log warning
- Log difficulty level in journal entries

**Enforcement**: The engine validates `DIFFICULTY_SPEC` at registration time. Auto-commands without `DIFFICULTY_SPEC` are logged as warnings and treated as difficulty-0-only (never escalated, never earn credit beyond baseline). This makes the spec effectively required for any command that wants trust progression.

**Files**: `src/lib/ops_protocol.py` (DIFFICULTY_SPEC type), all `plugins/*/skills/*/scripts/ops/*.py` (add spec), engine.py (difficulty-gated credit)

### 3. Human-Readable Trust Display

Replace raw float trust with percentage display and deltas:

```
auto-lint: 4% → 8% (+4%)  difficulty 1→2  [fixed 3 files]
auto-format: 12% → 12% (=)  difficulty 2  [clean scan]
auto-test-pytest: 0% → 0% (BROKEN)  [No such file: 'python']
```

Trust display rules:
- Map trust float (0.0-1.0) to percentage: `int(trust * 100)` — e.g., 0.114 → 11%, 0.8 → 80%, 1.0 → 100%
- Show as integer percentage (0-100%)
- Show delta after every run: `→ N% (+M%)` or `(=)` or `(-M%)`
- Show difficulty level and change
- Show action summary: files fixed, clean scan, or error excerpt
- `run_auto_cycle()` returns a `CycleReport` with before/after snapshots for display

**Files**: engine.py (CycleReport dataclass, snapshot before/after), SKILL.md (display format)

### 4. Scan Self-Test on First Run

When an auto-command runs for the first time (or after heal reset), the engine runs a **self-test**:

1. Call `scan(ctx)` with difficulty=0
2. If `scan()` throws → mark as `broken`, do not schedule future runs until healed
3. If `scan()` returns empty with `health="verified"` → accept as clean
4. If `scan()` returns empty with no health field → log warning "scanner may be shallow"

This prevents broken scanners from silently running for weeks.

**Files**: engine.py (run_auto_cycle, add self-test on cycle_count==0 or after reset)

### 5. Parallel Loop Execution with Git Worktrees

Each loop runs in its own **git worktree** via a **Claude Code subagent**, providing full filesystem isolation:

#### Architecture

```
/ops-loops run --all
  │
  ├─ Agent 1 (worktree: .worktrees/loop-code-quality)
  │    └─ engine.run_auto_cycle('code-quality')
  │         └─ scan → fix → commit in worktree
  │
  ├─ Agent 2 (worktree: .worktrees/loop-testing)
  │    └─ engine.run_auto_cycle('testing')
  │         └─ scan → fix → commit in worktree
  │
  ├─ Agent 3 (worktree: .worktrees/loop-hardening)
  │    ...
  │
  └─ Main thread: collect results, merge worktrees, update trust state
```

#### Worktree runtime/ bootstrap

Git worktrees don't include `runtime/` (gitignored). Before dispatching a subagent, the main thread:

1. Creates the worktree via `git worktree add`
2. Copies `runtime/adaptive/` into the worktree (trust_state.json, journal.jsonl)
3. Creates `runtime/adaptive/reports/` directory
4. Dispatches the subagent with the worktree path

After completion, main thread reads back the worktree's `runtime/adaptive/trust_state.json` for merge.

#### Why git worktrees (not ThreadPoolExecutor)

- **File safety**: Loops that commit (auto-format, auto-lint, auto-mcp-hygiene) modify overlapping files. Without worktrees, parallel commits corrupt the working tree.
- **Trust state**: Each worktree gets a bootstrapped `runtime/adaptive/` copy. Main thread merges results after all agents complete — no file locking needed.
- **Claude Code native**: The Agent tool's `isolation: "worktree"` parameter creates worktrees automatically. No custom infrastructure.
- **Long-running safe**: Subagents handle their own timeouts (up to 10 minutes). No Bash 2-minute timeout issue.

#### Daemon vs CLI usage

**CLI** (`/ops-loops run --all`): Uses worktree-per-loop architecture described above. The user's interactive session dispatches subagents.

**Daemon** (nightly 3 AM): Runs sequentially in a single process — the daemon is already a background process with no interactive session. Worktree overhead is unnecessary for unattended nightly runs. The daemon uses `fcntl.flock` on `trust_state.json` for basic safety.

#### Claude Code Teams Integration

For `/ops-loops run --all`, the skill uses **Claude Code teams** with one subagent per loop:

```python
# Pseudocode for the skill execution — Agent-only pattern (no TaskCreate)
agents = []
for loop_name in enabled_loops:
    # Bootstrap worktree with runtime/adaptive/ copy
    wt_path = create_loop_worktree(loop_name)
    copy_runtime_adaptive(project_root, wt_path)

    agent = Agent(
        prompt=LOOP_AGENT_PROMPT.format(loop_name=loop_name),
        isolation="worktree",
        run_in_background=True,
    )
    agents.append((loop_name, agent, wt_path))

# Wait for all agents to complete
# Read each worktree's runtime/adaptive/trust_state.json
# Merge trust state: for each loop, take state from the agent that ran it
# Merge commits: git merge --ff-only each worktree branch to main
# Cleanup worktrees
```

#### Trust state merge

After all agents complete, main thread:
1. Read each worktree's `runtime/adaptive/trust_state.json`
2. For each loop: copy the full loop state from the agent that ran it (no conflicts — each agent runs exactly one loop)
3. Write merged state to main `runtime/adaptive/trust_state.json`
4. For worktrees with commits: `git merge --ff-only` each branch

#### Subagent contract

Each subagent receives:
- Loop name to run
- Exact Python script (from SKILL.md) — no API guessing
- Bash timeout set to 300s (5 minutes) — enough for ESLint + build
- Expected output format: JSON with `{loop, categories: [{name, status, trust_before, trust_after, difficulty, action_summary}]}`

Each subagent returns:
- `CycleReport` JSON (structured, parseable)
- Worktree path and branch name (if commits were made)
- Error details if any category failed

#### Fallback

If worktree creation fails (e.g., dirty state, no git), fall back to sequential execution with `fcntl.flock` on `trust_state.json` for basic file-level locking.

**Files**: engine.py (parallel executor, trust merge), trust_ledger.py (flock fallback), SKILL.md (agent dispatch), adaptive_loops.yaml (parallel config)

### 6. Cycle Summary Report

After every `run --all`, generate a human-readable summary:

```
Adaptive Loop Cycle — 2026-03-07 14:52
═══════════════════════════════════════

8 loops | 16 categories ran | 15 ok | 1 broken | 112.5s

code-quality (5 ran, 71.8s)
  auto-format    12% → 15% (+3%)  d1→2  fixed 2 files
  auto-lint       4% →  8% (+4%)  d0→1  fixed 3 files; 1 AI fix skipped
  auto-mcp-hyg   10% → 12% (+2%)  d1    26 hygiene reports
  auto-coverage  10% → 12% (+2%)  d1    coverage report updated
  auto-code-rev  10% → 12% (+2%)  d1    clean review

testing (5 ran, 40.8s)
  auto-test-build   10% → 12%  d0→1  build passed
  auto-test-pytest   0% →  0%  BROKEN  exit code 2 (5 failures)
  ...

command-evolution (0 ran)
  auto-command-evolution  0%  STAGNANT  no execution logs in pipeline

Health: 1 broken, 1 stagnant, 25 waiting (tier-gated)
Next nightly: 2026-03-08 03:00
```

**Files**: engine.py (generate_cycle_report), SKILL.md (display format)

## Consequences

### Positive

- **User trust**: Clear percentage-based feedback with deltas shows whether loops are improving
- **Scanner accountability**: Broken scanners are immediately visible, not hidden behind "clean scan"
- **Meaningful depth**: Difficulty-aware scanning means loops actually find more issues over time
- **Faster execution**: Parallel loops cut wall-clock time proportional to loop count
- **Self-healing**: First-run self-test catches broken scanners before they waste cycles

### Negative

- **Breaking change**: 10 highest-value auto-commands get full difficulty-aware scanning in Phase 2. Remaining 39 auto-commands work unchanged — they just won't earn trust credit beyond baseline until they add `DIFFICULTY_SPEC` (opt-in, not blocking)
- **Migration effort**: The 10 priority scanners need refactoring to use difficulty levels
- **Complexity**: Parallel execution with worktrees adds merge complexity
- **Trust reset**: Changing clean-scan credit rules may reset some trust progress

### Neutral

- Trust state format changes are backward-compatible (new fields with defaults)
- Journal format unchanged (difficulty already logged)

## Acceptance Criteria

All of the following must pass before this ADR is marked Implemented:

1. **No false clean scans**: A scanner returning empty issues at difficulty 0 gets zero trust credit
2. **Broken scanners visible**: Any `scan()` that throws an exception is immediately shown as `BROKEN` in the cycle report — not hidden behind "success"
3. **Trust is readable**: `/ops-loops status` and `/ops-loops run` show trust as `N%` with deltas (`+M%`), not raw floats
4. **Difficulty drives depth**: At least 10 auto-commands have `DIFFICULTY_SPEC` and demonstrably scan deeper at higher difficulty (unit tests prove different behavior at d0 vs d2)
5. **Parallel run works**: `/ops-loops run --all` dispatches subagents in parallel with worktree isolation; wall-clock time is less than sequential time
6. **Trust state survives**: Parallel execution merges trust state correctly — no category state is lost or overwritten
7. **Self-test catches broken**: A new auto-command with a broken `scan()` is caught on first run, not after 7 cycles
8. **Existing tests green**: All existing `test_adaptive_engine.py` tests pass without modification

## Concrete Example: auto-lint at Each Difficulty Level

To illustrate what difficulty-aware scanning looks like in practice:

```python
# plugins/dev/skills/devops/scripts/ops/lint.py
DIFFICULTY_SPEC = {
    0: "Check if eslint is available and dashboard dir exists",
    1: "Run eslint --quiet, report fixable count only",
    2: "Run eslint, report per-file errors, attempt auto-fix",
    3: "Run eslint + tsc --noEmit, cross-reference type errors with lint errors",
    4: "Full audit: eslint + tsc + unused exports + import cycle detection",
}

def scan(ctx: OpsContext) -> ScanResult:
    if ctx.difficulty == 0:
        # Just verify eslint is runnable
        ...
        return ScanResult(issues=[], summary="eslint available", health="verified")
    elif ctx.difficulty == 1:
        # Run eslint, count fixable issues
        ...
    elif ctx.difficulty >= 2:
        # Full scan with per-file error reporting
        ...
    # difficulty 3+: add tsc, deeper checks
```

Each level does strictly more work than the previous. This is the contract that `DIFFICULTY_SPEC` documents and tests verify.

## Implementation Order

### Phase 1: Trust Display + Scan Health (no breaking changes)

1. Add `ScanHealth` type and `health` field to `ScanResult` (default `"verified"` for backward compat)
2. Add `CycleReport` dataclass with before/after trust snapshots
3. Update `run_auto_cycle()` to: check health, gate clean-scan credit on difficulty > 0, return CycleReport
4. Update `format_cycle_report()` for human-readable output
5. Update `/ops-loops run` display to show percentages and deltas
6. Tests for all new behavior

### Phase 2: Difficulty Contract + Scanner Upgrades

7. Add `DIFFICULTY_SPEC` to `OpsCommand` protocol
8. Update 10 highest-value auto-commands to implement difficulty-aware scanning:
   - auto-lint, auto-format, auto-test-pytest, auto-test-build, auto-test-dashboard
   - auto-page-mounts, auto-yaml-lint, auto-mcp-hygiene, auto-rag-reindex, auto-doc-freshness
9. Add first-run self-test to engine
10. Tests for difficulty escalation behavior

### Phase 3: Parallel Execution with Worktrees + Subagents

11. Add worktree lifecycle helpers: `create_loop_worktree(loop_name)`, `merge_loop_worktree(loop_name)`, `cleanup_worktrees()`
12. Add trust state merge: `merge_trust_states(main_state, worktree_states) -> merged_state`
13. Add `fcntl.flock` fallback wrapper to TrustLedger.save/load (for sequential fallback)
14. Update `/ops-loops run --all` in SKILL.md: dispatch one Agent per loop with `isolation: "worktree"` and `run_in_background: true`, collect results via TaskOutput, merge trust + commits
15. Add subagent contract: exact Python script, JSON output format, 300s Bash timeout
16. Performance and correctness tests: parallel trust merge, worktree commit merge, fallback to sequential

## Alternatives Considered

### A: Keep current system, just fix individual scanners

Rejected. The problem is architectural — fixing individual scanners doesn't address the fundamental issue that empty scans award credit and difficulty is unused. We'd be playing whack-a-mole forever.

### B: Replace trust system with simple pass/fail

Rejected. The graduated trust system is sound in principle — the problem is the inputs (scan results) are unreliable, not the trust math. Fixing inputs while keeping trust gives us both accountability and progressive automation.

### C: Run loops as external CI jobs

Rejected. Loops need access to the local runtime environment, trust state, and project context. CI-based execution would lose the "second brain" integration that makes loops useful.

### D: Consolidate to fewer, deeper scanners

Considered. Instead of 49 shallow auto-commands, reduce to ~15 deep scanners that each cover a wider domain. Trade-off: fewer scanners means each is more complex and harder to maintain. The current decentralized model (each plugin owns its scanner) aligns with the plugin-first architecture (Rule #1). Instead of consolidating, we make existing scanners deeper via difficulty levels — same architecture, better depth.

## References

- ADR-176: Adaptive Loop Engine (original design)
- ADR-200: Auto-Command Protocol (scan/fix interface)
- ADR-256: Heal Command (detection of broken loops)
- `plugins/observability/skills/daemon/scripts/adaptive/engine.py` — main engine
- `plugins/observability/skills/daemon/scripts/adaptive/trust_ledger.py` — trust state
- `src/lib/ops_protocol.py` — OpsCommand protocol

## Impact Manifest

```yaml
apis_changed:
  - src/lib/ops_protocol.py:ScanResult  # new health field
  - src/lib/ops_protocol.py:OpsCommand  # new DIFFICULTY_SPEC
  - engine.py:run_auto_cycle  # returns CycleReport, health gating
  - engine.py:generate_cycle_report  # new method
  - engine.py:run_parallel_cycle  # new method, worktree dispatch
  - trust_ledger.py:save  # file locking added
  - trust_ledger.py:merge_states  # new method for worktree result merge

patterns_deprecated:
  - "Clean scan credit at difficulty 0"  # no longer awards trust
  - "scan() returning empty treated as success"  # now checked against health
  - "Sequential run --all in single process"  # replaced by worktree-per-loop subagents

files_affected:
  - src/lib/ops_protocol.py
  - plugins/observability/skills/daemon/scripts/adaptive/engine.py
  - plugins/observability/skills/daemon/scripts/adaptive/trust_ledger.py
  - plugins/observability/skills/daemon/scripts/adaptive/worktree_utils.py  # NEW
  - plugins/observability/skills/ops-loops/SKILL.md
  - 10 priority auto-command modules (Phase 2), remaining 39 opt-in later
```

## Implementation Prompt

### Team: adr-257-loop-effectiveness

| Phase | Step | Task | Files | Dependencies | Agent Tier |
|-------|------|------|-------|-------------|------------|
| 1 | 1.1 | Add ScanHealth type and health field to ScanResult | ops_protocol.py | — | medium |
| 1 | 1.2 | Add CycleReport dataclass | engine.py | — | medium |
| 1 | 1.3 | Update run_auto_cycle: health gating, difficulty-gated credit, return CycleReport | engine.py | 1.1, 1.2 | high |
| 1 | 1.4 | Add format_cycle_report() with % trust and deltas | engine.py | 1.2 | medium |
| 1 | 1.5 | Update SKILL.md run section with new display format | SKILL.md | 1.4 | low |
| 1 | 1.6 | Tests: health gating, credit rules, CycleReport | test_adaptive_engine.py | 1.3 | high |
| 2 | 2.1 | Add DIFFICULTY_SPEC to OpsCommand protocol | ops_protocol.py | 1.1 | medium |
| 2 | 2.2 | Upgrade 5 code-quality scanners with difficulty levels | lint.py, format.py, markers.py, logs.py, mcp_hygiene.py | 2.1 | PARALLEL, high |
| 2 | 2.3 | Upgrade 5 testing/hardening scanners with difficulty levels | test_pytest_ops.py, test_build_ops.py, test_pages_ops.py, yaml_lint.py, page_mounts.py | 2.1 | PARALLEL, high |
| 2 | 2.4 | Add first-run self-test to engine | engine.py | 2.1 | medium |
| 2 | 2.5 | Tests: difficulty escalation, self-test, DIFFICULTY_SPEC validation | test_adaptive_engine.py | 2.2, 2.3, 2.4 | high |
| 3 | 3.1 | Add worktree lifecycle helpers (create, merge, cleanup) | engine.py, new worktree_utils.py | — | high |
| 3 | 3.2 | Add trust state merge logic | trust_ledger.py | — | medium |
| 3 | 3.3 | Add fcntl.flock fallback to TrustLedger.save/load | trust_ledger.py | 3.2 | medium |
| 3 | 3.4 | Update SKILL.md: Agent dispatch per loop with isolation:"worktree", subagent contract (JSON output, 300s timeout) | SKILL.md | 3.1, 3.2 | high |
| 3 | 3.5 | Add result collection: TaskOutput polling, trust merge, worktree branch merge | engine.py | 3.1, 3.2, 3.4 | high |
| 3 | 3.6 | Tests: parallel trust merge, worktree commit merge, fallback to sequential, subagent contract validation | test_adaptive_engine.py, test_worktree_utils.py | 3.5 | high |

**Sequencing**: Phase 1 steps are PIPELINE (sequential). Phase 2 steps 2.2 and 2.3 are PARALLEL. Phase 3 is PIPELINE. Phases are sequential (1 → 2 → 3).

### Agent Dispatch Pattern (for implementation sessions)

This ADR itself should be implemented using Claude Code teams:

- **Phase 1**: Single agent, sequential — small scope, shared files
- **Phase 2**: Team with 3 parallel agents:
  - Agent A (worktree): Upgrade 5 code-quality scanners (step 2.2)
  - Agent B (worktree): Upgrade 5 testing/hardening scanners (step 2.3)
  - Agent C (main): Protocol changes + self-test + tests (steps 2.1, 2.4, 2.5)
- **Phase 3**: Single agent — complex worktree/merge logic needs sequential coordination
