from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import src.lib.brain_init as brain_init
from src.lib.brain_init import init_project_brain
from src.lib.brain_context import resolve_active_context
from src.lib.brain_manifest import BRAIN_MANIFEST_NAME, read_brain_manifest
from src.lib.brain_registry_io import load_registry, save_registry
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
)
from src.mcp.augur_core.tools.core.brain_discovery import brain_init_impl


def _personal_brain(root: Path) -> Brain:
    return Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=root,
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )


def test_init_project_brain_creates_manifest_skeleton_and_registry(
    tmp_path: Path,
) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    registry_path = tmp_path / "brains.yaml"
    save_registry(
        BrainRegistry(
            version=1,
            brains={"personal": _personal_brain(tmp_path / "personal")},
        ),
        registry_path,
    )

    result = init_project_brain(
        project_root=project,
        registry_path=registry_path,
        run_sync=False,
    )

    brain_root = project.resolve() / "project-brain"
    assert result.brain_id == "project-repo"
    assert result.brain_root == brain_root
    assert result.project_root == project.resolve()
    assert result.created is True
    assert result.sync_returncode is None
    assert (brain_root / BRAIN_MANIFEST_NAME).is_file()
    assert (brain_root / "capabilities" / "skills").is_dir()
    assert (brain_root / "config").is_dir()
    assert (brain_root / "decisions" / "adrs").is_dir()
    assert result.inventory_path == brain_root / "config" / "inventory" / "ai-artifacts.json"
    assert result.inventory_count == 0
    assert result.inventory_warning_count == 0
    assert result.inventory_path.is_file()

    manifest = read_brain_manifest(brain_root / BRAIN_MANIFEST_NAME)
    assert manifest.id == "project-repo"
    assert manifest.type is BrainType.PROJECT
    assert manifest.root == str(brain_root)
    assert manifest.attached_project == str(project.resolve())
    assert manifest.description == "repo project brain"

    registry = load_registry(registry_path)
    project_brain = registry.get("project-repo")
    assert project_brain is not None
    assert project_brain.type is BrainType.PROJECT
    assert project_brain.data_root == brain_root
    assert project_brain.git.arrangement is GitArrangement.BUNDLED
    assert project_brain.git.host_repo == project.resolve()
    assert project_brain.description == "repo project brain"
    assert project_brain.auto_activate_cwd_under == (project.resolve(),)
    assert registry.get("personal") is not None


def test_init_project_brain_default_is_inventory_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    registry_path = tmp_path / "brains.yaml"
    sync_calls = []

    monkeypatch.setattr(
        brain_init,
        "_sync_client_projections",
        lambda project_root: sync_calls.append(project_root) or 0,
    )

    result = init_project_brain(
        project_root=project,
        registry_path=registry_path,
    )

    assert result.sync_returncode is None
    assert sync_calls == []
    assert result.inventory_path == project.resolve() / "project-brain" / "config" / "inventory" / "ai-artifacts.json"
    assert result.inventory_path.is_file()


def test_init_project_brain_sync_is_explicit_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    registry_path = tmp_path / "brains.yaml"
    sync_calls = []

    monkeypatch.setattr(
        brain_init,
        "_sync_client_projections",
        lambda project_root: sync_calls.append(project_root) or 23,
    )

    result = init_project_brain(
        project_root=project,
        registry_path=registry_path,
        run_sync=True,
    )

    assert result.sync_returncode == 23
    assert sync_calls == [project.resolve()]


def test_mcp_brain_init_defaults_to_inventory_only() -> None:
    signature = inspect.signature(brain_init_impl)
    assert signature.parameters["run_sync"].default is False

    core_source = Path("src/mcp/augur_core/tools/core/__init__.py").read_text(encoding="utf-8")
    assert 'async def brain_init(project_root: str = "", run_sync: bool = False)' in core_source


def test_init_project_brain_attaches_existing_manifest_without_recreating(
    tmp_path: Path,
) -> None:
    project = tmp_path / "firmware"
    brain_root = project / "project-brain"
    brain_root.mkdir(parents=True)
    manifest_path = brain_root / BRAIN_MANIFEST_NAME
    manifest_content = (
        "schema_version: 1\n"
        "id: project-firmware\n"
        "type: project\n"
        f"root: {brain_root}\n"
        f"attached_project: {project}\n"
        "description: firmware project brain\n"
    )
    manifest_path.write_text(manifest_content, encoding="utf-8")
    (project / "AGENTS.md").write_text("Existing vendor instruction file\n", encoding="utf-8")
    registry_path = tmp_path / "brains.yaml"
    save_registry(BrainRegistry(version=1, brains={}), registry_path)

    result = init_project_brain(
        project_root=project,
        registry_path=registry_path,
        run_sync=False,
    )

    assert result.created is False
    assert result.brain_id == "project-firmware"
    assert result.brain_root == brain_root.resolve()
    assert result.inventory_path == brain_root.resolve() / "config" / "inventory" / "ai-artifacts.json"
    assert result.inventory_count == 1
    # AGENTS.md is repo-authored source now (was mis-flagged unknown → spurious unknown_source warning).
    assert result.inventory_warning_count == 0
    assert "Existing vendor instruction file" in (project / "AGENTS.md").read_text(encoding="utf-8")
    assert manifest_path.read_text(encoding="utf-8") == manifest_content

    registry = load_registry(registry_path)
    project_brain = registry.get("project-firmware")
    assert project_brain is not None
    assert project_brain.data_root == brain_root.resolve()
    assert project_brain.git.host_repo == project.resolve()
    assert project_brain.description == "firmware project brain"


def test_init_project_brain_heals_cloned_manifest_paths(tmp_path: Path) -> None:
    original = tmp_path / "original"
    clone = tmp_path / "clone"
    brain_root = clone / "project-brain"
    nested = clone / "src" / "module"
    nested.mkdir(parents=True)
    brain_root.mkdir(parents=True)
    (brain_root / BRAIN_MANIFEST_NAME).write_text(
        "schema_version: 1\n"
        "id: project-firmware\n"
        "type: project\n"
        f"root: {original / 'project-brain'}\n"
        f"attached_project: {original}\n"
        "description: firmware project brain\n",
        encoding="utf-8",
    )
    registry_path = tmp_path / "brains.yaml"
    save_registry(
        BrainRegistry(
            version=1,
            brains={"personal": _personal_brain(tmp_path / "personal")},
        ),
        registry_path,
    )

    result = init_project_brain(
        project_root=clone,
        registry_path=registry_path,
        run_sync=False,
    )

    assert result.created is False
    assert result.brain_id == "project-firmware"
    manifest = read_brain_manifest(brain_root / BRAIN_MANIFEST_NAME)
    assert manifest.id == "project-firmware"
    assert manifest.root == str(brain_root.resolve())
    assert manifest.attached_project == str(clone.resolve())
    assert manifest.description == "firmware project brain"

    registry = load_registry(registry_path)
    assert registry.get("personal") is not None
    project_brain = registry.get("project-firmware")
    assert project_brain is not None
    assert project_brain.data_root == brain_root.resolve()
    assert project_brain.git.host_repo == clone.resolve()

    ctx = resolve_active_context(cwd=nested, registry_path=registry_path)
    assert ctx.attached_project == clone.resolve()
    assert ctx.active_brain.data_root == brain_root.resolve()
    assert ctx.active_brain.git.host_repo == clone.resolve()


def test_init_project_brain_is_idempotent(tmp_path: Path) -> None:
    project = tmp_path / "Repo With Spaces!"
    project.mkdir()
    registry_path = tmp_path / "brains.yaml"

    first = init_project_brain(
        project_root=project,
        registry_path=registry_path,
        run_sync=False,
    )
    second = init_project_brain(
        project_root=project,
        registry_path=registry_path,
        run_sync=False,
    )

    assert first.created is True
    assert second.created is False
    assert second.brain_id == "project-repo-with-spaces"
    registry = load_registry(registry_path)
    assert registry.ids() == ["project-repo-with-spaces"]


def test_init_project_brain_rejects_non_project_manifest(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    brain_root = project / "project-brain"
    brain_root.mkdir(parents=True)
    (brain_root / BRAIN_MANIFEST_NAME).write_text(
        "schema_version: 1\n" "id: team-repo\n" "type: team\n" f"root: {brain_root}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must declare type=project"):
        init_project_brain(
            project_root=project,
            registry_path=tmp_path / "brains.yaml",
            run_sync=False,
        )
    assert not (brain_root / "config" / "inventory" / "ai-artifacts.json").exists()
