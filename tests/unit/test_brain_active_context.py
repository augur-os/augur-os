from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.lib.brain_active_context import (
    ActiveBrainFolderContext,
    get_active_brain_folder_context,
    set_active_brain_folder_context,
)
from src.lib.brain_manifest import BrainManifest, ensure_brain_skeleton, write_brain_manifest
from src.lib.brain_registry import clear_cache
from src.lib.brain_registry_io import save_registry
from src.lib.brain_registry_models import Brain, BrainRegistry, BrainType, GitArrangement, GitConfig


def _personal(path: Path) -> Brain:
    path.mkdir(parents=True, exist_ok=True)
    return Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=path,
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
        description="Personal brain",
    )


def _project(project: Path, brain_id: str = "project-demo") -> Brain:
    brain_root = project / "project-brain"
    ensure_brain_skeleton(brain_root)
    write_brain_manifest(
        brain_root,
        BrainManifest(
            schema_version=1,
            id=brain_id,
            type=BrainType.PROJECT,
            root=str(brain_root),
            attached_project=str(project),
            description="Demo project brain",
        ),
    )
    return Brain(
        id=brain_id,
        type=BrainType.PROJECT,
        data_root=brain_root,
        git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project),
        auto_activate_cwd_under=(project,),
        description="Demo project brain",
    )


def _registry(tmp_path: Path, brains: dict[str, Brain]) -> Path:
    clear_cache()
    registry_path = tmp_path / "brains.yaml"
    save_registry(BrainRegistry(version=1, brains=brains), registry_path)
    return registry_path


def test_default_context_is_all_folders(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    registry_path = _registry(tmp_path, {"personal": _personal(tmp_path / "personal")})
    state_path = tmp_path / "active-context.json"

    result = get_active_brain_folder_context(
        cwd=project,
        project_root=project,
        registry_path=registry_path,
        state_path=state_path,
    )

    assert result.context == ActiveBrainFolderContext(scope="all", label="All Brains")
    assert result.repaired is False
    assert state_path.is_file()


@pytest.mark.parametrize("content", ["{not-json", "[]"])
def test_invalid_state_file_repairs_to_all_folders(
    tmp_path: Path,
    content: str,
) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    registry_path = _registry(tmp_path, {"personal": _personal(tmp_path / "personal")})
    state_path = tmp_path / "active-context.json"
    state_path.write_text(content, encoding="utf-8")

    result = get_active_brain_folder_context(
        cwd=project,
        project_root=project,
        registry_path=registry_path,
        state_path=state_path,
    )

    assert result.context == ActiveBrainFolderContext(scope="all", label="All Brains")
    assert result.repaired is True
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "brain_id": None,
        "label": "All Brains",
        "project_root": None,
        "root": None,
        "scope": "all",
    }


def test_stale_persisted_unknown_brain_repairs_to_all_folders(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    registry_path = _registry(tmp_path, {"personal": _personal(tmp_path / "personal")})
    state_path = tmp_path / "active-context.json"
    state_path.write_text(
        json.dumps({"scope": "brain", "brain_id": "missing"}),
        encoding="utf-8",
    )

    result = get_active_brain_folder_context(
        cwd=project,
        project_root=project,
        registry_path=registry_path,
        state_path=state_path,
    )

    assert result.context == ActiveBrainFolderContext(scope="all", label="All Brains")
    assert result.repaired is True
    assert json.loads(state_path.read_text(encoding="utf-8"))["scope"] == "all"


def test_set_context_to_registered_project(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    personal = _personal(tmp_path / "personal")
    project_brain = _project(project, "project-demo")
    registry_path = _registry(tmp_path, {"personal": personal, "project-demo": project_brain})
    state_path = tmp_path / "active-context.json"

    result = set_active_brain_folder_context(
        {"scope": "brain", "brain_id": "project-demo"},
        cwd=project,
        project_root=project,
        registry_path=registry_path,
        state_path=state_path,
    )

    assert result.success is True
    assert result.context.scope == "brain"
    assert result.context.brain_id == "project-demo"
    assert result.context.project_root == str(project)
    assert result.context.label == "Demo"


def test_unassigned_repair_context_is_selectable(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    registry_path = _registry(tmp_path, {"personal": _personal(tmp_path / "personal")})
    state_path = tmp_path / "active-context.json"

    result = set_active_brain_folder_context(
        {"scope": "unassigned"},
        cwd=project,
        project_root=project,
        registry_path=registry_path,
        state_path=state_path,
    )

    assert result.success is True
    assert result.context == ActiveBrainFolderContext(scope="unassigned", label="Unassigned")
    assert any(option["id"] == "unassigned" and option["badge"] == "Repair" for option in result.options)


def test_set_context_rejects_unknown_brain(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    registry_path = _registry(tmp_path, {"personal": _personal(tmp_path / "personal")})
    state_path = tmp_path / "active-context.json"

    result = set_active_brain_folder_context(
        {"scope": "brain", "brain_id": "missing"},
        cwd=project,
        project_root=project,
        registry_path=registry_path,
        state_path=state_path,
    )

    assert result.success is False
    assert result.error == "unknown_brain"
    assert (
        get_active_brain_folder_context(
            cwd=project,
            project_root=project,
            registry_path=registry_path,
            state_path=state_path,
        ).context.scope
        == "all"
    )


def test_set_context_rejects_unknown_brain_writes_default_without_valid_state(
    tmp_path: Path,
) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    registry_path = _registry(tmp_path, {"personal": _personal(tmp_path / "personal")})
    state_path = tmp_path / "active-context.json"
    state_path.write_text("{not-json", encoding="utf-8")

    result = set_active_brain_folder_context(
        {"scope": "brain", "brain_id": "missing"},
        cwd=project,
        project_root=project,
        registry_path=registry_path,
        state_path=state_path,
    )

    assert result.success is False
    assert result.error == "unknown_brain"
    assert result.context == ActiveBrainFolderContext(scope="all", label="All Brains")
    assert json.loads(state_path.read_text(encoding="utf-8"))["scope"] == "all"


def test_unregistered_detected_project_brain_cannot_be_selected(
    tmp_path: Path,
) -> None:
    project = tmp_path / "repo"
    brain_root = project / "project-brain"
    ensure_brain_skeleton(brain_root)
    write_brain_manifest(
        brain_root,
        BrainManifest(
            schema_version=1,
            id="project-unregistered",
            type=BrainType.PROJECT,
            root=str(brain_root),
            attached_project=str(project),
            description="Unregistered project brain",
        ),
    )
    registry_path = _registry(tmp_path, {"personal": _personal(tmp_path / "personal")})
    state_path = tmp_path / "active-context.json"

    result = set_active_brain_folder_context(
        {"scope": "brain", "brain_id": "project-unregistered"},
        cwd=project,
        project_root=project,
        registry_path=registry_path,
        state_path=state_path,
    )
    option = next(option for option in result.options if option["id"] == "detected:project-unregistered")

    assert option["state"] == "unregistered"
    assert result.success is False
    assert result.error == "unknown_brain"
    assert result.context == ActiveBrainFolderContext(scope="all", label="All Brains")
    assert json.loads(state_path.read_text(encoding="utf-8"))["scope"] == "all"


def test_set_context_rejects_unknown_brain_preserves_existing_context(
    tmp_path: Path,
) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    personal = _personal(tmp_path / "personal")
    project_brain = _project(project, "project-demo")
    registry_path = _registry(tmp_path, {"personal": personal, "project-demo": project_brain})
    state_path = tmp_path / "active-context.json"

    initial = set_active_brain_folder_context(
        {"scope": "brain", "brain_id": "project-demo"},
        cwd=project,
        project_root=project,
        registry_path=registry_path,
        state_path=state_path,
    )

    result = set_active_brain_folder_context(
        {"scope": "brain", "brain_id": "missing"},
        cwd=project,
        project_root=project,
        registry_path=registry_path,
        state_path=state_path,
    )
    persisted = get_active_brain_folder_context(
        cwd=project,
        project_root=project,
        registry_path=registry_path,
        state_path=state_path,
    )

    assert initial.context.scope == "brain"
    assert result.success is False
    assert result.error == "unknown_brain"
    assert result.context == initial.context
    assert persisted.context == initial.context


def test_missing_registered_brain_cannot_be_selected(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    missing_brain = Brain(
        id="project-missing",
        type=BrainType.PROJECT,
        data_root=project / "missing-project-brain",
        git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project),
        auto_activate_cwd_under=(project,),
        description="Missing project brain",
    )
    registry_path = _registry(
        tmp_path,
        {
            "personal": _personal(tmp_path / "personal"),
            "project-missing": missing_brain,
        },
    )
    state_path = tmp_path / "active-context.json"

    result = set_active_brain_folder_context(
        {"scope": "brain", "brain_id": "project-missing"},
        cwd=project,
        project_root=project,
        registry_path=registry_path,
        state_path=state_path,
    )
    option = next(option for option in result.options if option["id"] == "brain:project-missing")

    assert option["state"] == "missing"
    assert result.success is False
    assert result.error == "unknown_brain"
    assert result.context == ActiveBrainFolderContext(scope="all", label="All Brains")
    assert json.loads(state_path.read_text(encoding="utf-8"))["scope"] == "all"


def test_project_id_label_falls_back_to_title_without_project_prefix(
    tmp_path: Path,
) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    brain_root = project / "project-brain"
    ensure_brain_skeleton(brain_root)
    write_brain_manifest(
        brain_root,
        BrainManifest(
            schema_version=1,
            id="project-demo",
            type=BrainType.PROJECT,
            root=str(brain_root),
            attached_project=str(project),
        ),
    )
    project_brain = Brain(
        id="project-demo",
        type=BrainType.PROJECT,
        data_root=brain_root,
        git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project),
        auto_activate_cwd_under=(project,),
    )
    registry_path = _registry(
        tmp_path,
        {
            "personal": _personal(tmp_path / "personal"),
            "project-demo": project_brain,
        },
    )
    state_path = tmp_path / "active-context.json"

    result = set_active_brain_folder_context(
        {"scope": "brain", "brain_id": "project-demo"},
        cwd=project,
        project_root=project,
        registry_path=registry_path,
        state_path=state_path,
    )

    assert result.success is True
    assert result.context.label == "Demo"


def test_stale_registered_project_and_detected_current_project_are_repairable(
    tmp_path: Path,
) -> None:
    current = tmp_path / "current"
    current.mkdir()
    current_project_brain = _project(current, "project-demo")
    old = tmp_path / "old-worktree"
    old.mkdir()
    stale_brain = Brain(
        id="project-demo",
        type=BrainType.PROJECT,
        data_root=old / "project-brain",
        git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=old),
        auto_activate_cwd_under=(old,),
        description="Demo project brain",
    )
    registry_path = _registry(
        tmp_path,
        {
            "personal": _personal(tmp_path / "personal"),
            "project-demo": stale_brain,
        },
    )
    state_path = tmp_path / "active-context.json"

    result = get_active_brain_folder_context(
        cwd=current,
        project_root=current,
        registry_path=registry_path,
        state_path=state_path,
    )

    option = next(option for option in result.options if option["id"] == "brain:project-demo")
    assert option["state"] == "repairable"
    assert option["root"] == str(current_project_brain.data_root)
    assert option["registered_root"] == str(stale_brain.data_root)
