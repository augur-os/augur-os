"""Smoke tests for the extracted unified_rag_search library."""
from __future__ import annotations


def test_unified_rag_search_importable_from_package():
    """unified_rag_search is reachable via the src.lib.index public API."""
    from src.lib.index import unified_rag_search  # noqa: F401


def test_unified_rag_search_importable_from_submodule():
    """unified_rag_search is reachable via its owning submodule."""
    from src.lib.index.unified_search import unified_rag_search  # noqa: F401


def test_unified_rag_search_origin_module():
    """The function originates in src.lib.index.unified_search, not a re-export shim."""
    from src.lib.index import unified_rag_search

    assert unified_rag_search.__module__ == "src.lib.index.unified_search"


def test_supporting_helpers_importable():
    """Companion helpers (iterative_search, resolve_scope_paths) are also exposed."""
    from src.lib.index import iterative_search, resolve_scope_paths  # noqa: F401

    assert iterative_search.__module__ == "src.lib.index.unified_search"
    assert resolve_scope_paths.__module__ == "src.lib.index.unified_search"


def test_rag_mcp_wrapper_re_exports_function():
    """The rag MCP wrapper still exposes unified_rag_search by importing it from the library."""
    from skills.rag.scripts.mcp import rag_tools

    assert rag_tools.unified_rag_search.__module__ == "src.lib.index.unified_search"
