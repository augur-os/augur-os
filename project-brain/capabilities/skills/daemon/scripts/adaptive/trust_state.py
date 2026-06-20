"""Trust ledger state dataclasses.

CategoryState and LoopState hold the per-category and per-loop
runtime state tracked by the TrustLedger.

Extracted from trust_ledger.py so other modules can import
the dataclasses without pulling in the full ledger.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CategoryState:
    """State of a single category within a loop."""

    enabled: bool = False
    trust: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    consecutive_successes: int = 0
    consecutive_failures: int = 0
    tier: int = 0
    disabled_at_cycle: int = -1  # Cycle when disabled (-1 = never/config); for cooldown retry
    disable_count: int = 0  # Lifetime count of auto-disables; drives exponential backoff
    difficulty: int = 0  # 0=trivial .. MAX_DIFFICULTY=expert; escalates on consecutive successes
    consecutive_clean_scans: int = 0  # Resets when scan finds actions
    strategy: str = "scan"  # "scan" | "self-repair" | "dormant"
    # Commit-based trust: only increments on verified code commits, not reports
    commit_trust: float = 0.0
    total_commits: int = 0  # Lifetime commit count
    total_fixes: int = 0  # Lifetime fix() success count (including report-only)
    max_committed_difficulty: int = 0  # Highest difficulty at which a real commit was produced
    # Post-fix verification: set after commit, cleared after next scan
    pending_commit_verification: bool = False
    last_commit_trust_credit: float = 0.0  # Trust credited for last commit (for reversal)
    last_actionable_fingerprints: list[str] = field(default_factory=list)
    last_scanner_defect_fingerprints: list[str] = field(default_factory=list)
    issue_decay_streak: int = 0
    stagnation_streak: int = 0
    self_repair_count: int = 0
    self_repair_successes: int = 0
    issue_cycles: int = 0
    false_positive_signal_count: int = 0
    last_snapshot_fingerprint: str = ""
    force_deep_runs_remaining: int = 0
    # ADR-412 Phase 3: Hotspot tracking
    hot_paths: list[str] = field(default_factory=list)       # Top file/dir paths with recurring issues
    hot_patterns: list[str] = field(default_factory=list)     # Recurring error/issue pattern clusters
    dominant_root_cause: str = ""                             # Most common root_cause_type across recent issues


@dataclass
class LoopState:
    """State of a single loop."""

    enabled: bool = True
    trigger: str = "nightly"
    budget: int = 10
    budget_remaining: int = 10
    budget_growth_rate: int = 1
    probation: bool = False
    probation_successes: int = 0
    total_consecutive_successes: int = 0
    cycle_count: int = 0
    consecutive_clean_cycles: int = 0
    completed_expansions: list[str] = field(default_factory=list)
    categories: dict[str, CategoryState] = field(default_factory=dict)
