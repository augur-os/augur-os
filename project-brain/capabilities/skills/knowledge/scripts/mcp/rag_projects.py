"""RAG project CRUD and indexing tools.

Handles list, create, and background indexing of RAG projects.
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
import asyncio
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.mcp.augur_shared.logging import get_entity_logger
    from src.mcp.augur_shared.annotations import tool_annotations
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        logging = importlib.import_module("logging")
        return logging.getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations

logger = get_entity_logger("mcp.knowledge.rag.projects")

try:
    from src.config.paths import get_project_root, get_rag_dir

    PROJECT_ROOT = get_project_root()
except ImportError:
    import sys

    # skills/knowledge/scripts/mcp/rag_projects.py -> project root
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent  # fallback
    if sys.platform == "darwin":
        get_rag_dir = lambda: Path.home() / "Library" / "Application Support" / "Augur" / "rag"
    else:
        get_rag_dir = lambda: Path.home() / ".local" / "share" / "augur" / "rag"


def register_rag_project_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register RAG project CRUD and indexing tools."""
    from . import _list_rag_projects, _create_rag_project

    @mcp.tool(
        name="list-rag-projects",
        annotations=tool_annotations(
            {
                "title": "List RAG Projects",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_rag_projects_tool() -> str:
        """List all RAG projects.

        Returns:
            str: JSON with projects list
        """
        metrics.track_tool("list_rag_projects", skill="knowledge")

        try:
            projects = await asyncio.to_thread(_list_rag_projects)
            return json.dumps({"projects": projects}, indent=2, default=str)

        except Exception as e:
            logger.error(f"Failed to list RAG projects: {e}", exc_info=True)
            return json.dumps({"projects": []})

    @mcp.tool(
        name="create-rag-project",
        annotations=tool_annotations(
            {
                "title": "Create RAG Project",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def create_rag_project_tool(
        name: str,
        index_mode: str | None = None,
        limits: dict[str, Any] | None = None,
    ) -> str:
        """Create a new RAG project.

        Args:
            name: Project name
            index_mode: Index mode (auto or manual)
            limits: Project limits configuration

        Returns:
            str: JSON with created project
        """
        metrics.track_tool("create_rag_project", skill="knowledge")

        try:
            project = await asyncio.to_thread(_create_rag_project, name, index_mode, limits)
            return json.dumps({"project": project}, indent=2, default=str)

        except Exception as e:
            logger.error(f"Failed to create RAG project: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="start-rag-indexing",
        annotations=tool_annotations(
            {
                "title": "Start RAG Indexing",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def start_rag_indexing_tool(
        folder_path: str,
        project_name: str = "",
    ) -> str:
        """Start a background RAG indexing job for a folder.

        Spawns a detached Python process that indexes the given folder into
        a new RAG project.  Returns immediately with the project ID so the
        caller can poll for status via the project metadata file.

        Args:
            folder_path: Absolute path to the folder to index
            project_name: Human-readable project name (defaults to folder basename)

        Returns:
            str: JSON with project_id, status, and metadata
        """
        metrics.track_tool("start_rag_indexing", skill="knowledge")

        folder = Path(folder_path).resolve()
        if not folder.is_dir():
            return json.dumps(
                {"success": False, "error": "Folder does not exist or is not a directory"},
            )

        project_id = str(uuid.uuid4())
        name = project_name.strip() if project_name else folder.name

        data_root = Path(os.environ.get("AUGUR_ROOT", str(PROJECT_ROOT)))
        projects_root = get_rag_dir() / "projects"
        projects_root.mkdir(parents=True, exist_ok=True)
        project_dir = projects_root / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = project_dir / "metadata.json"

        # Global safety rail: only one active indexing job at a time
        try:
            import fcntl as _fcntl
        except ImportError:
            _fcntl = None  # type: ignore[assignment]

        lock_path = projects_root / ".indexing.lock"
        lock_fp = open(lock_path, "w")  # noqa: WPS515
        try:
            if _fcntl is not None:
                _fcntl.flock(lock_fp.fileno(), _fcntl.LOCK_EX)

            for entry in projects_root.iterdir():
                if not entry.is_dir():
                    continue
                candidate_meta = entry / "metadata.json"
                if not candidate_meta.exists():
                    continue
                try:
                    existing = json.loads(candidate_meta.read_text(encoding="utf-8"))
                    if (
                        existing.get("status") == "indexing"
                        and isinstance(existing.get("pid"), int)
                    ):
                        try:
                            os.kill(existing["pid"], 0)
                            return json.dumps(
                                {
                                    "success": False,
                                    "error": "Another indexing job is already running",
                                    "statusCode": 409,
                                    "active_project_id": existing.get("id", entry.name),
                                },
                            )
                        except OSError:
                            pass
                except (json.JSONDecodeError, KeyError):
                    pass

            metadata: dict[str, Any] = {
                "id": project_id,
                "name": name,
                "source_folder": str(folder),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "indexing",
                "total_files": 0,
                "processed_files": 0,
            }
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        finally:
            if _fcntl is not None:
                _fcntl.flock(lock_fp.fileno(), _fcntl.LOCK_UN)
            lock_fp.close()

        repo_root = str(PROJECT_ROOT)
        cli_script = str(PROJECT_ROOT / "src" / "lib" / "rag" / "cli.py")
        python_cmd = os.environ.get("AUGUR_PYTHON", "python3")

        env = {**os.environ}
        python_path_parts = [repo_root]
        if env.get("PYTHONPATH"):
            python_path_parts.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(python_path_parts)
        env["AUGUR_RAG_PROJECT_ID"] = project_id
        env["AUGUR_ROOT"] = str(data_root)

        args = [
            python_cmd,
            cli_script,
            "index",
            str(folder),
            "--project",
            name,
            "--no-ocr",
            "--progress",
        ]

        try:
            proc = subprocess.Popen(
                args,
                cwd=repo_root,
                env=env,
                start_new_session=True,
                close_fds=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            metadata["status"] = "failed"
            metadata["failed_at"] = datetime.now(timezone.utc).isoformat()
            metadata["error"] = str(exc)
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            return json.dumps({"success": False, "error": f"Failed to start indexer: {exc}"})

        metadata["pid"] = proc.pid
        metadata["started_at"] = datetime.now(timezone.utc).isoformat()
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        logger.info(
            "Started RAG indexing job %s (PID %d) for %s",
            project_id,
            proc.pid,
            folder,
        )

        return json.dumps(
            {
                "success": True,
                "project_id": project_id,
                "project_name": name,
                "folder_path": str(folder),
                "status": "indexing",
            },
            indent=2,
        )
