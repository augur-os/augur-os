from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.paths import get_brain_registry_path
from src.lib.brain_manifest import BRAIN_MANIFEST_NAME, project_brain_root_for, read_brain_manifest
from src.lib.brain_registry_io import load_registry
from src.lib.brain_registry_models import BrainRegistry, BrainType


@dataclass(frozen=True)
class ProjectScopeStatus:
    project_root: Path
    brain_root: Path
    manifest_path: Path
    initialized: bool
    registered: bool
    can_init: bool
    status: str
    message: str
    brain_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "project_root": str(self.project_root),
            "brain_root": str(self.brain_root),
            "manifest_path": str(self.manifest_path),
            "initialized": self.initialized,
            "registered": self.registered,
            "can_init": self.can_init,
            "status": self.status,
            "message": self.message,
            "brain_id": self.brain_id,
        }


def inspect_project_scope(
    project_root: Path,
    *,
    registry_path: Path | None = None,
) -> ProjectScopeStatus:
    project = Path(project_root).expanduser().resolve()
    brain_root = project_brain_root_for(project).resolve()
    manifest_path = brain_root / BRAIN_MANIFEST_NAME

    if not manifest_path.is_file():
        return ProjectScopeStatus(
            project_root=project,
            brain_root=brain_root,
            manifest_path=manifest_path,
            initialized=False,
            registered=False,
            can_init=True,
            status="not_initialized",
            message="No project brain is attached. Run /project init for this folder.",
        )

    try:
        manifest = read_brain_manifest(manifest_path)
    except (OSError, ValueError) as exc:
        return ProjectScopeStatus(
            project_root=project,
            brain_root=brain_root,
            manifest_path=manifest_path,
            initialized=False,
            registered=False,
            can_init=False,
            status="invalid_manifest",
            message=f"Project brain manifest is invalid: {exc}",
        )

    if manifest.type is not BrainType.PROJECT:
        return ProjectScopeStatus(
            project_root=project,
            brain_root=brain_root,
            manifest_path=manifest_path,
            initialized=False,
            registered=False,
            can_init=False,
            status="invalid_manifest",
            message=f"{manifest_path} declares type={manifest.type.value}, expected project.",
            brain_id=manifest.id,
        )

    registry = _load_registry(registry_path or get_brain_registry_path())
    registered = False
    existing = registry.get(manifest.id)
    if existing is not None:
        registered = _same_path(Path(str(existing.data_root)), brain_root)

    return ProjectScopeStatus(
        project_root=project,
        brain_root=brain_root,
        manifest_path=manifest_path,
        initialized=True,
        registered=registered,
        can_init=not registered,
        status="initialized" if registered else "initialized_unregistered",
        message=(
            "Project brain is initialized and registered."
            if registered
            else "Project brain exists but is not registered. Run /project init to attach it."
        ),
        brain_id=manifest.id,
    )


def _load_registry(path: Path) -> BrainRegistry:
    if path.is_file():
        return load_registry(path)
    return BrainRegistry(version=1, brains={})


def _same_path(left: Path, right: Path) -> bool:
    return left.expanduser().resolve(strict=False) == right.expanduser().resolve(strict=False)
