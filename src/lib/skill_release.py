"""Shared release model helpers for skill group and release gating."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

GROUP_VALUES = (
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

RELEASE_ORDER = ("mvp", "r1", "r2", "r3", "r4")
RELEASE_VALUES = RELEASE_ORDER + ("later",)


def ensure_valid_group(group: str) -> str:
    if group not in GROUP_VALUES:
        raise ValueError(f"Invalid group: {group!r}")
    return group


def ensure_valid_release(release: str) -> str:
    if release not in RELEASE_VALUES:
        raise ValueError(f"Invalid release: {release!r}")
    return release


def enabled_release_tags(release: str) -> tuple[str, ...]:
    ensure_valid_release(release)
    if release == "later":
        raise ValueError("later is not a buildable release target")
    index = RELEASE_ORDER.index(release)
    return RELEASE_ORDER[: index + 1]


def _release_rank(release: str) -> int:
    ensure_valid_release(release)
    if release == "later":
        return len(RELEASE_ORDER)
    return RELEASE_ORDER.index(release)


def is_release_enabled(skill_release: str, target_release: str) -> bool:
    return _release_rank(skill_release) <= _release_rank(target_release)


def _iter_required_dependencies(dependencies: dict[str, Any] | None) -> Iterable[str]:
    if not dependencies:
        return ()
    required = dependencies.get("required")
    if isinstance(required, list):
        return (str(dependency_name) for dependency_name in required)
    return (
        dependency_name
        for dependency_name, metadata in dependencies.items()
        if isinstance(metadata, dict) and metadata.get("kind") == "required"
    )


def validate_dependency_closure(records: Iterable[Any], target_release: str) -> list[str]:
    ensure_valid_release(target_release)
    records_list = list(records)
    releases = {getattr(record, "name"): getattr(record, "release") for record in records_list}
    errors: list[str] = []
    for record in records_list:
        record_release = getattr(record, "release")
        if not is_release_enabled(record_release, target_release):
            continue
        for dependency_name in _iter_required_dependencies(getattr(record, "dependencies", None)):
            dependency_release = releases.get(dependency_name)
            if dependency_release is None or not is_release_enabled(dependency_release, target_release):
                errors.append(f"{getattr(record, 'name')} -> {dependency_name}")
    return errors
