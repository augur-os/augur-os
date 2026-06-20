"""Summarization and PDF tools.

Handles URL/YouTube/podcast/file summarization and PDF editing
via CLIBridge wrappers.
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
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.lib.extraction import extract
except ImportError:  # pragma: no cover — extraction library always available post-Track-1
    extract = None  # type: ignore[assignment]

try:
    from src.mcp.augur_shared.logging import get_entity_logger
    from src.mcp.augur_shared.annotations import tool_annotations
    from src.mcp.augur_shared.cli_bridge import CLIBridge
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        logging = importlib.import_module("logging")
        return logging.getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations

    CLIBridge = None  # type: ignore


logger = get_entity_logger("mcp.knowledge.summarize")


def register_summarize_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register summarization and PDF tools with the MCP server."""
    logger.info("Registering summarize tools...")

    summarize_cli = CLIBridge("summarize", install_hint="brew install steipete/tap/summarize") if CLIBridge else None
    nano_pdf_cli = CLIBridge("nano-pdf", install_hint="brew install nano-pdf") if CLIBridge else None

    @mcp.tool(
        name="knowledge-summarize-url",
        annotations=tool_annotations(
            {
                "title": "Summarize URL",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_summarize_url_tool(url: str) -> str:
        """Summarize a webpage or article.

        Args:
            url: URL to summarize

        Returns:
            str: Summary text
        """
        metrics.track_tool("knowledge_summarize_url", skill="knowledge")

        if not summarize_cli:
            return json.dumps({"error": "CLIBridge not available"})

        return summarize_cli.run_or_error([url], timeout=60)

    @mcp.tool(
        name="knowledge-summarize-youtube",
        annotations=tool_annotations(
            {
                "title": "Summarize YouTube Video",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_summarize_youtube_tool(url: str) -> str:
        """Summarize a YouTube video.

        Args:
            url: YouTube URL

        Returns:
            str: Video summary
        """
        metrics.track_tool("knowledge_summarize_youtube", skill="knowledge")

        if not summarize_cli:
            return json.dumps({"error": "CLIBridge not available"})

        return summarize_cli.run_or_error([url], timeout=120)

    @mcp.tool(
        name="knowledge-summarize-podcast",
        annotations=tool_annotations(
            {
                "title": "Summarize Podcast",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_summarize_podcast_tool(url: str) -> str:
        """Summarize a podcast episode.

        Args:
            url: Podcast episode URL

        Returns:
            str: Episode summary
        """
        metrics.track_tool("knowledge_summarize_podcast", skill="knowledge")

        if not summarize_cli:
            return json.dumps({"error": "CLIBridge not available"})

        return summarize_cli.run_or_error([url], timeout=180)

    @mcp.tool(
        name="knowledge-summarize-file",
        annotations=tool_annotations(
            {
                "title": "Summarize Local File",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_summarize_file_tool(file_path: str) -> str:
        """Extract content from a local file (PDF, DOCX, PPTX, images, etc.) via document-extractor (ADR-518).

        Returns extracted markdown content for the AI agent to summarize.

        Args:
            file_path: Path to local file

        Returns:
            str: JSON with {success, markdown, title, format, ...}
        """
        metrics.track_tool("knowledge_summarize_file", skill="knowledge")

        if extract is None:
            return json.dumps({"success": False, "error": "extraction library unavailable"})

        try:
            result = extract(file_path, max_tier=1)
            return json.dumps({
                "success": result.success,
                "markdown": result.markdown if result.success else "",
                "title": result.title,
                "format": result.format,
                "size_bytes": result.size_bytes,
                "error": result.error,
            })
        except Exception as exc:
            logger.error("Document extraction failed for %s: %s", file_path, exc)
            return json.dumps({"success": False, "error": str(exc)})

    # =========================================================================
    # PDF Tools (nano-pdf CLI)
    # =========================================================================

    @mcp.tool(
        name="knowledge-edit-pdf",
        annotations=tool_annotations(
            {
                "title": "Edit PDF",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_edit_pdf_tool(file_path: str, instruction: str) -> str:
        """Edit a PDF with natural language instructions.

        Args:
            file_path: Path to PDF file
            instruction: Natural language edit instruction

        Returns:
            str: Edit result
        """
        metrics.track_tool("knowledge_edit_pdf", skill="knowledge")

        if not nano_pdf_cli:
            return json.dumps({"error": "CLIBridge not available"})

        return nano_pdf_cli.run_or_error([file_path, "--instruction", instruction], timeout=120)
