"""File analyzers for external data source scanning (ADR-086).

Each analyzer extracts structure from a specific file type and returns
a FileStructure dict consumed by the integration planner.
"""

from __future__ import annotations

from .directory import DirectoryAnalyzer
from .excel import ExcelAnalyzer
from .generic import GenericAnalyzer
from .notion import NotionAnalyzer
from .pdf import PdfAnalyzer

__all__ = [
    "DirectoryAnalyzer",
    "ExcelAnalyzer",
    "GenericAnalyzer",
    "NotionAnalyzer",
    "PdfAnalyzer",
]


def get_analyzer_map() -> dict[str, object]:
    """Return a mapping of file_type -> analyzer instance.

    Suitable for passing to FolderAdapter(analyzers=...).
    """
    return {
        "xlsx": ExcelAnalyzer(),
        "xls": ExcelAnalyzer(),
        "csv": ExcelAnalyzer(),
        "pdf": PdfAnalyzer(),
        "md": NotionAnalyzer(),
        "directory": DirectoryAnalyzer(),
        # Everything else falls through to GenericAnalyzer
    }
