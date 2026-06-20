"""PdfAnalyzer: extract structure from PDF files (ADR-086)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

# PyPDF2 is an optional dependency
try:
    from PyPDF2 import PdfReader

    HAS_PYPDF2 = True
except ImportError:
    PdfReader = None  # type: ignore[assignment, misc]
    HAS_PYPDF2 = False


class PdfAnalyzer:
    """Analyze PDF files to extract structure.

    Returns a FileStructure dict with:
        - type: "pdf"
        - page_count: number of pages
        - text_extractable: whether text can be extracted (vs scanned image)
        - headings: list of detected section headings
        - has_tables: whether tables were detected
    """

    def analyze(self, path: Path) -> dict[str, Any]:
        """Analyze a PDF file.

        Tries PyPDF2 first for text extraction. Falls back to macOS mdls
        for page count if PyPDF2 is not available.

        Args:
            path: Path to the PDF file.

        Returns:
            FileStructure dict.
        """
        path = Path(path)
        result: dict[str, Any] = {
            "type": "pdf",
            "page_count": 0,
            "text_extractable": False,
            "headings": [],
            "has_tables": False,
        }

        if HAS_PYPDF2:
            self._analyze_with_pypdf2(path, result)
        else:
            self._analyze_with_mdls(path, result)

        return result

    def _analyze_with_pypdf2(self, path: Path, result: dict[str, Any]) -> None:
        """Extract PDF structure using PyPDF2."""
        try:
            reader = PdfReader(str(path))
            result["page_count"] = len(reader.pages)

            # Try to extract text from first few pages
            sample_text = ""
            pages_to_check = min(3, len(reader.pages))
            for i in range(pages_to_check):
                page_text = reader.pages[i].extract_text() or ""
                sample_text += page_text + "\n"

            result["text_extractable"] = len(sample_text.strip()) > 50

            if result["text_extractable"]:
                # Extract headings (lines that look like section headers)
                result["headings"] = self._extract_headings(sample_text)
                # Detect tables (lines with multiple tab/pipe separators)
                result["has_tables"] = self._detect_tables(sample_text)

        except Exception as e:
            result["error"] = str(e)

    def _analyze_with_mdls(self, path: Path, result: dict[str, Any]) -> None:
        """Extract basic PDF metadata using macOS mdls command."""
        try:
            proc = subprocess.run(
                ["mdls", "-name", "kMDItemNumberOfPages", str(path)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0:
                # Output like: kMDItemNumberOfPages = 12
                match = re.search(r"=\s*(\d+)", proc.stdout)
                if match:
                    result["page_count"] = int(match.group(1))
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # mdls not available (non-macOS) or timed out
            pass

    def _extract_headings(self, text: str) -> list[str]:
        """Extract likely section headings from PDF text.

        Heuristic: short lines (< 80 chars) that are title-cased or all-caps,
        not ending in common sentence punctuation.
        """
        headings: list[str] = []
        for line in text.split("\n"):
            line = line.strip()
            if not line or len(line) > 80:
                continue
            # Skip lines ending in sentence punctuation
            if line[-1] in ".,:;":
                continue
            # Check for title case or all caps
            if line.isupper() or (line.istitle() and len(line.split()) <= 8):
                headings.append(line)
            if len(headings) >= 20:
                break
        return headings

    def _detect_tables(self, text: str) -> bool:
        """Detect if the text likely contains tables.

        Looks for lines with multiple tab characters or pipe separators.
        """
        table_line_count = 0
        for line in text.split("\n"):
            if line.count("\t") >= 2 or line.count("|") >= 2:
                table_line_count += 1
            if table_line_count >= 3:
                return True
        return False
