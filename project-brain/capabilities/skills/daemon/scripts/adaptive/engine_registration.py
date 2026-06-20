"""Auto-command and legacy loop registration for the adaptive engine.

Extracted from engine.py to keep each module under ~400 lines.
Provides RegistrationMixin which AdaptiveLoopEngine inherits.
"""
from __future__ import annotations

import logging
from typing import Any

from .loops.base_loop import BaseLoop

logger = logging.getLogger(__name__)


class RegistrationMixin:
    """Mixin providing register_loop() and register_auto_commands()."""

    def register_loop(self, loop: BaseLoop) -> None:
        """Register a legacy BaseLoop subclass."""
        if loop.NAME in self.loops:
            raise ValueError(f"Loop '{loop.NAME}' already registered")
        self.loops[loop.NAME] = loop

    def register_auto_commands(self, registry: dict, *, persist: bool = True) -> None:
        """Register discovered auto-commands grouped by loop.

        Also ensures each auto-command is registered as a category in the
        trust ledger so that check_allowed() permits execution.

        Args:
            registry: dict[str, AutoCommandEntry] from discover_auto_commands().
                      Each entry has: name, module, loop_name, tier, trigger,
                      scheduler, plugin_root.
            persist: When False, hydrate in-memory registration without
                     rewriting trust_state.json. Use for read-only CLI views.
        """
        from .discovery import group_by_loop
        from .trust_ledger import CategoryState

        grouped = group_by_loop(registry)
        for loop_name, entries in grouped.items():
            self._auto_commands[loop_name] = entries
            self._auto_loop_names.add(loop_name)

            # Ensure each auto-command is a category in the trust ledger.
            # If the loop doesn't exist in the ledger (not in config), create it
            # from the engine's loop config or with sensible defaults.
            try:
                loop_state = self.ledger.get_loop_state(loop_name)
            except KeyError:
                loop_cfg = self._config.get("loops", {}).get(loop_name, {})
                from .trust_ledger import LoopState
                self.ledger._loops[loop_name] = LoopState(
                    enabled=loop_cfg.get("enabled", True),
                    trigger=loop_cfg.get("trigger", "nightly"),
                    budget=loop_cfg.get("budget", 10),
                    budget_remaining=loop_cfg.get("budget", 10),
                    budget_growth_rate=loop_cfg.get("budget_growth_rate", 1),
                )
                loop_state = self.ledger._loops[loop_name]

            for entry in entries:
                if entry.name not in loop_state.categories:
                    loop_state.categories[entry.name] = CategoryState(
                        enabled=True,
                        trust=entry.initial_trust,
                        tier=entry.tier,
                    )

        # Re-load persisted state now that category slots exist.
        # On cold restart, load_persisted_state() runs before categories are
        # registered (config has 0 categories per ADR-200), so earned trust
        # values are skipped. Re-loading here recovers them.
        from .trust_persistence import load_persisted_state
        load_persisted_state(self.ledger._state_file, self.ledger._loops)

        # Apply bootstrap trust for newly discovered categories that have
        # initial_trust > 0 but persisted trust = 0.0 with no execution history.
        for loop_name, entries in grouped.items():
            ls = self.ledger._loops.get(loop_name)
            if not ls:
                continue
            for entry in entries:
                cs = ls.categories.get(entry.name)
                if (
                    cs
                    and entry.initial_trust > 0
                    and cs.trust == 0.0
                    and cs.success_count == 0
                    and cs.failure_count == 0
                ):
                    cs.trust = entry.initial_trust

        # Prune ghost categories from persistent state.  After a command is
        # renamed or its SKILL.md is deleted, the old category name lingers in
        # trust_state.json because save()'s merge logic preserves unknown
        # categories.  Pruning here removes them so they can't be resurrected.
        known_names: dict[str, set[str]] = {}
        for loop_name, entries in grouped.items():
            known_names.setdefault(loop_name, set()).update(
                entry.name for entry in entries
            )
        if persist:
            pruned = self.ledger.prune_unknown_categories(known_names)
            if pruned:
                logger.info(
                    "Pruned %d ghost categories from trust state: %s",
                    len(pruned),
                    ", ".join(pruned),
                )

        # ADR-405: Log commands without DIFFICULTY_SPEC (they won't earn
        # trust credit beyond baseline until they add one).
        no_spec = [
            name for name, entry in registry.items()
            if not hasattr(entry.module, "DIFFICULTY_SPEC")
        ]
        if no_spec:
            logger.info(
                "%d auto-commands without DIFFICULTY_SPEC (stuck at d0): %s",
                len(no_spec),
                ", ".join(sorted(no_spec)[:10]),
            )

        scheduler_counts: dict[str, int] = {}
        for entry in registry.values():
            scheduler = getattr(entry, "scheduler", "daemon")
            scheduler_counts[scheduler] = scheduler_counts.get(scheduler, 0) + 1

        counts_label = ", ".join(
            f"{scheduler}={count}"
            for scheduler, count in sorted(scheduler_counts.items())
        )
        logger.info(
            "Registered %d auto-commands across %d loops%s",
            len(registry),
            len(grouped),
            f" ({counts_label})" if counts_label else "",
        )
