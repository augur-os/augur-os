"""Wiki report agent-step contract.

Single source of truth for the rich-dict shape that the agent step must
produce. The contract has three surfaces:

1. ``SYNTHESIS_SCHEMA`` from this module, returned by ``wiki-report-data``.
2. ``/wiki report`` action docs, the narrative contract for the agent.
3. ``validate_rich_dict`` from this module, enforced by ``wiki-report-generate``.

Designed so the validator is testable in isolation, without MCP plumbing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Schema version. Bump on breaking contract changes.
SCHEMA_VERSION = 1

SYNTHESIS_MIN_LEN = 100
SYNTHESIS_MAX_LEN = 400
HUB_SUMMARY_MIN_LEN = 60
HUB_SUMMARY_MAX_LEN = 200

ALLOWED_SEVERITIES = frozenset({"low", "medium", "high"})
ALLOWED_EXPERTISE_LEVELS = frozenset({"Expert", "Advanced", "Intermediate", "Building", "Beginner"})

# JSON-shape description of what the agent step must produce.
SYNTHESIS_SCHEMA: dict[str, Any] = {
    "version": SCHEMA_VERSION,
    "required": [
        {"path": "synthesis", "type": "string", "min_len": SYNTHESIS_MIN_LEN, "max_len": SYNTHESIS_MAX_LEN},
        {
            "path": "hub_sections[*].summary",
            "type": "string",
            "min_len": HUB_SUMMARY_MIN_LEN,
            "max_len": HUB_SUMMARY_MAX_LEN,
        },
    ],
    "optional": [
        {"path": "who_you_are.what_you_do", "type": "string"},
        {"path": "who_you_are.how_you_think", "type": "string"},
        {
            "path": "expertise[*]",
            "shape": {
                "domain": "string",
                "level": "enum:Expert|Advanced|Intermediate|Building|Beginner",
                "percentage": "int:0-100",
                "color": "hex",
            },
        },
        {
            "path": "patterns[*]",
            "shape": {
                "title": "string",
                "description": "string",
            },
        },
        {
            "path": "blind_spots[*]",
            "shape": {
                "title": "string",
                "description": "string",
                "severity": "enum:low|medium|high",
            },
        },
    ],
    "passed_through": [
        {"path": "stats", "from": "raw_data.stats"},
        {"path": "portfolio", "from": "raw_data.portfolio"},
    ],
}


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a rich dict."""

    success: bool
    missing_required: list[str] = field(default_factory=list)


def validate_rich_dict(report: dict[str, Any]) -> ValidationResult:
    """Validate the rich dict for ``wiki-report-generate``.

    Collects every failing required field; does not short-circuit on first
    failure. Missing optional fields produce success.
    """
    missing: list[str] = []

    synthesis = report.get("synthesis")
    if not isinstance(synthesis, str) or not (SYNTHESIS_MIN_LEN <= len(synthesis) <= SYNTHESIS_MAX_LEN):
        missing.append("synthesis")

    hub_sections = report.get("hub_sections")
    if not isinstance(hub_sections, list) or not hub_sections:
        missing.append("hub_sections")
    else:
        for i, hub in enumerate(hub_sections):
            if not isinstance(hub, dict):
                missing.append(f"hub_sections[{i}]")
                continue
            summary = hub.get("summary")
            if not isinstance(summary, str) or not (HUB_SUMMARY_MIN_LEN <= len(summary) <= HUB_SUMMARY_MAX_LEN):
                missing.append(f"hub_sections[{i}].summary")

    blind_spots = report.get("blind_spots")
    if isinstance(blind_spots, list):
        for i, spot in enumerate(blind_spots):
            if not isinstance(spot, dict):
                continue
            severity = spot.get("severity")
            if severity is not None and severity not in ALLOWED_SEVERITIES:
                missing.append(f"blind_spots[{i}].severity")

    expertise = report.get("expertise")
    if isinstance(expertise, list):
        for i, item in enumerate(expertise):
            if not isinstance(item, dict):
                continue
            pct = item.get("percentage")
            if pct is not None and not (isinstance(pct, int) and 0 <= pct <= 100):
                missing.append(f"expertise[{i}].percentage")
            level = item.get("level")
            if level is not None and level not in ALLOWED_EXPERTISE_LEVELS:
                missing.append(f"expertise[{i}].level")

    return ValidationResult(success=len(missing) == 0, missing_required=missing)


def hub_sections_skeleton(hubs: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive the hub_sections list-of-dicts skeleton from raw hub metadata."""

    def source_count(item: tuple[str, Any]) -> int:
        meta = item[1]
        if isinstance(meta, dict):
            value = meta.get("source_count", 0)
            return value if isinstance(value, int) else 0
        return 0

    return [
        {
            "name": name,
            "source_count": source_count((name, hub_meta)),
        }
        for name, hub_meta in sorted(hubs.items(), key=source_count, reverse=True)
    ]
