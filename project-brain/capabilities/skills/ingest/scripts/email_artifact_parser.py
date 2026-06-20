from __future__ import annotations

import mailbox
import re
import tarfile
import tempfile
import zipfile
from email import policy
from email.message import Message
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path, PurePosixPath

from skills.ingest.scripts.email_drop_models import (
    EmailArtifactInfo,
    EmailArtifactParseResult,
    EmailDropAttachment,
    EmailDropPacket,
    EmailDropSkipped,
)


EMAIL_NATIVE_SUFFIXES = {
    ".eml": "eml",
    ".msg": "msg",
    ".oft": "oft",
    ".mbox": "mbox",
    ".pst": "pst",
}
ARCHIVE_SUFFIXES = {
    ".zip": "zip",
    ".tgz": "tgz",
    ".tar": "tar",
    ".tar.gz": "tar.gz",
}
DEGRADED_SUFFIXES = {
    ".pdf": "pdf",
    ".txt": "txt",
    ".html": "html",
    ".htm": "htm",
    ".mht": "mht",
    ".mhtml": "mhtml",
}
DEPENDENCY_ISOLATED_TYPES = {"msg", "oft", "pst"}
LINK_RE = re.compile(r"https?://[^\s<>\"]+")


def classify_artifact(path: Path | str) -> EmailArtifactInfo:
    resolved = Path(path)
    suffix = _artifact_suffix(resolved)
    if resolved.is_dir() and suffix == ".mbox":
        return EmailArtifactInfo(
            path=str(resolved),
            category="email_native",
            artifact_type="apple_mbox_bundle",
            supported=True,
        )
    if suffix in EMAIL_NATIVE_SUFFIXES:
        return EmailArtifactInfo(
            path=str(resolved),
            category="email_native",
            artifact_type=EMAIL_NATIVE_SUFFIXES[suffix],
            supported=True,
        )
    if suffix in ARCHIVE_SUFFIXES:
        return EmailArtifactInfo(
            path=str(resolved),
            category="archive",
            artifact_type=ARCHIVE_SUFFIXES[suffix],
            supported=True,
        )
    if suffix in DEGRADED_SUFFIXES:
        return EmailArtifactInfo(
            path=str(resolved),
            category="degraded",
            artifact_type=DEGRADED_SUFFIXES[suffix],
            supported=True,
        )
    return EmailArtifactInfo(
        path=str(resolved),
        category="unsupported",
        artifact_type=suffix.lstrip(".") or "unknown",
        supported=False,
    )


def parse_artifact(
    path: Path | str,
    *,
    staging_dir: Path | str | None = None,
    max_entries: int = 1000,
    max_entry_bytes: int = 50 * 1024 * 1024,
) -> EmailArtifactParseResult:
    artifact_path = Path(path)
    info = classify_artifact(artifact_path)
    result = EmailArtifactParseResult(
        source_path=str(artifact_path),
        artifact_type=info.artifact_type,
    )
    if not info.supported:
        result.skipped.append(
            EmailDropSkipped(
                source_path=str(artifact_path),
                reason="unsupported",
                artifact_type=info.artifact_type,
            )
        )
        return result
    if info.artifact_type == "eml":
        result.packets.append(
            _packet_from_eml(
                artifact_path,
                "eml",
                staging_dir=Path(staging_dir) if staging_dir is not None else None,
            )
        )
        return result
    if info.artifact_type == "mbox":
        result.packets.extend(
            _packets_from_mbox(
                artifact_path,
                "mbox",
                staging_dir=Path(staging_dir) if staging_dir is not None else None,
            )
        )
        return result
    if info.artifact_type == "apple_mbox_bundle":
        result.packets.extend(
            _packets_from_apple_bundle(
                artifact_path,
                staging_dir=Path(staging_dir) if staging_dir is not None else None,
            )
        )
        return result
    if info.artifact_type in DEPENDENCY_ISOLATED_TYPES:
        result.skipped.append(
            EmailDropSkipped(
                source_path=str(artifact_path),
                reason="parser_unavailable",
                artifact_type=info.artifact_type,
            )
        )
        return result
    if info.category == "archive":
        return _parse_archive(
            artifact_path,
            info.artifact_type,
            staging_dir=Path(staging_dir) if staging_dir is not None else None,
            max_entries=max_entries,
            max_entry_bytes=max_entry_bytes,
        )
    if info.category == "degraded":
        result.packets.append(_packet_from_degraded(artifact_path, info.artifact_type))
        return result
    return result


def _artifact_suffix(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".tar.gz"):
        return ".tar.gz"
    return path.suffix.lower()


def _packet_from_eml(
    path: Path,
    artifact_type: str,
    *,
    staging_dir: Path | None = None,
    container_path: Path | None = None,
    contained_path: str | None = None,
    ordinal: int = 0,
) -> EmailDropPacket:
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    return _packet_from_message(
        message,
        source_path=path,
        artifact_type=artifact_type,
        staging_dir=staging_dir,
        container_path=container_path,
        contained_path=contained_path,
        ordinal=ordinal,
    )


def _packets_from_mbox(
    path: Path,
    artifact_type: str,
    *,
    staging_dir: Path | None = None,
    container_path: Path | None = None,
    contained_path: str | None = None,
) -> list[EmailDropPacket]:
    packets: list[EmailDropPacket] = []
    for ordinal, message in enumerate(mailbox.mbox(path)):
        parsed = BytesParser(policy=policy.default).parsebytes(message.as_bytes())
        packets.append(
            _packet_from_message(
                parsed,
                source_path=path,
                artifact_type=artifact_type,
                staging_dir=staging_dir,
                container_path=container_path,
                contained_path=contained_path,
                ordinal=ordinal,
            )
        )
    return packets


def _packets_from_apple_bundle(
    path: Path,
    *,
    staging_dir: Path | None = None,
) -> list[EmailDropPacket]:
    mbox_path = path / "mbox"
    if mbox_path.exists():
        return _packets_from_mbox(
            mbox_path,
            "apple_mbox_bundle",
            staging_dir=staging_dir,
        )
    packets: list[EmailDropPacket] = []
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        if child.name == "mbox" or child.suffix.lower() == ".eml":
            child_result = parse_artifact(child, staging_dir=staging_dir)
            for packet in child_result.packets:
                packet.artifact_type = "apple_mbox_bundle"
                packets.append(packet)
    return packets


def _packet_from_message(
    message: Message,
    *,
    source_path: Path,
    artifact_type: str,
    staging_dir: Path | None,
    container_path: Path | None,
    contained_path: str | None,
    ordinal: int,
) -> EmailDropPacket:
    body_text = _message_body(message, "plain")
    body_html = _message_body(message, "html")
    links = _extract_links("\n".join(item for item in (body_text, body_html) if item))
    attachments = _message_attachments(
        message,
        staging_dir=staging_dir,
        source_path=source_path,
        ordinal=ordinal,
    )
    return EmailDropPacket(
        source_path=str(source_path),
        artifact_type=artifact_type,
        subject=_header(message, "Subject"),
        from_address=_first_address(message, "From"),
        to_addresses=_addresses(message, "To"),
        cc_addresses=_addresses(message, "Cc"),
        bcc_addresses=_addresses(message, "Bcc"),
        date=_header(message, "Date"),
        message_id=_header(message, "Message-ID"),
        body_text=body_text,
        body_html=body_html,
        links=links,
        attachments=attachments,
        metadata_partial=False,
        container_path=str(container_path) if container_path is not None else None,
        contained_path=contained_path,
        ordinal=ordinal,
    )


def _message_body(message: Message, subtype: str) -> str | None:
    if hasattr(message, "get_body"):
        body = message.get_body(preferencelist=(subtype,))
        if body is not None:
            content = body.get_content()
            return content if isinstance(content, str) else str(content)
    if not message.is_multipart() and message.get_content_subtype() == subtype:
        payload = message.get_payload(decode=True)
        charset = message.get_content_charset() or "utf-8"
        if payload is not None:
            return payload.decode(charset, errors="replace")
    return None


def _message_attachments(
    message: Message,
    *,
    staging_dir: Path | None,
    source_path: Path,
    ordinal: int,
) -> list[EmailDropAttachment]:
    attachments: list[EmailDropAttachment] = []
    iter_attachments = getattr(message, "iter_attachments", None)
    parts = iter_attachments() if iter_attachments is not None else []
    for part in parts:
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            content = part.get_payload()
            payload = str(content).encode("utf-8")
        staged_path = None
        if staging_dir is not None:
            attachment_dir = staging_dir / "attachments" / _safe_stem(source_path)
            attachment_dir.mkdir(parents=True, exist_ok=True)
            target = _unique_attachment_path(
                attachment_dir / f"{ordinal}-{_safe_attachment_name(filename)}"
            )
            target.write_bytes(payload)
            staged_path = str(target)
        attachments.append(
            EmailDropAttachment(
                filename=filename,
                content_type=part.get_content_type(),
                size=len(payload),
                staged_path=staged_path,
            )
        )
    return attachments


def _safe_attachment_name(filename: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", Path(filename).name).strip("-") or "attachment"


def _unique_attachment_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 10_000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find available path for {path}")


def _packet_from_degraded(path: Path, artifact_type: str) -> EmailDropPacket:
    body_text = None
    if artifact_type in {"txt", "html", "htm", "mht", "mhtml"}:
        body_text = path.read_text(encoding="utf-8", errors="replace")
    return EmailDropPacket(
        source_path=str(path),
        artifact_type=artifact_type,
        subject=path.name,
        body_text=body_text,
        links=_extract_links(body_text or ""),
        metadata_partial=True,
    )


def _parse_archive(
    path: Path,
    artifact_type: str,
    *,
    staging_dir: Path | None,
    max_entries: int,
    max_entry_bytes: int,
) -> EmailArtifactParseResult:
    result = EmailArtifactParseResult(
        source_path=str(path),
        artifact_type=artifact_type,
    )
    if staging_dir is None:
        with tempfile.TemporaryDirectory(prefix="augur-email-archive-") as temp_dir:
            return _extract_and_parse_archive(
                path,
                artifact_type,
                Path(temp_dir),
                result,
                max_entries=max_entries,
                max_entry_bytes=max_entry_bytes,
            )
    return _extract_and_parse_archive(
        path,
        artifact_type,
        staging_dir,
        result,
        max_entries=max_entries,
        max_entry_bytes=max_entry_bytes,
    )


def _extract_and_parse_archive(
    path: Path,
    artifact_type: str,
    staging_dir: Path,
    result: EmailArtifactParseResult,
    *,
    max_entries: int,
    max_entry_bytes: int,
) -> EmailArtifactParseResult:
    extract_dir = staging_dir / _safe_stem(path)
    extract_dir.mkdir(parents=True, exist_ok=True)
    if artifact_type == "zip":
        extracted = _extract_zip(
            path,
            extract_dir,
            result,
            max_entries=max_entries,
            max_entry_bytes=max_entry_bytes,
        )
    else:
        extracted = _extract_tar(
            path,
            extract_dir,
            result,
            max_entries=max_entries,
            max_entry_bytes=max_entry_bytes,
        )
    if result.errors:
        return result
    for member_path, relative_name in extracted:
        child_result = parse_artifact(member_path, staging_dir=staging_dir)
        for packet in child_result.packets:
            packet.container_path = str(path)
            packet.contained_path = relative_name
            result.packets.append(packet)
        for skipped in child_result.skipped:
            skipped.container_path = str(path)
            skipped.contained_path = relative_name
            result.skipped.append(skipped)
        result.errors.extend(child_result.errors)
    return result


def _extract_zip(
    path: Path,
    extract_dir: Path,
    result: EmailArtifactParseResult,
    *,
    max_entries: int,
    max_entry_bytes: int,
) -> list[tuple[Path, str]]:
    extracted: list[tuple[Path, str]] = []
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > max_entries:
            result.errors.append(f"archive_too_many_entries: {len(members)}")
            return extracted
        for member in members:
            if member.is_dir():
                continue
            if member.file_size > max_entry_bytes:
                result.errors.append(f"archive_entry_too_large: {member.filename}")
                continue
            target = _safe_archive_target(extract_dir, member.filename, result)
            if target is None:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source:
                target.write_bytes(source.read())
            extracted.append((target, member.filename))
    return extracted


def _extract_tar(
    path: Path,
    extract_dir: Path,
    result: EmailArtifactParseResult,
    *,
    max_entries: int,
    max_entry_bytes: int,
) -> list[tuple[Path, str]]:
    extracted: list[tuple[Path, str]] = []
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        if len(members) > max_entries:
            result.errors.append(f"archive_too_many_entries: {len(members)}")
            return extracted
        for member in members:
            if not member.isfile():
                continue
            if member.size > max_entry_bytes:
                result.errors.append(f"archive_entry_too_large: {member.name}")
                continue
            target = _safe_archive_target(extract_dir, member.name, result)
            if target is None:
                continue
            source = archive.extractfile(member)
            if source is None:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read())
            extracted.append((target, member.name))
    return extracted


def _safe_archive_target(
    extract_dir: Path,
    member_name: str,
    result: EmailArtifactParseResult,
) -> Path | None:
    normalized = PurePosixPath(member_name)
    if normalized.is_absolute() or ".." in normalized.parts:
        result.errors.append(f"unsafe_archive_entry: {member_name}")
        return None
    target = (extract_dir / Path(*normalized.parts)).resolve(strict=False)
    base = extract_dir.resolve(strict=False)
    if target != base and base not in target.parents:
        result.errors.append(f"unsafe_archive_entry: {member_name}")
        return None
    return target


def _safe_stem(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", path.name).strip("-") or "archive"


def _header(message: Message, name: str) -> str | None:
    value = message.get(name)
    return str(value) if value is not None else None


def _first_address(message: Message, name: str) -> str | None:
    values = _addresses(message, name)
    return values[0] if values else None


def _addresses(message: Message, name: str) -> list[str]:
    raw = message.get_all(name, [])
    return [address or display for display, address in getaddresses(raw)]


def _extract_links(value: str) -> list[str]:
    links: list[str] = []
    for match in LINK_RE.findall(value):
        cleaned = match.rstrip(").,;!?]'\"")
        if cleaned not in links:
            links.append(cleaned)
    return links
