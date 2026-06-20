import pytest
from routine_orchestrator import goal_catalog


def test_catalog_lists_known_goals():
    ids = {spec.id for spec in goal_catalog.catalog()}
    assert {"harden", "clean", "harden-and-clean"} <= ids


def test_resolve_returns_ordered_loops_test_before_hygiene():
    spec = goal_catalog.resolve("harden-and-clean")
    assert spec.loops.index("testing") < spec.loops.index("knowledge-enrichment")


def test_resolve_unknown_goal_raises():
    with pytest.raises(goal_catalog.UnknownGoalError):
        goal_catalog.resolve("does-not-exist")
