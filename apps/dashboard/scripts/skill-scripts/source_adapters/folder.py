"""FolderAdapter: reads files from a local filesystem directory (ADR-086)."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import FileInfo, ScanManifest, SourceAdapter

# Directories and files to skip during scanning
IGNORED_NAMES = {
    ".DS_Store",
    ".git",
    ".svn",
    "__pycache__",
    "node_modules",
    ".Spotlight-V100",
    ".Trashes",
    "Thumbs.db",
    "desktop.ini",
}

# Max depth to recurse into subdirectories
MAX_DEPTH = 5

# Extension -> file_type mapping for common types
EXTENSION_MAP = {
    ".xlsx": "xlsx",
    ".xls": "xls",
    ".csv": "csv",
    ".pdf": "pdf",
    ".md": "md",
    ".txt": "txt",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".png": "png",
    ".jpg": "jpg",
    ".jpeg": "jpg",
    ".gif": "gif",
    ".svg": "svg",
    ".docx": "docx",
    ".doc": "doc",
    ".pptx": "pptx",
    ".html": "html",
}


def _extension_to_type(path: Path) -> str:
    """Map a file extension to a normalized type string."""
    ext = path.suffix.lower()
    return EXTENSION_MAP.get(ext, ext.lstrip(".") or "unknown")


def _should_ignore(name: str) -> bool:
    """Return True if this file/directory should be skipped."""
    return name in IGNORED_NAMES or name.startswith("._")


class FolderAdapter(SourceAdapter):
    """Adapter that scans a local filesystem directory.

    Walks the directory tree up to MAX_DEPTH, collects file metadata,
    and optionally runs file analyzers to extract structure.
    """

    source_type: str = "folder"

    def __init__(self, path: str | Path, *, analyzers: dict[str, Any] | None = None) -> None:
        """Initialize with a directory path.

        Args:
            path: Absolute or ~ prefixed path to directory.
            analyzers: Optional mapping of file_type -> analyzer instance.
                       Each analyzer must have an analyze(path) -> dict method.
        """
        self._root = Path(os.path.expanduser(str(path))).resolve()
        self._analyzers = analyzers or {}

        if not self._root.is_dir():
            raise NotADirectoryError(f"Not a directory: {self._root}")

    @property
    def root(self) -> Path:
        """Resolved absolute path to the source directory."""
        return self._root

    def scan(self) -> ScanManifest:
        """Walk the directory tree and return a structured manifest.

        If analyzers are provided, each file's structure will be analyzed
        and stored in the manifest's file_structures dict.
        """
        files: list[FileInfo] = []
        total_size = 0
        structures: dict[str, Any] = {}

        self._walk(self._root, files, structures, depth=0)

        total_size = sum(f.size for f in files if not f.is_directory)

        return ScanManifest(
            source_type=self.source_type,
            source_path=str(self._root),
            files=files,
            total_size=total_size,
            file_structures=structures,
        )

    def read_file(self, path: str) -> bytes:
        """Read a file relative to the source root.

        Args:
            path: Relative path within the source directory.

        Returns:
            File contents as bytes.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the path escapes the source root.
        """
        target = (self._root / path).resolve()

        # Prevent path traversal
        if not str(target).startswith(str(self._root)):
            raise ValueError(f"Path escapes source root: {path}")

        if not target.is_file():
            raise FileNotFoundError(f"File not found: {target}")

        return target.read_bytes()

    def list_files(self) -> list[FileInfo]:
        """Return a flat list of all files and directories (no analysis)."""
        files: list[FileInfo] = []
        self._walk(self._root, files, structures=None, depth=0)
        return files

    def _walk(
        self,
        directory: Path,
        files: list[FileInfo],
        structures: dict[str, Any] | None,
        depth: int,
    ) -> None:
        """Recursively walk a directory, collecting FileInfo entries.

        Args:
            directory: Current directory being walked.
            files: Accumulator for FileInfo objects.
            structures: If not None, accumulates analyzer results keyed by relative path.
            depth: Current recursion depth.
        """
        if depth > MAX_DEPTH:
            return

        try:
            entries = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return

        for entry in entries:
            if _should_ignore(entry.name):
                continue

            rel_path = str(entry.relative_to(self._root))

            if entry.is_dir():
                info = FileInfo(
                    name=entry.name,
                    path=rel_path,
                    size=0,
                    modified=datetime.fromtimestamp(entry.stat().st_mtime),
                    file_type="directory",
                    is_directory=True,
                )
                files.append(info)

                # Recurse into subdirectory
                children: list[FileInfo] = []
                self._walk(entry, children, structures, depth + 1)
                info.children = children
                files.extend(children)

                # Run directory analyzer if available
                if structures is not None and "directory" in self._analyzers:
                    try:
                        structures[rel_path] = self._analyzers["directory"].analyze(entry)
                    except Exception:
                        pass

            elif entry.is_file():
                try:
                    stat = entry.stat()
                except (PermissionError, OSError):
                    continue

                file_type = _extension_to_type(entry)
                info = FileInfo(
                    name=entry.name,
                    path=rel_path,
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime),
                    file_type=file_type,
                )
                files.append(info)

                # Run type-specific analyzer if available
                if structures is not None and file_type in self._analyzers:
                    try:
                        structures[rel_path] = self._analyzers[file_type].analyze(entry)
                    except Exception:
                        pass
