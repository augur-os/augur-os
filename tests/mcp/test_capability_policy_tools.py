from __future__ import annotations

import json
from types import SimpleNamespace

import pytest


class CapturingMCP:
    def __init__(self) -> None:
        self.tools = {}
        self.annotations = {}

    def tool(self, *args, **kwargs):
        name = kwargs.get("name")
        if name is None and args and isinstance(args[0], str):
            name = args[0]

        def decorator(func):
            tool_name = name or func.__name__
            self.tools[tool_name] = func
            self.annotations[tool_name] = kwargs.get("annotations")
            return func

        return decorator


def _record(
    capability_id: str,
    *,
    owner_kind: str = "augur",
    classification_status: str = "approved",
    drift: tuple[str, ...] = (),
    capability_type: str = "mcp-tool",
):
    return SimpleNamespace(
        id=capability_id,
        owner_kind=owner_kind,
        classification_status=classification_status,
        drift=drift,
        type=capability_type,
    )


@pytest.mark.asyncio
async def test_inventory_report_impl_returns_json_payload(monkeypatch):
    from src.mcp.augur_framework.tools.hubs import capability_policy

    discovered = [object()]
    records = [
        _record(
            "keep",
            owner_kind="augur",
            classification_status="approved",
            drift=("duplicate",),
            capability_type="mcp-tool",
        ),
        _record(
            "drop",
            owner_kind="external",
            classification_status="unclassified",
            drift=(),
            capability_type="skill",
        ),
    ]

    monkeypatch.setattr(capability_policy, "discover_capabilities", lambda: discovered)
    monkeypatch.setattr(
        capability_policy,
        "resolve_capability_records",
        lambda items: records if items is discovered else [],
    )
    monkeypatch.setattr(
        capability_policy,
        "build_capability_report",
        lambda items: {
            "counts": {"total": len(items)},
            "records": [item.id for item in items],
        },
    )

    payload = json.loads(
        await capability_policy.capability_inventory_report_impl(
            owner="augur",
            status="approved",
            drift="duplicate",
            capability_type="mcp-tool",
        )
    )

    assert payload == {
        "ok": True,
        "counts": {"total": 1},
        "records": ["keep"],
    }


@pytest.mark.asyncio
async def test_policy_draft_impl_catches_capability_policy_error(monkeypatch):
    from src.mcp.augur_framework.tools.hubs import capability_policy

    monkeypatch.setattr(capability_policy, "_resolved_records", lambda: [])

    def raise_policy_error(*args, **kwargs):
        raise capability_policy.CapabilityPolicyError("bad policy edit")

    monkeypatch.setattr(capability_policy, "draft_capability_policy", raise_policy_error)

    payload = json.loads(
        await capability_policy.capability_policy_draft_impl(
            action="move_to_cli_only",
            capability_ids=["missing"],
        )
    )

    assert payload == {"ok": False, "error": "bad policy edit"}


@pytest.mark.asyncio
async def test_policy_apply_impl_returns_apply_payload(monkeypatch):
    from src.mcp.augur_framework.tools.hubs import capability_policy

    draft = {"draft_id": "abc", "base_hash": "123", "entries": {"tool": {}}}
    monkeypatch.setattr(
        capability_policy,
        "apply_capability_policy_draft",
        lambda *args, **kwargs: {"ok": True, "applied_capabilities": ["tool"]},
    )

    payload = json.loads(await capability_policy.capability_policy_apply_impl(draft))

    assert payload == {"ok": True, "applied_capabilities": ["tool"]}


def test_register_tools_registers_capability_policy_tools():
    from src.mcp.augur_framework.tools.hubs import capability_policy

    mcp = CapturingMCP()
    capability_policy.register_tools(mcp)

    assert set(mcp.tools) == {
        "capability-inventory-report",
        "capability-policy-draft",
        "capability-policy-apply",
        "capability-impact-preview",
    }
    assert mcp.annotations["capability-inventory-report"].readOnlyHint is True
    assert mcp.annotations["capability-inventory-report"].destructiveHint is False
    assert mcp.annotations["capability-inventory-report"].idempotentHint is True
    assert mcp.annotations["capability-policy-draft"].readOnlyHint is True
    assert mcp.annotations["capability-policy-draft"].destructiveHint is False
    assert mcp.annotations["capability-policy-draft"].idempotentHint is True
    assert mcp.annotations["capability-policy-apply"].readOnlyHint is False
    assert mcp.annotations["capability-policy-apply"].destructiveHint is False
    assert mcp.annotations["capability-policy-apply"].idempotentHint is False
    assert mcp.annotations["capability-impact-preview"].readOnlyHint is True
    assert mcp.annotations["capability-impact-preview"].destructiveHint is False
    assert mcp.annotations["capability-impact-preview"].idempotentHint is True


@pytest.mark.asyncio
async def test_capability_impact_preview_impl_returns_would_remove(tmp_path, monkeypatch):
    """ADR-734 C6.5: MCP wrapper passes through to compute_impact_preview."""
    from src.mcp.augur_framework.tools.hubs import capability_policy

    cmd_dir = tmp_path / ".claude" / "commands"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "doomed.md").write_text("x", encoding="utf-8")

    monkeypatch.setattr(capability_policy, "get_project_root", lambda: tmp_path)

    payload = json.loads(
        await capability_policy.capability_impact_preview_impl(
            capability_id="command:doomed",
            action="move_to_cli_only",
        )
    )

    assert payload["ok"] is True
    assert payload["would_remove"] == [".claude/commands/doomed.md"]
