"""NotionAnalyzer: extract structure from Notion-exported markdown files (ADR-086)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class NotionAnalyzer:
    """Analyze Notion-exported markdown files to extract structure.

    Returns a FileStructure dict with:
        - type: "notion_md"
        - title: page title (first H1 or filename)
        - headings: list of {level, text} dicts
        - has_tables: whether markdown tables were detected
        - has_databases: whether database-style tables were detected
        - linked_pages: list of internal links to other pages
    """

    def analyze(self, path: Path) -> dict[str, Any]:
        """Analyze a markdown file (typically Notion export).

        Args:
            path: Path to the .md file.

        Returns:
            FileStructure dict.
        """
        path = Path(path)
        result: dict[str, Any] = {
            "type": "notion_md",
            "title": path.stem,
            "headings": [],
            "has_tables": False,
            "has_databases": False,
            "linked_pages": [],
        }

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            result["error"] = str(e)
            return result

        lines = text.split("\n")

        headings: list[dict[str, Any]] = []
        table_row_count = 0
        table_separator_count = 0
        linked_pages: list[str] = []

        for line in lines:
            stripped = line.strip()

            # Extract headings
            heading_match = re.match(r"^(#{1,6})\s+(.+)", stripped)
            if heading_match:
                level = len(heading_match.group(1))
                text_content = heading_match.group(2).strip()
                headings.append({"level": level, "text": text_content})
                # Use first H1 as title
                if level == 1 and result["title"] == path.stem:
                    result["title"] = text_content

            # Detect markdown tables (lines starting with |)
            if stripped.startswith("|") and stripped.endswith("|"):
                if re.match(r"^\|[\s\-:|]+\|$", stripped):
                    table_separator_count += 1
                else:
                    table_row_count += 1

            # Detect internal links (Notion-style: [Page Name](page-id))
            for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", stripped):
                link_text = match.group(1)
                link_target = match.group(2)
                # Notion exports use relative paths or UUIDs, not http URLs
                if not link_target.startswith(("http://", "https://", "#")):
                    linked_pages.append(link_text)

        result["headings"] = headings
        result["has_tables"] = table_separator_count > 0 and table_row_count >= 2
        # A "database" in Notion exports as a markdown table with many rows
        result["has_databases"] = table_separator_count > 0 and table_row_count >= 5
        result["linked_pages"] = list(dict.fromkeys(linked_pages))  # dedupe, preserve order

        return result
