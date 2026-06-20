"""Smoke test for the per-bundle MCP server launcher.

Verifies that `python -m augur_shared.bundle_server <bundle>` resolves
the bundle dir, calls register_tools, and would run a stdio loop.
We don't actually run the stdio loop in tests (it'd block); we
verify FastMCP receives the correct tools via mocked register.

    Track 3a PR 1 moved the canonical bundle_server to augur_shared.
    ADR-778 retired the legacy `augur_mcp.bundle_server` re-export shim.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


from src.mcp.augur_shared import bundle_server


def test_run_unknown_bundle_returns_1(capsys) -> None:
    rc = bundle_server.run("definitely-does-not-exist-bundle")
    assert rc == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err


def test_run_known_bundle_calls_register_tools(tmp_path: Path) -> None:
    """For an existing bundle, register_tools is invoked exactly once."""
    register_calls: list[tuple] = []

    fake_module = MagicMock()
    fake_module.__name__ = "plugin_scripts_apple_test.mcp"
    fake_module.register_tools = lambda mcp, interceptor, metrics: register_calls.append((mcp, interceptor, metrics))

    fake_dir = tmp_path / "apple"
    (fake_dir / "scripts" / "mcp").mkdir(parents=True, exist_ok=True)
    (fake_dir / "scripts" / "mcp" / "__init__.py").write_text("")

    fake_interceptor = MagicMock(name="mcp_tool_interceptor")
    fake_metrics = MagicMock(name="metrics")

    with (
        patch("src.mcp.augur_shared.bundle_server._load_bundle_mcp_module", return_value=fake_module),
        patch("src.mcp.augur_shared.bundle_server._pin_mcp_sdk_package"),
        patch("src.mcp.augur_shared.mcp_sdk.mcp_tool_interceptor", fake_interceptor),
        patch("src.mcp.augur_shared.mcp_sdk.metrics", fake_metrics),
        patch("src.mcp.augur_shared.bundle_server._collect_skill_dirs") as collect,
        patch("src.mcp.augur_shared.bundle_server.FastMCP") as fast_mcp_cls,
    ):
        collect.return_value = [("life/apple", fake_dir)]
        mcp_instance = MagicMock()
        fast_mcp_cls.return_value = mcp_instance

        rc = bundle_server.run("apple")
        assert rc == 0
        assert len(register_calls) == 1
        mcp_instance.run.assert_called_once()
