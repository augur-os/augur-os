#!/usr/bin/env python3
"""One-shot generator for orphan dashboard-caller policy entries.

Discovers @mcp.tool definitions in the codebase, extracts their docstrings,
and prints YAML policy entries for the 20 orphan dashboard callers that
need a proper classification per the surface decision matrix.

Output is printed to stdout — manually splice into
config/system/capability_exposure.yaml alphabetically.

Usage:
    PYTHONPATH=project-brain/capabilities:$PYTHONPATH .venv/bin/python \\
        scripts/_audit_seed_orphan_policies.py
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ORPHANS = [
    "activate-template",
    "execute-fast-action",
    "file-delete",
    "file-move",
    "file-write",
    "get-ide-status",
    "list-available-clients",
    "open-client-runtime-folder",
    "open-file",
    "refresh-brain-harness-snapshot",
    "reindex-browse-category",
    "resolve-client",
    "run-oneshot-cli",
    "set-client-override",
    "set-config",
    "skill-action",
    "sync-bugs",
    "system-open",
    "system-open-file",
    "update-chat-session",
]


def _find_docstring(name: str) -> str:
    """Find the docstring of the @mcp.tool decorated function with this name."""
    # Look across the codebase for @mcp.tool(name="...") definitions.
    for path in Path("src").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if name not in text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                # @mcp.tool(name="...") or @<x>.tool(name="...")
                if isinstance(dec, ast.Call):
                    for kw in dec.keywords:
                        if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                            if kw.value.value == name:
                                ds = ast.get_docstring(node)
                                if ds:
                                    # First sentence; trim if very long
                                    first = ds.splitlines()[0].strip()
                                    return first[:200]
                                return ""
    return ""


def _yaml_entry(name: str, description: str) -> str:
    # Reasonable defaults — owner_kind augur, dashboard-driven, mcp via dashboard
    safe_desc = description or f"Dashboard atomic op: {name}"
    safe_desc = safe_desc.replace('"', "'")
    return f"""  mcp-tool:{name}:
    classification_status: approved
    description: "{safe_desc}"
    export_to:
    - cli
    - agents-md
    - browse
    management: generated
    owner_kind: augur
    preferred_client: dashboard
    primary_surface: mcp via dashboard
    scope: project"""


def main() -> None:
    for name in ORPHANS:
        ds = _find_docstring(name)
        print(_yaml_entry(name, ds))


if __name__ == "__main__":
    main()
