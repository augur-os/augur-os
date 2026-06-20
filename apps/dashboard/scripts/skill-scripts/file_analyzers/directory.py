"""DirectoryAnalyzer: extract structure from directories (ADR-086)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any


class DirectoryAnalyzer:
    """Analyze a directory to extract structure.

    Returns a FileStructure dict with:
        - type: "directory"
        - file_count: total number of files
        - dir_count: number of subdirectories
        - dominant_type: most common file extension
        - type_distribution: dict of extension -> count
        - purpose_guess: heuristic guess at directory purpose
    """

    def analyze(self, path: Path) -> dict[str, Any]:
        """Analyze a directory's contents.

        Args:
            path: Path to the directory.

        Returns:
            FileStructure dict.
        """
        path = Path(path)
        result: dict[str, Any] = {
            "type": "directory",
            "file_count": 0,
            "dir_count": 0,
            "dominant_type": "",
            "type_distribution": {},
            "purpose_guess": "unknown",
        }

        if not path.is_dir():
            result["error"] = f"Not a directory: {path}"
            return result

        ext_counter: Counter[str] = Counter()
        file_count = 0
        dir_count = 0

        try:
            for entry in path.iterdir():
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    dir_count += 1
                elif entry.is_file():
                    file_count += 1
                    ext = entry.suffix.lower().lstrip(".")
                    if ext:
                        ext_counter[ext] += 1
                    else:
                        ext_counter["no_ext"] += 1
        except PermissionError:
            result["error"] = "Permission denied"
            return result

        result["file_count"] = file_count
        result["dir_count"] = dir_count

        if ext_counter:
            result["dominant_type"] = ext_counter.most_common(1)[0][0]
            result["type_distribution"] = dict(ext_counter.most_common())

        result["purpose_guess"] = self._guess_purpose(path.name, ext_counter, file_count)

        return result

    def _guess_purpose(self, dir_name: str, ext_counter: Counter[str], file_count: int) -> str:
        """Heuristic guess at directory purpose based on name and contents."""
        name_lower = dir_name.lower()

        # Name-based guesses
        purpose_keywords = {
            "receipt": "receipts",
            "invoice": "invoices",
            "tax": "tax_documents",
            "statement": "statements",
            "photo": "photos",
            "image": "images",
            "report": "reports",
            "doc": "documents",
            "backup": "backups",
            "archive": "archive",
            "template": "templates",
            "export": "exports",
        }
        for keyword, purpose in purpose_keywords.items():
            if keyword in name_lower:
                return purpose

        # Content-based guesses
        if not ext_counter:
            return "empty"

        dominant = ext_counter.most_common(1)[0][0]
        dominant_ratio = ext_counter[dominant] / max(file_count, 1)

        if dominant_ratio > 0.7:
            type_purposes = {
                "pdf": "pdf_collection",
                "jpg": "photos",
                "jpeg": "photos",
                "png": "images",
                "xlsx": "spreadsheets",
                "csv": "data_files",
                "md": "documentation",
                "txt": "text_files",
            }
            return type_purposes.get(dominant, f"{dominant}_collection")

        return "mixed_files"
