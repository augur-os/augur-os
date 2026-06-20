from __future__ import annotations

from pathlib import Path

import yaml

from src.lib.brain_mount import ensure_mount, mount_dir_for_brain
from src.lib.brain_registry_models import (
    Brain,
    BrainType,
    GitArrangement,
    GitConfig,
)


def _brain(
    tmp_path: Path,
    brain_id: str = "project-demo",
    brain_type: BrainType = BrainType.PROJECT,
    host_repo: Path | None = None,
) -> Brain:
    data_root = tmp_path / "project-brain"
    data_root.mkdir(parents=True, exist_ok=True)
    return Brain(
        id=brain_id,
        type=brain_type,
        data_root=data_root,
        git=GitConfig(
            arrangement=GitArrangement.BUNDLED if host_repo else GitArrangement.UNTRACKED,
            host_repo=host_repo,
        ),
    )


def test_mount_dir_for_brain_is_brain_root(tmp_path: Path):
    brain = _brain(tmp_path)

    assert mount_dir_for_brain(brain) == tmp_path / "project-brain"


def test_ensure_mount_writes_root_brain_yaml(tmp_path: Path):
    brain = _brain(tmp_path)

    mount = ensure_mount(brain)
    brain_yaml = mount / "BRAIN.yaml"

    assert mount == brain.data_root
    assert brain_yaml.is_file()
    assert not (brain.data_root / ".augur" / "BRAIN.yaml").exists()
    parsed = yaml.safe_load(brain_yaml.read_text(encoding="utf-8"))
    assert parsed["id"] == "project-demo"
    assert parsed["type"] == "project"
    assert parsed["schema_version"] == 1
    assert parsed["root"] == str(brain.data_root)
    assert "attached_project" not in parsed


def test_ensure_mount_is_idempotent(tmp_path: Path):
    brain = _brain(tmp_path)
    first = ensure_mount(brain)
    (first / "marker.txt").write_text("preserved", encoding="utf-8")
    second = ensure_mount(brain)
    assert first == second
    assert (second / "marker.txt").read_text(encoding="utf-8") == "preserved"


def test_ensure_mount_updates_brain_yaml_when_brain_changes(tmp_path: Path):
    brain = _brain(tmp_path, "personal", BrainType.PERSONAL)
    ensure_mount(brain)
    original = yaml.safe_load((brain.data_root / "BRAIN.yaml").read_text(encoding="utf-8"))
    # Simulate type change (would not happen in practice, but covers refresh).
    rebadged = Brain(
        id=brain.id,
        type=BrainType.PROJECT,
        data_root=brain.data_root,
        git=brain.git,
    )
    ensure_mount(rebadged)
    parsed = yaml.safe_load((brain.data_root / "BRAIN.yaml").read_text(encoding="utf-8"))
    assert parsed["type"] == "project"
    assert parsed != original


def test_ensure_mount_records_attached_project_for_bundled_brain(tmp_path: Path):
    brain = _brain(tmp_path, host_repo=tmp_path)

    ensure_mount(brain)

    parsed = yaml.safe_load((brain.data_root / "BRAIN.yaml").read_text(encoding="utf-8"))
    assert parsed["attached_project"] == str(tmp_path)
