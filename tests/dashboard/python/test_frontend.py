"""
Tests for frontend skill: pattern compliance, component audit,
design token documentation, and UI ranking functions.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

# Add the scripts directory to path for imports
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Tests for component_audit.py
# ---------------------------------------------------------------------------


class TestFindComponents:
    """Tests for component discovery functions."""

    def test_find_components_empty_dir(self, tmp_path):
        from component_audit import find_components

        result = find_components(tmp_path)
        assert result == []

    def test_find_components_with_tsx_files(self, tmp_path):
        from component_audit import find_components

        components_dir = tmp_path / "components"
        components_dir.mkdir()

        # Create a valid component
        comp_file = components_dir / "Button.tsx"
        comp_file.write_text("'use client'\nexport default function Button() { return <button>Click</button> }\n")

        # Create a test file (should be excluded)
        test_file = components_dir / "Button.test.tsx"
        test_file.write_text("test content")

        # Create an underscore-prefixed file (should be excluded)
        hidden = components_dir / "_internal.tsx"
        hidden.write_text("internal stuff")

        result = find_components(tmp_path)
        assert len(result) == 1
        assert result[0]["name"] == "Button"
        assert result[0]["is_client"] is True
        assert result[0]["is_component"] is True

    def test_find_components_detects_server_component(self, tmp_path):
        from component_audit import find_components

        components_dir = tmp_path / "components"
        components_dir.mkdir()

        server_comp = components_dir / "Header.tsx"
        server_comp.write_text("export function Header() { return <h1>Title</h1> }\n")

        result = find_components(tmp_path)
        assert len(result) == 1
        assert result[0]["is_client"] is False


class TestFindComponentUsage:
    """Tests for component usage counting."""

    def test_find_component_usage_counts_jsx(self, tmp_path):
        from component_audit import find_component_usage

        app_dir = tmp_path / "app"
        app_dir.mkdir()

        page = app_dir / "page.tsx"
        page.write_text(
            "import Button from './Button'\nexport default function Page() {\n"
            "  return <div><Button /><Button variant='primary'>Submit</Button></div>\n}\n"
        )

        usage = find_component_usage(tmp_path, {"Button", "Modal"})
        assert usage["Button"] == 2
        assert usage["Modal"] == 0

    def test_find_component_usage_ignores_node_modules(self, tmp_path):
        from component_audit import find_component_usage

        node_dir = tmp_path / "node_modules" / "pkg"
        node_dir.mkdir(parents=True)
        pkg_file = node_dir / "index.tsx"
        pkg_file.write_text("<Button />")

        usage = find_component_usage(tmp_path, {"Button"})
        assert usage["Button"] == 0


class TestCheckDesignTokens:
    """Tests for design token checking."""

    def test_detects_hardcoded_colors(self, tmp_path):
        from component_audit import check_design_tokens

        app_dir = tmp_path / "app"
        app_dir.mkdir()

        page = app_dir / "page.tsx"
        page.write_text('<div className="bg-[#ff0000] text-[#333333]">Bad colors</div>\n')

        issues = check_design_tokens(tmp_path)
        assert len(issues) >= 2
        assert any("theme" in i["suggestion"].lower() for i in issues)

    def test_no_issues_with_proper_tokens(self, tmp_path):
        from component_audit import check_design_tokens

        app_dir = tmp_path / "app"
        app_dir.mkdir()

        page = app_dir / "page.tsx"
        page.write_text('<div className="bg-card text-foreground border-border">Good tokens</div>\n')

        issues = check_design_tokens(tmp_path)
        assert len(issues) == 0


class TestCheckTableStructure:
    """Tests for table structure validation."""

    def test_detects_th_without_width(self, tmp_path):
        from component_audit import check_table_structure

        app_dir = tmp_path / "app"
        app_dir.mkdir()

        page = app_dir / "table.tsx"
        page.write_text('<table><thead><tr><th className="text-left">Name</th></tr></thead></table>\n')

        issues = check_table_structure(tmp_path)
        assert len(issues) >= 1
        assert any("width" in i["suggestion"].lower() for i in issues)

    def test_no_issue_with_width_class(self, tmp_path):
        from component_audit import check_table_structure

        app_dir = tmp_path / "app"
        app_dir.mkdir()

        page = app_dir / "table.tsx"
        page.write_text('<table><thead><tr><th className="w-1/3 text-left">Name</th></tr></thead></table>\n')

        issues = check_table_structure(tmp_path)
        assert len(issues) == 0


class TestGenerateReport:
    """Tests for audit report generation."""

    def test_generate_report_creates_file(self, tmp_path):
        from component_audit import generate_report

        components = [
            {"name": "Button", "path": "components/Button.tsx", "lines": 50, "is_client": True, "is_component": True},
            {"name": "Modal", "path": "components/Modal.tsx", "lines": 120, "is_client": False, "is_component": True},
        ]
        usage = {"Button": 5, "Modal": 0}
        token_issues = [
            {"file": "app/page.tsx", "pattern": "bg-[#000]", "suggestion": "Use theme colors"},
        ]

        report_path = tmp_path / "report.md"
        report = generate_report(components, usage, token_issues, report_path)

        assert report_path.exists()
        assert "Design System Audit Report" in report
        assert "Modal" in report  # Unused component should be listed
        assert "bg-[#000]" in report


# ---------------------------------------------------------------------------
# Tests for document_tokens.py
# ---------------------------------------------------------------------------


class TestExtractCssVariables:
    """Tests for CSS variable extraction."""

    def test_extract_variables_from_css(self, tmp_path):
        from document_tokens import extract_css_variables

        css_file = tmp_path / "globals.css"
        css_file.write_text(
            ":root {\n"
            "  --background: #ffffff;\n"
            "  --foreground: #000000;\n"
            "  --font-sans: 'Inter', sans-serif;\n"
            "}\n"
        )

        variables = extract_css_variables(css_file)
        assert len(variables) == 3
        names = [v["name"] for v in variables]
        assert "--background" in names
        assert "--foreground" in names
        assert "--font-sans" in names

    def test_extract_variables_nonexistent_file(self, tmp_path):
        from document_tokens import extract_css_variables

        result = extract_css_variables(tmp_path / "nonexistent.css")
        assert result == []


class TestCategorizeTokens:
    """Tests for token categorization."""

    def test_categorize_colors(self):
        from document_tokens import categorize_tokens

        variables = [
            {"name": "--background-color", "value": "#ffffff"},
            {"name": "--text-primary", "value": "hsl(0, 0%, 0%)"},
            {"name": "--font-size", "value": "16px"},
            {"name": "--border-radius", "value": "8px"},
        ]

        categories = categorize_tokens(variables)
        assert len(categories["colors"]) >= 1
        assert len(categories["typography"]) >= 1
        assert len(categories["borders"]) >= 1

    def test_categorize_empty_list(self):
        from document_tokens import categorize_tokens

        categories = categorize_tokens([])
        assert all(len(v) == 0 for v in categories.values())


class TestGenerateDocumentation:
    """Tests for design token documentation generation."""

    def test_generate_documentation_format(self):
        from document_tokens import generate_documentation

        categories = {
            "colors": [{"name": "--bg", "value": "#fff"}],
            "typography": [],
            "spacing": [],
            "borders": [],
            "shadows": [],
            "other": [],
        }

        doc = generate_documentation(categories, [Path("test.css")])
        assert "# Design Tokens" in doc
        assert "Colors" in doc
        assert "--bg" in doc
        assert "Total tokens**: 1" in doc


# ---------------------------------------------------------------------------
# Tests for pattern_compliance_audit.py
# ---------------------------------------------------------------------------


class TestCheckGradientBackground:
    """Tests for gradient background compliance checks."""

    def test_compliant_gradient(self):
        from pattern_compliance_audit import check_gradient_background

        content = (
            'className="min-h-screen bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] '
            'from-indigo-950 via-slate-950 to-black text-white"'
        )
        result = check_gradient_background(content, "page.tsx")
        assert result["compliant"] is True
        assert len(result["issues"]) == 0

    def test_missing_gradient(self):
        from pattern_compliance_audit import check_gradient_background

        content = '<div className="bg-gray-900 text-white">'
        result = check_gradient_background(content, "page.tsx")
        assert result["compliant"] is False
        assert len(result["issues"]) >= 1
        assert result["issues"][0]["type"] == "missing_gradient_background"

    def test_wrong_colors(self):
        from pattern_compliance_audit import check_gradient_background

        content = (
            'className="bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] '
            'from-blue-900 via-gray-900 to-black text-white"'
        )
        result = check_gradient_background(content, "page.tsx")
        assert result["compliant"] is False
        # Should have an issue about incorrect colors
        assert any(i["type"] == "incorrect_gradient_colors" for i in result["issues"])


class TestCheckHeaderStructure:
    """Tests for header structure compliance."""

    def test_compliant_header(self):
        from pattern_compliance_audit import check_header_structure

        content = (
            '<header className="flex items-center justify-between mb-8 border-b border-white/10 pb-4">\n'
            '  <div className="flex items-center gap-3">\n'
            '    <div className="p-2 bg-blue-500/20 rounded-lg border border-blue-500/50">\n'
            '      <Icon className="w-6 h-6 text-blue-400" />\n'
            '    </div>\n'
            '    <div>\n'
            '      <h1 className="text-2xl font-bold tracking-tight text-white">Title</h1>\n'
            '      <p className="text-sm text-slate-400">Subtitle</p>\n'
            '    </div>\n'
            '  </div>\n'
            '</header>\n'
        )
        result = check_header_structure(content, "page.tsx")
        assert result["compliant"] is True

    def test_missing_header(self):
        from pattern_compliance_audit import check_header_structure

        content = '<div className="container"><h1>Title</h1></div>'
        result = check_header_structure(content, "page.tsx")
        assert result["compliant"] is False
        assert len(result["issues"]) >= 1


# ---------------------------------------------------------------------------
# Tests for rank_ui_visuals.py
# ---------------------------------------------------------------------------


class TestRankUiVisuals:
    """Tests for UI visual ranking function."""

    @patch("rank_ui_visuals._get_operations_dir")
    def test_rank_returns_score(self, mock_ops_dir, tmp_path):
        from rank_ui_visuals import rank_ui_visuals

        mock_ops_dir.return_value = tmp_path / "plugins" / "dev"

        result = rank_ui_visuals("/path/to/screenshot.png", {})
        assert "score" in result
        assert 0 <= result["score"] <= 10
        assert "criteria" in result
        assert "critique" in result
        assert "suggestions" in result

    @patch("rank_ui_visuals._get_operations_dir")
    def test_high_node_count_reduces_score(self, mock_ops_dir, tmp_path):
        from rank_ui_visuals import rank_ui_visuals

        mock_ops_dir.return_value = tmp_path / "plugins" / "dev"

        result_low = rank_ui_visuals("/path/to/screenshot.png", {"nodeCount": 100})
        result_high = rank_ui_visuals("/path/to/screenshot.png", {"nodeCount": 1500})

        assert result_high["score"] < result_low["score"]

    @patch("rank_ui_visuals._get_operations_dir")
    def test_rank_saves_retrospective(self, mock_ops_dir, tmp_path):
        from rank_ui_visuals import rank_ui_visuals

        mock_ops_dir.return_value = tmp_path / "plugins" / "dev"

        rank_ui_visuals("/path/to/screenshot.png", {})

        retro_dir = tmp_path / "plugins" / "dev" / "frontend" / "retrospectives"
        assert retro_dir.exists()
        retro_files = list(retro_dir.glob("ui_rank_*.json"))
        assert len(retro_files) == 1

        data = json.loads(retro_files[0].read_text())
        assert "timestamp" in data
        assert "feedback_score" in data
        assert "outcome" in data


class TestGetRepoRoot:
    """Tests for repo root discovery."""

    def test_get_repo_root_returns_path(self):
        from document_tokens import get_repo_root

        result = get_repo_root()
        assert isinstance(result, Path)
