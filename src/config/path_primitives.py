"""
Shared path primitives for Augur path resolution.

This module provides the low-level building blocks used by both the monorepo
path resolver (src.config.paths) and the standalone MCP config
(src.mcp.augur_shared.config). It has ZERO dependencies on other Augur modules
so it can be imported in standalone/isolated contexts.

ADR-466 Fix 1: Eliminates 12 duplicated functions between paths.py and config.py.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path


def expand_path(path: str | Path) -> Path:
    """Expand ~ and resolve to absolute path."""
    return Path(os.path.expanduser(str(path))).resolve()


def env_path(*names: str) -> Path | None:
    """Return the first matching environment variable as a resolved Path.

    Strips whitespace from values. Returns None if no variable is set
    or all values are whitespace-only.
    """
    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return expand_path(value.strip())
    return None


def is_macos() -> bool:
    """Return True if running on macOS."""
    return platform.system() == "Darwin"


def is_windows() -> bool:
    """Return True if running on Windows."""
    return platform.system() == "Windows"


def windows_roaming_dir() -> Path:
    """Return Windows roaming AppData or its default."""
    return expand_path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))


def windows_local_dir() -> Path:
    """Return Windows local AppData or its default."""
    return expand_path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))


def xdg_data_home() -> Path:
    """Return XDG_DATA_HOME or its default (~/.local/share)."""
    return expand_path(os.environ.get("XDG_DATA_HOME", "~/.local/share"))


def xdg_state_home() -> Path:
    """Return XDG_STATE_HOME or its default (~/.local/state)."""
    return expand_path(os.environ.get("XDG_STATE_HOME", "~/.local/state"))


def xdg_cache_home() -> Path:
    """Return XDG_CACHE_HOME or its default (~/.cache)."""
    return expand_path(os.environ.get("XDG_CACHE_HOME", "~/.cache"))


def application_support_dir(project_name: str) -> Path:
    """Return the application support directory for the given project.

    macOS: ~/Library/Application Support/{project_name}
    Windows: %APPDATA%/{project_name}
    Linux: $XDG_DATA_HOME/{project_name_lower}
    """
    if is_macos():
        return expand_path(f"~/Library/Application Support/{project_name}")
    if is_windows():
        return windows_roaming_dir() / project_name
    return xdg_data_home() / project_name.lower()


def state_home_dir(project_name: str) -> Path:
    """Return the persistent state directory for the given project.

    macOS: ~/Library/Application Support/{project_name}/state
    Windows: %LOCALAPPDATA%/{project_name}/state
    Linux: $XDG_STATE_HOME/{project_name_lower}
    """
    if is_macos():
        return application_support_dir(project_name) / "state"
    if is_windows():
        return windows_local_dir() / project_name / "state"
    return xdg_state_home() / project_name.lower()


def logs_home_dir(project_name: str) -> Path:
    """Return the logs directory for the given project.

    macOS: ~/Library/Logs/{project_name}
    Windows: %LOCALAPPDATA%/{project_name}/logs
    Linux: $XDG_STATE_HOME/{project_name_lower}/logs
    """
    if is_macos():
        return expand_path(f"~/Library/Logs/{project_name}")
    if is_windows():
        return windows_local_dir() / project_name / "logs"
    return xdg_state_home() / project_name.lower() / "logs"


def cache_home_dir(project_name: str) -> Path:
    """Return the cache directory for the given project.

    macOS: ~/Library/Caches/{project_name}
    Windows: %LOCALAPPDATA%/{project_name}/Caches
    Linux: $XDG_CACHE_HOME/{project_name_lower}
    """
    if is_macos():
        return expand_path(f"~/Library/Caches/{project_name}")
    if is_windows():
        return windows_local_dir() / project_name / "Caches"
    return xdg_cache_home() / project_name.lower()


def vault_home_dir(project_name: str) -> Path:
    """Return the vault directory: ~/Vault/{project_name}."""
    return expand_path(f"~/Vault/{project_name}")


def documents_home_dir(project_name: str) -> Path:
    """Return the documents directory: ~/Documents/{project_name}."""
    return expand_path(f"~/Documents/{project_name}")


def _read_project_yaml_paths() -> dict[str, str]:
    """Read paths: block from project.yaml by walking up from this file.

    Returns raw string values (not resolved). Empty dict on any failure.
    Used by standalone fallbacks that cannot load the full path resolver.
    """
    try:
        import yaml
    except ImportError:
        return {}
    try:
        root = Path(__file__).resolve().parents[2]  # src/config -> src -> root
        project_yaml = root / "project.yaml"
        if not project_yaml.exists():
            return {}
        data = yaml.safe_load(project_yaml.read_text(encoding="utf-8"))
        paths_block = data.get("paths", {}) if isinstance(data, dict) else {}
        return paths_block if isinstance(paths_block, dict) else {}
    except Exception:
        return {}


def resolve_vault_standalone() -> Path:
    """Resolve vault path without full src.config import chain.

    Checks: AUGUR_VAULT env var > project.yaml > hardcoded default.
    ADR-481: Used by skill MCP fallbacks in except ImportError blocks.
    """
    vault = env_path("AUGUR_VAULT")
    if vault:
        return vault
    yaml_vault = _read_project_yaml_paths().get("vault")
    if yaml_vault:
        return expand_path(yaml_vault)
    return vault_home_dir("Augur")


def resolve_documents_standalone() -> Path:
    """Resolve documents path without full src.config import chain."""
    docs = env_path("AUGUR_DOCUMENTS")
    if docs:
        return docs
    yaml_docs = _read_project_yaml_paths().get("documents")
    if yaml_docs:
        return expand_path(yaml_docs)
    return documents_home_dir("Augur")
