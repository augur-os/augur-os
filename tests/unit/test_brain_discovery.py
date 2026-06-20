from __future__ import annotations

from pathlib import Path

from src.lib.brain_discovery import build_discovery_snapshot
from src.lib.brain_manifest import (
    BrainManifest,
    ensure_brain_skeleton,
    write_brain_manifest,
)
from src.lib.brain_registry import clear_cache
from src.lib.brain_registry_io import save_registry
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
)


def _personal(path: Path) -> Brain:
    path.mkdir(parents=True, exist_ok=True)
    return Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=path,
        git=GitConfig(arrangement=GitArrangement.STANDALONE),
    )


def _save(tmp_path: Path, brains: dict[str, Brain]) -> Path:
    clear_cache()
    registry_path = tmp_path / "brains.yaml"
    save_registry(BrainRegistry(version=1, brains=brains), registry_path)
    return registry_path


def _seed_legacy_content(root: Path) -> None:
    """Populate the pre-ADR-770 top-level layout the live brain still uses."""
    (root / "notes").mkdir(parents=True, exist_ok=True)
    (root / "memory" / "entries").mkdir(parents=True, exist_ok=True)
    (root / "wiki").mkdir(parents=True, exist_ok=True)
    (root / "notes" / "a.md").write_text("a", encoding="utf-8")
    (root / "notes" / "b.md").write_text("b", encoding="utf-8")
    (root / "memory" / "entries" / "decision_x.md").write_text("x", encoding="utf-8")
    (root / "wiki" / "overview.md").write_text("o", encoding="utf-8")


def test_snapshot_reports_registered_brain_index_counts(tmp_path: Path) -> None:
    personal_root = tmp_path / "Au-vault"
    _seed_legacy_content(personal_root)
    project = tmp_path / "uninitialized-repo"
    project.mkdir()
    registry_path = _save(tmp_path, {"personal": _personal(personal_root)})

    snapshot = build_discovery_snapshot(
        cwd=project,
        registry_path=registry_path,
        project_root=project,
        include_git_status=False,
    )

    assert snapshot["success"] is True
    personal = next(b for b in snapshot["brains"] if b["id"] == "personal")
    assert personal["type"] == "personal"
    assert personal["index"]["notes"] == 2
    assert personal["index"]["memory_entries"] == 1
    assert personal["index"]["wiki_pages"] == 1
    assert personal["index"]["total_records"] == 4
    assert personal["index"]["populated"] is True


def test_uninitialized_project_can_init(tmp_path: Path) -> None:
    personal_root = tmp_path / "Au-vault"
    project = tmp_path / "fresh-repo"
    project.mkdir()
    registry_path = _save(tmp_path, {"personal": _personal(personal_root)})

    snapshot = build_discovery_snapshot(
        cwd=project,
        registry_path=registry_path,
        project_root=project,
        include_git_status=False,
    )

    current = snapshot["current_project"]
    assert current["has_project_brain"] is False
    assert current["registered"] is False
    assert current["can_init"] is True


def test_cloned_repo_with_unregistered_project_brain_is_detected(tmp_path: Path) -> None:
    """A cloned repo carrying project-brain/BRAIN.yaml that the local registry
    does not know about must surface as a detected-but-unregistered brain."""
    personal_root = tmp_path / "Au-vault"
    cloned = tmp_path / "cloned-repo"
    brain_root = cloned / "project-brain"
    ensure_brain_skeleton(brain_root)
    write_brain_manifest(
        brain_root,
        BrainManifest(
            schema_version=1,
            id="project-cloned",
            type=BrainType.PROJECT,
            root=str(brain_root),
            attached_project=str(cloned),
            description="Cloned project brain",
        ),
    )
    registry_path = _save(tmp_path, {"personal": _personal(personal_root)})

    snapshot = build_discovery_snapshot(
        cwd=cloned,
        registry_path=registry_path,
        project_root=cloned,
        include_git_status=False,
    )

    detected = snapshot["detected_project_brains"]
    assert len(detected) == 1
    assert detected[0]["id"] == "project-cloned"
    assert detected[0]["registered"] is False
    assert snapshot["current_project"]["has_project_brain"] is True
    # BRAIN.yaml exists but the registry has no matching entry → still initable.
    assert snapshot["current_project"]["registered"] is False
    assert snapshot["current_project"]["can_init"] is True


def test_registered_project_brain_marked_registered(tmp_path: Path) -> None:
    personal_root = tmp_path / "Au-vault"
    project = tmp_path / "registered-repo"
    brain_root = project / "project-brain"
    ensure_brain_skeleton(brain_root)
    write_brain_manifest(
        brain_root,
        BrainManifest(
            schema_version=1,
            id="project-registered",
            type=BrainType.PROJECT,
            root=str(brain_root),
            attached_project=str(project),
        ),
    )
    registry_path = _save(
        tmp_path,
        {
            "personal": _personal(personal_root),
            "project-registered": Brain(
                id="project-registered",
                type=BrainType.PROJECT,
                data_root=brain_root,
                git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project),
                auto_activate_cwd_under=(project,),
            ),
        },
    )

    snapshot = build_discovery_snapshot(
        cwd=project,
        registry_path=registry_path,
        project_root=project,
        include_git_status=False,
    )

    current = snapshot["current_project"]
    assert current["registered"] is True
    assert current["registered_brain_id"] == "project-registered"
    assert current["can_init"] is False
    detected = snapshot["detected_project_brains"]
    assert detected[0]["registered"] is True


def test_real_local_registry_snapshot_is_well_formed() -> None:
    """Smoke the engine against the real local registry (rule 34): the snapshot
    must be structurally sound and resolve an active brain on this machine."""
    clear_cache()
    snapshot = build_discovery_snapshot(cwd=Path.cwd(), include_git_status=False)
    assert snapshot["success"] is True
    assert isinstance(snapshot["brains"], list)
    assert snapshot["active"] is not None
    assert snapshot["active"]["brain_id"]
    for brain in snapshot["brains"]:
        assert {"id", "type", "root", "git", "index"} <= set(brain)
