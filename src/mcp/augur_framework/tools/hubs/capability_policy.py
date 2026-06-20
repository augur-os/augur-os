"""MCP hub tools for capability inventory and exposure policy edits."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from src.config.paths import get_project_root
from src.lib.capabilities.discovery import discover_capabilities
from src.lib.capabilities.exposure_policy import resolve_capability_records
from src.lib.capabilities.policy_editor import (
    CapabilityPolicyError,
    apply_capability_policy_draft,
    compute_impact_preview,
    draft_capability_policy,
)
from src.lib.capabilities.reconciliation import build_capability_report
from src.mcp.augur_shared.annotations import tool_annotations

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _resolved_records() -> list[Any]:
    return resolve_capability_records(discover_capabilities())


def _matches(value: str, candidate: str) -> bool:
    return not value or candidate == value


async def capability_inventory_report_impl(
    owner: str = "",
    status: str = "",
    drift: str = "",
    capability_type: str = "",
) -> str:
    """Return a filtered capability inventory reconciliation report."""
    records = [
        record
        for record in _resolved_records()
        if _matches(owner, record.owner_kind)
        and _matches(status, record.classification_status)
        and (not drift or drift in record.drift)
        and _matches(capability_type, record.type)
    ]
    return _json({"ok": True, **build_capability_report(records)})


async def capability_policy_draft_impl(
    action: str,
    capability_ids: list[str],
    params: dict[str, Any] | None = None,
) -> str:
    """Return a reviewed capability policy draft without applying it."""
    try:
        draft = draft_capability_policy(
            _resolved_records(),
            action=action,
            capability_ids=capability_ids,
            params=params,
        )
    except CapabilityPolicyError as exc:
        return _json({"ok": False, "error": str(exc)})
    return _json({"ok": True, **draft})


async def capability_policy_apply_impl(draft: dict[str, Any]) -> str:
    """Apply a reviewed capability policy draft."""
    try:
        return _json(apply_capability_policy_draft(draft=draft))
    except CapabilityPolicyError as exc:
        return _json({"ok": False, "error": str(exc)})


async def capability_impact_preview_impl(
    capability_id: str,
    action: str,
) -> str:
    """Return the list of client files a destructive policy action would remove."""
    preview = compute_impact_preview(
        project_root=get_project_root(),
        capability_id=capability_id,
        action=action,
    )
    return _json({"ok": True, **preview})


def register_tools(
    mcp: FastMCP,
    interceptor=None,
    metrics: Any = None,
) -> None:
    """Register capability policy MCP tools."""
    intercept = interceptor or (lambda func: func)

    @mcp.tool(
        name="capability-inventory-report",
        annotations=tool_annotations(
            {
                "title": "Capability Inventory Report",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @intercept
    async def capability_inventory_report(
        owner: str = "",
        status: str = "",
        drift: str = "",
        capability_type: str = "",
    ) -> str:
        """Build a capability inventory report with optional filters."""
        if metrics is not None:
            metrics.track_tool("capability-inventory-report")
        return await capability_inventory_report_impl(
            owner=owner,
            status=status,
            drift=drift,
            capability_type=capability_type,
        )

    @mcp.tool(
        name="capability-policy-draft",
        annotations=tool_annotations(
            {
                "title": "Draft Capability Policy",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @intercept
    async def capability_policy_draft(
        action: str,
        capability_ids: list[str],
        params: dict[str, Any] | None = None,
    ) -> str:
        """Draft a reviewed capability exposure policy edit."""
        if metrics is not None:
            metrics.track_tool("capability-policy-draft")
        return await capability_policy_draft_impl(
            action=action,
            capability_ids=capability_ids,
            params=params,
        )

    @mcp.tool(
        name="capability-policy-apply",
        annotations=tool_annotations(
            {
                "title": "Apply Capability Policy",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @intercept
    async def capability_policy_apply(draft: dict[str, Any]) -> str:
        """Apply a reviewed capability exposure policy draft."""
        if metrics is not None:
            metrics.track_tool("capability-policy-apply")
        return await capability_policy_apply_impl(draft)

    @mcp.tool(
        name="capability-impact-preview",
        annotations=tool_annotations(
            {
                "title": "Preview Capability Policy Impact",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @intercept
    async def capability_impact_preview(
        capability_id: str,
        action: str,
    ) -> str:
        """Return the client files a destructive policy action would remove."""
        if metrics is not None:
            metrics.track_tool("capability-impact-preview")
        return await capability_impact_preview_impl(
            capability_id=capability_id,
            action=action,
        )
