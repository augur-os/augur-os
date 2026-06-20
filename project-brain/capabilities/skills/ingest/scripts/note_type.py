"""Pure-logic helpers for /note argument-shape detection.

No I/O beyond stat() on filesystem-path arguments. The /note command policy
uses these helpers to decide which atomic operation should persist the note.
"""
from __future__ import annotations

import re
from pathlib import Path

URL_RE = re.compile(r"^https?://", re.IGNORECASE)

AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".mp4", ".mov", ".m4v"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".heic", ".webp", ".gif"}
DOC_EXTS = {".pdf", ".docx", ".doc", ".md", ".html", ".htm", ".txt", ".rtf", ".epub"}

VALID_NOTE_TYPES = (
    "url",
    "file",
    "thought",
    "voice-memo",
    "meeting",
    "image",
    "prompt",
    "folder",
    "audio",
)


def detect_note_type_from_arg(arg: str) -> str:
    """Return the routing label for an /note argument."""
    if not arg or not arg.strip():
        return "thought"

    candidate = arg.strip()
    if URL_RE.match(candidate):
        return "url"

    path = Path(candidate)
    suffix = path.suffix.lower()
    if suffix in AUDIO_EXTS:
        return "audio"
    if suffix in IMAGE_EXTS:
        return "image"
    if suffix in DOC_EXTS:
        return "file"
    if path.exists():
        if path.is_dir():
            return "folder"
        return "file"

    return "thought"


def is_valid_note_type(value: str) -> bool:
    """Return whether ``value`` is a supported note type tag."""
    return value in VALID_NOTE_TYPES
