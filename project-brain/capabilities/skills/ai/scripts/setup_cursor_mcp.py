#!/usr/bin/env python3
"""Thin wrapper for configuring Cursor MCP via the shared configure_mcp script."""

from __future__ import annotations

import argparse
import subprocess
from typing import Sequence

from bootstrap_paths import ensure_project_paths  # noqa: E402

ensure_project_paths(__file__)

from src.config.paths import get_project_root, get_python_executable


def setup_cursor_mcp() -> int:
    """Configure Cursor MCP through the shared native MCP wiring entrypoint."""
    project_root = get_project_root()
    configure_script = project_root / "scripts" / "configure_mcp.py"
    result = subprocess.run(  # nosec B603
        [str(get_python_executable()), str(configure_script), "--client", "cursor", "--auto"],
        check=False,
    )
    return result.returncode


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Configure Cursor MCP through the shared Augur MCP wiring.",
    )
    parser.parse_args(argv)
    return setup_cursor_mcp()


if __name__ == "__main__":
    raise SystemExit(main())
