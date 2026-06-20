from __future__ import annotations

from pathlib import Path

from src.lib.brain_context import resolve_active_context
from src.lib.brain_manifest import (
    BrainManifest,
    ensure_brain_skeleton,
    write_brain_manifest,
)
from src.lib.brain_registry_io import save_registry
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
)


def _personal(path: Path) -> Brain:
    return Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=path,
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )


def _write_project_brain(project: Path, brain_id: str = "project-repo") -> Path:
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
        ),
    )
    return brain_root


def test_resolve_active_context_uses_nearest_project_brain(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    nested = project / "src" / "module"
    nested.mkdir(parents=True)
    brain_root = _write_project_brain(project)
    registry_path = tmp_path / "brains.yaml"
    save_registry(
        BrainRegistry(
            version=1,
            brains={
                "personal": _personal(tmp_path / "personal"),
                "project-repo": Brain(
                    id="project-repo",
                    type=BrainType.PROJECT,
                    data_root=brain_root,
                    git=GitConfig(
                        arrangement=GitArrangement.BUNDLED,
                        host_repo=project,
                    ),
                    auto_activate_cwd_under=(project,),
                ),
            },
        ),
        registry_path,
    )

    ctx = resolve_active_context(cwd=nested, registry_path=registry_path)

    assert ctx.active_brain.id == "project-repo"
    assert ctx.active_brain.type is BrainType.PROJECT
    assert ctx.attached_project == project.resolve()
    assert ctx.source == "nearest-project-brain"


def test_resolve_active_context_resolves_relative_manifest_project_path(
    tmp_path: Path,
) -> None:
    project = tmp_path / "repo"
    nested = project / "src" / "module"
    nested.mkdir(parents=True)
    brain_root = project / "project-brain"
    ensure_brain_skeleton(brain_root)
    write_brain_manifest(
        brain_root,
        BrainManifest(
            schema_version=1,
            id="project-repo",
            type=BrainType.PROJECT,
            root=".",
            attached_project="..",
        ),
    )

    ctx = resolve_active_context(cwd=nested)

    assert ctx.active_brain.id == "project-repo"
    assert ctx.active_brain.git.host_repo == project.resolve()
    assert ctx.attached_project == project.resolve()


def test_nearest_project_brain_ignores_stale_same_id_registry_entry(
    tmp_path: Path,
) -> None:
    old_project = tmp_path / "old-repo"
    old_brain_root = old_project / "project-brain"
    new_project = tmp_path / "new-repo"
    nested = new_project / "src" / "module"
    nested.mkdir(parents=True)
    new_brain_root = _write_project_brain(new_project)
    registry_path = tmp_path / "brains.yaml"
    save_registry(
        BrainRegistry(
            version=1,
            brains={
                "project-repo": Brain(
                    id="project-repo",
                    type=BrainType.PROJECT,
                    data_root=old_brain_root,
                    git=GitConfig(
                        arrangement=GitArrangement.BUNDLED,
                        host_repo=old_project,
                    ),
                    auto_activate_cwd_under=(old_project,),
                ),
            },
        ),
        registry_path,
    )

    ctx = resolve_active_context(cwd=nested, registry_path=registry_path)

    assert ctx.active_brain.id == "project-repo"
    assert ctx.active_brain.data_root == new_brain_root.resolve()
    assert ctx.active_brain.git.host_repo == new_project.resolve()
    assert ctx.attached_project == new_project.resolve()
    assert ctx.source == "nearest-project-brain"


def test_resolve_active_context_falls_back_to_personal(tmp_path: Path) -> None:
    registry_path = tmp_path / "brains.yaml"
    save_registry(
        BrainRegistry(
            version=1,
            brains={"personal": _personal(tmp_path / "personal")},
        ),
        registry_path,
    )

    ctx = resolve_active_context(cwd=tmp_path / "outside", registry_path=registry_path)

    assert ctx.active_brain.id == "personal"
    assert ctx.attached_project is None
    assert ctx.source == "default-personal"


def test_resolve_active_context_uses_nearest_auto_activation_root(
    tmp_path: Path,
) -> None:
    parent_project = tmp_path / "workspace"
    child_project = parent_project / "repo"
    cwd = child_project / "src" / "module"
    cwd.mkdir(parents=True)
    registry_path = tmp_path / "brains.yaml"
    parent = Brain(
        id="project-parent",
        type=BrainType.PROJECT,
        data_root=parent_project / "project-brain",
        git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=parent_project),
        auto_activate_cwd_under=(parent_project,),
    )
    child = Brain(
        id="project-child",
        type=BrainType.PROJECT,
        data_root=child_project / "project-brain",
        git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=child_project),
        auto_activate_cwd_under=(child_project,),
    )
    save_registry(
        BrainRegistry(
            version=1,
            brains={
                "project-parent": parent,
                "project-child": child,
            },
        ),
        registry_path,
    )

    ctx = resolve_active_context(cwd=cwd, registry_path=registry_path)

    assert ctx.active_brain.id == "project-child"
    assert ctx.attached_project == child_project.resolve()
    assert ctx.source == "registered-project"


def test_resolve_active_context_honors_explicit_brain(tmp_path: Path) -> None:
    registry_path = tmp_path / "brains.yaml"
    team = Brain(
        id="team-core",
        type=BrainType.TEAM,
        data_root=tmp_path / "team",
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    save_registry(
        BrainRegistry(
            version=1,
            brains={"personal": _personal(tmp_path / "personal"), "team-core": team},
        ),
        registry_path,
    )

    ctx = resolve_active_context(
        cwd=tmp_path,
        registry_path=registry_path,
        explicit_brain="team-core",
    )

    assert ctx.active_brain.id == "team-core"
    assert ctx.attached_project is None
    assert ctx.source == "explicit-brain"


def test_to_header_dict_reports_attached_project_state(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    nested = project / "src" / "module"
    nested.mkdir(parents=True)
    brain_root = _write_project_brain(project)

    ctx = resolve_active_context(cwd=nested)

    assert ctx.active_brain.git.arrangement is GitArrangement.BUNDLED
    assert ctx.active_brain.git.host_repo == project.resolve()
    assert ctx.to_header_dict() == {
        "active_brain": {
            "id": "project-repo",
            "type": "project",
            "root": str(brain_root.resolve()),
        },
        "attached_project": {
            "root": str(project.resolve()),
            "has_adrs": True,
            "has_runtime": True,
        },
        "generated_projection": True,
    }
