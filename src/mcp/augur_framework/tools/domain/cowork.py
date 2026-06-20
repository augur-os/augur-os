"""
Cowork Integration MCP Tools (ADR-135).

Tools for Claude Cowork result ingestion, status, and collateral classification.

Tools registered:
- sync-cowork-results: Scan the runtime state cowork-dispatch directory for
  completed task files,
  ingest results into plugin data directories, mark tasks done.
- get-cowork-status: Report pending/completed task counts and dispatch dir health.
- classify-collateral: Trigger classify_collateral.py for manual re-routing of
  stray root files from the dashboard.
"""

import asyncio
import json
import subprocess  # nosec B404
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field
from src.config.paths import get_python_executable, get_skill_assets_dir
from src.mcp.augur_shared.annotations import tool_annotations
from src.mcp.augur_shared.config import get_runtime_dir
from src.mcp.augur_shared.logging import get_entity_logger

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_entity_logger("mcp")

# Project root — 4 levels up from this file.
PROJECT_ROOT = Path(__file__).resolve().parents[4]
CLASSIFY_SCRIPT = PROJECT_ROOT / "src" / "scripts" / "classify_collateral.py"


def _get_cowork_dispatch_dir() -> Path:
    """Return the canonical Cowork dispatch directory in runtime state."""
    return get_runtime_dir() / "cowork-dispatch"


def _get_cowork_results_dir() -> Path:
    """Return the canonical Cowork results log directory in runtime state."""
    return get_runtime_dir() / "cowork-results"


# =============================================================================
# Pydantic Input Models
# =============================================================================


class SyncCoworkResultsInput(BaseModel):
    """Input for sync-cowork-results tool."""

    model_config = ConfigDict(extra="forbid")
    dry_run: bool = Field(False, description="If true, report what would be synced without moving files")
    max_tasks: int = Field(50, description="Maximum number of completed task files to process per call")


class GetCoworkStatusInput(BaseModel):
    """Input for get-cowork-status tool."""

    model_config = ConfigDict(extra="forbid")
    include_completed: bool = Field(False, description="Include completed task details in the response")


class ClassifyCollateralInput(BaseModel):
    """Input for classify-collateral tool."""

    model_config = ConfigDict(extra="forbid")
    dry_run: bool = Field(False, description="Simulate routing without moving files")
    root_dir: str | None = Field(None, description="Project root to scan (defaults to Augur root)")
    verbose: bool = Field(False, description="Include detailed classification log in response")


# =============================================================================
# Helpers
# =============================================================================


def _read_task_file(path: Path) -> dict[str, Any] | None:
    """Safely parse a Cowork task JSON file."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Failed to read task file {path}: {e}")
        return None


def _ingest_result(task: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """
    Ingest a completed Cowork task result into Augur's plugin data.

    Cowork task files may include a 'result' dict with:
      - skill: target skill name
      - hub: target hub name
      - output_files: list of {filename, content} to write
      - summary: text summary to append to a log

    Returns an ingest status dict.
    """
    task_id = task.get("task_id", "unknown")
    result = task.get("result")

    if not result or not isinstance(result, dict):
        return {
            "task_id": task_id,
            "ingested": False,
            "reason": "no result payload",
        }

    skill = result.get("skill", "")
    hub = result.get("hub", "")
    output_files: list[dict] = result.get("output_files", [])
    summary = result.get("summary", "")

    ingested_files = []
    errors = []

    if skill and hub and output_files:
        target_dir = get_skill_assets_dir(skill)
        for file_spec in output_files:
            filename = file_spec.get("filename", "")
            content = file_spec.get("content", "")
            if not filename:
                continue
            dest = target_dir / filename
            if dry_run:
                ingested_files.append(f"[DRY RUN] {dest}")
            else:
                try:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    dest.write_text(content, encoding="utf-8")
                    ingested_files.append(str(dest))
                except Exception as e:
                    errors.append(f"{filename}: {e}")

    # Append summary to a session log if present
    if summary and not dry_run:
        log_dir = _get_cowork_results_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"session_{datetime.now().strftime('%Y%m%d')}.log"
        try:
            with log_file.open("a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now().isoformat()}] task={task_id}\n{summary}\n")
        except Exception as e:
            errors.append(f"log write: {e}")

    return {
        "task_id": task_id,
        "ingested": len(ingested_files) > 0 or bool(summary),
        "files_written": ingested_files,
        "errors": errors,
        "skill": skill,
        "hub": hub,
    }


# =============================================================================
# Tool Registration
# =============================================================================


def register_cowork_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable,
    metrics: Any,
) -> None:
    """Register Cowork integration tools with the MCP server."""

    @mcp.tool(
        name="sync-cowork-results",
        annotations=tool_annotations(
            {
                "title": "Sync Cowork Results",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def sync_cowork_results_tool(params: SyncCoworkResultsInput) -> str:
        """Scan the runtime state cowork-dispatch directory for completed Cowork task files and ingest results.

        Completed task files have status='completed' and a 'result' payload.
        After ingestion, task files are moved to the dispatch directory's done/.
        Files with status='pending' are left untouched for Cowork to process.

        Args:
            params: SyncCoworkResultsInput with dry_run and max_tasks

        Returns:
            str: JSON with sync summary {synced, skipped, errors, tasks}
        """
        metrics.track_tool("sync_cowork_results")
        dispatch_dir = _get_cowork_dispatch_dir()

        if not dispatch_dir.exists():
            return json.dumps(
                {
                    "success": True,
                    "synced": 0,
                    "skipped": 0,
                    "errors": 0,
                    "tasks": [],
                    "message": f"Dispatch directory does not exist yet: {dispatch_dir}",
                },
                indent=2,
            )

        done_dir = dispatch_dir / "done"
        task_files = sorted(
            [f for f in dispatch_dir.glob("task_*.json") if f.is_file()],
            key=lambda p: p.stat().st_mtime,
        )[: params.max_tasks]

        synced, skipped, errors_count = 0, 0, 0
        tasks_summary = []

        for task_path in task_files:
            task = _read_task_file(task_path)
            if not task:
                errors_count += 1
                tasks_summary.append({"file": task_path.name, "status": "unreadable"})
                continue

            status = task.get("status", "")
            if status != "completed":
                skipped += 1
                tasks_summary.append({"file": task_path.name, "status": status, "action": "skipped"})
                continue

            ingest_result = await asyncio.to_thread(_ingest_result, task, params.dry_run)

            if ingest_result.get("errors"):
                errors_count += 1
            else:
                synced += 1

            # Move to done/ after ingestion
            if not params.dry_run:
                try:
                    done_dir.mkdir(parents=True, exist_ok=True)
                    task_path.rename(done_dir / task_path.name)
                except Exception as e:
                    logger.warning(f"Could not move {task_path.name} to done/: {e}")

            tasks_summary.append(
                {
                    "file": task_path.name,
                    "task_id": ingest_result["task_id"],
                    "ingested": ingest_result["ingested"],
                    "files_written": ingest_result.get("files_written", []),
                    "errors": ingest_result.get("errors", []),
                }
            )

        return json.dumps(
            {
                "success": True,
                "dry_run": params.dry_run,
                "synced": synced,
                "skipped": skipped,
                "errors": errors_count,
                "tasks": tasks_summary,
                "dispatch_dir": str(dispatch_dir),
            },
            indent=2,
        )

    @mcp.tool(
        name="get-cowork-status",
        annotations=tool_annotations(
            {
                "title": "Get Cowork Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_cowork_status_tool(params: GetCoworkStatusInput) -> str:
        """Get Cowork dispatch directory status and pending task counts.

        Returns counts of pending/completed/failed tasks and dispatch dir health.

        Args:
            params: GetCoworkStatusInput with include_completed flag

        Returns:
            str: JSON with status {dispatch_dir_exists, pending, completed, tasks}
        """
        metrics.track_tool("get_cowork_status")
        dispatch_dir = _get_cowork_dispatch_dir()

        dispatch_exists = dispatch_dir.exists()
        pending, completed, done_count = 0, 0, 0
        tasks_detail: list[dict] = []

        if dispatch_exists:
            for task_path in dispatch_dir.glob("task_*.json"):
                if not task_path.is_file():
                    continue
                task = _read_task_file(task_path)
                status = task.get("status", "unknown") if task else "unreadable"
                if status == "pending":
                    pending += 1
                elif status == "completed":
                    completed += 1

                if params.include_completed or status == "pending":
                    tasks_detail.append(
                        {
                            "file": task_path.name,
                            "task_id": task.get("task_id") if task else None,
                            "status": status,
                            "created_at": task.get("created_at") if task else None,
                        }
                    )

            done_dir = dispatch_dir / "done"
            if done_dir.exists():
                done_count = sum(1 for f in done_dir.glob("task_*.json") if f.is_file())

        return json.dumps(
            {
                "success": True,
                "dispatch_dir": str(dispatch_dir),
                "dispatch_dir_exists": dispatch_exists,
                "pending": pending,
                "completed": completed,
                "done_archived": done_count,
                "tasks": tasks_detail,
            },
            indent=2,
        )

    @mcp.tool(
        name="classify-collateral",
        annotations=tool_annotations(
            {
                "title": "Classify Collateral Files",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def classify_collateral_tool(params: ClassifyCollateralInput) -> str:
        """Route stray repo-root files to the correct skill assets directories using LLM classification.

        Runs classify_collateral.py which scans the project root for non-whitelisted
        files, asks the LLM to classify each by skill/hub based on file content and
        git context, then moves files to the target skill assets directory.
        Files the LLM cannot classify go to state/garbage_collector/.

        Args:
            params: ClassifyCollateralInput with dry_run, root_dir, verbose

        Returns:
            str: JSON with routing summary {routed, archived, errors, log}
        """
        metrics.track_tool("classify_collateral")

        if not CLASSIFY_SCRIPT.exists():
            return json.dumps(
                {
                    "success": False,
                    "error": f"classify_collateral.py not found at: {CLASSIFY_SCRIPT}",
                },
                indent=2,
            )

        cmd = [str(get_python_executable()), str(CLASSIFY_SCRIPT)]
        if params.dry_run:
            cmd.append("--dry-run")
        if params.root_dir:
            cmd.extend(["--root-dir", params.root_dir])
        if params.verbose:
            cmd.append("--verbose")

        logger.info(f"Running classify_collateral: dry_run={params.dry_run}")

        try:
            result = await asyncio.to_thread(
                subprocess.run,  # nosec B603
                cmd,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            # Parse summary lines from script output
            routed, archived, errors_count = 0, 0, 0
            log_lines = []
            for line in stdout.splitlines():
                log_lines.append(line)
                if "Routed:" in line:
                    try:
                        routed = int(line.split("Routed:")[1].strip().split()[0])
                    except (ValueError, IndexError):
                        pass
                elif "Archived:" in line:
                    try:
                        archived = int(line.split("Archived:")[1].strip().split()[0])
                    except (ValueError, IndexError):
                        pass
                elif "Errors:" in line:
                    try:
                        errors_count = int(line.split("Errors:")[1].strip().split()[0])
                    except (ValueError, IndexError):
                        pass

            success = result.returncode == 0
            return json.dumps(
                {
                    "success": success,
                    "dry_run": params.dry_run,
                    "routed": routed,
                    "archived": archived,
                    "errors": errors_count,
                    "log": log_lines if params.verbose else [],
                    "stderr": stderr[:500] if stderr and not success else "",
                },
                indent=2,
            )

        except subprocess.TimeoutExpired:
            logger.error("classify_collateral timed out after 120s")
            return json.dumps(
                {"success": False, "error": "classify_collateral.py timed out (120s)"},
                indent=2,
            )
        except Exception as e:
            logger.error(f"classify_collateral failed: {e}")
            return json.dumps({"success": False, "error": str(e)}, indent=2)


__all__ = ["register_cowork_tools"]
