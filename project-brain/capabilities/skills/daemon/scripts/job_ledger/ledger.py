"""The job ledger run() context manager + state machine (ADR-743).

Wrap work in ``with run(...) as job:``. The context manager records
pending -> running -> (complete | failed | cancelled). It records failures but
never swallows real exceptions. If the ledger cannot write, it degrades to a
no-op job so the wrapped work still runs.
"""
from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    from . import job_record
except ImportError:  # pragma: no cover - direct spec loading in tests
    import job_record

logger = logging.getLogger("job_ledger.ledger")
_CURRENT_JOB_DIR: ContextVar[Path | None] = ContextVar("augur_current_job_dir", default=None)


class JobCancelled(Exception):
    """Raised by job.phase()/heartbeat() when cancel_requested exists."""


class Job:
    """Handle for one ledger job. phase/heartbeat/log append running events."""

    def __init__(self, job_dir: Path) -> None:
        self.job_dir = str(job_dir)
        self._dir = job_dir

    def _append(self, **event: Any) -> None:
        job_record.append_event(self._dir, event)

    def _is_cancel_requested(self) -> bool:
        return (self._dir / "cancel_requested").exists()

    def _check_cancel(self) -> None:
        if self._is_cancel_requested():
            raise JobCancelled("cancel requested")

    def phase(self, name: str) -> None:
        self._check_cancel()
        self._append(state="running", phase=name)

    def heartbeat(self) -> None:
        self._check_cancel()
        self._append(state="running", heartbeat=True)

    def log(self, msg: str) -> None:
        self._append(state="running", msg=msg)


class _NullJob(Job):
    """Used when the ledger cannot write; every method is a no-op."""

    def __init__(self) -> None:
        self.job_dir = ""

    def _append(self, **event: Any) -> None:
        pass

    def _check_cancel(self) -> None:
        pass

    def _is_cancel_requested(self) -> bool:
        return False


def current_job_dir() -> Path | None:
    """Return the job dir for the current ledger run context, if any."""
    return _CURRENT_JOB_DIR.get()


def _create_job(
    *,
    kind: str,
    name: str,
    args: dict[str, Any],
    timeout_s: int | None,
    submitter: str,
) -> Job:
    """Create the job dir + meta.json + pending event; return _NullJob on failure."""
    try:
        job_id = job_record.new_job_id(name)
        job_dir = job_record.jobs_dir() / job_id
        job_dir.mkdir(parents=True, exist_ok=False)
        (job_dir / "output").mkdir()
        (job_dir / "meta.json").write_text(
            json.dumps(
                {
                    "job_id": job_id,
                    "kind": kind,
                    "name": name,
                    "submitter": submitter,
                    "args": args,
                    "declared_timeout_s": timeout_s,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        job = Job(job_dir)
        job._append(state="pending")
        return job
    except Exception as exc:  # noqa: BLE001
        logger.warning("job ledger could not create a job for %s: %s", name, exc)
        return _NullJob()


def create_job(
    *,
    kind: str,
    name: str,
    args: dict[str, Any] | None = None,
    timeout_s: int | None = None,
    submitter: str = "daemon",
) -> Job:
    """Create a job record without managing completion; used by submit/replay surfaces."""
    return _create_job(
        kind=kind,
        name=name,
        args=args or {},
        timeout_s=timeout_s,
        submitter=submitter,
    )


@contextmanager
def run(
    *,
    kind: str,
    name: str,
    args: dict[str, Any] | None = None,
    timeout_s: int | None = None,
    submitter: str = "daemon",
) -> Iterator[Job]:
    """Wrap a run. Records the state machine; re-raises real exceptions."""
    job = create_job(
        kind=kind,
        name=name,
        args=args or {},
        timeout_s=timeout_s,
        submitter=submitter,
    )
    active_dir = getattr(job, "_dir", None)
    token = _CURRENT_JOB_DIR.set(active_dir if isinstance(active_dir, Path) else None)
    job._append(state="running", pid=os.getpid(), msg="started")
    try:
        yield job
    except JobCancelled as exc:
        job._append(state="cancelled", msg=str(exc))
    except BaseException as exc:
        job._append(state="failed", error=type(exc).__name__, msg=str(exc))
        raise
    else:
        if job._is_cancel_requested():
            job._append(state="cancelled", msg="cancel requested")
        else:
            job._append(state="complete")
    finally:
        _CURRENT_JOB_DIR.reset(token)
