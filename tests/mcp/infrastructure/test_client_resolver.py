"""Tests for ClientResolver — per-action AI client routing."""

import pytest
from unittest.mock import patch
from src.mcp.augur_framework.tools.infrastructure.client_resolver import ClientResolver, ResolvedClient


@pytest.fixture
def resolver():
    return ClientResolver()


def _prefs(*, airplane_enabled=False, default_client=None, overrides=None):
    """Build a mock preferences dict."""
    return {
        "airplane_mode": {"enabled": airplane_enabled},
        "client_routing": {
            "default_client": default_client,
            "overrides": overrides or {},
        },
    }


class TestResolutionChain:
    """Priority: airplane > local_flag > override > global > implicit."""

    def test_implicit_default_when_no_config(self, resolver):
        with patch.object(resolver, "_load_prefs", return_value=_prefs()):
            result = resolver.resolve("some-action")
        assert result.source == "implicit"

    def test_global_default(self, resolver):
        prefs = _prefs(default_client="codex")
        with patch.object(resolver, "_load_prefs", return_value=prefs):
            result = resolver.resolve("some-action")
        assert result.client_id == "codex"
        assert result.source == "global"

    def test_override_beats_global(self, resolver):
        prefs = _prefs(default_client="claude-code", overrides={"job-search": "codex"})
        with patch.object(resolver, "_load_prefs", return_value=prefs):
            result = resolver.resolve("job-search")
        assert result.client_id == "codex"
        assert result.source == "override"

    def test_local_flag_beats_override(self, resolver):
        prefs = _prefs(overrides={"job-search": "codex"})
        with patch.object(resolver, "_load_prefs", return_value=prefs):
            result = resolver.resolve("job-search", local_flag=True)
        assert result.client_id == "ollama"
        assert result.source == "local_flag"

    def test_airplane_beats_everything(self, resolver):
        prefs = _prefs(airplane_enabled=True, default_client="claude-code", overrides={"job-search": "codex"})
        with patch.object(resolver, "_load_prefs", return_value=prefs):
            result = resolver.resolve("job-search")
        assert result.client_id == "ollama"
        assert result.source == "airplane"

    def test_action_without_override_falls_through(self, resolver):
        prefs = _prefs(default_client="claude-code", overrides={"other": "codex"})
        with patch.object(resolver, "_load_prefs", return_value=prefs):
            result = resolver.resolve("unrelated-action")
        assert result.client_id == "claude-code"
        assert result.source == "global"


class TestResolvedClient:
    def test_dataclass_fields(self):
        rc = ResolvedClient(client_id="ollama", client_type="local", model="qwen3.5:9b", source="airplane")
        assert rc.client_id == "ollama"
        assert rc.client_type == "local"
        assert rc.model == "qwen3.5:9b"
        assert rc.source == "airplane"
