"""Report loading and parsing for the Hardening ADR Generator (ADR-065).

Auto-numbering, audit report loading, user choice normalization,
dimension filtering, and conflict detection.
"""

import re
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Auto-Numbering
# ---------------------------------------------------------------------------


def find_next_adr_number(decisions_dir: Path) -> int:
    """Find the next available ADR number from the central index (ADR-642).

    Falls back to scanning ``ADR-*.md`` filenames in the decisions dir for
    environments that haven't migrated yet.
    """
    try:
        from src.lib.adr_utils import find_next_adr_number as _canonical

        return _canonical(decisions_dir)
    except Exception:
        max_num = 0
        if decisions_dir.is_dir():
            for f in decisions_dir.iterdir():
                match = re.match(r"ADR-(\d+)", f.name)
                if match:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
        return max_num + 1


def parse_adr_number_from_path(path: Path) -> int | None:
    """Extract ADR number from a file path like ADR-202-*.md."""
    match = re.search(r"ADR-(\d+)", path.name, re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def parse_adr_slug_from_path(path: Path) -> str | None:
    """Extract ADR slug from a filename like ADR-202-ai-hardening.md."""
    match = re.search(r"ADR-\d+-(.+)\.md$", path.name, re.IGNORECASE)
    if not match:
        return None
    slug = match.group(1).strip().lower()
    if slug.endswith("-hardening"):
        slug = slug[: -len("-hardening")]
    return slug or None


# ---------------------------------------------------------------------------
# Report Loading
# ---------------------------------------------------------------------------


def load_audit_report(audit_path: Path) -> dict[str, Any]:
    """Load and parse a hardening audit YAML report."""
    import yaml

    content = audit_path.read_text(encoding="utf-8")
    return yaml.safe_load(content) or {}


def _normalize_scope(raw_scope: str) -> str:
    normalized = raw_scope.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"critical", "critical_only"}:
        return "critical_only"
    if normalized in {"critical_plus_completeness", "critical_and_completeness"}:
        return "critical_plus_completeness"
    return "all_phases"


def _normalize_skip_dimensions(raw_skip: Any) -> list[str]:
    if isinstance(raw_skip, list):
        return [str(item).strip() for item in raw_skip if str(item).strip()]
    if isinstance(raw_skip, str):
        return [item.strip() for item in raw_skip.split(",") if item.strip()]
    return []


def get_user_choices(report: dict[str, Any]) -> dict[str, Any]:
    """Get normalized user choices from audit report metadata."""
    raw = report.get("user_choices", {}) or {}
    return {
        "scope": _normalize_scope(str(raw.get("scope", "all_phases"))),
        "skip_dimensions": _normalize_skip_dimensions(raw.get("skip_dimensions", [])),
        "wow_effect": str(raw.get("wow_effect", "")).strip(),
        "notes": str(raw.get("notes", "")).strip(),
        "choice_source": str(raw.get("choice_source", "")).strip(),
    }


def get_selected_dimensions(report: dict[str, Any]) -> dict[str, Any]:
    """Filter dimensions based on user scope + skip settings."""
    dimensions = report.get("dimensions", {})
    choices = get_user_choices(report)
    scope = choices["scope"]
    skip_dims = set(choices["skip_dimensions"])

    selected: dict[str, Any] = {}
    for dim_id, dim_data in dimensions.items():
        score = int(dim_data.get("score", 100))

        if scope == "critical_only":
            include = dim_id == "wow_effect" or score < 50
        elif scope == "critical_plus_completeness":
            include = dim_id == "wow_effect" or score < 70
        else:
            include = score < 90 or dim_id == "wow_effect"

        if include and dim_id not in skip_dims:
            selected[dim_id] = dim_data

    return selected


def _dimension_label_map(report: dict[str, Any]) -> dict[str, str]:
    dimensions = report.get("dimensions", {})
    return {dim_id: str(dim_data.get("label", dim_id)) for dim_id, dim_data in dimensions.items()}


def _parse_action_ratio(findings: list[str], patterns: list[str]) -> tuple[int, int] | None:
    for finding in findings:
        for pattern in patterns:
            match = re.search(pattern, str(finding), re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1)), int(match.group(2))
                except Exception:
                    continue
    return None


def _action_signal_conflict_note(report: dict[str, Any]) -> str | None:
    """Detect contradictory action findings across dimensions and return a note."""
    dims = report.get("dimensions", {})
    user_value = dims.get("user_value", {})
    workflows = dims.get("workflows", {})
    action_buttons = dims.get("action_buttons", {})
    user_findings = [str(f) for f in user_value.get("findings", [])]
    workflow_findings = [str(f) for f in workflows.get("findings", [])]

    # Reconciled semantics:
    # - User Value tracks autonomous outcomes
    # - Workflows tracks functional/usable execution paths (includes IDE-assisted actions)
    # If findings already state this distinction, do not force a reconciliation phase.
    semantics_explicit = any(
        "ide-assisted" in f.lower() or "not counted as autonomous" in f.lower()
        for f in user_findings
    )
    workflow_scope_explicit = any("working backends" in f.lower() for f in workflow_findings)

    user_ratio = _parse_action_ratio(
        user_findings,
        [
            r"(\d+)\s*/\s*(\d+)\s*actions have autonomous backends",
            r"(\d+)\s*/\s*(\d+)\s*actions have real backends",
        ],
    )
    workflow_ratio = _parse_action_ratio(
        workflow_findings,
        [r"(\d+)\s*/\s*(\d+)\s*actions have working backends"],
    )
    button_ratio = _parse_action_ratio(
        action_buttons.get("findings", []),
        [r"(\d+)\s*/\s*(\d+)\s*actions are"],
    )

    if user_ratio and workflow_ratio and user_ratio[1] == workflow_ratio[1] and user_ratio[0] != workflow_ratio[0]:
        if semantics_explicit and workflow_scope_explicit and workflow_ratio[0] >= user_ratio[0]:
            return None
        return (
            "Action metrics use different semantics across dimensions "
            f"(User Value: {user_ratio[0]}/{user_ratio[1]} autonomous, "
            f"Workflows: {workflow_ratio[0]}/{workflow_ratio[1]} functional). "
            "Reconcile this classification during implementation."
        )

    if workflow_ratio and button_ratio and workflow_ratio[1] == button_ratio[1] and workflow_ratio[0] > button_ratio[0]:
        return (
            "Workflow functional-action count exceeds action-button quality count. "
            "Validate action definitions and scoring assumptions."
        )

    return None
