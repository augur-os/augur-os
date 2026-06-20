from __future__ import annotations

from pathlib import Path

import pytest

from src.lib.brain_registry_io import load_registry, save_registry
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
    PropagationPolicy,
)


def _sample_registry() -> BrainRegistry:
    personal = Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=Path("/Users/x/Projects/Au-vault"),
        git=GitConfig(
            arrangement=GitArrangement.STANDALONE,
            remote="https://github.com/x/au-vault.git",
            branch="main",
            auto_commit=True,
            auto_push=True,
        ),
    )
    team = Brain(
        id="team-augur",
        type=BrainType.TEAM,
        data_root=Path("/Users/x/Projects/Augur/shared-vault"),
        git=GitConfig(
            arrangement=GitArrangement.BUNDLED,
            host_repo=Path("/Users/x/Projects/Augur"),
        ),
        write_policy="packets_only",
    )
    return BrainRegistry(version=1, brains={"personal": personal, "team-augur": team})


def test_roundtrip_preserves_registry(tmp_path: Path):
    target = tmp_path / "brains.yaml"
    original = _sample_registry()
    save_registry(original, target)
    loaded = load_registry(target)
    assert loaded == original


def test_load_missing_file_raises_filenotfound(tmp_path: Path):
    target = tmp_path / "missing.yaml"
    with pytest.raises(FileNotFoundError):
        load_registry(target)


def test_save_creates_parent_directories(tmp_path: Path):
    target = tmp_path / "nested" / "dir" / "brains.yaml"
    save_registry(_sample_registry(), target)
    assert target.is_file()


def test_load_rejects_wrong_version(tmp_path: Path):
    target = tmp_path / "brains.yaml"
    target.write_text("version: 99\nbrains: {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported registry version: 99"):
        load_registry(target)


def test_load_rejects_unknown_brain_type(tmp_path: Path):
    target = tmp_path / "brains.yaml"
    target.write_text(
        "version: 1\n"
        "brains:\n"
        "  x:\n"
        "    type: bogus\n"
        "    data_root: /tmp/x\n"
        "    git:\n"
        "      arrangement: untracked\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid brain type"):
        load_registry(target)


def test_propagation_policy_roundtrips(tmp_path: Path):
    brain = Brain(
        id="project-firmware",
        type=BrainType.PROJECT,
        data_root=Path("/Users/x/Projects/firmware/project-brain"),
        git=GitConfig(
            arrangement=GitArrangement.BUNDLED,
            host_repo=Path("/Users/x/Projects/firmware"),
        ),
        propagation=PropagationPolicy(
            allow_from=("personal",),
            allow_to=("personal",),
        ),
    )
    original = BrainRegistry(version=1, brains={"project-firmware": brain})
    target = tmp_path / "brains.yaml"
    save_registry(original, target)
    loaded = load_registry(target)
    assert loaded.get("project-firmware").type is BrainType.PROJECT
    assert loaded.get("project-firmware").propagation == PropagationPolicy(
        allow_from=("personal",), allow_to=("personal",)
    )
