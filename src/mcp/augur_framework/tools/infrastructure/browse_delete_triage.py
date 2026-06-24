"""browse-delete-triage — classify selected Browse items into trash / sweep / blocked."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from src.config.paths import get_rag_dir
from src.mcp.augur_framework.tools.infrastructure.artifact_reconcile import _under_allowed_root
from src.mcp.augur_framework.tools.infrastructure.browse_trash import browse_trash_default_roots
from src.mcp.augur_shared.annotations import tool_annotations
from src.mcp.augur_shared.config import get_project_root


def _is_git_tracked(path: Path, repo_root: Path) -> bool:
    try:
        resolved = path.resolve()
        resolved.relative_to(repo_root.resolve())
    except (OSError, ValueError):
        return False
    try:
        # `--` ends option parsing so a filename beginning with `-` can't be
        # smuggled as a git flag (argv flag injection); pass the resolved
        # absolute path we just verified is under repo_root.
        r = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", str(resolved)],
            cwd=repo_root,
            capture_output=True,
        )
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _has_rag_chunks(path: Path) -> bool:
    """A document/note with downstream RAG chunks needs index cleanup -> sweep."""
    try:
        chunks_root = get_rag_dir() / "chunks"
    except Exception:
        return False
    stem = path.stem
    return chunks_root.is_dir() and any(chunks_root.rglob(f"{stem}*"))


def triage_impl(
    items: list[dict],
    *,
    allowed_roots: list[Path],
    repo_root: Path,
) -> dict[str, Any]:
    trash: list[str] = []
    sweep: list[str] = []
    blocked: list[dict[str, str]] = []
    for item in items:
        iid = str(item.get("id") or "")
        raw = str(item.get("path") or "").strip()
        if not raw:
            blocked.append({"id": iid, "reason": "missing path"})
            continue
        p = Path(raw).expanduser()
        if _is_git_tracked(p, repo_root) or _has_rag_chunks(p):
            sweep.append(iid)
        elif _under_allowed_root(p, allowed_roots):
            trash.append(iid)
        else:
            blocked.append({"id": iid, "reason": "outside allowed roots"})
    return {"trash": trash, "sweep": sweep, "blocked": blocked}


def register_browse_delete_triage_tools(mcp: Any, mcp_tool_interceptor: Any, metrics: Any) -> None:
    @mcp.tool(
        name="browse-delete-triage",
        annotations=tool_annotations(
            {
                "title": "Triage Browse Delete",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def browse_delete_triage(items: list[dict]) -> str:
        metrics.track_tool("browse_delete_triage")
        result = triage_impl(
            items,
            allowed_roots=browse_trash_default_roots(),
            repo_root=get_project_root(),
        )
        return json.dumps(result, indent=2)
