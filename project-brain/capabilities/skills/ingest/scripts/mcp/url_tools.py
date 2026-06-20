"""MCP tool definitions for URL ingestion atomic ops.

This module exposes two atomic operations per the surface decision matrix
(docs/references/surface-decision-matrix.md):

  url-extract     — Mode-2 helper. Fetches and parses a URL. Used by callers
                    without an AI session present (dashboard, daemon). Agent
                    callers should usually fetch with their own browser/HTTP
                    tools per docs/references/agent-fetch-primitives.md.
  save-url-source — Atomic write. Persists a source card with already-parsed
                    title/body/url into the vault. Returns the resulting path
                    and content hash; idempotent on content_hash.
  save-prompt     — Atomic write. Persists a user prompt card with an
                    already-parsed label/description/body into the vault.
                    Returns the resulting path and content hash; idempotent
                    on content_hash.

The legacy `ingest-url` tool that combined fetch+extract+save was retired
because it conflated workflow with atomic op (see agent-vs-mcp-examples.md
Example 2). Callers compose `url-extract` + `save-url-source` instead.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from src.config.paths import get_vault_dir
from src.lib.frontmatter_utils import parse_frontmatter

from skills.ingest.scripts.mcp._shared import tool_annotations
from src.lib.ingest.note_index_refresh import (
    refresh_notes_browse_index,
    refresh_browse_after_write,
)
from skills.ingest.scripts.prompt_cards import (
    compute_prompt_hash,
    find_existing_prompt_card,
    write_prompt_card,
)
from skills.ingest.scripts.url_ingest import (
    ExtractionError,
    Fetcher,
    canonicalize_url,
    compute_content_hash,
    fetch_and_extract,
    find_existing_url_card,
    maybe_await_fetch,
    write_url_source_card,
)

try:
    from src.mcp.augur_shared.logging import get_entity_logger
except ImportError:
    import logging

    def get_entity_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_entity_logger("ingest.url")


def _parse_tags(tags: str | list[Any]) -> list[str]:
    try:
        parsed = json.loads(tags) if isinstance(tags, str) else tags
    except json.JSONDecodeError as exc:
        raise ValueError("tags must be a JSON list") from exc
    if not isinstance(parsed, list) or any(not isinstance(tag, str) for tag in parsed):
        raise ValueError("tags must be a JSON list")
    return parsed


def _lead_summary(body: str, *, max_chars: int = 280) -> str:
    """Return a deterministic single-line lead excerpt of the body.

    No LLM call — this is a mechanical excerpt so the `note-url` workflow can
    return a useful summary line without an AI session. The agent is free to
    write a richer summary in its reply; this just guarantees the command's
    JSON result alone is enough to report back to the user.
    """
    text = " ".join(body.split())
    if len(text) <= max_chars:
        return text
    clipped = text[:max_chars]
    for separator in (". ", "! ", "? "):
        idx = clipped.rfind(separator)
        if idx > max_chars * 0.5:
            return clipped[: idx + 1].strip()
    return f"{clipped.rsplit(' ', 1)[0].strip()}…"


def _routed_vault_dir(
    *,
    vault_dir: Path | None,
    to: str | None,
    cwd: str | Path | None,
    registry_path: Path | None,
) -> tuple[Path | None, dict[str, str] | None, dict[str, object] | None]:
    if to is None and cwd is None and registry_path is None:
        return vault_dir or get_vault_dir(), None, None

    from src.lib.brain_write_routing import resolve_write_target

    try:
        target = resolve_write_target(
            explicit_brain=to,
            cwd=Path(cwd) if cwd is not None else None,
            registry_path=registry_path,
        )
    except KeyError as exc:
        return None, None, {"success": False, "error": str(exc)}
    if target.mode == "packet":
        return None, target.summary(), {
            "success": False,
            "error": f"brain {target.brain.id} requires packet-based writes",
            "brain": target.summary(),
            "packet_root": str(target.packet_root),
        }
    return target.notes_vault_dir, target.summary(), None


async def url_extract_impl(
    *,
    url: str = "",
    fetcher: Fetcher = fetch_and_extract,
) -> str:
    """Fetch and parse a URL (Mode-2 helper for callers without an AI session).

    Atomic: returns parsed content, never writes. Returns a JSON string with
    {success, canonical_url, title, body, content_hash} on success or
    {success: False, error} on failure.

    Agent callers should usually pick a fetcher from
    docs/references/agent-fetch-primitives.md and call `save-url-source`
    directly with the parsed content instead of invoking this tool.
    """
    try:
        if not url.strip():
            return json.dumps({"success": False, "error": "url is required"})

        canonical_url = canonicalize_url(url)
        extracted = await maybe_await_fetch(fetcher, canonical_url)
        body = extracted["body"]
        title = extracted["title"]
        content_hash = compute_content_hash(canonical_url, body)

        return json.dumps(
            {
                "success": True,
                "canonical_url": canonical_url,
                "title": title,
                "body": body,
                "content_hash": content_hash,
            },
            indent=2,
        )
    except ExtractionError as exc:
        logger.warning("url-extract failed for %s: %s", url, exc)
        return json.dumps({"success": False, "error": str(exc)})
    except Exception as exc:
        logger.error("url-extract failed: %s", exc, exc_info=True)
        return json.dumps({"success": False, "error": str(exc)})


async def save_url_source_impl(
    *,
    url: str = "",
    title: str = "",
    body: str = "",
    tags: str | list[Any] = "[]",
    note: str = "",
    vault_dir: Path | None = None,
    to: str | None = None,
    cwd: str | Path | None = None,
    registry_path: Path | None = None,
) -> str:
    """Persist a URL source card with already-parsed content.

    Atomic write op. Inputs are pre-parsed by the caller (agent picked its own
    fetcher per agent-fetch-primitives.md, or the dashboard composed this with
    `url-extract` first). Returns JSON with {success, path, sha256,
    deduplicated, canonical_url, title}.

    Idempotent on content_hash: re-saving the same canonical_url + body
    returns the existing card path with deduplicated=true.
    """
    try:
        if not url.strip():
            return json.dumps({"success": False, "error": "url is required"})
        if not body.strip():
            return json.dumps({"success": False, "error": "body is required"})

        parsed_tags = _parse_tags(tags)
        canonical_url = canonicalize_url(url)
        resolved_title = title.strip() or canonical_url
        content_hash = compute_content_hash(canonical_url, body)
        resolved_vault_dir, brain_summary, route_error = _routed_vault_dir(
            vault_dir=vault_dir,
            to=to,
            cwd=cwd,
            registry_path=registry_path,
        )
        if route_error is not None:
            return json.dumps(route_error)
        assert resolved_vault_dir is not None

        existing = find_existing_url_card(resolved_vault_dir, content_hash)
        if existing is not None:
            result: dict[str, object] = {
                "success": True,
                "path": str(existing),
                "sha256": content_hash,
                "deduplicated": True,
                "canonical_url": canonical_url,
                "title": resolved_title,
            }
            if brain_summary is not None:
                result["brain"] = brain_summary
            return json.dumps(result, indent=2)

        path = write_url_source_card(
            vault_dir=resolved_vault_dir,
            meta={
                "title": resolved_title,
                "canonical_url": canonical_url,
                "content_hash": content_hash,
                "tags": parsed_tags,
                "captured_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "note": note or None,
            },
            body=body,
        )
        browse_index = refresh_notes_browse_index(vault_dir=resolved_vault_dir)
        result = {
            "success": True,
            "path": str(path),
            "sha256": content_hash,
            "deduplicated": False,
            "canonical_url": canonical_url,
            "title": resolved_title,
            "browse_index": browse_index.to_dict(),
        }
        if brain_summary is not None:
            result["brain"] = brain_summary
        return json.dumps(result, indent=2)
    except ValueError as exc:
        return json.dumps({"success": False, "error": str(exc)})
    except Exception as exc:
        logger.error("save-url-source failed: %s", exc, exc_info=True)
        return json.dumps({"success": False, "error": str(exc)})


async def note_url_impl(
    *,
    url: str = "",
    tags: str | list[Any] = "[]",
    note: str = "",
    fetcher: Fetcher = fetch_and_extract,
    vault_dir: Path | None = None,
    to: str | None = None,
    cwd: str | Path | None = None,
    registry_path: Path | None = None,
) -> str:
    """CLI/agent workflow: fetch a URL's full prose and persist a card in one call.

    This is a WORKFLOW composition over the two atomic ops (`url-extract` +
    `save-url-source`), exposed only on the cli/agents-md surfaces. It does NOT
    reintroduce the retired combined `ingest-url` MCP tool (see module
    docstring): the dashboard/MCP surface still composes the atomic ops
    separately, and the agent keeps the judgment of *whether* to capture a URL
    (it decided to run `/note` and chose this URL). The only thing collapsed
    here is the mechanical fetch+persist, so the agent never has to shuttle a
    multi-thousand-character body through the shell or hand-roll a script.

    Returns JSON with {success, path, sha256, deduplicated, canonical_url,
    title, summary, word_count, browse_index}. Idempotent on content_hash, same
    as `save-url-source`.
    """
    try:
        if not url.strip():
            return json.dumps({"success": False, "error": "url is required"})

        canonical_url = canonicalize_url(url)
        try:
            extracted = await maybe_await_fetch(fetcher, canonical_url)
        except ExtractionError as exc:
            logger.warning("note-url fetch failed for %s: %s", url, exc)
            return json.dumps({"success": False, "error": f"fetch failed: {exc}"})

        body = extracted["body"]
        title = extracted["title"]

        saved_raw = await save_url_source_impl(
            url=url,
            title=title,
            body=body,
            tags=tags,
            note=note,
            vault_dir=vault_dir,
            to=to,
            cwd=cwd,
            registry_path=registry_path,
        )
        saved = json.loads(saved_raw)
        if not saved.get("success"):
            return saved_raw

        saved["summary"] = _lead_summary(body)
        saved["word_count"] = len(body.split())
        return json.dumps(saved, indent=2)
    except Exception as exc:
        logger.error("note-url failed: %s", exc, exc_info=True)
        return json.dumps({"success": False, "error": str(exc)})


async def save_prompt_impl(
    *,
    label: str = "",
    description: str = "",
    body: str = "",
    source_url: str = "",
    vault_dir: Path | None = None,
    to: str | None = None,
    cwd: str | Path | None = None,
    registry_path: Path | None = None,
) -> str:
    """Persist a user prompt card under <vault>/prompts/. Inputs pre-parsed by caller."""
    try:
        if not label.strip():
            return json.dumps({"success": False, "error": "label is required"})
        if not body.strip():
            return json.dumps({"success": False, "error": "body is required"})

        resolved_vault_dir, brain_summary, route_error = _routed_vault_dir(
            vault_dir=vault_dir,
            to=to,
            cwd=cwd,
            registry_path=registry_path,
        )
        if route_error is not None:
            return json.dumps(route_error)
        assert resolved_vault_dir is not None
        content_hash = compute_prompt_hash(body)
        existing = find_existing_prompt_card(resolved_vault_dir, content_hash)
        if existing is not None:
            existing_meta, _ = parse_frontmatter(existing)
            resolved_label = existing_meta.get("label") or label.strip()
            result: dict[str, object] = {
                "success": True,
                "path": str(existing),
                "sha256": content_hash,
                "deduplicated": True,
                "label": resolved_label,
            }
            if brain_summary is not None:
                result["brain"] = brain_summary
            return json.dumps(result, indent=2)

        path = write_prompt_card(
            vault_dir=resolved_vault_dir,
            label=label,
            description=description,
            body=body,
            source_url=source_url,
        )
        statuses = refresh_browse_after_write(paths=[path], vault_dir=resolved_vault_dir)
        result = {
            "success": True,
            "path": str(path),
            "sha256": content_hash,
            "deduplicated": False,
            "label": label.strip(),
            "browse_index": {cat: s.to_dict() for cat, s in statuses.items()},
        }
        if brain_summary is not None:
            result["brain"] = brain_summary
        return json.dumps(result, indent=2)
    except Exception as exc:
        logger.error("save-prompt failed: %s", exc, exc_info=True)
        return json.dumps({"success": False, "error": str(exc)})


def register_url_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any = None,
) -> None:
    """Register `url-extract`, `save-url-source`, and `save-prompt` MCP tools."""

    @mcp.tool(
        name="url-extract",
        annotations=tool_annotations(
            {
                "title": "Extract URL",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def url_extract_tool(url: str = "") -> str:
        """Fetch and parse a URL (Mode-2 helper). Returns parsed content; does not write."""
        if metrics:
            metrics.track_tool("url_extract", skill="ingest")
        return await url_extract_impl(url=url)

    @mcp.tool(
        name="note-url",
        annotations=tool_annotations(
            {
                "title": "Note a URL (fetch + save)",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def note_url_tool(
        url: str = "",
        tags: str | list[Any] = "[]",
        note: str = "",
        to: str | None = None,
        cwd: str | None = None,
    ) -> str:
        """CLI/agent workflow: fetch a URL's full prose and persist a card in one call.

        Composes url-extract + save-url-source so `/note <url>` is a single
        invocation. Returns {path, title, summary, word_count, deduplicated, ...}.
        """
        if metrics:
            metrics.track_tool("note_url", skill="ingest")
        return await note_url_impl(url=url, tags=tags, note=note, to=to, cwd=cwd)

    @mcp.tool(
        name="save-url-source",
        annotations=tool_annotations(
            {
                "title": "Save URL Source Card",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def save_url_source_tool(
        url: str = "",
        title: str = "",
        body: str = "",
        tags: str | list[Any] = "[]",
        note: str = "",
        to: str | None = None,
        cwd: str | None = None,
    ) -> str:
        """Persist a URL source card. Inputs are pre-parsed by the caller."""
        if metrics:
            metrics.track_tool("save_url_source", skill="ingest")
        return await save_url_source_impl(
            url=url,
            title=title,
            body=body,
            tags=tags,
            note=note,
            to=to,
            cwd=cwd,
        )

    @mcp.tool(
        name="save-prompt",
        annotations=tool_annotations(
            {
                "title": "Save Prompt Card",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def save_prompt_tool(
        label: str = "",
        description: str = "",
        body: str = "",
        source_url: str = "",
        to: str | None = None,
        cwd: str | None = None,
    ) -> str:
        """Persist a user prompt card. Inputs are pre-parsed by the caller."""
        if metrics:
            metrics.track_tool("save_prompt", skill="ingest")
        return await save_prompt_impl(
            label=label,
            description=description,
            body=body,
            source_url=source_url,
            to=to,
            cwd=cwd,
        )


__all__ = [
    "note_url_impl",
    "save_prompt_impl",
    "save_url_source_impl",
    "url_extract_impl",
    "register_url_tools",
]
