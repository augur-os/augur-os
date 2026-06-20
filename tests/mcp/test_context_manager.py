from __future__ import annotations

import asyncio
import json

from src.mcp.augur_shared.context_manager import ContextManager


class FakeMcp:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.removed: list[str] = []

    def add_tool(self, tool: object) -> None:
        self.added.append(tool)

    def remove_tool(self, tool_name: str) -> None:
        self.removed.append(tool_name)


def _write_config(tmp_path):
    config_path = tmp_path / "assembled_tool_config.json"
    config_path.write_text(
        json.dumps(
            {
                "core_tools": ["core-tool"],
                "tool_groups": {
                    "WIKI_MAINTENANCE": ["wiki-report-data", "wiki-rewrite-candidates"],
                },
                "pages": {
                    "/": {"groups": [], "max_tools": 10},
                    "/brain": {"groups": ["WIKI_MAINTENANCE"], "max_tools": 20},
                },
            }
        ),
        encoding="utf-8",
    )
    return config_path


def test_switch_context_tracks_active_tools_without_unregistering_runtime_tools(tmp_path) -> None:
    mcp = FakeMcp()
    ctx = ContextManager(mcp, config_path=_write_config(tmp_path))
    ctx.register_tool("wiki-report-data", object())
    ctx.register_tool("wiki-rewrite-candidates", object())
    ctx.initialize_core_tools()

    result = asyncio.run(ctx.switch_context("/brain"))

    assert result["success"] is True
    assert set(result["added"]) == {"wiki-report-data", "wiki-rewrite-candidates"}
    assert mcp.added == []
    assert mcp.removed == []
    assert set(ctx.get_active_tools()) == {
        "core-tool",
        "wiki-report-data",
        "wiki-rewrite-candidates",
    }


def test_switch_context_reports_removed_tools_without_removing_them_from_mcp(tmp_path) -> None:
    mcp = FakeMcp()
    ctx = ContextManager(mcp, config_path=_write_config(tmp_path))
    ctx.register_tool("wiki-report-data", object())
    ctx.register_tool("wiki-rewrite-candidates", object())
    ctx.initialize_core_tools()
    asyncio.run(ctx.switch_context("/brain"))

    result = asyncio.run(ctx.switch_context("/"))

    assert result["success"] is True
    assert set(result["removed"]) == {"wiki-report-data", "wiki-rewrite-candidates"}
    assert mcp.added == []
    assert mcp.removed == []
    assert set(ctx.get_active_tools()) == {"core-tool"}
