"""
Adaptive Loop for Slash Commands (ADR-102)

Wraps any slash command with automatic improvement capability.
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
from pathlib import Path
from typing import Any, Callable, Coroutine

from .analyze_execution import analyze_execution, classify_improvements, save_analysis
from .command_rewriter import (
    apply_improvement_to_chain,
    apply_improvement_to_skill,
    commit_skill_update,
    find_chain_definition,
    find_skill_definition,
    log_improvement,
)
from .execution_tracker import ExecutionTracker, Outcome


class AdaptiveCommand:
    """Wrapper that adds adaptive improvement to any slash command."""

    def __init__(
        self,
        command_name: str,
        project_root: Path,
        runtime_dir: Path,
    ):
        self.command_name = command_name
        self.project_root = project_root
        self.runtime_dir = runtime_dir
        self.tracker = ExecutionTracker(command_name, project_root=project_root)

    def start_phase(self, name: str):
        """Start tracking a phase."""
        return self.tracker.start_phase(name)

    def end_phase(self, status: str = "completed", issue: dict | None = None):
        """End the current phase."""
        from .execution_tracker import PhaseStatus

        self.tracker.end_phase(PhaseStatus(status), issue)

    def start_step(self, name: str):
        """Start tracking a step."""
        return self.tracker.start_step(name)

    def end_step(
        self,
        status: str = "completed",
        error: str | None = None,
        resolution: str | None = None,
    ):
        """End the current step."""
        from .execution_tracker import PhaseStatus

        self.tracker.end_step(PhaseStatus(status), error, resolution)

    def record_retry(self):
        """Record a retry."""
        self.tracker.record_retry()

    def record_metrics(self, **kwargs):
        """Record execution metrics."""
        self.tracker.record_metrics(**kwargs)

    def add_blocker(self, blocker: str):
        """Add a blocker."""
        self.tracker.add_blocker(blocker)

    def add_learning(self, learning: str):
        """Add a learning."""
        self.tracker.add_learning(learning)

    def add_incident(self, incident):
        """Add a normalized incident."""
        self.tracker.add_incident(incident)

    async def run_adaptive(
        self,
        execution_func: Callable[[], Coroutine[Any, Any, Any]],
    ) -> dict[str, Any]:
        """Execute a command with adaptive improvement."""

        # 1. Execute the command
        try:
            result = await execution_func()
            outcome = Outcome.SUCCESS
        except Exception as e:
            result = {"error": str(e)}
            outcome = Outcome.FAILURE
            self.tracker.add_blocker(str(e))

        # 2. Finalize tracking
        self.tracker.finalize(outcome)

        # 3. Save execution log
        execution_path = self.tracker.save(self.runtime_dir)

        # 4. Analyze execution
        analysis = analyze_execution(self.tracker.get_log())
        analysis_path = save_analysis(self.command_name, analysis, self.runtime_dir)

        # 5. Classify improvements
        classified = classify_improvements(analysis.improvements)

        # 6. Find skill and chain definitions
        skill_path = find_skill_definition(self.command_name, self.project_root)
        chain_path = find_chain_definition(self.command_name, self.project_root)

        # 7. Apply auto-safe improvements
        applied_count = 0
        for improvement in classified["auto_apply"]:
            applied = False

            if skill_path:
                applied = apply_improvement_to_skill(skill_path, improvement)

            if chain_path and not applied:
                applied = apply_improvement_to_chain(chain_path, improvement)

            if applied:
                log_improvement(self.command_name, improvement, self.runtime_dir, applied=True)
                applied_count += 1

        # 8. Queue improvements needing review
        for improvement in classified["needs_review"]:
            log_improvement(self.command_name, improvement, self.runtime_dir, applied=False)

        # 9. Commit changes if any applied
        if applied_count > 0 and (skill_path or chain_path):
            commit_skill_update(self.command_name, skill_path, chain_path, self.runtime_dir)

        return {
            "execution_result": result,
            "execution_log": str(execution_path),
            "analysis_log": str(analysis_path),
            "improvements_applied": applied_count,
            "improvements_queued": len(classified["needs_review"]),
            "incidents_detected": len(self.tracker.get_log().incidents),
            "incident_index": str(self.runtime_dir / "command-evolution" / "incidents" / "index.json"),
            "outcome": outcome.value,
        }


async def run_adaptive_command(
    command_name: str,
    args: dict[str, Any],
    execution_func: Callable[[], Coroutine[Any, Any, Any]],
    project_root: Path | None = None,
    runtime_dir: Path | None = None,
) -> dict[str, Any]:
    """Run a command with adaptive improvement."""
    if project_root is None:
        from src.config.paths import get_project_root

        project_root = get_project_root()

    if runtime_dir is None:
        from src.config.paths import get_runtime_dir

        runtime_dir = get_runtime_dir()

    adaptive = AdaptiveCommand(command_name, project_root, runtime_dir)
    return await adaptive.run_adaptive(execution_func)


def create_adaptive_wrapper(
    command_name: str,
    project_root: Path | None = None,
    runtime_dir: Path | None = None,
):
    """Create an adaptive wrapper for a command.

    Usage:
        adaptive = create_adaptive_wrapper("implement-adr")

        # Track phases
        adaptive.start_phase("Phase 1: Analysis")
        # ... do work ...
        adaptive.end_phase("completed")

        # Track steps
        adaptive.start_step("parse-adr")
        # ... do work ...
        adaptive.end_step("completed")

        # Record issues
        adaptive.add_blocker("TypeScript build error")

        # Record learnings
        adaptive.add_learning("Worktree isolation prevented port collision")

        # Finalize and get improvements
        result = await adaptive.finalize()
    """
    if project_root is None:
        from src.config.paths import get_project_root

        project_root = get_project_root()

    if runtime_dir is None:
        from src.config.paths import get_runtime_dir

        runtime_dir = get_runtime_dir()

    return AdaptiveCommand(command_name, project_root, runtime_dir)
