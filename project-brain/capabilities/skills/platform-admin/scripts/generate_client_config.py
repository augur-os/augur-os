#!/usr/bin/env python3
"""
Generate MCP client configuration files for remote users.

Creates ready-to-import config files for:
- Claude Desktop (Windows/macOS)
- Antigravity (Gemini IDE agent)

Usage:
    python3 generate_client_config.py --host 192.168.1.100 [--output-dir ./configs]
"""

import argparse
import json
from pathlib import Path


def generate_claude_desktop_config(host: str, port: int = 443) -> dict:
    """Generate Claude Desktop MCP server configuration."""
    return {
        "mcpServers": {
            "augur": {
                "url": f"https://{host}/mcp/",
                "transport": "streamable-http",
                "note": "Augur MCP server — remote access via Caddy TLS proxy"
            }
        }
    }


def generate_antigravity_config(host: str, port: int = 443) -> dict:
    """Generate Antigravity MCP server configuration."""
    return {
        "mcp_servers": [
            {
                "name": "augur",
                "url": f"https://{host}/mcp/",
                "transport": "streamable-http",
                "description": "Augur personal knowledge system"
            }
        ]
    }


def main():
    parser = argparse.ArgumentParser(description="Generate MCP client configs for remote access")
    parser.add_argument("--host", required=True, help="Augur server hostname or IP (e.g., 192.168.1.100)")
    parser.add_argument("--port", type=int, default=443, help="HTTPS port (default: 443)")
    parser.add_argument("--output-dir", default=".", help="Output directory for config files")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Claude Desktop config
    claude_config = generate_claude_desktop_config(args.host, args.port)
    claude_path = output_dir / "claude_desktop_config.json"
    with open(claude_path, "w") as f:
        json.dump(claude_config, f, indent=2)
    print(f"Claude Desktop config: {claude_path}")

    # Antigravity config
    anti_config = generate_antigravity_config(args.host, args.port)
    anti_path = output_dir / "antigravity_config.json"
    with open(anti_path, "w") as f:
        json.dump(anti_config, f, indent=2)
    print(f"Antigravity config:    {anti_path}")

    # Setup instructions
    readme_path = output_dir / "SETUP.md"
    with open(readme_path, "w") as f:
        f.write(f"""# Remote MCP Client Setup

## Server: {args.host}

### Claude Desktop (Windows)

1. Open Claude Desktop Settings > Developer > MCP Servers
2. Click "Edit Config" to open the config file
3. Merge the contents of `claude_desktop_config.json` into your config
4. Restart Claude Desktop

### Antigravity

1. Open Antigravity settings
2. Add the MCP server from `antigravity_config.json`
3. Restart Antigravity

### TLS Trust (Required)

The Augur server uses Caddy's internal CA for TLS. You must trust it:

1. Get the CA certificate from the server admin
2. On Windows: Double-click the .crt file > Install Certificate > Local Machine > Trusted Root Certification Authorities
3. Verify: Open `https://{args.host}/api/health` in a browser — should show no certificate warnings

### Verify Connection

After setup, verify MCP connectivity:
- Claude Desktop: Check the MCP icon in the input bar — "augur" should appear as connected
- Test a tool: Ask Claude to "list available Augur tools"
""")
    print(f"Setup instructions:    {readme_path}")
    print(f"\nDone! Share the '{output_dir}' directory with the remote user.")


if __name__ == "__main__":
    main()
