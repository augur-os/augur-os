#!/usr/bin/env python3
"""
Generate MCP configuration for a git worktree.

Reads the worktree MCP template and substitutes placeholders with actual values.
Optionally registers the worktree in the registry for port allocation.
Supports multiple IDE clients (Claude, Cursor, Windsurf, Gemini, OpenCode).

Usage:
    # Register worktree and generate config for all IDEs
    python scripts/generate-worktree-mcp.py --path ../augur-adr-101 --name adr-101 --all

    # Generate for specific IDE
    python scripts/generate-worktree-mcp.py --path ../augur-adr-101 --name adr-101 --client cursor

    # Just generate with default port (no registration)
    python scripts/generate-worktree-mcp.py --path ../augur-adr-101 --client claude
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = PROJECT_ROOT / "src" / "config" / "mcp_worktree.template.json"

DEFAULT_DASHBOARD_PORT = 3001
DEFAULT_MCP_PORT = 8081

CLIENT_CONFIG_PATHS = {
    "claude": ".claude/mcp.json",
    "cursor": ".cursor/mcp.json",
    "windsurf": ".windsurf/mcp.json",
    "gemini": ".gemini/settings.json",
    "opencode": ".opencode/mcp.json",
    "antigravity": ".antigravity/mcp_config.json",
    "agent": ".agent/mcp.json",
    # Repo-root project config; Copilot loads it via gca's
    # --additional-mcp-config injection (no per-client config dir).
    "copilot": ".mcp.json",
}


def load_template() -> str:
    if not TEMPLATE_PATH.exists():
        raise SystemExit(f"Template not found: {TEMPLATE_PATH}")
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def substitute_placeholders(template: str, worktree_path: str, mcp_port: int) -> str:
    # JSON templates need slash-normalized paths on Windows; raw backslashes
    # turn sequences like "\U" into invalid JSON escapes before parsing.
    worktree_abs = Path(worktree_path).resolve().as_posix()
    result = template.replace("$WORKTREE_PATH", worktree_abs)
    result = result.replace("$MCP_PORT", str(mcp_port))
    return result


def get_ports_from_registry(path: str, name: str) -> tuple[int, int]:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from worktree_registry import cmd_register

    result = cmd_register(path, name)
    if result.get("worktree"):
        # Already registered - use existing allocation
        return result["worktree"]["dashboard_port"], result["worktree"]["mcp_port"]
    if not result.get("success"):
        error = result.get("error", "Unknown error")
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)

    return result["dashboard_port"], result["mcp_port"]


def get_client_path(client: str, worktree_path: str) -> Path:
    if client not in CLIENT_CONFIG_PATHS:
        raise ValueError(
            f"Unknown client: {client}. Supported: {list(CLIENT_CONFIG_PATHS.keys())}"
        )

    config_rel = CLIENT_CONFIG_PATHS[client]
    return Path(worktree_path).resolve() / config_rel


def write_config_for_client(client: str, worktree_path: str, config: dict) -> Path:
    target_path = get_client_path(client, worktree_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if client == "gemini":
        existing = {}
        if target_path.exists():
            try:
                existing = json.loads(target_path.read_text())
            except json.JSONDecodeError:
                pass
        existing["mcpServers"] = config.get("mcpServers", {})
        target_path.write_text(json.dumps(existing, indent=2))
    else:
        target_path.write_text(json.dumps(config, indent=2))

    return target_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate MCP configuration for a git worktree.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # Register worktree and generate config for all IDEs
  python scripts/generate-worktree-mcp.py --path ../augur-adr-101 --name adr-101 --all

  # Generate for specific IDE
  python scripts/generate-worktree-mcp.py --path ../augur-adr-101 --name adr-101 --client cursor

  # Generate for multiple IDEs
  python scripts/generate-worktree-mcp.py --path ../augur-adr-101 --client claude --client cursor

Supported clients: {", ".join(CLIENT_CONFIG_PATHS.keys())}
        """,
    )

    parser.add_argument(
        "--path",
        required=True,
        help="Path to the worktree directory",
    )
    parser.add_argument(
        "--name",
        help="Worktree name for registry (triggers registration and port allocation)",
    )
    parser.add_argument(
        "--client",
        action="append",
        choices=list(CLIENT_CONFIG_PATHS.keys()),
        help="IDE client to generate config for (can specify multiple)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate config for all supported IDEs",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Output to stdout instead of writing files",
    )
    parser.add_argument(
        "--dashboard-port",
        type=int,
        default=DEFAULT_DASHBOARD_PORT,
        help=f"Dashboard port when not using registry (default: {DEFAULT_DASHBOARD_PORT})",
    )
    parser.add_argument(
        "--mcp-port",
        type=int,
        default=DEFAULT_MCP_PORT,
        help=f"MCP port when not using registry (default: {DEFAULT_MCP_PORT})",
    )

    args = parser.parse_args()

    if args.name:
        _, mcp_port = get_ports_from_registry(args.path, args.name)
    else:
        mcp_port = args.mcp_port

    template = load_template()
    config_str = substitute_placeholders(template, args.path, mcp_port)

    try:
        config = json.loads(config_str)
    except json.JSONDecodeError as e:
        print(f"Error: Generated config is not valid JSON: {e}", file=sys.stderr)
        raise SystemExit(1)

    if args.stdout:
        print(json.dumps(config, indent=2))
        return 0

    clients = args.client or []
    if args.all:
        clients = list(CLIENT_CONFIG_PATHS.keys())

    if not clients:
        print("Error: Specify --client, --all, or --stdout", file=sys.stderr)
        raise SystemExit(1)

    written = []
    for client in clients:
        target = write_config_for_client(client, args.path, config)
        written.append(target)
        print(f"Generated {target.relative_to(Path(args.path).resolve())}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
