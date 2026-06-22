"""Codex MCP runtime config helpers."""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any

from src.cli_config.manifest import ServerEntry, load_manifest
from src.config.runtime_identity import global_mcp_project_root

CODEX_MCP_LAUNCHER = "scripts/augur-codex-mcp"
CODEX_MCP_WINDOWS_LAUNCHER = "scripts/augur-codex-mcp.ps1"

CODEX_HOME = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))


def codex_mcp_pythonpath(project_root: str | Path, platform_name: str | None = None) -> str:
    """Return launcher PYTHONPATH with project capabilities before repo and src/mcp."""
    root = Path(project_root).expanduser().resolve()
    separator = ";" if _is_windows(platform_name) else ":"
    return separator.join(
        [
            (root / "project-brain" / "capabilities").as_posix(),
            root.as_posix(),
            (root / "src" / "mcp").as_posix(),
        ]
    )


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _is_windows(platform_name: str | None = None) -> bool:
    return (platform_name or platform.system()).lower() == "windows"


def build_codex_mcp_entry(
    server_args: list[str],
    configured_root: str | Path | None = None,
    platform_name: str | None = None,
    startup_timeout_sec: int | None = None,
) -> dict[str, Any]:
    """Return a compact Codex MCP entry with a cwd-independent launcher path."""
    root = Path(configured_root).expanduser().resolve() if configured_root else _default_project_root()
    if _is_windows(platform_name):
        entry: dict[str, Any] = {
            "command": "powershell.exe",
            "args": [
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                (root / CODEX_MCP_WINDOWS_LAUNCHER).as_posix(),
                *server_args,
            ],
        }
    else:
        entry = {
            "command": (root / CODEX_MCP_LAUNCHER).as_posix(),
            "args": list(server_args),
        }
    if startup_timeout_sec is not None:
        entry["startup_timeout_sec"] = startup_timeout_sec
    return entry


def _load_toml(path: Path) -> dict:
    """Read a TOML file into a dict; return {} on missing/unreadable input."""
    if not path.exists():
        return {}
    try:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _codex_args_for_entry(entry: ServerEntry) -> list[str]:
    args = list(entry.args)
    args.extend(entry.per_client_args.get("codex", []))
    return args


def _build_codex_mcp_entry_for(entry: ServerEntry, project_root: Path) -> dict[str, Any]:
    """Codex MCP entry for a manifest server, anchored at the given project root."""
    return build_codex_mcp_entry(
        _codex_args_for_entry(entry),
        configured_root=project_root,
        startup_timeout_sec=entry.startup_timeout_sec,
    )


def _build_codex_mcp_servers(
    project_root: Path,
    *,
    existing_server_ids: set[str] | None = None,
    include_project_scoped: bool = False,
) -> dict[str, dict[str, Any]]:
    manifest = load_manifest(project_root / "config" / "system" / "mcp_servers.yaml")
    return {
        entry.id: _build_codex_mcp_entry_for(entry, project_root)
        for entry in manifest.all_augur_servers_for_client(
            "codex",
            existing_server_ids=existing_server_ids,
            include_project_scoped=include_project_scoped,
        )
    }


def codex_runtime_config_issues(
    config_path: Path | None = None,
    *,
    project_root: Path | None = None,
    codex_home: Path | None = None,
) -> list[str]:
    """Return stale or missing Augur entries in the active Codex runtime config.

    Returns an empty list when the config matches the manifest's expected
    Augur servers, marketplace, and plugin entries.
    """
    requested_root = Path(project_root).expanduser().resolve() if project_root else _default_project_root()
    root = global_mcp_project_root(requested_root)
    home = Path(codex_home).expanduser() if codex_home else CODEX_HOME
    target = config_path or (home / "config.toml")
    if not target.exists():
        return [f"missing Codex config {target}"]

    current = _load_toml(target)
    if not current:
        return [f"empty or unreadable Codex config {target}"]

    issues: list[str] = []
    servers = current.get("mcp_servers")
    if not isinstance(servers, dict):
        servers = {}
        issues.append("missing mcp_servers table")
    desired_servers = _build_codex_mcp_servers(
        root,
        existing_server_ids={str(server_id) for server_id in servers if str(server_id).startswith("augur")},
        include_project_scoped=True,
    )

    if "augur" in servers:
        issues.append("legacy MCP server augur is still registered")

    for server_id, expected in sorted(desired_servers.items()):
        actual = servers.get(server_id)
        if actual is None:
            issues.append(f"missing MCP server {server_id}")
        elif actual != expected:
            issues.append(f"stale MCP server {server_id}")

    marketplaces = current.get("marketplaces")
    marketplace = marketplaces.get("augur-local") if isinstance(marketplaces, dict) else None
    expected_marketplace = {"source": root.as_posix(), "source_type": "local"}
    if marketplace is None:
        issues.append("missing marketplace augur-local")
    elif marketplace != expected_marketplace:
        issues.append("stale marketplace augur-local")

    plugins = current.get("plugins")
    plugin = plugins.get("augur@augur-local") if isinstance(plugins, dict) else None
    if plugin is None:
        issues.append("missing plugin augur@augur-local")
    elif not isinstance(plugin, dict) or plugin.get("enabled") is not True:
        issues.append("disabled plugin augur@augur-local")

    return issues
