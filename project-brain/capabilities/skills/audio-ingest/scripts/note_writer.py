"""Write voice-memo and meeting notes under <vault>/notes/."""
from __future__ import annotations

from datetime import date
import hashlib
from pathlib import Path
import re
import shutil
import sys
from typing import Any
import unicodedata

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.lib.brain_layout import brain_layout, vault_machine_dir  # noqa: E402
from src.lib.frontmatter_utils import parse_frontmatter, write_vault_frontmatter  # noqa: E402

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str, max_len: int = 80) -> str:
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    slug = _SLUG_RE.sub("-", normalized.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "audio"


def _content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def _segments_to_transcript(segments: list[dict]) -> str:
    lines: list[str] = []
    for segment in segments:
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        speaker = segment.get("speaker")
        if speaker:
            lines.append(f"[{speaker}] {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


def _frontmatter_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _repair_existing_meeting_note(path: Path, attendee_count: int, attendee_slugs: list[str]) -> None:
    if attendee_count <= 0 and not attendee_slugs:
        return
    metadata, body = parse_frontmatter(path, include_sidecar_config=False)
    current_count = _frontmatter_int(metadata.get("attendee_count"))
    next_count = max(current_count, attendee_count, len(attendee_slugs))
    next_slugs = attendee_slugs or list(metadata.get("attendee_slugs") or [])
    if next_count == current_count and next_slugs == metadata.get("attendee_slugs"):
        return
    metadata["attendee_count"] = next_count
    if next_slugs:
        metadata["attendee_slugs"] = next_slugs
    write_vault_frontmatter(path, metadata, body)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Unable to choose unique audio destination for {path}")


def _audio_storage_dir(notes_dir: Path, note_type: str, vault_dir: Path | None = None) -> Path:
    folder = "voice-memos" if note_type == "voice-memo" else "meetings"
    # Brain root for the layout probe: callers (tools_audio) pass the vault
    # root explicitly; older callers fall back to notes_dir.parent, which IS
    # the vault root in domains layout (notes_dir = <vault>/inbox).
    root = vault_dir if vault_dir is not None else notes_dir.parent
    # Domains layout: audio binaries are machine-stored content — keep them
    # under _augur/ (where the migration moves the top-level voice-memos dir)
    # instead of creating a rogue top-level dir the structure guard would
    # flag. Legacy stays byte-identical: the layout probe returns "knowledge"
    # (vault root BRAIN.yaml has no domains layout; the notes_dir.parent
    # fallback probes <vault>/knowledge which has no BRAIN.yaml at all), so
    # audio keeps landing at notes_dir.parent (<vault>/knowledge/{folder}).
    if brain_layout(root) == "domains":
        return vault_machine_dir(root, folder)
    return notes_dir.parent / folder


def _store_audio_source(
    *,
    notes_dir: Path,
    audio_path: Path,
    note_type: str,
    title: str,
    consume_source: bool,
    vault_dir: Path | None = None,
) -> Path:
    source = audio_path.expanduser()
    if not source.is_file():
        return audio_path

    in_vault_root = notes_dir.parent.resolve(strict=False)
    resolved_source = source.resolve(strict=False)
    if _is_relative_to(resolved_source, in_vault_root):
        return source

    destination_dir = _audio_storage_dir(notes_dir, note_type, vault_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix or ".audio"
    stem = _slugify(title or source.stem)
    destination = _unique_path(destination_dir / f"{date.today().isoformat()}-{stem}{suffix}")
    if consume_source:
        shutil.move(str(source), str(destination))
    else:
        shutil.copy2(str(source), str(destination))
    return destination


def _repair_existing_audio_note(
    path: Path,
    *,
    audio_path: Path,
    note_type: str,
    attendee_count: int,
    attendee_slugs: list[str],
) -> None:
    metadata, body = parse_frontmatter(path, include_sidecar_config=False)
    changed = False
    if str(metadata.get("audio_path") or "") != str(audio_path):
        metadata["audio_path"] = str(audio_path)
        changed = True
    if note_type == "meeting":
        current_count = _frontmatter_int(metadata.get("attendee_count"))
        next_count = max(current_count, attendee_count, len(attendee_slugs))
        next_slugs = attendee_slugs or list(metadata.get("attendee_slugs") or [])
        if next_count != current_count:
            metadata["attendee_count"] = next_count
            changed = True
        if next_slugs and next_slugs != metadata.get("attendee_slugs"):
            metadata["attendee_slugs"] = next_slugs
            changed = True
    if changed:
        write_vault_frontmatter(path, metadata, body)


def write_audio_note(
    *,
    notes_dir: Path,
    audio_path: Path,
    note_type: str,
    title: str,
    transcript_text: str,
    segments: list[dict],
    duration_seconds: float,
    provider: str,
    provider_version: str,
    attendee_slugs: list[str],
    attendee_count_hint: int = 0,
    consume_source: bool = False,
    vault_dir: Path | None = None,
) -> Path:
    """Write a typed audio note and return the path.

    ``vault_dir`` is the brain root used to resolve the layout-aware audio
    storage dir; when omitted, ``notes_dir.parent`` is probed instead.
    """
    if note_type not in {"voice-memo", "meeting"}:
        raise ValueError(f"unsupported audio note_type: {note_type}")

    notes_dir.mkdir(parents=True, exist_ok=True)
    stored_audio_path = _store_audio_source(
        notes_dir=notes_dir,
        audio_path=audio_path,
        note_type=note_type,
        title=title,
        consume_source=consume_source,
        vault_dir=vault_dir,
    )
    content_hash = _content_hash(transcript_text)
    attendee_count = max(len(attendee_slugs), int(attendee_count_hint or 0))
    for existing in notes_dir.glob("*.md"):
        try:
            existing_text = existing.read_text(encoding="utf-8")
            if (
                f"content_hash: {content_hash}" in existing_text
                and f"x-augur-note-type: {note_type}" in existing_text
            ):
                _repair_existing_audio_note(
                    existing,
                    audio_path=stored_audio_path,
                    note_type=note_type,
                    attendee_count=attendee_count,
                    attendee_slugs=attendee_slugs,
                )
                return existing
        except OSError:
            continue

    kind = "voice" if note_type == "voice-memo" else "meeting"
    target = notes_dir / f"{date.today().isoformat()}-{kind}-{_slugify(title or stored_audio_path.stem)}.md"

    metadata: dict[str, Any] = {
        "title": title or stored_audio_path.stem,
        "x-augur-note-type": note_type,
        "audio_path": str(stored_audio_path),
        "duration_seconds": duration_seconds,
        "transcript_status": "complete",
        "provider": provider,
        "provider_version": provider_version,
        "content_hash": content_hash,
        "transcript_preview": (transcript_text or _segments_to_transcript(segments))[:4000],
    }
    if note_type == "meeting":
        metadata["attendee_count"] = attendee_count
        if attendee_slugs:
            metadata["attendee_slugs"] = attendee_slugs

    body_lines: list[str] = []
    if note_type == "meeting" and attendee_slugs:
        body_lines.append("## Attendees")
        body_lines.extend(f"- [[wiki/people/{slug}]]" for slug in attendee_slugs)
        body_lines.append("")
    # Prefer the speaker-labeled rendering when the segments carry diarization
    # labels, so meeting notes show "[SPEAKER_XX] ..." per turn; otherwise fall
    # back to the flat transcript text (single-speaker / no diarization).
    diarized = any(segment.get("speaker") for segment in segments)
    transcript_body = (
        _segments_to_transcript(segments)
        if diarized
        else (transcript_text or _segments_to_transcript(segments))
    )
    body_lines.extend(["## Transcript", "", transcript_body, ""])
    write_vault_frontmatter(target, metadata, "\n".join(body_lines))
    return target
