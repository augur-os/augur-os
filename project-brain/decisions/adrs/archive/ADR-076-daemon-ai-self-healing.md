---
status: Implemented
date: '2026-02-11'
deciders:
- Augur Team
related: []
hub: null
tags:
- daemon
- powered
- self
- healing
superseded_by: null
---

# ADR-076: Daemon AI-Powered Self-Healing

**Supersedes**: Extends ADR-041 (Daemon Production Monitoring)

## Context

ADR-041 introduced production monitoring with mode-aware behavior: the daemon scans runtime logs, detects errors, and either auto-restarts services (production) or notifies (dev). However, the current self-healing is limited to **process-level recovery** — restart crashed services, kill stalled PIDs, generate TODO markers.

Many runtime issues require **code-level fixes**, not just restarts:
- A hydration error recurring every page load won't be fixed by restarting the dashboard
- A MCP tool returning malformed JSON needs a code patch, not a PID kill
- A Python traceback in a daemon script requires debugging the actual logic

Today, these issues are logged as `TODO_BUG` markers in `tech_debt.md` and wait for a human or nightly cycle to address them. This creates a gap between detection (seconds) and resolution (hours/days).

**Goal**: Close the detection-to-resolution gap by having the daemon autonomously classify, triage, and fix runtime errors using AI — with zero user interaction required for critical/high issues.

## Decision

Add an **AI Self-Heal Service** (`ai_self_healer.py`) to the daemon that:

1. **Monitors** `data/runtime/` for errors via ripgrep on a configurable interval
2. **Classifies** found issues by severity using an LLM
3. **Auto-fixes** critical/high issues by invoking the `/debug` protocol headlessly
4. **Logs** medium/low issues as `TODO_` markers (with dedup)
5. **Notifies** the user at each stage: detected → healing → resolved/failed

### Architecture

```
unified_daemon.py
    └── ai_self_healer.py (NEW)
            ├── Scanner: ripgrep over data/runtime/logs/
            ├── Classifier: LLM severity triage
            ├── Healer: CLI-based /debug invocation
            ├── Dedup: issue registry to avoid duplicate work
            └── Notifier: notification_service.py integration
```

### 1. Scanning Phase

The scanner runs as a daemon subprocess with two triggers:

| Trigger | Interval | Purpose |
|---------|----------|---------|
| **Periodic** | Every N minutes (default: 5) | Catch accumulated warnings/errors |
| **Crash signal** | On SIGCHLD from child process | Immediate response to service crashes |

**Scan targets** (configurable in `self_heal.yaml`):

```yaml
scan_targets:
  - path: data/runtime/logs/*.log
    patterns: ["ERROR", "FATAL", "CRITICAL", "Traceback"]
  - path: data/runtime/logs/*.stderr.log
    patterns: ["Error:", "Exception:", "panic:"]
  - path: data/runtime/mcp_issues.md
    patterns: ["TODO_BUG"]
```

**Implementation**: Uses `ripgrep` (rg) for fast pattern matching across log files. Falls back to Python `re` if rg is not installed.

```python
def scan_runtime_errors() -> list[ErrorFinding]:
    """Scan runtime dir for errors using ripgrep."""
    findings = []
    for target in config.scan_targets:
        result = subprocess.run(
            ["rg", "--json", "-e", "|".join(target.patterns), target.path],
            capture_output=True, text=True, timeout=30
        )
        findings.extend(parse_rg_output(result.stdout))
    return deduplicate(findings)
```

### 2. Deduplication — Issue Registry

Before classifying or fixing, every finding is checked against a persistent **issue registry** at `data/runtime/self_heal_registry.json`:

```json
{
  "issues": {
    "a1b2c3": {
      "dedup_key": "a1b2c3",
      "message": "TypeError: Cannot read property 'map' of undefined",
      "file": "daemon.stderr.log",
      "severity": "high",
      "status": "fixed",
      "first_seen": "2026-02-11T10:00:00",
      "last_seen": "2026-02-11T10:05:00",
      "occurrences": 3,
      "fix_attempts": 1,
      "fix_result": "resolved",
      "fix_commit": "abc123"
    }
  },
  "last_scan": "2026-02-11T10:05:00"
}
```

**Dedup rules**:
- Same `dedup_key` (hash of normalized error message + source file) → increment `occurrences`, skip re-classification
- Status `fixing` → skip (already being handled)
- Status `fixed` + reappeared within 1h → escalate to `regression`, re-trigger fix
- Status `fixed` + reappeared after 1h → treat as new issue
- Status `failed` + fewer than `max_fix_attempts` (default: 2) → retry
- Status `failed` + exhausted retries → mark `abandoned`, create TODO_BUG, notify user

### 3. Classification Phase

New or unclassified issues are sent to the LLM for severity triage:

```python
CLASSIFY_PROMPT = """
You are a runtime error classifier for the Augur system.
Given the following error context, classify its severity.

Error: {error_message}
Source file: {source_file}
Stack trace: {stack_trace}
Occurrences: {count}

Classify as one of:
- CRITICAL: System is down or data loss imminent. Immediate fix required.
- HIGH: Feature is broken, user-visible impact. Fix within minutes.
- MEDIUM: Degraded functionality, workaround exists. Fix during next maintenance.
- LOW: Cosmetic, warning, or minor. Track as TODO.

Respond with JSON:
{{"severity": "critical|high|medium|low", "category": "integration|ux|performance|data|security", "summary": "one-line description", "likely_file": "path/to/suspected/file.py", "suggested_approach": "brief fix strategy"}}
"""
```

**LLM invocation**: Uses the configured CLI tool (see Section 6). The classifier prompt is small and fast — suitable for any tier.

### 4. Action Phase — Severity-Based Routing

| Severity | Action | User Interaction |
|----------|--------|-----------------|
| **CRITICAL** | Immediate headless `/debug` invocation | Notification only |
| **HIGH** | Queued `/debug` invocation (next available slot) | Notification only |
| **MEDIUM** | Create `TODO_BUG` marker in `tech_debt.md` | None (surfaces in nightly) |
| **LOW** | Create `TODO_IMPROVE` marker in `tech_debt.md` | None (surfaces in nightly) |

### 5. Headless Debug Flow (Critical/High)

For critical and high severity issues, the healer spawns a CLI session that executes the `/debug` protocol:

```python
def invoke_headless_debug(issue: Issue) -> FixResult:
    """Spawn a CLI debug session to fix the issue."""

    prompt = f"""
    AUTONOMOUS SELF-HEAL MODE — No user interaction available.

    The daemon detected a runtime error that needs immediate fixing.

    Error: {issue.message}
    Severity: {issue.severity}
    Source: {issue.file}
    Stack trace: {issue.stack_trace}
    Category: {issue.category}
    Suggested approach: {issue.suggested_approach}

    Execute the /debug protocol:
    1. Phase 0: Establish visibility (read the affected file and recent logs)
    2. Phase 1: Assess complexity
    3. Phase 2: Reproduce (read log context, trace the error)
    4. Phase 3: Hypothesize root cause
    5. Phase 4: Apply minimal fix (ONLY the affected file, smallest change possible)
    6. Phase 5: Run tests for the affected module only

    CONSTRAINTS:
    - Do NOT modify more than 3 files
    - Do NOT install new dependencies
    - Do NOT modify tests to make them pass — fix the source code
    - If complexity > 7/10, ABORT and create a TODO_BUG marker instead
    - Commit with prefix: fix(self-heal):
    """

    result = run_cli(prompt, timeout=config.fix_timeout_s)
    return parse_fix_result(result)
```

**Safety constraints**:
- Max 3 files modified per fix
- Max fix duration: 5 minutes (configurable)
- No dependency changes
- No test modifications (fix source, not tests)
- Complexity abort threshold: if the LLM judges complexity > 7/10, it aborts and creates a marker instead
- Single concurrent fix (lock file prevents parallel fix attempts)

**Fix lock**: `data/runtime/locks/self_heal_fix.lock` — prevents multiple simultaneous fix attempts. Contains `{"issue_key": "...", "started": "ISO8601", "pid": NNN}`.

### 6. LLM Configuration

User controls the LLM via `config/system/self_heal.yaml`:

```yaml
# AI Self-Healing Configuration
enabled: true

# Scanner settings
scan_interval_minutes: 5
scan_targets:
  - path: "data/runtime/logs/*.log"
    patterns: ["ERROR", "FATAL", "CRITICAL", "Traceback"]
  - path: "data/runtime/logs/*.stderr.log"
    patterns: ["Error:", "Exception:", "panic:"]

# LLM settings (for classification + fix)
llm:
  # Which CLI to use for AI operations
  # Options: "auto" (uses active CLI from llm.yaml), "claude", "kimi", "codex"
  # Default: "auto" — resolves to whatever CLI the user has configured
  cli: auto

  # CLI flags for classification (fast, low-cost)
  classify_flags:
    - "--print"
    - "--max-turns"
    - "1"

  # CLI flags for fix (needs more turns for debug protocol)
  fix_flags:
    - "--print"
    - "--max-turns"
    - "10"
    - "--allowedTools"
    - "Read,Edit,Bash,Grep,Glob"

  # Timeout for classification call
  classify_timeout_s: 30

  # Timeout for fix attempt
  fix_timeout_s: 300

# Fix constraints
fix:
  max_files_modified: 3
  max_fix_attempts: 2
  complexity_abort_threshold: 7
  auto_commit: true
  commit_prefix: "fix(self-heal):"

# Severity routing
routing:
  critical: fix       # Immediate headless /debug
  high: fix           # Queued headless /debug
  medium: todo        # Create TODO_BUG marker
  low: todo           # Create TODO_IMPROVE marker

# Notification settings (uses daemon's notification_service.py)
notifications:
  on_detect: true     # "Issue detected: {summary}"
  on_fix_start: true  # "Self-healing: {summary}"
  on_fix_success: true # "Fixed: {summary} ({commit})"
  on_fix_failure: true # "Self-heal failed: {summary}. Created TODO_BUG."
  on_abort: true      # "Issue too complex, created TODO_BUG marker"
```

**If no config exists**: Falls back to sensible defaults — uses `auto` CLI (resolves from `llm.yaml` active profile), 5-minute scan interval, standard constraints.

**CLI resolution (`auto` mode)**:
1. Read `config/system/llm.yaml` → `external.preferred_cli`
2. If `auto`: detect installed CLI (`claude` → `kimi` → `codex` → fail)
3. Use detected CLI for both classification and fix operations
4. Same CLI the user would get in Operation Mode

### 7. Notification Flow

Three-stage notifications via existing `notification_service.py`:

```
Stage 1: DETECTED
  "Self-Heal: Detected {severity} issue — {summary}"

Stage 2: HEALING (critical/high only)
  "Self-Heal: Applying fix for — {summary}"

Stage 3a: RESOLVED
  "Self-Heal: Fixed — {summary} (commit: {hash})"

Stage 3b: FAILED
  "Self-Heal: Could not fix — {summary}. Created TODO_BUG for manual review."

Stage 3c: DEFERRED (medium/low)
  (No notification — silently tracked in tech_debt.md)
```

### 8. Integration with Existing Systems

| System | Integration |
|--------|------------|
| `runtime_marker_scanner.py` | Self-healer replaces its error detection for classified issues; scanner still handles unclassified warnings |
| `unified_daemon.py` | New child subprocess: `ai_self_healer.py --loop` |
| `notification_service.py` | Uses existing `notify()` with category `self_heal` |
| `tech_debt.md` | Medium/low issues written here (same format as scanner) |
| `/nightly` | Reviews `self_heal_registry.json` for failed/abandoned fixes |
| `/debug` protocol | Headless fix follows the same 6-phase protocol |
| `llm.yaml` | Reads CLI config for `auto` mode |

## New Files

| File | Purpose |
|------|---------|
| `plugins/observability/skills/daemon/scripts/ai_self_healer.py` | Main self-heal service |
| `plugins/observability/skills/daemon/config/self_heal.yaml` | Default configuration |
| `config/system/self_heal.yaml` | User-editable configuration (created on first run from defaults) |
| `data/runtime/self_heal_registry.json` | Issue registry (dedup + history) |
| `plugins/observability/skills/daemon/modules/ai-self-heal.md` | Module documentation |

## Consequences

### Positive

- Runtime errors fixed in minutes instead of hours/days
- Zero user intervention for critical/high issues
- Dedup prevents duplicate work and noise
- User retains full control via config (can disable, change routing, swap LLM)
- Builds on existing infrastructure (notification, markers, debug protocol)
- Registry provides full audit trail of every detected issue and fix attempt

### Negative

- LLM API costs for classification + fixes (mitigated: classification is 1 fast call; fixes only for critical/high)
- Risk of bad auto-fixes (mitigated: max 3 files, complexity abort, test verification, max 2 attempts)
- Another daemon subprocess consuming resources (mitigated: mostly sleeping between scan intervals)
- Fix commits without human review (mitigated: prefixed `fix(self-heal):` for easy identification and revert)

### Neutral

- Existing `runtime_marker_scanner.py` continues to run for unclassified warnings
- Existing process-level self-healing (ADR-041) unchanged — AI healer handles code-level issues
- Users who don't configure an LLM CLI get the feature disabled gracefully (scanner still runs, just skips classification)

## Alternatives Considered

### Alternative 1: LLM API Direct (No CLI)

Call the LLM API directly from Python (e.g., `anthropic` SDK).

**Rejected**: Violates the AI integration pattern (CLAUDE.md) — all AI goes through IDE/CLI bridge. Also requires API keys in daemon config, which is less secure than using the CLI's existing auth.

### Alternative 2: Fix Everything (No Severity Routing)

Auto-fix all detected issues regardless of severity.

**Rejected**: Low/medium issues are often cosmetic or ambiguous. Auto-fixing them wastes LLM budget and risks unnecessary code churn. Better to track them as TODOs for human review during nightly.

### Alternative 3: Human-in-the-Loop for All Fixes

Require user approval before any auto-fix.

**Rejected**: Defeats the purpose. The whole point is seamless background operation. Critical production issues shouldn't wait for a human to click "approve" at 3 AM. Safety is ensured through constraints (max files, complexity abort, test verification) not human gating.

## References

- ADR-038: Unified Daemon Process
- ADR-041: Daemon Production Monitoring & Self-Healing
- ADR-052: Full-Stack Debugging Vision
- ADR-054: Offloading & External Execution
- `/debug` protocol: `plugins/ai/ai_bridge/agent-workflows/debug-protocol.md`
- LLM config: `config/system/llm.yaml`
- Notification service: `plugins/observability/skills/daemon/scripts/notification_service.py`

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `/write-adr`. Edit if needed before running.

**Team name**: `adr-076-impl`

### Phase 1: Core Service + Config
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create `self_heal.yaml` default config with all settings documented | `plugins/observability/skills/daemon/config/self_heal.yaml` |
| 1.2 | developer | medium | Implement `ai_self_healer.py` — scanner (ripgrep), dedup registry, classification prompt, severity router, headless debug invocation, notification integration | `plugins/observability/skills/daemon/scripts/ai_self_healer.py` |
| 1.3 | developer | low | Register `ai_self_healer.py` as child subprocess in `unified_daemon.py` | `plugins/observability/skills/daemon/scripts/unified_daemon.py` |

### Phase 2: Documentation + Dashboard
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | low | Write module doc `ai-self-heal.md` and update `SKILL.md` with new capability | `plugins/observability/skills/daemon/modules/ai-self-heal.md`, `plugins/observability/skills/daemon/SKILL.md` |
| 2.2 | frontend | medium | Add Self-Heal status card to daemon dashboard health page — shows registry stats, recent fixes, config status | `plugins/observability/skills/daemon/dashboard/health/page.tsx` |

### Phase 3: Tests
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Unit tests for scanner, dedup, classifier, severity router (mock LLM calls) | `plugins/observability/skills/daemon/tests/test_ai_self_healer.py` |
| 3.2 | validator | low | Integration test: create fake error log, verify registry update and TODO marker creation | `plugins/observability/skills/daemon/tests/test_self_heal_integration.py` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all daemon tests (`pytest plugins/observability/skills/daemon/tests/`), verify no regressions |
| V.2 | validator | low | Verify `npm run build` in `src/dashboard/` passes (if dashboard changes made) |
| V.3 | devops | low | Verify `unified_daemon.py status` shows new self-healer service |

### Completion Criteria
- [ ] `ai_self_healer.py` scans logs, classifies via LLM, routes by severity
- [ ] Dedup registry prevents duplicate classification and fix attempts
- [ ] Critical/high issues invoke headless `/debug` with safety constraints
- [ ] Medium/low issues create `TODO_` markers in `tech_debt.md`
- [ ] Config at `config/system/self_heal.yaml` controls all behavior
- [ ] Default CLI fallback works when no explicit LLM config is set
- [ ] Notifications fire at detect/heal/resolve stages
- [ ] All tests pass
- [ ] ADR status updated to Accepted/Implemented
