"""Tests for system MCP helpers."""

from __future__ import annotations

import textwrap
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def test_load_module_from_path_registers_module_for_dataclasses(tmp_path: Path) -> None:
    from src.mcp.augur_framework.tools.infrastructure.system import _load_module_from_path

    module_path = tmp_path / "temp_dataclass_module.py"
    module_path.write_text(
        textwrap.dedent("""
            from dataclasses import dataclass

            @dataclass
            class Demo:
                value: int = 1
            """),
        encoding="utf-8",
    )

    module = _load_module_from_path("temp_dataclass_module", module_path)

    demo = module.Demo()
    assert demo.value == 1
    assert module.__name__ == "temp_dataclass_module"


def test_resolve_client_runtime_dir_maps_known_dashboard_keys() -> None:
    from src.mcp.augur_framework.tools.infrastructure.system import _resolve_client_runtime_dir

    with patch(
        "src.config.paths.get_client_runtime_dir",
        side_effect=lambda client: Path(f"/tmp/{client}"),
    ):
        assert _resolve_client_runtime_dir("codex") == Path("/tmp/codex")
        assert _resolve_client_runtime_dir("claudeCode") == Path("/tmp/claude-code")
        assert _resolve_client_runtime_dir("gemini") == Path("/tmp/gemini")


class _CapturingMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, name=None, *args, **kwargs):
        tool_name = kwargs.get("name") or name

        def decorator(func):
            self.tools[tool_name or func.__name__] = func
            return func

        return decorator


def test_register_system_tools_exposes_permissions_status_for_settings(
    monkeypatch,
) -> None:
    from src.mcp.augur_framework.tools.infrastructure import system

    monkeypatch.setattr(system.sys, "platform", "darwin")
    monkeypatch.setattr(
        system.shutil,
        "which",
        lambda command: "/opt/homebrew/bin/tesseract" if command == "tesseract" else None,
    )

    mcp = _CapturingMCP()
    metrics = SimpleNamespace(track_tool=lambda *args, **kwargs: None)
    system.register_system_tools(mcp, lambda func: func, metrics)

    assert "check-system-permissions" in mcp.tools

    payload = json.loads(asyncio.run(mcp.tools["check-system-permissions"]()))  # type: ignore[index,operator]

    assert payload["ok"] is True
    assert payload["platform"] == "darwin"
    permissions = {item["id"]: item for item in payload["permissions"]}
    assert permissions["screen_recording"]["category"] == "macos_system"
    assert permissions["apple_mail"]["category"] == "email_calendar"
    assert permissions["tesseract"]["status"] == "granted"
    assert permissions["ffmpeg"]["status"] == "not_configured"
