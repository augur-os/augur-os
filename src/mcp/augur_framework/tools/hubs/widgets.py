"""MCP tools for widget lifecycle — render, list, pin, delete."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.mcp.augur_shared.config import get_runtime_dir

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _widgets_dir() -> Path:
    d = get_runtime_dir() / "widgets"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_widget(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_widget(widget: dict[str, Any]) -> Path:
    path = _widgets_dir() / f"{widget['id']}.json"
    path.write_text(json.dumps(widget, indent=2), encoding="utf-8")
    return path


def register_tools(mcp: FastMCP, interceptor=None, metrics: Any = None) -> None:
    """Register widget lifecycle tools."""

    @mcp.tool(name="render-widget")
    def render_widget(title: str, widget_code: str, source: str = "chat") -> dict:
        """Render an interactive HTML/SVG widget. Persists to runtime state.

        Args:
            title: Snake_case identifier for the widget
            widget_code: Raw HTML or SVG code to render
            source: Origin context — "chat", "skill", or "block"
        """
        widget_id = str(uuid.uuid4())[:8]
        widget = {
            "id": widget_id,
            "type": "widget",
            "title": title,
            "html": widget_code,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pinned_to": None,
        }
        _write_widget(widget)
        return widget

    @mcp.tool(name="list-widgets")
    def list_widgets(pinned_to: str | None = None) -> dict:
        """List all widgets, optionally filtered by pinned page.

        Args:
            pinned_to: Optional page path to filter by. If None, returns all widgets.
        """
        widgets = []
        for path in sorted(_widgets_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            w = _read_widget(path)
            if w is None:
                continue
            if pinned_to is not None and w.get("pinned_to") != pinned_to:
                continue
            widgets.append(w)
        return {"items": widgets, "count": len(widgets)}

    @mcp.tool(name="pin-widget")
    def pin_widget(widget_id: str, page_path: str) -> dict:
        """Pin a widget to a dashboard page so it appears as a widget block.

        Args:
            widget_id: The widget ID returned by render-widget
            page_path: Dashboard page path to pin to (e.g., "/studio/visualization")
        """
        path = _widgets_dir() / f"{widget_id}.json"
        if not path.exists():
            return {"error": f"Widget {widget_id} not found"}
        widget = _read_widget(path)
        if widget is None:
            return {"error": f"Widget {widget_id} is corrupted"}
        widget["pinned_to"] = page_path
        _write_widget(widget)
        return widget

    @mcp.tool(name="delete-widget")
    def delete_widget(widget_id: str) -> dict:
        """Remove a widget from runtime state.

        Args:
            widget_id: The widget ID to delete
        """
        path = _widgets_dir() / f"{widget_id}.json"
        if not path.exists():
            return {"error": f"Widget {widget_id} not found"}
        path.unlink()
        return {"deleted": widget_id}
