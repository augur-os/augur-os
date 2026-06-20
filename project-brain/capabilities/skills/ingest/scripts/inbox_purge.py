from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import get_runtime_dir

from src.lib.ingest.inbox_models import InboxFileResult, InboxRunRecord
from src.lib.ingest.inbox_scan import scan_folder
from src.lib.ingest.inbox_store import InboxStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _unique_destination_path(target: Path) -> Path:
    if not target.exists():
        return target
    for index in range(2, 10_000):
        candidate = target.with_name(f"{target.stem}-{index}{target.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find available destination path for {target}")


def purge_folder(*, store: InboxStore, folder_id: str) -> InboxRunRecord:
    folder = store.get_folder(folder_id)
    started = _now()
    scan = scan_folder(folder.path)
    trash_dir = (
        get_runtime_dir()
        / "brain"
        / "inbox"
        / "trash"
        / folder_id
        / started.replace(":", "-")
    )
    file_results: list[InboxFileResult] = []
    files_moved = 0

    if scan.counts.failed and not scan.items:
        file_results.append(
            InboxFileResult(
                source_path=folder.path,
                final_path="",
                source_card_path="",
                content_type="folder",
                extraction_method="scan",
                hardware_backend="none",
                confidence="low",
                route="",
                renamed_to="",
                rag_indexed=False,
                status="failed",
                review_reason="Inbox folder scan failed before purge.",
                error=f"Inbox folder scan failed: {folder.path}",
            )
        )
    else:
        for item in scan.items:
            if item.candidate_type != "trash":
                continue

            source = Path(item.path)
            if not item.stable:
                file_results.append(
                    InboxFileResult(
                        source_path=str(source),
                        final_path="",
                        source_card_path="",
                        content_type="trash",
                        extraction_method="purge-to-trash",
                        hardware_backend="none",
                        confidence="low",
                        route="trash",
                        renamed_to="",
                        rag_indexed=False,
                        status="needs_review",
                        review_reason="Trash candidate is still changing; retry after it is stable.",
                    )
                )
                continue

            try:
                destination = _unique_destination_path(trash_dir / source.name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), destination)
                files_moved += 1
                file_results.append(
                    InboxFileResult(
                        source_path=str(source),
                        final_path=str(destination),
                        source_card_path="",
                        content_type="trash",
                        extraction_method="purge-to-trash",
                        hardware_backend="none",
                        confidence="high",
                        route="trash",
                        renamed_to=destination.name,
                        rag_indexed=False,
                        status="success",
                    )
                )
            except OSError as exc:
                file_results.append(
                    InboxFileResult(
                        source_path=str(source),
                        final_path="",
                        source_card_path="",
                        content_type="trash",
                        extraction_method="purge-to-trash",
                        hardware_backend="none",
                        confidence="low",
                        route="trash",
                        renamed_to="",
                        rag_indexed=False,
                        status="failed",
                        review_reason="Trash candidate could not be moved.",
                        error=str(exc),
                    )
                )

    failed = sum(1 for result in file_results if result.status == "failed")
    needs_review = sum(1 for result in file_results if result.status == "needs_review")
    status = "success"
    if failed and files_moved == 0:
        status = "failed"
    elif failed or needs_review:
        status = "partial_success"

    record = InboxRunRecord(
        id=f"purge_{uuid.uuid4().hex[:12]}",
        folder_id=folder_id,
        started_at=started,
        completed_at=_now(),
        status=status,
        airplane_mode=True,
        files_seen=scan.counts.trash_candidates,
        files_moved=files_moved,
        files_skipped=needs_review,
        files_failed=failed,
        file_results=file_results,
    )
    saved = store.save_run(record)
    refreshed = scan_folder(folder.path)
    store.update_folder_state(
        folder_id,
        counts=refreshed.counts,
        last_scan_at=saved.completed_at,
        last_run_status=saved.status,
    )
    return saved
