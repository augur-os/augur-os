"""Entry point: python -m augur_core."""

from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
from src.mcp.augur_core.tools import register_core_tools
from src.mcp.augur_shared.mcp_sdk import (
    _pin_mcp_sdk_package,
    mcp_tool_interceptor,
    metrics,
)


def _client_id_from_argv(argv: list[str] | None = None) -> str:
    args = list(sys.argv[1:] if argv is None else argv)
    for index, arg in enumerate(args):
        if arg == "--client-id" and index + 1 < len(args):
            return args[index + 1]
        if arg.startswith("--client-id="):
            return arg.split("=", 1)[1]
    return "client-mcp"


def run() -> int:
    _pin_mcp_sdk_package()
    mcp = FastMCP("augur-core")
    register_core_tools(
        mcp,
        mcp_tool_interceptor,
        metrics,
        capability_target=_client_id_from_argv(),
    )
    mcp.run()
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
