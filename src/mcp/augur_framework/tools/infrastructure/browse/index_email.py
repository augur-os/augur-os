"""Email-drop inbox browse entries."""

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from src.config.paths import get_documents_dir, get_runtime_dir

from .index_common import _BROWSE_LIMIT


def _email_drop_source_root(source_path: Path) -> str:
    default_email_dir = get_documents_dir() / "inbox" / "email"
    try:
        if source_path.expanduser().resolve(strict=False) == default_email_dir.expanduser().resolve(strict=False):
            return "documents-inbox-email"
    except OSError:
        pass
    return "email-drop"


def _email_drop_sources_for_browse() -> list[object]:
    try:
        from skills.ingest.scripts.email_drop_models import EmailDropSource
        from skills.ingest.scripts.email_drop_store import EmailDropStore
    except Exception:
        return []

    store = EmailDropStore(get_runtime_dir() / "brain" / "inbox")
    sources = [source for source in store.list_sources() if source.enabled]
    default_path = get_documents_dir() / "inbox" / "email"
    if not default_path.is_dir():
        return sources

    default_resolved = default_path.expanduser().resolve(strict=False)
    for source in sources:
        try:
            source_resolved = Path(source.path).expanduser().resolve(strict=False)
        except OSError:
            continue
        if source_resolved == default_resolved:
            return sources

    return [
        *sources,
        EmailDropSource(
            id="mail-drop",
            name="Mail Drop",
            path=str(default_path),
        ),
    ]


def _packet_browse_source_path(packet: object, fallback: Path) -> Path:
    raw = getattr(packet, "container_path", None) or getattr(packet, "source_path", None) or fallback
    return Path(str(raw))


def _packet_entry_id(source_id: str, packet: object, browse_source_path: Path) -> str:
    identity = "|".join(
        [
            source_id,
            str(browse_source_path),
            str(getattr(packet, "contained_path", "") or ""),
            str(getattr(packet, "ordinal", 0)),
            str(getattr(packet, "message_id", "") or ""),
        ]
    )
    digest = sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"email-drop:{source_id}:{digest}"


def _email_packet_excerpt(packet: object) -> str:
    body = str(getattr(packet, "body_text", "") or getattr(packet, "body_html", "") or "")
    normalized = " ".join(body.split())
    if len(normalized) > 180:
        return f"{normalized[:177]}..."
    return normalized


def _email_packet_description(packet: object) -> str:
    pieces = [
        str(getattr(packet, "from_address", "") or "").strip(),
        str(getattr(packet, "date", "") or "").strip(),
        _email_packet_excerpt(packet),
    ]
    return " · ".join(piece for piece in pieces if piece)


def _email_drop_inbox_entries() -> list[dict]:
    try:
        from skills.ingest.scripts.email_artifact_parser import parse_artifact
        from skills.ingest.scripts.email_drop_consume import _email_artifacts
    except Exception:
        return []

    entries: list[dict] = []
    indexed_at = datetime.now(timezone.utc).isoformat()
    for source in _email_drop_sources_for_browse():
        source_path = Path(str(getattr(source, "path", ""))).expanduser()
        source_root = _email_drop_source_root(source_path)
        artifacts = _email_artifacts(
            source_path,
            order=str(getattr(source, "batch_order", "newest_first") or "newest_first"),
        )
        for artifact in artifacts:
            if len(entries) >= _BROWSE_LIMIT:
                return entries
            try:
                parsed = parse_artifact(artifact)
            except Exception:
                continue
            for packet in parsed.packets:
                if len(entries) >= _BROWSE_LIMIT:
                    return entries
                packet_source = _packet_browse_source_path(packet, artifact)
                try:
                    modified = datetime.fromtimestamp(
                        packet_source.stat().st_mtime,
                        tz=timezone.utc,
                    ).isoformat()
                except OSError:
                    modified = indexed_at
                links = [str(link) for link in getattr(packet, "links", []) if str(link)]
                attachments = list(getattr(packet, "attachments", []) or [])
                attachment_names = [
                    str(getattr(attachment, "filename", "") or "")
                    for attachment in attachments
                    if str(getattr(attachment, "filename", "") or "")
                ]
                title = str(getattr(packet, "subject", "") or "").strip() or packet_source.stem
                entry = {
                    "id": _packet_entry_id(
                        str(getattr(source, "id", "mail-drop")),
                        packet,
                        packet_source,
                    ),
                    "type": "email-drop",
                    "hub": "workspace",
                    "name": packet_source.stem,
                    "title": title,
                    "description": _email_packet_description(packet),
                    "source_path": str(packet_source),
                    "tags": ["inbox", "email", "mail-drop"],
                    "journey_category": "inbox",
                    "source_root": source_root,
                    "promotion_state": "packet",
                    "status": "pending",
                    "format": str(getattr(packet, "artifact_type", "") or packet_source.suffix.lstrip(".") or "email"),
                    "source_id": str(getattr(source, "id", "")),
                    "source_name": str(getattr(source, "name", "")),
                    "email_source_path": str(source_path),
                    "email_from": str(getattr(packet, "from_address", "") or ""),
                    "email_to": ",".join(str(item) for item in getattr(packet, "to_addresses", []) if str(item)),
                    "email_cc": ",".join(str(item) for item in getattr(packet, "cc_addresses", []) if str(item)),
                    "email_date": str(getattr(packet, "date", "") or ""),
                    "message_id": str(getattr(packet, "message_id", "") or ""),
                    "artifact_type": str(getattr(packet, "artifact_type", "") or ""),
                    "container_path": str(getattr(packet, "container_path", "") or ""),
                    "contained_path": str(getattr(packet, "contained_path", "") or ""),
                    "ordinal": str(getattr(packet, "ordinal", 0)),
                    "metadata_partial": str(bool(getattr(packet, "metadata_partial", False))).lower(),
                    "link_count": str(len(links)),
                    "links": ",".join(links),
                    "attachment_count": str(len(attachments)),
                    "attachment_names": ",".join(attachment_names),
                    "modified": modified,
                    "indexed_at": indexed_at,
                }
                entries.append(entry)
    return entries
