"""Per-bundle MCP stdio server.

Usage: python -m src.mcp.augur_shared.bundle_server <bundle-name>

Resolves the bundle dir via _collect_skill_dirs(), creates a fresh
FastMCP instance, and calls just that bundle's register_tools() —
unlike the monolith, which registers all enabled bundles' tools.

Used by Track 2's per-bundle vault-tier servers (augur-apple, etc.).
After Track 3a PR 7, the manifest's vault-tier `args` reference this
canonical bundle server directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
from src.mcp.augur_shared.mcp_sdk import _pin_mcp_sdk_package
from src.mcp.augur_shared.plugin_tools import (
    _collect_skill_dirs,
    _load_bundle_mcp_module,
    _register_bundle_tools,
)


def run(bundle_name: str) -> int:
    """Start a per-bundle stdio MCP server for `bundle_name`.

    Returns:
        Exit code: 0 on clean shutdown, non-zero on error.
    """
    _pin_mcp_sdk_package()

    skill_entries = {sd.name: sd for _, sd in _collect_skill_dirs(apply_exclusions=False)}
    if bundle_name not in skill_entries:
        print(
            f"[augur_shared.bundle_server] bundle '{bundle_name}' not found in any registered skill dir",
            file=sys.stderr,
        )
        return 1

    skill_dir: Path = skill_entries[bundle_name]
    mcp_init = skill_dir / "scripts" / "mcp" / "__init__.py"
    if not mcp_init.exists():
        print(
            f"[augur_shared.bundle_server] bundle '{bundle_name}' has no scripts/mcp/__init__.py",
            file=sys.stderr,
        )
        return 1

    module = _load_bundle_mcp_module(skill_dir)
    if not hasattr(module, "register_tools"):
        print(
            f"[augur_shared.bundle_server] bundle '{bundle_name}' has no register_tools()",
            file=sys.stderr,
        )
        return 1

    mcp = FastMCP(f"augur-{bundle_name}")
    # Local imports defer FastMCP/SDK init until the bundle is resolved.
    # `mcp_tool_interceptor` and `metrics` come from the shared SDK singleton.
    from src.mcp.augur_shared.mcp_sdk import mcp_tool_interceptor, metrics

    _register_bundle_tools(module, skill_dir, mcp, mcp_tool_interceptor, metrics)
    mcp.run()
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m src.mcp.augur_shared.bundle_server <bundle-name>", file=sys.stderr)
        return 2
    return run(sys.argv[1])


if __name__ == "__main__":
    sys.exit(main())
