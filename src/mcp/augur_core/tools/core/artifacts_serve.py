"""artifact-resolve / artifact-html — warm-server artifact metadata + raw HTML."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config.paths import get_documents_dir
from src.lib.artifacts_sidecar import iter_artifact_files, read_sidecar
from src.mcp.augur_shared.annotations import tool_annotations


def _under_allowed_root(path: Path, allowed: list[Path]) -> bool:
    """True if path resolves to (or under) at least one allowed root.

    Inlined (not imported from the framework server) so the lightweight core
    server stays independent of augur_framework. `strict=True` makes a
    symlink-escape attempt raise and return False.
    """
    try:
        resolved = path.resolve(strict=True)
        return any(resolved.is_relative_to(root.resolve()) for root in allowed)
    except OSError:
        return False


def resolve_artifact(slug: str, *, docs_dir: Path) -> dict[str, Any] | None:
    for html_path, sidecar_path in iter_artifact_files(docs_dir):
        try:
            sc = read_sidecar(sidecar_path)
        except Exception:
            # A corrupt/incomplete sidecar (missing a required field) must not
            # 500 the whole resolve — skip it and keep scanning for the slug.
            continue
        if sc.slug == slug:
            return {
                "slug": sc.slug,
                "path": html_path.as_posix(),
                "title": sc.title,
                "kind": sc.kind,
                "hub": sc.hub,
                "tags": sc.tags,
                "url": f"/artifact/{sc.slug}",
            }
    return None


def artifact_resolve_impl(slug: str, *, docs_dir: Path) -> dict[str, Any]:
    meta = resolve_artifact(slug, docs_dir=docs_dir)
    if not meta:
        return {"found": False}
    return {"found": True, **meta}


def artifact_html_impl(slug: str, *, docs_dir: Path, allowed_roots: list[Path]) -> dict[str, Any]:
    meta = resolve_artifact(slug, docs_dir=docs_dir)
    if not meta:
        return {"found": False}
    path = Path(meta["path"])
    if not _under_allowed_root(path, allowed_roots):
        return {"found": False}
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"found": False}
    return {"found": True, "content": content}


def register_artifacts_serve_tools(mcp: Any, mcp_tool_interceptor: Any, metrics: Any) -> None:
    # mcp_tool_interceptor is optional (the registry convention across
    # register_core_tools): it is None when no correlation-id wrapper is
    # supplied (e.g. tests). Use a no-op so it can stay a stacked decorator
    # without crashing on `@None`.
    def _intercept(fn: Any) -> Any:
        return mcp_tool_interceptor(fn) if mcp_tool_interceptor else fn

    @mcp.tool(
        name="artifact-resolve",
        annotations=tool_annotations(
            {
                "title": "Resolve Artifact",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @_intercept
    async def artifact_resolve(slug: str) -> str:
        metrics.track_tool("artifact_resolve")
        return json.dumps(artifact_resolve_impl(slug, docs_dir=get_documents_dir()))

    @mcp.tool(
        name="artifact-html",
        annotations=tool_annotations(
            {
                "title": "Read Artifact HTML",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @_intercept
    async def artifact_html(slug: str) -> str:
        metrics.track_tool("artifact_html")
        return json.dumps(artifact_html_impl(slug, docs_dir=get_documents_dir(), allowed_roots=[get_documents_dir()]))
