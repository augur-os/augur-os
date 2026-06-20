from __future__ import annotations

import shutil
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import get_vault_dir
from src.lib.extraction import extract, get_extraction_policy

from src.lib.ingest.inbox_models import InboxFileResult, InboxRunRecord
from src.lib.ingest.note_index_refresh import refresh_notes_browse_index
from src.lib.ingest.inbox_routing import decide_route
from src.lib.ingest.inbox_scan import scan_folder
from src.lib.ingest.inbox_store import InboxStore
from src.lib.ingest.source_cards import write_source_card


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".mp3", ".wav", ".m4a", ".flac"}:
        return "audio"
    if suffix in {".png", ".jpg", ".jpeg", ".tiff", ".webp"}:
        return "image"
    return "document"


def _unique_destination_path(target: Path) -> Path:
    if not target.exists():
        return target
    for index in range(2, 10_000):
        candidate = target.with_name(f"{target.stem}-{index}{target.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find available destination path for {target}")


def _write_extracted_artifact(
    *,
    vault_dir: Path,
    decision_filename: str,
    body: str,
    content_type: str,
) -> Path:
    suffix = ".transcript.md" if content_type == "audio" else ".extracted.md"
    target = _unique_destination_path(vault_dir / "sources" / "extracted" / f"{Path(decision_filename).stem}{suffix}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def _status(file_results: list[InboxFileResult]) -> str:
    failed = sum(1 for result in file_results if result.status == "failed")
    needs_review = sum(1 for result in file_results if result.status == "needs_review")
    if failed == 0 and needs_review == 0:
        return "success"
    if (
        failed
        and not needs_review
        and not any(result.status == "success" or result.source_card_path for result in file_results)
    ):
        return "failed"
    return "partial_success"


def _save_record(
    *,
    store: InboxStore,
    folder_id: str,
    started: str,
    policy: dict[str, bool],
    file_results: list[InboxFileResult],
    files_seen: int,
    files_moved: int,
) -> InboxRunRecord:
    indexed = sum(1 for result in file_results if result.rag_indexed)
    failed = sum(1 for result in file_results if result.status == "failed")
    needs_review = sum(1 for result in file_results if result.status == "needs_review")
    skipped = sum(1 for result in file_results if result.status == "skipped")
    record = InboxRunRecord(
        id=f"run_{uuid.uuid4().hex[:12]}",
        folder_id=folder_id,
        started_at=started,
        completed_at=_now(),
        status=_status(file_results),
        airplane_mode=bool(policy.get("airplane_mode_enabled", False)),
        files_seen=files_seen,
        files_moved=files_moved,
        files_indexed=indexed,
        files_skipped=skipped,
        files_failed=failed,
        files_needing_review=needs_review,
        cloud_calls=sum(1 for result in file_results if result.cloud_used),
        local_agent_calls=sum(1 for result in file_results if result.local_agent_used),
        wiki_update_marked=indexed > 0,
        file_results=file_results,
    )
    return store.save_run(record)


def _resolve_consume_vault_dir(
    *,
    to: str | None,
    cwd: Path | None,
    registry_path: Path | None,
) -> Path:
    """Resolve the destination vault root for an ingest run (ADR-771).

    When no brain-routing arguments are supplied, fall back to the configured
    personal vault so existing daemon/CLI callers keep their behavior. When a
    destination is requested (``--to`` or active-context ``cwd``), route through
    the shared brain write-target resolver and reject packets-only brains, which
    cannot accept direct ingest writes.
    """
    if to is None and cwd is None and registry_path is None:
        return get_vault_dir()

    from src.lib.brain_write_routing import resolve_write_target

    target = resolve_write_target(
        explicit_brain=to,
        cwd=cwd,
        registry_path=registry_path,
    )
    if target.mode == "packet":
        raise ValueError(
            f"brain {target.brain.id} requires packet-based writes; " "ingest does not support packet routing"
        )
    return target.notes_vault_dir


def consume_folder(
    *,
    store: InboxStore,
    folder_id: str,
    to: str | None = None,
    cwd: Path | None = None,
    registry_path: Path | None = None,
) -> InboxRunRecord:
    folder = store.get_folder(folder_id)
    started = _now()
    policy = get_extraction_policy()
    scan = scan_folder(folder.path)
    vault_dir = _resolve_consume_vault_dir(to=to, cwd=cwd, registry_path=registry_path)
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
                review_reason="Inbox folder scan failed.",
                error=f"Inbox folder scan failed: {folder.path}",
            )
        )
        return _save_record(
            store=store,
            folder_id=folder_id,
            started=started,
            policy=policy,
            file_results=file_results,
            files_seen=0,
            files_moved=files_moved,
        )

    for item in scan.items:
        source = Path(item.path)
        if item.candidate_type == "trash":
            file_results.append(
                InboxFileResult(
                    source_path=str(source),
                    final_path="",
                    source_card_path="",
                    content_type="trash",
                    extraction_method="skipped",
                    hardware_backend="none",
                    confidence="low",
                    route="",
                    renamed_to="",
                    rag_indexed=False,
                    status="skipped",
                    review_reason="Temporary or partial download file.",
                )
            )
            continue

        content_type = _content_type(source)
        if item.candidate_type == "failed":
            file_results.append(
                InboxFileResult(
                    source_path=str(source),
                    final_path="",
                    source_card_path="",
                    content_type=content_type,
                    extraction_method="scan",
                    hardware_backend="none",
                    confidence="low",
                    route="",
                    renamed_to="",
                    rag_indexed=False,
                    status="failed",
                    review_reason="File metadata could not be read during scan.",
                    error="File metadata could not be read during scan.",
                )
            )
            continue

        if not item.stable:
            file_results.append(
                InboxFileResult(
                    source_path=str(source),
                    final_path="",
                    source_card_path="",
                    content_type=content_type,
                    extraction_method="skipped",
                    hardware_backend="none",
                    confidence="low",
                    route="",
                    renamed_to="",
                    rag_indexed=False,
                    status="needs_review",
                    review_reason="File is still changing; retry after it is stable.",
                )
            )
            continue

        try:
            extracted = extract(
                str(source),
                max_tier=1,
                allow_cloud=bool(policy.get("cloud_escalation_allowed", False)),
            )
            body = extracted.markdown.strip()
            tier_used = extracted.tier_used
            error = extracted.error
        except Exception as exc:
            extracted = None
            body = ""
            tier_used = "error"
            error = str(exc)

        extraction_method = f"document-extractor:{tier_used}"
        if extracted is None or not extracted.success or not body:
            file_results.append(
                InboxFileResult(
                    source_path=str(source),
                    final_path="",
                    source_card_path="",
                    content_type=content_type,
                    extraction_method=extraction_method,
                    hardware_backend="unknown",
                    confidence="low",
                    route="",
                    renamed_to="",
                    rag_indexed=False,
                    status="needs_review",
                    review_reason=error or "No readable text captured.",
                    error=error,
                    local_agent_used=(
                        bool(getattr(extracted, "local_agent_used", False)) if extracted is not None else False
                    ),
                    cloud_used=bool(getattr(extracted, "cloud_used", False)) if extracted is not None else False,
                    escalation_reason=getattr(extracted, "escalation_reason", None) if extracted is not None else None,
                    cloud_provider=getattr(extracted, "cloud_provider", None) if extracted is not None else None,
                    cloud_model=getattr(extracted, "cloud_model", None) if extracted is not None else None,
                )
            )
            continue

        if extracted.needs_llm:
            file_results.append(
                InboxFileResult(
                    source_path=str(source),
                    final_path="",
                    source_card_path="",
                    content_type=content_type,
                    extraction_method=extraction_method,
                    hardware_backend="local",
                    confidence="low",
                    route="",
                    renamed_to="",
                    rag_indexed=False,
                    status="needs_review",
                    review_reason=("Extraction requires a local agent result before routing."),
                    local_agent_used=bool(getattr(extracted, "local_agent_used", False) or extracted.needs_llm),
                    cloud_used=bool(getattr(extracted, "cloud_used", False)),
                    escalation_reason=getattr(extracted, "escalation_reason", None),
                    cloud_provider=getattr(extracted, "cloud_provider", None),
                    cloud_model=getattr(extracted, "cloud_model", None),
                )
            )
            continue

        title = extracted.title or source.stem
        decision = decide_route(
            source_name=source.name,
            title=title,
            body=body,
            content_type=content_type,
        )
        confidence = "medium" if extracted.ocr_applied else "high"
        final_path: Path | None = None
        extracted_artifact: Path | None = None
        actual_decision = decision
        try:
            final_path = _unique_destination_path(vault_dir / decision.route / decision.filename)
            actual_decision = replace(decision, filename=final_path.name)
            extracted_artifact = _write_extracted_artifact(
                vault_dir=vault_dir,
                decision_filename=actual_decision.filename,
                body=body,
                content_type=content_type,
            )
            final_path.parent.mkdir(parents=True, exist_ok=True)
            if not source.exists():
                raise FileNotFoundError(f"Source disappeared before move: {source}")
            shutil.move(str(source), str(final_path))
            files_moved += 1
            card = write_source_card(
                vault_dir=vault_dir,
                title=title,
                body=body,
                decision=actual_decision,
                original_path=str(source),
                final_path=str(final_path),
                extracted_path=str(extracted_artifact),
                extraction_method=extraction_method,
                hardware_backend=getattr(extracted, "hardware_backend", "local"),
                confidence=confidence,
                content_type=content_type,
                escalation_reason=getattr(extracted, "escalation_reason", None),
                cloud_used=bool(getattr(extracted, "cloud_used", False)),
                cloud_provider=getattr(extracted, "cloud_provider", None),
                cloud_model=getattr(extracted, "cloud_model", None),
            )
        except Exception as exc:
            file_results.append(
                InboxFileResult(
                    source_path=str(source),
                    final_path=str(final_path) if final_path is not None else "",
                    source_card_path="",
                    content_type=content_type,
                    extraction_method=extraction_method,
                    hardware_backend=getattr(extracted, "hardware_backend", "local"),
                    confidence="low",
                    route=decision.route,
                    renamed_to=actual_decision.filename,
                    rag_indexed=False,
                    status="failed",
                    route_reason=decision.reason,
                    extracted_path=(str(extracted_artifact) if extracted_artifact is not None else None),
                    local_agent_used=bool(getattr(extracted, "local_agent_used", False) or extracted.needs_llm),
                    cloud_used=bool(getattr(extracted, "cloud_used", False)),
                    escalation_reason=getattr(extracted, "escalation_reason", None),
                    cloud_provider=getattr(extracted, "cloud_provider", None),
                    cloud_model=getattr(extracted, "cloud_model", None),
                    review_reason=str(exc),
                    error=str(exc),
                )
            )
            continue

        file_results.append(
            InboxFileResult(
                source_path=str(source),
                final_path=str(final_path),
                source_card_path=str(card),
                content_type=content_type,
                extraction_method=extraction_method,
                hardware_backend=getattr(extracted, "hardware_backend", "local"),
                confidence=confidence,
                route=actual_decision.route,
                renamed_to=actual_decision.filename,
                rag_indexed=True,
                status="success",
                route_reason=actual_decision.reason,
                extracted_path=str(extracted_artifact),
                local_agent_used=bool(getattr(extracted, "local_agent_used", False) or extracted.needs_llm),
                cloud_used=bool(getattr(extracted, "cloud_used", False)),
                escalation_reason=getattr(extracted, "escalation_reason", None),
                cloud_provider=getattr(extracted, "cloud_provider", None),
                cloud_model=getattr(extracted, "cloud_model", None),
            )
        )

    indexed = sum(1 for result in file_results if result.rag_indexed)
    if indexed:
        browse_index = refresh_notes_browse_index(vault_dir=vault_dir)
        if not browse_index.success:
            file_results = [
                (
                    replace(
                        result,
                        rag_indexed=False,
                        status="needs_review",
                        review_reason=(
                            f"{result.review_reason} Reindex failed: {browse_index.error}"
                            if result.review_reason
                            else f"Reindex failed: {browse_index.error}"
                        ),
                    )
                    if result.rag_indexed
                    else result
                )
                for result in file_results
            ]

    return _save_record(
        store=store,
        folder_id=folder_id,
        started=started,
        policy=policy,
        file_results=file_results,
        files_seen=len(scan.items),
        files_moved=files_moved,
    )
