"""Clean-loop escalation logic for the adaptive engine.

Extracted from engine.py to keep each module under ~400 lines.
Provides EscalationMixin which AdaptiveLoopEngine inherits.
"""
from __future__ import annotations

import logging
from typing import Any

from .cycle_helpers import (
    CLEAN_LOOP_ESCALATION_LIMIT,
    difficulty_label,
    entry_max_difficulty,
    expansion_targets,
)

logger = logging.getLogger(__name__)


class EscalationMixin:
    """Mixin providing _apply_clean_loop_escalation and _escalate_difficulty_for_clean_d0."""

    def _escalate_difficulty_for_clean_d0(
        self,
        loop_name: str,
        entries: list,
        trigger_filter: str | None,
        degraded_categories: set[str],
        loop_state: object | None = None,
    ) -> None:
        """Escalate difficulty for categories at d0 that returned clean scans.

        At difficulty 0, an empty scan proves nothing. Instead of awarding trust
        credit, escalate to d1 so the next cycle scans deeper (ADR-405).
        """
        if loop_state is None:
            loop_state = self.ledger.get_loop_state(loop_name)
        for entry in entries:
            if trigger_filter and entry.trigger != trigger_filter:
                continue
            if entry.name in degraded_categories:
                continue
            cs = loop_state.categories.get(entry.name)
            if cs and cs.enabled and cs.difficulty == 0:
                cs.difficulty = 1
        self.ledger.save()

    def _apply_clean_loop_escalation(
        self,
        loop_name: str,
        entries: list[Any],
        trigger_filter: str | None,
        degraded_categories: set[str],
        loop_state: Any,
    ) -> list[str]:
        """Raise coverage after an all-clean cycle.

        Priority:
        1. Expand into explicitly declared adjacent harder issue families.
        2. Enable one dormant higher-tier category (if any exist from config).
        3. Raise difficulty for a small number of enabled categories that
           advertise deeper DIFFICULTY_SPEC levels and force one deep rerun.
        """
        limit = max(
            1,
            min(
                CLEAN_LOOP_ESCALATION_LIMIT,
                int(getattr(loop_state, "budget_growth_rate", 1) or 1),
            ),
        )
        notifications: list[str] = []
        remaining = limit

        entry_by_name = {entry.name: entry for entry in entries}
        clean_streak = int(getattr(loop_state, "consecutive_clean_cycles", 0) or 0)
        family_candidates: list[tuple[int, int, int, int, str, str, int, str, str]] = []
        dormant_candidates: list[tuple[int, str]] = []
        deep_candidates: list[tuple[int, int, int, str]] = []

        for entry in entries:
            if trigger_filter and entry.trigger != trigger_filter:
                continue
            if entry.name in degraded_categories:
                continue
            cs = loop_state.categories.get(entry.name)
            if not cs:
                continue
            if cs.enabled and cs.strategy == "scan":
                for target in expansion_targets(entry):
                    target_name = target["category"]
                    target_entry = entry_by_name.get(target_name)
                    if not target_entry:
                        continue
                    if trigger_filter and target_entry.trigger != trigger_filter:
                        continue
                    if target_name in degraded_categories:
                        continue
                    if clean_streak < target["min_clean_streak"]:
                        continue
                    expansion_key = (
                        f"{entry.name}->{target_name}@d{target['difficulty']}"
                    )
                    if self.ledger.has_completed_expansion(loop_name, expansion_key):
                        continue
                    target_state = loop_state.categories.get(target_name)
                    if not target_state or target_state.strategy != "scan":
                        continue
                    max_supported = entry_max_difficulty(target_entry)
                    if max_supported <= 0:
                        continue
                    requested_difficulty = min(target["difficulty"], max_supported)
                    if (
                        target_state.enabled
                        and target_state.difficulty >= requested_difficulty
                    ):
                        continue
                    family_candidates.append(
                        (
                            target["min_clean_streak"],
                            target_state.tier,
                            -requested_difficulty,
                            -int(cs.trust * 1000),
                            entry.name,
                            target_name,
                            requested_difficulty,
                            target["reason"],
                            expansion_key,
                        )
                    )
            if not cs.enabled and cs.disable_count == 0:
                dormant_candidates.append((cs.tier, entry.name))
                continue
            if not cs.enabled:
                continue
            if cs.strategy != "scan":
                continue
            max_supported = entry_max_difficulty(entry)
            if max_supported <= max(cs.difficulty, 0):
                continue
            if cs.difficulty < 1:
                continue
            headroom = max_supported - cs.difficulty
            deep_candidates.append((cs.difficulty, -headroom, cs.tier, entry.name))

        family_candidates.sort()
        for _, _, _, _, source_name, target_name, requested_difficulty, reason, expansion_key in family_candidates[:remaining]:
            target_state = loop_state.categories[target_name]
            target_state.enabled = True
            target_state.consecutive_failures = 0
            target_state.disabled_at_cycle = -1
            target_state.consecutive_clean_scans = 0
            target_state.strategy = "scan"
            target_state.difficulty = max(target_state.difficulty, requested_difficulty)
            target_state.force_deep_runs_remaining = max(
                target_state.force_deep_runs_remaining, 1
            )
            target_entry = entry_by_name.get(target_name)
            next_check = (
                difficulty_label(target_entry, target_state.difficulty)
                if target_entry is not None
                else ""
            )
            suffix = f" — next: {next_check}" if next_check else ""
            reason_suffix = f" ({reason})" if reason else ""
            notifications.append(
                f"Expanded from {source_name} to {target_name} after clean loop; "
                f"forced d{target_state.difficulty} next cycle{suffix}{reason_suffix}"
            )
            self.ledger.mark_completed_expansion(loop_name, expansion_key)
        remaining -= min(len(family_candidates), remaining)

        dormant_candidates.sort()
        for _, category_name in dormant_candidates[:remaining]:
            cs = loop_state.categories[category_name]
            cs.enabled = True
            cs.consecutive_failures = 0
            cs.disabled_at_cycle = -1
            cs.consecutive_clean_scans = 0
            cs.strategy = "scan"
            cs.force_deep_runs_remaining = 0
            notifications.append(
                f"Enabled dormant category {category_name} after clean loop "
                f"(tier {cs.tier})"
            )
        remaining -= min(len(dormant_candidates), remaining)

        if remaining > 0:
            deep_candidates.sort()
            for _, _, _, category_name in deep_candidates[:remaining]:
                cs = loop_state.categories[category_name]
                cs.difficulty += 1
                cs.consecutive_clean_scans = 0
                cs.force_deep_runs_remaining = max(cs.force_deep_runs_remaining, 1)
                entry = next((candidate for candidate in entries if candidate.name == category_name), None)
                next_check = difficulty_label(entry, cs.difficulty) if entry is not None else ""
                suffix = f" — next: {next_check}" if next_check else ""
                notifications.append(
                    f"Raised {category_name} to d{cs.difficulty} after clean loop; "
                    f"forced deep scan next cycle{suffix}"
                )

        if notifications:
            self.ledger.save()
        return notifications
