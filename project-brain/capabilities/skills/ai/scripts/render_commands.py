#!/usr/bin/env python3
"""Render grouped slash command reference from the ai skill."""

from __future__ import annotations

import argparse
import json
import sys

from skills.ai.scripts.mcp import _render_commands_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Render slash command reference")
    parser.add_argument("--json", action="store_true", help="Output JSON (default)")
    parser.parse_args()

    json.dump(_render_commands_payload(), sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
