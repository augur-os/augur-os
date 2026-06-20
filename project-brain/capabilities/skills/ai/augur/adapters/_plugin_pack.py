"""Helpers for loading plugin-pack formatter modules."""
from __future__ import annotations

import sys
from pathlib import Path

from src.config.paths import get_project_brain_skills_dir


def ensure_plugin_pack_formatters_path(project_root: Path) -> Path:
    """Add the project-brain plugin-pack formatter directory to sys.path."""
    formatters_path = get_project_brain_skills_dir(project_root) / "plugin-pack" / "scripts" / "formatters"
    path_str = str(formatters_path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
    return formatters_path
