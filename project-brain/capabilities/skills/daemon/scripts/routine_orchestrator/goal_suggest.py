"""Suggestion engine for /routines goal.

assess(): run loop scanners in pure scan-only mode (no mutation) and aggregate
findings per loop. suggest(): rank catalog goals by their live findings so the
user picks from real debt, never fabricated work.
"""
from __future__ import annotations

import contextlib
import logging
import signal
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

try:
    from . import goal_catalog, scan_phase
except ImportError:  # pragma: no cover - direct-path import fallback
    from routine_orchestrator import goal_catalog, scan_phase  # type: ignore[no-redef]

ScanFn = Callable[..., list[dict[str, Any]]]

# Roughly how many findings one convergence iteration is expected to clear.
_FINDINGS_PER_ITERATION = 5


class _ScanDeadlineExpired(BaseException):
    """Private timeout signal that scanner-level Exception handlers do not swallow."""


@dataclass(frozen=True)
class GoalSuggestion:
    id: str
    title: str
    loops: tuple[str, ...]
    finding_count: int
    top_findings: tuple[str, ...]
    est_iterations: int
    # Partial scan fields: set when one or more loops were cut off by the scan timeout.
    # finding_count is a FLOOR when partial=True; the real count is unknown.
    partial: bool = False
    timed_out_loops: tuple[str, ...] = ()
    partial_note: str = ""


def assess(
    loops: list[str],
    *,
    project_root: Path | str,
    scan: ScanFn = scan_phase.scan_loop,
    per_loop_timeout_seconds: float | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Scan each loop without mutating anything; return findings per loop.

    A scanner that crashes contributes an empty list (assessment never aborts on
    one bad scanner).
    """
    out: dict[str, list[dict[str, Any]]] = {}
    for loop in loops:
        try:
            with _scan_deadline(per_loop_timeout_seconds):
                out[loop] = list(scan(loop, project_root=project_root))
        except _ScanDeadlineExpired:
            out[loop] = [
                {
                    "detail": f"scan timed out after {per_loop_timeout_seconds:g}s",
                    "auto_command": "goal-suggest-timeout",
                    "goal_suggest_timeout": True,
                    "severity": "warning",
                }
            ]
        except Exception:  # noqa: BLE001 - a bad scanner must not block the pick list
            logger.debug("assess: scanner for loop %s crashed", loop, exc_info=True)
            out[loop] = []
    return out


def suggest(
    *,
    project_root: Path | str,
    scan: ScanFn = scan_phase.scan_loop,
    specs: list[goal_catalog.GoalSpec] | None = None,
    per_loop_timeout_seconds: float | None = None,
) -> list[GoalSuggestion]:
    """Rank catalog goals by live findings; drop goals with zero findings."""
    specs = specs if specs is not None else goal_catalog.catalog()
    needed = sorted({loop for spec in specs for loop in spec.loops})
    findings_by_loop = assess(
        needed,
        project_root=project_root,
        scan=scan,
        per_loop_timeout_seconds=per_loop_timeout_seconds,
    )

    suggestions: list[GoalSuggestion] = []
    for spec in specs:
        loop_findings = findings_by_loop  # alias for clarity
        # Separate timed-out loops from loops with real findings.
        timed_out: list[str] = []
        spec_findings: list[dict[str, Any]] = []
        for loop in spec.loops:
            loop_data = loop_findings.get(loop, [])
            if any(f.get("goal_suggest_timeout") for f in loop_data):
                timed_out.append(loop)
            else:
                spec_findings.extend(loop_data)

        is_partial = bool(timed_out)
        count = len(spec_findings)

        # Drop only if there are no real findings AND no timed-out loops (truly clean).
        if count == 0 and not is_partial:
            continue

        top = tuple(
            str(f.get("detail") or f.get("title") or f.get("auto_command") or "finding")
            for f in spec_findings[:3]
        )
        est = max(1, -(-count // _FINDINGS_PER_ITERATION)) if count > 0 else 1
        partial_note = (
            f"scan incomplete — {len(timed_out)} loop(s) timed out "
            f"({', '.join(timed_out)}); finding count is a floor, not the truth"
            if is_partial
            else ""
        )
        suggestions.append(
            GoalSuggestion(
                id=spec.id,
                title=spec.title,
                loops=spec.loops,
                finding_count=count,
                top_findings=top,
                est_iterations=est,
                partial=is_partial,
                timed_out_loops=tuple(timed_out),
                partial_note=partial_note,
            )
        )
    suggestions.sort(key=lambda s: (-s.finding_count, s.id))
    return suggestions


@contextlib.contextmanager
def _scan_deadline(seconds: float | None):
    if not seconds or seconds <= 0 or threading.current_thread() is not threading.main_thread():
        yield
        return

    def _raise_timeout(_signum, _frame):
        raise _ScanDeadlineExpired("goal suggestion scan timed out")

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    signal.signal(signal.SIGALRM, _raise_timeout)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])
