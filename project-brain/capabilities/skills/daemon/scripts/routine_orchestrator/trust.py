"""Trust ledger for adaptive loops.

Tracks per-category trust scores, budgets, and promotion/demotion.
Persists state to disk. Computes trust from success/failure history.

Sub-modules (extracted for maintainability):
- trust_constants.py:    Thresholds, increments, limits
- trust_state.py:        CategoryState, LoopState dataclasses
- trust_persistence.py:  Init from config, load/save with file locking
- trust_convergence.py:  Issue decay / convergence analysis
- trust_diagnostics.py:  Diagnostic reporting
"""
from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any


def _adaptive_candidates(module_name: str) -> list[str]:
    package = __package__ or ""
    if package.startswith("skills.daemon.scripts.routine_orchestrator"):
        return [
            f"skills.daemon.scripts.adaptive.{module_name}",
            f"adaptive.{module_name}",
        ]
    return [
        f"adaptive.{module_name}",
        f"skills.daemon.scripts.adaptive.{module_name}",
    ]


def _import_adaptive(module_name: str) -> Any:
    last_error: ModuleNotFoundError | None = None
    for candidate in _adaptive_candidates(module_name):
        try:
            return import_module(candidate)
        except ModuleNotFoundError as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


_trust_constants = _import_adaptive("trust_constants")
for _constant_name in dir(_trust_constants):
    if _constant_name.isupper() or _constant_name == "module_has_self_repair":
        globals()[_constant_name] = getattr(_trust_constants, _constant_name)

_trust_state = _import_adaptive("trust_state")
CategoryState = _trust_state.CategoryState
LoopState = _trust_state.LoopState

_trust_persistence = _import_adaptive("trust_persistence")
init_loops_from_config = _trust_persistence.init_loops_from_config
load_persisted_state = _trust_persistence.load_persisted_state
save_state = _trust_persistence.save_state

_trust_convergence = _import_adaptive("trust_convergence")
_record_convergence = _trust_convergence.record_convergence

_trust_diagnostics = _import_adaptive("trust_diagnostics")
_diagnose_loops = _trust_diagnostics.diagnose_loops


class TrustLedger:
    """Manages trust scores, budgets, and promotion/demotion for all loops."""

    def __init__(self, config: dict[str, Any], state_dir: Path) -> None:
        self._config = config
        self._state_dir = state_dir
        self._state_file = state_dir / "trust_state.json"
        self._loops: dict[str, LoopState] = {}
        self._category_order: dict[str, list[str]] = {}
        # Loops whose in-memory categories are authoritative (set by
        # prune_unknown_categories).  For these loops, save() will NOT
        # preserve on-disk categories that aren't in memory.
        self._authoritative_loops: set[str] = set()

        # Initialize from config, then overlay persisted state
        self._loops, self._category_order = init_loops_from_config(config)
        load_persisted_state(self._state_file, self._loops)

    def prune_unknown_categories(self, known_names: dict[str, set[str]]) -> list[str]:
        """Remove ghost categories from persistent state.

        After auto-command discovery, any category in trust_state.json that
        isn't in the discovered registry is a ghost (from a renamed or deleted
        command).  This method:
        1. Removes ghost categories from in-memory state (if any leaked in).
        2. Marks these loops as authoritative so that save()'s merge logic
           will NOT re-introduce ghost categories from the on-disk file.
        3. Rewrites trust_state.json without the ghosts.

        Args:
            known_names: dict mapping loop_name -> set of valid category names.

        Returns:
            List of pruned category descriptions for logging.
        """
        pruned: list[str] = []
        for loop_name, valid_names in known_names.items():
            self._authoritative_loops.add(loop_name)
            ls = self._loops.get(loop_name)
            if not ls:
                continue
            stale = [cn for cn in ls.categories if cn not in valid_names]
            for cn in stale:
                del ls.categories[cn]
                pruned.append(f"{loop_name}/{cn}")
        # Always save to flush ghost categories from disk, even if none
        # were found in memory (they may only exist on disk).
        self.save()
        return pruned

    def save(self) -> None:
        save_state(self._state_dir, self._state_file, self._loops, self._authoritative_loops)

    def get_loop_state(self, loop: str) -> LoopState:
        return self._loops[loop]

    def check_allowed(self, loop: str, category: str) -> bool:
        ls = self._loops.get(loop)
        if not ls or not ls.enabled:
            return False
        if ls.budget_remaining <= 0:
            return False
        cs = ls.categories.get(category)
        if not cs or not cs.enabled:
            return False
        # In probation, only tier 0 allowed
        if ls.probation and cs.tier > 0:
            return False
        return True

    def consume_budget(self, loop: str) -> None:
        ls = self._loops[loop]
        ls.budget_remaining = max(0, ls.budget_remaining - 1)

    def record_success(self, loop: str, category: str) -> list[str]:
        """Record a successful action. Returns list of notification messages."""
        notifications = []
        ls = self._loops[loop]
        cs = ls.categories[category]

        # Update category trust (diminishing returns)
        cs.trust = cs.trust + (1.0 - cs.trust) * TRUST_INCREMENT_FACTOR
        cs.success_count += 1
        cs.consecutive_successes += 1
        cs.consecutive_failures = 0

        # Informational cross-category counter (not used for budget growth)
        ls.total_consecutive_successes += 1

        # Probation recovery
        if ls.probation:
            ls.probation_successes += 1
            if ls.probation_successes >= PROBATION_RECOVERY_SUCCESSES:
                ls.probation = False
                ls.probation_successes = 0
                notifications.append(
                    f"Loop '{loop}' exited probation"
                )

        # Promotion: unlock next tier category
        if (
            cs.success_count >= PROMOTION_MIN_SUCCESSES
            and cs.trust > PROMOTION_THRESHOLD
        ):
            next_cat = self._get_next_tier_category(loop, category)
            if next_cat and not ls.categories[next_cat].enabled:
                next_cs = ls.categories[next_cat]
                if next_cs.disable_count < MAX_DISABLE_RETRIES:
                    next_cs.enabled = True
                    notifications.append(
                        f"Loop '{loop}' promoted: '{next_cat}' now enabled"
                    )

        # Difficulty escalation: consecutive successes raise the bar
        if (
            cs.consecutive_successes > 0
            and cs.consecutive_successes % DIFFICULTY_ESCALATION_THRESHOLD == 0
        ):
            if cs.difficulty < MAX_DIFFICULTY:
                cs.difficulty += 1
                notifications.append(
                    f"Loop '{loop}' category '{category}' escalated to difficulty {cs.difficulty}"
                )
            elif cs.difficulty == MAX_DIFFICULTY:
                # Mastery: auto-promote next disabled tier
                next_cat = self._get_next_tier_category(loop, category)
                if next_cat and not ls.categories[next_cat].enabled:
                    next_cs = ls.categories[next_cat]
                    if next_cs.disable_count < MAX_DISABLE_RETRIES:
                        next_cs.enabled = True
                        notifications.append(
                            f"Loop '{loop}' mastery-promoted: '{next_cat}' now enabled"
                        )

        # Budget growth: per-category streak (not cross-category)
        if cs.consecutive_successes >= CONSECUTIVE_SUCCESS_FOR_BUDGET_GROWTH:
            ls.budget += ls.budget_growth_rate
            ls.budget_remaining += ls.budget_growth_rate
            cs.consecutive_successes = 0
            notifications.append(
                f"Loop '{loop}' budget increased to {ls.budget}"
            )

        self.save()
        return notifications

    def record_failure(self, loop: str, category: str) -> list[str]:
        """Record a failed action. Returns list of notification messages."""
        notifications = []
        ls = self._loops[loop]
        cs = ls.categories[category]

        # Steep penalty
        cs.trust = max(0.0, cs.trust - TRUST_DECREMENT)
        cs.failure_count += 1
        cs.consecutive_failures += 1
        cs.consecutive_successes = 0
        cs.difficulty = max(0, cs.difficulty - 1)
        cs.consecutive_clean_scans = 0

        # Check if THIS failure triggers a new disable
        newly_disabled = (
            cs.enabled
            and cs.consecutive_failures >= CONSECUTIVE_FAILURES_TO_DISABLE
        )

        # Budget shrink — skip for the failure that disables (disable IS the punishment)
        if not newly_disabled:
            ls.budget = max(BUDGET_FLOOR, ls.budget - 1)
            ls.budget_remaining = min(ls.budget_remaining, ls.budget)

            # Budget at floor -> probation
            if ls.budget <= BUDGET_FLOOR:
                ls.probation = True
                ls.probation_successes = 0
                notifications.append(
                    f"Loop '{loop}' entered probation — only tier 0 categories"
                )

        # Disable category on consecutive failures
        if newly_disabled:
            cs.enabled = False
            cs.disabled_at_cycle = ls.cycle_count
            cs.disable_count += 1
            if cs.disable_count >= MAX_DISABLE_RETRIES:
                notifications.append(
                    f"Loop '{loop}' demoted: '{category}' permanently disabled after "
                    f"{cs.disable_count} disable cycles (manual /a-loops promote required)"
                )
            else:
                cooldown = COOLDOWN_CYCLES * (2 ** (cs.disable_count - 1))
                notifications.append(
                    f"Loop '{loop}' demoted: '{category}' disabled after "
                    f"{CONSECUTIVE_FAILURES_TO_DISABLE} failures "
                    f"(retry {cs.disable_count}/{MAX_DISABLE_RETRIES}, "
                    f"cooldown {cooldown} cycles)"
                )

        self.save()
        return notifications

    def set_loop_enabled(self, loop: str, enabled: bool) -> None:
        self._loops[loop].enabled = enabled
        self.save()

    def promote_category(self, loop: str, category: str) -> None:
        cs = self._loops[loop].categories[category]
        cs.enabled = True
        cs.consecutive_failures = 0
        cs.disable_count = 0
        cs.disabled_at_cycle = -1
        cs.trust = 0.0
        cs.difficulty = 0
        cs.strategy = "scan"
        cs.last_actionable_fingerprints = []
        cs.last_scanner_defect_fingerprints = []
        cs.issue_decay_streak = 0
        cs.stagnation_streak = 0
        cs.self_repair_count = 0
        cs.self_repair_successes = 0
        cs.issue_cycles = 0
        cs.false_positive_signal_count = 0
        cs.last_snapshot_fingerprint = ""
        cs.force_deep_runs_remaining = 0
        cs.pending_commit_verification = False
        cs.last_commit_trust_credit = 0.0
        # Preserve commit_trust, total_commits, total_fixes, max_committed_difficulty
        # — those are lifetime stats, not reset on promote
        self.save()

    def _reset_category_state(
        self,
        category: CategoryState,
        *,
        enabled: bool,
        trust: float,
    ) -> None:
        category.trust = trust
        category.enabled = enabled
        category.success_count = 0
        category.failure_count = 0
        category.consecutive_successes = 0
        category.consecutive_failures = 0
        category.disable_count = 0
        category.disabled_at_cycle = -1
        category.difficulty = 0
        category.consecutive_clean_scans = 0
        category.strategy = "scan"
        category.last_actionable_fingerprints = []
        category.last_scanner_defect_fingerprints = []
        category.issue_decay_streak = 0
        category.stagnation_streak = 0
        category.self_repair_count = 0
        category.self_repair_successes = 0
        category.issue_cycles = 0
        category.false_positive_signal_count = 0
        category.last_snapshot_fingerprint = ""
        category.force_deep_runs_remaining = 0
        category.pending_commit_verification = False
        category.last_commit_trust_credit = 0.0
        category.hot_paths = []
        category.hot_patterns = []
        category.dominant_root_cause = ""

    def reset_loop(self, loop: str) -> None:
        """Reset trust scores to config defaults."""
        cfg = self._config.get("loops", {}).get(loop, {})
        ls = self._loops[loop]
        ls.budget = cfg.get("budget", 10)
        ls.budget_remaining = ls.budget
        ls.probation = False
        ls.probation_successes = 0
        ls.total_consecutive_successes = 0
        category_config = cfg.get("categories", {})
        for cat_name, cs in ls.categories.items():
            cat_cfg = category_config.get(cat_name)
            if cat_cfg is None:
                self._reset_category_state(cs, enabled=True, trust=0.0)
            else:
                self._reset_category_state(
                    cs,
                    enabled=cat_cfg.get("enabled", False),
                    trust=cat_cfg.get("trust", 0.0),
                )
        ls.consecutive_clean_cycles = 0
        ls.completed_expansions = []
        self.save()

    def set_budget(self, loop: str, budget: int) -> None:
        ls = self._loops[loop]
        ls.budget = budget
        ls.budget_remaining = min(ls.budget_remaining, budget)
        self.save()

    def reset_budget_cycle(self, loop: str) -> list[str]:
        """Reset budget for a new cycle. Syncs config, checks cooldowns."""
        notifications: list[str] = []
        ls = self._loops[loop]

        # Sync budget from config (picks up increases made outside the ledger)
        config_budget = (
            self._config.get("loops", {}).get(loop, {}).get("budget", ls.budget)
        )
        ls.budget = max(ls.budget, config_budget)
        ls.budget_remaining = ls.budget

        # Increment cycle and check cooldown-expired disabled categories
        ls.cycle_count += 1
        for cat_name, cs in ls.categories.items():
            if not cs.enabled and cs.disabled_at_cycle >= 0:
                # Permanently disabled after MAX_DISABLE_RETRIES
                if cs.disable_count >= MAX_DISABLE_RETRIES:
                    continue
                # Exponential backoff: 5, 10, 20, ... cycles
                cooldown = COOLDOWN_CYCLES * (2 ** max(0, cs.disable_count - 1))
                if ls.cycle_count - cs.disabled_at_cycle >= cooldown:
                    cs.enabled = True
                    cs.trust = 0.0
                    cs.consecutive_failures = 0
                    cs.disabled_at_cycle = -1
                    notifications.append(
                        f"Loop '{loop}': '{cat_name}' re-enabled after cooldown "
                        f"(attempt {cs.disable_count + 1}/{MAX_DISABLE_RETRIES})"
                    )

        self.save()
        return notifications

    def record_clean_scan(self, loop: str, min_difficulty: int = 0) -> list[str]:
        """Record that a scan found nothing to fix. Small trust credit with saturation."""
        notifications: list[str] = []
        ls = self._loops.get(loop)
        if not ls:
            return notifications
        for cat_name, cs in ls.categories.items():
            if not cs.enabled:
                continue
            if cs.difficulty < min_difficulty:
                continue
            cs.consecutive_clean_scans += 1
            if cs.consecutive_clean_scans > CLEAN_SCAN_SATURATION:
                # Saturated: no trust credit, but escalate difficulty
                if cs.difficulty < MAX_DIFFICULTY:
                    cs.difficulty += 1
                    notifications.append(
                        f"Loop '{loop}' category '{cat_name}' saturated clean scan — "
                        f"difficulty escalated to {cs.difficulty}"
                    )
            else:
                cs.trust = cs.trust + (1.0 - cs.trust) * CLEAN_SCAN_TRUST_INCREMENT
        self.save()
        return notifications

    def note_clean_loop(self, loop: str) -> int:
        """Record an all-clean loop cycle and return the clean streak length."""
        ls = self._loops.get(loop)
        if not ls:
            return 0
        ls.consecutive_clean_cycles += 1
        self.save()
        return ls.consecutive_clean_cycles

    def reset_clean_loop_streak(self, loop: str) -> None:
        """Reset all-clean loop streak after actionable/broken work appears."""
        ls = self._loops.get(loop)
        if not ls or ls.consecutive_clean_cycles == 0:
            return
        ls.consecutive_clean_cycles = 0
        self.save()

    def has_completed_expansion(self, loop: str, expansion_key: str) -> bool:
        """Return True if a clean-loop family expansion has already run."""
        ls = self._loops.get(loop)
        if not ls:
            return False
        return expansion_key in ls.completed_expansions

    def mark_completed_expansion(self, loop: str, expansion_key: str) -> None:
        """Persist that a clean-loop family expansion has already been consumed."""
        ls = self._loops.get(loop)
        if not ls:
            return
        if expansion_key not in ls.completed_expansions:
            ls.completed_expansions.append(expansion_key)
            self.save()

    def arm_forced_deep_scan(self, loop: str, category: str, runs: int = 1) -> None:
        """Require the next N runs for a category to skip classify shortcuts."""
        ls = self._loops.get(loop)
        if not ls or category not in ls.categories:
            return
        cs = ls.categories[category]
        cs.force_deep_runs_remaining = max(cs.force_deep_runs_remaining, max(0, runs))
        self.save()

    def consume_forced_deep_scan(self, loop: str, category: str) -> None:
        """Consume one queued forced-deep execution, if present."""
        ls = self._loops.get(loop)
        if not ls or category not in ls.categories:
            return
        cs = ls.categories[category]
        if cs.force_deep_runs_remaining <= 0:
            return
        cs.force_deep_runs_remaining -= 1
        self.save()

    def record_convergence(
        self,
        loop: str,
        category: str,
        issues: list[dict[str, Any]] | None = None,
        snapshot_fingerprint: str | None = None,
        entry_module: Any | None = None,
    ) -> list[str]:
        """Adjust trust and strategy from issue decay across cycles."""
        ls = self._loops.get(loop)
        if not ls or category not in ls.categories:
            return []

        notifications, changed = _record_convergence(
            ls, category, issues, snapshot_fingerprint,
            entry_module=entry_module,
        )
        # Prefix notifications with loop name for consistency
        notifications = [f"Loop '{loop}' {msg}" for msg in notifications]
        if changed:
            self.save()
        return notifications

    def get_strategy(self, loop: str, category: str) -> str:
        """Return the current execution strategy for a category."""
        return self._loops.get(loop, LoopState()).categories.get(
            category, CategoryState()
        ).strategy

    def get_difficulties(self, loop: str) -> dict[str, int]:
        """Return per-category difficulty levels for a loop."""
        ls = self._loops.get(loop)
        if not ls:
            return {}
        return {name: cs.difficulty for name, cs in ls.categories.items()}

    def reset_clean_scan_streaks(self, loop: str) -> None:
        """Reset consecutive_clean_scans for all categories in a loop."""
        ls = self._loops.get(loop)
        if not ls:
            return
        for cs in ls.categories.values():
            cs.consecutive_clean_scans = 0

    def check_consistency(self, loop: str) -> list[str]:
        """Auto-fix inconsistent state. Returns fix notifications."""
        ls = self._loops.get(loop)
        if not ls:
            return []
        fixes: list[str] = []
        for cat_name, cs in ls.categories.items():
            # Zombie: enabled but permanently disabled
            if cs.enabled and cs.disable_count >= MAX_DISABLE_RETRIES:
                cs.enabled = False
                fixes.append(
                    f"Consistency fix: '{cat_name}' was enabled with "
                    f"disable_count={cs.disable_count}, set enabled=False"
                )
            # Uncaught disable: enough failures but still enabled
            if cs.enabled and cs.consecutive_failures >= CONSECUTIVE_FAILURES_TO_DISABLE:
                cs.enabled = False
                cs.disabled_at_cycle = ls.cycle_count
                cs.disable_count += 1
                fixes.append(
                    f"Consistency fix: '{cat_name}' had "
                    f"{cs.consecutive_failures} consecutive failures, disabled"
                )
            # Stale disable cycle
            if cs.disabled_at_cycle > ls.cycle_count:
                old_val = cs.disabled_at_cycle
                cs.disabled_at_cycle = -1
                fixes.append(
                    f"Consistency fix: '{cat_name}' had disabled_at_cycle="
                    f"{old_val} > cycle_count={ls.cycle_count}, reset"
                )
        if ls.budget_remaining < 0:
            ls.budget_remaining = 0
            fixes.append("Consistency fix: budget_remaining was negative, clamped to 0")
        if fixes:
            self.save()
        return fixes

    def diagnose(self, journal_entries: list[dict] | None = None) -> dict:
        """Analyze all loops for issues. Returns structured report."""
        return _diagnose_loops(self._loops, journal_entries)

    def _get_next_tier_category(self, loop: str, category: str) -> str | None:
        """Find the next-tier disabled category to promote."""
        ls = self._loops.get(loop)
        if not ls:
            return None
        current_cs = ls.categories.get(category)
        if not current_cs:
            return None

        order = self._category_order.get(loop, [])
        max_tier = max(
            (ls.categories[c].tier for c in order if c in ls.categories),
            default=0,
        )
        target_tier = current_cs.tier + 1

        while target_tier <= max_tier:
            candidate_name = None
            for cat_name in order:
                cs = ls.categories.get(cat_name)
                if cs and cs.tier == target_tier:
                    candidate_name = cat_name
                    break

            if not candidate_name:
                break

            candidate = ls.categories[candidate_name]
            if not candidate.enabled:
                return candidate_name

            if candidate.trust >= CASCADE_TRUST_FLOOR:
                target_tier += 1
                continue

            break

        return None
