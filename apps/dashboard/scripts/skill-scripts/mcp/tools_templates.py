"""Factory template listing tools for mcp-app-factory.

Tool: list-factory-templates — returns questionnaire stage templates
and scaffold asset templates used by the Plugin Factory wizard.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from ._helpers import (
    logger,
    tool_annotations,
    PLUGIN_ROOT,
)


# Template directories
QUESTIONNAIRE_TEMPLATES_DIR = PLUGIN_ROOT / "scripts" / "questionnaires" / "templates"
ASSET_TEMPLATES_DIR = PLUGIN_ROOT / "assets" / "templates"


def _load_yaml_safe(path: Path) -> dict:
    """Load a YAML file, returning {} on any failure."""
    try:
        import yaml

        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:
        logger.warning("Failed to load template %s: %s", path.name, exc)
        return {}


def list_factory_templates_impl(name: str | None = None) -> dict:
    """List available factory templates.

    Args:
        name: Optional template name filter (substring match).

    Returns:
        Dict with templates list, count, and grouped categories.
    """
    templates = []
    grouped: dict[str, list[dict]] = {}

    # 1. Questionnaire stage templates (the wizard flow)
    if QUESTIONNAIRE_TEMPLATES_DIR.exists():
        for tpl_file in sorted(QUESTIONNAIRE_TEMPLATES_DIR.glob("*.yaml")):
            data = _load_yaml_safe(tpl_file)
            entry = {
                "name": tpl_file.stem,
                "file": tpl_file.name,
                "category": "questionnaire",
                "stage": data.get("stage"),
                "title": data.get("name", tpl_file.stem),
                "description": data.get("description", ""),
                "question_count": len(data.get("questions", [])),
            }
            if name and name.lower() not in entry["name"].lower():
                continue
            templates.append(entry)
            grouped.setdefault("questionnaire", []).append(entry)

    # 2. Scaffold asset templates (file generation)
    if ASSET_TEMPLATES_DIR.exists():
        for tpl_file in sorted(ASSET_TEMPLATES_DIR.glob("*.template")):
            # Derive category from filename pattern: "mcp-init.py.template" -> "mcp"
            stem = tpl_file.name.removesuffix(".template")
            parts = stem.split("-")
            category = parts[0] if parts else "misc"
            entry = {
                "name": stem,
                "file": tpl_file.name,
                "category": f"scaffold-{category}",
                "stage": None,
                "title": stem.replace("-", " ").replace(".", " ").title(),
                "description": f"Scaffold template for {stem}",
                "question_count": 0,
            }
            if name and name.lower() not in entry["name"].lower():
                continue
            templates.append(entry)
            grouped.setdefault(f"scaffold-{category}", []).append(entry)

        # Include README if present
        readme = ASSET_TEMPLATES_DIR / "README.md"
        if readme.exists() and (not name or "readme" in name.lower()):
            entry = {
                "name": "README",
                "file": "README.md",
                "category": "documentation",
                "stage": None,
                "title": "Template Documentation",
                "description": "README describing all template variables and usage",
                "question_count": 0,
            }
            templates.append(entry)
            grouped.setdefault("documentation", []).append(entry)

    return {
        "templates": templates,
        "count": len(templates),
        "grouped": grouped,
    }


def register_template_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register factory template tools with the MCP server."""

    @mcp.tool(
        name="list-factory-templates",
        annotations=tool_annotations(
            {
                "title": "List Factory Templates",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_factory_templates_tool(name: str | None = None) -> str:
        """List available Plugin Factory templates (questionnaire stages and scaffold files).

        Args:
            name: Optional filter — only return templates whose name contains this substring.

        Returns:
            JSON with templates array, count, and grouped-by-category dict.
        """
        metrics.track_tool("list_factory_templates", skill="mcp-app-factory")
        result = list_factory_templates_impl(name=name)
        return json.dumps(result, indent=2, default=str)

    logger.info("Registered list-factory-templates MCP tool")
