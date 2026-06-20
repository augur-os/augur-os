from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from src.config.paths import get_brain_registry_path
from src.lib.ai_artifact_inventory import scan_ai_artifacts, write_ai_artifact_inventory
from src.lib.brain_manifest import (
    BRAIN_MANIFEST_NAME,
    BrainManifest,
    project_brain_root_for,
    read_brain_manifest,
    write_brain_manifest,
)
from src.lib.brain_registry import clear_cache
from src.lib.brain_registry_io import load_registry, save_registry
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
)


@dataclass(frozen=True)
class ProjectBrainInitResult:
    brain_id: str
    brain_root: Path
    project_root: Path
    created: bool
    sync_returncode: int | None
    inventory_path: Path | None
    inventory_count: int
    inventory_warning_count: int


def init_project_brain(
    project_root: Path,
    registry_path: Path | None = None,
    run_sync: bool = False,
    refresh_inventory: bool = True,
) -> ProjectBrainInitResult:
    """Create or attach a repository-local project brain and registry entry."""
    project = project_root.resolve()
    registry_file = registry_path or get_brain_registry_path()
    brain_root = project_brain_root_for(project)
    manifest_path = brain_root / BRAIN_MANIFEST_NAME
    created = not manifest_path.exists()

    if created:
        manifest = BrainManifest(
            schema_version=1,
            id=f"project-{_slug(project.name)}",
            type=BrainType.PROJECT,
            root=str(brain_root),
            attached_project=str(project),
            description=f"{project.name} project brain",
        )
        write_brain_manifest(brain_root, manifest)
    else:
        manifest = read_brain_manifest(manifest_path)
        if manifest.type is not BrainType.PROJECT:
            raise ValueError(f"{manifest_path} must declare type=project")
        healed_manifest = _project_manifest_with_current_paths(
            manifest=manifest,
            brain_root=brain_root,
            project=project,
        )
        if healed_manifest != manifest:
            write_brain_manifest(brain_root, healed_manifest)
        manifest = healed_manifest

    registry = _load_or_empty_registry(registry_file)
    project_brain = Brain(
        id=manifest.id,
        type=BrainType.PROJECT,
        data_root=brain_root,
        git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project),
        description=manifest.description,
        auto_activate_cwd_under=(project,),
    )
    brains = dict(registry.brains)
    brains[project_brain.id] = project_brain
    save_registry(
        BrainRegistry(version=registry.version, brains=brains),
        registry_file,
    )
    clear_cache()

    inventory_path: Path | None = None
    inventory_count = 0
    inventory_warning_count = 0
    if refresh_inventory:
        inventory = scan_ai_artifacts(
            project_root=project,
            project_brain_id=project_brain.id,
        )
        inventory_path = write_ai_artifact_inventory(inventory, brain_root)
        inventory_count = len(inventory.artifacts)
        inventory_warning_count = len(inventory.warnings) + sum(len(record.warnings) for record in inventory.artifacts)

    sync_returncode = _sync_client_projections(project) if run_sync else None
    return ProjectBrainInitResult(
        brain_id=project_brain.id,
        brain_root=brain_root,
        project_root=project,
        created=created,
        sync_returncode=sync_returncode,
        inventory_path=inventory_path,
        inventory_count=inventory_count,
        inventory_warning_count=inventory_warning_count,
    )


def _load_or_empty_registry(path: Path) -> BrainRegistry:
    if path.is_file():
        return load_registry(path)
    return BrainRegistry(version=1, brains={})


def _project_manifest_with_current_paths(
    *,
    manifest: BrainManifest,
    brain_root: Path,
    project: Path,
) -> BrainManifest:
    return BrainManifest(
        schema_version=manifest.schema_version,
        id=manifest.id,
        type=BrainType.PROJECT,
        root=str(brain_root),
        attached_project=str(project),
        description=manifest.description,
    )


def _sync_client_projections(project_root: Path) -> int:
    env = os.environ.copy()
    pythonpath = [str(project_root)]
    project_capabilities = project_root / "project-brain" / "capabilities"
    if project_capabilities.is_dir():
        pythonpath.insert(0, str(project_capabilities))
    existing = env.get("PYTHONPATH")
    if existing:
        pythonpath.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    env["AUGUR_SYNC_PROJECT_ROOT"] = str(project_root)

    result = subprocess.run(
        [sys.executable, "-m", "skills.ai.scripts.sync_agents", "sync", "all"],
        cwd=project_root,
        env=env,
        check=False,
    )
    return result.returncode


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "project"
