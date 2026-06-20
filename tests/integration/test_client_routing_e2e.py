"""Integration test for client routing end-to-end flow."""

import pytest

import yaml

from src.mcp.augur_framework.tools.infrastructure.client_resolver import ClientResolver


@pytest.fixture
def temp_prefs(tmp_path):
    """Create a temporary preferences file."""
    prefs_path = tmp_path / "preferences.yaml"
    prefs_path.write_text(
        yaml.dump(
            {
                "airplane_mode": {"enabled": False},
                "local_backends": {"ollama": {"model": "qwen3.5:9b"}},
                "client_routing": {
                    "default_client": "claude-code",
                    "overrides": {},
                },
            }
        )
    )
    return prefs_path


class TestEndToEndRouting:
    def test_full_override_lifecycle(self, temp_prefs):
        resolver = ClientResolver(prefs_path=temp_prefs)

        # Initially: global default
        result = resolver.resolve("career-search")
        assert result.client_id == "claude-code"
        assert result.source == "global"

        # Set override
        resolver.set_override("career-search", "codex")
        result = resolver.resolve("career-search")
        assert result.client_id == "codex"
        assert result.source == "override"

        # Other actions unaffected
        result = resolver.resolve("health-track")
        assert result.client_id == "claude-code"
        assert result.source == "global"

        # Clear override
        resolver.clear_override("career-search")
        result = resolver.resolve("career-search")
        assert result.client_id == "claude-code"
        assert result.source == "global"

    def test_airplane_overrides_all(self, temp_prefs):
        resolver = ClientResolver(prefs_path=temp_prefs)
        resolver.set_override("career-search", "codex")

        # Enable airplane
        prefs = yaml.safe_load(temp_prefs.read_text())
        prefs["airplane_mode"]["enabled"] = True
        temp_prefs.write_text(yaml.dump(prefs))

        result = resolver.resolve("career-search")
        assert result.client_id == "ollama"
        assert result.source == "airplane"
        assert result.model == "qwen3.5:9b"

    def test_local_flag_overrides_override(self, temp_prefs):
        resolver = ClientResolver(prefs_path=temp_prefs)
        resolver.set_override("career-search", "codex")

        result = resolver.resolve("career-search", local_flag=True)
        assert result.client_id == "ollama"
        assert result.source == "local_flag"

    def test_list_overrides(self, temp_prefs):
        resolver = ClientResolver(prefs_path=temp_prefs)
        resolver.set_override("a", "codex")
        resolver.set_override("b", "ollama")

        overrides = resolver.list_overrides()
        assert overrides == {"a": "codex", "b": "ollama"}

    def test_set_default(self, temp_prefs):
        resolver = ClientResolver(prefs_path=temp_prefs)
        resolver.set_default("antigravity")

        result = resolver.resolve("any-action")
        assert result.client_id == "antigravity"
        assert result.source == "global"
