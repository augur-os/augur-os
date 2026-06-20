from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from skills.ingest.scripts.inbox_registry import load_inbox_registry
from skills.ingest.scripts.inbox_unified_models import InboxPacket, InboxSourceLane, to_dict


_RESERVED_PACKET_FILENAMES = {"manifest.yaml", "manifest.yml", ".meta.yaml", ".meta.yml"}


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80].strip("-") or "packet"


def _now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_filename(value: str) -> str:
    basename = re.split(r"[\\/]+", value.strip())[-1]
    if not basename or basename in {".", ".."}:
        return "payload.md"

    parts = [part for part in basename.lower().split(".") if part]
    safe_name = ".".join(_slug(part) for part in parts) or "payload.md"
    if safe_name in _RESERVED_PACKET_FILENAMES:
        return f"payload-{safe_name}"
    return safe_name


def _write_manifest(packet: InboxPacket) -> None:
    path = Path(packet.packet_dir) / "manifest.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(to_dict(packet), sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def _create_packet_dir(source: InboxSourceLane, title: str) -> tuple[str, Path]:
    base_id = f"{_now_compact()}-{_slug(title)}"
    drop_root = Path(source.drop_root)
    drop_root.mkdir(parents=True, exist_ok=True)
    for index in range(1, 1000):
        packet_id = base_id if index == 1 else f"{base_id}-{index}"
        directory = drop_root / packet_id
        try:
            directory.mkdir()
        except FileExistsError:
            continue
        return packet_id, directory
    raise FileExistsError(f"Could not allocate unique inbox packet directory for {base_id}")


def stage_packet(
    *,
    source_id: str,
    title: str,
    filename: str,
    content: bytes,
    user_instruction: str,
    content_type: str = "",
    capture_mode: str = "mcp_content",
    conversation_hint: str = "",
    target_vault: str = "",
    target_domain: str = "docs",
) -> InboxPacket:
    registry = load_inbox_registry()
    source = registry.source_by_id(source_id)
    packet_id, directory = _create_packet_dir(source, title)

    safe_name = _safe_filename(filename)
    payload_path = directory / safe_name
    payload_path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()

    packet = InboxPacket(
        packet_id=packet_id,
        source_id=source_id,
        source_type=source.type,
        capture_mode=capture_mode,
        packet_dir=str(directory),
        title=title,
        status="staged",
        target_vault=target_vault or source.default_target_vault,
        target_domain=target_domain,
        original_filename=safe_name,
        content_type=content_type,
        content_hash=f"sha256:{digest}",
        conversation_hint=conversation_hint,
        user_instruction=user_instruction,
        created_at=_now_iso(),
        payload_paths=[safe_name],
    )
    _write_manifest(packet)
    return packet


def create_pending_packet(
    *,
    source_id: str,
    title: str,
    user_instruction: str,
    conversation_hint: str = "",
    target_vault: str = "",
    target_domain: str = "docs",
) -> InboxPacket:
    registry = load_inbox_registry()
    source = registry.source_by_id(source_id)
    packet_id, directory = _create_packet_dir(source, title)

    packet = InboxPacket(
        packet_id=packet_id,
        source_id=source_id,
        source_type=source.type,
        capture_mode="pending_drop",
        packet_dir=str(directory),
        title=title,
        status="pending_content",
        target_vault=target_vault or source.default_target_vault,
        target_domain=target_domain,
        conversation_hint=conversation_hint,
        user_instruction=user_instruction,
        created_at=_now_iso(),
        failure_state="pending_content",
    )
    _write_manifest(packet)
    return packet
