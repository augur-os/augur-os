from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.lib.brain_manifest import find_project_brain_root, read_brain_manifest
from src.lib.brain_registry_io import load_registry
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
)


@dataclass(frozen=True)
class ActiveBrainContext:
    active_brain: Brain
    attached_project: Path | None
    source: str

    def to_header_dict(self) -> dict[str, object]:
        attached_project = None
        if self.attached_project is not None:
            attached_project = {
                "root": str(self.attached_project),
                "has_adrs": (self.attached_project / "project-brain" / "decisions" / "adrs").is_dir(),
                "has_runtime": True,
            }
        return {
            "active_brain": {
                "id": self.active_brain.id,
                "type": self.active_brain.type.value,
                "root": str(self.active_brain.data_root),
            },
            "attached_project": attached_project,
            "generated_projection": True,
        }


def resolve_active_context(
    *,
    cwd: Path | None = None,
    registry_path: Path | None = None,
    explicit_brain: str | None = None,
    explicit_project: Path | None = None,
) -> ActiveBrainContext:
    start = (explicit_project or cwd or Path.cwd()).resolve()
    registry = _load_registry_if_present(registry_path)

    if explicit_brain is not None:
        if registry is None:
            raise KeyError(f"brain not registered: {explicit_brain}")
        brain = registry.get(explicit_brain)
        if brain is None:
            raise KeyError(f"brain not registered: {explicit_brain}")
        return ActiveBrainContext(
            active_brain=brain,
            attached_project=_attached_project_for(brain, start),
            source="explicit-brain",
        )

    project_brain_root = find_project_brain_root(start)
    if project_brain_root is not None:
        manifest = read_brain_manifest(project_brain_root / "BRAIN.yaml")
        if manifest.attached_project is not None:
            attached_project = Path(manifest.attached_project)
            project_root = (
                attached_project if attached_project.is_absolute() else project_brain_root / attached_project
            ).resolve()
        else:
            project_root = project_brain_root.parent.resolve()
        registered = registry.get(manifest.id) if registry is not None else None
        brain = (
            registered
            if _registered_project_matches(
                registered,
                project_brain_root,
                project_root,
            )
            else Brain(
                id=manifest.id,
                type=BrainType.PROJECT,
                data_root=project_brain_root,
                git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project_root),
                description=manifest.description,
                auto_activate_cwd_under=(project_root,),
            )
        )
        return ActiveBrainContext(
            active_brain=brain,
            attached_project=project_root,
            source="nearest-project-brain",
        )

    if registry is not None:
        match = _nearest_auto_activation_match(registry, start)
        if match is not None:
            brain, root = match
            return ActiveBrainContext(
                active_brain=brain,
                attached_project=root if brain.type is BrainType.PROJECT else None,
                source="registered-project",
            )

        personal = registry.get("personal")
        if personal is not None:
            return ActiveBrainContext(
                active_brain=personal,
                attached_project=None,
                source="default-personal",
            )

    raise KeyError("no active brain could be resolved")


def _registered_project_matches(
    brain: Brain | None,
    project_brain_root: Path,
    project_root: Path,
) -> bool:
    if brain is None or brain.type is not BrainType.PROJECT:
        return False
    if Path(brain.data_root).resolve() != project_brain_root.resolve():
        return False
    return brain.git.host_repo is not None and Path(brain.git.host_repo).resolve() == project_root.resolve()


def _nearest_auto_activation_match(
    registry: BrainRegistry,
    start: Path,
) -> tuple[Brain, Path] | None:
    matches: list[tuple[int, int, Brain, Path]] = []
    for brain in registry.brains.values():
        for root in brain.auto_activate_cwd_under:
            resolved_root = Path(root).resolve()
            try:
                start.relative_to(resolved_root)
            except ValueError:
                continue
            matches.append(
                (
                    len(resolved_root.parts),
                    len(str(resolved_root)),
                    brain,
                    resolved_root,
                )
            )
    if not matches:
        return None
    _, _, brain, root = max(matches, key=lambda match: (match[0], match[1]))
    return brain, root


def _attached_project_for(brain: Brain, cwd: Path) -> Path | None:
    if brain.type is not BrainType.PROJECT:
        return None
    if brain.git.host_repo is not None:
        return Path(brain.git.host_repo).resolve()
    if brain.auto_activate_cwd_under:
        return Path(brain.auto_activate_cwd_under[0]).resolve()
    return cwd.resolve()


def _load_registry_if_present(registry_path: Path | None) -> BrainRegistry | None:
    if registry_path is None or not registry_path.is_file():
        return None
    return load_registry(registry_path)
