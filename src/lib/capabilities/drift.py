"""Capability drift guardrail — 9 dimensions per ADR-734 Phase 3 spec.

Augur-generated regressions (D1, D2, D3, D4, D7, D8, D9) raise FAIL.
External/unmanaged drift (D5, D6) raises WARN.

Dimensions:
    D1 direct_mcp_exposure       — generated MCP surface without policy export_to: mcp
    D2 unclassified_export       — unclassified capability exported to a client target
    D3 blocked_present           — blocked capability still present in any generated surface
    D4 unexpected_client         — exposed to client not in export_to
    D5 duplicate_external_skill  — same skill name across multiple external clients (warn)
    D6 draft_leakage             — staged/draft skill surfaced as active in a client dir
    D7 agents_md_drift           — AGENTS.md capability table disagrees with policy
    D8 client_budget_blowout     — generated tool/skill count exceeds client budget
    D9 invalid_primary_surface   — primary_surface is not a canonical surface name
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .drafts import find_draft_leftovers
from .duplicates import find_external_skill_duplicates
from .exposure_policy import CapabilityRecord


class Severity(Enum):
    FAIL = "fail"
    WARN = "warn"


@dataclass(frozen=True)
class DriftFinding:
    dimension: str
    capability_id: str
    severity: Severity
    message: str
    surface: str

    def is_failure(self) -> bool:
        return self.severity is Severity.FAIL


_CLIENT_TARGETS = frozenset({"claude", "codex", "gemini", "opencode", "cursor", "copilot"})
_VALID_PRIMARY_SURFACES = frozenset({"cli", "mcp", "mcp via dashboard", "skill", "command", "workflow"})

_CLIENT_DIR_TUPLES = (
    (".claude", "claude"),
    (".codex", "codex"),
    (".gemini", "gemini"),
    (".opencode", "opencode"),
)


def detect_direct_mcp_exposure(records: Iterable[CapabilityRecord]) -> list[DriftFinding]:
    """D1: generated MCP surface without policy export_to: mcp."""
    findings: list[DriftFinding] = []
    for record in records:
        if record.owner_kind not in {"augur", "user"}:
            continue
        if record.management != "generated":
            continue
        if "mcp" not in record.current_exposure:
            continue
        if "mcp" in record.export_to:
            continue
        severity = Severity.WARN if record.owner_kind == "user" else Severity.FAIL
        findings.append(
            DriftFinding(
                dimension="direct_mcp_exposure",
                capability_id=record.id,
                severity=severity,
                message="generated MCP surface without policy export_to: mcp",
                surface="mcp",
            )
        )
    return findings


def detect_unclassified_export(records: Iterable[CapabilityRecord]) -> list[DriftFinding]:
    """D2: unclassified capability exported to a client target."""
    findings: list[DriftFinding] = []
    for record in records:
        if record.owner_kind != "augur" or record.management != "generated":
            continue
        if record.classification_status != "unclassified":
            continue
        for client in record.current_exposure:
            if client in _CLIENT_TARGETS:
                findings.append(
                    DriftFinding(
                        dimension="unclassified_export",
                        capability_id=record.id,
                        severity=Severity.FAIL,
                        message=f"unclassified capability exported to {client}",
                        surface=client,
                    )
                )
    return findings


def detect_blocked_present(records: Iterable[CapabilityRecord]) -> list[DriftFinding]:
    """D3: blocked capability still present in any generated surface."""
    findings: list[DriftFinding] = []
    for record in records:
        if record.owner_kind != "augur" or record.management != "generated":
            continue
        if record.classification_status != "blocked":
            continue
        for surface in record.current_exposure:
            findings.append(
                DriftFinding(
                    dimension="blocked_present",
                    capability_id=record.id,
                    severity=Severity.FAIL,
                    message="blocked capability present in generated surface",
                    surface=surface,
                )
            )
    return findings


def detect_unexpected_client(records: Iterable[CapabilityRecord]) -> list[DriftFinding]:
    """D4: exposed to client not in export_to."""
    findings: list[DriftFinding] = []
    for record in records:
        if record.owner_kind != "augur" or record.management != "generated":
            continue
        if record.classification_status != "approved":
            continue
        for surface in record.current_exposure:
            if surface not in _CLIENT_TARGETS:
                continue
            if surface in record.export_to:
                continue
            findings.append(
                DriftFinding(
                    dimension="unexpected_client",
                    capability_id=record.id,
                    severity=Severity.FAIL,
                    message=f"exposed to {surface} but export_to forbids it",
                    surface=surface,
                )
            )
    return findings


def detect_duplicate_external_skills(
    project_root: Path,
    multi_client_approved: set[str],
) -> list[DriftFinding]:
    """D5: same skill name across multiple external clients (warn unless approved)."""
    findings: list[DriftFinding] = []
    for name, clients in find_external_skill_duplicates(project_root):
        if name in multi_client_approved:
            continue
        findings.append(
            DriftFinding(
                dimension="duplicate_external_skill",
                capability_id=f"skill:{name}",
                severity=Severity.WARN,
                message=f"external skill duplicated across {', '.join(clients)}",
                surface=",".join(clients),
            )
        )
    return findings


def detect_draft_leakage(project_root: Path) -> list[DriftFinding]:
    """D6: staged/draft skill surfaced as active in a client dir."""
    draft_names = {p.stem.replace(".draft", "") for p in find_draft_leftovers(project_root)}
    findings: list[DriftFinding] = []
    for dirname, client in _CLIENT_DIR_TUPLES:
        skills_dir = project_root / dirname / "skills"
        if not skills_dir.is_dir():
            continue
        for child in skills_dir.iterdir():
            if child.is_dir() and child.name in draft_names:
                findings.append(
                    DriftFinding(
                        dimension="draft_leakage",
                        capability_id=f"skill:{child.name}",
                        severity=Severity.FAIL,
                        message=f"draft surfaced as active skill in {client}",
                        surface=client,
                    )
                )
    return findings


_TABLE_ROW = re.compile(r"^\|\s*`(?P<id>[^`]+)`\s*\|.*?\|\s*(?P<surface>[^|]+?)\s*\|")

_SURFACE_LABEL_MAP = {
    "mcp": "mcp via dashboard",
    "cli": "cli via shell",
    "command": "command",
    "skill": "skill",
    "workflow": "workflow",
}


def _expected_surface_label(record: CapabilityRecord) -> str:
    if record.primary_surface == "skill":
        preferred_client = str(record.preferred_client or "").strip()
        if preferred_client and preferred_client != "none":
            return f"skill via {preferred_client}"
    return _SURFACE_LABEL_MAP.get(record.primary_surface, "")


def detect_agents_md_drift(
    agents_md_path: Path,
    records: Iterable[CapabilityRecord],
) -> list[DriftFinding]:
    """D7: AGENTS.md capability table disagrees with policy primary_surface."""
    if not agents_md_path.is_file():
        return []
    by_id = {record.id: record for record in records}
    findings: list[DriftFinding] = []
    for line in agents_md_path.read_text(encoding="utf-8").splitlines():
        match = _TABLE_ROW.match(line)
        if not match:
            continue
        cap_id = match.group("id").strip()
        surface = match.group("surface").strip()
        record = by_id.get(cap_id)
        if record is None:
            continue
        expected_surface = _expected_surface_label(record)
        if expected_surface and expected_surface != surface:
            findings.append(
                DriftFinding(
                    dimension="agents_md_drift",
                    capability_id=cap_id,
                    severity=Severity.FAIL,
                    message=(
                        f"AGENTS.md says '{surface}' but policy primary_surface is " f"'{record.primary_surface}'"
                    ),
                    surface="agents-md",
                )
            )
    return findings


def detect_client_budget_blowout(
    records: Iterable[CapabilityRecord],
    budgets: dict[str, int],
) -> list[DriftFinding]:
    """D8: generated tool/skill count exceeds client budget."""
    counts: dict[str, int] = {client: 0 for client in budgets}
    for record in records:
        if record.owner_kind != "augur" or record.management != "generated":
            continue
        for client in budgets:
            if client in record.current_exposure:
                counts[client] += 1
    findings: list[DriftFinding] = []
    for client, budget in budgets.items():
        if counts[client] > budget:
            findings.append(
                DriftFinding(
                    dimension="client_budget_blowout",
                    capability_id=f"client:{client}",
                    severity=Severity.FAIL,
                    message=(f"{client} has {counts[client]} generated tools/skills; " f"budget is {budget}"),
                    surface=client,
                )
            )
    return findings


def detect_invalid_primary_surface(records: Iterable[CapabilityRecord]) -> list[DriftFinding]:
    """D9: primary_surface must use canonical surface names."""
    findings: list[DriftFinding] = []
    for record in records:
        if record.primary_surface in _VALID_PRIMARY_SURFACES:
            continue
        severity = Severity.WARN if record.owner_kind == "user" else Severity.FAIL
        findings.append(
            DriftFinding(
                dimension="invalid_primary_surface",
                capability_id=record.id,
                severity=severity,
                message=f"invalid primary_surface {record.primary_surface!r}",
                surface=record.primary_surface,
            )
        )
    return findings


def run_all_drift_checks(
    records: list[CapabilityRecord],
    *,
    project_root: Path,
    agents_md_path: Path,
    budgets: dict[str, int],
    multi_client_approved: set[str],
) -> dict[str, object]:
    """Run all 9 drift dimensions and return an aggregated JSON-serializable report."""
    findings: list[DriftFinding] = []
    findings.extend(detect_direct_mcp_exposure(records))
    findings.extend(detect_unclassified_export(records))
    findings.extend(detect_blocked_present(records))
    findings.extend(detect_unexpected_client(records))
    findings.extend(detect_duplicate_external_skills(project_root, multi_client_approved))
    findings.extend(detect_draft_leakage(project_root))
    findings.extend(detect_agents_md_drift(agents_md_path, records))
    findings.extend(detect_invalid_primary_surface(records))
    findings.extend(detect_client_budget_blowout(records, budgets))
    return {
        "findings": [
            {
                "dimension": f.dimension,
                "capability_id": f.capability_id,
                "severity": f.severity.value,
                "message": f.message,
                "surface": f.surface,
            }
            for f in findings
        ],
        "fail_count": sum(1 for f in findings if f.is_failure()),
        "warn_count": sum(1 for f in findings if not f.is_failure()),
    }
