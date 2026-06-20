"""Base class and types for external data source adapters (ADR-086)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class FileInfo:
    """Metadata for a single file in an external source."""

    name: str
    path: str  # relative to source root
    size: int  # bytes
    modified: datetime
    file_type: str  # extension without dot, e.g. "xlsx", "pdf"
    is_directory: bool = False
    children: list[FileInfo] = field(default_factory=list)

    @property
    def extension(self) -> str:
        """Return lowercase extension without leading dot."""
        return self.file_type.lower()


@dataclass
class ScanManifest:
    """Result of scanning an external data source."""

    source_type: str  # "folder", "notion", "gdrive"
    source_path: str  # original path/URI provided by user
    scanned_at: datetime = field(default_factory=datetime.now)
    files: list[FileInfo] = field(default_factory=list)
    total_size: int = 0
    file_structures: dict[str, Any] = field(default_factory=dict)
    # Maps relative path -> FileStructure dict from analyzers

    @property
    def file_count(self) -> int:
        """Total number of files (excluding directories)."""
        return sum(1 for f in self.files if not f.is_directory)

    @property
    def directory_count(self) -> int:
        """Total number of directories."""
        return sum(1 for f in self.files if f.is_directory)


class SourceAdapter(ABC):
    """Base class for external data sources.

    Subclasses implement scan(), read_file(), and list_files() to provide
    a uniform interface over folders, Notion workspaces, Google Drive, etc.
    """

    source_type: str = "unknown"

    @abstractmethod
    def scan(self) -> ScanManifest:
        """Scan the source and return a structured manifest.

        Returns a ScanManifest containing file metadata and, when analyzers
        are available, per-file structure information.
        """
        raise NotImplementedError

    @abstractmethod
    def read_file(self, path: str) -> bytes:
        """Read a specific file from the source.

        Args:
            path: Relative path within the source.

        Returns:
            Raw file contents as bytes.

        Raises:
            FileNotFoundError: If the path does not exist in the source.
        """
        raise NotImplementedError

    @abstractmethod
    def list_files(self) -> list[FileInfo]:
        """List all files in the source (flat, no structure analysis).

        Returns a flat list of FileInfo objects for every file and directory
        in the source, suitable for quick enumeration without deep analysis.
        """
        raise NotImplementedError
