"""Memory read/write/search/curation tools.

Handles memory search, stats, index rebuild, decision/preference logging,
curation, profile regeneration, daily logs, profile read/write,
workspace open, memory config, and cleanup.

Sub-modules:
    tools_memory_core      — search, stats, index, logging, curation, profile regen
    tools_memory_dashboard — dashboard read payload, daily logs
    tools_memory_profile   — HUMAN_API profile, workspace, config, cleanup
"""

from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.mcp.augur_shared.logging import get_entity_logger
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        logging = importlib.import_module("logging")
        return logging.getLogger(name)


from src.lib.knowledge import DailyLogger, MemoryStore, MemoryCurator

logger = get_entity_logger("mcp.knowledge.memory")

TOOLS_DIR = Path(__file__).parent
PLUGIN_ROOT = TOOLS_DIR.parent

try:
    from src.config.paths import get_project_root

    PROJECT_ROOT = get_project_root()
except ImportError:
    PROJECT_ROOT = PLUGIN_ROOT.parent.parent.parent.parent  # fallback


def register_memory_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register memory tools with the MCP server."""
    logger.info("Registering memory tools...")

    # Initialize memory components
    daily_logger = DailyLogger()
    memory_store = MemoryStore(ensure_file=False)
    curator = MemoryCurator()

    from .tools_memory_core import register_memory_core_tools
    from .tools_memory_dashboard import register_memory_dashboard_tools
    from .tools_memory_profile import register_memory_profile_tools

    register_memory_core_tools(
        mcp, mcp_tool_interceptor, metrics,
        daily_logger=daily_logger,
        memory_store=memory_store,
        curator=curator,
    )
    register_memory_dashboard_tools(
        mcp, mcp_tool_interceptor, metrics,
        project_root=PROJECT_ROOT,
    )
    register_memory_profile_tools(mcp, mcp_tool_interceptor, metrics)
