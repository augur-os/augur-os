from __future__ import annotations

from pathlib import Path

from src.lib.brain_path import annotate_brain_id, resolve_brain_id_for_path
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
)


def _registry(tmp_path: Path) -> tuple[BrainRegistry, Path, Path]:
    personal_root = tmp_path / "personal"
    project_root = personal_root / "repo" / "project-brain"
    personal_root.mkdir(parents=True)
    project_root.mkdir(parents=True)
    registry = BrainRegistry(
        version=1,
        brains={
            "personal": Brain(
                id="personal",
                type=BrainType.PERSONAL,
                data_root=personal_root,
                git=GitConfig(arrangement=GitArrangement.STANDALONE),
            ),
            "project-repo": Brain(
                id="project-repo",
                type=BrainType.PROJECT,
                data_root=project_root,
                git=GitConfig(
                    arrangement=GitArrangement.BUNDLED,
                    host_repo=personal_root / "repo",
                ),
            ),
        },
    )
    return registry, personal_root, project_root


def test_resolves_path_inside_personal_brain(tmp_path: Path) -> None:
    registry, personal_root, _ = _registry(tmp_path)
    note = personal_root / "notes" / "thought.md"
    assert resolve_brain_id_for_path(note, registry=registry) == "personal"


def test_longest_match_wins_for_nested_project_brain(tmp_path: Path) -> None:
    registry, _, project_root = _registry(tmp_path)
    # This path is inside BOTH the personal root and the deeper project root;
    # the deeper project brain must win.
    record = project_root / "knowledge" / "memory" / "entries" / "fact.md"
    assert resolve_brain_id_for_path(record, registry=registry) == "project-repo"


def test_returns_none_for_path_outside_every_brain(tmp_path: Path) -> None:
    registry, _, _ = _registry(tmp_path)
    outside = tmp_path / "elsewhere" / "src" / "cli.py"
    assert resolve_brain_id_for_path(outside, registry=registry) is None


def test_brain_root_itself_resolves(tmp_path: Path) -> None:
    registry, personal_root, _ = _registry(tmp_path)
    assert resolve_brain_id_for_path(personal_root, registry=registry) == "personal"


def test_handles_unusable_path_without_raising(tmp_path: Path) -> None:
    registry, _, _ = _registry(tmp_path)
    assert resolve_brain_id_for_path("", registry=registry) is None


def test_annotate_brain_id_sets_field_from_first_present_key(tmp_path: Path) -> None:
    registry, personal_root, _ = _registry(tmp_path)
    record = {"file": str(personal_root / "notes" / "x.md"), "scope": "memory"}
    annotate_brain_id(record, "file", "source_path", "path", registry=registry)
    assert record["brain_id"] == "personal"


def test_annotate_brain_id_omits_field_for_non_brain_path(tmp_path: Path) -> None:
    registry, _, _ = _registry(tmp_path)
    record = {"file": str(tmp_path / "elsewhere" / "cli.py")}
    annotate_brain_id(record, "file", registry=registry)
    assert "brain_id" not in record


def test_annotate_brain_id_uses_default_keys(tmp_path: Path) -> None:
    registry, personal_root, _ = _registry(tmp_path)
    record = {"source_path": str(personal_root / "wiki" / "overview.md")}
    annotate_brain_id(record, registry=registry)
    assert record["brain_id"] == "personal"
