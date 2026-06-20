"""Integration planner: assigns integration modes to scanned files (ADR-086).

Input: ScanManifest from a source adapter.
Output: A connections.yaml draft with per-file mode assignments.

Modes:
    summary        - Read specific values, show as stat cards
    ai-analyze     - Button feeds file content to AI
    open-external  - Button opens file in native app
    page-candidate - File maps to a dashboard tab/page (L1 only)
    ignore         - No integration
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .source_adapters.base import FileInfo, ScanManifest
except ImportError:
    from source_adapters.base import FileInfo, ScanManifest

# Files matching these patterns are auto-ignored
IGNORE_PATTERNS = [
    re.compile(r"\.DS_Store$"),
    re.compile(r"^\."),  # hidden files
    re.compile(r"Thumbs\.db$"),
    re.compile(r"desktop\.ini$"),
    re.compile(r"~\$"),  # Excel temp files
]

# Date patterns in filenames (e.g., "2020", "old-", "archive-")
DATED_OLD_PATTERNS = re.compile(r"(?i)(20[01]\d|201\d|old[-_]|archive[-_]|backup[-_]|deprecated)")

# Small file threshold (bytes) — files under this are likely metaconfig
SMALL_FILE_THRESHOLD = 512

# Row threshold for page-candidate mode (CSV/simple xlsx)
PAGE_CANDIDATE_MAX_ROWS = 100


@dataclass
class IntegrationItem:
    """A single integration assignment for a file or file group."""

    id: str
    file: str | None = None
    files: str | None = None  # glob pattern for file groups
    mode: str = "ignore"
    extractions: list[dict[str, Any]] = field(default_factory=list)
    action: dict[str, Any] = field(default_factory=dict)
    display: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dict suitable for connections.yaml."""
        result: dict[str, Any] = {"id": self.id, "mode": self.mode}
        if self.file:
            result["file"] = self.file
        if self.files:
            result["files"] = self.files
        if self.extractions:
            result["extractions"] = self.extractions
        if self.action:
            result["action"] = self.action
        if self.display:
            result["display"] = self.display
        return result


@dataclass
class IgnoredItem:
    """A file that was skipped during planning."""

    file: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"file": self.file, "reason": self.reason}


@dataclass
class IntegrationPlan:
    """The full integration plan for a source connection."""

    hub: str
    source_type: str
    source_path: str
    integrations: list[IntegrationItem] = field(default_factory=list)
    ignored: list[IgnoredItem] = field(default_factory=list)

    def to_connections_dict(self) -> dict[str, Any]:
        """Convert to a connections.yaml structure."""
        return {
            "version": 1,
            "hub": self.hub,
            "connections": [
                {
                    "id": f"{self.hub}-{self.source_type}",
                    "source_type": self.source_type,
                    "source_path": self.source_path,
                    "connected_at": datetime.now().isoformat(),
                    "integrations": [i.to_dict() for i in self.integrations],
                    "ignored": [i.to_dict() for i in self.ignored],
                }
            ],
        }


class IntegrationPlanner:
    """Assigns integration modes to files based on their structure.

    Rules (in priority order):
        1. System/hidden files -> ignore
        2. Dated/old/small files -> ignore
        3. Excel with totals -> summary + open-external
        4. Excel/CSV without totals, <100 rows -> page-candidate (L1) or open-external (L2)
        5. PDF with extractable text -> ai-analyze + open-external
        6. PDF without text -> open-external only
        7. Markdown (Notion) -> ai-analyze + open-external
        8. Directories -> open-external
        9. Everything else -> open-external

    Args:
        hub: Hub identifier (e.g., "finance").
        level: 1 for /import (allows page-candidate), 2 for Connect (no code gen).
        overrides: Optional dict of path -> mode to override auto-assignment.
    """

    def __init__(
        self,
        hub: str,
        *,
        level: int = 2,
        overrides: dict[str, str] | None = None,
    ) -> None:
        self.hub = hub
        self.level = level
        self.overrides = overrides or {}

    def plan(self, manifest: ScanManifest) -> IntegrationPlan:
        """Generate an integration plan from a scan manifest.

        Args:
            manifest: ScanManifest from a source adapter.

        Returns:
            IntegrationPlan with per-file mode assignments.
        """
        result = IntegrationPlan(
            hub=self.hub,
            source_type=manifest.source_type,
            source_path=manifest.source_path,
        )

        # Process only top-level files (children are part of directory entries)
        top_level_files = [f for f in manifest.files if "/" not in f.path]

        for file_info in top_level_files:
            # Check for user override first
            if file_info.path in self.overrides:
                override_mode = self.overrides[file_info.path]
                if override_mode == "ignore":
                    result.ignored.append(IgnoredItem(file=file_info.path, reason="User override"))
                else:
                    result.integrations.append(
                        IntegrationItem(
                            id=self._make_id(file_info),
                            file=file_info.path,
                            mode=override_mode,
                        )
                    )
                continue

            # Check ignore rules
            ignore_reason = self._should_ignore(file_info)
            if ignore_reason:
                result.ignored.append(IgnoredItem(file=file_info.path, reason=ignore_reason))
                continue

            # Get file structure if available
            structure = manifest.file_structures.get(file_info.path, {})

            # Assign modes based on file type and structure
            items = self._assign_modes(file_info, structure)
            result.integrations.extend(items)

        return result

    def _should_ignore(self, file_info: FileInfo) -> str | None:
        """Return ignore reason if file should be skipped, None otherwise."""
        # Check ignore patterns
        for pattern in IGNORE_PATTERNS:
            if pattern.search(file_info.name):
                return "System file"

        # Check for dated/old files
        if DATED_OLD_PATTERNS.search(file_info.name):
            return "Dated, low relevance"

        # Check for very small files (likely metadata)
        if not file_info.is_directory and file_info.size < SMALL_FILE_THRESHOLD:
            return "Too small (likely metadata)"

        return None

    def _assign_modes(self, file_info: FileInfo, structure: dict[str, Any]) -> list[IntegrationItem]:
        """Assign one or more integration modes to a file."""
        items: list[IntegrationItem] = []
        file_type = file_info.extension

        if file_info.is_directory:
            items.append(self._make_directory_integration(file_info, structure))

        elif file_type in ("xlsx", "xls", "csv"):
            items.extend(self._make_excel_integrations(file_info, structure))

        elif file_type == "pdf":
            items.extend(self._make_pdf_integrations(file_info, structure))

        elif file_type == "md":
            items.extend(self._make_markdown_integrations(file_info, structure))

        else:
            # Default: open in native app
            items.append(
                IntegrationItem(
                    id=self._make_id(file_info, "open"),
                    file=file_info.path,
                    mode="open-external",
                    action={
                        "label": f"Open {file_info.name}",
                        "icon": "FileText",
                    },
                )
            )

        return items

    def _make_excel_integrations(self, file_info: FileInfo, structure: dict[str, Any]) -> list[IntegrationItem]:
        """Create integrations for Excel/CSV files."""
        items: list[IntegrationItem] = []
        has_totals = structure.get("has_totals", False)
        row_count = structure.get("row_count", 0)
        totals_cells = structure.get("totals_cells", [])

        # If totals detected, add summary mode
        if has_totals and totals_cells:
            extractions = []
            for tc in totals_cells[:10]:  # cap at 10 extractions
                extractions.append(
                    {
                        "id": self._slugify(tc.get("label", "value")),
                        "label": tc.get("label", "Value"),
                        "sheet": tc.get("sheet", ""),
                        "cell": tc.get("cell", ""),
                        "format": "number",
                    }
                )
            items.append(
                IntegrationItem(
                    id=self._make_id(file_info, "summary"),
                    file=file_info.path,
                    mode="summary",
                    extractions=extractions,
                    display={
                        "type": "stat-cards",
                        "tab": "overview",
                        "section": "external-data",
                    },
                )
            )

        # Small files (L1 only) can be rendered as tables
        if (
            self.level == 1
            and row_count > 0
            and row_count <= PAGE_CANDIDATE_MAX_ROWS
            and not structure.get("has_formulas", False)
        ):
            items.append(
                IntegrationItem(
                    id=self._make_id(file_info, "page"),
                    file=file_info.path,
                    mode="page-candidate",
                )
            )

        # Always add open-external for spreadsheets
        items.append(
            IntegrationItem(
                id=self._make_id(file_info, "open"),
                file=file_info.path,
                mode="open-external",
                action={
                    "label": f"Open in {'Excel' if file_info.extension != 'csv' else 'default app'}",
                    "icon": "FileSpreadsheet",
                },
            )
        )

        return items

    def _make_pdf_integrations(self, file_info: FileInfo, structure: dict[str, Any]) -> list[IntegrationItem]:
        """Create integrations for PDF files."""
        items: list[IntegrationItem] = []
        text_extractable = structure.get("text_extractable", False)

        if text_extractable:
            items.append(
                IntegrationItem(
                    id=self._make_id(file_info, "analyze"),
                    file=file_info.path,
                    mode="ai-analyze",
                    action={
                        "label": f"Analyze {file_info.name}",
                        "icon": "Brain",
                        "dispatch": "oneshot",
                        "prompt_context": (
                            f"You are analyzing {file_info.name}. "
                            "Extract key information, summarize the content, "
                            "and highlight important points."
                        ),
                    },
                )
            )

        items.append(
            IntegrationItem(
                id=self._make_id(file_info, "open"),
                file=file_info.path,
                mode="open-external",
                action={
                    "label": f"Open {file_info.name}",
                    "icon": "FileText",
                },
            )
        )

        return items

    def _make_markdown_integrations(self, file_info: FileInfo, structure: dict[str, Any]) -> list[IntegrationItem]:
        """Create integrations for markdown (Notion export) files."""
        items: list[IntegrationItem] = []

        title = structure.get("title", file_info.name)
        items.append(
            IntegrationItem(
                id=self._make_id(file_info, "analyze"),
                file=file_info.path,
                mode="ai-analyze",
                action={
                    "label": f"Analyze {title}",
                    "icon": "Brain",
                    "dispatch": "oneshot",
                    "prompt_context": (
                        f"You are analyzing a Notion page: {title}. "
                        "Summarize the content and extract key information."
                    ),
                },
            )
        )

        items.append(
            IntegrationItem(
                id=self._make_id(file_info, "open"),
                file=file_info.path,
                mode="open-external",
                action={
                    "label": f"Open {file_info.name}",
                    "icon": "FileText",
                },
            )
        )

        return items

    def _make_directory_integration(self, file_info: FileInfo, structure: dict[str, Any]) -> IntegrationItem:
        """Create integration for a directory."""
        return IntegrationItem(
            id=self._make_id(file_info, "open"),
            file=file_info.path,
            mode="open-external",
            action={
                "label": f"Open {file_info.name}",
                "icon": "FolderOpen",
            },
        )

    def _make_id(self, file_info: FileInfo, suffix: str = "") -> str:
        """Generate a kebab-case integration ID from filename."""
        base = self._slugify(Path(file_info.name).stem)
        if suffix:
            return f"{base}-{suffix}"
        return base

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to kebab-case slug."""
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower())
        return slug.strip("-")
