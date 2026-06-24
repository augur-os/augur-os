"""browse-trash — reversible (send2trash) removal for Browse user-content items."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config.paths import get_documents_dir, get_vault_dir
from src.mcp.augur_framework.tools.infrastructure.artifact_reconcile import (
    _send_to_trash,
    _under_allowed_root,
)
from src.mcp.augur_shared.annotations import tool_annotations


def _sidecar_for(path: Path) -> Path | None:
    """Pages artifacts carry a <stem>.meta.yaml sidecar; trash it too."""
    if path.suffix.lower() != ".html":
        return None
    sidecar = path.with_suffix("").with_suffix(".meta.yaml")
    return sidecar if sidecar.is_file() else None


def browse_trash_default_roots() -> list[Path]:
    return [get_documents_dir(), get_vault_dir()]


def browse_trash_impl(paths: list[str], *, allowed_roots: list[Path]) -> dict[str, Any]:
    trashed: list[str] = []
    refused: list[dict[str, str]] = []
    seen: set[Path] = set()
    for raw in paths:
        p = Path(raw).expanduser()
        if not p.is_file():
            refused.append({"path": raw, "reason": "not an existing file"})
            continue
        if not _under_allowed_root(p, allowed_roots):
            refused.append({"path": raw, "reason": "outside allowed roots"})
            continue
        resolved = p.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        _send_to_trash(p)
        trashed.append(str(p))
        sidecar = _sidecar_for(p)
        if sidecar is not None:
            _send_to_trash(sidecar)
            trashed.append(str(sidecar))
    return {"trashed": trashed, "refused": refused}


def register_browse_trash_tools(mcp: Any, mcp_tool_interceptor: Any, metrics: Any) -> None:
    @mcp.tool(
        name="browse-trash",
        annotations=tool_annotations(
            {
                "title": "Trash Browse Items",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def browse_trash(paths: list[str]) -> str:
        metrics.track_tool("browse_trash")
        result = browse_trash_impl(paths, allowed_roots=browse_trash_default_roots())
        return json.dumps(result, indent=2)
