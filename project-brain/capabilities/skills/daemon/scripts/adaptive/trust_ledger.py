"""Compatibility re-export for the extracted routine orchestrator trust ledger."""
from __future__ import annotations

from importlib import import_module


def _import_matching_trust_module():
    package = __package__ or ""
    if package.startswith("skills.daemon.scripts.adaptive"):
        candidates = [
            "skills.daemon.scripts.routine_orchestrator.trust",
            "routine_orchestrator.trust",
        ]
    else:
        candidates = [
            "routine_orchestrator.trust",
            "skills.daemon.scripts.routine_orchestrator.trust",
        ]

    last_error: ModuleNotFoundError | None = None
    for candidate in candidates:
        try:
            return import_module(candidate)
        except ModuleNotFoundError as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


_trust = _import_matching_trust_module()

__all__ = [
    "BUDGET_FLOOR",
    "CASCADE_TRUST_FLOOR",
    "CLEAN_LOOP_ESCALATION_WIDTH",
    "CLEAN_SCAN_SATURATION",
    "CLEAN_SCAN_TRUST_INCREMENT",
    "CLEAN_SCAN_SKIP_MODULO",
    "CLEAN_SCAN_SKIP_THRESHOLD",
    "COMMIT_RATE_PRIORITY_THRESHOLD",
    "COMMIT_TRUST_INCREMENT",
    "CONSECUTIVE_FAILURES_TO_DISABLE",
    "CONSECUTIVE_SUCCESS_FOR_BUDGET_GROWTH",
    "COOLDOWN_CYCLES",
    "DIFFICULTY_COMMIT_GATE_BUFFER",
    "DIFFICULTY_ESCALATION_THRESHOLD",
    "DORMANT_CLEAN_THRESHOLD",
    "HOLLOW_FIX_TRUST_PENALTY",
    "ISSUE_DECAY_TRUST_BONUS",
    "MAX_DIFFICULTY",
    "MAX_DISABLE_RETRIES",
    "PARTIAL_DECAY_TRUST_BONUS",
    "PROBATION_RECOVERY_SUCCESSES",
    "PRODUCTIVE_FIX_TRUST_INCREMENT",
    "PROMOTION_MIN_SUCCESSES",
    "PROMOTION_THRESHOLD",
    "REPORT_ONLY_DEMOTION_THRESHOLD",
    "REPORT_ONLY_TRUST_CREDIT",
    "SCANNER_DEFECT_TRUST_PENALTY",
    "SELF_REPAIR_FAILURE_RATIO",
    "SELF_REPAIR_MAX_ATTEMPTS",
    "SELF_REPAIR_STREAK_THRESHOLD",
    "SELF_REPAIR_TRUST_THRESHOLD",
    "STAGNATION_DIFFICULTY_REDUCTION_THRESHOLD",
    "STAGNATION_TRUST_PENALTY",
    "TRUST_DECREMENT",
    "TRUST_INCREMENT_FACTOR",
    "module_has_self_repair",
    "CategoryState",
    "LoopState",
    "TrustLedger",
]

globals().update({name: getattr(_trust, name) for name in __all__})
