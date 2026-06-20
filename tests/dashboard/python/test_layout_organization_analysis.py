"""Tests for layout_organization_analysis.py — page layout analysis and suggestions."""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from layout_organization_analysis import (
    analyze_page_structure,
    suggest_cross_page_organization,
)


class TestAnalyzePageStructure:
    """Tests for single-page layout analysis."""

    def test_empty_blocks(self):
        result = analyze_page_structure("/test/page", [])
        assert result["page"] == "/test/page"
        assert result["metrics"]["total_blocks"] == 0
        assert result["metrics"]["content_density"] == "low"
        assert len(result["issues"]) == 0

    def test_single_block_low_density(self):
        blocks = [{"id": "stats", "title": "Stats", "layout": "full"}]
        result = analyze_page_structure("/agents/overview", blocks)
        assert result["metrics"]["content_density"] == "low"
        assert result["metrics"]["full_width_blocks"] == 1

    def test_medium_density(self):
        blocks = [
            {"id": "a", "title": "A", "layout": "grid"},
            {"id": "b", "title": "B", "layout": "full"},
        ]
        result = analyze_page_structure("/test", blocks)
        assert result["metrics"]["content_density"] == "medium"

    def test_high_density(self):
        blocks = [
            {"id": "a", "title": "A", "layout": "grid"},
            {"id": "b", "title": "B", "layout": "grid"},
            {"id": "c", "title": "C", "layout": "full"},
            {"id": "d", "title": "D", "layout": "grid"},
        ]
        result = analyze_page_structure("/test", blocks)
        assert result["metrics"]["content_density"] == "high"

    def test_grid_cramping_issue(self):
        blocks = [
            {"id": "a", "title": "Agents", "layout": "grid", "purpose": "status"},
            {"id": "b", "title": "Health", "layout": "grid", "purpose": "health"},
            {"id": "c", "title": "Pipeline", "layout": "full", "purpose": "workflow"},
        ]
        result = analyze_page_structure("/agents/workforce", blocks)
        assert any(i["type"] == "grid_cramping" for i in result["issues"])

    def test_infrastructure_block_move_suggestion(self):
        blocks = [
            {"id": "workforce", "title": "Workforce Status", "purpose": "agents"},
            {"id": "pipeline", "title": "CI/CD Pipeline", "purpose": "pipeline"},
        ]
        result = analyze_page_structure("/agents/workforce", blocks)
        assert any(s["type"] == "move_block" and s["to_page"] == "/agents/devops" for s in result["suggestions"])

    def test_design_pattern_notes_present(self):
        result = analyze_page_structure("/test", [])
        assert len(result["design_pattern_notes"]) > 0
        assert any("gradient" in note.lower() for note in result["design_pattern_notes"])


class TestSuggestCrossPageOrganization:
    """Tests for cross-page reorganization suggestions."""

    def test_empty_pages(self):
        suggestions = suggest_cross_page_organization([])
        assert suggestions == []

    def test_infrastructure_block_on_wrong_page(self):
        pages = [
            {
                "page": "/agents/workforce",
                "blocks": [
                    {"id": "pipeline", "title": "CI/CD Pipeline"},
                ],
            },
        ]
        suggestions = suggest_cross_page_organization(pages)
        assert len(suggestions) >= 1
        assert suggestions[0]["to_page"] == "/agents/devops"

    def test_infrastructure_on_devops_no_suggestion(self):
        pages = [
            {
                "page": "/agents/devops",
                "blocks": [
                    {"id": "pipeline", "title": "GitHub Workflow"},
                ],
            },
        ]
        suggestions = suggest_cross_page_organization(pages)
        assert len(suggestions) == 0

    def test_non_infra_blocks_no_suggestion(self):
        pages = [
            {
                "page": "/agents/overview",
                "blocks": [
                    {"id": "stats", "title": "Quick Stats"},
                    {"id": "recent", "title": "Recent Activity"},
                ],
            },
        ]
        suggestions = suggest_cross_page_organization(pages)
        assert len(suggestions) == 0
