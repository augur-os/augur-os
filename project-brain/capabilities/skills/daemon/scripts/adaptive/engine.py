"""Adaptive Loop Engine -- orchestrates all loops.

Ties together the ADR-743 loop-history ledger, trust ledger, and individual loops.
Runs as a child service inside unified_daemon.py.

Supports two registration modes:
1. Legacy: register_loop() with BaseLoop subclasses (scan all categories at once)
2. Auto-commands (ADR-200): register_auto_commands() with discovered OpsCommand
   modules (per-command scan/fix, decentralized from plugin SKILL.md frontmatter)

Module structure:
- reporting.py: CategoryReport, CycleReport dataclasses
- cycle_helpers.py: Issue normalization, yield classification, helper functions
- engine_registration.py: Loop/auto-command registration (RegistrationMixin)
- engine_auto_cycle.py: Auto-command cycle execution (AutoCycleMixin)
- engine_verification.py: Commit verification (VerificationMixin)
- engine_queue.py: Post-execution queue draining (QueueMixin)
- engine_report.py: Morning report generation (ReportMixin)
- engine.py (this file): AdaptiveLoopEngine class (thin orchestrator)
"""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import os
import shutil
import subprocess  # noqa: F401 — kept for test patch compatibility (adaptive.engine.subprocess)
from pathlib import Path
from typing import Any

from routine_orchestrator.ledger_view import LedgerJournalReader, LedgerJournalWriter
from .snapshot import build_shared_snapshot  # noqa: F401 — kept for test patch compatibility
from .trust_ledger import (
    CLEAN_SCAN_SATURATION,  # noqa: F401
    CLEAN_SCAN_TRUST_INCREMENT,  # noqa: F401
    TrustLedger,
)
from .loops.base_loop import BaseLoop, LoopResult

# Re-export reporting types for backward compatibility
from .reporting import CategoryReport, CycleReport  # noqa: F401
from .cycle_helpers import (
    CLEAN_LOOP_ESCALATION_LIMIT,  # noqa: F401
    TWO_PHASE_SNAPSHOT_KEYS,
    candidate_test_files,
    count_issue_kinds,
    dependency_invalidations,
    difficulty_label,
    entry_max_difficulty,
    expansion_targets,
    generate_next_actions,
    issue_fingerprint_sets,
    normalize_issue,
    save_cycle_report,
    should_short_circuit_classify,
    snapshot_fingerprint,
    two_phase_enabled,
    write_self_repair_plan,
    yield_class,
)

# Mixin imports
from .engine_registration import RegistrationMixin
from .engine_auto_cycle import AutoCycleMixin
from .engine_escalation import EscalationMixin
from .engine_verification import VerificationMixin
from .engine_queue import QueueMixin
from .engine_report import ReportMixin

import logging

logger = logging.getLogger(__name__)

# Backward compatibility aliases
_TWO_PHASE_SNAPSHOT_KEYS = TWO_PHASE_SNAPSHOT_KEYS
_CLEAN_LOOP_ESCALATION_LIMIT = CLEAN_LOOP_ESCALATION_LIMIT


class AdaptiveLoopEngine(
    RegistrationMixin,
    AutoCycleMixin,
    EscalationMixin,
    VerificationMixin,
    QueueMixin,
    ReportMixin,
):
    """Orchestrates adaptive loops with trust-gated execution."""

    def __init__(
        self,
        config: dict[str, Any],
        runtime_dir: Path,
        project_root: Path | None = None,
    ) -> None:
        self._config = config
        self._runtime_dir = runtime_dir
        self._project_root = project_root or Path.cwd()
        # Guard against double-nesting: if runtime_dir already ends with
        # /adaptive (e.g. caller passed get_runtime_dir() / "adaptive"),
        # use it directly instead of appending another /adaptive.
        if runtime_dir.name == "adaptive":
            self._adaptive_dir = runtime_dir
        else:
            self._adaptive_dir = runtime_dir / "adaptive"

        self.journal_writer = LedgerJournalWriter(self._adaptive_dir)
        self.journal_reader = LedgerJournalReader()
        self.ledger = TrustLedger(config, state_dir=self._adaptive_dir)
        self.loops: dict[str, BaseLoop] = {}

        # Auto-command registry: loop_name -> list of AutoCommandEntry (ADR-200)
        self._auto_commands: dict[str, list] = {}
        # Set of loop names managed by auto-commands (not legacy loops)
        self._auto_loop_names: set[str] = set()

        self._verify_command = (
            config.get("engine", {}).get("verify_command", "")
        )
        self._shared_snapshot_enabled = bool(
            config.get("engine", {}).get("shared_snapshot", False)
        )
        self._local_client: str | None = None  # Set by --local flag for Ollama backend
        self._session = self._detect_session(config)
        _llm_cfg = config.get("engine", {}).get("llm_escalation", {})
        self._llm_escalation_enabled = bool(_llm_cfg.get("enabled", False))
        self._llm_min_trust = _llm_cfg.get("min_trust", 0.5)
        self._llm_budget_multiplier = _llm_cfg.get("budget_multiplier", 3)

    @staticmethod
    def _detect_session(config: dict[str, Any]) -> "SessionContext":
        """Detect runtime environment capabilities (ADR-444).

        Checks PATH for known CLI binaries, detects agent session env vars,
        and loads config overrides from adaptive_loops.yaml.
        """
        from src.lib.ops_protocol import SessionContext

        ctx = SessionContext()

        # 1. Check if running inside an agent session with tool access
        agent_env_vars = [
            "CLAUDE_CODE_ENTRY_POINT",
            "CODEX_SESSION",
            "GEMINI_SESSION",
            "AUGUR_AGENT_SESSION",
        ]
        ctx.has_tool_access = any(os.environ.get(v) for v in agent_env_vars)

        # 2. Resolve CLI for headless dispatch
        try:
            from src.lib.llm_retry import resolve_cli
            cli_path = resolve_cli()
            if cli_path:
                ctx.has_llm = True
                ctx.cli_path = cli_path
                ctx.cli_name = Path(cli_path).stem
        except Exception:
            pass

        # 3. If in-session, LLM is always available
        if ctx.has_tool_access:
            ctx.has_llm = True

        # 4. Load config overrides
        llm_cfg = config.get("engine", {}).get("llm_escalation", {})
        ctx.max_turns = llm_cfg.get("max_turns", 20)
        ctx.timeout = llm_cfg.get("timeout_s", 600)

        return ctx

    # -- Trigger-based execution (legacy + auto-command) --

    def run_all_by_trigger(self, trigger: str) -> dict[str, list[LoopResult]]:
        """Run all loops matching a trigger type.

        Handles both legacy loops and auto-command loops.
        For 'mixed' trigger loops, filters actions to only those categories
        whose per-category trigger matches the requested trigger.
        """
        results = {}

        # Legacy loops
        for name, loop in self.loops.items():
            loop_state = self.ledger.get_loop_state(name)
            if not loop_state.enabled:
                continue

            if loop.TRIGGER == trigger:
                results[name] = self.run_cycle(name)
            elif loop.TRIGGER == "mixed":
                results[name] = self.run_cycle(name, trigger_filter=trigger)

        # Auto-command loops (ADR-200)
        for loop_name, entries in self._auto_commands.items():
            if loop_name in self.loops:
                # Already handled as legacy loop, skip
                continue
            try:
                loop_state = self.ledger.get_loop_state(loop_name)
                if not loop_state.enabled:
                    continue
            except KeyError:
                continue

            daemon_entries = [
                entry
                for entry in entries
                if getattr(entry, "scheduler", "daemon") == "daemon"
            ]
            if not daemon_entries:
                continue

            # Only daemon-owned entries should be eligible for daemon-triggered cycles.
            loop_triggers = {entry.trigger for entry in daemon_entries}
            if trigger in loop_triggers or "mixed" in loop_triggers:
                original_entries = self._auto_commands[loop_name]
                self._auto_commands[loop_name] = daemon_entries
                try:
                    report = self.run_auto_cycle(
                        loop_name, trigger_filter=trigger
                    )
                finally:
                    self._auto_commands[loop_name] = original_entries
                results[loop_name] = report.results

        return results

    def run_cycle(self, loop_name: str, trigger_filter: str | None = None) -> list[LoopResult]:
        """Run a single cycle of a loop. Returns list of results.

        Args:
            loop_name: Name of the loop to run.
            trigger_filter: If set, only execute actions whose category has
                a matching per-category trigger in config. Used for mixed-trigger loops.
        """
        loop_state = self.ledger.get_loop_state(loop_name)
        if not loop_state.enabled:
            return []

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

        loop = self.loops[loop_name]
        difficulties = self.ledger.get_difficulties(loop_name)
        actions = loop.scan(difficulties=difficulties)
        results = []

        # Reset budget for this cycle
        self.ledger.reset_budget_cycle(loop_name)

        # Clean scan: credit enabled categories with small trust bump
        if not actions:
            self.ledger.record_clean_scan(loop_name)
            # Log clean scans so status consumers can report true last run
            # instead of only the last fix/failure action.
            self.journal_writer.log(
                loop=loop_name,
                action="clean-scan",
                category="engine",
                result="success",
                files=[],
                duration_ms=0,
            )
            loop.finalize()
            return []

        # Non-clean scan: reset clean scan streaks
        self.ledger.reset_clean_scan_streaks(loop_name)

        for action in actions:
            category = action.get("category", "")

            # Filter by per-category trigger if applicable
            if trigger_filter and not self._category_matches_trigger(
                loop_name, category, trigger_filter
            ):
                continue

            if not self.ledger.check_allowed(loop_name, category):
                continue

            self.ledger.consume_budget(loop_name)
            result = loop.execute_action(action)

            # Regression guard for commits
            if result.success and result.commit and self._verify_command:
                if not self.verify_commit(result.commit):
                    result = LoopResult(
                        success=False,
                        action=result.action,
                        category=result.category,
                        files=result.files,
                        error="regression: verify failed, commit reverted",
                    )

            # Log to journal
            self.journal_writer.log(
                loop=loop_name,
                action=result.action,
                category=result.category,
                files=result.files or [],
                result="success" if result.success else "failure",
                commit=result.commit,
                error=result.error,
                duration_ms=result.duration_ms,
            )

            # Update trust
            if result.success:
                self.ledger.record_success(loop_name, category)
            else:
                self.ledger.record_failure(loop_name, category)

            results.append(result)

            # Stop if budget exhausted
            if not self.ledger.check_allowed(loop_name, category):
                break

        # Let the loop flush any batched work (e.g., staged RAG commits)
        loop.finalize()

        return results

    # -- Delegating helper methods to cycle_helpers module --

    def _normalize_issue(self, category_name: str, issue: object) -> dict[str, Any]:
        return normalize_issue(category_name, issue)

    def _count_issue_kinds(self, issues: list[dict[str, Any]]) -> dict[str, int]:
        return count_issue_kinds(issues)

    @staticmethod
    def _issue_fingerprint_sets(issues: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
        return issue_fingerprint_sets(issues)

    @staticmethod
    def _yield_class(
        execution_mode: str,
        issues: list[dict[str, Any]],
        issue_counts: dict[str, int],
        previous_actionable: set[str],
        current_actionable: set[str],
        current_scanner: set[str],
    ) -> tuple[str, int, int, int]:
        return yield_class(
            execution_mode, issues, issue_counts,
            previous_actionable, current_actionable, current_scanner,
        )

    def _dependency_invalidations(self) -> dict[str, set[str]]:
        return dependency_invalidations(self._config)

    def _recent_category_failures(
        self, loop_name: str, category_name: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        entries = self.journal_reader.filter(loop=loop_name, category=category_name, result="failure")
        recent = entries[-limit:]
        return [
            {
                "timestamp": entry.timestamp,
                "action": entry.action,
                "error": entry.error or "",
            }
            for entry in recent
        ]

    def _candidate_test_files(self, entry: Any) -> list[str]:
        return candidate_test_files(entry)

    def _write_self_repair_plan(
        self,
        loop_name: str,
        entry: Any,
        issues: list[dict[str, Any]],
        summary: str,
    ) -> str:
        return write_self_repair_plan(
            self._adaptive_dir, loop_name, entry, issues, summary,
            self.ledger, self.journal_reader,
        )

    def _two_phase_enabled(self, entry_name: str, entry_config: dict[str, Any]) -> bool:
        return two_phase_enabled(entry_name, entry_config)

    def _snapshot_fingerprint(
        self,
        entry_name: str,
        shared_snapshot: dict[str, Any],
    ) -> str:
        return snapshot_fingerprint(entry_name, shared_snapshot)

    def _should_short_circuit_classify(
        self,
        cat_state: Any,
        entry_name: str,
        entry_config: dict[str, Any],
        difficulty: int,
        snap_fingerprint: str,
    ) -> bool:
        return should_short_circuit_classify(
            cat_state, entry_name, entry_config, difficulty, snap_fingerprint,
        )

    @staticmethod
    def _entry_max_difficulty(entry: Any) -> int:
        return entry_max_difficulty(entry)

    @staticmethod
    def _difficulty_label(entry: Any, level: int) -> str:
        return difficulty_label(entry, level)

    @staticmethod
    def _expansion_targets(entry: Any) -> list[dict[str, Any]]:
        return expansion_targets(entry)

    def _save_cycle_report(
        self,
        report: CycleReport,
        loop_state: object,
        shared_snapshot: dict[str, Any] | None = None,
    ) -> None:
        """Persist a structured JSON report for dashboard API consumption."""
        save_cycle_report(self._adaptive_dir, report, loop_state, shared_snapshot)

    def _generate_next_actions(
        self, report: CycleReport, loop_state: object
    ) -> list[str]:
        """Compute actionable next steps from cycle results and trust state."""
        return generate_next_actions(report, loop_state)

    def _category_matches_trigger(
        self, loop_name: str, category: str, trigger: str
    ) -> bool:
        """Check if a category's per-category trigger matches the requested trigger."""
        loop_cfg = self._config.get("loops", {}).get(loop_name, {})
        cat_cfg = loop_cfg.get("categories", {}).get(category, {})
        cat_trigger = cat_cfg.get("trigger", loop_cfg.get("trigger", "nightly"))
        return cat_trigger == trigger
