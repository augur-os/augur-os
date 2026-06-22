"""
IDE-specific MCP config writers for configure_mcp.

Handles writing MCP server configuration to IDE config files in various
formats (JSON, TOML, DXT manifest) with flat or per-project structures.
Also contains config file read/diff/dump utilities used across the MCP
configuration pipeline.
"""

from __future__ import annotations

import difflib
import json
import ntpath
import os
import platform
import re
from pathlib import Path
from typing import Any

import yaml

from src.config.worktrees import is_linked_worktree
from src.logging import get_entity_logger

logger = get_entity_logger("configure_mcp")


# ============================================================================
# Path helpers
# ============================================================================

_WINDOWS_ENV_VAR_RE = re.compile(r"%([^%]+)%")


def _expand_path(p: str, repo_root: Path | None = None) -> Path:
    """Expand path with ~ and environment variables."""
    expanded = p
    if repo_root and "{repo_root}" in expanded:
        expanded = expanded.replace("{repo_root}", repo_root.as_posix())
    expanded = os.path.expanduser(expanded)
    expanded = _WINDOWS_ENV_VAR_RE.sub(
        lambda match: os.environ.get(match.group(1), match.group(0)),
        expanded,
    )
    expanded = os.path.expandvars(expanded)
    if platform.system().lower() == "windows" and ntpath.isabs(expanded):
        return Path(ntpath.normpath(expanded))
    return Path(expanded).resolve()


def _get_config_path_for_platform(ide_config: dict[str, Any], repo_root: Path) -> Path | None:
    """Get the config path for the current platform."""
    config_path = ide_config.get("config_path", {})

    if isinstance(config_path, str):
        return _expand_path(config_path, repo_root)

    system = platform.system().lower()
    platform_map = {"darwin": "darwin", "linux": "linux", "windows": "windows"}
    current_platform = platform_map.get(system, "linux")

    # Try platform-specific, then "all"
    path_str = config_path.get(current_platform) or config_path.get("all")
    if path_str:
        return _expand_path(path_str, repo_root)

    return None


def _load_ide_registry(registry_path: Path) -> dict[str, Any]:
    """Load IDE configurations from YAML registry."""
    if not registry_path.exists():
        print(f"Warning: IDE registry not found at {registry_path}")
        return {"ides": {}}

    with open(registry_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"ides": {}}


# ============================================================================
# Config file read/diff/dump utilities
# ============================================================================

def _read_json(path: Path) -> dict[str, Any]:
    """Read JSON config file."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_toml(path: Path) -> dict[str, Any]:
    """Read TOML config file."""
    if not path.exists():
        return {}
    try:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _json_diff(current: dict[str, Any], new: dict[str, Any], label: str) -> str:
    """Generate unified diff between two JSON configs."""
    current_str = json.dumps(current, indent=2, sort_keys=True)
    new_str = json.dumps(new, indent=2, sort_keys=True)

    diff = difflib.unified_diff(
        current_str.splitlines(),
        new_str.splitlines(),
        fromfile=f"Current {label}",
        tofile=f"Proposed {label}",
        lineterm="",
    )
    return "\n".join(diff)


def _toml_format_value(value: Any) -> str:
    """Format a value for TOML output."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_format_value(item) for item in value) + "]"
    return json.dumps(str(value))


_TOML_BARE_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _toml_format_key(key: str) -> str:
    """Format a TOML key, quoting path-like keys when required."""
    return key if _TOML_BARE_KEY_RE.match(key) else json.dumps(key)


def _toml_table_name(parts: tuple[str, ...]) -> str:
    """Join TOML table path parts with quoting for non-bare keys."""
    return ".".join(_toml_format_key(part) for part in parts)


def _toml_dump_table(parts: tuple[str, ...], data: dict[str, Any]) -> list[str]:
    """Dump a TOML table."""
    lines: list[str] = []
    scalar_items = [(k, v) for k, v in data.items() if not isinstance(v, dict)]
    lines.append(f"[{_toml_table_name(parts)}]")
    for key, value in sorted(scalar_items, key=lambda item: item[0]):
        lines.append(f"{key} = {_toml_format_value(value)}")
    lines.append("")

    for key, value in sorted(data.items(), key=lambda item: item[0]):
        if isinstance(value, dict):
            lines.extend(_toml_dump_table((*parts, key), value))

    return lines


def _toml_dump(config: dict[str, Any]) -> str:
    """Dump config to TOML format."""
    lines: list[str] = []
    scalar_items = [(k, v) for k, v in config.items() if not isinstance(v, dict)]
    for key, value in sorted(scalar_items, key=lambda item: item[0]):
        lines.append(f"{key} = {_toml_format_value(value)}")

    table_items = [(k, v) for k, v in config.items() if isinstance(v, dict)]
    for key, value in sorted(table_items, key=lambda item: item[0]):
        lines.extend(_toml_dump_table((key,), value))

    return "\n".join(lines).rstrip() + "\n"


def _toml_diff(current: dict[str, Any], new: dict[str, Any], label: str) -> str:
    """Generate unified diff between two TOML configs."""
    current_str = _toml_dump(current).rstrip()
    new_str = _toml_dump(new).rstrip()

    diff = difflib.unified_diff(
        current_str.splitlines(),
        new_str.splitlines(),
        fromfile=f"Current {label}",
        tofile=f"Proposed {label}",
        lineterm="",
    )
    return "\n".join(diff)


# ============================================================================
# Config structure builders
# ============================================================================

def _ensure_flat_entry(
    config: dict[str, Any],
    server_key: str,
    server_name: str,
    server_entry: dict[str, Any],
) -> dict[str, Any]:
    """Add MCP server to flat config structure (mcpServers at root)."""
    new_config = json.loads(json.dumps(config)) if config else {}

    servers = new_config.get(server_key)
    if not isinstance(servers, dict):
        servers = {}
        new_config[server_key] = servers

    servers[server_name] = server_entry
    return new_config


def _ensure_per_project_entry(
    config: dict[str, Any],
    project_path: str,
    server_key: str,
    server_name: str,
    server_entry: dict[str, Any],
) -> dict[str, Any]:
    """Add MCP server to per-project config structure (projects -> path -> mcpServers)."""
    new_config = json.loads(json.dumps(config)) if config else {}

    projects = new_config.get("projects")
    if not isinstance(projects, dict):
        projects = {}
        new_config["projects"] = projects

    # Normalize lookup for existing project_path to avoid path-separator duplication
    target_path = Path(project_path).resolve()
    matched_key = None
    for k in projects:
        try:
            if Path(k).resolve() == target_path:
                matched_key = k
                break
        except Exception:
            pass
    if matched_key:
        project_path = matched_key

    project_config = projects.get(project_path)
    if not isinstance(project_config, dict):
        project_config = {}
        projects[project_path] = project_config

    servers = project_config.get(server_key)
    if not isinstance(servers, dict):
        servers = {}
        project_config[server_key] = servers

    servers[server_name] = server_entry
    return new_config


def _drop_stale_augur_servers(
    config: dict[str, Any],
    config_structure: str,
    server_key: str,
    repo_root: Path,
    desired_server_names: set[str],
) -> None:
    """Remove managed Augur server entries that are no longer in the desired topology."""

    def prune(servers: Any) -> None:
        if not isinstance(servers, dict):
            return
        for server_name in list(servers):
            if server_name.startswith("augur") and server_name not in desired_server_names:
                del servers[server_name]

    if config_structure == "per_project":
        projects = config.get("projects")
        if not isinstance(projects, dict):
            return

        # Deduplicate/merge duplicate project keys (e.g. forward vs backslashes on Windows)
        resolved_map: dict[Path, str] = {}
        keys_to_delete: list[str] = []
        for k in list(projects):
            try:
                r_path = Path(k).resolve()
                if r_path in resolved_map:
                    primary_key = resolved_map[r_path]
                    if isinstance(projects[k], dict) and isinstance(projects[primary_key], dict):
                        prim_servers = projects[primary_key].setdefault(server_key, {})
                        dup_servers = projects[k].get(server_key)
                        if isinstance(prim_servers, dict) and isinstance(dup_servers, dict):
                            for s_name, s_cfg in dup_servers.items():
                                if s_name not in prim_servers:
                                    prim_servers[s_name] = s_cfg
                        for sub_key, sub_val in projects[k].items():
                            if sub_key != server_key and sub_key not in projects[primary_key]:
                                projects[primary_key][sub_key] = sub_val
                    keys_to_delete.append(k)
                else:
                    resolved_map[r_path] = k
            except Exception:
                pass

        for k in keys_to_delete:
            del projects[k]

        _drop_stale_augur_project_entries(projects, server_key, repo_root)

        # Normalize lookup for project config matching repo_root resolved path
        project_config = None
        target_path = repo_root.resolve()
        for k, v in projects.items():
            try:
                if Path(k).resolve() == target_path:
                    project_config = v
                    break
            except Exception:
                pass

        if project_config is None:
            project_config = projects.get(str(repo_root))

        if isinstance(project_config, dict):
            prune(project_config.get(server_key))
        return

    prune(config.get(server_key))


def _is_stale_augur_project_path(project_path: str, repo_root: Path) -> bool:
    if project_path == str(repo_root):
        return False
    try:
        path = Path(project_path).expanduser().resolve(strict=False)
    except OSError:
        path = Path(project_path).expanduser()
    if not path.exists():
        return True
    return is_linked_worktree(path)


def _drop_stale_augur_project_entries(
    projects: dict[str, Any],
    server_key: str,
    repo_root: Path,
) -> None:
    """Remove Augur-managed servers from stale per-project global config blocks."""
    for project_path, project_config in list(projects.items()):
        if not isinstance(project_config, dict):
            continue
        if not _is_stale_augur_project_path(str(project_path), repo_root):
            continue

        servers = project_config.get(server_key)
        if not isinstance(servers, dict):
            continue

        removed_augur_server = False
        for server_name in list(servers):
            if str(server_name).startswith("augur"):
                del servers[server_name]
                removed_augur_server = True

        if not removed_augur_server:
            continue
        if not servers:
            project_config.pop(server_key, None)
        if not project_config:
            del projects[project_path]


# ============================================================================
# DXT manifest builder
# ============================================================================

def _build_dxt_manifest(
    python_path: Path,
    repo_root: Path,
    mcp_args: list[str],
    mcp_cwd: Path,
) -> dict[str, Any]:
    """Build a DXT manifest.json for Perplexity connector installation."""
    return {
        "dxt_version": "0.1",
        "name": "augur-mcp",
        "display_name": "Augur",
        "version": "1.0.0",
        "description": (
            "Augur -- local-first personal knowledge and automation system (second brain). "
            "Provides 300+ MCP tools across productivity, career, finance, health, and more."
        ),
        "author": {
            "name": "Augur",
        },
        "server": {
            "type": "python",
            "mcp_config": {
                "command": Path(python_path).as_posix(),
                "args": mcp_args,
                "cwd": Path(mcp_cwd).as_posix(),
                "env": {
                    "AUGUR_ROOT": repo_root.as_posix(),
                    "PYTHONUNBUFFERED": "1",
                    "PYTHONPATH": f"{repo_root}{os.pathsep}{repo_root / 'src' / 'mcp'}",
                },
            },
        },
        "keywords": ["augur", "mcp", "productivity", "knowledge-management", "automation"],
        "license": "MIT",
    }


# ============================================================================
# IDE config writers
# ============================================================================

def _backup_config(path: Path) -> Path | None:
    """Log that a config change is happening (backup disabled)."""
    if not path.exists():
        return None
    # Backup disabled to prevent file spam. Just log.
    logger.info(f"Config change detected for {path}. Backup files are disabled.")
    return None


def _configure_ide_dxt(
    ide_name: str,
    ide_config: dict[str, Any],
    repo_root: Path,
    python_path: Path,
    mcp_args: list[str],
    mcp_cwd: Path,
    cli_overrides: dict[str, str | None],
    should_apply: bool,
    quiet_mode: bool,
) -> bool:
    """Configure Perplexity DXT connector. Returns True if changes were pending."""
    display_name = ide_config.get("display_name", ide_name)
    cli_arg = ide_config.get("cli_arg", f"--{ide_name}-config")
    dxt_id = ide_config.get("dxt_id", "augur%2Faugur-mcp")

    override_key = cli_arg.lstrip("-").replace("-", "_")
    cli_value = cli_overrides.get(override_key)

    if cli_value == "none":
        return False

    # Get the installed dir path
    if cli_value:
        installed_dir = _expand_path(cli_value, repo_root)
    else:
        installed_dir = _get_config_path_for_platform(ide_config, repo_root)

    if not installed_dir:
        if not quiet_mode:
            print(f"Skipping {display_name}: no config path for this platform")
        return False

    manifest_path = installed_dir / dxt_id / "manifest.json"

    # Build new manifest
    new_manifest = _build_dxt_manifest(python_path, repo_root, mcp_args, mcp_cwd)

    # Read current manifest if it exists
    current_manifest = _read_json(manifest_path)

    # Generate diff
    diff = _json_diff(current_manifest, new_manifest, str(manifest_path))

    if not diff:
        if not quiet_mode:
            print(f"No changes needed for {display_name}: {manifest_path}")
        return False

    if not quiet_mode:
        print(f"\nTarget {display_name} DXT manifest: {manifest_path}")
        print(diff)

    if should_apply:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(new_manifest, indent=2) + "\n", encoding="utf-8")
        if not quiet_mode:
            print(f"Wrote: {manifest_path}")

    return True


def _configure_ide(
    ide_name: str,
    ide_config: dict[str, Any],
    repo_root: Path,
    servers: dict[str, dict[str, Any]],
    cli_overrides: dict[str, str | None],
    should_apply: bool,
    quiet_mode: bool,
) -> bool:
    """Configure a single IDE with all servers. Returns True if changes were pending."""
    display_name = ide_config.get("display_name", ide_name)
    cli_arg = ide_config.get("cli_arg", f"--{ide_name}-config")

    # Check for CLI override or skip
    override_key = cli_arg.lstrip("-").replace("-", "_")
    cli_value = cli_overrides.get(override_key)

    if cli_value == "none":
        return False  # Skip this IDE

    # Get config path
    if cli_value:
        config_path = _expand_path(cli_value, repo_root)
    else:
        config_path = _get_config_path_for_platform(ide_config, repo_root)

    if not config_path:
        if not quiet_mode:
            print(f"Skipping {display_name}: no config path for this platform")
        return False

    config_format = ide_config.get("config_format", "json")
    config_structure = ide_config.get("config_structure", "flat")
    server_key = ide_config.get("server_key", "mcpServers")

    # Read current config
    if config_format == "toml":
        current_config = _read_toml(config_path)
    else:
        current_config = _read_json(config_path)

    # Build new config by adding all servers
    new_config = json.loads(json.dumps(current_config)) if current_config else {}
    _drop_stale_augur_servers(
        new_config,
        config_structure,
        server_key,
        repo_root,
        set(servers),
    )

    # Optional: ensure opencode config has a schema
    if ide_name == "opencode" and "$schema" not in new_config:
        new_config["$schema"] = "https://opencode.ai/config.json"

    for server_name, server_entry in servers.items():
        # Format specifically for OpenCode if needed
        if ide_name == "opencode":
            cmd = server_entry.get("command", "")
            args = server_entry.get("args", [])
            env = server_entry.get("env", {})

            new_server_entry = {
                "type": "local",
                "command": [cmd] + args,
            }
            if env:
                new_server_entry["environment"] = env

            # Preserve existing optional fields if present in current config
            existing_mcp = current_config.get(server_key, {}) if current_config else {}
            if isinstance(existing_mcp, dict) and server_name in existing_mcp:
                existing_entry = existing_mcp[server_name]
                if isinstance(existing_entry, dict):
                    if "enabled" in existing_entry:
                        new_server_entry["enabled"] = existing_entry["enabled"]
                    if "timeout" in existing_entry:
                        new_server_entry["timeout"] = existing_entry["timeout"]

            server_entry = new_server_entry

        if config_structure == "per_project":
            new_config = _ensure_per_project_entry(
                new_config,
                str(repo_root),
                server_key,
                server_name,
                server_entry,
            )
        else:
            new_config = _ensure_flat_entry(
                new_config,
                server_key,
                server_name,
                server_entry,
            )

    # Generate diff
    if config_format == "toml":
        diff = _toml_diff(current_config, new_config, str(config_path))
    else:
        diff = _json_diff(current_config, new_config, str(config_path))

    if not diff:
        if not quiet_mode:
            print(f"No changes needed for {display_name}: {config_path}")
        return False

    # Changes pending
    if not quiet_mode:
        print(f"\nTarget {display_name} Config: {config_path}")
        print(diff)

    if should_apply:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if config_path.exists():
            _backup_config(config_path)

        if config_format == "toml":
            config_path.write_text(_toml_dump(new_config), encoding="utf-8")
        else:
            config_path.write_text(json.dumps(new_config, indent=2) + "\n", encoding="utf-8")

        if not quiet_mode:
            print(f"Wrote: {config_path}")

    return True
