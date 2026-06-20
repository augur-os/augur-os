from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from src.lib.brain_manifest import (
    BRAIN_MANIFEST_NAME,
    PROJECT_BRAIN_DIRNAME,
    read_brain_manifest,
)
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
)


def build_default_registry(project_root: Path) -> BrainRegistry:
    """Produce the default personal registry plus attached project brain.

    Reads ``project_root/config/system/vault.yaml`` for personal brain Git
    metadata while resolving data roots through the same path helper stack used
    by existing vault callers when the target project is active.
    """
    brains: dict[str, Brain] = {}
    personal = _personal_from_vault_yaml(project_root)
    brains[personal.id] = personal

    project = _project_from_project_brain(project_root)
    if project is not None:
        brains[project.id] = project

    return BrainRegistry(version=1, brains=brains)


def migrate_loaded_registry(
    registry: BrainRegistry,
    *,
    project_root: Path,
) -> tuple[BrainRegistry, bool]:
    """Remove legacy registry entries that conflict with the project-brain model."""
    resolved_project_root = project_root.resolve()
    brains = {
        brain_id: brain
        for brain_id, brain in registry.brains.items()
        if not _is_legacy_shared_vault_team_brain(
            brain,
            project_root=resolved_project_root,
        )
        and not _is_ephemeral_temp_project_brain(
            brain,
            project_root=resolved_project_root,
        )
    }
    if len(brains) == len(registry.brains):
        return registry, False
    return BrainRegistry(version=registry.version, brains=brains), True


def _personal_from_vault_yaml(project_root: Path) -> Brain:
    vault_yaml = project_root / "config" / "system" / "vault.yaml"
    if not vault_yaml.is_file():
        raise FileNotFoundError(f"vault.yaml not found: {vault_yaml}")
    data: dict[str, Any] = yaml.safe_load(vault_yaml.read_text(encoding="utf-8")) or {}
    vault_block: dict[str, Any] = data.get("vault") or {}

    data_root = _personal_data_root(project_root, vault_block, vault_yaml)

    git_block: dict[str, Any] = vault_block.get("git") or {}
    git = GitConfig(
        arrangement=GitArrangement.STANDALONE,
        remote=vault_block.get("remote"),
        branch=str(git_block.get("branch") or "main"),
        auto_commit=bool(git_block.get("auto_commit", True)),
        auto_push=bool(git_block.get("auto_push", True)),
    )
    return Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=data_root,
        git=git,
        description="Personal brain (migrated from vault.yaml)",
    )


def _project_from_project_brain(project_root: Path) -> Brain | None:
    resolved_project_root = project_root.resolve()
    brain_root = resolved_project_root / PROJECT_BRAIN_DIRNAME
    manifest_path = brain_root / BRAIN_MANIFEST_NAME
    if not manifest_path.is_file():
        return None

    manifest = read_brain_manifest(manifest_path)
    if manifest.type is not BrainType.PROJECT:
        raise ValueError(f"project brain manifest must have type=project: {manifest_path}")

    return Brain(
        id=manifest.id,
        type=BrainType.PROJECT,
        data_root=brain_root,
        git=GitConfig(
            arrangement=GitArrangement.BUNDLED,
            host_repo=resolved_project_root,
        ),
        write_policy="free",
        description=manifest.description or "Project brain",
        auto_activate_cwd_under=(resolved_project_root,),
    )


def _is_legacy_shared_vault_team_brain(
    brain: Brain,
    *,
    project_root: Path,
) -> bool:
    if brain.id != "team-augur" or brain.type is not BrainType.TEAM:
        return False
    if brain.git.arrangement is not GitArrangement.BUNDLED:
        return False
    if not _same_path(brain.data_root, project_root / "shared-vault"):
        return False
    if brain.git.host_repo is not None and not _same_path(brain.git.host_repo, project_root):
        return False
    return True


def _is_ephemeral_temp_project_brain(
    brain: Brain,
    *,
    project_root: Path,
) -> bool:
    """Prune project-init registry entries created from throwaway temp folders."""
    if brain.type is not BrainType.PROJECT:
        return False
    if brain.git.arrangement is not GitArrangement.BUNDLED or brain.git.host_repo is None:
        return False
    if not brain.id.startswith("project-tmp-"):
        return False
    host_repo = Path(str(brain.git.host_repo)).expanduser()
    if _same_path(host_repo, project_root):
        return False
    if not host_repo.name.lower().startswith("tmp"):
        return False
    try:
        temp_root = Path(tempfile.gettempdir()).resolve(strict=False)
        resolved_host = host_repo.resolve(strict=False)
        resolved_host.relative_to(temp_root)
    except (OSError, ValueError):
        return False
    return True


def _same_path(left: object, right: Path) -> bool:
    try:
        return Path(str(left)).expanduser().resolve(strict=False) == right.resolve(strict=False)
    except OSError:
        return Path(str(left)).expanduser() == right


def _personal_data_root(
    project_root: Path,
    vault_block: dict[str, Any],
    vault_yaml: Path,
) -> Path:
    if _should_use_live_path_helpers(project_root, env_var="AUGUR_VAULT"):
        from src.config.paths import get_vault_dir

        return get_vault_dir()

    configured = _project_yaml_vault_path(project_root)
    if configured is not None:
        return configured

    raw_path = vault_block.get("path")
    if not raw_path:
        raise ValueError(f"vault.yaml missing vault.path: {vault_yaml}")
    return Path(str(raw_path)).expanduser()


def _should_use_live_path_helpers(project_root: Path, *, env_var: str) -> bool:
    if os.environ.get(env_var):
        return True
    try:
        from src.config.paths import get_project_root

        return get_project_root().resolve() == project_root.resolve()
    except Exception:
        return False


def _project_yaml_vault_path(project_root: Path) -> Path | None:
    project_yaml = project_root / "project.yaml"
    if not project_yaml.is_file():
        return None
    try:
        data = yaml.safe_load(project_yaml.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    paths_block = data.get("paths")
    if not isinstance(paths_block, dict):
        return None
    raw_path = paths_block.get("vault")
    if not isinstance(raw_path, str) or not raw_path:
        return None
    return Path(os.path.expanduser(raw_path)).resolve()
