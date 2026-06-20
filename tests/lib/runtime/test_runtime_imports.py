"""Smoke tests for the src.lib.runtime public API.

Verifies the migrated runtime helpers (performance ledger + behavior thresholds)
are reachable via clean Python imports. Functional behavior is covered by the
existing skill-side tests in project-brain/capabilities/skills/daemon/augur/tests/.
"""

from __future__ import annotations


def test_public_api_importable():
    """All 11 documented public symbols are importable from src.lib.runtime."""
    from src.lib.runtime import (  # noqa: F401
        AUTONOMY_LEVELS,
        AUTONOMY_THRESHOLDS,
        LEARNING_LEVELS,
        LEARNING_THRESHOLDS,
        TaskRecord,
        compact,
        get_action_required_level,
        get_aggregates,
        get_learning_behavior_at_level,
        is_behavior_enabled,
        record_task,
    )


def test_performance_ledger_origin():
    """Performance ledger symbols originate in src.lib.runtime.performance_ledger."""
    from src.lib.runtime import TaskRecord, record_task, compact, get_aggregates

    assert TaskRecord.__module__ == "src.lib.runtime.performance_ledger"
    assert record_task.__module__ == "src.lib.runtime.performance_ledger"
    assert compact.__module__ == "src.lib.runtime.performance_ledger"
    assert get_aggregates.__module__ == "src.lib.runtime.performance_ledger"


def test_behavior_thresholds_origin():
    """Behavior threshold symbols originate in src.lib.runtime.behavior_thresholds."""
    from src.lib.runtime import (
        get_action_required_level,
        get_learning_behavior_at_level,
        is_behavior_enabled,
    )

    assert get_action_required_level.__module__ == "src.lib.runtime.behavior_thresholds"
    assert get_learning_behavior_at_level.__module__ == "src.lib.runtime.behavior_thresholds"
    assert is_behavior_enabled.__module__ == "src.lib.runtime.behavior_thresholds"


def test_task_record_is_dataclass():
    """TaskRecord is the dataclass consumers expect."""
    from dataclasses import is_dataclass, fields

    from src.lib.runtime import TaskRecord

    assert is_dataclass(TaskRecord)
    field_names = {f.name for f in fields(TaskRecord)}
    # Documented fields per the original definition:
    expected_fields = {
        "id",
        "timestamp",
        "agent",
        "tier",
        "model",
        "tokens_in",
        "tokens_out",
        "duration_seconds",
        "files_edited",
        "files_created",
        "outcome",
        "task_signals",
    }
    assert expected_fields.issubset(field_names), f"TaskRecord missing expected fields. Got: {field_names}"


def test_autonomy_thresholds_is_list():
    """AUTONOMY_THRESHOLDS is a list of dicts (the format consumers expect)."""
    from src.lib.runtime import AUTONOMY_THRESHOLDS

    assert isinstance(AUTONOMY_THRESHOLDS, list)
    assert len(AUTONOMY_THRESHOLDS) > 0
    assert all(isinstance(t, dict) for t in AUTONOMY_THRESHOLDS)
    assert all("level" in t and "action" in t for t in AUTONOMY_THRESHOLDS)
