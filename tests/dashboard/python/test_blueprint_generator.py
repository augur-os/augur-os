"""Tests for blueprint_generator.py — blueprint generation from FlowAnalysis."""

import sys
from pathlib import Path

SKILL_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "apps" / "dashboard" / "scripts" / "skill-scripts"
if str(SKILL_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS_DIR))

from blueprint_generator import BlueprintGenerator, UserOverrides, _titleize
from flow_analyzer import (
    FileStrategy,
    FlowAnalysis,
    SuggestedAction,
    SuggestedTab,
    StatCard,
)


def _make_flow(hub: str = "finance") -> FlowAnalysis:
    """Create a minimal FlowAnalysis for testing."""
    return FlowAnalysis(
        hub=hub,
        source_path="/Users/test/Documents/Finance",
        suggested_tabs=[
            SuggestedTab(id="overview", label="Overview", tab_type="overview"),
            SuggestedTab(
                id="expenses", label="Expenses", icon="FileSpreadsheet", source_files=["expenses.csv"], tab_type="table"
            ),
        ],
        stat_cards=[
            StatCard(
                id="total-spend",
                label="Total Spend",
                source_file="expenses.csv",
                extraction={"sheet": "Sheet1", "cell": "B10"},
            ),
        ],
        actions=[
            SuggestedAction(id="open-expenses", label="Open Expenses", dispatch="fire", source_file="expenses.csv"),
        ],
        file_strategies=[
            FileStrategy(path="expenses.csv", mode="render-table", tab="expenses", reason="Small CSV"),
            FileStrategy(path="report.pdf", mode="open-external", tab=None, reason="PDF file"),
        ],
    )


class TestTitleize:
    """Tests for _titleize helper."""

    def test_slug_to_title(self):
        assert _titleize("my-project") == "My Project"

    def test_underscore_to_title(self):
        assert _titleize("budget_report") == "Budget Report"

    def test_plain_word(self):
        assert _titleize("finance") == "Finance"


class TestUserOverrides:
    """Tests for UserOverrides construction."""

    def test_defaults(self):
        overrides = UserOverrides()
        assert overrides.hub_bundle == "lifestyle"
        assert overrides.hub_category == "personal"
        assert overrides.tab_overrides == []
        assert overrides.extra_tabs == []

    def test_from_answers(self):
        answers = {
            "hub_title": "My Budget",
            "hub_icon": "DollarSign",
            "hub_bundle": "finance",
            "tab_overrides": [{"id": "expenses", "action": "rename", "label": "Spending"}],
        }
        overrides = UserOverrides.from_answers(answers)
        assert overrides.hub_title == "My Budget"
        assert overrides.hub_icon == "DollarSign"
        assert overrides.hub_bundle == "finance"
        assert len(overrides.tab_overrides) == 1

    def test_from_answers_defaults(self):
        overrides = UserOverrides.from_answers({})
        assert overrides.hub_title is None
        assert overrides.hub_bundle == "lifestyle"


class TestBlueprintGenerator:
    """Tests for BlueprintGenerator.generate."""

    def test_basic_generation(self):
        flow = _make_flow()
        gen = BlueprintGenerator(flow)
        bp = gen.generate()

        assert bp["version"] == 1
        assert bp["hub"]["id"] == "finance"
        assert bp["hub"]["title"] == "Finance"
        assert bp["source"]["path"] == "/Users/test/Documents/Finance"
        assert len(bp["tabs"]) == 2
        assert len(bp["stat_cards"]) == 1
        assert len(bp["actions"]) == 1

    def test_title_override(self):
        flow = _make_flow()
        overrides = UserOverrides(hub_title="My Budget Tracker")
        gen = BlueprintGenerator(flow, overrides)
        bp = gen.generate()

        assert bp["hub"]["title"] == "My Budget Tracker"

    def test_tab_removal(self):
        flow = _make_flow()
        overrides = UserOverrides(tab_overrides=[{"id": "expenses", "action": "remove"}])
        gen = BlueprintGenerator(flow, overrides)
        bp = gen.generate()

        tab_ids = [t["id"] for t in bp["tabs"]]
        assert "expenses" not in tab_ids
        assert "overview" in tab_ids

    def test_extra_tabs_added(self):
        flow = _make_flow()
        overrides = UserOverrides(extra_tabs=[{"id": "notes", "label": "Notes", "tab_type": "rendered-content"}])
        gen = BlueprintGenerator(flow, overrides)
        bp = gen.generate()

        tab_ids = [t["id"] for t in bp["tabs"]]
        assert "notes" in tab_ids

    def test_ignore_file_override(self):
        flow = _make_flow()
        overrides = UserOverrides(ignore_files=["report.pdf"])
        gen = BlueprintGenerator(flow, overrides)
        bp = gen.generate()

        pdf_strategy = next(s for s in bp["file_strategies"] if s["path"] == "report.pdf")
        assert pdf_strategy["mode"] == "ignore"

    def test_render_file_override(self):
        flow = _make_flow()
        overrides = UserOverrides(render_files=["report.pdf"])
        gen = BlueprintGenerator(flow, overrides)
        bp = gen.generate()

        pdf_strategy = next(s for s in bp["file_strategies"] if s["path"] == "report.pdf")
        assert pdf_strategy["mode"] == "render-table"


class TestBlueprintIconInference:
    """Tests for icon inference based on hub name."""

    def test_finance_icon(self):
        flow = _make_flow("finance")
        gen = BlueprintGenerator(flow)
        bp = gen.generate()
        assert bp["hub"]["icon"] == "DollarSign"

    def test_health_icon(self):
        flow = _make_flow("health")
        gen = BlueprintGenerator(flow)
        bp = gen.generate()
        assert bp["hub"]["icon"] == "Heart"

    def test_unknown_hub_default_icon(self):
        flow = _make_flow("something-unusual")
        gen = BlueprintGenerator(flow)
        bp = gen.generate()
        assert bp["hub"]["icon"] == "LayoutDashboard"

    def test_icon_override_takes_precedence(self):
        flow = _make_flow("finance")
        overrides = UserOverrides(hub_icon="Wallet")
        gen = BlueprintGenerator(flow, overrides)
        bp = gen.generate()
        assert bp["hub"]["icon"] == "Wallet"
