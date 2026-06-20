"""Auto-command cycle execution for the adaptive engine.

Extracted from engine.py to keep each module under ~400 lines.
Provides AutoCycleMixin which AdaptiveLoopEngine inherits.

Contains run_auto_cycle() and its supporting methods:
- _make_cat_report()
- _self_test_disable()
"""
from __future__ import annotations

import logging
import time
from typing import Any

from .evolve_remediate import load_all_hints
from .snapshot import build_shared_snapshot, update_snapshot_hotspots
from .trust_ledger import (
    CLEAN_SCAN_SATURATION,
    CLEAN_SCAN_TRUST_INCREMENT,
)
from .trust_constants import COMMIT_RATE_PRIORITY_THRESHOLD
from .loops.base_loop import LoopResult
from .reporting import CategoryReport, CycleReport
from .cycle_helpers import save_cycle_report
from .engine_entry_runner import run_entry_scan_fix

logger = logging.getLogger(__name__)


class AutoCycleMixin:
    """Mixin providing run_auto_cycle() and related helpers."""

    def run_auto_cycle(
        self, loop_name: str, trigger_filter: str | None = None
    ) -> CycleReport:
        """Run a cycle for auto-command loops (ADR-200 per-command scan/fix).

        Iterates each auto-command in the loop (sorted by tier), calls scan()
        individually per command, then trust-gates fix(). Preserves all engine
        guarantees: verify_commit, journal, trust recording, budget control,
        and clean scan tracking.

        Returns a CycleReport with per-category trust snapshots (ADR-405).

        Args:
            loop_name: Name of the auto-command loop.
            trigger_filter: If set, skip commands whose trigger doesn't match.
        """
        entries = self._auto_commands.get(loop_name, [])
        if not entries:
            return CycleReport(loop_name=loop_name)

        try:
            loop_state = self.ledger.get_loop_state(loop_name)
        except KeyError:
            return CycleReport(loop_name=loop_name)
        if not loop_state.enabled:
            return CycleReport(loop_name=loop_name)

        # Auto-fix state inconsistencies before scan
        consistency_fixes = self.ledger.check_consistency(loop_name)
        for fix in consistency_fixes:
            self.journal_writer.log(
                loop=loop_name,
                action="consistency-fix",
                category="engine",
                result="success",
                files=[],
                duration_ms=0,
            )

        # Reset budget for this cycle
        self.ledger.reset_budget_cycle(loop_name)

        difficulties = self.ledger.get_difficulties(loop_name)
        results: list[LoopResult] = []
        cat_reports: list[CategoryReport] = []
        any_issues_found = False
        # Track which categories had broken/degraded scans (ADR-405)
        broken_categories: set[str] = set()
        degraded_categories: set[str] = set()
        no_coverage_categories: set[str] = set()
        invalidated_categories: set[str] = set()
        dep_invalidations = self._dependency_invalidations()
        needs_save = False  # Deferred save for self-test disables
        cycle_t0 = time.monotonic()
        shared_snapshot = (
            build_shared_snapshot(self._project_root)
            if self._shared_snapshot_enabled
            else {}
        )
        clean_escalations: list[str] = []

        # Reset per-cycle LLM dispatch budget (moved from run_fix_phase
        # where it incorrectly reset per-entry instead of per-cycle)
        from .engine_fix_phase import _llm_dispatch_counts
        _llm_dispatch_counts.clear()

        # ADR-458: Pre-load evolve hints once per cycle (avoids N file reads)
        load_all_hints()

        # Cache tsc baseline once per cycle (avoids running tsc twice per commit)
        if hasattr(self, "capture_tsc_baseline"):
            self.capture_tsc_baseline()

        # Mutable state container passed into run_entry_scan_fix
        cycle_state = {
            "any_issues_found": any_issues_found,
            "needs_save": needs_save,
        }

        def run_entry(entry: Any, *, allow_invalidations: bool) -> bool:
            """Execute a single auto-command entry. Returns True if budget remains."""
            continue_loop = run_entry_scan_fix(
                engine=self,
                loop_name=loop_name,
                loop_state=loop_state,
                entry=entry,
                trigger_filter=trigger_filter,
                shared_snapshot=shared_snapshot,
                results=results,
                cat_reports=cat_reports,
                broken_categories=broken_categories,
                degraded_categories=degraded_categories,
                invalidated_categories=invalidated_categories,
                dep_invalidations=dep_invalidations,
                cycle_state=cycle_state,
                allow_invalidations=allow_invalidations,
                no_coverage_categories=no_coverage_categories,
            )
            return continue_loop

        # Fix #3: Budget priority — within each tier, categories with higher
        # commit rates run first. Tier ordering is preserved as primary key
        # (tier-0 always runs before tier-1, which gates promotion).
        def _commit_priority(entry: Any) -> tuple:
            cs = loop_state.categories.get(entry.name)
            tier = cs.tier if cs else 0
            if not cs or cs.total_fixes == 0:
                return (tier, 1, 0, entry.name)  # Unknown — default within tier
            commit_rate = cs.total_commits / cs.total_fixes
            if commit_rate >= COMMIT_RATE_PRIORITY_THRESHOLD:
                return (tier, 0, -commit_rate, entry.name)  # High priority within tier
            return (tier, 2, -commit_rate, entry.name)  # Low priority within tier

        sorted_entries = sorted(entries, key=_commit_priority)

        for entry in sorted_entries:
            if not run_entry(entry, allow_invalidations=True):
                break

        if invalidated_categories:
            for entry in entries:
                if entry.name not in invalidated_categories:
                    continue
                run_entry(entry, allow_invalidations=False)

        any_issues_found = cycle_state["any_issues_found"]
        needs_save = cycle_state["needs_save"]

        # Clean scan tracking (ADR-405: difficulty-gated credit)
        # Per-category: d1+ categories earn trust, d0 categories escalate.
        if not any_issues_found and not broken_categories:
            has_d0 = False
            has_d1_plus = False
            for entry in entries:
                if trigger_filter and entry.trigger != trigger_filter:
                    continue
                if entry.name in degraded_categories:
                    continue
                if entry.name in no_coverage_categories:
                    continue
                cs = loop_state.categories.get(entry.name)
                if not cs or not cs.enabled:
                    continue
                if difficulties.get(entry.name, 0) == 0:
                    has_d0 = True
                else:
                    has_d1_plus = True

            # Award clean-scan credit to d1+ categories
            if has_d1_plus:
                self.ledger.record_clean_scan(loop_name, min_difficulty=1)
            # Escalate d0 categories to d1
            if has_d0:
                self._escalate_difficulty_for_clean_d0(loop_name, entries, trigger_filter, degraded_categories, loop_state)
            self.ledger.note_clean_loop(loop_name)
            clean_escalations = self._apply_clean_loop_escalation(
                loop_name,
                entries,
                trigger_filter,
                degraded_categories,
                loop_state,
            )

            self.journal_writer.log(
                loop=loop_name,
                action="clean-scan",
                category="engine",
                result="success",
                files=[],
                duration_ms=0,
            )
            # Update cat_reports with post-credit trust values
            for cr in cat_reports:
                cs = loop_state.categories.get(cr.name)
                if cs:
                    cr.trust_after = cs.trust
                    cr.difficulty_after = cs.difficulty
        elif any_issues_found:
            self.ledger.reset_clean_loop_streak(loop_name)
        elif broken_categories:
            self.ledger.reset_clean_loop_streak(loop_name)

        if needs_save:
            self.ledger.save()

        cycle_duration = int((time.monotonic() - cycle_t0) * 1000)
        report = CycleReport(
            loop_name=loop_name,
            categories=cat_reports,
            duration_ms=cycle_duration,
            results=results,
            clean_escalations=clean_escalations,
        )

        # ADR-412: aggregate hotspot data into snapshot before persisting
        cats = getattr(loop_state, "categories", {})
        if shared_snapshot and cats:
            update_snapshot_hotspots(shared_snapshot, cats)

        # Persist structured report for dashboard API consumption
        save_cycle_report(self._adaptive_dir, report, loop_state, shared_snapshot)

        return report

    def _make_cat_report(
        self,
        entry_name: str,
        trust_before: float,
        diff_before: int,
        loop_state: object,
        status: str,
        action_summary: str = "",
        outcome: str = "",
        issue_count: int = 0,
        issue_counts: dict[str, int] | None = None,
        self_repair_plan: str = "",
        self_repair_transition: str = "",
        deepening_reason: str = "",
        yield_class: str = "",
        new_fingerprint_count: int = 0,
        repeated_fingerprint_count: int = 0,
        resolved_fingerprint_count: int = 0,
        execution_mode: str = "deep",
        short_circuit_used: bool = False,
        scan_duration_ms: int = 0,
        fix_duration_ms: int = 0,
        total_duration_ms: int = 0,
        files_changed: list[str] | None = None,
    ) -> CategoryReport:
        """Build a CategoryReport, reading current trust/difficulty from loop_state."""
        cs = loop_state.categories.get(entry_name)
        counts = issue_counts or {}
        return CategoryReport(
            name=entry_name,
            trust_before=trust_before,
            trust_after=cs.trust if cs else 0.0,
            difficulty_before=diff_before,
            difficulty_after=cs.difficulty if cs else 0,
            status=status,
            action_summary=action_summary,
            outcome=outcome,
            issue_count=issue_count,
            actionable_count=counts.get("actionable", 0),
            maintenance_count=counts.get("maintenance", 0),
            environment_count=counts.get("environment", 0),
            scanner_defect_count=counts.get("scanner-defect", 0),
            manual_count=counts.get("manual", 0),
            broken_count=counts.get("broken", 0),
            strategy_after=cs.strategy if cs else "scan",
            self_repair_plan=self_repair_plan,
            self_repair_transition=self_repair_transition,
            execution_mode=execution_mode,
            deepening_reason=deepening_reason,
            yield_class=yield_class,
            new_fingerprint_count=new_fingerprint_count,
            repeated_fingerprint_count=repeated_fingerprint_count,
            resolved_fingerprint_count=resolved_fingerprint_count,
            false_positive_rate=round(
                (
                    (cs.false_positive_signal_count / cs.issue_cycles)
                    if cs and getattr(cs, "issue_cycles", 0) > 0
                    else 0.0
                ),
                3,
            ),
            self_repair_success_rate=round(
                (
                    (cs.self_repair_successes / cs.self_repair_count)
                    if cs and getattr(cs, "self_repair_count", 0) > 0
                    else 0.0
                ),
                3,
            ),
            short_circuit_used=short_circuit_used,
            scan_duration_ms=scan_duration_ms,
            fix_duration_ms=fix_duration_ms,
            total_duration_ms=total_duration_ms,
            files_changed=files_changed or [],
            # ADR-412: propagate hotspot data from category state
            hot_paths=list(getattr(cs, "hot_paths", []) or []),
            hot_patterns=list(getattr(cs, "hot_patterns", []) or []),
            dominant_root_cause=str(getattr(cs, "dominant_root_cause", "") or ""),
        )

    def _self_test_disable(
        self,
        cat_state: object,
        loop_state: object,
        entry_name: str,
        reason: str,
    ) -> None:
        """Disable a category on first-run self-test failure (ADR-405)."""
        cat_state.enabled = False
        cat_state.disabled_at_cycle = loop_state.cycle_count
        logger.warning(
            "Self-test failed for %s: disabled on first run (%s)",
            entry_name,
            reason,
        )
