"""Shared helpers for platform-admin MCP tool modules."""

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
import asyncio
import json
import os
import subprocess
from typing import Any

from src.config.paths import get_python_executable
from src.mcp.augur_shared.annotations import tool_annotations as tool_annotations
from src.mcp.augur_shared.config import get_project_root
from src.mcp.augur_shared.logging import get_entity_logger

logger = get_entity_logger("mcp.dev.platform-admin")


def _run_python_script(relative_script: str, args: list[str] | None = None, timeout: int = 180) -> dict[str, Any]:
    """Run a repo script and return a structured response."""
    project_root = get_project_root()
    script_path = project_root / relative_script
    if not script_path.exists():
        return {
            "success": False,
            "error": f"Script not found: {relative_script}",
            "script": relative_script,
        }

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    python_path_entries = [
        str(project_root / "project-brain"),
        str(project_root),
        str(project_root / "src" / "mcp"),
    ]
    if existing_pythonpath:
        python_path_entries.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(python_path_entries)

    cmd = [str(get_python_executable()), str(script_path), *(args or [])]
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

    response: dict[str, Any] = {
        "success": result.returncode == 0,
        "returncode": result.returncode,
        "script": relative_script,
        "result": parsed,
    }
    if stderr:
        response["stderr"] = stderr
    return response


async def _run_python_script_async(relative_script: str, args: list[str] | None = None, timeout: int = 180) -> dict[str, Any]:
    return await asyncio.to_thread(_run_python_script, relative_script, args, timeout)
