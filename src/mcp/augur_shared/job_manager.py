"""
Background Job Manager - Async Task Execution for MCP Tools

Enables heavy MCP tools to run in the background without blocking the IDE.
Jobs are tracked with status and progress, and can be cancelled.

Usage:
    from src.mcp.augur_shared.job_manager import job_manager, async_tool

    @async_tool("transcribe_audio")
    def transcribe_audio(file_path: str):
        # Heavy work - runs in background
        ...

    # Or manually:
    job_id = job_manager.start_job("my_task", my_function, {"arg": "value"})
    status = job_manager.get_status(job_id)
    job_manager.cancel(job_id)

Author: Augur
Version: 1.0.0
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import wraps
from pathlib import Path
from threading import Lock
from typing import Any

from src.mcp.augur_shared.logging import get_entity_logger

logger = get_entity_logger("mcp.jobs")


class JobStatus(str, Enum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobInfo:
    """Information about a background job."""

    job_id: str
    name: str
    status: JobStatus
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    progress: int = 0  # 0-100
    progress_message: str = ""
    result: Any | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "name": self.name,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "result": self.result,
            "error": self.error,
        }


class BackgroundJobManager:
    """
    Manages background job execution for heavy MCP tools.

    Uses ThreadPoolExecutor for I/O-bound tasks (transcription, scraping, API calls).
    Stores job status in memory with optional persistence to disk.
    """

    def __init__(self, max_workers: int = 4, status_dir: Path | None = None):
        """
        Initialize the job manager.

        Args:
            max_workers: Maximum concurrent background jobs
            status_dir: Directory to persist job status (optional)
        """
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: dict[str, JobInfo] = {}
        self._futures: dict[str, Future] = {}
        self._lock = Lock()
        self._status_dir = status_dir

        if status_dir:
            status_dir.mkdir(parents=True, exist_ok=True)

    def start_job(self, name: str, func: Callable, kwargs: dict[str, Any], job_id: str | None = None) -> str:
        """
        Start a background job.

        Args:
            name: Human-readable job name
            func: Function to execute
            kwargs: Arguments to pass to function
            job_id: Optional custom job ID

        Returns:
            Job ID for status tracking
        """
        job_id = job_id or f"job_{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        job_info = JobInfo(job_id=job_id, name=name, status=JobStatus.PENDING, created_at=now)

        with self._lock:
            self._jobs[job_id] = job_info
            job_info.status = JobStatus.RUNNING
            job_info.started_at = datetime.now().isoformat()

        # Submit to executor
        future = self._executor.submit(self._run_job, func, kwargs, job_id)
        future.add_done_callback(lambda f: self._on_job_complete(job_id, f))

        with self._lock:
            self._futures[job_id] = future

        self._persist_status(job_id)
        logger.info(f"Started job {job_id}: {name}")

        return job_id

    def _run_job(self, func: Callable, kwargs: dict[str, Any], job_id: str) -> Any:
        """Execute job function (runs in subprocess)."""
        try:
            # Note: Progress updates from subprocess require IPC
            # For now, we just run the function directly
            result = func(**kwargs)
            return result
        except Exception:
            # Re-raise to be caught by callback
            raise

    def _on_job_complete(self, job_id: str, future: Future):
        """Callback when job completes or fails."""
        with self._lock:
            if job_id not in self._jobs:
                return

            job_info = self._jobs[job_id]
            job_info.completed_at = datetime.now().isoformat()

            if future.cancelled():
                job_info.status = JobStatus.CANCELLED
                job_info.progress_message = "Cancelled by user"
                logger.info(f"Job {job_id} cancelled")
            else:
                try:
                    result = future.result()
                    job_info.status = JobStatus.COMPLETED
                    job_info.result = result
                    job_info.progress = 100
                    job_info.progress_message = "Complete"
                    logger.info(f"Job {job_id} completed successfully")
                except Exception as e:
                    job_info.status = JobStatus.FAILED
                    job_info.error = str(e)
                    job_info.progress_message = f"Failed: {e}"
                    logger.error(f"Job {job_id} failed: {e}")

        self._persist_status(job_id)

    def get_status(self, job_id: str) -> JobInfo | None:
        """Get current status of a job."""
        with self._lock:
            return self._jobs.get(job_id)

    def get_all_jobs(self, include_completed: bool = False) -> list[JobInfo]:
        """Get all active (and optionally completed) jobs."""
        with self._lock:
            jobs = list(self._jobs.values())

        if not include_completed:
            jobs = [j for j in jobs if j.status in (JobStatus.PENDING, JobStatus.RUNNING)]

        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def cancel(self, job_id: str) -> bool:
        """
        Cancel a running job.

        Returns:
            True if cancelled, False if not found or already done
        """
        with self._lock:
            if job_id not in self._jobs:
                return False

            job_info = self._jobs[job_id]
            if job_info.status not in (JobStatus.PENDING, JobStatus.RUNNING):
                return False

            future = self._futures.get(job_id)

        if not future:
            return False

        cancelled = future.cancel()
        if not cancelled:
            return False

        with self._lock:
            maybe_job_info = self._jobs.get(job_id)
            if not maybe_job_info:
                return False
            maybe_job_info.status = JobStatus.CANCELLED
            maybe_job_info.completed_at = datetime.now().isoformat()
            maybe_job_info.progress_message = "Cancelled by user"
            logger.info(f"Job {job_id} cancelled")

        self._persist_status(job_id)
        return True

    def update_progress(self, job_id: str, progress: int, message: str = ""):
        """
        Update job progress (call from within job function if needed).

        Note: This only works if called from main process.
        For subprocess progress, use file-based IPC.
        """
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].progress = min(100, max(0, progress))
                self._jobs[job_id].progress_message = message

        self._persist_status(job_id)

    def _persist_status(self, job_id: str):
        """Persist job status to disk for recovery/polling."""
        if not self._status_dir:
            return

        with self._lock:
            if job_id not in self._jobs:
                return

            status_file = self._status_dir / f"{job_id}.json"
            try:
                status_file.write_text(json.dumps(self._jobs[job_id].to_dict(), indent=2), encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed to persist job status: {e}")

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove completed jobs older than max_age_hours."""
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)

        with self._lock:
            to_remove = []
            for job_id, job_info in self._jobs.items():
                if job_info.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                    if job_info.completed_at:
                        completed_ts = datetime.fromisoformat(job_info.completed_at).timestamp()
                        if completed_ts < cutoff:
                            to_remove.append(job_id)

            for job_id in to_remove:
                del self._jobs[job_id]
                if job_id in self._futures:
                    del self._futures[job_id]

                # Remove status file
                if self._status_dir:
                    status_file = self._status_dir / f"{job_id}.json"
                    if status_file.exists():
                        status_file.unlink()

        logger.info(f"Cleaned up {len(to_remove)} old jobs")

    def shutdown(self):
        """Shutdown the executor."""
        self._executor.shutdown(wait=False)


# Global job manager instance
_job_manager: BackgroundJobManager | None = None


def _resolve_project_root() -> Path:
    from src.mcp.augur_shared.config import get_project_root

    return get_project_root()


def get_job_manager() -> BackgroundJobManager:
    """Get or create the global job manager."""
    global _job_manager
    if _job_manager is None:
        # Status dir in project root
        project_root = _resolve_project_root()
        status_dir = project_root / ".job_status"
        _job_manager = BackgroundJobManager(max_workers=4, status_dir=status_dir)
    return _job_manager


def async_tool(name: str):
    """
    Decorator to make an MCP tool async (background execution).

    Usage:
        @async_tool("transcribe_audio")
        def transcribe_audio(file_path: str) -> str:
            # Heavy work
            return "result"

    When called, returns immediately with job_id for tracking.
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(**kwargs) -> dict:
            manager = get_job_manager()
            job_id = manager.start_job(name, func, kwargs)

            return {
                "status": "started",
                "job_id": job_id,
                "message": f"Job '{name}' started in background",
                "check_status": f"Call get_job_status with job_id='{job_id}'",
                "cancel": f"Call cancel_job with job_id='{job_id}'",
            }

        # Mark as async tool for MCP registration
        wrapper._is_async_tool = True  # type: ignore[attr-defined]
        wrapper._async_name = name  # type: ignore[attr-defined]
        return wrapper

    return decorator


# Convenience functions for MCP tools
def start_background_job(name: str, func: Callable, kwargs: dict[str, Any]) -> str:
    """Start a background job and return job_id."""
    return get_job_manager().start_job(name, func, kwargs)


def get_job_status(job_id: str) -> dict:
    """Get status of a background job."""
    manager = get_job_manager()
    job_info = manager.get_status(job_id)

    if not job_info:
        return {"error": f"Job not found: {job_id}"}

    return job_info.to_dict()


def cancel_job(job_id: str) -> dict:
    """Cancel a running background job."""
    manager = get_job_manager()
    cancelled = manager.cancel(job_id)

    if cancelled:
        return {"success": True, "message": f"Job {job_id} cancelled"}
    else:
        return {"success": False, "message": f"Could not cancel job {job_id} (not found or already done)"}


def list_active_jobs() -> dict:
    """List all active background jobs."""
    manager = get_job_manager()
    jobs = manager.get_all_jobs(include_completed=True)

    return {
        "active_count": sum(1 for j in jobs if j.status in (JobStatus.PENDING, JobStatus.RUNNING)),
        "total_count": len(jobs),
        "jobs": [j.to_dict() for j in jobs],
    }
