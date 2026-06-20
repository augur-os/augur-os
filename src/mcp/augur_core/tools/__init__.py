"""Wire the augur-core tools into a FastMCP instance.

Tool definitions live in canonical packages under src/mcp/augur_core,
src/mcp/augur_framework, and src/mcp/augur_shared. The actual tool
functions are imported and re-registered.

Tools registered (per Track 3a design spec, post-PR-2 retirement):
- core (24): cross-skill, find-skill, get-skill, get-skill-doc,
  get-skill-health, list-skills, list-skill-actions, list-hub-recent-files,
  list-hub-vault-notes, list-skill-vault-notes, health, metrics,
  get-context, load-module, load-reference, update-skill-doc,
  save-synthesis, cache-control, get-config, get-design-standards,
  get-preferences, update-preference, ask-retain
- browse (17 — listings + 4 operational; design spec leaves the
  refactored partition for PR 6 once both servers exist)
- hubs (2): agent-registry, augur-list-capabilities
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]


def register_core_tools(
    mcp: FastMCP,
    interceptor: Callable[..., Any],
    metrics: Any,
    *,
    capability_target: str = "mcp",
) -> None:
    """Register augur-core tools against `mcp`.

    Imports the existing register_*_tools functions and invokes them against
    this server's FastMCP instance.
    """
    # Build the helpers expected by core tool registration.
    # The monolith owns `_resolve_skill_entry`, `_available_skill_ids`, and
    # `registry_list_skills` — replicate that wiring here so augur-core
    # is self-contained.
    from src.mcp.augur_shared.compat import list_skills as registry_list_skills
    from src.mcp.augur_shared.compat import resolve_skill
    from src.mcp.augur_shared.config import get_config as get_mcp_config
    from src.mcp.augur_shared.interfaces import SkillRecord
    from src.mcp.augur_shared.plugin_tools import create_capability_policy_filtered_mcp
    from src.mcp.augur_shared.server_cache import SkillCache

    filtered_mcp = create_capability_policy_filtered_mcp(
        mcp,
        source_name="augur-core",
        target=capability_target,
    )
    config = get_mcp_config()
    skills_dir = config.plugins_dir
    skill_cache = SkillCache()

    def _resolve_skill_entry(skill_name: str, *, include_disabled: bool = False) -> SkillRecord | None:
        return resolve_skill(skill_name, plugins_dir=skills_dir, include_disabled=include_disabled)

    def _available_skill_ids() -> list[str]:
        return [skill.name for skill in registry_list_skills(plugins_dir=skills_dir)]

    # ---- 24 core registry/discovery tools ----
    from src.mcp.augur_core.tools.core import register_core_tools as _reg_core

    _reg_core(
        mcp=filtered_mcp,
        skill_cache=skill_cache,
        metrics=metrics,
        registry_list_skills=registry_list_skills,
        resolve_skill_entry=_resolve_skill_entry,
        available_skill_ids=_available_skill_ids,
        mcp_tool_interceptor=interceptor,
    )

    # ---- browse tools (listings + 4 operational) ----
    from src.mcp.augur_framework.tools.infrastructure.browse import register_browse_tools as _reg_browse

    _reg_browse(filtered_mcp, mcp_tool_interceptor=interceptor, metrics=metrics)

    # ---- 2 hub registry/capabilities tools ----
    from src.mcp.augur_framework.tools.hubs.agent_registry import register_tools as _reg_agent
    from src.mcp.augur_framework.tools.hubs.capabilities import register_tools as _reg_cap

    _reg_agent(filtered_mcp, interceptor=interceptor, metrics=metrics)
    _reg_cap(filtered_mcp, interceptor=interceptor, metrics=metrics)
