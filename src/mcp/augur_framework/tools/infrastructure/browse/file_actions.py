"""File action tools: reveal in Finder, open file."""

import json
import os
import platform
import subprocess
from pathlib import Path

from ._helpers import _is_path_allowed


async def reveal_in_finder_impl(path: str) -> str:
    """Validate path and reveal in Finder (macOS) or file manager."""
    if not _is_path_allowed(path):
        return json.dumps({"success": False, "error": "Path not within allowed directories"})

    resolved = Path(path).resolve()
    if not resolved.exists():
        return json.dumps({"success": False, "error": f"Path does not exist: {path}"})

    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", "-R", str(resolved)], check=True)
        elif system == "Windows":
            # explorer.exe returns a non-zero exit code even on success, so do
            # not pass check=True here.
            subprocess.run(["explorer", f"/select,{resolved}"], check=False)
        else:
            subprocess.run(["xdg-open", str(resolved.parent)], check=True)
        return json.dumps({"success": True, "path": str(resolved)})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


async def open_file_impl(path: str) -> str:
    """Validate path and open file in default application."""
    if not _is_path_allowed(path):
        return json.dumps({"success": False, "error": "Path not within allowed directories"})

    resolved = Path(path).resolve()
    if not resolved.exists():
        return json.dumps({"success": False, "error": f"Path does not exist: {path}"})

    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", str(resolved)], check=True)
        elif system == "Windows":
            os.startfile(str(resolved))  # type: ignore[attr-defined]  # Windows-only
        else:
            subprocess.run(["xdg-open", str(resolved)], check=True)
        return json.dumps({"success": True, "path": str(resolved)})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
