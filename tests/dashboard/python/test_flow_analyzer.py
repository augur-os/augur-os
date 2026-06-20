"""Tests for flow_analyzer.py — ScanManifest analysis and tab/action inference."""

import sys
from datetime import datetime
from pathlib import Path

SKILL_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "apps" / "dashboard" / "scripts" / "skill-scripts"
if str(SKILL_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS_DIR))

from flow_analyzer import (
    MONTH_PATTERN,
    FlowAnalysis,
    FlowAnalyzer,
    _slugify,
    _titleize,
)
from source_adapters.base import FileInfo, ScanManifest


def _make_file(name: str, size: int = 100, file_type: str = "", is_dir: bool = False) -> FileInfo:
    """Helper to create a FileInfo with minimal boilerplate."""
    ft = file_type or (name.rsplit(".", 1)[-1] if "." in name else "")
    return FileInfo(
        name=name,
        path=name,
        size=size,
        modified=datetime.now(),
        file_type=ft,
        is_directory=is_dir,
    )


def _make_manifest(files: list[FileInfo], structures: dict | None = None) -> ScanManifest:
    return ScanManifest(
        source_type="folder",
        source_path="/test/data",
        files=files,
        file_structures=structures or {},
    )


class TestSlugify:
    """Tests for the _slugify utility."""

    def test_basic_text(self):
        assert _slugify("Hello World") == "hello-world"

    def test_special_characters(self):
        assert _slugify("Budget (2024)") == "budget-2024"  # non-alpha chars become dashes, collapsed and stripped

    def test_empty_string(self):
        assert _slugify("") == "item"

    def test_already_slugified(self):
        assert _slugify("my-slug") == "my-slug"


class TestTitleize:
    """Tests for the _titleize utility."""

    def test_kebab_case(self):
        assert _titleize("hello-world") == "Hello World"

    def test_underscore_case(self):
        assert _titleize("my_project") == "My Project"

    def test_mixed_separators(self):
        assert _titleize("my-cool_project") == "My Cool Project"


class TestMonthPattern:
    """Tests for time-series month detection regex."""

    def test_detects_month_names(self):
        assert MONTH_PATTERN.search("Budget-January")
        assert MONTH_PATTERN.search("Budget-Jan")
        assert MONTH_PATTERN.search("Report_Feb")
        assert MONTH_PATTERN.search("data-Q1")

    def test_detects_year_patterns(self):
        assert MONTH_PATTERN.search("Budget-2024")
        assert MONTH_PATTERN.search("Report_202401")

    def test_no_match_on_plain_names(self):
        assert MONTH_PATTERN.search("README") is None
        assert MONTH_PATTERN.search("notes") is None


class TestFlowAnalyzer:
    """Tests for the FlowAnalyzer.analyze method."""

    def test_always_creates_overview_tab(self):
        analyzer = FlowAnalyzer("test-hub")
        manifest = _make_manifest([])
        result = analyzer.analyze(manifest)
        assert any(t.id == "overview" for t in result.suggested_tabs)

    def test_directory_creates_folder_browser_tab(self):
        analyzer = FlowAnalyzer("test-hub")
        files = [_make_file("receipts", is_dir=True)]
        manifest = _make_manifest(files)
        result = analyzer.analyze(manifest)
        tabs_ids = [t.id for t in result.suggested_tabs]
        assert "receipts" in tabs_ids
        browser_tab = next(t for t in result.suggested_tabs if t.id == "receipts")
        assert browser_tab.tab_type == "folder-browser"

    def test_small_csv_creates_table_tab(self):
        analyzer = FlowAnalyzer("finance")
        files = [_make_file("expenses.csv")]
        structures = {"expenses.csv": {"row_count": 50, "sheets": [], "has_totals": False}}
        manifest = _make_manifest(files, structures)
        result = analyzer.analyze(manifest)
        strategy = next(s for s in result.file_strategies if s.path == "expenses.csv")
        assert strategy.mode == "render-table"

    def test_pdf_with_text_creates_analyze_action(self):
        analyzer = FlowAnalyzer("finance")
        files = [_make_file("report.pdf")]
        structures = {"report.pdf": {"text_extractable": True}}
        manifest = _make_manifest(files, structures)
        result = analyzer.analyze(manifest)
        action_ids = [a.id for a in result.actions]
        assert any("analyze" in aid for aid in action_ids)

    def test_markdown_creates_rendered_content_tab(self):
        analyzer = FlowAnalyzer("docs")
        files = [_make_file("notes.md")]
        structures = {"notes.md": {"title": "My Notes"}}
        manifest = _make_manifest(files, structures)
        result = analyzer.analyze(manifest)
        strategy = next(s for s in result.file_strategies if s.path == "notes.md")
        assert strategy.mode == "rendered-content"


class TestFlowAnalysisToDict:
    """Tests for FlowAnalysis serialization."""

    def test_empty_analysis_serializes(self):
        analysis = FlowAnalysis(hub="test", source_path="/test")
        d = analysis.to_dict()
        assert d["hub"] == "test"
        assert d["source_path"] == "/test"
        assert d["suggested_tabs"] == []
        assert d["stat_cards"] == []
        assert d["actions"] == []
        assert d["file_strategies"] == []
