"""Artifacts MCP tools: sidecar I/O and artifact metadata helpers."""

from __future__ import annotations

import asyncio
import glob as _glob
import json
import re
import shutil
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from src.config.paths import get_documents_dir
from src.lib.artifacts_sidecar import (
    Sidecar,
    read_sidecar,
    write_sidecar,
)
from src.lib.artifacts_sidecar import (
    iter_artifact_files as _iter_artifact_files,
)
from src.lib.artifacts_sidecar import (
    sidecar_path_for_html as _sidecar_path_for_html,
)
from src.mcp.augur_shared.annotations import tool_annotations
from src.mcp.augur_shared.logging import get_entity_logger

_log = get_entity_logger("mcp.artifacts")


def _refresh_pages_index() -> None:
    """Best-effort scoped reindex so artifact changes appear in Browse pages.

    Failures are logged, never raised — saving the artifact must not fail
    because the index refresh did.
    """
    try:
        from src.config.paths import get_rag_dir

        # Module-attribute access (not `from ... import reindex_category`) so the
        # test's monkeypatch on src.lib.index.unified_indexer.reindex_category
        # takes effect (late binding).
        from src.lib.index import unified_indexer
        from src.mcp.augur_shared.config import get_project_root

        unified_indexer.reindex_category(
            "pages",
            get_project_root(),
            get_rag_dir(),
            documents_dir=get_documents_dir(),
        )
    except Exception:
        _log.warning("pages index refresh after artifact change failed", exc_info=True)


class _HtmlTitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_title = False
        self._in_h1 = False
        self._title_closed = False
        self._h1_closed = False
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        tag_name = tag.lower()
        if tag_name == "title" and not self._title_closed:
            self._in_title = True
        elif tag_name == "h1" and not self._h1_closed:
            self._in_h1 = True

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if tag_name == "title" and self._in_title:
            self._in_title = False
            self._title_closed = True
        elif tag_name == "h1" and self._in_h1:
            self._in_h1 = False
            self._h1_closed = True

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        elif self._in_h1:
            self.h1_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())

    @property
    def h1(self) -> str:
        return " ".join("".join(self.h1_parts).split())


def derive_title(html: str, fallback: str) -> str:
    """Derive an artifact title from HTML title, first h1, or filename."""
    parser = _HtmlTitleParser()
    parser.feed(html)
    parser.close()
    return parser.title or parser.h1 or Path(fallback).stem


_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def derive_slug(*, title: str = "", filename: str = "") -> str:
    """Derive a URL-safe slug from a title or filename."""
    candidate = title or Path(filename).stem
    slug = _SLUG_NON_ALNUM.sub("-", candidate.lower()).strip("-")
    return slug or "artifact"


def artifacts_list_impl(*, docs_dir: Path) -> dict[str, Any]:
    """Return Browse-shape entries for every sidecar-backed HTML artifact."""
    entries: list[dict[str, Any]] = []
    for html_path, sidecar_path in _iter_artifact_files(docs_dir):
        sc = read_sidecar(sidecar_path)
        entries.append(
            {
                "slug": sc.slug,
                "title": sc.title,
                "kind": sc.kind,
                "hub": sc.hub,
                "url": f"/artifact/{sc.slug}",
                "path": html_path.as_posix(),
                "tags": sc.tags,
                "promoted_at": sc.promoted_at,
                "created_at": sc.created_at,
            }
        )
    return {"artifacts": entries}


def _hub_from_path(path: Path, docs_dir: Path) -> str:
    """Infer hub from the first path segment under docs_dir."""
    rel = path.relative_to(docs_dir)
    return rel.parts[0] if rel.parts else "uncategorized"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _collect_existing_slugs(docs_dir: Path) -> set[str]:
    slugs: set[str] = set()
    for sidecar_path in docs_dir.rglob("*.meta.yaml"):
        try:
            slug = read_sidecar(sidecar_path).slug
        except Exception:
            continue
        if slug:
            slugs.add(slug)
    return slugs


def _resolve_unique_slug_from_seen(base_slug: str, seen: set[str]) -> str:
    candidate = base_slug
    counter = 2
    while candidate in seen:
        candidate = f"{base_slug}-{counter}"
        counter += 1
    seen.add(candidate)
    return candidate


def artifacts_reindex_impl(
    *,
    docs_dir: Path,
    dry_run: bool = False,
    import_glob: str | None = None,
    import_hub: str = "uncategorized",
) -> dict[str, Any]:
    """Scan docs_dir for HTML artifacts and optionally import external HTMLs."""
    created = 0
    proposed = 0
    imported = 0
    proposals: list[dict[str, Any]] = []
    seen_slugs = _collect_existing_slugs(docs_dir)

    if import_glob:
        for src in sorted(Path(p) for p in _glob.glob(import_glob)):
            if not src.is_file():
                continue
            target_dir = docs_dir / import_hub / "artifacts"
            html_text = src.read_text(encoding="utf-8", errors="replace")
            title = derive_title(html_text, fallback=src.name)
            slug = _resolve_unique_slug_from_seen(
                derive_slug(title=title, filename=src.name),
                seen_slugs,
            )
            target = target_dir / f"{slug}.html"
            sidecar_path = _sidecar_path_for_html(target)
            proposal = {
                "html": target.as_posix(),
                "sidecar": sidecar_path.as_posix(),
                "slug": slug,
                "title": title,
                "hub": import_hub,
            }
            if dry_run:
                proposals.append(proposal)
                proposed += 1
                continue

            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            write_sidecar(
                sidecar_path,
                Sidecar(
                    slug=slug,
                    title=title,
                    kind="generated",
                    hub=import_hub,
                    source={"type": "brainstorm", "origin_path": str(src)},
                    created_at=_now_iso(),
                    promoted_at=_now_iso(),
                ),
            )
            imported += 1

    for html_path in sorted(docs_dir.rglob("*.html")):
        sidecar_path = _sidecar_path_for_html(html_path)
        if sidecar_path.exists():
            continue
        html_text = html_path.read_text(encoding="utf-8", errors="replace")
        title = derive_title(html_text, fallback=html_path.name)
        slug = _resolve_unique_slug_from_seen(
            derive_slug(title=title, filename=html_path.name),
            seen_slugs,
        )
        hub = _hub_from_path(html_path, docs_dir)
        proposal = {
            "html": html_path.as_posix(),
            "sidecar": sidecar_path.as_posix(),
            "slug": slug,
            "title": title,
            "hub": hub,
        }
        if dry_run:
            proposals.append(proposal)
            proposed += 1
            continue

        write_sidecar(
            sidecar_path,
            Sidecar(
                slug=slug,
                title=title,
                kind="saved",
                hub=hub,
                source={"type": "manual", "origin_path": str(html_path)},
                created_at=_now_iso(),
                promoted_at=_now_iso(),
            ),
        )
        created += 1

    return {
        "created": created,
        "proposed": proposed,
        "imported": imported,
        "proposals": proposals,
    }


def _resolve_unique_slug(docs_dir: Path, target_dir: Path, slug: str) -> str:
    seen_slugs = _collect_existing_slugs(docs_dir)
    candidate = slug
    counter = 2
    while (
        candidate in seen_slugs
        or (target_dir / f"{candidate}.html").exists()
        or (target_dir / f"{candidate}.meta.yaml").exists()
    ):
        candidate = f"{slug}-{counter}"
        counter += 1
    return candidate


def _is_brainstorm_source(source_path: Path) -> bool:
    normalized = str(source_path).replace("\\", "/")
    return "/.superpowers/brainstorm/" in normalized or "/brainstorm/" in normalized


def save_artifact_impl(
    *,
    docs_dir: Path,
    source_path: Path,
    hub: str,
    slug: str | None,
    title: str | None,
    tags: list[str] | None,
) -> dict[str, Any]:
    """Promote one HTML file into docs_dir/<hub>/artifacts/<slug>.html."""
    html_text = source_path.read_text(encoding="utf-8", errors="replace")
    resolved_title = title or derive_title(html_text, fallback=source_path.name)
    base_slug = slug or derive_slug(title=resolved_title, filename=source_path.name)
    target_dir = docs_dir / hub / "artifacts"
    target_dir.mkdir(parents=True, exist_ok=True)
    final_slug = _resolve_unique_slug(docs_dir, target_dir, base_slug)
    target = target_dir / f"{final_slug}.html"
    sidecar_path = _sidecar_path_for_html(target)

    shutil.copy2(source_path, target)
    is_brainstorm = _is_brainstorm_source(source_path)
    write_sidecar(
        sidecar_path,
        Sidecar(
            slug=final_slug,
            title=resolved_title,
            kind="generated" if is_brainstorm else "saved",
            hub=hub,
            source={
                "type": "brainstorm" if is_brainstorm else "manual",
                "origin_path": str(source_path),
            },
            tags=list(tags or []),
            created_at=_now_iso(),
            promoted_at=_now_iso(),
        ),
    )
    return {"slug": final_slug, "target": target.as_posix(), "sidecar": sidecar_path.as_posix()}


def register_artifacts_tools(
    mcp: Any,
    mcp_tool_interceptor: Any,
    metrics: Any,
) -> None:
    """Wire artifact discovery/promote tools onto the MCP server."""

    @mcp.tool(
        name="save-artifact",
        annotations=tool_annotations(
            {
                "title": "Save HTML Artifact",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def save_artifact(
        source_path: str,
        hub: str,
        slug: str | None = None,
        title: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        metrics.track_tool("save_artifact")
        result = save_artifact_impl(
            docs_dir=get_documents_dir(),
            source_path=Path(source_path),
            hub=hub,
            slug=slug,
            title=title,
            tags=tags,
        )
        await asyncio.to_thread(_refresh_pages_index)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="artifacts-reindex",
        annotations=tool_annotations(
            {
                "title": "Reindex HTML Artifacts",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def artifacts_reindex(
        dry_run: bool = False,
        import_glob: str | None = None,
        import_hub: str = "uncategorized",
    ) -> str:
        metrics.track_tool("artifacts_reindex")
        result = artifacts_reindex_impl(
            docs_dir=get_documents_dir(),
            dry_run=dry_run,
            import_glob=import_glob,
            import_hub=import_hub,
        )
        if not dry_run:
            await asyncio.to_thread(_refresh_pages_index)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="artifacts-list",
        annotations=tool_annotations(
            {
                "title": "List HTML Artifacts",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def artifacts_list() -> str:
        metrics.track_tool("artifacts_list")
        return json.dumps(artifacts_list_impl(docs_dir=get_documents_dir()), indent=2)
