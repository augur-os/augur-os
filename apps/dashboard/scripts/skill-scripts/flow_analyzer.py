"""Flow analyzer: infer dashboard layout from a ScanManifest (ADR-086 Stage 1).

Input:  ScanManifest (from source_adapters/base.py)
Output: FlowAnalysis dataclass with suggested tabs, stat cards, actions,
        and per-file rendering strategy.

Heuristics
----------
- Excel with multiple sheets -> one tab per sheet (or grouped tabs)
- Monthly file series (Budget-Jan.xlsx, Budget-Feb.xlsx) -> time-based view tab
- Nested directories -> folder-browser tab
- CSV / simple xlsx with <100 rows -> renderable table tab
- PDF with extractable text -> ai-analyze action
- Large/complex Excel -> summary stat cards + open-external
- Markdown (Notion export) -> rendered-content tab
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from .source_adapters.base import FileInfo, ScanManifest
except ImportError:
    from source_adapters.base import FileInfo, ScanManifest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Row limit for inline table rendering
TABLE_ROW_LIMIT = 100

# Month patterns to detect time series files
MONTH_PATTERN = re.compile(
    r"(?i)[-_ ]"
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|"
    r"q[1-4]|"
    r"20\d{2}[-_]?\d{0,2})"
)

# Lucide icon suggestions per file type
ICON_MAP: dict[str, str] = {
    "xlsx": "FileSpreadsheet",
    "xls": "FileSpreadsheet",
    "csv": "FileSpreadsheet",
    "pdf": "FileText",
    "md": "FileType",
    "json": "FileJson",
    "txt": "FileText",
    "directory": "FolderOpen",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class StatCard:
    """A stat card to display on the overview tab."""

    id: str
    label: str
    source_file: str
    extraction: dict[str, Any] = field(default_factory=dict)
    icon: str = "BarChart3"
    format: str = "number"  # number, currency, percent, text


@dataclass
class SuggestedTab:
    """A suggested tab for the hub."""

    id: str
    label: str
    icon: str = "LayoutDashboard"
    description: str = ""
    source_files: list[str] = field(default_factory=list)
    tab_type: str = "table"  # table, time-series, folder-browser, rendered-content, overview


@dataclass
class SuggestedAction:
    """An action button for the hub."""

    id: str
    label: str
    icon: str = "Zap"
    dispatch: str = "oneshot"  # oneshot, fire, modal
    source_file: str = ""
    description: str = ""


@dataclass
class FileStrategy:
    """Per-file rendering strategy."""

    path: str
    mode: str  # render-table, stat-card, ai-analyze, open-external, ignore, rendered-content
    tab: str | None = None  # which tab this file contributes to
    reason: str = ""


@dataclass
class FlowAnalysis:
    """Complete flow analysis output for blueprint generation."""

    hub: str
    source_path: str
    suggested_tabs: list[SuggestedTab] = field(default_factory=list)
    stat_cards: list[StatCard] = field(default_factory=list)
    actions: list[SuggestedAction] = field(default_factory=list)
    file_strategies: list[FileStrategy] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON/YAML output."""
        return {
            "hub": self.hub,
            "source_path": self.source_path,
            "suggested_tabs": [
                {
                    "id": t.id,
                    "label": t.label,
                    "icon": t.icon,
                    "description": t.description,
                    "source_files": t.source_files,
                    "tab_type": t.tab_type,
                }
                for t in self.suggested_tabs
            ],
            "stat_cards": [
                {
                    "id": c.id,
                    "label": c.label,
                    "source_file": c.source_file,
                    "extraction": c.extraction,
                    "icon": c.icon,
                    "format": c.format,
                }
                for c in self.stat_cards
            ],
            "actions": [
                {
                    "id": a.id,
                    "label": a.label,
                    "icon": a.icon,
                    "dispatch": a.dispatch,
                    "source_file": a.source_file,
                    "description": a.description,
                }
                for a in self.actions
            ],
            "file_strategies": [
                {
                    "path": f.path,
                    "mode": f.mode,
                    "tab": f.tab,
                    "reason": f.reason,
                }
                for f in self.file_strategies
            ],
        }


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class FlowAnalyzer:
    """Analyze a ScanManifest and produce a FlowAnalysis.

    The analyzer applies heuristics in priority order to determine how each
    file should be represented in the generated hub dashboard.

    Args:
        hub: Hub identifier (e.g., "finance").
    """

    def __init__(self, hub: str) -> None:
        self.hub = hub

    def analyze(self, manifest: ScanManifest) -> FlowAnalysis:
        """Run flow analysis on a scan manifest.

        Args:
            manifest: ScanManifest from a source adapter.

        Returns:
            FlowAnalysis with suggested tabs, stat cards, actions, and
            per-file strategies.
        """
        result = FlowAnalysis(hub=self.hub, source_path=manifest.source_path)

        # Always start with an overview tab
        result.suggested_tabs.append(
            SuggestedTab(
                id="overview",
                label="Overview",
                icon="LayoutDashboard",
                description="Hub overview with key stats and external data",
                tab_type="overview",
            )
        )

        # Collect top-level files (skip nested children)
        top_level = [f for f in manifest.files if "/" not in f.path]

        # Detect time-series groups
        time_groups = self._detect_time_series(top_level)

        # Process each file
        for file_info in top_level:
            if file_info.is_directory:
                self._handle_directory(file_info, manifest, result)
                continue

            structure = manifest.file_structures.get(file_info.path, {})

            # Check if this file is part of a time-series group
            group_key = self._get_time_group_key(file_info, time_groups)
            if group_key:
                # Handled as part of the group below
                continue

            self._handle_file(file_info, structure, result)

        # Process time-series groups as tabs
        for group_name, group_files in time_groups.items():
            self._handle_time_series_group(group_name, group_files, manifest, result)

        return result

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    def _detect_time_series(self, files: list[FileInfo]) -> dict[str, list[FileInfo]]:
        """Detect files that form a time series (monthly/quarterly/yearly).

        Groups files by their base name (without the date portion).
        Only groups with 2+ files are considered time series.

        Returns:
            Dict mapping group name -> list of FileInfo.
        """
        groups: dict[str, list[FileInfo]] = {}

        for f in files:
            if f.is_directory:
                continue

            match = MONTH_PATTERN.search(f.name)
            if match:
                # Strip the date part to get the base name
                base = MONTH_PATTERN.sub("", Path(f.name).stem).strip("-_ ")
                if not base:
                    base = "data"
                key = _slugify(base)
                groups.setdefault(key, []).append(f)

        # Only keep groups with 2+ files
        return {k: v for k, v in groups.items() if len(v) >= 2}

    def _get_time_group_key(self, file_info: FileInfo, time_groups: dict[str, list[FileInfo]]) -> str | None:
        """Return the time-series group key if this file belongs to one."""
        for key, files in time_groups.items():
            if file_info in files:
                return key
        return None

    # ------------------------------------------------------------------
    # File type handlers
    # ------------------------------------------------------------------

    def _handle_directory(
        self,
        file_info: FileInfo,
        manifest: ScanManifest,
        result: FlowAnalysis,
    ) -> None:
        """Handle a directory entry: suggest folder-browser tab."""
        tab_id = _slugify(file_info.name)
        result.suggested_tabs.append(
            SuggestedTab(
                id=tab_id,
                label=_titleize(file_info.name),
                icon="FolderOpen",
                description=f"Browse files in {file_info.name}/",
                source_files=[file_info.path],
                tab_type="folder-browser",
            )
        )
        result.file_strategies.append(
            FileStrategy(
                path=file_info.path,
                mode="open-external",
                tab=tab_id,
                reason="Directory -> folder-browser tab",
            )
        )

    def _handle_file(
        self,
        file_info: FileInfo,
        structure: dict[str, Any],
        result: FlowAnalysis,
    ) -> None:
        """Handle a single file based on type and structure."""
        ext = file_info.extension

        if ext in ("xlsx", "xls", "csv"):
            self._handle_spreadsheet(file_info, structure, result)
        elif ext == "pdf":
            self._handle_pdf(file_info, structure, result)
        elif ext == "md":
            self._handle_markdown(file_info, structure, result)
        else:
            self._handle_generic(file_info, result)

    def _handle_spreadsheet(
        self,
        file_info: FileInfo,
        structure: dict[str, Any],
        result: FlowAnalysis,
    ) -> None:
        """Handle Excel/CSV files."""
        sheets = structure.get("sheets", [])
        row_count = structure.get("row_count", 0)
        has_totals = structure.get("has_totals", False)
        totals_cells = structure.get("totals_cells", [])

        stem = _slugify(Path(file_info.name).stem)

        # Stat cards from totals
        if has_totals and totals_cells:
            for tc in totals_cells[:5]:
                card_id = _slugify(tc.get("label", "value"))
                result.stat_cards.append(
                    StatCard(
                        id=f"{stem}-{card_id}",
                        label=tc.get("label", "Value"),
                        source_file=file_info.path,
                        extraction={
                            "sheet": tc.get("sheet", ""),
                            "cell": tc.get("cell", ""),
                        },
                        icon="BarChart3",
                        format="number",
                    )
                )

        # Multi-sheet Excel -> one tab per sheet (or one data tab for the file)
        if len(sheets) > 1:
            for sheet in sheets:
                sheet_id = _slugify(sheet.get("name", "sheet"))
                tab_id = f"{stem}-{sheet_id}"
                s_rows = sheet.get("row_count", 0)
                tab_type = "table" if s_rows <= TABLE_ROW_LIMIT else "table"

                result.suggested_tabs.append(
                    SuggestedTab(
                        id=tab_id,
                        label=f"{_titleize(Path(file_info.name).stem)} - {sheet['name']}",
                        icon="FileSpreadsheet",
                        description=f"Sheet '{sheet['name']}' ({s_rows} rows)",
                        source_files=[file_info.path],
                        tab_type=tab_type,
                    )
                )

            result.file_strategies.append(
                FileStrategy(
                    path=file_info.path,
                    mode="render-table",
                    tab=f"{stem}-{_slugify(sheets[0].get('name', 'sheet'))}",
                    reason=f"Multi-sheet Excel ({len(sheets)} sheets) -> per-sheet tabs",
                )
            )

        elif row_count > 0 and row_count <= TABLE_ROW_LIMIT:
            # Small dataset -> render as table tab
            tab_id = stem
            result.suggested_tabs.append(
                SuggestedTab(
                    id=tab_id,
                    label=_titleize(Path(file_info.name).stem),
                    icon="FileSpreadsheet",
                    description=f"Data table ({row_count} rows)",
                    source_files=[file_info.path],
                    tab_type="table",
                )
            )
            result.file_strategies.append(
                FileStrategy(
                    path=file_info.path,
                    mode="render-table",
                    tab=tab_id,
                    reason=f"Small spreadsheet ({row_count} rows) -> renderable table",
                )
            )

        elif has_totals:
            # Large file with totals -> stat cards + open external
            result.file_strategies.append(
                FileStrategy(
                    path=file_info.path,
                    mode="stat-card",
                    tab="overview",
                    reason="Large spreadsheet with totals -> stat cards on overview",
                )
            )

        else:
            # Large, no totals -> just open external
            result.file_strategies.append(
                FileStrategy(
                    path=file_info.path,
                    mode="open-external",
                    tab=None,
                    reason="Large spreadsheet, no totals -> open-external only",
                )
            )

        # Always add open-external action for spreadsheets
        result.actions.append(
            SuggestedAction(
                id=f"open-{stem}",
                label=f"Open {file_info.name}",
                icon="FileSpreadsheet",
                dispatch="fire",
                source_file=file_info.path,
                description=f"Open {file_info.name} in its default application",
            )
        )

    def _handle_pdf(
        self,
        file_info: FileInfo,
        structure: dict[str, Any],
        result: FlowAnalysis,
    ) -> None:
        """Handle PDF files."""
        stem = _slugify(Path(file_info.name).stem)
        text_extractable = structure.get("text_extractable", False)

        if text_extractable:
            result.actions.append(
                SuggestedAction(
                    id=f"analyze-{stem}",
                    label=f"Analyze {file_info.name}",
                    icon="Brain",
                    dispatch="oneshot",
                    source_file=file_info.path,
                    description=f"AI analysis of {file_info.name}",
                )
            )
            result.file_strategies.append(
                FileStrategy(
                    path=file_info.path,
                    mode="ai-analyze",
                    tab=None,
                    reason="PDF with extractable text -> ai-analyze action",
                )
            )
        else:
            result.file_strategies.append(
                FileStrategy(
                    path=file_info.path,
                    mode="open-external",
                    tab=None,
                    reason="PDF without extractable text -> open-external only",
                )
            )

        result.actions.append(
            SuggestedAction(
                id=f"open-{stem}",
                label=f"Open {file_info.name}",
                icon="FileText",
                dispatch="fire",
                source_file=file_info.path,
                description=f"Open {file_info.name} in Preview",
            )
        )

    def _handle_markdown(
        self,
        file_info: FileInfo,
        structure: dict[str, Any],
        result: FlowAnalysis,
    ) -> None:
        """Handle Markdown (Notion export) files."""
        stem = _slugify(Path(file_info.name).stem)
        title = structure.get("title", _titleize(Path(file_info.name).stem))

        tab_id = stem
        result.suggested_tabs.append(
            SuggestedTab(
                id=tab_id,
                label=title,
                icon="FileType",
                description=f"Rendered content from {file_info.name}",
                source_files=[file_info.path],
                tab_type="rendered-content",
            )
        )

        result.actions.append(
            SuggestedAction(
                id=f"analyze-{stem}",
                label=f"Analyze {title}",
                icon="Brain",
                dispatch="oneshot",
                source_file=file_info.path,
                description=f"AI analysis of {title}",
            )
        )

        result.file_strategies.append(
            FileStrategy(
                path=file_info.path,
                mode="rendered-content",
                tab=tab_id,
                reason="Markdown file -> rendered-content tab",
            )
        )

    def _handle_generic(self, file_info: FileInfo, result: FlowAnalysis) -> None:
        """Handle any other file type: open-external."""
        stem = _slugify(Path(file_info.name).stem)

        result.actions.append(
            SuggestedAction(
                id=f"open-{stem}",
                label=f"Open {file_info.name}",
                icon=ICON_MAP.get(file_info.extension, "FileText"),
                dispatch="fire",
                source_file=file_info.path,
                description=f"Open {file_info.name} in its default application",
            )
        )
        result.file_strategies.append(
            FileStrategy(
                path=file_info.path,
                mode="open-external",
                tab=None,
                reason=f"Generic file type ({file_info.extension}) -> open-external",
            )
        )

    def _handle_time_series_group(
        self,
        group_name: str,
        files: list[FileInfo],
        manifest: ScanManifest,
        result: FlowAnalysis,
    ) -> None:
        """Handle a group of time-series files as a single time-based tab."""
        tab_id = f"{group_name}-timeline"
        file_paths = [f.path for f in files]

        result.suggested_tabs.append(
            SuggestedTab(
                id=tab_id,
                label=f"{_titleize(group_name)} Timeline",
                icon="CalendarDays",
                description=f"Time-based view of {len(files)} files",
                source_files=file_paths,
                tab_type="time-series",
            )
        )

        for f in files:
            result.file_strategies.append(
                FileStrategy(
                    path=f.path,
                    mode="render-table",
                    tab=tab_id,
                    reason=f"Part of time-series group '{group_name}' ({len(files)} files)",
                )
            )

            # Extract stat cards from each file if it has totals
            structure = manifest.file_structures.get(f.path, {})
            if structure.get("has_totals") and structure.get("totals_cells"):
                for tc in structure["totals_cells"][:3]:
                    card_id = _slugify(tc.get("label", "value"))
                    stem = _slugify(Path(f.name).stem)
                    result.stat_cards.append(
                        StatCard(
                            id=f"{stem}-{card_id}",
                            label=f"{tc.get('label', 'Value')} ({Path(f.name).stem})",
                            source_file=f.path,
                            extraction={
                                "sheet": tc.get("sheet", ""),
                                "cell": tc.get("cell", ""),
                            },
                        )
                    )


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Convert text to kebab-case slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower())
    return slug.strip("-") or "item"


def _titleize(text: str) -> str:
    """Convert a slug or filename stem to Title Case."""
    return re.sub(r"[-_]+", " ", text).strip().title()
