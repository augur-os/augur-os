"""MCP tool for correcting note classification frontmatter."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, NoReturn

from src.lib.frontmatter_utils import (
    VAULT_SYSTEM_FIELD_MAP,
    parse_frontmatter,
    write_frontmatter,
)
from src.config.paths import get_vault_dir
from skills.ingest.scripts.mcp._shared import tool_annotations
from src.lib.ingest.note_index_refresh import refresh_notes_browse_index

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


VALID_DOMAINS = {"projects", "jobs", "companies", "people", "research", "reading"}
VALID_SOURCES = {"github", "linkedin", "website", "email", "local-file"}
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_STATUSES_BY_DOMAIN = {
    "jobs": {"saved", "applied", "interviewing", "offer", "rejected", "archived"},
    "projects": {"saved", "evaluating", "watching", "active", "archived"},
    "reading": {"queued", "reading", "finished", "archived"},
}
ALLOWED_VAULT_NOTE_ROOTS = (
    ("knowledge", "notes"),
    ("knowledge", "sources", "urls"),
    ("knowledge", "sources", "files"),
    ("prompts",),
    ("drafts",),
    ("archive",),
)


def _clean(value: str) -> str:
    return value.strip().lower()


def _invalid(value_name: str, value: str, allowed: set[str]) -> NoReturn:
    options = ", ".join(sorted(allowed))
    raise ValueError(f"{value_name} {value} is not valid; expected one of: {options}")


def _write_frontmatter_preserving_body(
    path: Path,
    metadata: dict[str, Any],
    body: str,
) -> None:
    write_frontmatter(path, metadata, body)
    if not body:
        return

    content = path.read_text(encoding="utf-8")
    # write_frontmatter adds a blank separator line; remove only that line so
    # parse_frontmatter(path)[1] remains identical before and after the update.
    closing = content.find("\n---\n\n", 4)
    if closing == -1:
        return
    path.write_text(
        f"{content[: closing + 5]}{content[closing + 6:]}",
        encoding="utf-8",
    )


def _metadata_without_injected_aliases(metadata: dict[str, Any]) -> dict[str, Any]:
    """Drop read aliases that parse_frontmatter synthesizes from system fields."""
    cleaned = dict(metadata)
    for alias, system_key in VAULT_SYSTEM_FIELD_MAP.items():
        if system_key in cleaned:
            cleaned.pop(alias, None)
    return cleaned


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _allowed_note_roots(vault_dir: Path) -> list[Path]:
    return [
        vault_dir.joinpath(*parts).expanduser().resolve(strict=False)
        for parts in ALLOWED_VAULT_NOTE_ROOTS
    ]


def _resolve_supported_note_path(path: Path) -> Path | None:
    resolved_path = path.expanduser().resolve()
    vault_dir = get_vault_dir().expanduser().resolve(strict=False)
    if any(_is_relative_to(resolved_path, root) for root in _allowed_note_roots(vault_dir)):
        return resolved_path
    return None


def normalize_note_classification_update(
    *,
    domain: str,
    source: str,
    status: str = "",
    classification_confidence: str = "high",
) -> dict[str, Any]:
    """Validate and normalize note classification metadata."""
    normalized_domain = _clean(domain)
    normalized_source = _clean(source)
    normalized_status = _clean(status)
    normalized_confidence = _clean(classification_confidence)

    if normalized_domain not in VALID_DOMAINS:
        _invalid("domain", normalized_domain, VALID_DOMAINS)
    if normalized_source not in VALID_SOURCES:
        _invalid("source", normalized_source, VALID_SOURCES)
    if normalized_confidence not in VALID_CONFIDENCE:
        _invalid(
            "classification confidence",
            normalized_confidence,
            VALID_CONFIDENCE,
        )

    valid_statuses = VALID_STATUSES_BY_DOMAIN.get(normalized_domain, set())
    if normalized_status and normalized_status not in valid_statuses:
        raise ValueError(
            f"status {normalized_status} is not valid for domain "
            f"{normalized_domain}"
        )

    payload: dict[str, Any] = {
        "x-augur-domain": normalized_domain,
        "x-augur-source": normalized_source,
        "x-augur-classification-confidence": normalized_confidence,
    }
    if normalized_status:
        payload["x-augur-status"] = normalized_status
    return payload


def update_note_classification_impl(
    note_path: str,
    domain: str,
    source: str,
    status: str = "",
    classification_confidence: str = "high",
) -> dict[str, Any]:
    """Update classification frontmatter on a markdown note."""
    path = Path(note_path)
    if not path.is_file():
        return {"success": False, "error": f"note not found: {note_path}"}
    if path.suffix.lower() != ".md":
        return {
            "success": False,
            "error": f"note must be a markdown file: {note_path}",
        }
    supported_path = _resolve_supported_note_path(path)
    if supported_path is None:
        return {
            "success": False,
            "error": f"note must be inside an Augur note root: {note_path}",
        }

    try:
        update = normalize_note_classification_update(
            domain=domain,
            source=source,
            status=status,
            classification_confidence=classification_confidence,
        )
    except ValueError as exc:
        return {"success": False, "error": str(exc)}

    metadata, body = parse_frontmatter(supported_path, include_sidecar_config=False)
    updated_metadata = _metadata_without_injected_aliases(metadata)
    updated_metadata["x-augur-domain"] = update["x-augur-domain"]
    updated_metadata["x-augur-source"] = update["x-augur-source"]
    updated_metadata["x-augur-classification-confidence"] = update[
        "x-augur-classification-confidence"
    ]
    if "x-augur-status" in update:
        updated_metadata["x-augur-status"] = update["x-augur-status"]
    else:
        updated_metadata.pop("x-augur-status", None)

    _write_frontmatter_preserving_body(supported_path, updated_metadata, body)
    refresh = refresh_notes_browse_index().to_dict()
    return {
        "success": True,
        "note_path": str(supported_path),
        "metadata": update,
        "refresh": refresh,
    }


def register_note_classification_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any = None,
) -> None:
    """Register note-classification-update MCP tool."""

    @mcp.tool(
        name="note-classification-update",
        annotations=tool_annotations(
            {
                "title": "Update Note Classification",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    def note_classification_update_tool(
        note_path: str,
        domain: str,
        source: str,
        status: str = "",
        classification_confidence: str = "high",
    ) -> dict[str, Any]:
        """Update x-augur classification metadata on a markdown note."""
        if metrics:
            metrics.track_tool("note_classification_update", skill="ingest")
        return update_note_classification_impl(
            note_path=note_path,
            domain=domain,
            source=source,
            status=status,
            classification_confidence=classification_confidence,
        )


__all__ = [
    "normalize_note_classification_update",
    "register_note_classification_tools",
    "update_note_classification_impl",
]
