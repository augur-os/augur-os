from __future__ import annotations

from pathlib import Path

import pytest

from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
    PropagationPolicy,
)


def _git_standalone() -> GitConfig:
    return GitConfig(arrangement=GitArrangement.STANDALONE)


def test_brain_minimal_required_fields():
    brain = Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=Path("/Users/x/Brains/personal"),
        git=_git_standalone(),
    )
    assert brain.id == "personal"
    assert brain.type is BrainType.PERSONAL
    assert brain.write_policy == "free"
    assert brain.propagation == PropagationPolicy()
    assert brain.auto_activate_cwd_under == ()


def test_brain_rejects_relative_data_root():
    with pytest.raises(ValueError, match="data_root must be absolute"):
        Brain(
            id="x",
            type=BrainType.PERSONAL,
            data_root=Path("Brains/personal"),
            git=GitConfig(arrangement=GitArrangement.UNTRACKED),
        )


def test_brain_rejects_unknown_write_policy():
    with pytest.raises(ValueError, match="unknown write_policy"):
        Brain(
            id="x",
            type=BrainType.TEAM,
            data_root=Path("/x"),
            git=GitConfig(arrangement=GitArrangement.UNTRACKED),
            write_policy="bogus",
        )


def test_git_config_bundled_requires_host_repo():
    with pytest.raises(ValueError, match="bundled arrangement requires host_repo"):
        GitConfig(arrangement=GitArrangement.BUNDLED)


def test_git_config_standalone_rejects_host_repo():
    with pytest.raises(ValueError, match="standalone arrangement must not set host_repo"):
        GitConfig(arrangement=GitArrangement.STANDALONE, host_repo=Path("/x"))


def test_git_config_host_repo_must_be_absolute():
    with pytest.raises(ValueError, match="host_repo must be an absolute path"):
        GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=Path("relative/path"))


def test_registry_lookup_by_id():
    brain = Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=Path("/x"),
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    registry = BrainRegistry(version=1, brains={"personal": brain})
    assert registry.get("personal") is brain
    assert registry.get("missing") is None
    assert registry.ids() == ["personal"]


def test_registry_rejects_id_mismatch():
    brain = Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=Path("/x"),
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    with pytest.raises(ValueError, match="registry key 'wrong-id' does not match brain id 'personal'"):
        BrainRegistry(version=1, brains={"wrong-id": brain})


def test_global_brain_type_and_read_only_policy_construct():
    brain = Brain(
        id="augur-core",
        type=BrainType.GLOBAL,
        data_root=Path("/opt/augur"),
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
        write_policy="read_only",
    )

    assert brain.type is BrainType.GLOBAL
    assert brain.type.value == "global"
    assert brain.write_policy == "read_only"


def _brain(brain_id: str, brain_type: BrainType) -> Brain:
    return Brain(
        id=brain_id,
        type=brain_type,
        data_root=Path(f"/data/{brain_id}"),
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )


def test_registry_rejects_two_personal_brains():
    with pytest.raises(ValueError, match="at most one personal"):
        BrainRegistry(
            version=1,
            brains={
                "personal": _brain("personal", BrainType.PERSONAL),
                "personal-2": _brain("personal-2", BrainType.PERSONAL),
            },
        )


def test_registry_rejects_two_global_brains():
    with pytest.raises(ValueError, match="at most one global"):
        BrainRegistry(
            version=1,
            brains={
                "augur-core": _brain("augur-core", BrainType.GLOBAL),
                "augur-core-2": _brain("augur-core-2", BrainType.GLOBAL),
            },
        )


def test_registry_allows_one_personal_many_projects_and_team():
    registry = BrainRegistry(
        version=1,
        brains={
            "personal": _brain("personal", BrainType.PERSONAL),
            "team-core": _brain("team-core", BrainType.TEAM),
            "project-a": _brain("project-a", BrainType.PROJECT),
            "project-b": _brain("project-b", BrainType.PROJECT),
        },
    )

    assert registry.get("personal") is not None
    assert len([b for b in registry.brains.values() if b.type is BrainType.PROJECT]) == 2
