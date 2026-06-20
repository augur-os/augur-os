#!/usr/bin/env python3
"""
augur init — Create a new Augur project from the augur-os template.

Usage:
    python augur_init.py <project-name> [--port PORT] [--repo URL]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


DEFAULT_REPO = "https://github.com/augur-os/augur-os"
DEFAULT_PORT = 3000


def write_project_yaml(target: Path, name: str, port: int) -> None:
    """Write project.yaml with name and port."""
    (target / "project.yaml").write_text(
        yaml.dump({"name": name, "port": port}, default_flow_style=False)
    )


def create_external_dirs(name: str, home: Path | None = None) -> list[Path]:
    """Create all scoped external directories for a project."""
    home = home or Path.home()
    dirs = [
        home / "Vault" / name,
        home / "Vault" / name / "skills",
        home / "Vault" / name / "drafts" / "staging",
        home / "Documents" / name,
        home / "Library" / "Application Support" / name / "state",
        home / "Library" / "Application Support" / name / "rag",
        home / "Library" / "Logs" / name,
        home / "Library" / "Caches" / name,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def write_mcp_config(target: Path, name: str) -> None:
    """Generate .claude/mcp.json with project-specific MCP config."""
    claude_dir = target / ".claude"
    claude_dir.mkdir(exist_ok=True)
    mcp_config = {
        "mcpServers": {
            name: {
                "command": str(target / ".venv" / "bin" / "python3"),
                "args": ["-m", "src.mcp.server"],
                "env": {
                    "AUGUR_ROOT": str(target),
                    "PYTHONPATH": str(target),
                },
            }
        }
    }
    (claude_dir / "mcp.json").write_text(json.dumps(mcp_config, indent=2))


def init_project(
    name: str,
    target_dir: Path | None = None,
    port: int = DEFAULT_PORT,
    repo: str = DEFAULT_REPO,
) -> Path:
    """Create a new Augur project.

    1. Clone augur-os repo
    2. Write project.yaml with name and port
    3. Create scoped external dirs
    4. Generate MCP config
    """
    target = target_dir or Path.cwd() / name

    # 1. Clone
    if not target.exists():
        subprocess.run(
            ["git", "clone", repo, str(target)],
            check=True,
        )

    # 2. Write project.yaml
    write_project_yaml(target, name, port)

    # 3. Create scoped external dirs
    create_external_dirs(name)

    # 4. Generate MCP config
    write_mcp_config(target, name)

    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new Augur project")
    parser.add_argument("name", help="Project name")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Dashboard port (default: 3000)")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="Template repo URL")
    args = parser.parse_args()

    target = init_project(args.name, port=args.port, repo=args.repo)
    print(f"Project '{args.name}' created at {target}")
    print(f"Next: cd {target} && python project-brain/capabilities/skills/onboard/scripts/onboard.py")


if __name__ == "__main__":
    main()
