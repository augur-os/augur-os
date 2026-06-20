"""ADR section generators for the Hardening ADR Generator (ADR-065).

Generates metadata, audit summary, wow effect, context, decision,
and consequences sections of the hardening ADR.
"""

from datetime import datetime
from typing import Any

from ._hardening_constants import SCOPE_LABELS
from ._hardening_report import (
    _action_signal_conflict_note,
    _dimension_label_map,
    get_selected_dimensions,
    get_user_choices,
)


# ---------------------------------------------------------------------------
# ADR Section Generators
# ---------------------------------------------------------------------------


def generate_metadata(adr_number: int, hub_title: str) -> str:
    """Generate ADR metadata header."""
    date = datetime.now().strftime("%Y-%m-%d")
    return f"""# ADR-{adr_number:03d}: {hub_title} Hardening

**Status**: Proposed
**Date**: {date}
**Deciders**: Project team
**Related**: ADR-065 (dashboard hardening workflow automation)
"""


def generate_audit_summary(report: dict[str, Any]) -> str:
    """Generate the audit summary table from dimension scores."""
    lines = [
        "## Audit Summary",
        "",
        "| # | Dimension | Score | Weight | Status | Key Finding |",
        "|---|-----------|-------|--------|--------|-------------|",
    ]

    dimensions = report.get("dimensions", {})
    for i, (dim_id, dim_data) in enumerate(dimensions.items(), 1):
        label = dim_data.get("label", dim_id)
        score = dim_data.get("score", 0)
        weight = dim_data.get("weight", 0)
        status = dim_data.get("status", "unknown")
        findings = dim_data.get("findings", [])
        key_finding = findings[0] if findings else "-"
        # Truncate long findings for the table
        if len(key_finding) > 60:
            key_finding = key_finding[:57] + "..."
        lines.append(f"| {i} | {label} | {score}/100 | {weight}% | {status} | {key_finding} |")

    composite = report.get("composite_score", 0)
    interpretation = report.get("interpretation", "unknown")
    lines.append("")
    lines.append(f"**Composite Score**: {composite}/100 ({interpretation})")
    conflict_note = _action_signal_conflict_note(report)
    if conflict_note:
        lines.append("")
        lines.append(f"**Scoring Confidence Note**: {conflict_note}")
    lines.append("")

    return "\n".join(lines)


def generate_wow_effect_section(report: dict[str, Any]) -> str:
    """Generate the wow effect section from the audit report."""
    wow = report.get("wow_effect", {})
    name = wow.get("name", "Not identified")
    description = wow.get("description", "")
    score = wow.get("score", 0)
    flow_steps = wow.get("flow_steps", [])
    current_state = wow.get("current_state", "")
    gap = wow.get("gap", "")
    cross_hub = wow.get("cross_hub_leverage", [])
    candidates = wow.get("candidate_actions", [])
    runtime_bonus = int(wow.get("runtime_bonus", 0) or 0)
    expected_output = wow.get("expected_output", "")
    base_score = wow.get("base_score")
    if base_score is None:
        base_score = next((c.get("score", 0) for c in candidates if c.get("name") == name), None)

    lines = [
        f"## Wow Effect: {name}",
        "",
    ]

    if description:
        lines.append(f"> {description}")
        lines.append("")

    lines.append(f"**Score**: {score}/100")
    lines.append("")
    if base_score is not None:
        lines.append(f"**Score breakdown**: static evidence {base_score}/100 + runtime bonus {runtime_bonus} = {score}/100")
        lines.append("")

    if flow_steps:
        lines.append("**Demo Flow**:")
        for i, step in enumerate(flow_steps, 1):
            lines.append(f"{i}. {step}")
        lines.append("")

    if expected_output:
        lines.append(f"**Expected visible output**: {expected_output}")
        lines.append("")

    if current_state:
        lines.append(f"**Current state**: {current_state}")
    if gap:
        lines.append(f"**Gap to demo-ready**: {gap}")
    lines.append("")

    if cross_hub:
        lines.append(f"**Cross-hub leverage**: Pulls data from {', '.join(cross_hub)}")
        lines.append("")

    if candidates and len(candidates) > 1:
        lines.append("**Other candidates**:")
        for c in candidates[1:]:
            lines.append(f"- {c.get('name', '?')} ({c.get('score', 0)}/100, {c.get('type', '')})")
        lines.append("")

    lines.append("**Priority**: This is the first thing to implement in Phase 1.")
    lines.append("")

    return "\n".join(lines)


def generate_context(report: dict[str, Any]) -> str:
    """Generate the Context section based on audit findings."""
    hub_title = report.get("audit", {}).get("hub_title", "Unknown")
    hub_url = report.get("audit", {}).get("url", "")
    timestamp = report.get("audit", {}).get("timestamp", "")
    composite = report.get("composite_score", 0)
    dimensions = report.get("dimensions", {})

    lines = [
        "## Context",
        "",
        f"Automated hardening audit of **{hub_title}** ({hub_url}) on {timestamp[:10]}.",
        f"Composite score: **{composite}/100**.",
        "",
    ]

    # List dimensions scoring below 70 as problems
    problems = [(dim_id, dim_data) for dim_id, dim_data in dimensions.items() if dim_data.get("score", 100) < 70]

    if problems:
        lines.append("### Issues Identified")
        lines.append("")
        for dim_id, dim_data in problems:
            label = dim_data.get("label", dim_id)
            score = dim_data.get("score", 0)
            findings = dim_data.get("findings", [])
            lines.append(f"**{label}** ({score}/100):")
            for finding in findings[:3]:
                lines.append(f"- {finding}")
            lines.append("")
    else:
        lines.append("All dimensions are scoring 70 or above. This hub is in good shape")
        lines.append("and only needs targeted polish.")
        lines.append("")

    return "\n".join(lines)


def _group_dimensions_by_phase(dimensions: dict[str, Any]) -> dict[str, list[tuple[str, dict[str, Any]]]]:
    """Group dimensions into phases based on score thresholds.

    Phase 1 (Critical): score < 50 + wow effect
    Phase 2 (Completeness): 50 <= score < 70
    Phase 3 (Polish): 70 <= score < 90
    Skipped: score >= 90
    """
    phases: dict[str, list[tuple[str, dict[str, Any]]]] = {
        "phase1": [],
        "phase2": [],
        "phase3": [],
    }

    for dim_id, dim_data in dimensions.items():
        score = dim_data.get("score", 100)
        if dim_id == "wow_effect":
            # Wow effect always goes in Phase 1
            phases["phase1"].insert(0, (dim_id, dim_data))
        elif score < 50:
            phases["phase1"].append((dim_id, dim_data))
        elif score < 70:
            phases["phase2"].append((dim_id, dim_data))
        elif score < 90:
            phases["phase3"].append((dim_id, dim_data))
        # score >= 90 -> skip

    return phases


def _build_execution_phases(report: dict[str, Any], dimensions: dict[str, Any]) -> list[dict[str, Any]]:
    """Build ordered execution phases with sequential display numbers."""
    grouped = _group_dimensions_by_phase(dimensions)
    phases: list[dict[str, Any]] = []

    conflict_note = _action_signal_conflict_note(report)
    if conflict_note:
        phases.append(
            {
                "key": "reconciliation",
                "title": "Scoring Reconciliation",
                "dims": [],
                "conflict_note": conflict_note,
            }
        )

    phase_names = {
        "phase1": "Wow Effect & Critical Gaps",
        "phase2": "Completeness",
        "phase3": "Polish & Performance",
    }
    for phase_key in ["phase1", "phase2", "phase3"]:
        dims = grouped[phase_key]
        if not dims:
            continue
        phases.append(
            {
                "key": phase_key,
                "title": phase_names[phase_key],
                "dims": dims,
                "conflict_note": None,
                "provisional": bool(conflict_note),
            }
        )

    for index, phase in enumerate(phases, start=1):
        phase["display_num"] = index

    return phases


def generate_decision(report: dict[str, Any]) -> str:
    """Generate the Decision section with phased implementation."""
    dimensions = get_selected_dimensions(report)
    user_choices = get_user_choices(report)
    phases = _build_execution_phases(report, dimensions)
    active_phase_count = len(phases)
    phase_word = "phase" if active_phase_count == 1 else "phases"

    lines = [
        "## Decision",
        "",
        f"Implement hardening in {active_phase_count} {phase_word}, ordered by severity and user impact.",
        "",
    ]
    lines.append(f"User-selected scope: **{SCOPE_LABELS.get(user_choices['scope'], user_choices['scope'])}**.")
    if user_choices["skip_dimensions"]:
        labels = _dimension_label_map(report)
        skip_labels = [labels.get(dim_id, dim_id) for dim_id in user_choices["skip_dimensions"]]
        lines.append(f"Skipped dimensions: {', '.join(skip_labels)}.")
    lines.append("")

    for phase in phases:
        phase_num = int(phase.get("display_num", 0) or 0)
        phase_key = str(phase.get("key", ""))
        phase_label = str(phase.get("title", ""))
        lines.append(f"### Phase {phase_num}: {phase_label}")
        lines.append("")

        if phase_key == "reconciliation":
            conflict_note = str(phase.get("conflict_note", "")).strip()
            lines.append("**Action scoring conflict (must resolve first):**")
            lines.append(f"- {conflict_note}")
            lines.append("- Define one canonical action-state rubric shared by User Value, Workflows, and Action Buttons")
            lines.append("- Recompute findings so action counts align before planning execution tasks")
            lines.append("")
            continue

        if phase.get("provisional"):
            lines.append(
                "Provisional phase: re-run the audit and regenerate this ADR after Phase 1 reconciliation before execution."
            )
            lines.append("")

        dims = phase.get("dims", [])
        for dim_id, dim_data in dims:
            label = dim_data.get("label", dim_id)
            score = dim_data.get("score", 0)
            findings = dim_data.get("findings", [])
            lines.append(f"**{label}** (current: {score}/100):")
            for finding in findings[:3]:
                lines.append(f"- {finding}")
            lines.append("")

    return "\n".join(lines)


def generate_consequences(report: dict[str, Any]) -> str:
    """Generate the Consequences section."""
    hub_title = report.get("audit", {}).get("hub_title", "Unknown")
    dimensions = get_selected_dimensions(report)
    phases = _group_dimensions_by_phase(dimensions)

    # Count selected implementation targets (wow_effect is always a target when selected).
    dims_needing_work = sum(
        1
        for dim_id, d in dimensions.items()
        if dim_id == "wow_effect" or d.get("score", 100) < 90
    )

    lines = [
        "## Consequences",
        "",
        "### Positive",
        "",
        f"- {hub_title} hub upgraded with standardized hardening across {dims_needing_work} dimensions",
    ]

    phase1_critical_dims = [
        dim_id for dim_id, dim_data in phases["phase1"] if dim_id != "wow_effect" and int(dim_data.get("score", 100)) < 50
    ]
    if phase1_critical_dims:
        lines.append("- Critical gaps addressed in Phase 1, enabling demo-ready wow effect")
    elif any(dim_id == "wow_effect" for dim_id, _ in phases["phase1"]):
        lines.append("- Phase 1 preserves and validates the wow-effect demo flow")
    if report.get("wow_effect", {}).get("name"):
        lines.append(f"- Killer demo use case identified: {report['wow_effect']['name']}")

    lines.extend(
        [
            "",
            "### Negative",
            "",
            f"- Requires implementation effort across {dims_needing_work} dimensions",
        ]
    )

    selected_dim_ids = set(dimensions.keys())
    if {"performance", "cross_hub_connectivity", "wow_effect"} & selected_dim_ids:
        lines.append("- Some dimensions may require runtime testing (performance, cross-hub connectivity)")

    lines.extend(
        [
            "",
            "### Neutral",
            "",
            "- Existing working features remain untouched",
            "- Audit report stored for trend tracking",
            "",
        ]
    )

    return "\n".join(lines)
