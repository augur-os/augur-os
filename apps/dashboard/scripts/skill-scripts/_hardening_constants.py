"""Constants for the Hardening ADR Generator (ADR-065).

Dimension-to-agent mapping, tier model mapping, and scope labels.
"""

from typing import Any

# ---------------------------------------------------------------------------
# Dimension-to-Agent Mapping (ADR-065 Section 5)
# ---------------------------------------------------------------------------

DIMENSION_AGENT_MAP: dict[str, dict[str, Any]] = {
    "ui_compliance": {
        "agent": "frontend",
        "tier": "medium",
        "chains": ["ui_quality_audit", "redesign_page"],
        "label": "UI Compliance",
    },
    "page_coverage": {
        "agent": "developer",
        "tier": "medium",
        "chains": [],
        "label": "Page Coverage",
    },
    "api_completeness": {
        "agent": "developer",
        "tier": "medium",
        "chains": [],
        "label": "API Completeness",
    },
    "mcp_tool_wiring": {
        "agent": "devops",
        "tier": "low",
        "chains": [],
        "label": "MCP Tool Wiring",
    },
    "performance": {
        "agent": "frontend",
        "tier": "medium",
        "chains": [],
        "label": "Performance",
    },
    "user_value": {
        "agent": "architect",
        "tier": "high",
        "chains": [],
        "label": "User Value",
    },
    "workflows": {
        "agent": "developer",
        "tier": "medium",
        "chains": [],
        "label": "Workflows",
    },
    "cross_hub_connectivity": {
        "agent": "developer",
        "tier": "medium",
        "chains": [],
        "label": "Cross-Hub Connectivity",
    },
    "action_buttons": {
        "agent": "frontend",
        "tier": "medium",
        "chains": [],
        "label": "Action Buttons",
    },
    "wow_effect": {
        "agent": "developer",
        "tier": "high",
        "chains": [],
        "label": "Wow Effect",
    },
}

TIER_MODEL_MAP = {
    "low": "haiku",
    "medium": "sonnet",
    "high": "opus",
}

SCOPE_LABELS = {
    "all_phases": "All Phases",
    "critical_only": "Critical Only",
    "critical_plus_completeness": "Critical + Completeness",
}
