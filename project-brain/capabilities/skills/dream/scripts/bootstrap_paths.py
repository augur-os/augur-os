"""Bootstrap Augur project paths for dream skill scripts."""
from __future__ import annotations

import sys
from pathlib import Path


def find_project_root(start_file: str | Path) -> Path:
    """Find the Augur project root by repo landmarks."""
    start = Path(start_file).resolve()
    for candidate in (start.parent, *start.parents):
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "src" / "config" / "paths.py").is_file()
        ):
            return candidate
    raise RuntimeError(f"Unable to locate Augur project root from {start}")


def ensure_project_paths(start_file: str | Path) -> Path:
    """Put canonical project-brain capability and project import roots on sys.path."""
    project_root = find_project_root(start_file)
    for path in (project_root / "src" / "mcp", project_root, project_root / "project-brain" / "capabilities"):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
    return project_root
