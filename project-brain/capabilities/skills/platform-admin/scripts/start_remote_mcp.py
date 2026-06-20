#!/usr/bin/env python3
"""
Start MCP server with streamable-http transport for remote access.

Reads config from config/remote/mcp-remote.yaml.
Caddy reverse proxy handles TLS and routes /mcp/* to this server.

Usage:
    python3 project-brain/capabilities/skills/platform-admin/scripts/start_remote_mcp.py
"""


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
import sys
import os
import yaml
from pathlib import Path


def get_project_root() -> Path:
    """Walk up from script to find project root."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "src" / "mcp").exists():
            return parent
    raise RuntimeError("Cannot find project root")


def main():
    root = get_project_root()
    config_path = root / "config" / "remote" / "mcp-remote.yaml"

    if not config_path.exists():
        print(f"Error: {config_path} not found. Run setup first.", file=sys.stderr)
        sys.exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Add src/mcp to path for runtime MCP imports.
    sys.path.insert(0, str(root / "src" / "mcp"))

    # Set AUGUR_ROOT for the MCP server context
    os.environ["AUGUR_ROOT"] = str(root)

    # Store blocked tools list for the tool scoping middleware
    blocked = config.get("blocked_tools", [])
    if blocked:
        os.environ["MCP_BLOCKED_TOOLS"] = ",".join(blocked)

    print(f"Starting remote MCP server on {config['host']}:{config['port']}")
    print(f"Transport: {config['transport']}")
    print(f"Auth: {config.get('auth', {}).get('type', 'none')}")
    print(f"Blocked tools: {', '.join(blocked) if blocked else 'none'}")

    # Import the canonical framework MCP server.
    from src.mcp.augur_framework.__main__ import main as mcp_main

    # Build sys.argv for the MCP server's argparse
    sys.argv = [
        "src.mcp.augur_framework",
        "--transport", config.get("transport", "streamable-http"),
        "--host", config.get("host", "127.0.0.1"),
        "--port", str(config.get("port", 8000)),
    ]

    # Enable auth if configured
    if config.get("auth", {}).get("enabled", True):
        sys.argv.extend(["--auth", config["auth"].get("type", "oauth")])

    # Run the MCP server with parsed arguments
    mcp_main()


if __name__ == "__main__":
    main()
