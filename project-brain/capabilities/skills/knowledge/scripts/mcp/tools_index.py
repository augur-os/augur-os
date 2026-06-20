"""Index build/rebuild/status tools.

Handles knowledge-project-index-rebuild and index-documents tools.
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
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

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


logger = get_entity_logger("mcp.knowledge.index")

TOOLS_DIR = Path(__file__).parent
PLUGIN_ROOT = TOOLS_DIR.parent

try:
    from src.config.paths import (
        get_documents_dir,
        get_project_root,
        get_rag_dir,
        get_vault_dir,
    )

    PROJECT_ROOT = get_project_root()
except ImportError:
    PROJECT_ROOT = PLUGIN_ROOT.parent.parent.parent.parent  # fallback
    if sys.platform == "darwin":
        get_rag_dir = lambda: Path.home() / "Library" / "Application Support" / "Augur" / "rag"
    else:
        get_rag_dir = lambda: Path.home() / ".local" / "share" / "augur" / "rag"
    get_vault_dir = lambda: None
    get_documents_dir = lambda: None


def _load_unified_indexer_module():
    import importlib.util as _ilu

    idx_path = PROJECT_ROOT / "src" / "lib" / "index" / "unified_indexer.py"
    idx_spec = _ilu.spec_from_file_location("unified_indexer", idx_path)
    if not idx_spec or not idx_spec.loader:
        raise ImportError(f"Cannot load unified_indexer from {idx_path}")
    idx_mod = _ilu.module_from_spec(idx_spec)
    idx_spec.loader.exec_module(idx_mod)
    return idx_mod


def _get_external_roots() -> tuple[Path | None, Path | None]:
    try:
        return get_vault_dir(), get_documents_dir()
    except Exception:
        return None, None


def _default_document_sources(documents_dir: Path | None) -> list[Any]:
    if documents_dir is None:
        return []
    from src.lib.index.document_source_config import configured_document_sources

    return configured_document_sources(
        project_root=PROJECT_ROOT,
        documents_dir=documents_dir,
    )


def _document_source_metadata(sources: list[Any]) -> list[dict[str, str]]:
    return [
        {
            "id": source.id,
            "name": source.name,
            "path": str(source.resolved_path),
            "provider": str(getattr(source, "provider", "")),
            "source_type": str(getattr(source, "source_type", "")),
            "attached_brain_ids": ",".join(
                getattr(source, "attached_brain_ids", ()) or ()
            ),
        }
        for source in sources
    ]


def register_index_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register index build/rebuild tools with the MCP server."""
    logger.info("Registering index tools...")

    @mcp.tool(
        name="knowledge-project-index-rebuild",
        annotations=tool_annotations(
            {
                "title": "Rebuild Knowledge Project Index",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_project_index_rebuild_tool() -> str:
        """Rebuild the centralized project index for project-wide search."""
        metrics.track_tool("knowledge_project_index_rebuild", skill="knowledge")

        try:
            reindex_all = _load_unified_indexer_module().reindex_all
            rag_dir = get_rag_dir()
            vault_dir, documents_dir = _get_external_roots()
            sources = _default_document_sources(documents_dir)
            counts = await asyncio.to_thread(
                reindex_all,
                PROJECT_ROOT,
                rag_dir,
                vault_dir,
                documents_dir,
                sources,
            )

            return json.dumps(
                {
                    "success": True,
                    "message": "Rebuilt project index via unified indexer",
                    "outputPath": str(rag_dir),
                    "indexedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "counts": counts,
                    "sources": _document_source_metadata(sources),
                },
                indent=2,
            )
        except Exception as e:
            logger.error(f"Failed to rebuild project index: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    # =========================================================================
    # Index Documents
    # =========================================================================

    @mcp.tool(
        name="index-documents",
        annotations=tool_annotations(
            {
                "title": "Trigger Document Reindexing",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def index_documents_tool(
        force: bool = False,
        project: str | None = None,
        project_id: str | None = None,
        source_type: str | None = None,
    ) -> str:
        """Trigger document reindexing.

        Args:
            force: Force full reindex even if unchanged
            project: Optional project name to limit reindex scope (dashboard alias: project_id)
            project_id: Dashboard alias for project
            source_type: Source type filter (ignored, always indexes all)

        Returns:
            str: JSON with reindex results
        """
        # Accept dashboard param name
        project = project or project_id
        metrics.track_tool("index_documents", skill="knowledge")

        started = datetime.now(timezone.utc).isoformat()
        try:
            reindex_all = _load_unified_indexer_module().reindex_all
            rag_dir = get_rag_dir()
            vault_dir, documents_dir = _get_external_roots()
            sources = _default_document_sources(documents_dir)
            counts = await asyncio.to_thread(
                reindex_all,
                PROJECT_ROOT,
                rag_dir,
                vault_dir,
                documents_dir,
                sources,
            )
            finished = datetime.now(timezone.utc).isoformat()

            return json.dumps({
                "startedAt": started,
                "finishedAt": finished,
                "force": force,
                "sources": _document_source_metadata(sources),
                "results": counts,
            }, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to reindex documents: {e}", exc_info=True)
            finished = datetime.now(timezone.utc).isoformat()
            return json.dumps({
                "startedAt": started,
                "finishedAt": finished,
                "force": force,
                "results": {},
                "error": str(e),
            }, indent=2, default=str)
