"""Shared MCP config rendering for plugin-pack formatters."""
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
from pathlib import Path
import sys
from typing import Any


def _is_project_root(candidate: Path) -> bool:
    return (
        (candidate / "config" / "system" / "mcp_servers.yaml").is_file()
        or (
            (candidate / "pyproject.toml").is_file()
            and (
                (candidate / "src" / "config" / "paths.py").is_file()
                or (candidate / "config" / "system").is_dir()
            )
        )
    )


def _find_repo_root(start_file: str | Path = __file__) -> Path:
    start = Path(start_file).resolve()
    for candidate in (start.parent, *start.parents):
        if _is_project_root(candidate):
            return candidate
    return start.parents[4]


REPO_ROOT = _find_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.cli_config.manifest import ServerEntry, load_manifest


def resolve_project_python_path(project_root: Path) -> str:
    """Return the project venv Python path, with native Windows layout first."""
    for candidate in (
        project_root / ".venv" / "Scripts" / "python.exe",
        project_root / ".venv" / "bin" / "python3",
        project_root / ".venv" / "bin" / "python",
    ):
        if candidate.exists():
            return str(candidate)
    return "python3"


def _server_module(entry: ServerEntry) -> str | None:
    try:
        module_index = entry.args.index("-m") + 1
    except ValueError:
        return None
    if module_index >= len(entry.args):
        return None
    return entry.args[module_index]


def _args_for_client(entry: ServerEntry, client_id: str) -> list[str]:
    args = list(entry.args)
    if client_id in entry.per_client_args:
        args.extend(entry.per_client_args[client_id])
    elif _server_module(entry) != "augur_shared.bundle_server":
        args.extend(["--client-id", client_id])
    return args


def _render_env(entry: ServerEntry, project_root: Path) -> dict[str, str]:
    root_text = str(project_root)
    env = {
        key: value.replace("${AUGUR_ROOT}", root_text)
        for key, value in entry.env.items()
    }
    env["AUGUR_ROOT"] = root_text
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault(
        "PYTHONPATH",
        f"{project_root / 'project-brain'}:{project_root}:{project_root / 'src' / 'mcp'}",
    )
    return env


def build_augur_mcp_servers(
    project_root: Path,
    python_path: str,
    client_id: str,
    existing_server_ids: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Render all canonical Augur MCP servers for a plugin target."""
    manifest = load_manifest(_find_repo_root() / "config" / "system" / "mcp_servers.yaml")
    servers: dict[str, dict[str, Any]] = {}
    for entry in manifest.all_augur_servers_for_client(
        client_id,
        existing_server_ids=existing_server_ids,
        include_project_scoped=True,
    ):
        if client_id == "gemini" and entry.bundle:
            continue
        servers[entry.id] = {
            "command": python_path,
            "args": _args_for_client(entry, client_id),
            "cwd": str(project_root),
            "env": _render_env(entry, project_root),
        }
    return servers


def build_augur_mcp_config(
    project_root: Path,
    python_path: str,
    client_id: str,
    existing_server_ids: set[str] | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "mcpServers": build_augur_mcp_servers(
            project_root,
            python_path,
            client_id,
            existing_server_ids=existing_server_ids,
        )
    }


def prune_augur_servers(servers: dict[str, Any]) -> None:
    """Remove stale managed Augur server entries before writing current ones."""
    for server_name in list(servers):
        if server_name.startswith("augur"):
            del servers[server_name]
