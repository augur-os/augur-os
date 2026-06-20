"""Behavior tests for the setup MCP tools (get-setup-status, set-setup-skipped)."""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SETUP_DIR = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "onboard" / "scripts" / "setup"
MCP_DIR = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "onboard" / "scripts" / "mcp"

SETUP_PKG = "onboard_setup_pkg"
MCP_PKG = "onboard_mcp_pkg"


def _ensure_package(pkg_name: str, pkg_dir: Path) -> None:
    if pkg_name in sys.modules:
        return
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    spec = importlib.util.spec_from_file_location(
        pkg_name,
        pkg_dir / "__init__.py",
        submodule_search_locations=[str(pkg_dir)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[pkg_name] = module
    spec.loader.exec_module(module)


_ensure_package(SETUP_PKG, SETUP_DIR)
_ensure_package(MCP_PKG, MCP_DIR)

aggregator = importlib.import_module(f"{SETUP_PKG}.aggregator")
setup_status_tools = importlib.import_module(f"{MCP_PKG}.setup_status_tools")

# The MCP tool resolves its own imports via try/except — wire its lookup
# functions to use the test packages we just constructed.
state = importlib.import_module(f"{SETUP_PKG}.state")
setup_status_tools._aggregator_imports = lambda: (aggregator.clear_cache, aggregator.compute_setup_status)
setup_status_tools._state_imports = lambda: (state.load_persisted_state, state.save_skipped)


class FakeMcp:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, name: str):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


class FakeMetrics:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def track_tool(self, name: str, *, skill: str) -> None:
        self.calls.append((name, skill))


def _passthrough(func):
    return func


@pytest.mark.asyncio
async def test_get_setup_status_tool_returns_setup_status_payload(setup_env) -> None:
    aggregator.clear_cache()
    mcp = FakeMcp()
    metrics = FakeMetrics()

    setup_status_tools.register_tools(mcp, _passthrough, metrics)
    payload = json.loads(await mcp.tools["get-setup-status"](skip_cache=True))

    assert payload["version"] == 1
    assert payload["total"] == 12
    assert payload["state"] == "card"
    assert ("get_setup_status", "onboard") in metrics.calls


@pytest.mark.asyncio
async def test_set_setup_skipped_tool_persists_preference(setup_env) -> None:
    aggregator.clear_cache()
    mcp = FakeMcp()
    metrics = FakeMetrics()

    setup_status_tools.register_tools(mcp, _passthrough, metrics)
    payload = json.loads(await mcp.tools["set-setup-skipped"]("integration", skipped=True))

    assert payload == {"success": True, "skipped": ["integration"]}
    assert "integration" in (setup_env.runtime_dir / "preferences.yaml").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_set_setup_skipped_tool_removes_when_unskipped(setup_env) -> None:
    aggregator.clear_cache()
    mcp = FakeMcp()
    metrics = FakeMetrics()
    setup_status_tools.register_tools(mcp, _passthrough, metrics)

    await mcp.tools["set-setup-skipped"]("integration", skipped=True)
    payload = json.loads(await mcp.tools["set-setup-skipped"]("integration", skipped=False))

    assert payload == {"success": True, "skipped": []}


@pytest.mark.asyncio
async def test_get_setup_status_tool_reports_error_payload_on_failure(setup_env, monkeypatch) -> None:
    aggregator.clear_cache()
    mcp = FakeMcp()
    metrics = FakeMetrics()
    setup_status_tools.register_tools(mcp, _passthrough, metrics)

    def _boom(*args, **kwargs):
        raise RuntimeError("induced failure")

    monkeypatch.setattr(
        setup_status_tools,
        "_aggregator_imports",
        lambda: (aggregator.clear_cache, _boom),
    )

    payload = json.loads(await mcp.tools["get-setup-status"](skip_cache=True))

    assert payload["success"] is False
    assert "induced failure" in payload["error"]
