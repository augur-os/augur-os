"""Tests for verify_action_wiring.py — action dispatch and endpoint validation."""

import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from verify_action_wiring import (
    _split_segments,
    _trim_issues,
    endpoint_exists,
    parse_actions,
)


class TestParseActions:
    """Tests for YAML action file parsing."""

    def test_parse_single_dict(self, tmp_path):
        f = tmp_path / "action.yaml"
        f.write_text(yaml.dump({"id": "test-action", "dispatch": "fire", "endpoint": "/api/test"}))
        actions, issues = parse_actions(f)
        assert len(actions) == 1
        assert actions[0]["id"] == "test-action"
        assert len(issues) == 0

    def test_parse_list_of_dicts(self, tmp_path):
        f = tmp_path / "actions.yaml"
        data = [
            {"id": "a1", "dispatch": "fire"},
            {"id": "a2", "dispatch": "ide"},
        ]
        f.write_text(yaml.dump(data))
        actions, issues = parse_actions(f)
        assert len(actions) == 2

    def test_parse_empty_yaml(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text("")
        actions, issues = parse_actions(f)
        assert len(actions) == 0
        assert len(issues) == 1
        assert "Empty YAML" in issues[0]

    def test_parse_invalid_yaml(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text(":\n  bad: yaml\n  - broken: [")
        actions, issues = parse_actions(f)
        assert len(actions) == 0
        assert len(issues) == 1
        assert "YAML parse error" in issues[0]

    def test_parse_unsupported_structure(self, tmp_path):
        f = tmp_path / "string.yaml"
        f.write_text('"just a string"')
        actions, issues = parse_actions(f)
        assert len(actions) == 0
        assert any("Unsupported" in i for i in issues)


class TestEndpointExists:
    """Tests for endpoint matching against known routes."""

    def test_exact_match(self):
        routes = {"/api/test", "/api/users"}
        assert endpoint_exists("/api/test", routes) is True
        assert endpoint_exists("/api/missing", routes) is False

    def test_strips_query_params(self):
        routes = {"/api/test"}
        assert endpoint_exists("/api/test?foo=bar", routes) is True

    def test_strips_trailing_slash(self):
        routes = {"/api/test"}
        assert endpoint_exists("/api/test/", routes) is True

    def test_dynamic_segment_matching(self):
        routes = {"/api/users/[id]"}
        assert endpoint_exists("/api/users/123", routes) is True
        assert endpoint_exists("/api/users/abc", routes) is True

    def test_dynamic_segment_wrong_length(self):
        routes = {"/api/users/[id]"}
        assert endpoint_exists("/api/users/123/extra", routes) is False


class TestSplitSegments:
    """Tests for URL segment splitting."""

    def test_basic_path(self):
        assert _split_segments("/api/test") == ["api", "test"]

    def test_trailing_slash(self):
        assert _split_segments("/api/test/") == ["api", "test"]

    def test_empty_path(self):
        assert _split_segments("/") == []
        assert _split_segments("") == []


class TestTrimIssues:
    """Tests for issue trimming."""

    def test_no_trim_needed(self):
        items = ["a", "b"]
        trimmed, hidden = _trim_issues(items, max_items=10)
        assert trimmed == items
        assert hidden == 0

    def test_trim_over_limit(self):
        items = list(range(200))
        trimmed, hidden = _trim_issues(items, max_items=100)
        assert len(trimmed) == 100
        assert hidden == 100
