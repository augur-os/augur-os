"""Trust ledger constants.

Thresholds, increments, and limits for trust scoring,
promotion/demotion, budget management, difficulty escalation,
and convergence analysis.

Extracted from trust_ledger.py for reuse across sub-modules.
"""

PROMOTION_THRESHOLD = 0.5
PROMOTION_MIN_SUCCESSES = 3
CONSECUTIVE_SUCCESS_FOR_BUDGET_GROWTH = 5
CONSECUTIVE_FAILURES_TO_DISABLE = 5
TRUST_INCREMENT_FACTOR = 0.15  # Moderate: was 0.25 — slower trust build prevents premature escalation
TRUST_DECREMENT = 0.1  # Softer failure penalty
BUDGET_FLOOR = 1
PROBATION_RECOVERY_SUCCESSES = 3
CLEAN_SCAN_TRUST_INCREMENT = 0.05  # Conservative but reachable — ~0.40 trust within 20 clean cycles
COOLDOWN_CYCLES = 3  # Faster re-enable after disable
MAX_DISABLE_RETRIES = 5  # More chances before permanent disable
CASCADE_TRUST_FLOOR = 0.2  # Lower floor for cascade promotion
DIFFICULTY_ESCALATION_THRESHOLD = 3  # Was 4 — 3 consecutive successes for d+1
MAX_DIFFICULTY = 4  # 0=trivial, 1=easy, 2=moderate, 3=hard, 4=expert
CLEAN_SCAN_SATURATION = 2  # Was 3 — 2 consecutive clean scans before escalation
ISSUE_DECAY_TRUST_BONUS = 0.06
PARTIAL_DECAY_TRUST_BONUS = 0.03
STAGNATION_TRUST_PENALTY = 0.08  # Was 0.06 — stronger stagnation penalty
SCANNER_DEFECT_TRUST_PENALTY = 0.08
SELF_REPAIR_TRUST_THRESHOLD = 0.35
SELF_REPAIR_STREAK_THRESHOLD = 2
CLEAN_LOOP_ESCALATION_WIDTH = 2

# Self-repair caps — prevent endless repair cycles
SELF_REPAIR_MAX_ATTEMPTS = 5  # After 5 failed repairs, disable category
SELF_REPAIR_FAILURE_RATIO = 0.25  # Disable if success rate < 25% after 4+ attempts

# Stagnation difficulty reduction — back off when fixes aren't helping
STAGNATION_DIFFICULTY_REDUCTION_THRESHOLD = 4  # Reduce difficulty after 4 consecutive stagnation cycles

# Clean scan throttle — skip categories with long clean streaks
CLEAN_SCAN_SKIP_THRESHOLD = 20  # After 20 consecutive clean scans, only run every Nth cycle
CLEAN_SCAN_SKIP_MODULO = 3  # Run once every 3 cycles when throttled

# Fix #1: Report-only fixes get zero trust credit (only code-fix outcomes build trust)
REPORT_ONLY_TRUST_CREDIT = 0.0  # Was implicitly ~0.05 via clean-scan-like path

# Productive non-code-fix outcomes (sync, index rebuild) get partial credit.
# These produce real side effects (git commits, cache rebuilds) but aren't
# source code changes. Enough to advance trust and difficulty, not enough
# to reach promotion threshold on reports alone.
PRODUCTIVE_FIX_TRUST_INCREMENT = 0.05

# Fix #2: Difficulty gated on proven commit capability
DIFFICULTY_COMMIT_GATE_BUFFER = 1  # Allow difficulty up to max_committed_difficulty + buffer

# Fix #3: Budget priority — categories with zero commits after N fixes get demoted
REPORT_ONLY_DEMOTION_THRESHOLD = 20  # Fixes without any commit before demotion to d0
COMMIT_RATE_PRIORITY_THRESHOLD = 0.3  # Categories above this commit rate get priority

# Fix #4: Post-fix verification — hollow fix penalty
HOLLOW_FIX_TRUST_PENALTY = 0.10  # Penalty when a commit doesn't reduce issue count
COMMIT_TRUST_INCREMENT = 0.12  # Trust credit for verified commits (separate from scan trust)

# Fix #6: Dormant after clean ceiling at max difficulty
DORMANT_CLEAN_THRESHOLD = 20  # Clean scans at max difficulty before entering dormant mode


def module_has_self_repair(module: object | None) -> bool:
    """Check if an auto-command module supports self-repair.

    Centralizes the capability check used by trust_convergence and
    engine_fix_phase to avoid diverging attribute lists.
    """
    if module is None:
        return True  # Backward compat: assume capability when module unknown
    return (
        getattr(module, "HAS_SELF_REPAIR", False)
        or hasattr(module, "self_repair")
        or hasattr(module, "llm_fix")
    )
