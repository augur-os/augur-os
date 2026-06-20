"""
_cli_mcp — Pure formatting and schema helpers for the Augur CLI.

Contains only stateless helper functions with no module-level globals.
MCP infrastructure globals (_TOOLS_REGISTERED, _CLI_MCPS) and the functions
that reference them stay in src/cli.py so tests can monkeypatch them there.

Split from src/cli.py (WS5, behavior-preserving — no importer changes).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List


def format_tool_list(tools: Dict[str, Dict[str, Any]]) -> str:
    """Format tool list for display."""
    lines = ["Available MCP Tools:", "=" * 50]

    # Hub-aware grouping — prefix match first, then verb-based fallback
    _hub_prefixes = (
        ("apple-", "Apple"),
        ("google-", "Google"),
        ("home-", "Home"),
        ("finance-", "Finance"),
        ("career-", "Career"),
        ("channels-", "Channels"),
        ("knowledge-", "Knowledge"),
        ("memory-", "Memory"),
        ("note-", "Notes"),
        ("rag-", "RAG"),
        ("workflow-", "Workflow"),
        ("updater-", "Updater"),
        ("training-", "Training"),
        ("publish-", "Publishing"),
        ("daemon-", "Daemon"),
    )

    categories: Dict[str, List[str]] = {}
    for name in sorted(tools.keys()):
        category = None

        # 1. Check hub prefix matches
        for prefix, cat in _hub_prefixes:
            if name.startswith(prefix):
                category = cat
                break

        # 2. Verb-based grouping for remaining tools
        if category is None:
            if name.startswith(("get-", "list-")):
                category = "Query"
            elif name.startswith(("run-", "execute-")):
                category = "Execution"
            elif name.startswith(("update-", "save-", "delete-")):
                category = "Mutation"
            elif name.startswith(("skill-", "plugin-", "install-", "export-", "import-")):
                category = "Skills & Plugins"
            elif name.startswith(("mcp-", "switch-", "preload-")):
                category = "MCP"
            elif name.startswith(("ide-", "configure-")):
                category = "IDE & Agents"
            elif name.startswith("file-"):
                category = "Files"
            elif any(
                name.startswith(p)
                for p in (
                    "doctor-",
                    "symptom-",
                    "medication-",
                    "add-symptom",
                    "add-medication",
                )
            ):
                category = "Health"
            elif any(
                name.startswith(p)
                for p in (
                    "linkedin-",
                    "smb-",
                    "content-",
                    "create-linkedin",
                    "create-smb",
                )
            ):
                category = "Content"
            else:
                category = "System"

        categories.setdefault(category, []).append(name)

    for category in sorted(categories.keys()):
        lines.append(f"\n{category}:")
        for name in categories[category]:
            desc = tools[name].get("description", "")
            if desc and desc != "No description":
                full_first_line = desc.split("\n", 1)[0]
                truncated = full_first_line[:60]
                if len(truncated) < len(full_first_line):
                    truncated += "..."
                lines.append(f"  {name:<35} {truncated}")
            else:
                lines.append(f"  {name:<35} (no description)")

    lines.append(f"\nTotal: {len(tools)} tools")
    return "\n".join(lines)


def format_tool_list_json(tools: Dict[str, Dict[str, Any]]) -> str:
    """Format tool list as JSON."""
    return json.dumps(
        {"tools": list(tools.values()), "total": len(tools)},
        indent=2,
        ensure_ascii=False,
    )


def _print_manifest_markdown(manifest: dict[str, Any]) -> None:
    """Print the discovery manifest in a compact human-readable format."""
    manifest_meta = manifest.get("manifest") if isinstance(manifest, dict) else {}
    focus = manifest.get("focus") if isinstance(manifest, dict) else {}
    tools = manifest.get("recommended_tools") if isinstance(manifest, dict) else []

    name = manifest_meta.get("name", "augur") if isinstance(manifest_meta, dict) else "augur"
    print(f"# {name} capability manifest")
    if isinstance(focus, dict):
        hub = focus.get("hub") or "none"
        skill = focus.get("skill") or "none"
        print(f"\nFocus: hub={hub} skill={skill}")
    if isinstance(tools, list) and tools:
        print("\nRecommended tools:")
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            print(f"- {tool.get('name', '')}: {tool.get('skill', '')}")


def _schema_ref_target(schema: dict[str, Any], ref: str) -> dict[str, Any] | None:
    """Resolve a local JSON-schema ``#/$defs/...`` reference."""
    prefix = "#/$defs/"
    if not isinstance(ref, str) or not ref.startswith(prefix):
        return None
    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        return None
    target = defs.get(ref[len(prefix) :])
    return target if isinstance(target, dict) else None


def _wrapped_params_payload_schema(
    schema: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Return the inner payload schema for FastMCP tools shaped as ``params``."""
    if not isinstance(schema, dict):
        return None
    properties = schema.get("properties")
    if not isinstance(properties, dict) or set(properties) != {"params"}:
        return None
    params_schema = properties.get("params")
    if not isinstance(params_schema, dict):
        return None
    ref_target = _schema_ref_target(schema, str(params_schema.get("$ref") or ""))
    if ref_target is not None:
        return ref_target
    return params_schema


def _schema_uses_wrapped_params(schema: dict[str, Any] | None) -> bool:
    """Return whether a tool schema expects a single ``params`` argument."""
    return _wrapped_params_payload_schema(schema) is not None


def _pack_tool_params_for_schema(
    params: dict[str, Any],
    schema: dict[str, Any] | None,
) -> dict[str, Any]:
    """Pack CLI flags according to the target MCP tool's input schema."""
    if schema is None or _schema_uses_wrapped_params(schema):
        return {"params": params} if params else {"params": {}}
    return params


def parse_param_value(value: str) -> Any:
    """Parse a parameter value, attempting JSON parsing for complex types."""
    # Try JSON first for objects/arrays
    if value.startswith("{") or value.startswith("["):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass

    # Boolean handling
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False

    # Number handling
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        pass

    # String
    return value


def _render_tool_help(tool_name: str, tool_info: dict) -> str:
    """Render schema-driven help for an MCP tool from its inputSchema."""
    desc = tool_info.get("description") or "(no description)"
    lines = [f"{tool_name} — {desc.split(chr(10), 1)[0]}", ""]

    schema = tool_info.get("inputSchema")
    payload_schema = _wrapped_params_payload_schema(schema)
    help_schema = payload_schema or schema
    props = help_schema.get("properties", {}) if help_schema else {}

    if not props:
        lines.append("This tool takes no parameters.")
        return "\n".join(lines)

    required = set(help_schema.get("required", []))
    lines.append("Parameters:")

    for param_name, prop in props.items():
        flag = f"--{param_name.replace('_', '-')}"
        resolved_prop = prop
        if isinstance(prop, dict):
            ref_target = _schema_ref_target(help_schema, str(prop.get("$ref") or ""))
            if ref_target is not None:
                resolved_prop = {**ref_target, **prop}
        ptype = (resolved_prop.get("type") or "string").upper()
        pdesc = prop.get("description") or "(no description)"
        req = " (required)" if param_name in required else ""
        lines.append(f"  {flag} {ptype}    {pdesc}{req}")

    return "\n".join(lines)
