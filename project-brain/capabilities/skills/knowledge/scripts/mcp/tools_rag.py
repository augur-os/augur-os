"""RAG project, search, and document management tools.

Handles RAG projects CRUD, linked folders, knowledge sources,
hub files, document listing, OCR queue, search status, unified search,
knowledge graph, and project index stats/search.

This module delegates to sub-modules:
- rag_projects: Project CRUD and indexing
- rag_knowledge: Config, hub files, linked folders, sources
- rag_search: Search, stats, graph, documents, OCR queue
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from .rag_knowledge import register_rag_knowledge_tools
from .rag_projects import register_rag_project_tools
from .rag_search import register_rag_search_tools
from .tools_reflect import register_reflect_tools


def register_rag_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register RAG project and search tools with the MCP server."""
    register_rag_project_tools(mcp, mcp_tool_interceptor, metrics)
    register_rag_knowledge_tools(mcp, mcp_tool_interceptor, metrics)
    register_rag_search_tools(mcp, mcp_tool_interceptor, metrics)
    register_reflect_tools(mcp, mcp_tool_interceptor, metrics)
