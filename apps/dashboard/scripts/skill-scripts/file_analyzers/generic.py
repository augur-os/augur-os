"""GenericAnalyzer: basic metadata for any file type (ADR-086)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class GenericAnalyzer:
    """Fallback analyzer that extracts basic metadata from any file.

    Returns a FileStructure dict with:
        - type: "generic"
        - name: filename
        - extension: file extension
        - size: file size in bytes
        - size_human: human-readable size string
    """

    def analyze(self, path: Path) -> dict[str, Any]:
        """Analyze any file and return basic metadata.

        Args:
            path: Path to the file.

        Returns:
            FileStructure dict.
        """
        path = Path(path)
        result: dict[str, Any] = {
            "type": "generic",
            "name": path.name,
            "extension": path.suffix.lower().lstrip("."),
            "size": 0,
            "size_human": "0 B",
        }

        try:
            stat = path.stat()
            result["size"] = stat.st_size
            result["size_human"] = _format_size(stat.st_size)
        except (OSError, PermissionError):
            pass

        return result


def _format_size(size_bytes: int) -> str:
    """Convert bytes to a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
