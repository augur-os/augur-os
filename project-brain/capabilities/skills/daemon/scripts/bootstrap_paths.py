"""Bootstrap project paths for daemon scripts before importing ``src`` modules."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def find_project_root(start_file: str | Path) -> Path:
    """Find the Augur project root from script landmarks, env, or old layout."""
    start = Path(start_file).resolve()
    for candidate in (start.parent, *start.parents):
        if (
            (candidate / "pyproject.toml").is_file()
            and (
                (candidate / "src" / "config" / "paths.py").is_file()
                or (candidate / "config" / "system").is_dir()
            )
        ):
            return candidate

    if env_path := os.environ.get("AUGUR_ROOT"):
        return Path(env_path).expanduser().resolve()

    return start.parents[3]


def ensure_project_paths(start_file: str | Path) -> Path:
    """Put project-brain capabilities and project root first on sys.path."""
    project_root = find_project_root(start_file)
    os.environ["AUGUR_ROOT"] = str(project_root)
    project_capabilities = project_root / "project-brain" / "capabilities"
    mcp_src = project_root / "src" / "mcp"
    root_text = str(project_root)
    capabilities_text = str(project_capabilities)
    mcp_text = str(mcp_src)
    sys.path[:] = [entry for entry in sys.path if entry not in {capabilities_text, root_text, mcp_text}]
    sys.path.insert(0, mcp_text)
    sys.path.insert(0, root_text)
    sys.path.insert(0, capabilities_text)

    if sys.platform == "win32":
        _patch_subprocess_no_window()

    return project_root


def _patch_subprocess_no_window() -> None:
    """Monkey-patch subprocess.Popen on Windows to ensure CREATE_NO_WINDOW is always set."""
    try:
        import subprocess

        # Avoid double patching
        if getattr(subprocess.Popen, "_patched_no_window", False):
            return

        original_init = subprocess.Popen.__init__

        def patched_init(self, *args, **kwargs):
            # 0x08000000 is CREATE_NO_WINDOW
            if len(args) >= 14:
                args_list = list(args)
                args_list[13] = (args_list[13] or 0) | 0x08000000
                args = tuple(args_list)
            else:
                creationflags = kwargs.get("creationflags", 0) or 0
                kwargs["creationflags"] = creationflags | 0x08000000
            original_init(self, *args, **kwargs)

        subprocess.Popen.__init__ = patched_init
        subprocess.Popen._patched_no_window = True
    except Exception:
        # Ignore errors during monkey patching to prevent breaking execution
        pass



def _is_stale_augur_pythonpath_entry(entry: str, project_root: Path) -> bool:
    if not entry:
        return True
    try:
        path = Path(entry).expanduser().resolve()
    except (OSError, RuntimeError):
        return False
    current = {
        (project_root / "project-brain" / "capabilities").resolve(),
        project_root.resolve(),
        (project_root / "src" / "mcp").resolve(),
    }
    if path in current:
        return True
    parts = path.parts
    if len(parts) >= 2 and parts[-2:] == ("src", "mcp"):
        return True
    if path.name == "project-brain":
        return True
    if path.name == "Augur":
        return True
    return False


def project_python_env(project_root: Path) -> dict[str, str]:
    """Return environment with canonical Augur paths first in PYTHONPATH."""
    env = os.environ.copy()
    root_text = str(project_root)
    capabilities_text = str(project_root / "project-brain" / "capabilities")
    mcp_text = str(project_root / "src" / "mcp")
    existing = [
        entry
        for entry in env.get("PYTHONPATH", "").split(os.pathsep)
        if not _is_stale_augur_pythonpath_entry(entry, project_root)
    ]
    env["AUGUR_ROOT"] = root_text
    env["PYTHONPATH"] = os.pathsep.join([capabilities_text, root_text, mcp_text, *existing])
    return env
