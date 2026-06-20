"""MCP tool definitions for user-configurable wiki queries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import yaml

from skills.wiki.scripts.wiki_query_registry import list_queries, read_query, write_query
from skills.wiki.scripts.wiki_query_runner import run_query
from src.config.paths import get_vault_dir
from src.lib.frontmatter_utils import parse_frontmatter

from ._shared import tool_annotations

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

DEFAULT_QUERIES_PATH = Path(__file__).resolve().parents[2] / "assets" / "seeds" / "queries-defaults.yaml"


async def wiki_queries_list_impl() -> str:
    """Return every registered wiki query with its persisted run status."""
    try:
        queries = list_queries()
        return json.dumps(
            {
                "success": True,
                "queries": [
                    {
                        "id": query_id,
                        "spec": spec,
                        "status": _status_for_query(query_id, spec),
                    }
                    for query_id, spec in sorted(queries.items())
                ],
                "count": len(queries),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


async def wiki_queries_read_impl(id: str = "") -> str:
    """Return one registered wiki query spec with its persisted run status."""
    query_id = id.strip()
    if not query_id:
        return json.dumps({"success": False, "error": "Query id is required"}, ensure_ascii=False)

    try:
        spec = read_query(query_id)
        if spec is None:
            return json.dumps(
                {"success": False, "error": f"Query not found: {query_id}"},
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "success": True,
                "id": query_id,
                "spec": spec,
                "status": _status_for_query(query_id, spec),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


async def wiki_queries_write_impl(id: str = "", spec_json: str = "") -> str:
    """Validate and persist one wiki query spec."""
    query_id = id.strip()
    if not query_id:
        return json.dumps({"success": False, "error": "Query id is required"}, ensure_ascii=False)

    try:
        spec = json.loads(spec_json)
    except json.JSONDecodeError as exc:
        return json.dumps({"success": False, "error": f"Invalid spec_json: {exc}"}, ensure_ascii=False)

    if not isinstance(spec, dict):
        return json.dumps({"success": False, "error": "spec_json must decode to an object"}, ensure_ascii=False)

    try:
        path = write_query(query_id, spec)
        return json.dumps(
            {
                "success": True,
                "id": query_id,
                "path": str(path),
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


async def wiki_queries_seed_defaults_impl() -> str:
    """Seed the default query registry entries without overwriting existing ids."""
    try:
        defaults = _load_default_queries()
        existing = list_queries()
        seeded: list[str] = []
        skipped: list[str] = []

        for query_id, spec in sorted(defaults.items()):
            if query_id in existing:
                skipped.append(query_id)
                continue
            write_query(query_id, spec)
            seeded.append(query_id)

        return json.dumps(
            {
                "success": True,
                "seeded": seeded,
                "skipped": skipped,
                "count": len(defaults),
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


async def wiki_queries_run_impl(id: str = "", synthesis_markdown: str = "") -> str:
    """Run one wiki query and return the full runner result."""
    query_id = id.strip()
    if not query_id:
        return json.dumps({"success": False, "query_id": "", "error": "Query id is required"}, ensure_ascii=False)

    try:
        return json.dumps(
            run_query(query_id, synthesis_markdown=synthesis_markdown or None).to_dict(),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    except Exception as exc:
        return json.dumps(
            {"success": False, "query_id": query_id, "error": str(exc)},
            ensure_ascii=False,
        )


def register_wiki_queries_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any = None,
) -> None:
    """Register wiki query MCP tools."""

    @mcp.tool(
        name="wiki-queries-list",
        annotations=tool_annotations(
            {
                "title": "Wiki Queries List",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def wiki_queries_list_tool() -> str:
        if metrics:
            metrics.track_tool("wiki_queries_list", skill="wiki")
        return await wiki_queries_list_impl()

    @mcp.tool(
        name="wiki-queries-read",
        annotations=tool_annotations(
            {
                "title": "Wiki Queries Read",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def wiki_queries_read_tool(id: str = "") -> str:
        if metrics:
            metrics.track_tool("wiki_queries_read", skill="wiki")
        return await wiki_queries_read_impl(id=id)

    @mcp.tool(
        name="wiki-queries-write",
        annotations=tool_annotations(
            {
                "title": "Wiki Queries Write",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def wiki_queries_write_tool(id: str = "", spec_json: str = "") -> str:
        if metrics:
            metrics.track_tool("wiki_queries_write", skill="wiki")
        return await wiki_queries_write_impl(id=id, spec_json=spec_json)

    @mcp.tool(
        name="wiki-queries-seed-defaults",
        annotations=tool_annotations(
            {
                "title": "Wiki Queries Seed Defaults",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def wiki_queries_seed_defaults_tool() -> str:
        if metrics:
            metrics.track_tool("wiki_queries_seed_defaults", skill="wiki")
        return await wiki_queries_seed_defaults_impl()

    @mcp.tool(
        name="wiki-queries-run",
        annotations=tool_annotations(
            {
                "title": "Wiki Queries Run",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def wiki_queries_run_tool(id: str = "", synthesis_markdown: str = "") -> str:
        if metrics:
            metrics.track_tool("wiki_queries_run", skill="wiki")
        return await wiki_queries_run_impl(id=id, synthesis_markdown=synthesis_markdown)


def _load_default_queries() -> dict[str, dict[str, Any]]:
    if not DEFAULT_QUERIES_PATH.exists():
        raise FileNotFoundError(f"Default queries file not found: {DEFAULT_QUERIES_PATH}")
    raw = yaml.safe_load(DEFAULT_QUERIES_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("Default queries file root must be a mapping")
    queries = raw.get("queries", {})
    if not isinstance(queries, dict):
        raise ValueError("Default queries file 'queries' must be a mapping")
    return {str(query_id): spec for query_id, spec in queries.items() if isinstance(spec, dict)}


def _status_for_query(query_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    state = _load_state().get(query_id, {})
    output_path = _output_path(spec)
    source_fingerprint = None
    output_size = 0

    if output_path.exists():
        output_size = output_path.stat().st_size
        try:
            metadata, _ = parse_frontmatter(output_path)
            source_fingerprint = metadata.get("source_fingerprint")
        except Exception:
            source_fingerprint = None

    return {
        "last_run": state.get("last_run"),
        "last_error": state.get("last_error"),
        "output_size": output_size,
        "source_fingerprint": source_fingerprint,
    }


def _load_state() -> dict[str, Any]:
    path = get_vault_dir() / "wiki" / ".queries-state.json"
    if not path.exists():
        return {}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return state if isinstance(state, dict) else {}


def _output_path(spec: dict[str, Any]) -> Path:
    output = Path(str(spec.get("output") or ""))
    if len(output.parts) >= 2 and output.parts[0] == "vault":
        return get_vault_dir().joinpath(*output.parts[1:])
    return get_vault_dir() / output


__all__ = [
    "DEFAULT_QUERIES_PATH",
    "register_wiki_queries_tools",
    "wiki_queries_list_impl",
    "wiki_queries_read_impl",
    "wiki_queries_run_impl",
    "wiki_queries_seed_defaults_impl",
    "wiki_queries_write_impl",
]
