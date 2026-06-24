"""Trust ledger convergence analysis.

Adjusts trust and strategy based on issue decay across cycles.
Phase 2 of ADR-412: compare current actionable/scanner-defect
fingerprints with the previous cycle for the same category.

Extracted from trust_ledger.py to isolate convergence logic.
"""
from __future__ import annotations

from typing import Any

from .trust_constants import (
    ISSUE_DECAY_TRUST_BONUS,
    PARTIAL_DECAY_TRUST_BONUS,
    STAGNATION_TRUST_PENALTY,
    SCANNER_DEFECT_TRUST_PENALTY,
    SELF_REPAIR_TRUST_THRESHOLD,
    SELF_REPAIR_STREAK_THRESHOLD,
    SELF_REPAIR_MAX_ATTEMPTS,
    SELF_REPAIR_FAILURE_RATIO,
    STAGNATION_DIFFICULTY_REDUCTION_THRESHOLD,
    HOLLOW_FIX_TRUST_PENALTY,
    DORMANT_CLEAN_THRESHOLD,
    MAX_DIFFICULTY,
    module_has_self_repair,
)
from .trust_state import CategoryState, LoopState
from .cycle_helpers import update_category_hotspots

import logging

logger = logging.getLogger(__name__)


def record_convergence(
    ls: LoopState,
    category: str,
    issues: list[dict[str, Any]] | None = None,
    snapshot_fingerprint: str | None = None,
    entry_module: Any | None = None,
) -> tuple[list[str], bool]:
    """Adjust trust and strategy from issue decay across cycles.

    Returns (notifications, changed) where changed indicates whether
    a save is needed.
    """
    cs = ls.categories.get(category)
    if not cs:
        return [], False

    notifications: list[str] = []
    issues = issues or []

    # --- Fix #4: Post-fix verification ---
    # Save the pending flag before clearing — hollow-fix detection must
    # only fire on the cycle AFTER the commit, not the same cycle.
    was_pending_verification = cs.pending_commit_verification
    cs.pending_commit_verification = False

    current_actionable = sorted({
        str(issue.get("fingerprint", ""))
        for issue in issues
        if str(issue.get("kind", "actionable")) == "actionable"
        and str(issue.get("fingerprint", ""))
    })
    current_scanner = sorted({
        str(issue.get("fingerprint", ""))
        for issue in issues
        if str(issue.get("kind", "")) == "scanner-defect"
        and str(issue.get("fingerprint", ""))
    })
    previous_actionable = set(cs.last_actionable_fingerprints)
    previous_scanner = set(cs.last_scanner_defect_fingerprints)
    current_actionable_set = set(current_actionable)
    current_scanner_set = set(current_scanner)
    previous_strategy = cs.strategy

    resolved_actionable = previous_actionable - current_actionable_set
    repeated_actionable = previous_actionable & current_actionable_set
    repeated_scanner = previous_scanner & current_scanner_set

    trust_before = cs.trust
    had_previous_actionable = bool(previous_actionable)
    has_current_actionable = bool(current_actionable_set)

    # --- Fix #4: Hollow fix detection ---
    # Only fires on the cycle AFTER a commit (was_pending_verification=True).
    # If the same fingerprints reappear, the commit didn't fix anything.
    if (
        was_pending_verification
        and cs.last_commit_trust_credit > 0
        and has_current_actionable
        and repeated_actionable == current_actionable_set
        and not resolved_actionable
    ):
        # The commit didn't reduce issues — reverse trust credit
        penalty = cs.last_commit_trust_credit + HOLLOW_FIX_TRUST_PENALTY
        cs.trust = max(0.0, cs.trust - penalty)
        cs.commit_trust = max(0.0, cs.commit_trust - cs.last_commit_trust_credit)
        cs.last_commit_trust_credit = 0.0
        notifications.append(
            f"category '{category}' hollow fix detected — trust reversed "
            f"(commit didn't reduce issues)"
        )
    else:
        cs.last_commit_trust_credit = 0.0

    if had_previous_actionable and not has_current_actionable:
        cs.issue_decay_streak += 1
        cs.stagnation_streak = 0
        cs.trust = cs.trust + (1.0 - cs.trust) * ISSUE_DECAY_TRUST_BONUS
    elif resolved_actionable and len(current_actionable_set) < len(previous_actionable):
        cs.issue_decay_streak += 1
        cs.stagnation_streak = 0
        cs.trust = cs.trust + (1.0 - cs.trust) * PARTIAL_DECAY_TRUST_BONUS
    elif has_current_actionable and repeated_actionable == current_actionable_set:
        cs.issue_decay_streak = 0
        cs.stagnation_streak += 1
        # Scale penalty with streak: longer stagnation = faster trust decay
        scaled_penalty = STAGNATION_TRUST_PENALTY * min(cs.stagnation_streak, 5)
        cs.trust = max(0.0, cs.trust - scaled_penalty)
    elif has_current_actionable and len(current_actionable_set) > len(previous_actionable):
        cs.issue_decay_streak = 0
        cs.stagnation_streak += 1
        scaled_penalty = STAGNATION_TRUST_PENALTY * min(cs.stagnation_streak, 5)
        cs.trust = max(0.0, cs.trust - scaled_penalty)
    elif not has_current_actionable:
        cs.issue_decay_streak = 0
        cs.stagnation_streak = 0

    if repeated_scanner:
        cs.trust = max(0.0, cs.trust - SCANNER_DEFECT_TRUST_PENALTY)
        cs.stagnation_streak += 1
        cs.issue_decay_streak = 0
        cs.false_positive_signal_count += len(current_scanner_set)

    if issues:
        cs.issue_cycles += 1

    should_self_repair = (
        (
            cs.stagnation_streak >= SELF_REPAIR_STREAK_THRESHOLD
            and cs.trust < SELF_REPAIR_TRUST_THRESHOLD
            and has_current_actionable
        )
        or (
            bool(repeated_scanner)
            and cs.trust < max(SELF_REPAIR_TRUST_THRESHOLD, 0.5)
        )
    )

    # Penalize trust for repeated failed self-repairs: if repair count
    # significantly exceeds successes, the loop is wasting cycles.
    # Stronger penalty than before: scales with attempt count.
    if cs.self_repair_count >= 3 and cs.self_repair_successes == 0:
        repair_fail_penalty = STAGNATION_TRUST_PENALTY * min(cs.self_repair_count, 8)
        cs.trust = max(0.0, cs.trust - repair_fail_penalty)
    elif cs.self_repair_count >= 2 and cs.self_repair_count > cs.self_repair_successes * 3:
        repair_fail_penalty = STAGNATION_TRUST_PENALTY * min(cs.self_repair_count - cs.self_repair_successes, 5)
        cs.trust = max(0.0, cs.trust - repair_fail_penalty)

    # Self-repair cap: disable category after too many failed repairs
    # instead of continuing to waste cycles
    if cs.self_repair_count >= SELF_REPAIR_MAX_ATTEMPTS:
        success_rate = cs.self_repair_successes / cs.self_repair_count if cs.self_repair_count > 0 else 0
        if success_rate < SELF_REPAIR_FAILURE_RATIO:
            cs.enabled = False
            cs.trust = 0.0
            cs.strategy = "scan"
            notifications.append(
                f"category '{category}' disabled: {cs.self_repair_count} repair attempts "
                f"with {cs.self_repair_successes} successes ({success_rate:.0%}) — "
                f"requires manual /a-loops promote"
            )
            cs.last_actionable_fingerprints = current_actionable
            cs.last_scanner_defect_fingerprints = current_scanner
            if snapshot_fingerprint is not None:
                cs.last_snapshot_fingerprint = snapshot_fingerprint
            update_category_hotspots(cs, issues)
            return notifications, True

    # Stagnation difficulty reduction: if fixes aren't helping at the current
    # difficulty, back off to a lower level instead of staying at d4
    if cs.stagnation_streak >= STAGNATION_DIFFICULTY_REDUCTION_THRESHOLD and cs.difficulty > 1:
        cs.difficulty -= 1
        notifications.append(
            f"category '{category}' difficulty reduced to d{cs.difficulty} "
            f"(stagnation streak {cs.stagnation_streak})"
        )

    # Fix #5: Only enter self-repair if the module actually supports it.
    has_self_repair_capability = module_has_self_repair(entry_module)

    if should_self_repair and has_self_repair_capability:
        if cs.strategy != "self-repair":
            notifications.append(
                f"category '{category}' entered self-repair mode"
            )
        cs.strategy = "self-repair"
        cs.self_repair_count += 1
        cs.difficulty = max(cs.difficulty, 2)
    elif should_self_repair and not has_self_repair_capability:
        # No self-repair capability — just reduce difficulty and track stagnation.
        # Don't enter a repair mode that can never succeed.
        if cs.difficulty > 0:
            cs.difficulty -= 1
            notifications.append(
                f"category '{category}' stagnating without self-repair capability — "
                f"difficulty reduced to d{cs.difficulty}"
            )
    elif not has_current_actionable and not current_scanner_set and cs.strategy != "scan":
        cs.strategy = "scan"
        if previous_strategy == "self-repair":
            cs.self_repair_successes += 1
        notifications.append(
            f"category '{category}' returned to scan mode"
        )

    # --- Fix #6: Dormant after clean ceiling ---
    # Categories that have been clean at max difficulty for too many cycles
    # should enter dormant mode. They'll only wake when the snapshot changes.
    if (
        not has_current_actionable
        and not current_scanner_set
        and cs.consecutive_clean_scans >= DORMANT_CLEAN_THRESHOLD
        and cs.difficulty >= MAX_DIFFICULTY
        and cs.strategy == "scan"
        and bool(snapshot_fingerprint)
    ):
        cs.strategy = "dormant"
        notifications.append(
            f"category '{category}' entered dormant mode after "
            f"{cs.consecutive_clean_scans} clean scans at d{cs.difficulty}"
        )

    fingerprints_changed = (
        cs.last_actionable_fingerprints != current_actionable
        or cs.last_scanner_defect_fingerprints != current_scanner
    )
    snapshot_changed = (
        snapshot_fingerprint is not None
        and cs.last_snapshot_fingerprint != snapshot_fingerprint
    )

    # Wake dormant categories when the snapshot changes (new code appeared)
    if cs.strategy == "dormant" and snapshot_changed:
        cs.strategy = "scan"
        cs.consecutive_clean_scans = 0
        notifications.append(
            f"category '{category}' woke from dormant — snapshot changed"
        )

    cs.last_actionable_fingerprints = current_actionable
    cs.last_scanner_defect_fingerprints = current_scanner
    if snapshot_fingerprint is not None:
        cs.last_snapshot_fingerprint = snapshot_fingerprint

    # ADR-412 Phase 3: Update hotspot tracking
    update_category_hotspots(cs, issues)

    changed = cs.trust != trust_before or bool(notifications) or fingerprints_changed or snapshot_changed
    return notifications, changed
