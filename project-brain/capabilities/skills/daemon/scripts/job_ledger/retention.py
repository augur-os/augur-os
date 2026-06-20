"""Job ledger retention -- archive terminal jobs past the window (ADR-743).

Terminal jobs older than retention_days move to jobs/_archive/: events.jsonl is
gzipped, meta.json is kept uncompressed (small, grep-friendly), output/ is dropped.
Idempotent.
"""
from __future__ import annotations

import gzip
import logging
import shutil
import time
from typing import Any

try:
    from . import job_record
except ImportError:  # pragma: no cover - direct spec loading in tests
    import job_record

logger = logging.getLogger("job_ledger.retention")


def archive(*, retention_days: int = 30) -> dict[str, Any]:
    """Move terminal jobs older than retention_days into jobs/_archive/."""
    root = job_record.jobs_dir()
    archive_dir = root / "_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - retention_days * 86400

    archived = 0
    for job_dir in sorted(p for p in root.iterdir() if p.is_dir() and p.name != "_archive"):
        if not job_record.is_terminal(job_record.current_state(job_dir)):
            continue
        events_path = job_dir / "events.jsonl"
        if not events_path.exists() or events_path.stat().st_mtime > cutoff:
            continue
        try:
            archive_name = _archive_name(job_dir)
            with events_path.open("rb") as src, gzip.open(
                archive_dir / f"{archive_name}.events.jsonl.gz", "wb"
            ) as dst:
                shutil.copyfileobj(src, dst)
            meta_path = job_dir / "meta.json"
            if meta_path.exists():
                shutil.copy2(meta_path, archive_dir / f"{archive_name}.meta.json")
            shutil.rmtree(job_dir)
            archived += 1
        except Exception as exc:  # noqa: BLE001 - a partial archive run is acceptable
            logger.warning("job ledger could not archive %s: %s", job_dir.name, exc)

    return {"archived": archived}


def _archive_name(job_dir) -> str:
    meta = job_record.read_meta(job_dir)
    job_id = meta.get("job_id")
    if isinstance(job_id, str) and job_id:
        return job_id
    return job_dir.name
