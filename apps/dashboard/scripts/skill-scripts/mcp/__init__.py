"""Dashboard skill MCP Tool Implementations.

Merged from mcp-app-factory, frontend, and page-builder skills.

Tool groups:
- tools_plugin: Plugin scaffold/create/manage tools (from mcp-app-factory)
- tools_ide: IDE integration tools (from mcp-app-factory)
- tools_migrate: Migration/upgrade tools (from mcp-app-factory)
- tools_workflow: Workflow/generation tools (from mcp-app-factory)
- tools_templates: Template listing tools (from mcp-app-factory)
- tools_page_builder: Page builder list/delete tools (from page-builder)
- Frontend verify tools: verify-action-wiring (from frontend)

This module is loaded dynamically by the Augur MCP server
via the plugin tool loading system.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from ._helpers import logger
from .tools_plugin import register_plugin_tools
from .tools_ide import register_ide_tools
from .tools_migrate import register_migrate_tools
from .tools_workflow import register_workflow_tools
from .tools_templates import register_template_tools
from .tools_page_builder import register_tools as register_page_builder_tools

# Re-export impl functions for direct usage and discovery
from .tools_plugin import (
    create_plugin_impl,
    export_skill_impl,
    import_skill_impl,
    scan_importable_plugins_impl,
    audit_plugin_impl,
)
from .tools_ide import (
    skill_generate_impl,
    command_execute_impl,
    backlog_list_impl,
    backlog_read_impl,
    skill_analyze_impl,
)
from .tools_workflow import (
    workflow_start_impl,
    workflow_status_impl,
    workflow_resume_impl,
    workflow_answer_impl,
    workflow_advance_impl,
    workflow_abort_impl,
    workflow_list_impl,
)
from .tools_templates import list_factory_templates_impl

try:
    from src.mcp.augur_shared.annotations import tool_annotations
    from src.mcp.augur_shared.config import get_project_root
    from src.mcp.augur_shared.logging import get_entity_logger as _get_entity_logger
    _frontend_logger = _get_entity_logger("mcp.dashboard.frontend")
except ImportError:
    _frontend_logger = logger


def _run_python_script(relative_script: str, args: list[str] | None = None, timeout: int = 180) -> dict[str, Any]:
    try:
        from src.mcp.augur_shared.config import get_project_root as _get_root
        project_root = _get_root()
    except ImportError:
        from src.config.paths import get_project_root as _get_root
        project_root = _get_root()

    script_path = project_root / relative_script
    if not script_path.exists():
        return {
            "success": False,
            "error": f"Script not found: {relative_script}",
            "script": relative_script,
        }

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{project_root}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(project_root)
    )

    cmd = [sys.executable, str(script_path), *(args or [])]
    try:
        result = subprocess.run(  # nosec B603
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Timed out after {timeout}s",
            "script": relative_script,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "success": False,
            "error": str(exc),
            "script": relative_script,
        }

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    parsed: Any = None
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = stdout

    payload: dict[str, Any] = {
        "success": result.returncode == 0,
        "returncode": result.returncode,
        "script": relative_script,
        "result": parsed if parsed is not None else stdout,
    }
    if stderr:
        payload["stderr"] = stderr
    return payload


async def _run_python_script_async(relative_script: str, args: list[str] | None = None, timeout: int = 180) -> dict[str, Any]:
    return await asyncio.to_thread(_run_python_script, relative_script, args, timeout)


def _register_frontend_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register frontend verify tools (merged from frontend skill)."""
    _frontend_logger.info("Registering frontend verify MCP tools")

    try:
        _tool_annotations = tool_annotations
    except NameError:
        def _tool_annotations(a: dict) -> dict:
            return a

    @mcp.tool(
        name="verify-action-wiring",
        annotations=_tool_annotations(
            {
                "title": "Verify Action Wiring",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def verify_action_wiring_tool() -> str:
        """Verify that action YAML definitions are correctly wired to their endpoints."""
        metrics.track_tool("verify_action_wiring", skill="dashboard")
        result = await _run_python_script_async("apps/dashboard/scripts/skill-scripts/verify_action_wiring.py")
        return json.dumps(result, indent=2, default=str)


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register all Dashboard skill tools with the MCP server."""
    logger.info("Registering dashboard MCP tools (merged: mcp-app-factory, frontend, page-builder)...")

    # mcp-app-factory tools
    register_plugin_tools(mcp, mcp_tool_interceptor, metrics)
    register_ide_tools(mcp, mcp_tool_interceptor, metrics)
    register_migrate_tools(mcp, mcp_tool_interceptor, metrics)
    register_workflow_tools(mcp, mcp_tool_interceptor, metrics)
    register_template_tools(mcp, mcp_tool_interceptor, metrics)

    # page-builder tools
    register_page_builder_tools(mcp, mcp_tool_interceptor, metrics)

    # frontend verify tools
    _register_frontend_tools(mcp, mcp_tool_interceptor, metrics)

    logger.info("Dashboard MCP tools registered successfully")


__all__ = [
    "register_tools",
    # Plugin tools
    "create_plugin_impl",
    "export_skill_impl",
    "import_skill_impl",
    "scan_importable_plugins_impl",
    "audit_plugin_impl",
    # IDE tools
    "skill_generate_impl",
    "command_execute_impl",
    "backlog_list_impl",
    "backlog_read_impl",
    "skill_analyze_impl",
    # Workflow tools
    "workflow_start_impl",
    "workflow_status_impl",
    "workflow_resume_impl",
    "workflow_answer_impl",
    "workflow_advance_impl",
    "workflow_abort_impl",
    "workflow_list_impl",
    # Template tools
    "list_factory_templates_impl",
]
