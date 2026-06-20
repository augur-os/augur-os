"""ADR-753 article-enrichment MCP tools."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _ensure_project_paths(start: Path) -> Path:
    for candidate in (start.parent, *start.parents):
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "src" / "config" / "paths.py").is_file()
        ):
            for path in (candidate / "src" / "mcp", candidate, candidate / "project-brain"):
                text = str(path)
                if text not in sys.path:
                    sys.path.insert(0, text)
            return candidate
    raise RuntimeError(f"Unable to locate Augur project root from {start}")


_PROJECT_ROOT = _ensure_project_paths(Path(__file__).resolve())

from src.lib.frontmatter_utils import parse_frontmatter, write_vault_frontmatter  # noqa: E402
from skills.ingest.scripts.article_enrichment import (  # noqa: E402
    ENRICHMENT_SECTIONS,
    build_llm_dispatch_payload,
    compose_body,
    split_body,
    stamp_enrichment_frontmatter,
)
from skills.ingest.scripts.mcp._shared import tool_annotations  # noqa: E402

_WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
_CURRENT_ENRICHMENT_VERSION = 1


def _enrichment_version(frontmatter: dict[str, Any]) -> int:
    value = frontmatter.get("x-augur-enrichment-version", 0)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _note_type(frontmatter: dict[str, Any]) -> str:
    value = frontmatter.get("x-augur-note-type") or frontmatter.get("source_type")
    return value.strip() if isinstance(value, str) else ""


def _normalize_entity_slug(value: str) -> str:
    slug = value.strip().replace("\\", "/").strip("/")
    if slug.startswith("[[") and slug.endswith("]]"):
        slug = slug[2:-2].split("|", 1)[0].strip().strip("/")
    if slug.startswith("wiki/"):
        slug = slug[len("wiki/") :].strip("/")
    return slug


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        normalized = _normalize_entity_slug(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return out


def _read_existing_entity_slugs() -> list[str]:
    """Best-effort graph entity candidates; graph cache failures never block enrichment."""
    graph_scripts = _PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "graph" / "scripts"
    graph_text = str(graph_scripts)
    if graph_text not in sys.path:
        sys.path.insert(0, graph_text)
    try:
        import graph_cache  # type: ignore

        entities = graph_cache.load_entities()
    except Exception:
        return []
    slugs: list[str] = []
    for entity in entities:
        if isinstance(entity, dict) and isinstance(entity.get("id"), str):
            slugs.append(entity["id"])
    return _dedupe(slugs)


def _note_entity_candidates(frontmatter: dict[str, Any], body: str) -> list[str]:
    candidates: list[str] = []
    for key in ("tags", "entities", "topics", "keywords"):
        value = frontmatter.get(key)
        if isinstance(value, str):
            candidates.extend(part.strip() for part in value.split(","))
        elif isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, str))

    for match in _WIKILINK_RE.finditer(body):
        candidates.append(match.group(1))

    return _dedupe(candidates)


def _existing_entity_candidates(frontmatter: dict[str, Any], body: str) -> list[str]:
    return _dedupe([*_note_entity_candidates(frontmatter, body), *_read_existing_entity_slugs()])


def _validate_article_note(path: Path) -> tuple[dict[str, Any] | None, str, str | None]:
    frontmatter, body = parse_frontmatter(path)
    note_type = _note_type(frontmatter)
    if not note_type:
        return None, body, "missing x-augur-note-type for article enrichment"
    if note_type not in {"url", "file"}:
        return None, body, f"enrichment only applies to url/file notes; got {note_type}"
    return frontmatter, body, None


def _parse_cross_references(cross_references_json: str | list[Any]) -> tuple[list[str], str | None]:
    if isinstance(cross_references_json, str):
        if not cross_references_json.strip():
            return [], None
        try:
            parsed = json.loads(cross_references_json)
        except json.JSONDecodeError as exc:
            return [], f"cross_references_json must be a JSON list: {exc.msg}"
    else:
        parsed = cross_references_json

    if not isinstance(parsed, list):
        return [], "cross_references_json must be a JSON list"
    return _dedupe([item for item in parsed if isinstance(item, str)]), None


def _render_cross_references(slugs: list[str]) -> str:
    if not slugs:
        return "_No cross-references suggested._"
    return "\n".join(f"- [[wiki/{slug}]]" for slug in slugs)


def enrich_article_impl(note_path: str) -> dict[str, Any]:
    path = Path(note_path)
    if not path.is_file():
        return {"success": False, "error": f"note not found: {note_path}"}

    frontmatter, body, error = _validate_article_note(path)
    if error is not None or frontmatter is None:
        return {"success": False, "error": error or "invalid article note"}

    if (
        frontmatter.get("x-augur-enrichment-status") == "enriched"
        and _enrichment_version(frontmatter) >= _CURRENT_ENRICHMENT_VERSION
    ):
        return {"success": True, "skipped": True, "reason": "already enriched"}

    _, raw_content = split_body(body)
    payload = build_llm_dispatch_payload(
        note_title=str(frontmatter.get("title") or path.stem),
        note_url=frontmatter.get("url") or frontmatter.get("canonical_url"),
        raw_content=raw_content,
        existing_entities=_existing_entity_candidates(frontmatter, body),
    )
    payload["success"] = True
    payload["note_path"] = str(path)
    return payload


def submit_enrich_article_result_impl(
    *,
    note_path: str,
    executive_summary: str,
    key_insights: str,
    why_it_matters: str,
    verbatim_quotes: str,
    cross_references_json: str | list[Any] = "[]",
) -> dict[str, Any]:
    path = Path(note_path)
    if not path.is_file():
        return {"success": False, "error": f"note not found: {note_path}"}

    frontmatter, body, error = _validate_article_note(path)
    if error is not None or frontmatter is None:
        return {"success": False, "error": error or "invalid article note"}

    cross_references, parse_error = _parse_cross_references(cross_references_json)
    if parse_error is not None:
        return {"success": False, "error": parse_error}

    _, raw_content = split_body(body)
    enriched_sections = {
        "Executive summary": executive_summary.strip(),
        "Key insights": key_insights.strip(),
        "Why it matters": why_it_matters.strip(),
        "Verbatim quotes": verbatim_quotes.strip(),
        "Cross-references": _render_cross_references(cross_references),
    }
    missing_sections = [
        name
        for name, value in enriched_sections.items()
        if name != "Cross-references" and not value
    ]
    if missing_sections:
        return {
            "success": False,
            "error": f"missing enrichment section content: {', '.join(missing_sections)}",
        }

    new_body = compose_body(enriched_sections, raw_content)
    new_frontmatter = stamp_enrichment_frontmatter(
        frontmatter,
        version=_CURRENT_ENRICHMENT_VERSION,
    )
    write_vault_frontmatter(path, new_frontmatter, new_body)
    return {
        "success": True,
        "note_path": str(path),
        "enrichment_version": new_frontmatter["x-augur-enrichment-version"],
        "sections_written": list(ENRICHMENT_SECTIONS),
    }


def register_enrich_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any = None,
) -> None:
    @mcp.tool(
        name="enrich-article",
        annotations=tool_annotations(
            {
                "title": "Enrich Article",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    def enrich_article_tool(note_path: str) -> dict[str, Any]:
        if metrics:
            metrics.track_tool("enrich_article", skill="ingest")
        return enrich_article_impl(note_path)

    @mcp.tool(
        name="submit-enrich-article-result",
        annotations=tool_annotations(
            {
                "title": "Submit Enrich Article Result",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    def submit_enrich_article_result_tool(
        note_path: str,
        executive_summary: str,
        key_insights: str,
        why_it_matters: str,
        verbatim_quotes: str,
        cross_references_json: str | list[Any] = "[]",
    ) -> dict[str, Any]:
        if metrics:
            metrics.track_tool("submit_enrich_article_result", skill="ingest")
        return submit_enrich_article_result_impl(
            note_path=note_path,
            executive_summary=executive_summary,
            key_insights=key_insights,
            why_it_matters=why_it_matters,
            verbatim_quotes=verbatim_quotes,
            cross_references_json=cross_references_json,
        )


def register(mcp: "FastMCP") -> None:
    register_enrich_tools(mcp, lambda func: func, None)


__all__ = [
    "enrich_article_impl",
    "register",
    "register_enrich_tools",
    "submit_enrich_article_result_impl",
]
