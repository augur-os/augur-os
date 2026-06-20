"""Background-routines discovery surfaces ADR-758 declared routines (ADR-813):
a declared routine with a unique id appears as source_kind='declared-routine',
a declared id already produced by another discoverer is dropped (runtime entry
wins), and a registry failure never hides the other discoverers' routines.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import skills.daemon.scripts.routine_discovery as routine_discovery
from skills.daemon.scripts.routine_discovery import (
    DeclaredRoutineDiscoverer,
    Routine,
    discover_all_routines,
)


def _declared(
    tmp_path: Path,
    *,
    routine_id: str = "desktop-ingest",
    execution: str = "inline-session",
    skill_name: str = "file-manager-augur",
    description: str | None = "Triage Desktop & Downloads.",
) -> SimpleNamespace:
    skill_root = tmp_path / skill_name
    callable_ref = f"commands/{routine_id}.md"
    return SimpleNamespace(
        id=routine_id,
        execution=execution,
        policy="oneshot",
        callable=callable_ref,
        skill_name=skill_name,
        skill_root=skill_root,
        callable_path=skill_root / callable_ref,
        description=description,
    )


class _FakeServiceDiscoverer:
    source_kind = "daemon-service"

    def __init__(self, routines: list[Routine]):
        self._routines = routines

    def discover(self) -> list[Routine]:
        return self._routines


def _service_routine(routine_id: str) -> Routine:
    return Routine(
        id=routine_id,
        display_name=routine_id,
        source_kind="daemon-service",
        source_path=f"/fake/scripts/{routine_id}.py",
        cadence={"type": "interval", "spec": "every 12h", "spec_raw": "", "interval_seconds": 43200},
        status="enabled",
        spawn_kind="python",
    )


def test_declared_routine_with_unique_id_surfaces(monkeypatch, tmp_path: Path) -> None:
    declared = _declared(tmp_path, routine_id="declared-test-unique-id")
    monkeypatch.setattr(routine_discovery, "_call_list_declared_routines", lambda: [declared])

    routines = discover_all_routines()
    matches = [r for r in routines if r.id == "declared-test-unique-id"]
    assert len(matches) == 1
    routine = matches[0]
    assert routine.source_kind == "declared-routine"
    assert routine.spawn_kind == "inline-session"
    assert routine.source_path == str(declared.callable_path)
    assert routine.config_path == str(declared.skill_root / "SKILL.md")
    assert routine.cadence["type"] == "manual"
    assert routine.cadence["spec"] == "On demand"
    assert "declared" in routine.tags
    assert "file-manager-augur" in routine.tags


def test_declared_description_falls_back_to_skill_name(monkeypatch, tmp_path: Path) -> None:
    declared = _declared(tmp_path, routine_id="declared-test-no-desc", description=None)
    monkeypatch.setattr(routine_discovery, "_call_list_declared_routines", lambda: [declared])

    routines = discover_all_routines()
    routine = next(r for r in routines if r.id == "declared-test-no-desc")
    assert routine.description == "Declared routine from file-manager-augur"


def test_declared_id_colliding_with_runtime_routine_is_dropped(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        routine_discovery,
        "_call_list_declared_routines",
        lambda: [
            _declared(tmp_path, routine_id="code-quality", execution="tiered"),
            _declared(tmp_path, routine_id="declared-only-id"),
        ],
    )
    monkeypatch.setattr(
        routine_discovery,
        "DISCOVERERS",
        [_FakeServiceDiscoverer([_service_routine("code-quality")]), DeclaredRoutineDiscoverer()],
    )

    routines = discover_all_routines()
    ids = [r.id for r in routines]
    assert len(ids) == len(set(ids)), f"duplicate routine ids: {ids}"
    code_quality = next(r for r in routines if r.id == "code-quality")
    assert code_quality.source_kind == "daemon-service"  # runtime entry wins
    assert any(r.id == "declared-only-id" and r.source_kind == "declared-routine" for r in routines)


def test_registry_failure_does_not_break_other_discoverers(monkeypatch) -> None:
    def _boom() -> list:
        from skills.daemon.scripts.routine_orchestrator.registry import RoutineIdCollision

        raise RoutineIdCollision("routine id 'x' declared by both 'a' and 'b'")

    monkeypatch.setattr(routine_discovery, "_call_list_declared_routines", _boom)
    monkeypatch.setattr(
        routine_discovery,
        "DISCOVERERS",
        [_FakeServiceDiscoverer([_service_routine("survivor")]), DeclaredRoutineDiscoverer()],
    )

    routines = discover_all_routines()
    assert [r.id for r in routines] == ["survivor"]
    assert all(r.source_kind != "declared-routine" for r in routines)
