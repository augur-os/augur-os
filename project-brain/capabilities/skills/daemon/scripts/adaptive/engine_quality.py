"""Finding-band and outcome classification for adaptive engine fixes.

This module stays intentionally small so the fix pipeline can depend on it
without pulling in reporting, prompting, or write-side concerns.
"""
from __future__ import annotations

from typing import Any, Literal

FindingBand = Literal["mechanical", "local-semantic", "structural"]
FixOutcome = Literal[
    "auto-fixed",
    "report-only",
    "blocked-needs-design",
    "design-written",
    "design-gated-fixed",
    "verification-failed-reverted",
    "context-insufficient",
    "clean",
    "broken",
]

MECHANICAL: FindingBand = "mechanical"
LOCAL_SEMANTIC: FindingBand = "local-semantic"
STRUCTURAL: FindingBand = "structural"

OUTCOMES: frozenset[str] = frozenset(
    {
        "auto-fixed",
        "report-only",
        "blocked-needs-design",
        "design-written",
        "design-gated-fixed",
        "verification-failed-reverted",
        "context-insufficient",
        "clean",
        "broken",
    }
)

_MECHANICAL_FLAGS = (
    "tool_name_mismatch",
    "path_fix",
    "rename_only",
    "formatting_only",
    "typo_only",
)

_STRUCTURAL_FLAGS = (
    "scheduler_change",
    "ownership_change",
    "cross_subsystem",
    "data_source_change",
    "contract_change",
)


def classify_finding_band(issue: dict[str, Any]) -> FindingBand:
    """Classify a finding into a fixability band.

    Mechanical issues are narrow and localized. Structural issues cross
    subsystem or ownership boundaries and should trigger design-gated handling.
    Anything else defaults to local-semantic.
    """
    if issue.get("kind") == "scan-error":
        return MECHANICAL

    for key in _STRUCTURAL_FLAGS:
        if issue.get(key):
            return STRUCTURAL

    for key in _MECHANICAL_FLAGS:
        if issue.get(key):
            return MECHANICAL

    return LOCAL_SEMANTIC


def classify_fix_outcome(
    *,
    success: bool,
    changes: list[Any],
    fix_result: dict[str, Any] | None,
    finding_band: FindingBand,
    design_gate_written: bool,
    reverted: bool,
    context_insufficient: bool,
) -> FixOutcome:
    """Classify the final result of a fix attempt.

    The ordering matters: safety and gating outcomes take precedence over
    success/failure so the caller can report the real reason a change did not
    proceed.
    """
    _ = fix_result  # Reserved for future detail-based refinement.

    if context_insufficient:
        return "context-insufficient"
    if reverted:
        return "verification-failed-reverted"
    if finding_band == STRUCTURAL and not design_gate_written:
        return "blocked-needs-design"
    if success and finding_band == STRUCTURAL and design_gate_written and not changes:
        return "design-written"
    if success and changes and finding_band == STRUCTURAL:
        return "design-gated-fixed"
    if success and changes:
        return "auto-fixed"
    if success:
        return "report-only"
    return "broken"
