"""Data expiration MCP tool registration.

Tools: check-expirations, set-expiry, get-expiry-status.
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
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from . import logger, SCRIPTS_DIR

try:
    from src.mcp.augur_shared.annotations import tool_annotations
    from src.mcp.augur_shared.config import get_project_root
except ImportError:

    def tool_annotations(annotations: dict) -> dict:
        return annotations

    import os

    def get_project_root() -> Path:
        data_dir = os.environ.get("AUGUR_ROOT")
        if data_dir:
            return Path(data_dir)
        return Path.home() / "Projects" / "augur"


def register_expiration_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register data expiration tools with the MCP server."""

    @mcp.tool(
        name="check-expirations",
        annotations=tool_annotations(
            {
                "title": "Check Data Expirations",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def check_expirations_tool(dry_run: bool = False, files: list[str] | None = None) -> str:
        """Check data files for expired items and add them to review queue.

        Scans tracked YAML files for items that have passed their expiry date.
        Expired items appear in "Needs Your Attention" on the dashboard.

        Args:
            dry_run: If true, report expired items without adding to reviews
            files: Specific files to check (relative to data dir). If empty, checks all.

        Returns:
            str: JSON with expired items found and reviews added
        """
        metrics.track_tool("check_expirations", skill="daemon")

        try:
            sys.path.insert(0, str(SCRIPTS_DIR))
            from check_expirations import check_all_expirations, run_expiration_check

            if files:
                result = check_all_expirations(custom_files=files)
                return json.dumps({"success": True, "dry_run": True, **result}, indent=2)
            else:
                result = run_expiration_check(dry_run=dry_run)
                return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"Failed to check expirations: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="set-expiry",
        annotations=tool_annotations(
            {
                "title": "Set Item Expiry",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def set_expiry_tool(
        file: str,
        list_key: str | None = None,
        index: int | None = None,
        identifier: str | None = None,
        policy: str | None = None,
        expires_at: str | None = None,
        action: str | None = "review",
    ) -> str:
        """Set expiry policy or date on a data item.

        Args:
            file: File path relative to data directory
            list_key: Key in YAML dict containing items (e.g., 'jobs', 'competitors')
            index: Index of item in list (if targeting specific item)
            identifier: Identifier to match (id, title, name, url) instead of index
            policy: Expiry policy: 1d, 2d, 1w, 2w, 1m, 2m, 3m, never
            expires_at: Explicit expiry date (ISO format: 2026-02-15)
            action: Suggested action when expired: review, archive, delete

        Returns:
            str: JSON confirming the update
        """
        metrics.track_tool("set_expiry", skill="daemon")

        try:
            import yaml

            data_dir = get_project_root()
            file_path = data_dir / file

            if not file_path.exists():
                return json.dumps({"success": False, "error": f"File not found: {file}"})

            with open(file_path) as f:
                data = yaml.safe_load(f)

            if data is None:
                return json.dumps({"success": False, "error": "File is empty"})

            # Find target items
            items = None
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict) and list_key:
                items = data.get(list_key, [])
            elif isinstance(data, dict):
                for key in ['jobs', 'competitors', 'items', 'tasks', 'entries']:
                    if key in data and isinstance(data[key], list):
                        items = data[key]
                        break

            if not items:
                return json.dumps({"success": False, "error": "Could not find item list in file"})

            # Find specific item
            target_items = []
            if index is not None:
                if 0 <= index < len(items):
                    target_items = [items[index]]
                else:
                    return json.dumps({"success": False, "error": f"Index {index} out of range"})
            elif identifier:
                for item in items:
                    if isinstance(item, dict):
                        for field in ['id', 'title', 'name', 'url', 'company']:
                            if field in item and identifier in str(item[field]):
                                target_items.append(item)
                                break
            else:
                target_items = [item for item in items if isinstance(item, dict)]

            if not target_items:
                return json.dumps({"success": False, "error": "No matching items found"})

            # Update expiry settings
            for item in target_items:
                if policy:
                    item['expiry_policy'] = policy
                if expires_at:
                    item['expires_at'] = expires_at
                if action:
                    item['expiry_action'] = action

            with open(file_path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

            return json.dumps(
                {
                    "success": True,
                    "updated_items": len(target_items),
                    "file": file,
                    "policy": policy,
                    "expires_at": expires_at,
                    "action": action,
                },
                indent=2,
            )

        except Exception as e:
            logger.error(f"Failed to set expiry: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="get-expiry-status",
        annotations=tool_annotations(
            {
                "title": "Get Expiry Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_expiry_status_tool() -> str:
        """Get overview of expiry status across all tracked data files.

        Returns counts of items by expiry state:
        - expired: Past expiry date
        - expiring_soon: Within 7 days of expiry
        - healthy: More than 7 days until expiry
        - no_expiry: No expiry policy set (uses default)
        - never: Explicitly marked as never expiring
        """
        metrics.track_tool("get_expiry_status", skill="daemon")

        try:
            sys.path.insert(0, str(SCRIPTS_DIR))
            from check_expirations import (
                TRACKED_FILES,
                calculate_expiry_date,
                extract_items_from_file,
            )

            data_dir = get_project_root()
            now = datetime.now()
            soon_threshold = now.replace(hour=0, minute=0, second=0, microsecond=0)

            stats = {
                "expired": 0,
                "expiring_soon": 0,
                "healthy": 0,
                "no_expiry": 0,
                "never": 0,
            }

            file_stats = []

            for file_rel in TRACKED_FILES:
                file_path = data_dir / file_rel
                if not file_path.exists():
                    continue

                items = extract_items_from_file(file_path)
                file_stat = {
                    "file": file_rel,
                    "total": len(items),
                    "expired": 0,
                    "expiring_soon": 0,
                    "healthy": 0,
                    "no_expiry": 0,
                    "never": 0,
                }

                for item, _ in items:
                    if item.get('expiry_policy') == 'never':
                        file_stat["never"] += 1
                        stats["never"] += 1
                        continue

                    expiry_date = calculate_expiry_date(item)

                    if expiry_date is None:
                        file_stat["no_expiry"] += 1
                        stats["no_expiry"] += 1
                    elif now > expiry_date:
                        file_stat["expired"] += 1
                        stats["expired"] += 1
                    elif expiry_date <= soon_threshold:
                        file_stat["expiring_soon"] += 1
                        stats["expiring_soon"] += 1
                    else:
                        file_stat["healthy"] += 1
                        stats["healthy"] += 1

                file_stats.append(file_stat)

            return json.dumps(
                {
                    "success": True,
                    "checked_at": now.isoformat(),
                    "summary": stats,
                    "total_items": sum(stats.values()),
                    "files": file_stats,
                },
                indent=2,
            )

        except Exception as e:
            logger.error(f"Failed to get expiry status: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})
