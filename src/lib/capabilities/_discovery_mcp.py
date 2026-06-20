"""
capabilities._discovery_mcp — Pure MCP-tool AST helpers for capability discovery.

Only contains stateless helpers that don't call src.config.paths functions.
discover_declared_skill_capabilities and discover_script_mcp_tool_capabilities
stay in discovery.py so tests can monkeypatch discovery.get_managed_skill_source_dirs
and discovery.get_configured_vault_skills_dir.

Internal use by the capabilities package; do not import directly from outside.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from ._discovery_helpers import _policy_list, capability_id


def _declared_mcp_tool_exposure(tool_name: str, policy: dict[str, Any]) -> tuple[str, ...]:
    """Return effective generated exposure for a declared MCP tool."""
    exposure = ("mcp", "browse")
    entries = policy.get("capabilities") if isinstance(policy, dict) else {}
    if not isinstance(entries, dict):
        return exposure

    entry = entries.get(capability_id("mcp-tool", tool_name))
    if not isinstance(entry, dict):
        return exposure

    status = str(entry.get("classification_status") or "").strip()
    if status not in {"approved", "blocked", "deprecated"}:
        return exposure

    export_to = set(_policy_list(entry.get("export_to")))
    exposure_items = list(exposure)
    if "mcp" not in export_to:
        exposure_items = [item for item in exposure_items if item != "mcp"]
    if status in {"approved", "deprecated"}:
        for item in reversed(("cli", "agents-md")):
            if item in export_to:
                exposure_items.insert(0, item)
    return tuple(dict.fromkeys(exposure_items))


def _extract_mcp_tool_decorator_name(decorator: ast.expr) -> str:
    if not isinstance(decorator, ast.Call):
        return ""
    func = decorator.func
    if not isinstance(func, ast.Attribute) or func.attr != "tool":
        return ""
    if decorator.args:
        first_arg = decorator.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            return first_arg.value.strip()
    for keyword in decorator.keywords:
        if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
            value = keyword.value.value
            if isinstance(value, str):
                return value.strip()
    return ""


def _script_mcp_tool_names(py_file: Path) -> tuple[str, ...]:
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return ()

    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            tool_name = _extract_mcp_tool_decorator_name(decorator)
            if tool_name:
                names.append(tool_name)
    return tuple(dict.fromkeys(names))
