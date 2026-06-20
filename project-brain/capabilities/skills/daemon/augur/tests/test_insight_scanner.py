"""Tests for insight_scanner.py -- proactive page insight scanner."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SCRIPTS_PATH = Path(__file__).resolve().parents[2] / "scripts" / "insight_scanner.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import the module by path to match existing test patterns
_spec = importlib.util.spec_from_file_location("insight_scanner", SCRIPTS_PATH)
insight_scanner = importlib.util.module_from_spec(_spec)
sys.modules["insight_scanner"] = insight_scanner

# Stub runtime_paths before exec_module so insight_scanner can import it
import types

_rp = types.ModuleType("runtime_paths")
_rp.get_notification_history_path = lambda: Path("/tmp/augur-test/history.yaml")
_rp.get_notification_pending_path = lambda: Path("/tmp/augur-test/pending.yaml")
_rp.get_notification_preferences_path = lambda: Path("/tmp/augur-test/preferences.yaml")
_rp.get_notifications_runtime_dir = lambda: Path("/tmp/augur-test/notifications")
_rp.get_insights_archive_dir = lambda: Path("/tmp/augur-test/archive")
_rp.get_insights_config_path = lambda: Path("/tmp/augur-test/config.yaml")
_rp.get_insights_path = lambda: Path("/tmp/augur-test/insights.yaml")
sys.modules["runtime_paths"] = _rp

assert _spec.loader is not None
_spec.loader.exec_module(insight_scanner)

Insight = insight_scanner.Insight


class TestInsight:
    """Tests for the Insight dataclass."""

    def test_round_trip_dict(self):
        i = Insight(
            id="abc",
            page="/career",
            category="workflow",
            title="Add filters",
            description="Add filter controls",
            score=80,
            status="candidate",
            created_at="2026-01-01T00:00:00",
        )
        d = i.to_dict()
        i2 = Insight.from_dict(d)
        assert i2.id == "abc"
        assert i2.page == "/career"
        assert i2.score == 80

    def test_from_dict_ignores_extra_fields(self):
        data = {
            "id": "x",
            "page": "/home",
            "category": "workflow",
            "title": "T",
            "description": "D",
            "score": 50,
            "unknown_field": "ignored",
        }
        i = Insight.from_dict(data)
        assert i.id == "x"
        assert not hasattr(i, "unknown_field") or "unknown_field" not in i.to_dict()


class TestGetQualifyingPages:
    """Tests for filtering pages by usage threshold."""

    def test_filters_by_minimum_views(self):
        usage = {
            "/career": {"views_7d": 10},
            "/home": {"views_7d": 1},
            "/dev": {"views_7d": 5},
        }
        config = {"pages": {"min_views_7d": 3}}
        result = insight_scanner.get_qualifying_pages(usage, config)
        pages = [r["page"] for r in result]
        assert "/career" in pages
        assert "/dev" in pages
        assert "/home" not in pages

    def test_empty_usage_returns_empty_list(self):
        result = insight_scanner.get_qualifying_pages({}, {"pages": {"min_views_7d": 1}})
        assert result == []

    def test_non_dict_stats_skipped(self):
        usage = {"/foo": "not-a-dict", "/bar/baz": {"views_7d": 5}}
        config = {"pages": {"min_views_7d": 1}}
        result = insight_scanner.get_qualifying_pages(usage, config)
        assert len(result) == 1
        assert result[0]["page"] == "/bar/baz"


class TestMergeNewInsights:
    """Tests for insight deduplication during merge."""

    def test_deduplicates_by_page_and_title(self):
        existing = [
            Insight(id="1", page="/a", category="workflow", title="Add X", description="d", score=70),
        ]
        new = [
            Insight(id="2", page="/a", category="workflow", title="Add X", description="d2", score=80),
            Insight(id="3", page="/b", category="workflow", title="Add Y", description="d3", score=60),
        ]
        merged = insight_scanner.merge_new_insights(existing, new)
        assert len(merged) == 2  # existing + one new (not the dup)
        ids = [i.id for i in merged]
        assert "1" in ids
        assert "3" in ids

    def test_empty_new_returns_existing(self):
        existing = [Insight(id="1", page="/a", category="workflow", title="T", description="d", score=50)]
        merged = insight_scanner.merge_new_insights(existing, [])
        assert len(merged) == 1


class TestPromoteInsights:
    """Tests for promoting candidates to pending status."""

    def test_promotes_above_threshold(self):
        insights = [
            Insight(id="1", page="/a", category="workflow", title="T1", description="d", score=80, status="candidate"),
            Insight(id="2", page="/b", category="workflow", title="T2", description="d", score=50, status="candidate"),
            Insight(id="3", page="/c", category="workflow", title="T3", description="d", score=90, status="pending"),
        ]
        promoted = insight_scanner.promote_insights(insights, threshold=70)
        assert len(promoted) == 1
        assert promoted[0].id == "1"
        assert insights[0].status == "pending"
        assert insights[1].status == "candidate"  # below threshold


class TestParseLlmJsonArray:
    """Tests for extracting JSON arrays from LLM output."""

    def test_direct_json_array(self):
        output = '[{"title": "X", "score": 80}]'
        result = insight_scanner._parse_llm_json_array(output)
        assert len(result) == 1
        assert result[0]["title"] == "X"

    def test_markdown_fenced_json(self):
        output = 'Here are my suggestions:\n```json\n[{"title": "Y"}]\n```\nDone.'
        result = insight_scanner._parse_llm_json_array(output)
        assert len(result) == 1

    def test_embedded_array(self):
        output = 'Some text before [{"title": "Z"}] and after'
        result = insight_scanner._parse_llm_json_array(output)
        assert len(result) == 1

    def test_invalid_json_returns_empty(self):
        result = insight_scanner._parse_llm_json_array("not json at all")
        assert result == []

    def test_dict_with_insights_key(self):
        output = json.dumps({"insights": [{"title": "A"}]})
        result = insight_scanner._parse_llm_json_array(output)
        assert len(result) == 1


class TestSafeYamlWrite:
    def test_replaces_existing_file(self, tmp_path):
        path = tmp_path / "insights.yaml"
        path.write_text("old: true\n", encoding="utf-8")

        insight_scanner._safe_yaml_write(path, {"new": True})

        assert path.read_text(encoding="utf-8") == "new: true\n"
        assert not list(tmp_path.glob("*.tmp"))


class TestRunLoop:
    def test_effectively_disabled_interval_sleeps_without_scan(self, monkeypatch):
        class StopLoop(Exception):
            pass

        scans: list[dict] = []
        sleeps: list[int] = []

        monkeypatch.setattr(insight_scanner, "_load_service_interval", lambda: 876000)
        monkeypatch.setattr(insight_scanner, "run_scan", lambda config: scans.append(config))

        def fake_sleep(seconds: int) -> None:
            sleeps.append(seconds)
            raise StopLoop

        monkeypatch.setattr(insight_scanner.time, "sleep", fake_sleep)

        with pytest.raises(StopLoop):
            insight_scanner.run_loop({})

        assert scans == []
        assert sleeps == [876000 * 3600]
