from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import get_runtime_dir, get_vault_dir

from skills.ingest.scripts.email_artifact_parser import classify_artifact, parse_artifact
from skills.ingest.scripts.email_drop_models import (
    EmailDropCounts,
    EmailDropPacket,
    EmailDropRunRecord,
    EmailDropSkipped,
)
from skills.ingest.scripts.email_drop_store import EmailDropStore
from skills.ingest.scripts.email_link_classifier import classify_links
from src.lib.ingest.inbox_routing import decide_route
from src.lib.ingest.note_index_refresh import refresh_notes_browse_index
from src.lib.ingest.source_cards import write_source_card

IGNORED_SOURCE_DIRS = {"processed", "failed", "quarantine", ".staging"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def scan_email_drop_source(
    *,
    store: EmailDropStore,
    source_id: str,
) -> EmailDropCounts:
    source = store.get_source(source_id)
    counts = _scan_path(Path(source.path))
    health_state = "ok" if counts.failed == 0 else "warning"
    health_error = None
    if counts.failed:
        health_error = f"{counts.failed} email artifact(s) could not be fully parsed."
    store.update_source_state(
        source_id,
        counts=counts,
        last_scan_at=_now(),
        health_state=health_state,
        health_error=health_error,
    )
    return counts


def consume_email_drop_source(
    *,
    store: EmailDropStore,
    source_id: str,
    limit: int | None = None,
) -> EmailDropRunRecord:
    source = store.get_source(source_id)
    started = _now()
    run_id = f"email_run_{uuid.uuid4().hex[:12]}"
    artifacts = _email_artifacts(Path(source.path), order=source.batch_order)
    batch_limit = max(1, limit or source.batch_limit or 5)
    selected = artifacts[:batch_limit]
    staging_dir = store.root / ".staging" / run_id
    packets: list[EmailDropPacket] = []
    skipped: list[EmailDropSkipped] = []
    errors: list[str] = []
    files_moved = 0
    successful_artifacts: list[Path] = []

    for artifact in selected:
        parsed = parse_artifact(artifact, staging_dir=staging_dir)
        artifact_packets = [_prepare_packet(packet) for packet in parsed.packets]
        artifact_skipped = parsed.skipped
        artifact_errors = parsed.errors
        packets.extend(artifact_packets)
        skipped.extend(artifact_skipped)
        errors.extend(artifact_errors)
        if artifact_packets and not artifact_skipped and not artifact_errors:
            successful_artifacts.append(artifact)

    if packets and not skipped and not errors:
        for artifact in successful_artifacts:
            if _move_after_success(artifact, source.after_success_target):
                files_moved += 1

    vault_dir = get_vault_dir()
    wiki_update_marked = _write_packet_source_cards(packets, vault_dir=vault_dir)
    if wiki_update_marked:
        _mark_wiki_update_needed()
        browse_index = refresh_notes_browse_index(vault_dir=vault_dir)
        if not browse_index.success:
            errors.append(f"reindex_failed: {browse_index.error}")

    status = _run_status(packets, skipped, errors)
    record = EmailDropRunRecord(
        id=run_id,
        source_id=source_id,
        started_at=started,
        completed_at=_now(),
        status=status,
        artifacts_seen=len(selected),
        files_moved=files_moved,
        packets_created=len(packets),
        archives_seen=sum(
            1 for artifact in selected if classify_artifact(artifact).category == "archive"
        ),
        degraded_files_seen=sum(
            1 for artifact in selected if classify_artifact(artifact).category == "degraded"
        ),
        files_skipped=len(skipped),
        files_failed=len(errors),
        attachments_seen=sum(len(packet.attachments) for packet in packets),
        links_seen=sum(len(packet.links) for packet in packets),
        wiki_update_marked=wiki_update_marked,
        packets=packets,
        skipped=skipped,
        errors=errors,
    )
    store.save_run(record)
    counts = _scan_path(Path(source.path))
    store.update_source_state(
        source_id,
        counts=counts,
        last_consume_run_id=record.id,
        last_run_status=record.status,
        health_state="ok" if record.status == "success" else "warning",
        health_error="; ".join(errors[:3]) if errors else None,
    )
    return record


def _scan_path(path: Path) -> EmailDropCounts:
    counts = EmailDropCounts()
    if not path.expanduser().is_dir():
        counts.failed = 1
        return counts
    for artifact in _email_artifacts(path):
        counts.pending_files += 1
        info = classify_artifact(artifact)
        if info.category == "email_native":
            counts.email_native += 1
        elif info.category == "archive":
            counts.archives += 1
        elif info.category == "degraded":
            counts.degraded += 1
        else:
            counts.unsupported += 1
            continue
        parsed = parse_artifact(artifact)
        counts.failed += len(parsed.errors)
        counts.contained_messages += len(parsed.packets)
        counts.attachments += sum(len(packet.attachments) for packet in parsed.packets)
        counts.article_links += sum(
            len(classify_links(packet.body_text, packet.body_html).article_resource_urls)
            for packet in parsed.packets
        )
    return counts


def _email_artifacts(path: Path, *, order: str = "newest_first") -> list[Path]:
    root = path.expanduser().resolve(strict=False)
    if not root.is_dir():
        return []
    artifacts = [
        item
        for item in root.iterdir()
        if not item.is_symlink()
        and item.name not in IGNORED_SOURCE_DIRS
        and (item.is_file() or (item.is_dir() and item.name.lower().endswith(".mbox")))
    ]
    reverse = order != "oldest_first"
    return sorted(
        artifacts,
        key=lambda item: item.stat().st_mtime if item.exists() else 0,
        reverse=reverse,
    )


def _prepare_packet(packet: EmailDropPacket) -> EmailDropPacket:
    classified = classify_links(packet.body_text, packet.body_html, *packet.links)
    packet.links = [
        *classified.article_resource_urls,
        *classified.downloadable_file_urls,
    ]
    return packet


def _write_packet_source_cards(
    packets: list[EmailDropPacket],
    *,
    vault_dir: Path,
) -> bool:
    wrote_any = False
    for packet in packets:
        body = (packet.body_text or packet.body_html or "").strip()
        if not body and not packet.links and not packet.attachments:
            continue
        title = packet.subject or Path(packet.source_path).stem
        decision = decide_route(
            source_name=Path(packet.source_path).name,
            title=title,
            body=_packet_body_for_routing(packet),
            content_type="email",
        )
        extracted_artifact = _write_packet_body_artifact(
            vault_dir=vault_dir,
            decision_filename=decision.filename,
            body=body,
        )
        _persist_packet_attachments(
            vault_dir=vault_dir,
            decision_filename=decision.filename,
            packet=packet,
        )
        card_body = _packet_source_card_body(packet, body)
        write_source_card(
            vault_dir=vault_dir,
            title=title,
            body=card_body,
            decision=decision,
            original_path=packet.source_path,
            final_path=None,
            extracted_path=str(extracted_artifact) if extracted_artifact else None,
            extraction_method=f"email-drop:{packet.artifact_type}",
            hardware_backend="local",
            confidence="medium" if packet.metadata_partial else "high",
            content_type="email",
        )
        wrote_any = True
    return wrote_any


def _packet_body_for_routing(packet: EmailDropPacket) -> str:
    return "\n\n".join(
        item
        for item in (
            packet.body_text or packet.body_html or "",
            "\n".join(packet.links),
            "\n".join(attachment.filename for attachment in packet.attachments),
        )
        if item
    )


def _packet_source_card_body(packet: EmailDropPacket, body: str) -> str:
    link_section = "\n".join(f"- {link}" for link in packet.links)
    attachment_section = "\n".join(
        f"- {attachment.filename} ({attachment.content_type or 'unknown'}, "
        f"{attachment.size} bytes)"
        + (f" -> `{attachment.final_path}`" if attachment.final_path else "")
        for attachment in packet.attachments
    )
    return "\n\n".join(
        section
        for section in (
            body,
            "## Links\n\n" + link_section if link_section else "",
            "## Attachments\n\n" + attachment_section if attachment_section else "",
        )
        if section
    )


def _write_packet_body_artifact(
    *,
    vault_dir: Path,
    decision_filename: str,
    body: str,
) -> Path | None:
    if not body:
        return None
    target = _unique_path(
        vault_dir
        / "sources"
        / "extracted"
        / f"{Path(decision_filename).stem}.email.md"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def _persist_packet_attachments(
    *,
    vault_dir: Path,
    decision_filename: str,
    packet: EmailDropPacket,
) -> None:
    if not packet.attachments:
        return
    target_dir = vault_dir / "sources" / "attachments" / Path(decision_filename).stem
    target_dir.mkdir(parents=True, exist_ok=True)
    for index, attachment in enumerate(packet.attachments, start=1):
        if not attachment.staged_path:
            continue
        staged = Path(attachment.staged_path)
        if not staged.exists() or not staged.is_file():
            continue
        filename = _safe_filename(attachment.filename) or f"attachment-{index}"
        target = _unique_path(target_dir / filename)
        shutil.copy2(staged, target)
        attachment.final_path = str(target)


def _safe_filename(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in "._-" else "-"
        for character in Path(value).name
    ).strip(".-")


def _mark_wiki_update_needed() -> None:
    flag_path = get_runtime_dir() / "wiki" / "needs-update.flag"
    flag_path.parent.mkdir(parents=True, exist_ok=True)
    flag_path.write_text(_now() + "\n", encoding="utf-8")


def _move_after_success(artifact: Path, target_name: str) -> bool:
    if not artifact.exists():
        return False
    target_dir = artifact.parent / (target_name or "processed")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = _unique_path(target_dir / artifact.name)
    shutil.move(str(artifact), str(target))
    return True


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 10_000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find available path for {path}")


def _run_status(
    packets: list[EmailDropPacket],
    skipped: list[EmailDropSkipped],
    errors: list[str],
) -> str:
    if packets and not skipped and not errors:
        return "success"
    if packets:
        return "partial_success"
    return "failed"
