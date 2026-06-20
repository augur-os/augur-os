"""Trust ledger persistence.

Handles initialization from config, loading persisted state from
disk, and the atomic save (with file locking to handle concurrent
writers).

Extracted from trust_ledger.py to isolate serialization logic.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .trust_state import CategoryState, LoopState

if os.name == "nt":
    import msvcrt

    class _WindowsFcntlCompat:
        LOCK_EX = 1
        LOCK_UN = 2

        @staticmethod
        def flock(file_obj, operation: int) -> None:
            file_obj.seek(0, os.SEEK_END)
            if file_obj.tell() == 0:
                file_obj.write("0")
                file_obj.flush()
            file_obj.seek(0)
            mode = msvcrt.LK_LOCK if operation == _WindowsFcntlCompat.LOCK_EX else msvcrt.LK_UNLCK
            msvcrt.locking(file_obj.fileno(), mode, 1)

    fcntl = _WindowsFcntlCompat()
else:
    import fcntl


@contextmanager
def _locked_state_file(lock_file: Path):
    """Open and exclusively lock the trust-state sidecar file."""
    with open(lock_file, "a+") as lf:
        if os.name == "nt":
            lf.seek(0, os.SEEK_END)
            if lf.tell() == 0:
                lf.write("0")
                lf.flush()
            lf.seek(0)
            msvcrt.locking(lf.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lf.seek(0)
                msvcrt.locking(lf.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)


def init_loops_from_config(
    config: dict[str, Any],
) -> tuple[dict[str, LoopState], dict[str, list[str]]]:
    """Create LoopState instances from config. Returns (loops, category_order)."""
    loops: dict[str, LoopState] = {}
    category_order: dict[str, list[str]] = {}

    for loop_name, loop_cfg in config.get("loops", {}).items():
        cats = {}
        cat_names = list(loop_cfg.get("categories", {}).keys())
        category_order[loop_name] = cat_names
        for idx, (cat_name, cat_cfg) in enumerate(
            loop_cfg.get("categories", {}).items()
        ):
            cats[cat_name] = CategoryState(
                enabled=cat_cfg.get("enabled", False),
                trust=cat_cfg.get("trust", 0.0),
                tier=cat_cfg.get("tier", idx),
            )
        loops[loop_name] = LoopState(
            enabled=loop_cfg.get("enabled", True),
            trigger=loop_cfg.get("trigger", "nightly"),
            budget=loop_cfg.get("budget", 10),
            budget_remaining=loop_cfg.get("budget", 10),
            budget_growth_rate=loop_cfg.get("budget_growth_rate", 1),
            categories=cats,
        )

    return loops, category_order


def load_persisted_state(
    state_file: Path, loops: dict[str, LoopState]
) -> None:
    """Overlay persisted state from disk onto existing loop states (in-place)."""
    if not state_file.exists():
        return
    try:
        data = json.loads(state_file.read_text())
        for loop_name, loop_data in data.get("loops", {}).items():
            if loop_name not in loops:
                continue
            ls = loops[loop_name]
            ls.budget = loop_data.get("budget", ls.budget)
            ls.budget_remaining = loop_data.get("budget_remaining", ls.budget_remaining)
            ls.probation = loop_data.get("probation", False)
            ls.probation_successes = loop_data.get("probation_successes", 0)
            ls.total_consecutive_successes = loop_data.get(
                "total_consecutive_successes", 0
            )
            ls.cycle_count = loop_data.get("cycle_count", 0)
            ls.consecutive_clean_cycles = loop_data.get(
                "consecutive_clean_cycles", 0
            )
            ls.completed_expansions = list(
                loop_data.get("completed_expansions", [])
            )
            for cat_name, cat_data in loop_data.get("categories", {}).items():
                if cat_name not in ls.categories:
                    continue
                cs = ls.categories[cat_name]
                cs.trust = cat_data.get("trust", cs.trust)
                cs.enabled = cat_data.get("enabled", cs.enabled)
                cs.success_count = cat_data.get("success_count", 0)
                cs.failure_count = cat_data.get("failure_count", 0)
                cs.consecutive_successes = cat_data.get("consecutive_successes", 0)
                cs.consecutive_failures = cat_data.get("consecutive_failures", 0)
                cs.disabled_at_cycle = cat_data.get("disabled_at_cycle", -1)
                cs.disable_count = cat_data.get("disable_count", 0)
                cs.difficulty = cat_data.get("difficulty", 0)
                cs.consecutive_clean_scans = cat_data.get("consecutive_clean_scans", 0)
                cs.strategy = cat_data.get("strategy", "scan")
                # Commit tracking fields (must round-trip for commit gate)
                cs.commit_trust = cat_data.get("commit_trust", 0.0)
                cs.total_commits = cat_data.get("total_commits", 0)
                cs.total_fixes = cat_data.get("total_fixes", 0)
                cs.max_committed_difficulty = cat_data.get(
                    "max_committed_difficulty", 0
                )
                cs.pending_commit_verification = cat_data.get(
                    "pending_commit_verification", False
                )
                cs.last_commit_trust_credit = cat_data.get(
                    "last_commit_trust_credit", 0.0
                )
                cs.last_actionable_fingerprints = cat_data.get(
                    "last_actionable_fingerprints", []
                )
                cs.last_scanner_defect_fingerprints = cat_data.get(
                    "last_scanner_defect_fingerprints", []
                )
                cs.issue_decay_streak = cat_data.get("issue_decay_streak", 0)
                cs.stagnation_streak = cat_data.get("stagnation_streak", 0)
                cs.self_repair_count = cat_data.get("self_repair_count", 0)
                cs.self_repair_successes = cat_data.get(
                    "self_repair_successes", 0
                )
                cs.issue_cycles = cat_data.get("issue_cycles", 0)
                cs.false_positive_signal_count = cat_data.get(
                    "false_positive_signal_count", 0
                )
                cs.last_snapshot_fingerprint = cat_data.get(
                    "last_snapshot_fingerprint", ""
                )
                cs.force_deep_runs_remaining = cat_data.get(
                    "force_deep_runs_remaining", 0
                )
                # ADR-412 Phase 3: Hotspot fields
                cs.hot_paths = cat_data.get("hot_paths", [])
                cs.hot_patterns = cat_data.get("hot_patterns", [])
                cs.dominant_root_cause = cat_data.get("dominant_root_cause", "")
    except (json.JSONDecodeError, KeyError):
        pass  # Use config defaults on corrupt state


def save_state(
    state_dir: Path,
    state_file: Path,
    loops: dict[str, LoopState],
    authoritative_loops: set[str],
) -> None:
    """Persist loop state to disk with file locking and merge."""
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    data: dict[str, Any] = {"loops": {}}
    for name, ls in loops.items():
        data["loops"][name] = {
            "budget": ls.budget,
            "budget_remaining": ls.budget_remaining,
            "probation": ls.probation,
            "probation_successes": ls.probation_successes,
            "total_consecutive_successes": ls.total_consecutive_successes,
            "cycle_count": ls.cycle_count,
            "consecutive_clean_cycles": ls.consecutive_clean_cycles,
            "completed_expansions": ls.completed_expansions,
            "categories": {
                cn: asdict(cs) for cn, cs in ls.categories.items()
            },
        }
    lock_file = state_dir / "trust_state.lock"
    try:
        with open(lock_file, "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                # Re-read and merge to avoid clobbering concurrent writes
                if state_file.exists():
                    try:
                        existing = json.loads(state_file.read_text())
                    except (json.JSONDecodeError, OSError):
                        existing = {}
                    for ename, edata in existing.get("loops", {}).items():
                        if ename not in data["loops"]:
                            # Loop not in our state — preserve existing
                            data["loops"][ename] = edata
                        else:
                            our_loop = data["loops"][ename]
                            existing_cats = edata.get("categories", {})
                            our_cats = our_loop.get("categories", {})
                            # Preserve categories we don't have in memory,
                            # but skip ghost categories for authoritative
                            # loops (where discovery has run and pruned).
                            if ename not in authoritative_loops:
                                for ecat, ecat_data in existing_cats.items():
                                    if ecat not in our_cats:
                                        our_cats[ecat] = ecat_data
                            our_loop["categories"] = our_cats
                state_file.write_text(json.dumps(data, indent=2))
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)
    except OSError:
        return
