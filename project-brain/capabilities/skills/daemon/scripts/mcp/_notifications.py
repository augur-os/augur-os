"""Notification MCP tool registration.

Tools: get-daemon-notifications, manage-daemon-notifications,
       list-notifications, dismiss-old-notifications,
       send-test-notification, update-notification-preferences.
Split from __init__.py for module size management.
"""

from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from . import logger, SCRIPTS_DIR

try:
    from src.mcp.augur_shared.annotations import tool_annotations
except ImportError:

    def tool_annotations(annotations: dict) -> dict:
        return annotations


from runtime_paths import (
    get_notification_history_path,
    get_notification_pending_path,
    get_notification_preferences_path,
)


# ---------------------------------------------------------------------------
# Attention bridge (ADR-435 §2.4)
# ---------------------------------------------------------------------------

_SEVERITY_TO_PRIORITY: dict[str, str] = {
    "error": "critical",
    "alert": "critical",
    "warning": "high",
    "info": "low",
    "success": "low",
}


def _notify_attention(title: str, summary: str, severity: str = "info") -> None:
    """Bridge a daemon notification to the unified attention system.

    Maps daemon severity levels to attention priorities and calls
    :func:`raise_attention` with ``source_type="notification"``.
    Failures are logged but never propagate — daemon notifications must
    not break because the attention system is unavailable.
    """
    try:
        # Import lazily so the daemon MCP server still starts even if
        # the channels skill hasn't been loaded yet.
        # skills/ must be on sys.path for sibling skill imports.
        _skills_root = Path(__file__).resolve().parents[3]
        if str(_skills_root) not in sys.path:
            sys.path.insert(0, str(_skills_root))

        from channels.augur.lib.registry import raise_attention  # type: ignore[import-untyped]

        priority = _SEVERITY_TO_PRIORITY.get(severity, "low")
        raise_attention(
            skill="daemon",
            source_type="notification",
            title=title,
            summary=summary,
            priority=priority,
        )
    except Exception as exc:
        logger.debug("Attention bridge skipped: %s", exc)


def _default_notification_preferences() -> dict[str, Any]:
    return {
        "enabled": True,
        "quiet_hours": {"enabled": False, "start": "22:00", "end": "07:00"},
        "categories": {},
        "slack": {"enabled": False, "webhook_url": ""},
        "email": {"enabled": False, "smtp_host": "", "smtp_port": 587, "recipient": ""},
    }


def _notification_entry_id(entry: dict[str, Any], index: int) -> str:
    existing = entry.get("id")
    if isinstance(existing, str) and existing.strip():
        return existing
    timestamp = str(entry.get("timestamp", "") or "")
    channel = str(entry.get("channel", "") or "system")
    return f"notif-{channel}-{timestamp or index}"


def _load_notification_history() -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    import yaml as _yaml

    history_file = get_notification_history_path()
    if history_file.exists():
        with open(history_file) as f:
            payload = _yaml.safe_load(f) or {}
    else:
        payload = {}
    history = payload.get("history", [])
    if not isinstance(history, list):
        history = []
    return history_file, payload, history


def _save_notification_payload(path: Path, payload: dict[str, Any]) -> None:
    import yaml as _yaml

    with open(path, "w") as f:
        _yaml.safe_dump(payload, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def register_notification_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register notification tools with the MCP server."""

    @mcp.tool(
        name="get-daemon-notifications",
        annotations=tool_annotations(
            {
                "title": "Get Daemon Notifications",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_daemon_notifications_tool(
        mode: str = "feed",
        limit: int = 50,
        channel: str | None = None,
    ) -> str:
        """Return daemon notifications feed or preferences for the dashboard."""
        metrics.track_tool("get_daemon_notifications", skill="daemon")

        try:
            import yaml as _yaml

            if mode == "preferences":
                prefs_file = get_notification_preferences_path()
                prefs = _default_notification_preferences()
                if prefs_file.exists():
                    with open(prefs_file) as f:
                        loaded = _yaml.safe_load(f) or {}
                    if isinstance(loaded, dict):
                        prefs.update(loaded)
                return json.dumps({"success": True, "preferences": prefs}, indent=2)

            _, _, history = _load_notification_history()
            pending_file = get_notification_pending_path()
            pending_payload: dict[str, Any] = {}
            if pending_file.exists():
                with open(pending_file) as f:
                    pending_payload = _yaml.safe_load(f) or {}
            pending_entries = pending_payload.get("pending", [])
            if not isinstance(pending_entries, list):
                pending_entries = []

            normalized: list[dict[str, Any]] = []
            channels: set[str] = set()
            for index, entry in enumerate(history):
                if not isinstance(entry, dict):
                    continue
                normalized_entry = dict(entry)
                normalized_entry["id"] = _notification_entry_id(normalized_entry, index)
                normalized_entry.setdefault("read", False)
                normalized_entry.setdefault("dismissed", False)
                entry_channel = normalized_entry.get("channel")
                if isinstance(entry_channel, str) and entry_channel:
                    channels.add(entry_channel)
                normalized.append(normalized_entry)

            if channel:
                normalized = [entry for entry in normalized if entry.get("channel") == channel]

            normalized = [entry for entry in normalized if not entry.get("dismissed")]
            normalized.sort(key=lambda entry: entry.get("timestamp", ""), reverse=True)
            normalized = normalized[: max(1, limit)]

            return json.dumps(
                {
                    "success": True,
                    "notifications": normalized,
                    "pending": pending_entries[: max(1, limit)],
                    "total": len(normalized),
                    "unread": sum(1 for entry in normalized if not entry.get("read")),
                    "channels": sorted(channels),
                },
                indent=2,
            )
        except Exception as e:
            logger.error(f"Failed to get daemon notifications: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="manage-daemon-notifications",
        annotations=tool_annotations(
            {
                "title": "Manage Daemon Notifications",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def manage_daemon_notifications_tool(
        action: str,
        ids: list[str] | None = None,
        preferences: dict[str, Any] | None = None,
        channel: str = "system",
        message: str = "Test notification from Augur MCP",
    ) -> str:
        """Handle notification mutations used by the daemon dashboard."""
        metrics.track_tool("manage_daemon_notifications", skill="daemon")

        try:
            if action == "save-preferences":
                prefs_file = get_notification_preferences_path()
                prefs = _default_notification_preferences()
                if prefs_file.exists():
                    import yaml as _yaml

                    with open(prefs_file) as f:
                        loaded = _yaml.safe_load(f) or {}
                    if isinstance(loaded, dict):
                        prefs.update(loaded)
                if isinstance(preferences, dict):
                    prefs.update(preferences)
                _save_notification_payload(prefs_file, prefs)
                return json.dumps({"success": True, "preferences": prefs}, indent=2)

            if action == "send-test":
                return await send_test_notification_tool(message=message, channel=channel)

            if action not in {"mark-read", "dismiss"}:
                return json.dumps({"success": False, "error": f"Unsupported action: {action}"}, indent=2)

            target_ids = set(ids or [])
            history_file, payload, history = _load_notification_history()
            changed = 0
            for index, entry in enumerate(history):
                if not isinstance(entry, dict):
                    continue
                entry_id = _notification_entry_id(entry, index)
                if entry_id not in target_ids:
                    continue
                if action == "mark-read":
                    if not entry.get("read"):
                        entry["read"] = True
                        changed += 1
                elif action == "dismiss":
                    if not entry.get("dismissed"):
                        entry["dismissed"] = True
                        entry["read"] = True
                        changed += 1

            payload["history"] = history
            _save_notification_payload(history_file, payload)
            return json.dumps(
                {"success": True, "action": action, "updated": changed, "ids": sorted(target_ids)},
                indent=2,
            )
        except Exception as e:
            logger.error(f"Failed to manage daemon notifications: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="list-notifications",
        annotations=tool_annotations(
            {
                "title": "List Notifications",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_notifications_tool(limit: int = 20, channel: str | None = None) -> str:
        """List recent daemon notifications from the unified feed.

        Args:
            limit: Maximum notifications to return (default 20)
            channel: Filter by channel (macos, slack, email, system)

        Returns:
            str: JSON with notification list, unread count, and channels
        """
        metrics.track_tool("list_notifications", skill="daemon")

        try:
            import yaml as _yaml

            history_file = get_notification_history_path()

            if not history_file.exists():
                return json.dumps({"success": True, "notifications": [], "total": 0})

            with open(history_file) as f:
                data = _yaml.safe_load(f) or {}

            entries = data.get("history", [])

            # Filter
            if channel:
                entries = [e for e in entries if e.get("channel") == channel]

            # Filter dismissed
            entries = [e for e in entries if not e.get("dismissed")]

            # Sort by timestamp descending
            entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            entries = entries[:limit]

            unread = sum(1 for e in entries if not e.get("read"))

            return json.dumps(
                {
                    "success": True,
                    "notifications": entries,
                    "total": len(entries),
                    "unread": unread,
                },
                indent=2,
            )
        except Exception as e:
            logger.error(f"Failed to list notifications: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="dismiss-old-notifications",
        annotations=tool_annotations(
            {
                "title": "Dismiss Old Notifications",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def dismiss_old_notifications_tool(
        older_than_days: int = 7,
        dry_run: bool = False,
    ) -> str:
        """Dismiss read notifications older than N days.

        Args:
            older_than_days: Dismiss threshold in days (default 7)
            dry_run: If true, return targets without mutating files

        Returns:
            str: JSON with dismissed count and IDs
        """
        metrics.track_tool("dismiss_old_notifications", skill="daemon")

        try:
            import yaml as _yaml

            history_file = get_notification_history_path()

            if not history_file.exists():
                return json.dumps(
                    {"success": True, "dismissed": 0, "dismissed_ids": [], "message": "No history file found"},
                    indent=2,
                )

            with open(history_file) as f:
                payload = _yaml.safe_load(f) or {}

            history = payload.get("history", [])
            if not isinstance(history, list):
                return json.dumps({"success": False, "error": "history.yaml is malformed"}, indent=2)

            cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, older_than_days))
            dismissed_ids: list[str] = []

            for entry in history:
                if not isinstance(entry, dict):
                    continue
                if entry.get("dismissed"):
                    continue
                if not entry.get("read"):
                    continue

                ts_raw = str(entry.get("timestamp", "") or "")
                if not ts_raw:
                    continue
                try:
                    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    else:
                        ts = ts.astimezone(timezone.utc)
                except Exception:
                    continue

                if ts <= cutoff:
                    notif_id = f"notif-{ts_raw}"
                    dismissed_ids.append(notif_id)
                    if not dry_run:
                        entry["dismissed"] = True

            if not dry_run:
                with open(history_file, "w") as f:
                    _yaml.safe_dump(payload, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

            return json.dumps(
                {
                    "success": True,
                    "dry_run": dry_run,
                    "dismissed": len(dismissed_ids),
                    "dismissed_ids": dismissed_ids,
                    "older_than_days": older_than_days,
                },
                indent=2,
            )
        except Exception as e:
            logger.error(f"Failed to dismiss old notifications: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="send-test-notification",
        annotations=tool_annotations(
            {
                "title": "Send Test Notification",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def send_test_notification_tool(
        message: str = "Test notification from Augur MCP",
        channel: str = "system",
    ) -> str:
        """Send a test notification to verify channel configuration.

        Args:
            message: Message to send
            channel: Target channel (system, macos, slack, email)

        Returns:
            str: JSON with send result
        """
        metrics.track_tool("send_test_notification", skill="daemon")

        try:
            sys.path.insert(0, str(SCRIPTS_DIR))
            from notification_service import NotificationService

            service = NotificationService()
            result = service.send(message, channel=channel, title="Augur Test")

            # Bridge to unified attention system (ADR-435 §2.4)
            if result.success:
                _notify_attention(
                    title="Augur Test",
                    summary=message,
                    severity="info",
                )

            return json.dumps(
                {
                    "success": result.success,
                    "channel": result.channel,
                    "message": result.message,
                    "backend": result.backend,
                    "error": result.error,
                },
                indent=2,
            )
        except Exception as e:
            logger.error(f"Failed to send test notification: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="update-notification-preferences",
        annotations=tool_annotations(
            {
                "title": "Update Notification Preferences",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def update_notification_preferences_tool(
        enabled: bool | None = None,
        quiet_hours_enabled: bool | None = None,
        quiet_hours_start: str | None = None,
        quiet_hours_end: str | None = None,
        category: str | None = None,
        category_enabled: bool | None = None,
    ) -> str:
        """Update notification preferences (quiet hours, categories, global toggle).

        Args:
            enabled: Global notification toggle
            quiet_hours_enabled: Enable/disable quiet hours
            quiet_hours_start: Quiet hours start time (HH:MM)
            quiet_hours_end: Quiet hours end time (HH:MM)
            category: Category name to update (dashboard, mcp, runtime, tech_debt, insights)
            category_enabled: Enable/disable the specified category

        Returns:
            str: JSON with updated preferences
        """
        metrics.track_tool("update_notification_preferences", skill="daemon")

        try:
            import yaml as _yaml

            prefs_file = get_notification_preferences_path()

            prefs = {}
            if prefs_file.exists():
                with open(prefs_file) as f:
                    prefs = _yaml.safe_load(f) or {}

            if enabled is not None:
                prefs["enabled"] = enabled

            if quiet_hours_enabled is not None or quiet_hours_start or quiet_hours_end:
                qh = prefs.setdefault("quiet_hours", {})
                if quiet_hours_enabled is not None:
                    qh["enabled"] = quiet_hours_enabled
                if quiet_hours_start:
                    qh["start"] = quiet_hours_start
                if quiet_hours_end:
                    qh["end"] = quiet_hours_end

            if category and category_enabled is not None:
                cats = prefs.setdefault("categories", {})
                cat_cfg = cats.setdefault(category, {})
                cat_cfg["enabled"] = category_enabled

            with open(prefs_file, "w") as f:
                _yaml.safe_dump(prefs, f, default_flow_style=False)

            return json.dumps({"success": True, "preferences": prefs}, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to update preferences: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})
