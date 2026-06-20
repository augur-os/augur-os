"""Wire the augur-framework operational tools into a FastMCP instance.

Tool definitions live in canonical packages under src/mcp/augur_framework
and src/mcp/augur_shared. The actual tool functions are imported and
re-registered.

Tools registered (~114 per Track 3a design spec):
- domain (cowork, ide, plugins, hubs/widgets — registered via
  register_domain_tools)
- infrastructure (file ops, jobs, MCP management, paths, performance,
  settings, system, workflow, actions, templates, harness, etc. —
  registered via register_infrastructure_tools)

Note: register_domain_tools also pulls in `register_dynamic_plugin_tools`
(skill plugins via scripts/mcp/__init__.py), the same code path the
canonical framework server uses today.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]


def _env_flag_enabled(name: str) -> bool:
    value = os.environ.get(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _register_dashboard_core_tools(
    mcp: FastMCP,
    interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register core tools needed by dashboard-wide MCP calls.

    The normal augur-framework server stays framework-only. The Next.js
    dashboard uses a single stdio bridge, so it explicitly opts into these
    foundation tools instead of spawning a second bridge per request.
    """
    from src.mcp.augur_shared.compat import list_skills as registry_list_skills
    from src.mcp.augur_shared.compat import resolve_skill
    from src.mcp.augur_shared.config import get_config as get_mcp_config
    from src.mcp.augur_shared.interfaces import SkillRecord
    from src.mcp.augur_shared.server_cache import SkillCache

    config = get_mcp_config()
    skills_dir = config.plugins_dir
    skill_cache = SkillCache()

    def _resolve_skill_entry(skill_name: str, *, include_disabled: bool = False) -> SkillRecord | None:
        return resolve_skill(skill_name, plugins_dir=skills_dir, include_disabled=include_disabled)

    def _available_skill_ids() -> list[str]:
        return [skill.name for skill in registry_list_skills(plugins_dir=skills_dir)]

    from src.mcp.augur_core.tools.core import register_core_tools as _reg_core
    from src.mcp.augur_framework.tools.infrastructure.actions import (
        register_action_tools,
    )

    _reg_core(
        mcp=mcp,
        skill_cache=skill_cache,
        metrics=metrics,
        registry_list_skills=registry_list_skills,
        resolve_skill_entry=_resolve_skill_entry,
        available_skill_ids=_available_skill_ids,
        mcp_tool_interceptor=interceptor,
    )

    # Action tools (skill-action) depend on the
    # resolve_skill_entry helper. Wire them here so the
    # dashboard MCPBridge can call them; the standalone augur-framework path
    # doesn't need them since AI clients reach skill actions via slash
    # commands, not direct MCP.
    register_action_tools(
        mcp=mcp,
        mcp_tool_interceptor=interceptor,
        metrics=metrics,
        resolve_skill_entry=_resolve_skill_entry,
    )


def register_framework_tools(
    mcp: FastMCP,
    interceptor: Callable[..., Any],
    metrics: Any,
    *,
    capability_target: str = "mcp",
) -> None:
    """Register all augur-framework operational tools."""
    from src.mcp.augur_framework.tools.domain import register_domain_tools as _reg_domain
    from src.mcp.augur_framework.tools.infrastructure import (
        register_infrastructure_tools as _reg_infra,
    )
    from src.mcp.augur_shared.plugin_tools import create_capability_policy_filtered_mcp

    filtered_mcp = create_capability_policy_filtered_mcp(
        mcp,
        source_name="augur-framework",
        target=capability_target,
    )

    if _env_flag_enabled("AUGUR_DASHBOARD_MCP_INCLUDE_CORE_TOOLS"):
        _register_dashboard_core_tools(filtered_mcp, interceptor, metrics)

    _reg_domain(filtered_mcp, interceptor, metrics)
    _reg_infra(filtered_mcp, interceptor, metrics)
