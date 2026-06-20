"""Sync status checker.

Reports which Augur-native skills are synced to which clients,
sync health, and last sync timestamps.
"""

from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import json
from datetime import datetime
from pathlib import Path

from src.config.paths import (
    get_client_config_dir,
    get_client_skill_dirs,
)


_SOURCE_TAGS_BY_CLIENT = {
    "claude-code": ("claude-local", "claude-global"),
    "codex": ("codex-local", "codex-global"),
    "gemini": ("gemini-local", "gemini-global"),
    "opencode": ("opencode-local", "opencode-global"),
}


def get_sync_status(clients: list[str] | None = None) -> dict:
    """Get sync status for each client.

    Returns:
        Dict keyed by client name with status details:
        {
            "claude-code": {
                "status": "healthy" | "issues" | "not_installed",
                "synced_skills": ["career", "finance", ...],
                "last_sync": "2026-03-12T10:00:00",
                "issues": []
            }
        }
    """
    if clients is None:
        clients = ["claude-code", "codex", "gemini", "opencode"]

    result = {}
    skill_dirs = get_client_skill_dirs()

    for client in clients:
        try:
            config_dir = get_client_config_dir(client)
        except ValueError:
            result[client] = {
                "status": "unknown",
                "synced_skills": [],
                "issues": [f"Unknown client: {client}"],
            }
            continue

        source_tags = _SOURCE_TAGS_BY_CLIENT.get(client, ())
        client_skill_dirs = [
            skill_dirs[source_tag]
            for source_tag in source_tags
            if source_tag in skill_dirs
        ]

        installed = config_dir.is_dir() or any(path.is_dir() for path in client_skill_dirs)
        if not installed:
            result[client] = {"status": "not_installed", "synced_skills": [], "issues": []}
            continue

        synced: set[str] = set()
        issues: list[str] = []
        last_mod: float | None = None

        for skills_dir in client_skill_dirs:
            _collect_skill_dir_status(skills_dir, synced, issues)
            mod_time = _get_latest_modification(skills_dir)
            if mod_time is not None and (last_mod is None or mod_time > last_mod):
                last_mod = mod_time

        status = "healthy" if not issues else "issues"
        result[client] = {
            "status": status,
            "synced_skills": sorted(synced),
            "last_sync": datetime.fromtimestamp(last_mod).isoformat() if last_mod else None,
            "issues": issues,
        }

    return result


def _collect_skill_dir_status(skills_dir: Path, synced: set[str], issues: list[str]) -> None:
    """Collect sync status from a client skills directory."""
    if not skills_dir.is_dir():
        return

    managed_skills_manifest = skills_dir / ".augur-managed.json"
    if managed_skills_manifest.exists():
        try:
            data = json.loads(managed_skills_manifest.read_text(encoding="utf-8"))
            managed_skills = data.get("skills", [])
        except (OSError, json.JSONDecodeError):
            managed_skills = []
        for name in managed_skills:
            if not isinstance(name, str):
                continue
            entry = skills_dir / name
            if entry.is_dir() and (entry / "SKILL.md").exists():
                synced.add(name)
        return

    managed_prompts_manifest = skills_dir / ".augur-generated-prompts.json"
    if managed_prompts_manifest.exists():
        try:
            data = json.loads(managed_prompts_manifest.read_text(encoding="utf-8"))
            managed_files = data.get("files", [])
        except (OSError, json.JSONDecodeError):
            managed_files = []
        for name in managed_files:
            if not isinstance(name, str):
                continue
            entry = skills_dir / name
            if entry.is_file():
                synced.add(entry.stem)
        return

    for entry in skills_dir.iterdir():
        if entry.is_file() and entry.suffix == ".md":
            synced.add(entry.stem)
            continue

        if entry.is_symlink():
            if not entry.exists():
                issues.append(f"Stale symlink: {entry.name}")
                continue
            target = entry.resolve()
            if (target / "SKILL.md").exists():
                synced.add(entry.name)
            continue

        if entry.is_dir() and (entry / "SKILL.md").exists():
            synced.add(entry.name)


def _get_latest_modification(skills_dir: Path) -> float | None:
    """Return the latest SKILL.md mtime inside a client skills directory."""
    if not skills_dir.is_dir():
        return None

    latest: float | None = None
    for entry in skills_dir.iterdir():
        if entry.is_file() and entry.suffix == ".md":
            mod_time = entry.stat().st_mtime
            if latest is None or mod_time > latest:
                latest = mod_time
            continue

        if not entry.is_dir():
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.exists():
            continue
        mod_time = skill_md.stat().st_mtime
        if latest is None or mod_time > latest:
            latest = mod_time
    return latest
