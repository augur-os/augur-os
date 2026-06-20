#!/usr/bin/env python3
"""
Augur Remote Access Setup Script

Validates prerequisites and prepares the system for remote access.
Run this before starting Caddy and the remote MCP server.

Usage:
    python3 project-brain/capabilities/skills/platform-admin/scripts/setup_remote.py [--check-only]
"""

import argparse
import os
import secrets
import shutil
import socket
import subprocess
import sys
from pathlib import Path


def get_project_root() -> Path:
    """Walk up from script to find project root."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "src" / "mcp").exists():
            return parent
    raise RuntimeError("Cannot find project root")


def get_lan_ip() -> str:
    """Detect the LAN IP address."""
    try:
        # Connect to a public DNS to determine local interface IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def check_caddy() -> tuple[bool, str]:
    """Check if Caddy is installed."""
    caddy_path = shutil.which("caddy")
    if caddy_path:
        try:
            result = subprocess.run(
                ["caddy", "version"], capture_output=True, text=True, timeout=5
            )
            version = result.stdout.strip().split()[0] if result.stdout else "unknown"
            return True, f"Caddy {version} at {caddy_path}"
        except Exception:
            return True, f"Caddy at {caddy_path} (version unknown)"
    return False, "Not found. Install: brew install caddy"


def check_users_yaml(root: Path) -> tuple[bool, str]:
    """Check if users.yaml exists and has content."""
    users_path = root / "config" / "remote" / "users.yaml"
    example_path = root / "config" / "remote" / "users.yaml.example"

    if users_path.exists():
        content = users_path.read_text()
        if "REPLACE_WITH_REAL_HASH" in content:
            return False, "Exists but contains placeholder hashes — edit with real bcrypt hashes"
        return True, str(users_path)

    if example_path.exists():
        return False, f"Missing. Copy template: cp {example_path} {users_path}"
    return False, "Missing. No template found either."


def ensure_jwt_secret(root: Path) -> tuple[bool, str]:
    """Check or create JWT secret."""
    secret_path = root / "config" / "remote" / ".jwt-secret"

    if secret_path.exists():
        content = secret_path.read_text().strip()
        if len(content) >= 32:
            return True, f"Exists ({len(content)} chars)"
        return False, "Exists but too short (need >= 32 chars)"

    # Auto-generate
    secret = secrets.token_hex(32)
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    secret_path.write_text(secret)
    os.chmod(secret_path, 0o600)
    return True, f"Auto-generated at {secret_path}"


def check_caddyfile(root: Path) -> tuple[bool, str]:
    """Check if Caddyfile exists."""
    caddyfile = root / "config" / "remote" / "Caddyfile"
    if caddyfile.exists():
        return True, str(caddyfile)
    return False, "Missing. Expected at config/remote/Caddyfile"


def check_mcp_config(root: Path) -> tuple[bool, str]:
    """Check if MCP remote config exists."""
    mcp_config = root / "config" / "remote" / "mcp-remote.yaml"
    if mcp_config.exists():
        return True, str(mcp_config)
    return False, "Missing. Expected at config/remote/mcp-remote.yaml"


def main():
    parser = argparse.ArgumentParser(description="Augur Remote Access Setup")
    parser.add_argument("--check-only", action="store_true", help="Only check prerequisites, don't generate anything")
    args = parser.parse_args()

    root = get_project_root()
    lan_ip = get_lan_ip()

    print(f"\n{'=' * 60}")
    print("  Augur Remote Access Setup")
    print(f"  Project root: {root}")
    print(f"  Detected LAN IP: {lan_ip}")
    print(f"{'=' * 60}\n")

    checks = [
        ("Caddy", check_caddy()),
        ("User Store", check_users_yaml(root)),
        ("JWT Secret", (True, "Skipped (check-only)") if args.check_only else ensure_jwt_secret(root)),
        ("Caddyfile", check_caddyfile(root)),
        ("MCP Config", check_mcp_config(root)),
    ]

    all_ok = True
    for name, (ok, detail) in checks:
        status = "\u2705" if ok else "\u274C"
        print(f"  {status} {name}: {detail}")
        if not ok:
            all_ok = False

    print()

    if all_ok:
        print("All prerequisites met! Start services:\n")
        print("  # Terminal 1: Start Caddy")
        print(f"  AUGUR_HOST={lan_ip} caddy run --config config/remote/Caddyfile\n")
        print("  # Terminal 2: Start remote MCP server")
        print("  python3 project-brain/capabilities/skills/platform-admin/scripts/start_remote_mcp.py\n")
        print("  # Terminal 3: Start dashboard (if not already running)")
        print("  cd apps/dashboard && npm run dev\n")
        print(f"  Dashboard: https://{lan_ip}/")
        print(f"  MCP endpoint: https://{lan_ip}/mcp/\n")
        print("  Generate client configs:")
        print(f"  python3 project-brain/capabilities/skills/platform-admin/scripts/generate_client_config.py --host {lan_ip}\n")
    else:
        print("Some prerequisites are missing. Fix the issues above and re-run.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
