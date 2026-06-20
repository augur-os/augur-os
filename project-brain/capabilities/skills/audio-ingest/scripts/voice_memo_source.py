"""Discover the most recent macOS Voice Memos recording.

Voice Memos.app stores recordings inside its sandboxed group container at
``~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings/``.
That directory is TCC-protected — reading it requires the calling binary
(Terminal, the Python interpreter that backs Augur, etc.) to be granted
**Full Disk Access** in System Settings -> Privacy & Security.

This module is the L4 atomic helper behind the ``voice-memo-latest`` MCP
tool. It only reads and (optionally) copies; it never deletes the original.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import errno
import os
import shutil
import time
from typing import Any

VOICE_MEMO_EXTENSIONS = (".m4a", ".caf", ".wav")

VOICE_MEMO_SEARCH_ROOTS = (
    Path.home() / "Library" / "Group Containers" / "group.com.apple.VoiceMemos.shared" / "Recordings",
    Path.home() / "Library" / "Application Support" / "com.apple.voicememos" / "Recordings",
)

FDA_HINT = (
    "Open System Settings -> Privacy & Security -> Full Disk Access and grant "
    "access to your Terminal app (or the Python interpreter that runs Augur). "
    "Then retry."
)


@dataclass
class VoiceMemoResult:
    success: bool
    source_path: str | None = None
    copied_to: str | None = None
    filename: str | None = None
    size_bytes: int | None = None
    modified_at: float | None = None
    error: str | None = None
    hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None or k == "success"}


def _candidate_files(roots: tuple[Path, ...] = VOICE_MEMO_SEARCH_ROOTS) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        try:
            entries = list(root.rglob("*"))
        except PermissionError:
            raise
        except FileNotFoundError:
            continue
        except OSError as exc:
            if exc.errno in (errno.EPERM, errno.EACCES):
                raise PermissionError(str(exc)) from exc
            continue
        for entry in entries:
            if entry.is_file() and entry.suffix.lower() in VOICE_MEMO_EXTENSIONS:
                files.append(entry)
    return files


def latest_voice_memo(
    *,
    since_seconds: int | None = None,
    copy_to: str | None = None,
    roots: tuple[Path, ...] = VOICE_MEMO_SEARCH_ROOTS,
) -> VoiceMemoResult:
    """Return the most recent Voice Memos recording.

    Args:
        since_seconds: If set, only consider files modified within this many
            seconds. ``None`` (default) means no cutoff.
        copy_to: If set, copy the discovered file into this directory and
            return the destination path. The destination directory is created
            if needed.
        roots: Override the default search roots (used in tests).
    """
    try:
        files = _candidate_files(roots)
    except PermissionError as exc:
        return VoiceMemoResult(
            success=False,
            error=f"Voice Memos container is not readable: {exc}",
            hint=FDA_HINT,
        )

    if not files:
        return VoiceMemoResult(
            success=False,
            error=(
                "No Voice Memos recordings found in known macOS storage paths. "
                "If recordings exist, the container is likely sandboxed and not "
                "yet readable."
            ),
            hint=FDA_HINT,
        )

    cutoff = time.time() - since_seconds if since_seconds is not None else None
    candidates = [f for f in files if cutoff is None or f.stat().st_mtime >= cutoff]
    if not candidates:
        return VoiceMemoResult(
            success=False,
            error=f"No Voice Memos recordings modified in the last {since_seconds}s.",
        )

    latest = max(candidates, key=lambda f: f.stat().st_mtime)
    stat = latest.stat()
    result = VoiceMemoResult(
        success=True,
        source_path=str(latest),
        filename=latest.name,
        size_bytes=stat.st_size,
        modified_at=stat.st_mtime,
    )

    if copy_to:
        destination_dir = Path(copy_to).expanduser()
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / latest.name
        shutil.copy2(latest, destination)
        result.copied_to = str(destination)

    return result


def main(argv: list[str] | None = None) -> int:
    """CLI for ad-hoc use. Prints JSON for the agent or shell consumer."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Discover the latest macOS Voice Memos recording.")
    parser.add_argument("--copy-to", default="", help="Destination directory; if set, copy the file.")
    parser.add_argument("--since-seconds", type=int, default=0, help="0 = no cutoff.")
    args = parser.parse_args(argv)

    result = latest_voice_memo(
        since_seconds=args.since_seconds or None,
        copy_to=args.copy_to or None,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
