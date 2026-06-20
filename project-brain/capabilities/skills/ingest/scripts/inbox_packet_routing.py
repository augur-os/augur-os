from __future__ import annotations

import re
from pathlib import Path

from skills.ingest.scripts.inbox_unified_models import (
    InboxArchivePlan,
    InboxPacket,
    InboxRouteProposal,
    InboxVaultTarget,
)


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_VERSION_SUFFIX_RE = re.compile(r"([_\-\s])v\d+$", re.IGNORECASE)
_LABEL_SUFFIX_RE = re.compile(r"([_\-\s])(final|draft)$", re.IGNORECASE)


def _tokens(value: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(value.lower()) if len(token) > 1}


def _safe_payload_path(packet_dir: Path, payload: str) -> Path | None:
    rel = Path(payload)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        return None
    resolved_packet_dir = packet_dir.resolve()
    resolved_payload = (resolved_packet_dir / rel).resolve()
    try:
        resolved_payload.relative_to(resolved_packet_dir)
    except ValueError:
        return None
    if not resolved_payload.is_file():
        return None
    return resolved_payload


def _derive_version_group(filename: str) -> str:
    stem = Path(filename).stem
    previous = None
    current = stem
    while previous != current:
        previous = current
        current = _LABEL_SUFFIX_RE.sub("", current)
        current = _VERSION_SUFFIX_RE.sub("", current)
    slug = re.sub(r"[^a-z0-9]+", "-", current.lower()).strip("-")
    return slug or re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-") or "artifact"


def _relative_folder(path: Path, docs_root: Path) -> str:
    rel = path.relative_to(docs_root)
    return "" if rel == Path(".") else rel.as_posix()


def _best_folder(docs_root: Path, signal_tokens: set[str]) -> tuple[str, str] | None:
    scores: dict[str, tuple[int, int]] = {}
    for candidate in docs_root.rglob("*"):
        if not candidate.is_file():
            continue
        rel_parts = candidate.relative_to(docs_root).parts
        if ".archive" in rel_parts or "inbox" in rel_parts:
            continue
        overlap = len(signal_tokens & _tokens(candidate.stem))
        if overlap < 2:
            continue
        folder = _relative_folder(candidate.parent, docs_root)
        current_overlap, current_count = scores.get(folder, (0, 0))
        scores[folder] = (max(current_overlap, overlap), current_count + 1)

    if not scores:
        return None
    ordered = sorted(scores.items(), key=lambda item: (item[1][0], item[1][1], item[0]), reverse=True)
    best_folder_name, best_score = ordered[0]
    if len(ordered) > 1 and ordered[1][1][0] == best_score[0]:
        return None
    return best_folder_name, f"matched existing folder by {best_score[0]} shared tokens"


def _needs_input(
    *,
    packet: InboxPacket,
    target: InboxVaultTarget,
    filename: str,
    failure_state: str,
    question: str,
) -> InboxRouteProposal:
    return InboxRouteProposal(
        packet_id=packet.packet_id,
        target_vault=target.id,
        target_domain=packet.target_domain or "docs",
        target_folder="",
        final_filename=filename,
        route_reason="",
        version_group=_derive_version_group(filename or packet.title or "artifact"),
        status="needs_input",
        failure_state=failure_state,  # type: ignore[arg-type]
        questions=[question],
        archive_plan=InboxArchivePlan(),
    )


def propose_packet_route(packet: InboxPacket, target: InboxVaultTarget) -> InboxRouteProposal:
    """Propose a deterministic docs route for a staged packet payload."""
    filename = packet.payload_paths[0] if packet.payload_paths else packet.original_filename
    display_name = Path(filename).name if filename else packet.title or "payload"
    packet_dir = Path(packet.packet_dir)
    if not packet.payload_paths:
        return _needs_input(
            packet=packet,
            target=target,
            filename=display_name,
            failure_state="pending_content",
            question=f"Attach or drop the payload before routing {packet.title or display_name}.",
        )

    payload = _safe_payload_path(packet_dir, packet.payload_paths[0])
    if payload is None:
        return _needs_input(
            packet=packet,
            target=target,
            filename=display_name,
            failure_state="pending_content",
            question=f"Attach or drop the payload before routing {packet.title or display_name}.",
        )

    final_filename = payload.name
    signal = _tokens(" ".join([packet.title, packet.original_filename, final_filename]))
    docs_root = Path(target.docs_root).resolve()
    match = _best_folder(docs_root, signal) if docs_root.exists() else None
    if match is None:
        return _needs_input(
            packet=packet,
            target=target,
            filename=final_filename,
            failure_state="needs_route",
            question=f"Choose the final folder for {final_filename}.",
        )

    target_folder, reason = match
    return InboxRouteProposal(
        packet_id=packet.packet_id,
        target_vault=target.id,
        target_domain=packet.target_domain or "docs",
        target_folder=target_folder,
        final_filename=final_filename,
        route_reason=reason,
        version_group=_derive_version_group(final_filename),
        status="ready",
        failure_state=None,
        archive_plan=InboxArchivePlan(),
    )


__all__ = ["propose_packet_route"]
