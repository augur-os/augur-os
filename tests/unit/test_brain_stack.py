from __future__ import annotations

from pathlib import Path

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
from src.lib.brain_stack import BrainStack, resolve_active_stack, resolve_global_brain


def _personal(path: Path) -> Brain:
    return Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=path,
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )


def _write_registry_with_personal(tmp_path: Path) -> Path:
    registry_path = tmp_path / "brains.yaml"
    save_registry(
        BrainRegistry(version=1, brains={"personal": _personal(tmp_path / "personal")}),
        registry_path,
    )
    return registry_path


def test_resolve_global_brain_uses_explicit_core_root(tmp_path: Path) -> None:
    core_root = tmp_path / "augur-install"
    core_root.mkdir()

    brain = resolve_global_brain(core_root=core_root)

    assert brain.id == "augur-core"
    assert brain.type is BrainType.GLOBAL
    assert Path(brain.data_root) == core_root.resolve()
    assert brain.write_policy == "read_only"
    assert brain.git.arrangement is GitArrangement.UNTRACKED


def test_resolve_global_brain_defaults_to_core_brain_root() -> None:
    # ADR-781 D10: the Global tier's capabilities live in the Augur core BRAIN
    # root (the dir containing capabilities/), not the install/repo root.
    from src.config.paths import get_project_root

    brain = resolve_global_brain()

    assert Path(brain.data_root) == (get_project_root() / "project-brain").resolve()
    assert (Path(brain.data_root) / "capabilities" / "skills").is_dir()


def test_stack_personal_mode_has_global_and_user_only(tmp_path: Path) -> None:
    core_root = tmp_path / "augur-install"
    core_root.mkdir()
    registry_path = _write_registry_with_personal(tmp_path)

    stack = resolve_active_stack(
        cwd=tmp_path / "outside",
        registry_path=registry_path,
        core_root=core_root,
    )

    ordered = stack.ordered()
    assert [b.type for b in ordered] == [BrainType.GLOBAL, BrainType.PERSONAL]
    assert stack.project is None
    assert stack.most_specific().type is BrainType.PERSONAL


def test_stack_uses_default_registry_path_for_user_tier(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.brain_registry import clear_cache

    core_root = tmp_path / "augur-install"
    state = tmp_path / "state"
    core_root.mkdir()
    state.mkdir()
    monkeypatch.setenv("AUGUR_STATE_DIR", str(state))
    registry_path = state / "brains.yaml"
    save_registry(
        BrainRegistry(
            version=1,
            brains={"personal": _personal(tmp_path / "personal")},
        ),
        registry_path,
    )
    clear_cache()

    try:
        stack = resolve_active_stack(cwd=tmp_path / "outside", core_root=core_root)

        assert stack.user_brain is not None
        assert stack.user_brain.id == "personal"
        assert [b.type for b in stack.ordered()] == [
            BrainType.GLOBAL,
            BrainType.PERSONAL,
        ]
    finally:
        clear_cache()


def test_stack_project_mode_adds_project_tier(tmp_path: Path) -> None:
    core_root = tmp_path / "augur-install"
    core_root.mkdir()
    project = tmp_path / "repo"
    nested = project / "src"
    nested.mkdir(parents=True)
    brain_root = project / "project-brain"
    ensure_brain_skeleton(brain_root)
    write_brain_manifest(
        brain_root,
        BrainManifest(
            schema_version=1,
            id="project-repo",
            type=BrainType.PROJECT,
            root=str(brain_root),
            attached_project=str(project),
        ),
    )
    registry_path = _write_registry_with_personal(tmp_path)

    stack = resolve_active_stack(
        cwd=nested,
        registry_path=registry_path,
        core_root=core_root,
    )

    ordered = stack.ordered()
    assert [b.type for b in ordered] == [
        BrainType.GLOBAL,
        BrainType.PERSONAL,
        BrainType.PROJECT,
    ]
    assert stack.project is not None
    assert stack.project.active_brain.id == "project-repo"
    assert stack.most_specific().id == "project-repo"


def test_stack_to_header_dict_emits_tier_blocks(tmp_path: Path) -> None:
    core_root = tmp_path / "augur-install"
    core_root.mkdir()
    registry_path = _write_registry_with_personal(tmp_path)

    stack = resolve_active_stack(
        cwd=tmp_path / "outside",
        registry_path=registry_path,
        core_root=core_root,
    )
    header = stack.to_header_dict()

    assert header["augur_stack"]["global"]["id"] == "augur-core"
    assert header["augur_stack"]["user"]["id"] == "personal"
    assert "project" not in header["augur_stack"]
    assert isinstance(stack, BrainStack)
