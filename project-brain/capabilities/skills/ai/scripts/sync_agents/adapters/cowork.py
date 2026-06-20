"""sync_agents/adapters/cowork.py — Cowork (Claude Desktop plugin bundle) adapter."""
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
import logging
import platform
import shutil
import sys
from pathlib import Path

from src.config.paths import get_client_runtime_dir

from .base import BaseAdapter
from ..constants import PROJECT_ROOT, logger


def _find_cowork_plugin_dirs() -> list[Path]:
    """Find all Cowork cowork_plugins directories inside Claude Desktop app data."""
    base = get_client_runtime_dir("claude-desktop") / "local-agent-mode-sessions"
    if not base.exists():
        return []
    plugin_dirs: list[Path] = []
    for session_dir in base.iterdir():
        if not session_dir.is_dir():
            continue
        for org_dir in session_dir.iterdir():
            if not org_dir.is_dir():
                continue
            candidate = org_dir / "cowork_plugins"
            if candidate.exists():
                plugin_dirs.append(candidate)
    return sorted(plugin_dirs)


def _resolve_path(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


def _plugin_pack_scripts_dir(project_root: Path) -> Path:
    from src.lib.staged_skill_catalog import find_skill_dir
    skill_dir = find_skill_dir(project_root, "plugin-pack")
    if skill_dir is None:
        raise FileNotFoundError(
            "plugin-pack skill payload not found in repo or vault skills"
        )
    return skill_dir / "scripts"


class CoworkAdapter(BaseAdapter):
    """Assembles and installs the Augur plugin bundle into Claude Desktop (cowork)."""

    adapter_name = "cowork"
    _PLUGIN_KEYS = ("augur@local-desktop-app-uploads", "augur@augur-cowork")
    _LEGACY_CACHE_DIRS = ("augur-cowork",)
    _MANIFEST_FILES = (
        "augur@augur-cowork.json",
        "augur@local-desktop-app-uploads.json",
    )

    def __init__(self) -> None:
        super().__init__()
        self._output_dir = PROJECT_ROOT / "build" / "cowork"

    def get_managed_files(self) -> list[str]:
        paths: list[str] = [str(self._output_dir) + "/"]

        for cowork_dir in _find_cowork_plugin_dirs():
            paths.append(
                str(cowork_dir / "marketplaces" / "local-desktop-app-uploads" / "augur") + "/"
            )
            for cache_dir in self._LEGACY_CACHE_DIRS:
                paths.append(str(cowork_dir / "cache" / cache_dir) + "/")
            for manifest_name in self._MANIFEST_FILES:
                paths.append(str(cowork_dir / ".install-manifests" / manifest_name))
            paths.append(str(cowork_dir / "installed_plugins.json"))

        paths.append(str(get_client_runtime_dir("claude-desktop") / "claude_desktop_config.json"))
        return paths

    def get_state_files(self) -> list[str]:
        paths: list[str] = []
        for cowork_dir in _find_cowork_plugin_dirs():
            paths.extend(
                [
                    str(cowork_dir / "cache") + "/",
                    str(cowork_dir / "runtime-memory") + "/",
                    str(cowork_dir / "session-history") + "/",
                ]
            )
        return paths

    def detect_installed(self) -> bool:
        if platform.system() == "Darwin":
            return (
                Path("/Applications/Claude.app").exists()
                or (Path.home() / "Applications" / "Claude.app").exists()
            )
        if platform.system() == "Windows":
            import os
            app_data = os.environ.get("LOCALAPPDATA")
            if app_data:
                return (Path(app_data) / "Programs" / "Claude" / "Claude.exe").exists()
        return False

    def sync_rules(self, content: str) -> None:
        pass  # Plugin bundle carries its own instructions

    def sync_memory(self) -> None:
        pass

    def cleanup(self, exclude_paths: set[Path] | None = None, dry_run: bool = False) -> list[str]:
        deleted: list[str] = []
        excluded = {_resolve_path(path) for path in (exclude_paths or set())}

        def _is_excluded(path: Path) -> bool:
            resolved = _resolve_path(path)
            for excluded_path in excluded:
                if resolved == excluded_path:
                    return True
                try:
                    resolved.relative_to(excluded_path)
                    return True
                except ValueError:
                    pass
                try:
                    excluded_path.relative_to(resolved)
                    return True
                except ValueError:
                    pass
            return False

        # Build output dir
        if self._output_dir.exists() and not _is_excluded(self._output_dir):
            deleted.append(str(self._output_dir) + "/")
            if not dry_run:
                shutil.rmtree(self._output_dir)

        # Uploaded plugin dir + installed_plugins.json (surgical edit)
        for cowork_dir in _find_cowork_plugin_dirs():
            uploads_augur = cowork_dir / "marketplaces" / "local-desktop-app-uploads" / "augur"
            if uploads_augur.exists() and not _is_excluded(uploads_augur):
                deleted.append(str(uploads_augur) + "/")
                if not dry_run:
                    shutil.rmtree(uploads_augur)

            for cache_dir in self._LEGACY_CACHE_DIRS:
                legacy_cache = cowork_dir / "cache" / cache_dir
                if legacy_cache.exists() and not _is_excluded(legacy_cache):
                    deleted.append(str(legacy_cache) + "/")
                    if not dry_run:
                        shutil.rmtree(legacy_cache)

            for manifest_name in self._MANIFEST_FILES:
                manifest_path = cowork_dir / ".install-manifests" / manifest_name
                if manifest_path.exists() and not _is_excluded(manifest_path):
                    deleted.append(str(manifest_path))
                    if not dry_run:
                        manifest_path.unlink()

            installed_path = cowork_dir / "installed_plugins.json"
            if installed_path.exists() and not _is_excluded(installed_path):
                try:
                    data = json.loads(installed_path.read_text(encoding="utf-8"))
                    plugins = data.get("plugins", {})
                    matching_keys = [
                        key for key in self._PLUGIN_KEYS if isinstance(plugins, dict) and key in plugins
                    ]
                    if matching_keys:
                        deleted.append(str(installed_path))
                        if not dry_run:
                            for key in matching_keys:
                                del data["plugins"][key]
                            installed_path.write_text(
                                json.dumps(data, indent=2) + "\n", encoding="utf-8"
                            )
                except (OSError, json.JSONDecodeError) as e:
                    logger.warning("Failed to clean %s: %s", installed_path, e)

        # Remove mcpServers.augur from claude_desktop_config.json (surgical edit)
        claude_desktop_config = get_client_runtime_dir("claude-desktop") / "claude_desktop_config.json"
        if claude_desktop_config.exists() and not _is_excluded(claude_desktop_config):
            try:
                config = json.loads(claude_desktop_config.read_text(encoding="utf-8"))
                if "augur" in config.get("mcpServers", {}):
                    deleted.append(str(claude_desktop_config))
                    if not dry_run:
                        del config["mcpServers"]["augur"]
                        claude_desktop_config.write_text(
                            json.dumps(config, indent=2) + "\n", encoding="utf-8"
                        )
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("Failed to clean %s: %s", claude_desktop_config, e)

        return deleted

    def generate_mcp_config(self) -> None:
        """Assemble and install the Cowork plugin bundle into Claude Desktop."""
        scripts_path = str(_plugin_pack_scripts_dir(PROJECT_ROOT))
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)

        from plugin_assembler import assemble, install

        output, version = assemble("cowork", self._output_dir)
        install("cowork", output, version)
