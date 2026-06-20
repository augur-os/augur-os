"""Document source roots for Browse and the unified document index."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DOCUMENT_EXTENSIONS = {
    ".csv",
    ".doc",
    ".docx",
    ".epub",
    ".htm",
    ".html",
    ".json",
    ".md",
    ".markdown",
    ".odp",
    ".ods",
    ".odt",
    ".pdf",
    ".ppt",
    ".pptx",
    ".rst",
    ".rtf",
    ".svg",
    ".tex",
    ".text",
    ".toml",
    ".tsv",
    ".txt",
    ".xls",
    ".xlsx",
    ".xml",
    ".yaml",
    ".yml",
}
IMAGE_EXTENSIONS = {
    ".bmp",
    ".gif",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tiff",
    ".webp",
}
AUDIO_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav"}
VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v", ".webm"}
INDEXABLE_EXTENSIONS = DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

EXCLUDED_DIR_NAMES = {
    ".Trash",
    ".cache",
    ".git",
    ".venv",
    ".pnpm",
    "__pycache__",
    "env",
    "node_modules",
    "site-packages",
    "vendor",
    "venv",
}
EXCLUDED_SUFFIXES = {
    ".app",
    ".crdownload",
    ".dmg",
    ".download",
    ".iso",
    ".part",
    ".pkg",
    ".tmp",
}
EXCLUDED_FILENAMES = {
    ".DS_Store",
    "Thumbs.db",
}


@dataclass(frozen=True)
class DocumentSource:
    id: str
    name: str
    path: Path
    preserve_legacy_output: bool = False
    source_type: str = "local"
    provider: str = "filesystem"
    attached_brain_ids: tuple[str, ...] = ("personal",)
    source_remote_id: str = ""
    remote_revision: str = ""
    remote_modified_at: str = ""
    catalog_entry_path: str = ""
    catalog_title: str = ""
    catalog_summary: str = ""
    summary_status: str = ""
    summary_generated_from_revision: str = ""

    @property
    def resolved_path(self) -> Path:
        return self.path.expanduser().resolve(strict=False)


def default_document_sources(*, documents_dir: Path) -> list[DocumentSource]:
    sources = [
        DocumentSource(
            "documents",
            "Documents",
            Path(documents_dir).expanduser().resolve(strict=False),
            preserve_legacy_output=True,
        ),
    ]
    home = Path.home()
    for source_id, name in (("desktop", "Desktop"), ("downloads", "Downloads")):
        path = home / name
        if path.is_dir():
            sources.append(DocumentSource(source_id, name, path.expanduser().resolve(strict=False)))
    return sources


def media_kind_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    return ""


def should_index_source_file(path: Path, source: DocumentSource) -> bool:
    source_root = source.resolved_path
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = source_root / candidate
    resolved_candidate = candidate.resolve(strict=False)
    try:
        lexical_parts = set(candidate.relative_to(source_root).parts)
        resolved_parts = set(resolved_candidate.relative_to(source_root).parts)
    except ValueError:
        return False
    if not resolved_candidate.is_file():
        return False
    if candidate.name in EXCLUDED_FILENAMES:
        return False
    if candidate.name.lower() == "skill.md":
        return False
    if candidate.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if any(
        part.startswith(".") or part in EXCLUDED_DIR_NAMES or Path(part).suffix.lower() in EXCLUDED_SUFFIXES
        for part in lexical_parts | resolved_parts
    ):
        return False
    # .augurignore exclusion (spec 2026-06-13): consult the source-root ignore file.
    from src.lib.index.augurignore import load_augurignore, path_is_ignored

    rel_posix = resolved_candidate.relative_to(source_root).as_posix()
    if path_is_ignored(rel_posix, load_augurignore(source_root)):
        return False
    return resolved_candidate.suffix.lower() in INDEXABLE_EXTENSIONS
