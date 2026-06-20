"""Severity routing — deciding which fix strategy to apply."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_self_healer import RegistryEntry


DEFAULT_ROUTING = {
    "critical": "fix",
    "high": "fix",
    "medium": "fix",
    "low": "todo",
    "transient": "dismiss",
}


def route_issue(entry: "RegistryEntry", config: dict) -> str:
    """Determine action based on severity. Returns 'fix', 'todo', or 'dismiss'."""
    routing = {**DEFAULT_ROUTING, **config.get("routing", {})}
    severity = entry.severity.lower()
    return routing.get(severity, "todo")
