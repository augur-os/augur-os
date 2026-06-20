"""Shared helpers for mcp-app-factory tool modules.

Provides common imports, path constants, and utility functions
used across all tool group modules.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# Use augur_mcp imports with fallback to standalone
try:
    from src.mcp.augur_shared.logging import get_entity_logger
    from src.mcp.augur_shared.annotations import tool_annotations
    from src.mcp.augur_shared.config import get_project_root
    from src.mcp.augur_shared.compat import (
        KERNEL_AVAILABLE,
        get_ide_backlog_manager,
        get_ide_command_executor,
        get_instruction_generator,
    )
except ImportError:
    # Standalone mode
    KERNEL_AVAILABLE = False

    def get_entity_logger(name: str):
        return importlib.import_module("logging").getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations

    def get_project_root() -> Path:
        data_dir = os.environ.get("AUGUR_ROOT")
        if data_dir:
            path = Path(data_dir)
            if not path.exists():
                raise FileNotFoundError(f"AUGUR_ROOT path does not exist: {path}")
            return path
        home = Path.home()
        monorepo_path = home / "Projects" / "augur"
        if monorepo_path.exists():
            return monorepo_path
        raise FileNotFoundError("Project root not found. Set AUGUR_ROOT environment variable.")

    def get_ide_backlog_manager():
        return None

    def get_ide_command_executor():
        return None

    def get_instruction_generator():
        return None


logger = get_entity_logger("mcp.mcp-app-factory")

# Plugin paths
TOOLS_DIR = Path(__file__).resolve().parent
AUGUR_ROOT = TOOLS_DIR.parent
PLUGIN_ROOT = AUGUR_ROOT.parent

try:
    from src.config.paths import get_project_root as _get_project_root
    PROJECT_ROOT = _get_project_root()
except ImportError:
    PROJECT_ROOT = PLUGIN_ROOT.parent.parent.parent.parent  # fallback


def ai_required_error(feature: str) -> str:
    """Return standard error for ai-required features."""
    return json.dumps(
        {
            "success": False,
            "error": "ai_not_available",
            "feature": feature,
            "message": f"The '{feature}' feature requires the full Augur src. "
            "Install with: pip install augur-mcp or clone the monorepo.",
            "standalone_mode": True,
        }
    )


def get_project_root_local() -> Path:
    """Get project root, handling both package and monorepo contexts."""
    if env_root := os.environ.get("AUGUR_ROOT"):
        return Path(env_root)

    current = Path(__file__).resolve()
    for _ in range(10):
        if (current / "src").is_dir() and (current / "config").is_dir():
            return current
        current = current.parent

    return Path.home() / "Projects" / "augur"


def get_workflow_engine():
    """Get the workflow engine instance."""
    sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
    from workflow import WorkflowEngine

    return WorkflowEngine()
