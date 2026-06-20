from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace


class _FakeMCP:
    def __init__(
        self,
        tools: dict[str, str],
        *,
        input_schemas: dict[str, dict] | None = None,
    ) -> None:
        self._tools = {name: object() for name in tools}
        self._tool_descriptions = tools
        self._input_schemas = input_schemas or {}
        self.calls: list[tuple[str, dict]] = []

    async def list_tools(self) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                name=name,
                description=description,
                inputSchema=self._input_schemas.get(name),
            )
            for name, description in self._tool_descriptions.items()
        ]

    async def call_tool(self, tool_name: str, params: dict) -> list[SimpleNamespace]:
        self.calls.append((tool_name, params))
        return [SimpleNamespace(text=f"called {tool_name}")]


def test_cli_tool_listing_merges_core_and_framework_without_overwriting(
    monkeypatch,
) -> None:
    import src.cli as cli

    core = _FakeMCP({"list-skills": "Core skills"})
    framework = _FakeMCP({"list-skills": "Framework duplicate", "memory-search": "Search"})
    monkeypatch.setattr(cli, "_CLI_MCPS", [core, framework])
    monkeypatch.setattr(cli, "_TOOLS_REGISTERED", False)

    tools = cli.get_available_tools()

    assert tools["list-skills"]["description"] == "Core skills"
    assert tools["memory-search"]["description"] == "Search"


def test_cli_tool_call_routes_to_runtime_that_owns_tool(monkeypatch) -> None:
    import src.cli as cli

    core = _FakeMCP({"list-skills": "Core skills"})
    framework = _FakeMCP({"memory-search": "Search"})
    monkeypatch.setattr(cli, "_CLI_MCPS", [core, framework])
    monkeypatch.setattr(cli, "_TOOLS_REGISTERED", False)

    result = asyncio.run(cli.call_tool("memory-search", {"query": "agent"}))

    assert result == "called memory-search"
    assert core.calls == []
    assert framework.calls == [("memory-search", {"params": {"query": "agent"}})]


def test_cli_tool_call_uses_direct_args_for_direct_schema_tool(monkeypatch) -> None:
    import src.cli as cli

    browse_schema = {
        "properties": {
            "category": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["category"],
        "type": "object",
    }
    framework = _FakeMCP(
        {"browse-index": "Browse"},
        input_schemas={"browse-index": browse_schema},
    )
    monkeypatch.setattr(cli, "_CLI_MCPS", [framework])
    monkeypatch.setattr(cli, "_TOOLS_REGISTERED", False)

    result = asyncio.run(cli.call_tool("browse-index", {"category": "mcp-tools", "limit": 3}))

    assert result == "called browse-index"
    assert framework.calls == [("browse-index", {"category": "mcp-tools", "limit": 3})]


def test_cli_main_routes_unknown_first_positional_as_mcp_tool(
    monkeypatch,
    capsys,
) -> None:
    import src.cli as cli

    core = _FakeMCP({"list-skills": "Core skills"})
    monkeypatch.setattr(cli, "_CLI_MCPS", [core])
    monkeypatch.setattr(cli, "_TOOLS_REGISTERED", False)
    monkeypatch.setattr(sys, "argv", ["aug", "list-skills", "--limit", "1"])

    assert cli.main() == 0

    captured = capsys.readouterr()
    assert "called list-skills" in captured.out
    assert core.calls == [("list-skills", {"params": {"limit": 1}})]
