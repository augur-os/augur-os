#!/usr/bin/env python3
"""Onboard state tracking for Augur installations.

Manages ~/Library/Application Support/Augur/state/onboard-complete.json.
Importable as a library or callable as CLI.

Usage:
    python -m src.scripts.onboard_state read
    python -m src.scripts.onboard_state write --source claude-code --clients claude-code
    python -m src.scripts.onboard_state add-client cursor
    python -m src.scripts.onboard_state mark-vault-scaffolded
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE_FILENAME = "onboard-complete.json"


def _state_path() -> Path:
    """Resolve the state file path."""
    try:
        from src.config.paths import get_state_dir

        return get_state_dir() / STATE_FILENAME
    except Exception:
        # Fallback for environments without full Augur config
        state_dir = Path.home() / "Library" / "Application Support" / "Augur" / "state"
        return state_dir / STATE_FILENAME


def read_state() -> dict | None:
    """Read the current onboard state. Returns None if no state file exists."""
    path = _state_path()
    if not path.exists():
        return None
    return json.loads(path.read_text())


def write_state(
    install_source: str = "claude-code",
    configured_clients: list[str] | None = None,
) -> dict:
    """Write initial onboard state."""
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "install_source": install_source,
        "configured_clients": configured_clients or [install_source],
        "vault_scaffolded": False,
        "dashboard_started": False,
    }
    path.write_text(json.dumps(state, indent=2) + "\n")
    return state


def add_configured_client(client: str) -> dict:
    """Add a client to the configured_clients list (no duplicates)."""
    state = read_state()
    if state is None:
        return write_state(configured_clients=[client])
    if client not in state.get("configured_clients", []):
        state.setdefault("configured_clients", []).append(client)
    path = _state_path()
    path.write_text(json.dumps(state, indent=2) + "\n")
    return state


def mark_vault_scaffolded() -> dict:
    """Mark the vault as scaffolded."""
    state = read_state()
    if state is None:
        state = write_state()
    state["vault_scaffolded"] = True
    path = _state_path()
    path.write_text(json.dumps(state, indent=2) + "\n")
    return state


def main():
    parser = argparse.ArgumentParser(description="Augur onboard state management")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("read", help="Read current state")

    write_p = sub.add_parser("write", help="Write initial state")
    write_p.add_argument("--source", default="claude-code", help="Install source platform")
    write_p.add_argument("--clients", default="", help="Comma-separated client list")

    add_p = sub.add_parser("add-client", help="Add a configured client")
    add_p.add_argument("client", help="Client name to add")

    sub.add_parser("mark-vault-scaffolded", help="Mark vault as scaffolded")

    args = parser.parse_args()

    if args.command == "read":
        state = read_state()
        if state is None:
            print("No onboard state found. Run /onboard first.")
            sys.exit(1)
        print(json.dumps(state, indent=2))

    elif args.command == "write":
        clients = [c.strip() for c in args.clients.split(",") if c.strip()] or None
        state = write_state(install_source=args.source, configured_clients=clients)
        print(json.dumps(state, indent=2))

    elif args.command == "add-client":
        state = add_configured_client(args.client)
        print(json.dumps(state, indent=2))

    elif args.command == "mark-vault-scaffolded":
        state = mark_vault_scaffolded()
        print(json.dumps(state, indent=2))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
