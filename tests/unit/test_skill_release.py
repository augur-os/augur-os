from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.lib.skill_release import (
    GROUP_VALUES,
    RELEASE_ORDER,
    RELEASE_VALUES,
    enabled_release_tags,
    ensure_valid_group,
    ensure_valid_release,
    is_release_enabled,
    validate_dependency_closure,
)


def _record(name: str, release: str, dependencies: dict[str, str] | None = None):
    return SimpleNamespace(
        name=name,
        release=release,
        dependencies=dependencies or {},
    )


def test_group_and_release_enums_are_fixed():
    assert GROUP_VALUES == (
        "augur_core",
        "augur_autoloops",
        "augur_admin",
        "brain",
        "productivity",
        "business",
        "career",
        "life",
        "websites",
        "templates",
        "dev",
        "other",
    )
    assert RELEASE_ORDER == ("mvp", "r1", "r2", "r3", "r4")
    assert RELEASE_VALUES == ("mvp", "r1", "r2", "r3", "r4", "later")


def test_enabled_release_tags_are_cumulative():
    assert enabled_release_tags("mvp") == ("mvp",)
    assert enabled_release_tags("r2") == ("mvp", "r1", "r2")
    with pytest.raises(ValueError):
        enabled_release_tags("later")


def test_release_enablement_is_target_based():
    assert is_release_enabled("mvp", "r3") is True
    assert is_release_enabled("r3", "r1") is False


def test_invalid_group_and_release_values_raise():
    with pytest.raises(ValueError):
        ensure_valid_group("internal")
    with pytest.raises(ValueError):
        ensure_valid_release("release-1")


def test_dependency_closure_reports_disabled_required_skills():
    records = [
        _record("knowledge", "mvp", {"required": ["rag"]}),
        _record("rag", "r2"),
    ]

    errors = validate_dependency_closure(records, "mvp")
    assert errors == ["knowledge -> rag"]
