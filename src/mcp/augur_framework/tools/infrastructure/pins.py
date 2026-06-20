"""Pin store MCP tool helpers.

Storage: vault system/pins.yaml (under _augur/ in the domains layout).
Single-user, last-write-wins. Writes use a sibling temp file followed by
atomic replace.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from src.config.paths import get_vault_dir
from src.mcp.augur_shared.annotations import tool_annotations


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_pins(pins_path: Path) -> list[dict[str, Any]]:
    if not pins_path.exists():
        return []

    data = yaml.safe_load(pins_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return []

    pins = data.get("pins") or []
    if not isinstance(pins, list):
        return []
    return [pin for pin in pins if isinstance(pin, dict)]


def _save_pins(pins_path: Path, pins: list[dict[str, Any]]) -> None:
    pins_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = pins_path.parent / f".{pins_path.name}.{uuid4().hex}.tmp"
    body = yaml.safe_dump({"pins": pins}, sort_keys=False, allow_unicode=True)

    try:
        tmp_path.write_text(body, encoding="utf-8")
        os.replace(tmp_path, pins_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def pin_list_impl(*, pins_path: Path) -> dict[str, Any]:
    return {"pins": _load_pins(pins_path)}


def _pin_identity(pin: dict[str, Any]) -> tuple[str | None, str | None]:
    category = pin.get("category")
    item_key = pin.get("itemKey")
    if isinstance(category, str) and isinstance(item_key, str) and category and item_key:
        return category, item_key
    return None, None


def pin_add_impl(
    *,
    pins_path: Path,
    url: str,
    title: str,
    kind: str,
    category: str | None = None,
    itemKey: str | None = None,
) -> dict[str, Any]:
    pins = _load_pins(pins_path)
    requested_identity = (category, itemKey) if category and itemKey else (None, None)
    if requested_identity != (None, None):
        if any(_pin_identity(pin) == requested_identity for pin in pins):
            return {"added": False, "url": url, "itemKey": itemKey}
    elif any(pin.get("url") == url for pin in pins):
        return {"added": False, "url": url}

    entry: dict[str, Any] = {
        "url": url,
        "title": title,
        "kind": kind,
        "pinnedAt": _now_iso(),
    }
    if category:
        entry["category"] = category
    if itemKey:
        entry["itemKey"] = itemKey

    pins.append(entry)
    _save_pins(pins_path, pins)
    result = {"added": True, "url": url}
    if itemKey:
        result["itemKey"] = itemKey
    return result


def pin_remove_impl(
    *,
    pins_path: Path,
    url: str,
    category: str | None = None,
    itemKey: str | None = None,
) -> dict[str, Any]:
    pins = _load_pins(pins_path)
    requested_identity = (category, itemKey) if category and itemKey else (None, None)
    if requested_identity != (None, None):
        next_pins = [pin for pin in pins if _pin_identity(pin) != requested_identity]
    else:
        next_pins = [pin for pin in pins if pin.get("url") != url]
    if len(next_pins) == len(pins):
        result = {"removed": False, "url": url}
        if itemKey:
            result["itemKey"] = itemKey
        return result

    _save_pins(pins_path, next_pins)
    result = {"removed": True, "url": url}
    if itemKey:
        result["itemKey"] = itemKey
    return result


# ---------------------------------------------------------------------------
# Pin-card resolver — resolve a file/title selector to the SAME pin target the
# Browse UI computes, so a CLI/MCP pin renders on the real card without a
# browser round-trip. Mirrors apps/dashboard/lib/browse/{transforms,pinOrdering}.ts
# (browseIndexItemId / canonicalBrowseUrl / browseItemPinTarget). itemKey is the
# primary matcher; keep it byte-identical to the dashboard (see parity test).
# ---------------------------------------------------------------------------

SOURCE_BACKED_ID_CATEGORIES = {"documents", "vault", "scripts", "tests"}


def _first_str(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed:
                return trimmed
    return None


def _has_overlay_identity(entry: dict[str, Any]) -> bool:
    md = entry.get("metadata") or {}
    return (
        _first_str(
            entry.get("vault_scope"),
            md.get("vault_scope"),
            entry.get("promotion_state"),
            md.get("promotion_state"),
            entry.get("source_root"),
            md.get("source_root"),
        )
        is not None
    )


def browse_pin_item_id(entry: dict[str, Any], category: str) -> str:
    """Port of browseIndexItemId() — the id used in itemKey ``{category}::{id}``."""
    explicit_id = _first_str(entry.get("id"))
    source_path = _first_str(entry.get("source_path"))
    if category == "wiki":
        if explicit_id:
            return explicit_id
        if source_path:
            return source_path
    if category in SOURCE_BACKED_ID_CATEGORIES:
        if explicit_id and _has_overlay_identity(entry) and ":" in explicit_id:
            return explicit_id
        if source_path:
            return source_path
    if explicit_id:
        return explicit_id
    return _first_str(entry.get("title")) or source_path or _first_str(entry.get("name")) or category


def browse_pin_url(entry: dict[str, Any], category: str) -> str:
    """Port of canonicalBrowseUrl() for a raw browse-index entry."""
    md = entry.get("metadata") or {}
    return _first_str(md.get("url")) or _first_str(entry.get("source_path")) or browse_pin_item_id(entry, category)


def browse_pin_target(entry: dict[str, Any], category: str) -> dict[str, str]:
    """Deterministic pin target for a raw browse-index entry (== browseItemPinTarget)."""
    item_id = browse_pin_item_id(entry, category)
    return {
        "category": category,
        "itemKey": f"{category}::{item_id}",
        "url": browse_pin_url(entry, category),
        "title": _first_str(entry.get("title")) or item_id,
        "kind": "browse-card",
    }


def _basename_no_ext(path: str | None) -> str:
    if not path:
        return ""
    return os.path.splitext(os.path.basename(path))[0]


def _resolve_browse_item(
    items: list[dict[str, Any]], selector: str
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Pick the item a selector refers to. Returns ``(match, ambiguous_candidates)``."""
    sel = selector.strip()
    sel_lower = sel.lower()
    # 1. exact id / title / source_path
    for entry in items:
        if sel in (
            str(entry.get("id") or ""),
            str(entry.get("title") or ""),
            str(entry.get("source_path") or ""),
        ):
            return entry, []
    # 2. exact basename (filename without extension)
    exact_base = [e for e in items if _basename_no_ext(e.get("source_path")) == sel]
    if len(exact_base) == 1:
        return exact_base[0], []
    # 3. case-insensitive exact title / id
    ci = [
        e
        for e in items
        if str(e.get("title") or "").lower() == sel_lower or str(e.get("id") or "").lower() == sel_lower
    ]
    if len(ci) == 1:
        return ci[0], []
    # 4. a single search candidate
    if len(items) == 1:
        return items[0], []
    return None, items


def pin_card_impl(
    *,
    pins_path: Path,
    category: str,
    selector: str,
) -> dict[str, Any]:
    """Resolve a Browse card by file/title selector and pin it — deterministic, no UI."""
    # Lazy import: the browse index module imports broadly; keep it off module load.
    from src.mcp.augur_framework.tools.infrastructure.browse.index import (
        browse_index_impl,
    )

    payload = json.loads(browse_index_impl(category, search=selector, limit=50))
    items = payload.get("items") or []
    if not items:
        return {
            "added": False,
            "error": f"No '{category}' card matches {selector!r}.",
            "status": payload.get("status"),
        }

    match, candidates = _resolve_browse_item(items, selector)
    if match is None:
        return {
            "added": False,
            "error": (f"{selector!r} is ambiguous in '{category}' " f"({len(candidates)} matches) — be more specific."),
            "candidates": [{"id": c.get("id"), "title": c.get("title")} for c in candidates[:10]],
        }

    target = browse_pin_target(match, category)
    result = pin_add_impl(pins_path=pins_path, **target)
    result["itemKey"] = target["itemKey"]
    result["title"] = target["title"]
    result["category"] = category
    return result


def _pins_path() -> Path:
    from src.lib.brain_layout import vault_machine_dir

    return vault_machine_dir(get_vault_dir(), "system") / "pins.yaml"


def register_pin_tools(mcp: Any, mcp_tool_interceptor: Any, metrics: Any) -> None:
    """Wire pin-add / pin-remove / pin-list onto the MCP server."""

    @mcp.tool(
        name="pin-add",
        annotations=tool_annotations(
            {
                "title": "Pin Page or Artifact",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def pin_add(
        url: str,
        title: str,
        kind: str,
        category: str | None = None,
        itemKey: str | None = None,
    ) -> str:
        metrics.track_tool("pin_add")
        result = pin_add_impl(
            pins_path=_pins_path(),
            url=url,
            title=title,
            kind=kind,
            category=category,
            itemKey=itemKey,
        )
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="pin-remove",
        annotations=tool_annotations(
            {
                "title": "Remove Pin",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def pin_remove(
        url: str,
        category: str | None = None,
        itemKey: str | None = None,
    ) -> str:
        metrics.track_tool("pin_remove")
        return json.dumps(
            pin_remove_impl(
                pins_path=_pins_path(),
                url=url,
                category=category,
                itemKey=itemKey,
            ),
            indent=2,
        )

    @mcp.tool(
        name="pin-list",
        annotations=tool_annotations(
            {
                "title": "List Pins",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def pin_list() -> str:
        metrics.track_tool("pin_list")
        return json.dumps(pin_list_impl(pins_path=_pins_path()), indent=2)

    @mcp.tool(
        name="pin-card",
        annotations=tool_annotations(
            {
                "title": "Pin Browse Card by Selector",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def pin_card(category: str, selector: str) -> str:
        """Resolve a Browse card by file/title and pin it (no dashboard needed)."""
        metrics.track_tool("pin_card")
        return json.dumps(
            pin_card_impl(
                pins_path=_pins_path(),
                category=category,
                selector=selector,
            ),
            indent=2,
        )
