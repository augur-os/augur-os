"""
Knowledge MCP Tool Implementations.

Tools for managing RAG projects, knowledge bases, and session memory.
Migrated from augur-mcp/domain/skills.py (RAG tools only)

This module is loaded dynamically by the Augur MCP server
via the plugin tool loading system.

Memory tools (ADR-028) are also registered here as part of the knowledge plugin.
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
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import yaml

from src.lib.data_result import read_skill_data

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.mcp.augur_shared.logging import get_entity_logger
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        logging = importlib.import_module("logging")
        return logging.getLogger(name)


logger = get_entity_logger("mcp.knowledge")

TOOLS_DIR = Path(__file__).parent
PLUGIN_ROOT = TOOLS_DIR.parent

try:
    from src.config.paths import get_project_root, get_rag_dir

    PROJECT_ROOT = get_project_root()
except ImportError:
    # Fallback: skills/knowledge/scripts/mcp -> project root
    PROJECT_ROOT = PLUGIN_ROOT.parent.parent.parent.parent  # fallback
    if sys.platform == "darwin":
        get_rag_dir = lambda: Path.home() / "Library" / "Application Support" / "Augur" / "rag"
    else:
        get_rag_dir = lambda: Path.home() / ".local" / "share" / "augur" / "rag"


# ---------------------------------------------------------------------------
# Pure-Python RAG project helpers (used by tools_rag.py)
# ---------------------------------------------------------------------------

_DEFAULT_SETTINGS: dict[str, Any] = {
    "index_mode": "manual",
    "limits": {
        "max_file_size_mb": 50,
        "max_total_size_mb": 2000,
        "max_files": 1000,
    },
}


def _rag_projects_file() -> Path:
    """Return the path to the central projects.yaml."""
    return get_rag_dir() / "projects.yaml"


def _rag_projects_dir() -> Path:
    """Return the directory that holds per-project subdirectories."""
    return get_rag_dir() / "projects"


def _read_projects_file() -> list[dict[str, Any]]:
    """Read projects.yaml and return the project entries list."""
    path = _rag_projects_file()
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return []
        entries = data.get("projects", [])
        return entries if isinstance(entries, list) else []
    except Exception:
        return []


def _write_projects_file(entries: list[dict[str, Any]]) -> None:
    """Write the projects list back to projects.yaml."""
    path = _rag_projects_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "projects": entries}
    path.write_text(yaml.dump(payload, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _read_project_settings(project_id: str) -> dict[str, Any]:
    """Read per-project settings.yaml, returning defaults on any failure."""
    settings_path = _rag_projects_dir() / project_id / "settings.yaml"
    try:
        if settings_path.exists():
            data = yaml.safe_load(settings_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                limits_raw = data.get("limits", {})
                if not isinstance(limits_raw, dict):
                    limits_raw = {}
                defaults = _DEFAULT_SETTINGS["limits"]
                return {
                    "index_mode": data.get("index_mode", "manual") if data.get("index_mode") in ("auto", "manual") else "manual",
                    "limits": {
                        "max_file_size_mb": limits_raw.get("max_file_size_mb", defaults["max_file_size_mb"]),
                        "max_total_size_mb": limits_raw.get("max_total_size_mb", defaults["max_total_size_mb"]),
                        "max_files": limits_raw.get("max_files", defaults["max_files"]),
                    },
                }
    except Exception:
        pass
    return {
        "index_mode": _DEFAULT_SETTINGS["index_mode"],
        "limits": dict(_DEFAULT_SETTINGS["limits"]),
    }


def _write_project_settings(project_id: str, settings: dict[str, Any]) -> None:
    """Write per-project settings.yaml."""
    proj_dir = _rag_projects_dir() / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, **settings}
    (proj_dir / "settings.yaml").write_text(
        yaml.dump(payload, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _list_rag_projects() -> list[dict[str, Any]]:
    """List all RAG projects with their settings (pure Python)."""
    entries = _read_projects_file()
    projects: list[dict[str, Any]] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        pid = str(entry.get("id", "")).strip()
        name = str(entry.get("name", "")).strip()
        if not pid or not name:
            continue

        settings = _read_project_settings(pid)
        projects.append({
            "id": pid,
            "name": name,
            "created_at": str(entry.get("created_at", "")),
            "updated_at": str(entry.get("updated_at", "")) or None,
            "index_mode": settings["index_mode"],
            "limits": settings["limits"],
        })

    projects.sort(key=lambda p: p["name"].lower())

    # DataResult fallback: show starter projects when no real data exists
    if not projects:
        result = read_skill_data(__file__, "rag-projects.yaml", default={}, loader="yaml")
        if isinstance(result.data, dict):
            seed_entries = result.data.get("projects", [])
            for entry in seed_entries:
                if isinstance(entry, dict):
                    projects.append({
                        "id": str(entry.get("id", "")),
                        "name": str(entry.get("name", "")),
                        "created_at": str(entry.get("created_at", "")),
                        "updated_at": entry.get("updated_at"),
                        "index_mode": "manual",
                        "limits": dict(_DEFAULT_SETTINGS["limits"]),
                        "source": result.source,
                    })

    return projects


def _slugify(value: str) -> str:
    """Slugify a project name."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    slug = slug.strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug


def _create_rag_project(
    name: str,
    index_mode: str | None = None,
    limits: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a new RAG project (pure Python)."""
    trimmed = name.strip()
    if not trimmed:
        raise ValueError("Project name is required")

    entries = _read_projects_file()
    existing_ids = {str(e.get("id", "")).strip() for e in entries if isinstance(e, dict)}

    base = _slugify(trimmed)
    project_id = base if base and base not in existing_ids else f"{base or 'rag'}-{uuid.uuid4().hex[:6]}"

    timestamp = datetime.now(timezone.utc).isoformat()

    entries.append({
        "id": project_id,
        "name": trimmed,
        "created_at": timestamp,
        "updated_at": timestamp,
    })
    _write_projects_file(entries)

    settings: dict[str, Any] = {
        "index_mode": index_mode if index_mode in ("auto", "manual") else "manual",
        "limits": {**_DEFAULT_SETTINGS["limits"], **(limits or {})},
    }
    _write_project_settings(project_id, settings)

    # Write empty sources.yaml
    sources_path = _rag_projects_dir() / project_id / "sources.yaml"
    sources_path.parent.mkdir(parents=True, exist_ok=True)
    sources_path.write_text(
        yaml.dump({"version": 1, "sources": []}, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    return {
        "id": project_id,
        "name": trimmed,
        "created_at": timestamp,
        "updated_at": timestamp,
        "index_mode": settings["index_mode"],
        "limits": settings["limits"],
    }


# ---------------------------------------------------------------------------
# Thin dispatcher — delegates to per-group tool modules
# ---------------------------------------------------------------------------

def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register all Knowledge tools with the MCP server."""
    logger.info("Registering knowledge MCP tools...")

    from .tools_rag import register_rag_tools
    from .tools_memory import register_memory_tools
    from .tools_index import register_index_tools
    from .tools_summarize import register_summarize_tools
    from .tools_voice_profile import register_voice_profile_tools

    register_rag_tools(mcp, mcp_tool_interceptor, metrics)
    register_memory_tools(mcp, mcp_tool_interceptor, metrics)
    register_index_tools(mcp, mcp_tool_interceptor, metrics)
    register_summarize_tools(mcp, mcp_tool_interceptor, metrics)
    register_voice_profile_tools(mcp, mcp_tool_interceptor, metrics)

    logger.info("Knowledge MCP tools registered successfully (including memory + summarize + profile tools)")


__all__ = ["register_tools"]
