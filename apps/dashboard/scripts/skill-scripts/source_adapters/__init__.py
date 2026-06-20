"""Source adapters for external data sources (ADR-086).

Pluggable pattern: folder today, Notion/Google Drive tomorrow.
"""

from __future__ import annotations

from .base import FileInfo, ScanManifest, SourceAdapter
from .folder import FolderAdapter

__all__ = ["FileInfo", "FolderAdapter", "ScanManifest", "SourceAdapter"]
