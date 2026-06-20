from __future__ import annotations

from pathlib import Path

from src.lib.brain_init import init_project_brain
from src.lib.project_scope import inspect_project_scope


def test_uninitialized_folder_can_be_initialized(tmp_path: Path) -> None:
    registry = tmp_path / "registry.yaml"

    status = inspect_project_scope(tmp_path / "plain-folder", registry_path=registry)

    assert status.status == "not_initialized"
    assert status.initialized is False
    assert status.registered is False
    assert status.can_init is True
    assert status.project_root == (tmp_path / "plain-folder").resolve()
    assert status.brain_root == (tmp_path / "plain-folder" / "project-brain").resolve()


def test_initialized_registered_project_reports_ready(tmp_path: Path) -> None:
    registry = tmp_path / "registry.yaml"
    project = tmp_path / "ready-project"
    init_project_brain(project, registry_path=registry, refresh_inventory=False)

    status = inspect_project_scope(project, registry_path=registry)

    assert status.status == "initialized"
    assert status.initialized is True
    assert status.registered is True
    assert status.can_init is False
    assert status.brain_id == "project-ready-project"


def test_existing_project_brain_without_registry_entry_can_be_attached(tmp_path: Path) -> None:
    original_registry = tmp_path / "original-registry.yaml"
    missing_registry = tmp_path / "missing-registry.yaml"
    project = tmp_path / "detached-project"
    init_project_brain(project, registry_path=original_registry, refresh_inventory=False)

    status = inspect_project_scope(project, registry_path=missing_registry)

    assert status.status == "initialized_unregistered"
    assert status.initialized is True
    assert status.registered is False
    assert status.can_init is True
    assert status.brain_id == "project-detached-project"
