"""Tests for routine-vault MCP wrapper functions."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from src.mcp.augur_core.tools.core import hygiene as mod


def _run(coro):
    return asyncio.run(coro)


def test_create_selection_wrapper_returns_selection(monkeypatch):
    calls: list[dict[str, Any]] = []

    class FakeSelectionModule:
        @staticmethod
        def create_selection(**kwargs):
            calls.append(kwargs)
            return {
                "success": True,
                "selection_id": "browse-sweep-20260513-120000-abcdef12",
                "selection_path": "/tmp/selection.json",
                "target_count": 1,
                "refusal_count": 0,
                "refusals": [],
            }

    monkeypatch.setattr(mod, "_load_skill_module", lambda *args: FakeSelectionModule)

    payload = _run(
        mod.hygiene_create_selection_impl(
            "sources",
            None,
            [{"source_id": "doc1"}],
        )
    )

    data = json.loads(payload)
    assert data["success"] is True
    assert data["selection_id"] == "browse-sweep-20260513-120000-abcdef12"
    assert calls == [
        {
            "source_tab": "sources",
            "filter_summary": {},
            "targets": [{"source_id": "doc1"}],
        }
    ]


def test_scan_selection_wrapper_reads_selection_and_scans(monkeypatch):
    selection = {"selection_id": "browse-sweep-20260513-120000-abcdef12"}
    calls: list[dict[str, Any]] = []

    class FakeSelectionModule:
        @staticmethod
        def read_selection(selection_id: str):
            calls.append({"read_selection": selection_id})
            return selection

    class FakeScanModule:
        @staticmethod
        def hygiene_scan_selection(scan_selection):
            calls.append({"hygiene_scan_selection": scan_selection})
            return {
                "selection_id": scan_selection["selection_id"],
                "candidate_count": 1,
                "files": [{"source_id": "doc1"}],
            }

    def fake_load(module_filename: str, spec_name: str):
        if module_filename == "sweep_selection.py":
            return FakeSelectionModule
        if module_filename == "hygiene_scan.py":
            return FakeScanModule
        raise AssertionError(module_filename)

    monkeypatch.setattr(mod, "_load_skill_module", fake_load)

    payload = _run(mod.hygiene_scan_selection_impl("browse-sweep-20260513-120000-abcdef12"))

    data = json.loads(payload)
    assert data["success"] is True
    assert data["candidate_count"] == 1
    assert calls == [
        {"read_selection": "browse-sweep-20260513-120000-abcdef12"},
        {"hygiene_scan_selection": selection},
    ]


def test_apply_selection_wrapper_reads_selection_and_defaults_to_dry_run(monkeypatch):
    selection = {"selection_id": "browse-sweep-20260513-120000-abcdef12"}
    moves = [{"source_id": "doc1", "reason": "superseded"}]
    calls: list[dict[str, Any]] = []

    class FakeSelectionModule:
        @staticmethod
        def read_selection(selection_id: str):
            calls.append({"read_selection": selection_id})
            return selection

    class FakeApplyModule:
        @staticmethod
        def hygiene_apply_selection(**kwargs):
            calls.append(kwargs)
            return {
                "selection_id": kwargs["selection"]["selection_id"],
                "dry_run": kwargs["dry_run"],
                "moves": [{"status": "would_succeed"}],
            }

    def fake_load(module_filename: str, spec_name: str):
        if module_filename == "sweep_selection.py":
            return FakeSelectionModule
        if module_filename == "hygiene_apply.py":
            return FakeApplyModule
        raise AssertionError(module_filename)

    monkeypatch.setattr(mod, "_load_skill_module", fake_load)

    payload = _run(mod.hygiene_apply_selection_impl(selection["selection_id"], moves))

    data = json.loads(payload)
    assert data["success"] is True
    assert data["dry_run"] is True
    assert calls == [
        {"read_selection": selection["selection_id"]},
        {"selection": selection, "moves": moves, "dry_run": True},
    ]


def test_scan_selection_wrapper_returns_expected_read_error(monkeypatch):
    class FakeSelectionModule:
        @staticmethod
        def read_selection(selection_id: str):
            raise ValueError(f"selection not found: {selection_id}")

    monkeypatch.setattr(mod, "_load_skill_module", lambda *args: FakeSelectionModule)

    payload = _run(mod.hygiene_scan_selection_impl("browse-sweep-20260513-120000-abcdef12"))

    data = json.loads(payload)
    assert data == {
        "success": False,
        "error": "selection not found: browse-sweep-20260513-120000-abcdef12",
    }


def test_apply_selection_wrapper_returns_unexpected_error(monkeypatch):
    class FakeSelectionModule:
        @staticmethod
        def read_selection(selection_id: str):
            return {"selection_id": selection_id}

    class FakeApplyModule:
        @staticmethod
        def hygiene_apply_selection(**kwargs):
            raise RuntimeError("boom")

    def fake_load(module_filename: str, spec_name: str):
        if module_filename == "sweep_selection.py":
            return FakeSelectionModule
        if module_filename == "hygiene_apply.py":
            return FakeApplyModule
        raise AssertionError(module_filename)

    monkeypatch.setattr(mod, "_load_skill_module", fake_load)

    payload = _run(
        mod.hygiene_apply_selection_impl(
            "browse-sweep-20260513-120000-abcdef12",
            [{"source_id": "doc1"}],
            dry_run=False,
        )
    )

    data = json.loads(payload)
    assert data == {"success": False, "error": "unexpected error: boom"}


def test_register_core_tools_exposes_selection_hygiene_tools(monkeypatch):
    from src.mcp.augur_core.tools import core

    class CapturingMCP:
        def __init__(self) -> None:
            self.tools = {}
            self.annotations = {}

        def tool(self, *args, **kwargs):
            name = kwargs.get("name")
            annotations = kwargs.get("annotations")

            def decorator(func):
                self.tools[name or func.__name__] = func
                self.annotations[name or func.__name__] = annotations
                return func

            return decorator

    async def fake_create(source_tab, filter_summary, targets):
        return json.dumps({"success": True, "tool": "create", "source_tab": source_tab})

    async def fake_scan(selection_id):
        return json.dumps({"success": True, "tool": "scan", "selection_id": selection_id})

    async def fake_apply(selection_id, moves, dry_run=True):
        return json.dumps({"success": True, "tool": "apply", "dry_run": dry_run})

    monkeypatch.setattr(core, "hygiene_create_selection_impl", fake_create)
    monkeypatch.setattr(core, "hygiene_scan_selection_impl", fake_scan)
    monkeypatch.setattr(core, "hygiene_apply_selection_impl", fake_apply)

    mcp = CapturingMCP()
    core.register_core_tools(
        mcp,
        registry_list_skills=lambda *args, **kwargs: [],
        resolve_skill_entry=lambda *args, **kwargs: None,
        available_skill_ids=lambda *args, **kwargs: [],
    )

    assert "hygiene-create-selection" in mcp.tools
    assert "hygiene-scan-selection" in mcp.tools
    assert "hygiene-apply-selection" in mcp.tools
    scan_annotations = mcp.annotations["hygiene-scan-selection"]
    apply_annotations = mcp.annotations["hygiene-apply-selection"]
    assert scan_annotations.readOnlyHint is True
    assert apply_annotations.destructiveHint is True

    result = _run(
        mcp.tools["hygiene-apply-selection"](
            "browse-sweep-20260513-120000-abcdef12",
            [],
        )
    )
    assert json.loads(result)["dry_run"] is True
