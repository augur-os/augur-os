"""Private packet-routing helper functions for the inbox MCP layer.

These helpers are an implementation detail of ``inbox_tools.py``. They are
extracted here solely to keep ``inbox_tools.py`` under the 800-line threshold
while carrying the genuine inbox-tools logic intact. They are NOT part of the
public API of this package and may be moved or renamed between phases.
"""
from __future__ import annotations

import yaml
from dataclasses import replace
from pathlib import Path
from typing import Any

from skills.ingest.scripts.inbox_lifecycle import plan_version_archives
from skills.ingest.scripts.inbox_packet_routing import propose_packet_route
from skills.ingest.scripts.inbox_registry import load_inbox_registry
from src.lib.ingest.inbox_store import InboxStore
from skills.ingest.scripts.inbox_unified_models import (
    InboxPacket,
    to_dict as unified_to_dict,
)

ACTIVE_PACKET_STATUSES = {"pending_content", "staged"}
MAX_LATEST_RUNS = 3
MAX_LATEST_RUN_FILE_RESULTS = 10


def _latest_run_payloads(store: InboxStore) -> list[dict[str, Any]]:
    return store.list_run_payloads(
        limit=MAX_LATEST_RUNS,
        file_results_limit=MAX_LATEST_RUN_FILE_RESULTS,
    )


def _read_packet_manifest(path: Path) -> InboxPacket | None:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return InboxPacket(**payload)
    except TypeError:
        return None


def _has_staged_payload(packet: InboxPacket) -> bool:
    if not packet.payload_paths:
        return False
    packet_dir = Path(packet.packet_dir).resolve()
    for payload in packet.payload_paths:
        rel = Path(payload)
        if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
            continue
        resolved = (packet_dir / rel).resolve()
        try:
            resolved.relative_to(packet_dir)
        except ValueError:
            continue
        if resolved.is_file():
            return True
    return False


def _iter_unified_packets() -> list[InboxPacket]:
    registry = load_inbox_registry()
    packets: list[InboxPacket] = []
    for source in registry.sources:
        drop_root = Path(source.drop_root)
        if not drop_root.is_dir():
            continue
        for manifest in sorted(drop_root.glob("*/manifest.yaml")):
            packet = _read_packet_manifest(manifest)
            if packet is not None:
                if packet.status not in ACTIVE_PACKET_STATUSES:
                    continue
                if packet.status == "staged" and not _has_staged_payload(packet):
                    continue
                packets.append(packet)
    return sorted(
        packets, key=lambda packet: (packet.created_at, packet.packet_id), reverse=True
    )


def _find_unified_packet(packet_id: str) -> InboxPacket:
    for packet in _iter_unified_packets():
        if packet.packet_id == packet_id:
            return packet
    raise KeyError(f"Inbox packet not found: {packet_id}")


def _proposal_for_packet(packet: InboxPacket):
    registry = load_inbox_registry()
    target_id = packet.target_vault
    if not target_id:
        target_id = registry.source_by_id(packet.source_id).default_target_vault
    target = registry.vault_by_id(target_id)
    proposal = propose_packet_route(packet=packet, target=target)
    if proposal.status == "ready":
        archive_plan = plan_version_archives(
            docs_root=Path(target.docs_root),
            target_folder=proposal.target_folder,
            version_group=proposal.version_group,
            final_filename=proposal.final_filename,
        )
        proposal = replace(proposal, archive_plan=archive_plan)
    return target, proposal


def _routing_queue(limit: int = 50) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for packet in _iter_unified_packets()[:limit]:
        try:
            _, proposal = _proposal_for_packet(packet)
            status = proposal.status
            failure_state = proposal.failure_state
            questions = proposal.questions
        except Exception as exc:
            status = "failed"
            failure_state = "needs_route"
            questions = [str(exc)]
        row = unified_to_dict(packet)
        row.update(
            {
                "status": status,
                "failure_state": failure_state,
                "questions": questions,
            }
        )
        rows.append(row)
    return rows


def _latest_unified_runs(limit: int = 20) -> list[dict[str, Any]]:
    registry = load_inbox_registry()
    rows: list[dict[str, Any]] = []
    for target in registry.vaults:
        docs_root = Path(target.docs_root)
        if not docs_root.is_dir():
            continue
        for sidecar in docs_root.rglob("*.meta.yaml"):
            if "inbox" in sidecar.relative_to(docs_root).parts:
                continue
            try:
                payload = yaml.safe_load(sidecar.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                continue
            if not isinstance(payload, dict) or not payload.get("source_packet"):
                continue
            archived = payload.get("archived_superseded") or []
            rows.append(
                {
                    "id": str(payload.get("source_packet") or sidecar.stem),
                    "status": "success",
                    "source_id": str(payload.get("source_id") or ""),
                    "moved": 1,
                    "archived": len(archived) if isinstance(archived, list) else 0,
                    "questions": 0,
                    "target_vault": target.id,
                    "sidecar_path": str(sidecar),
                    "consumed_at": str(payload.get("consumed_at") or ""),
                }
            )
    return sorted(rows, key=lambda item: item.get("consumed_at") or "", reverse=True)[
        :limit
    ]


def _unified_overview_payload() -> dict[str, Any]:
    registry = load_inbox_registry()
    return {
        "source_lanes": unified_to_dict(registry.sources),
        "vault_targets": unified_to_dict(registry.vaults),
        "discovered_vaults": unified_to_dict(registry.candidates),
        "routing_queue": _routing_queue(),
        "latest_unified_runs": _latest_unified_runs(limit=MAX_LATEST_RUNS),
    }


def _packet_payload(packet: Any) -> dict[str, Any]:
    payload = unified_to_dict(packet)
    if isinstance(payload, dict):
        return payload
    return {
        "packet_id": getattr(packet, "packet_id", ""),
        "packet_dir": getattr(packet, "packet_dir", ""),
        "status": getattr(packet, "status", ""),
        "failure_state": getattr(packet, "failure_state", None),
    }
