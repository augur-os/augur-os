from __future__ import annotations

import hashlib
import shutil
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import yaml

from skills.ingest.scripts.inbox_lifecycle import apply_archive_plan
from skills.ingest.scripts.inbox_unified_models import (
    InboxConsumeResult,
    InboxPacket,
    InboxRouteProposal,
    InboxVaultTarget,
    to_dict,
)
from src.lib.ingest.note_index_refresh import refresh_notes_browse_index


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _resolve_inside(root: Path, relative: str) -> Path | None:
    rel = Path(relative)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        return None
    resolved_root = root.resolve()
    resolved = (resolved_root / rel).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        return None
    return resolved


def _is_plain_filename(value: str) -> bool:
    path = Path(value)
    return bool(value) and path.name == value and not path.is_absolute() and value not in {".", ".."}


def _payload_path(packet: InboxPacket) -> Path | None:
    if not packet.payload_paths:
        return None
    packet_dir = Path(packet.packet_dir).resolve()
    payload = _resolve_inside(packet_dir, packet.payload_paths[0])
    if payload is None or not payload.is_file():
        return None
    return payload


def _sidecar_path(final_path: Path) -> Path:
    return final_path.with_name(f"{final_path.stem}.meta.yaml")


def _archive_paths(archive_result: dict[str, object]) -> list[str]:
    moves = archive_result.get("moves")
    if not isinstance(moves, list):
        return []
    archived: list[str] = []
    for move in moves:
        if not isinstance(move, dict):
            continue
        if move.get("status") == "succeeded" and isinstance(move.get("to"), str):
            archived.append(move["to"])
    return archived


def _refused_paths(archive_result: dict[str, object]) -> list[str]:
    moves = archive_result.get("moves")
    if not isinstance(moves, list):
        return []
    refused: list[str] = []
    for move in moves:
        if not isinstance(move, dict):
            continue
        if move.get("status") in {"refused", "would_refuse"} and isinstance(move.get("from"), str):
            refused.append(move["from"])
    return refused


def _write_sidecar(
    *,
    sidecar_path: Path,
    packet: InboxPacket,
    target: InboxVaultTarget,
    proposal: InboxRouteProposal,
    final_path: Path,
    archived_paths: list[str],
) -> None:
    payload = {
        "source_id": packet.source_id,
        "source_type": packet.source_type,
        "source_packet": packet.packet_id,
        "target_vault": target.id,
        "target_domain": proposal.target_domain,
        "target_folder": proposal.target_folder,
        "route_reason": proposal.route_reason,
        "version_group": proposal.version_group,
        "archived_superseded": archived_paths,
        "content_hash": _sha256(final_path),
        "staged_content_hash": packet.content_hash,
        "original_filename": packet.original_filename,
        "final_filename": final_path.name,
        "user_instruction": packet.user_instruction,
        "created_at": packet.created_at,
        "consumed_at": _now_iso(),
    }
    sidecar_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def _mark_packet_consumed(packet: InboxPacket) -> None:
    manifest = Path(packet.packet_dir) / "manifest.yaml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    consumed = replace(packet, status="consumed", failure_state=None)
    manifest.write_text(
        yaml.safe_dump(to_dict(consumed), sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def consume_packet(
    *,
    packet: InboxPacket,
    target: InboxVaultTarget,
    proposal: InboxRouteProposal,
) -> InboxConsumeResult:
    """Move a routed packet payload into docs and record provenance."""
    if proposal.status != "ready":
        return InboxConsumeResult(
            packet_id=packet.packet_id,
            status="needs_input",
            questions=proposal.questions,
            failure_state=proposal.failure_state or "needs_route",
        )
    if proposal.packet_id != packet.packet_id or proposal.target_vault != target.id:
        return InboxConsumeResult(packet_id=packet.packet_id, status="failed", failure_state="blocked_permission")
    if not _is_plain_filename(proposal.final_filename):
        return InboxConsumeResult(packet_id=packet.packet_id, status="failed", failure_state="blocked_permission")

    docs_root = Path(target.docs_root).resolve()
    target_folder = _resolve_inside(docs_root, proposal.target_folder) if proposal.target_folder else docs_root
    if target_folder is None:
        return InboxConsumeResult(packet_id=packet.packet_id, status="failed", failure_state="blocked_permission")

    final_path = _resolve_inside(target_folder, proposal.final_filename)
    if final_path is None:
        return InboxConsumeResult(packet_id=packet.packet_id, status="failed", failure_state="blocked_permission")
    try:
        final_path.relative_to(docs_root)
    except ValueError:
        return InboxConsumeResult(packet_id=packet.packet_id, status="failed", failure_state="blocked_permission")

    payload = _payload_path(packet)
    if payload is None:
        return InboxConsumeResult(packet_id=packet.packet_id, status="needs_input", failure_state="pending_content")
    if proposal.archive_plan.ask:
        return InboxConsumeResult(
            packet_id=packet.packet_id,
            status="needs_input",
            questions=[move.reason for move in proposal.archive_plan.ask],
            refused_paths=[move.relative_path for move in proposal.archive_plan.refused],
            failure_state="needs_version_choice",
        )
    if final_path.exists():
        folder_label = proposal.target_folder or "."
        return InboxConsumeResult(
            packet_id=packet.packet_id,
            status="needs_input",
            questions=[
                f"{proposal.final_filename} already exists in {folder_label}. "
                "Choose whether to archive, rename, or skip it."
            ],
            failure_state="needs_version_choice",
        )

    archive_result = apply_archive_plan(docs_root, proposal.archive_plan, dry_run=False)
    archived_paths = _archive_paths(archive_result)
    refused_paths = _refused_paths(archive_result) + [move.relative_path for move in proposal.archive_plan.refused]
    questions = [move.reason for move in proposal.archive_plan.ask]

    target_folder.mkdir(parents=True, exist_ok=True)
    shutil.move(str(payload), str(final_path))
    sidecar = _sidecar_path(final_path)
    _write_sidecar(
        sidecar_path=sidecar,
        packet=packet,
        target=target,
        proposal=proposal,
        final_path=final_path,
        archived_paths=archived_paths,
    )
    _mark_packet_consumed(packet)

    browse_index = refresh_notes_browse_index(vault_dir=Path(target.vault_root))
    if not browse_index.success:
        return InboxConsumeResult(
            packet_id=packet.packet_id,
            status="needs_input",
            final_paths=[str(final_path)],
            sidecar_paths=[str(sidecar)],
            archived_paths=archived_paths,
            refused_paths=refused_paths,
            questions=questions + [f"Refresh Browse index failed: {getattr(browse_index, 'error', '')}".strip()],
            index_refreshed=False,
            failure_state="failed_index",
        )

    return InboxConsumeResult(
        packet_id=packet.packet_id,
        status="success",
        final_paths=[str(final_path)],
        sidecar_paths=[str(sidecar)],
        archived_paths=archived_paths,
        refused_paths=refused_paths,
        questions=questions,
        index_refreshed=True,
        failure_state=None,
    )


__all__ = ["consume_packet"]
