"""RAG knowledge management tools.

Handles configuration, hub files, linked folders, knowledge sources,
and recent ingestions.
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
import asyncio
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import yaml

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.mcp.augur_shared.logging import get_entity_logger
    from src.mcp.augur_shared.annotations import tool_annotations
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        logging = importlib.import_module("logging")
        return logging.getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations

import sys

logger = get_entity_logger("mcp.knowledge.rag.knowledge")

try:
    from src.config.paths import get_rag_dir
except ImportError:
    if sys.platform == "darwin":
        get_rag_dir = lambda: Path.home() / "Library" / "Application Support" / "Augur" / "rag"
    else:
        get_rag_dir = lambda: Path.home() / ".local" / "share" / "augur" / "rag"


def register_rag_knowledge_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register knowledge config, hub files, linked folders, and sources tools."""
    from . import _read_projects_file, _write_projects_file, _slugify

    # =========================================================================
    # Knowledge Config
    # =========================================================================

    @mcp.tool(
        name="knowledge-config",
        annotations=tool_annotations(
            {
                "title": "Knowledge Configuration",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_config_tool(
        action: str = "read",
        config: dict[str, Any] | None = None,
        updates: dict[str, Any] | None = None,
    ) -> str:
        """Read or write RAG configuration.

        Args:
            action: 'read' to get config, 'update'/'write' to update it
            config: New config for write action
            updates: Dashboard alias for config (used with action='update')

        Returns:
            str: JSON with config data
        """
        # Accept dashboard param names
        if action == "update":
            action = "write"
        if config is None and updates is not None:
            config = updates
        metrics.track_tool("knowledge_config", skill="knowledge")

        def _handle_config(act: str, new_config: dict[str, Any] | None) -> dict[str, Any]:
            rag_dir = get_rag_dir()
            config_path = rag_dir / "config.yaml"

            default_config: dict[str, Any] = {
                "version": "2.0",
                "core": {
                    "index_mode": "manual",
                    "auto_index": False,
                },
                "optional": {
                    "ocr_enabled": False,
                    "embedding_model": "none",
                },
                "linked_folders": [],
                "indexing": {
                    "max_file_size_mb": 50,
                    "max_total_size_mb": 2000,
                    "max_files": 1000,
                    "exclude_patterns": [".git", "node_modules", "__pycache__"],
                },
            }

            if act == "write":
                if new_config is None:
                    return {"success": False, "error": "Config is required for write action"}
                rag_dir.mkdir(parents=True, exist_ok=True)
                config_path.write_text(
                    yaml.dump(new_config, default_flow_style=False, sort_keys=False, allow_unicode=True),
                    encoding="utf-8",
                )
                return {"success": True, "config": new_config}

            if not config_path.exists():
                return {"success": True, "config": default_config}
            try:
                data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    return {"success": True, "config": default_config}
                return {"success": True, "config": data}
            except Exception:
                return {"success": True, "config": default_config}

        try:
            result = await asyncio.to_thread(_handle_config, action, config)
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to handle knowledge config: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    # =========================================================================
    # Hub Files (~/Documents/Augur/)
    # =========================================================================

    @mcp.tool(
        name="knowledge-hub-files",
        annotations=tool_annotations(
            {
                "title": "Manage Hub Documents",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_hub_files_tool(
        action: str = "list",
        hub: str | None = None,
        skill: str | None = None,
        file_path: str | None = None,
        path: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """List, add, or remove documents in ~/Documents/Augur/.

        Args:
            action: 'list', 'add', 'remove', or 'delete'
            hub: Hub filter for list, or target hub for add
            skill: Skill name for add action
            file_path: Source file path for add action
            path: File path for delete/remove action
            tags: Optional tags for added file

        Returns:
            str: JSON with file list or action result
        """
        # Accept dashboard action alias
        if action == "remove":
            action = "delete"
        metrics.track_tool("knowledge_hub_files", skill="knowledge")

        def _handle_hub_files(
            act: str,
            hub_filter: str | None,
            skill_name: str | None,
            src_path: str | None,
            del_path: str | None,
        ) -> dict[str, Any]:
            from src.config.paths import get_documents_dir

            docs_dir = get_documents_dir()

            if act == "delete":
                if not del_path:
                    return {"success": False, "error": "Path is required for delete"}
                target = Path(del_path)
                if not target.is_absolute():
                    target = docs_dir / target
                if not target.exists():
                    return {"success": False, "error": f"File not found: {target}"}
                target.unlink()
                return {"success": True, "deleted": str(target), "removed": str(target)}

            if act == "add":
                if not src_path:
                    return {"success": False, "error": "file_path is required for add"}
                source = Path(src_path)
                if not source.exists():
                    return {"success": False, "error": f"Source file not found: {source}"}
                target_dir = docs_dir
                if hub_filter:
                    target_dir = target_dir / hub_filter
                if skill_name:
                    target_dir = target_dir / skill_name
                target_dir.mkdir(parents=True, exist_ok=True)
                dest = target_dir / source.name
                shutil.copy2(str(source), str(dest))
                file_info = {"path": str(dest), "hub": hub_filter, "skill": skill_name}
                return {"success": True, "added": str(dest), "file": file_info, "hub": hub_filter, "skill": skill_name}

            # Default: list
            files: list[dict[str, Any]] = []
            if not docs_dir.exists():
                return {"files": files}

            for f in sorted(docs_dir.rglob("*")):
                if f.is_dir():
                    continue
                try:
                    rel = f.relative_to(docs_dir)
                    parts = rel.parts
                    # Flat layout: parts[0] is the skill name (no bundle prefix).
                    file_skill = parts[0] if len(parts) > 1 else "general"
                    if hub_filter and file_skill != hub_filter:
                        continue
                    files.append({
                        "name": f.name,
                        "skill": file_skill,
                        "path": str(f),
                        "size": f.stat().st_size,
                        "format": f.suffix.lstrip(".") or "unknown",
                    })
                except Exception:
                    continue

            return {"files": files}

        try:
            result = await asyncio.to_thread(
                _handle_hub_files, action, hub or None, skill or None, file_path, path
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to handle hub files: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="knowledge-hub-files-stats",
        annotations=tool_annotations(
            {
                "title": "Hub Document Stats",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_hub_files_stats_tool() -> str:
        """Return stats about documents in ~/Documents/Augur/."""
        metrics.track_tool("knowledge_hub_files_stats", skill="knowledge")

        def _get_hub_file_stats() -> dict[str, Any]:
            from src.config.paths import get_documents_dir

            docs_dir = get_documents_dir()
            by_hub: dict[str, dict[str, int]] = {}
            total_files = 0
            total_size = 0

            if not docs_dir.exists():
                return {"totalFiles": 0, "totalSizeBytes": 0, "byHub": {}, "hubs": []}

            for f in docs_dir.rglob("*"):
                if f.is_dir():
                    continue
                try:
                    rel = f.relative_to(docs_dir)
                    parts = rel.parts
                    # Flat layout: parts[0] is the skill name (no bundle prefix).
                    skill_name = parts[0] if len(parts) > 1 else "general"
                    size = f.stat().st_size
                    total_files += 1
                    total_size += size

                    if skill_name not in by_hub:
                        by_hub[skill_name] = {"files": 0, "sizeBytes": 0}
                    by_hub[skill_name]["files"] += 1
                    by_hub[skill_name]["sizeBytes"] += size
                except Exception:
                    continue

            return {
                "totalFiles": total_files,
                "totalSizeBytes": total_size,
                "byHub": by_hub,
                "hubs": sorted(by_hub.keys()),
            }

        try:
            result = await asyncio.to_thread(_get_hub_file_stats)
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to get hub file stats: {e}", exc_info=True)
            return json.dumps({"totalFiles": 0, "totalSizeBytes": 0, "byHub": {}, "hubs": []})

    # =========================================================================
    # Linked Folders
    # =========================================================================

    @mcp.tool(
        name="knowledge-linked-folders",
        annotations=tool_annotations(
            {
                "title": "Manage Linked Folders",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_linked_folders_tool(
        action: str = "list",
        path: str | None = None,
        name: str | None = None,
        project_id: str | None = None,
        folder_path: str | None = None,
        skill_name: str | None = None,
        project_name: str | None = None,
        ocr_enabled: bool = True,
    ) -> str:
        """Manage linked folders for RAG indexing.

        Args:
            action: 'list', 'link'/'add', 'unlink'/'delete'
            path: Folder path for add action (dashboard alias: folder_path)
            folder_path: Dashboard alias for path
            name: Folder name for add action (dashboard alias: skill_name)
            skill_name: Dashboard alias for name
            project_id: Project ID for delete action
            project_name: Optional project name for add action
            ocr_enabled: Whether to enable OCR for linked folder (default True)

        Returns:
            str: JSON with folders list or action result
        """
        # Accept dashboard param names and action aliases
        if action == "link":
            action = "add"
        elif action == "unlink":
            action = "delete"
        path = path or folder_path
        name = name or skill_name or project_name
        metrics.track_tool("knowledge_linked_folders", skill="knowledge")

        def _handle_linked_folders(
            act: str,
            folder_path: str | None,
            folder_name: str | None,
            pid: str | None,
        ) -> dict[str, Any]:
            entries = _read_projects_file()

            if act == "delete":
                if not pid:
                    return {"success": False, "error": "project_id is required for delete"}
                new_entries = [e for e in entries if e.get("id") != pid]
                if len(new_entries) == len(entries):
                    return {"success": False, "error": f"Project '{pid}' not found"}
                _write_projects_file(new_entries)
                return {"success": True, "message": f"Removed linked folder '{pid}'"}

            if act == "add":
                if not folder_path:
                    return {"success": False, "error": "path is required for add"}
                p = Path(folder_path).resolve()
                if not p.is_dir():
                    return {"success": False, "error": f"Directory not found: {p}"}
                new_name = folder_name or p.name
                new_id = _slugify(new_name)
                existing_ids = {str(e.get("id", "")).strip() for e in entries}
                if new_id in existing_ids:
                    new_id = f"{new_id}-{uuid.uuid4().hex[:6]}"
                timestamp = datetime.now(timezone.utc).isoformat()
                entries.append({
                    "id": new_id,
                    "name": new_name,
                    "path": str(p),
                    "created_at": timestamp,
                    "updated_at": timestamp,
                })
                _write_projects_file(entries)
                return {"success": True, "project_id": new_id, "message": f"Added linked folder '{new_name}'"}

            # Default: list
            folders = []
            for e in entries:
                if isinstance(e, dict):
                    folders.append({
                        "id": e.get("id", ""),
                        "name": e.get("name", ""),
                        "path": e.get("path", ""),
                        "created_at": e.get("created_at", ""),
                    })
            return {"success": True, "folders": folders, "count": len(folders)}

        try:
            result = await asyncio.to_thread(_handle_linked_folders, action, path, name, project_id)
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to handle linked folders: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    # =========================================================================
    # Knowledge Sources
    # =========================================================================

    @mcp.tool(
        name="knowledge-sources",
        annotations=tool_annotations(
            {
                "title": "Manage Knowledge Sources",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_sources_tool(
        action: str = "list",
        source: dict[str, Any] | None = None,
        path: str = "",
        project_id: str = "",
        project: str = "",
    ) -> str:
        """Manage RAG sources.

        Args:
            action: 'list' to get sources, 'add' to add a source
            source: Source definition for add action
            path: File path for add action (dashboard shorthand, builds source dict)
            project_id: Project ID filter for list, or target project for add
            project: Dashboard alias for project_id

        Returns:
            str: JSON with sources list
        """
        # Accept dashboard param name
        project_id = project_id or project
        # Dashboard shorthand: path + project_id → source dict
        if action == "add" and source is None and path:
            source = {"path": path}
            if project_id:
                source["project_id"] = project_id
        metrics.track_tool("knowledge_sources", skill="knowledge")

        # project_id is accepted but not currently used for filtering
        _ = project_id

        def _handle_sources(act: str, new_source: dict[str, Any] | None) -> dict[str, Any]:
            rag_dir = get_rag_dir()
            sources_path = rag_dir / "sources.yaml"

            def _read_sources() -> list[dict[str, Any]]:
                if not sources_path.exists():
                    return []
                try:
                    data = yaml.safe_load(sources_path.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        s = data.get("sources", [])
                        return s if isinstance(s, list) else []
                except Exception:
                    return []
                return []

            if act == "add":
                if not new_source:
                    return {"success": False, "error": "Source definition is required for add"}
                sources = _read_sources()
                new_source["added_at"] = datetime.now(timezone.utc).isoformat()
                sources.append(new_source)
                rag_dir.mkdir(parents=True, exist_ok=True)
                sources_path.write_text(
                    yaml.dump({"version": 1, "sources": sources}, default_flow_style=False, sort_keys=False, allow_unicode=True),
                    encoding="utf-8",
                )
                return {"sources": sources}

            return {"sources": _read_sources()}

        try:
            result = await asyncio.to_thread(_handle_sources, action, source)
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to handle knowledge sources: {e}", exc_info=True)
            return json.dumps({"sources": []})

    # =========================================================================
    # Recent Ingestions
    # =========================================================================

    @mcp.tool(
        name="get-recent-ingestions",
        annotations=tool_annotations(
            {
                "title": "Recent Ingestions",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_recent_ingestions_tool(limit: int = 8) -> str:
        """List recently indexed items.

        Args:
            limit: Maximum number of items to return (default 8)

        Returns:
            str: JSON with recent ingestion items
        """
        metrics.track_tool("get_recent_ingestions", skill="knowledge")

        def _get_recent() -> list[dict[str, Any]]:
            rag_dir = get_rag_dir()
            manifest_path = rag_dir / "_meta" / "manifest.yaml"
            if not manifest_path.exists():
                return []

            try:
                manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                return []

            entries = manifest.get("entries", [])
            if not isinstance(entries, list):
                return []

            indexed = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                indexed.append({
                    "name": entry.get("name", "unknown"),
                    "type": entry.get("type", "unknown"),
                    "indexed_at": entry.get("indexed_at", manifest.get("indexed_at", "")),
                    "hub": entry.get("hub", entry.get("bundle", "")),
                })

            indexed.sort(key=lambda x: str(x.get("indexed_at", "")), reverse=True)
            return indexed[:limit]

        try:
            items = await asyncio.to_thread(_get_recent)
            return json.dumps({"items": items}, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to get recent ingestions: {e}", exc_info=True)
            return json.dumps({"items": []})
