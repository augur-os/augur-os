"""Smoke tests for IDE health checks (no network dependency)."""

from __future__ import annotations

from skills.ai.augur.adapters.registry import get_registry  # noqa: E402
from src.lib.ai.ide_intent import Intent, AdapterOutputType  # noqa: E402


def test_registry_initialization():
    """Test that registry can be initialized and contains adapters."""
    registry = get_registry()
    adapters = registry.get_all()

    assert len(adapters) > 0, "Registry should contain at least one adapter"

    # Check that expected adapters are registered
    adapter_names = [a.ide_name for a in adapters]
    assert (
        "cursor" in adapter_names or "vscode_copilot" in adapter_names
    ), "Should have at least one IDE adapter registered"


def test_adapter_detect():
    """Test that adapters can detect IDE installation (may return False if not installed)."""
    registry = get_registry()

    for adapter in registry.get_all():
        detection = adapter.detect()

        # Detection should return a dict with expected keys
        assert isinstance(detection, dict), f"{adapter.ide_name}: detect() should return dict"
        assert "installed" in detection, f"{adapter.ide_name}: detect() should include 'installed'"
        assert isinstance(detection["installed"], bool), f"{adapter.ide_name}: 'installed' should be bool"

        # Optional keys
        if "running" in detection:
            assert isinstance(detection["running"], bool), f"{adapter.ide_name}: 'running' should be bool"


def test_adapter_health_check_structure():
    """Test that health_check returns expected structure (may fail if not configured)."""
    registry = get_registry()

    for adapter in registry.get_all():
        health = adapter.health_check()

        # Health check should return a dict with expected keys
        assert isinstance(health, dict), f"{adapter.ide_name}: health_check() should return dict"
        assert "healthy" in health, f"{adapter.ide_name}: health_check() should include 'healthy'"
        assert isinstance(health["healthy"], bool), f"{adapter.ide_name}: 'healthy' should be bool"
        assert "status" in health, f"{adapter.ide_name}: health_check() should include 'status'"
        assert "checks" in health, f"{adapter.ide_name}: health_check() should include 'checks'"
        assert isinstance(health["checks"], dict), f"{adapter.ide_name}: 'checks' should be dict"
        assert "last_check" in health, f"{adapter.ide_name}: health_check() should include 'last_check'"


def test_adapter_render_intent():
    """Test that adapters can render a simple intent."""
    registry = get_registry()

    test_intent = Intent(action="help", params={})

    for adapter in registry.get_all():
        try:
            output = adapter.render_intent(test_intent)

            # Output should be an AdapterOutput
            assert output is not None, f"{adapter.ide_name}: render_intent() should return output"
            assert hasattr(output, "output_type"), f"{adapter.ide_name}: output should have output_type"
            assert hasattr(output, "content"), f"{adapter.ide_name}: output should have content"
            assert isinstance(output.content, str), f"{adapter.ide_name}: output.content should be str"
        except NotImplementedError:
            # Some adapters might not implement this yet
            pass


def test_adapter_execution_modes():
    """Test that adapters declare execution modes."""
    registry = get_registry()

    for adapter in registry.get_all():
        mode = adapter.get_execution_mode()
        assert isinstance(mode, str), f"{adapter.ide_name}: get_execution_mode() should return str"
        assert mode in [
            "mcp",
            "chat_prompt",
            "cli",
            "workflow",
            "config_only",
            "sdk",
            "api",
            "file_dispatch",
        ], f"{adapter.ide_name}: execution mode should be valid"

        fallbacks = adapter.get_supported_fallbacks()
        assert isinstance(fallbacks, list), f"{adapter.ide_name}: get_supported_fallbacks() should return list"


def test_intent_model():
    """Test that Intent model works correctly."""
    intent = Intent(
        action="create_skill",
        params={"name": "test-skill", "patterns": ["inbox", "database"]},
        context={"workspace": "/test"},
    )

    assert intent.action == "create_skill"
    assert intent.params["name"] == "test-skill"
    assert intent.context["workspace"] == "/test"


def test_adapter_output_types():
    """Test that AdapterOutputType enum works."""

    assert AdapterOutputType.MCP_CALL == "mcp_call"
    assert AdapterOutputType.CHAT_PROMPT == "chat_prompt"
    assert AdapterOutputType.CLI_COMMAND == "cli_command"
    assert AdapterOutputType.WORKFLOW_YAML == "workflow_yaml"
    assert AdapterOutputType.CONFIG_PATCH == "config_patch"


if __name__ == "__main__":
    """Run smoke tests."""
    # Try to use pytest if available, otherwise use basic test runner
    try:
        import pytest

        pytest.main([__file__, "-v"])
    except ImportError:
        # Fallback to basic test runner
        print("Running basic smoke tests...")

        tests = [
            test_registry_initialization,
            test_adapter_detect,
            test_adapter_health_check_structure,
            test_adapter_render_intent,
            test_adapter_execution_modes,
            test_intent_model,
            test_adapter_output_types,
        ]

        passed = 0
        failed = 0

        for test in tests:
            try:
                test()
                print(f"✅ {test.__name__}")
                passed += 1
            except Exception as e:
                print(f"❌ {test.__name__}: {e}")
                failed += 1

        print(f"\nResults: {passed} passed, {failed} failed")
        sys.exit(0 if failed == 0 else 1)
