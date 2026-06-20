"""Job ledger query and mutation ops shared by MCP tools and the CLI (ADR-743)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from . import job_record
except ImportError:  # pragma: no cover - direct spec loading in tests
    import job_record


def list_jobs(
    *,
    state: str | None = None,
    kind: str | None = None,
    archived: bool = False,
) -> list[dict[str, Any]]:
    """List jobs with their current state; filter by state/kind."""
    if archived:
        return _list_archived_jobs(state=state, kind=kind)

    root = job_record.jobs_dir()
    out: list[dict[str, Any]] = []
    for job_dir in sorted((p for p in root.iterdir() if p.is_dir() and p.name != "_archive"), reverse=True):
        meta = job_record.read_meta(job_dir)
        cur = job_record.current_state(job_dir)
        if state and cur != state:
            continue
        if kind and meta.get("kind") != kind:
            continue
        out.append(
            {
                "job_id": job_dir.name,
                "state": cur,
                "name": meta.get("name"),
                "kind": meta.get("kind"),
                "created_at": meta.get("created_at"),
            }
        )
    return out


def job_detail(job_id: str) -> dict[str, Any]:
    """Full meta + events for one live job."""
    job_dir = job_record.jobs_dir() / job_id
    if not job_dir.is_dir():
        return {"error": "not found", "job_id": job_id}
    return {
        "job_id": job_id,
        "meta": job_record.read_meta(job_dir),
        "state": job_record.current_state(job_dir),
        "events": job_record.read_events(job_dir),
    }


def cancel_job(job_id: str) -> dict[str, Any]:
    """Write the cancel_requested marker; phase()/heartbeat() pick it up cooperatively."""
    job_dir = job_record.jobs_dir() / job_id
    if not job_dir.is_dir():
        return {"error": "not found", "job_id": job_id}
    (job_dir / "cancel_requested").write_text("", encoding="utf-8")
    return {"job_id": job_id, "cancel_requested": True}


def submit_job(
    *,
    kind: str,
    name: str,
    args: dict[str, Any] | None = None,
    timeout_s: int | None = None,
) -> dict[str, Any]:
    """Register + start a job for a caller that reports events out-of-band."""
    try:
        from . import ledger
    except ImportError:  # pragma: no cover - direct spec loading in tests
        import ledger

    job = ledger.create_job(
        kind=kind,
        name=name,
        args=args or {},
        timeout_s=timeout_s,
        submitter="mcp",
    )
    job._append(state="running", msg="submitted")
    return {"job_id": Path(job.job_dir).name if job.job_dir else None}


def replay_job(job_id: str) -> dict[str, Any]:
    """Re-dispatch a job from scratch by creating a fresh ledger record."""
    meta = job_record.read_meta(job_record.jobs_dir() / job_id)
    if not meta:
        return {"error": "not found", "job_id": job_id}
    fresh = submit_job(
        kind=str(meta.get("kind") or "loop"),
        name=str(meta.get("name") or "replay"),
        args=meta.get("args") if isinstance(meta.get("args"), dict) else {},
        timeout_s=meta.get("declared_timeout_s"),
    )
    return {"replayed_from": job_id, **fresh}


def _list_archived_jobs(
    *,
    state: str | None = None,
    kind: str | None = None,
) -> list[dict[str, Any]]:
    archive_dir = job_record.jobs_dir() / "_archive"
    if not archive_dir.is_dir():
        return []

    out: list[dict[str, Any]] = []
    for meta_file in sorted(archive_dir.glob("*.meta.json"), reverse=True):
        job_id = meta_file.name.removesuffix(".meta.json")
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
        cur = str(meta.get("state") or "archived")
        if state and cur != state:
            continue
        if kind and meta.get("kind") != kind:
            continue
        out.append(
            {
                "job_id": job_id,
                "state": cur,
                "name": meta.get("name"),
                "kind": meta.get("kind"),
                "created_at": meta.get("created_at"),
                "archived": True,
            }
        )
    return out
