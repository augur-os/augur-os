from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from src.lib.ingest.inbox_models import InboxFolderCounts

DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".webp",
    ".txt",
    ".md",
    ".mp3",
    ".wav",
    ".m4a",
    ".flac",
}
TRASH_EXTENSIONS = {".tmp", ".download", ".crdownload", ".part"}


@dataclass
class ScanItem:
    path: str
    name: str
    suffix: str
    candidate_type: str
    stable: bool = True


@dataclass
class ScanResult:
    path: str
    counts: InboxFolderCounts = field(default_factory=InboxFolderCounts)
    items: list[ScanItem] = field(default_factory=list)


def scan_folder(
    path: Path | str,
    stable_age_seconds: float = 2.0,
    now: float | None = None,
) -> ScanResult:
    folder_path = Path(path).expanduser().resolve(strict=False)
    result = ScanResult(path=str(folder_path))

    if not folder_path.is_dir():
        result.counts.failed = 1
        return result

    try:
        files = sorted(
            (item for item in folder_path.iterdir() if not item.is_symlink() and item.is_file()),
            key=lambda item: item.name.lower(),
        )
    except OSError:
        result.counts.failed = 1
        return result

    current_time = time.time() if now is None else now
    for file_path in files:
        try:
            file_stat = file_path.stat()
        except OSError:
            suffix = file_path.suffix.lower()
            result.items.append(
                ScanItem(
                    path=str(file_path.resolve(strict=False)),
                    name=file_path.name,
                    suffix=suffix,
                    candidate_type="failed",
                    stable=False,
                )
            )
            result.counts.failed += 1
            continue
        suffix = file_path.suffix.lower()
        candidate_type = _candidate_type(suffix)
        result.items.append(
            ScanItem(
                path=str(file_path.resolve(strict=False)),
                name=file_path.name,
                suffix=suffix,
                candidate_type=candidate_type,
                stable=(current_time - file_stat.st_mtime) >= stable_age_seconds,
            )
        )
        result.counts.new_files += 1
        if candidate_type == "document":
            result.counts.document_candidates += 1
        elif candidate_type == "trash":
            result.counts.trash_candidates += 1

    return result


def _candidate_type(suffix: str) -> str:
    if suffix in DOCUMENT_EXTENSIONS:
        return "document"
    if suffix in TRASH_EXTENSIONS:
        return "trash"
    return "unknown"
