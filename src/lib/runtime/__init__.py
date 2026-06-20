"""Runtime telemetry and threshold helpers.

Migrated from project-brain/capabilities/skills/daemon/augur/lib/ in Track 1 of the cross-client
bundle architecture migration. The daemon bundle keeps its scripts/
subsystem (adaptive loop engine, monitors, ops, self-heal) — only these
runtime/telemetry helpers move here so external consumers such as MCP
settings tools can import them via a clean Python path.

Public API:
    TaskRecord (dataclass), record_task, get_aggregates, compact
        Performance ledger for agent task tracking (ADR-460).

    AUTONOMY_THRESHOLDS, LEARNING_THRESHOLDS,
    AUTONOMY_LEVELS, LEARNING_LEVELS,
    get_action_required_level, get_learning_behavior_at_level,
    is_behavior_enabled
        Shared behavior threshold definitions for dashboard and
        orchestrator sync.
"""

from __future__ import annotations

from src.lib.runtime.behavior_thresholds import (
    AUTONOMY_LEVELS,
    AUTONOMY_THRESHOLDS,
    LEARNING_LEVELS,
    LEARNING_THRESHOLDS,
    get_action_required_level,
    get_learning_behavior_at_level,
    is_behavior_enabled,
)
from src.lib.runtime.performance_ledger import (
    TaskRecord,
    compact,
    get_aggregates,
    record_task,
)

__all__ = [
    # Performance ledger
    "TaskRecord",
    "compact",
    "get_aggregates",
    "record_task",
    # Behavior thresholds
    "AUTONOMY_LEVELS",
    "AUTONOMY_THRESHOLDS",
    "LEARNING_LEVELS",
    "LEARNING_THRESHOLDS",
    "get_action_required_level",
    "get_learning_behavior_at_level",
    "is_behavior_enabled",
]
