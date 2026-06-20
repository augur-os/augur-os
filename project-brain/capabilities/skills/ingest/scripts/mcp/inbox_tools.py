from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

from src.config.paths import (
    get_documents_dir,
    get_runtime_dir,
)
from skills.ingest.scripts.brain_insights import summarize_inbox_run
from src.lib.ingest.inbox_consume import consume_folder
from src.lib.ingest.inbox_models import to_dict
from skills.ingest.scripts.inbox_purge import purge_folder
from src.lib.ingest.inbox_scan import scan_folder
from src.lib.ingest.inbox_store import InboxStore
from skills.ingest.scripts.email_drop_consume import (
    consume_email_drop_source,
    scan_email_drop_source,
)
from skills.ingest.scripts.email_drop_models import to_dict as email_to_dict
from skills.ingest.scripts.email_drop_store import EmailDropStore
from skills.ingest.scripts.inbox_packet_consume import consume_packet
from skills.ingest.scripts.inbox_packets import create_pending_packet, stage_packet
from skills.ingest.scripts.inbox_unified_models import to_dict as unified_to_dict
from skills.ingest.scripts.inbox_vault_discovery import discover_vault_candidates, register_discovered_vault

from ._shared import tool_annotations
from ._inbox_packet_helpers import (
    MAX_LATEST_RUNS,
    _find_unified_packet,
    _iter_unified_packets,
    _latest_run_payloads,
    _latest_unified_runs,
    _packet_payload,
    _proposal_for_packet,
    _unified_overview_payload,
)

MAX_SCAN_ITEMS = 200
MAX_RUN_HISTORY_ITEMS = 50

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _store_root() -> "Path":
    return get_runtime_dir() / "brain" / "inbox"


def _store() -> InboxStore:
    return InboxStore(_store_root())


def _email_store() -> EmailDropStore:
    return EmailDropStore(_store_root())


async def inbox_folders_impl(
    action: str = "list",
    folder_id: str = "",
    name: str = "",
    path: str = "",
) -> str:
    store = _store()

    if action == "list":
        return json.dumps(
            {
                "success": True,
                "folders": to_dict(store.list_folders()),
                "mail_drop_sources": email_to_dict(_email_store().list_sources()),
                "email_drop_latest_runs": email_to_dict(
                    _email_store().list_runs(limit=MAX_LATEST_RUNS)
                ),
                "latest_runs": _latest_run_payloads(store),
                **_unified_overview_payload(),
            }
        )

    if action == "add":
        if not path:
            return json.dumps(
                {
                    "success": False,
                    "error": "Missing required path for inbox folder.",
                }
            )
        folder = store.add_folder(name=name or folder_id or "Inbox", path=path)
        return json.dumps({"success": True, "folder": to_dict(folder)})

    return json.dumps(
        {
            "success": False,
            "error": f"Unsupported inbox-folders action: {action}",
        }
    )


async def email_drop_sources_impl(
    action: str = "list",
    source_id: str = "",
    name: str = "",
    path: str = "",
) -> str:
    store = _email_store()

    if action == "list":
        return json.dumps(
            {
                "success": True,
                "sources": email_to_dict(store.list_sources()),
                "latest_runs": email_to_dict(store.list_runs(limit=MAX_LATEST_RUNS)),
            }
        )

    if action == "add":
        source_path = path.strip()
        if not source_path:
            source_path = str(get_documents_dir() / "inbox" / "email")
        source = store.add_source(
            name=name or source_id or "Mail Drop", path=source_path
        )
        return json.dumps({"success": True, "source": email_to_dict(source)})

    return json.dumps(
        {
            "success": False,
            "error": f"Unsupported email-drop-sources action: {action}",
        }
    )


async def email_drop_scan_source_impl(source_id: str = "") -> str:
    if not source_id:
        return json.dumps({"success": False, "error": "Missing source_id."})
    store = _email_store()
    try:
        counts = scan_email_drop_source(store=store, source_id=source_id)
        source = store.get_source(source_id)
    except KeyError as exc:
        return json.dumps({"success": False, "error": str(exc)})
    return json.dumps(
        {
            "success": counts.failed == 0,
            "source": email_to_dict(source),
            "counts": email_to_dict(counts),
            "message": "Mail Drop scan completed.",
        }
    )


async def email_drop_consume_source_impl(source_id: str = "", limit: int = 0) -> str:
    if not source_id:
        return json.dumps({"success": False, "error": "Missing source_id."})
    store = _email_store()
    try:
        record = consume_email_drop_source(
            store=store,
            source_id=source_id,
            limit=limit or None,
        )
    except KeyError as exc:
        return json.dumps({"success": False, "error": str(exc)})
    return json.dumps(
        {
            "success": record.status == "success",
            "partial": record.status == "partial_success",
            **email_to_dict(record),
            "message": "Mail Drop consume completed.",
        }
    )


async def inbox_scan_folder_impl(folder_id: str = "", limit: int = 200) -> str:
    store = _store()
    if not folder_id:
        return json.dumps({"success": False, "error": "Missing folder_id."})

    try:
        folder = store.get_folder(folder_id)
    except KeyError as exc:
        return json.dumps({"success": False, "error": str(exc)})

    result = scan_folder(folder.path)
    folder = store.update_folder_state(
        folder.id,
        counts=result.counts,
        last_scan_at=datetime.now(timezone.utc).isoformat(),
    )
    item_limit = min(max(0, limit), MAX_SCAN_ITEMS)
    preview_items = result.items[:item_limit]

    return json.dumps(
        {
            "success": result.counts.failed == 0,
            "folder": to_dict(folder),
            "items": to_dict(preview_items),
            "items_total": len(result.items),
            "items_truncated": len(preview_items) < len(result.items),
        }
    )


async def inbox_consume_folder_impl(
    folder_id: str = "",
    to: str | None = None,
    cwd: str | None = None,
) -> str:
    store = _store()
    if not folder_id:
        return json.dumps({"success": False, "error": "Missing folder_id."})

    try:
        record = consume_folder(
            store=store,
            folder_id=folder_id,
            to=to,
            cwd=Path(cwd) if cwd else None,
        )
    except (KeyError, ValueError) as exc:
        return json.dumps({"success": False, "error": str(exc)})

    folder = store.get_folder(folder_id)
    refreshed = scan_folder(folder.path)
    store.update_folder_state(
        folder_id,
        counts=refreshed.counts,
        last_scan_at=record.completed_at,
        last_run_status=record.status,
    )

    return json.dumps(
        {
            "success": record.status == "success",
            "partial": record.status == "partial_success",
            **to_dict(record),
            "message": "Consume completed.",
        }
    )


async def inbox_purge_folder_impl(folder_id: str = "") -> str:
    store = _store()
    if not folder_id:
        return json.dumps({"success": False, "error": "Missing folder_id."})

    try:
        record = purge_folder(store=store, folder_id=folder_id)
    except KeyError as exc:
        return json.dumps({"success": False, "error": str(exc)})

    return json.dumps(
        {
            "success": record.status == "success",
            "partial": record.status == "partial_success",
            **to_dict(record),
            "message": f"Purge moved {record.files_moved} trash candidate(s) to Augur trash.",
        }
    )


async def inbox_run_history_impl(folder_id: str = "", limit: int = 50) -> str:
    run_limit = min(max(0, limit), MAX_RUN_HISTORY_ITEMS)
    runs = _store().list_run_payloads(
        folder_id=folder_id or None,
        limit=run_limit,
        include_file_results=False,
    )
    return json.dumps(
        {"success": True, "runs": [summarize_inbox_run(run) for run in runs]}
    )


async def inbox_run_detail_impl(run_id: str = "") -> str:
    if not run_id:
        return json.dumps({"success": False, "error": "Missing run_id."})
    try:
        run = _store().get_run(run_id)
    except (KeyError, ValueError) as exc:
        return json.dumps({"success": False, "error": str(exc)})
    return json.dumps({"success": True, "run": to_dict(run)})


async def inbox_source_lanes_impl() -> str:
    try:
        return json.dumps({"success": True, **_unified_overview_payload()})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


async def inbox_discover_vaults_impl(search_root: str = "") -> str:
    try:
        roots = [search_root] if search_root.strip() else None
        candidates = discover_vault_candidates(search_roots=roots)
        return json.dumps(
            {
                "success": True,
                "candidates": unified_to_dict(candidates),
                "discovered_vaults": unified_to_dict(candidates),
            }
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


async def inbox_register_vault_impl(candidate_id: str = "") -> str:
    if not candidate_id:
        return json.dumps({"success": False, "error": "Missing candidate_id."})
    try:
        target = register_discovered_vault(candidate_id)
        return json.dumps({"success": True, "target": unified_to_dict(target)})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


async def inbox_stage_packet_impl(
    source_id: str = "claude-chat",
    title: str = "",
    filename: str = "",
    content_base64: str = "",
    content_text: str = "",
    user_instruction: str = "",
    content_type: str = "",
    capture_mode: str = "mcp_content",
) -> str:
    if not title:
        return json.dumps({"success": False, "error": "Missing title."})
    if not filename:
        return json.dumps({"success": False, "error": "Missing filename."})
    try:
        if content_base64:
            content = base64.b64decode(content_base64, validate=True)
        elif content_text:
            content = content_text.encode("utf-8")
        else:
            return json.dumps(
                {"success": False, "error": "Missing content_base64 or content_text."}
            )
        packet = stage_packet(
            source_id=source_id,
            title=title,
            filename=filename,
            content=content,
            user_instruction=user_instruction,
            content_type=content_type,
            capture_mode=capture_mode,
        )
        return json.dumps(
            {
                "success": True,
                "packet": unified_to_dict(packet),
                **unified_to_dict(packet),
            }
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


async def inbox_pending_packet_impl(
    source_id: str = "claude-chat",
    title: str = "",
    user_instruction: str = "",
) -> str:
    if not title:
        return json.dumps({"success": False, "error": "Missing title."})
    try:
        packet = create_pending_packet(
            source_id=source_id,
            title=title,
            user_instruction=user_instruction,
        )
        packet_payload = _packet_payload(packet)
        return json.dumps(
            {
                "success": True,
                "packet": packet_payload,
                "packet_id": packet_payload.get("packet_id", ""),
                "drop_target": packet_payload.get("packet_dir", ""),
                "status": packet_payload.get("status", ""),
                "failure_state": packet_payload.get("failure_state"),
            }
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


async def inbox_route_packets_impl(packet_id: str = "") -> str:
    try:
        packets = (
            [_find_unified_packet(packet_id)] if packet_id else _iter_unified_packets()
        )
        proposals = []
        for packet in packets:
            _, proposal = _proposal_for_packet(packet)
            proposals.append(unified_to_dict(proposal))
        return json.dumps({"success": True, "proposals": proposals})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


async def inbox_consume_packets_impl(packet_id: str = "", apply: bool = True) -> str:
    if not packet_id:
        return json.dumps({"success": False, "error": "Missing packet_id."})
    try:
        packet = _find_unified_packet(packet_id)
        target, proposal = _proposal_for_packet(packet)
        if not apply:
            return json.dumps({"success": True, "proposal": unified_to_dict(proposal)})
        result = consume_packet(packet=packet, target=target, proposal=proposal)
        return json.dumps(
            {
                "success": result.status == "success",
                "result": unified_to_dict(result),
                **unified_to_dict(result),
            }
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


async def inbox_runs_impl(limit: int = 20) -> str:
    try:
        run_limit = min(max(0, limit), MAX_RUN_HISTORY_ITEMS)
        return json.dumps(
            {"success": True, "runs": _latest_unified_runs(limit=run_limit)}
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


def register_inbox_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any = None,
) -> None:
    @mcp.tool(
        name="inbox-source-lanes",
        annotations=tool_annotations(
            {
                "title": "Inbox Source Lanes",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def inbox_source_lanes_tool() -> str:
        if metrics:
            metrics.track_tool("inbox_source_lanes", skill="ingest")
        return await inbox_source_lanes_impl()

    @mcp.tool(
        name="inbox-discover-vaults",
        annotations=tool_annotations(
            {
                "title": "Discover Inbox Vaults",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def inbox_discover_vaults_tool(search_root: str = "") -> str:
        if metrics:
            metrics.track_tool("inbox_discover_vaults", skill="ingest")
        return await inbox_discover_vaults_impl(search_root=search_root)

    @mcp.tool(
        name="inbox-register-vault",
        annotations=tool_annotations(
            {
                "title": "Register Inbox Vault",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def inbox_register_vault_tool(candidate_id: str = "") -> str:
        if metrics:
            metrics.track_tool("inbox_register_vault", skill="ingest")
        return await inbox_register_vault_impl(candidate_id=candidate_id)

    @mcp.tool(
        name="inbox-stage-packet",
        annotations=tool_annotations(
            {
                "title": "Stage Inbox Packet",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def inbox_stage_packet_tool(
        source_id: str = "claude-chat",
        title: str = "",
        filename: str = "",
        content_base64: str = "",
        content_text: str = "",
        user_instruction: str = "",
        content_type: str = "",
        capture_mode: str = "mcp_content",
    ) -> str:
        if metrics:
            metrics.track_tool("inbox_stage_packet", skill="ingest")
        return await inbox_stage_packet_impl(
            source_id=source_id,
            title=title,
            filename=filename,
            content_base64=content_base64,
            content_text=content_text,
            user_instruction=user_instruction,
            content_type=content_type,
            capture_mode=capture_mode,
        )

    @mcp.tool(
        name="inbox-pending-packet",
        annotations=tool_annotations(
            {
                "title": "Create Pending Inbox Packet",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def inbox_pending_packet_tool(
        source_id: str = "claude-chat",
        title: str = "",
        user_instruction: str = "",
    ) -> str:
        if metrics:
            metrics.track_tool("inbox_pending_packet", skill="ingest")
        return await inbox_pending_packet_impl(
            source_id=source_id,
            title=title,
            user_instruction=user_instruction,
        )

    @mcp.tool(
        name="inbox-route-packets",
        annotations=tool_annotations(
            {
                "title": "Route Inbox Packets",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def inbox_route_packets_tool(packet_id: str = "") -> str:
        if metrics:
            metrics.track_tool("inbox_route_packets", skill="ingest")
        return await inbox_route_packets_impl(packet_id=packet_id)

    @mcp.tool(
        name="inbox-consume-packets",
        annotations=tool_annotations(
            {
                "title": "Consume Inbox Packets",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def inbox_consume_packets_tool(
        packet_id: str = "", apply: bool = True
    ) -> str:
        if metrics:
            metrics.track_tool("inbox_consume_packets", skill="ingest")
        return await inbox_consume_packets_impl(packet_id=packet_id, apply=apply)

    @mcp.tool(
        name="inbox-runs",
        annotations=tool_annotations(
            {
                "title": "Unified Inbox Runs",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def inbox_runs_tool(limit: int = 20) -> str:
        if metrics:
            metrics.track_tool("inbox_runs", skill="ingest")
        return await inbox_runs_impl(limit=limit)

    @mcp.tool(
        name="inbox-folders",
        annotations=tool_annotations(
            {
                "title": "Inbox Folders",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def inbox_folders_tool(
        action: str = "list",
        folder_id: str = "",
        name: str = "",
        path: str = "",
    ) -> str:
        if metrics:
            metrics.track_tool("inbox_folders", skill="ingest")
        return await inbox_folders_impl(
            action=action,
            folder_id=folder_id,
            name=name,
            path=path,
        )

    @mcp.tool(
        name="email-drop-sources",
        annotations=tool_annotations(
            {
                "title": "Email Drop Sources",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def email_drop_sources_tool(
        action: str = "list",
        source_id: str = "",
        name: str = "",
        path: str = "",
    ) -> str:
        if metrics:
            metrics.track_tool("email_drop_sources", skill="ingest")
        return await email_drop_sources_impl(
            action=action,
            source_id=source_id,
            name=name,
            path=path,
        )

    @mcp.tool(
        name="email-drop-scan-source",
        annotations=tool_annotations(
            {
                "title": "Scan Email Drop Source",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def email_drop_scan_source_tool(source_id: str = "") -> str:
        if metrics:
            metrics.track_tool("email_drop_scan_source", skill="ingest")
        return await email_drop_scan_source_impl(source_id=source_id)

    @mcp.tool(
        name="email-drop-consume-source",
        annotations=tool_annotations(
            {
                "title": "Consume Email Drop Source",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def email_drop_consume_source_tool(
        source_id: str = "", limit: int = 0
    ) -> str:
        if metrics:
            metrics.track_tool("email_drop_consume_source", skill="ingest")
        return await email_drop_consume_source_impl(source_id=source_id, limit=limit)

    @mcp.tool(
        name="inbox-scan-folder",
        annotations=tool_annotations(
            {
                "title": "Scan Inbox Folder",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def inbox_scan_folder_tool(folder_id: str = "", limit: int = 200) -> str:
        if metrics:
            metrics.track_tool("inbox_scan_folder", skill="ingest")
        return await inbox_scan_folder_impl(folder_id=folder_id, limit=limit)

    @mcp.tool(
        name="inbox-consume-folder",
        annotations=tool_annotations(
            {
                "title": "Consume Inbox Folder",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def inbox_consume_folder_tool(
        folder_id: str = "",
        to: str | None = None,
        cwd: str | None = None,
    ) -> str:
        if metrics:
            metrics.track_tool("inbox_consume_folder", skill="ingest")
        return await inbox_consume_folder_impl(folder_id=folder_id, to=to, cwd=cwd)

    @mcp.tool(
        name="inbox-purge-folder",
        annotations=tool_annotations(
            {
                "title": "Purge Inbox Folder Trash",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def inbox_purge_folder_tool(folder_id: str = "") -> str:
        if metrics:
            metrics.track_tool("inbox_purge_folder", skill="ingest")
        return await inbox_purge_folder_impl(folder_id=folder_id)

    @mcp.tool(
        name="inbox-run-history",
        annotations=tool_annotations(
            {
                "title": "Inbox Run History",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def inbox_run_history_tool(folder_id: str = "", limit: int = 50) -> str:
        if metrics:
            metrics.track_tool("inbox_run_history", skill="ingest")
        return await inbox_run_history_impl(folder_id=folder_id, limit=limit)

    @mcp.tool(
        name="inbox-run-detail",
        annotations=tool_annotations(
            {
                "title": "Inbox Run Detail",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def inbox_run_detail_tool(run_id: str = "") -> str:
        if metrics:
            metrics.track_tool("inbox_run_detail", skill="ingest")
        return await inbox_run_detail_impl(run_id=run_id)
