"""Run user-configured wiki queries through the wiki synthesis engine."""

from __future__ import annotations

import json
import re
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.lib.frontmatter_utils import write_vault_frontmatter
from skills.wiki.scripts.wiki_pages import compute_source_fingerprint
from skills.wiki.scripts.wiki_query_registry import read_query
from skills.wiki.scripts.wiki_query_sources import (
    AdrIndexAdapter,
    AskRetentionAdapter,
    DailyLogsAdapter,
    GitRecentCommitsAdapter,
    InboxAdapter,
    LinkedFolderAdapter,
    MemoryMdAdapter,
    SourceResult,
)
from src.config.paths import get_runtime_dir, get_vault_dir


_SECTION_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)
_RUN_LOCKS: dict[str, threading.Lock] = {}
_RUN_LOCKS_GUARD = threading.Lock()
_ADAPTERS = {
    "memory_md": MemoryMdAdapter,
    "daily_logs": DailyLogsAdapter,
    "ask_retention": AskRetentionAdapter,
    "adr_index": AdrIndexAdapter,
    "git_recent_commits": GitRecentCommitsAdapter,
    "inbox": InboxAdapter,
    "linked_folder": LinkedFolderAdapter,
}


@dataclass
class RunResult:
    success: bool
    query_id: str
    status: str | None = None
    message: str | None = None
    error: str | None = None
    output_path: str | None = None
    prompt_path: str | None = None
    prompt_preview: str | None = None
    instructions: str | None = None
    next_steps: list[dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0
    sections_validated: list[str] = field(default_factory=list)
    truncated_sources: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_query(
    query_id: str,
    *,
    budget_tokens: int = 16_000,
    synthesis_markdown: str | None = None,
) -> RunResult:
    lock = _lock_for(query_id)
    if not lock.acquire(blocking=False):
        result = RunResult(
            success=False,
            query_id=query_id,
            status="already_running",
            error=f"query '{query_id}' already running",
        )
        _record_state(query_id, result)
        return result

    try:
        spec = read_query(query_id)
        if spec is None:
            result = RunResult(
                success=False,
                query_id=query_id,
                status="not_found",
                error=f"query not found: {query_id}",
            )
            _record_state(query_id, result)
            return result

        source_bundle = _resolve_sources(spec, budget_tokens=budget_tokens)
        prompt = _build_prompt(spec, source_bundle.text)
        if synthesis_markdown is None or not synthesis_markdown.strip():
            prompt_path = _write_agent_prompt(query_id, spec, prompt, source_bundle)
            result = RunResult(
                success=True,
                query_id=query_id,
                status="agent_action_required",
                message=f"Agent synthesis required for wiki query '{query_id}'.",
                prompt_path=str(prompt_path),
                prompt_preview=_prompt_preview(prompt),
                instructions=_agent_instructions(query_id),
                next_steps=_agent_next_steps(query_id, prompt_path),
                tokens_used=_approx_tokens(prompt),
                truncated_sources=source_bundle.truncated,
            )
            _record_state(query_id, result)
            return result

        body = synthesis_markdown.strip()
        try:
            sections = _validate_sections(body, spec.get("required_sections", []))
        except Exception as exc:
            result = RunResult(
                success=False,
                query_id=query_id,
                status="validation_failed",
                error=str(exc),
                tokens_used=_approx_tokens(prompt) + _approx_tokens(body),
                truncated_sources=source_bundle.truncated,
            )
            _record_state(query_id, result)
            return result

        output_path = _output_path(spec)
        metadata = {
            "title": spec.get("title") or query_id,
            "page_type": "query",
            "query_id": query_id,
            "description": spec.get("description", ""),
            "sources": source_bundle.citations,
            "source_fingerprint": compute_source_fingerprint(source_bundle.citations),
            "updated": _now_iso(),
        }
        write_vault_frontmatter(output_path, metadata, body)

        result = RunResult(
            success=True,
            query_id=query_id,
            status="complete",
            message=f"Query {query_id} refreshed.",
            output_path=str(output_path),
            tokens_used=_approx_tokens(prompt) + _approx_tokens(body),
            sections_validated=sections,
            truncated_sources=source_bundle.truncated,
        )
        _record_state(query_id, result)
        return result
    finally:
        lock.release()


def _resolve_sources(spec: dict[str, Any], *, budget_tokens: int) -> SourceResult:
    sources = spec.get("sources", [])
    per_source_budget = max(1, budget_tokens // max(len(sources), 1))
    parts: list[str] = []
    citations: list[str] = []
    truncated = False

    for index, source_spec in enumerate(sources, start=1):
        kind = source_spec.get("kind")
        adapter_type = _ADAPTERS.get(kind)
        if adapter_type is None:
            continue
        result = adapter_type().resolve(source_spec, budget_tokens=per_source_budget)
        truncated = truncated or result.truncated
        citations.extend(result.citations)
        text = result.text.strip()
        if not text:
            parts.append(f"### Source {index}: {kind}\nINSUFFICIENT_DATA")
            continue
        parts.append(f"### Source {index}: {kind}\n{text}")

    if not parts:
        return SourceResult(text="INSUFFICIENT_DATA", citations=[], truncated=truncated)
    return SourceResult(text="\n\n---\n\n".join(parts), citations=citations, truncated=truncated)


def _build_prompt(spec: dict[str, Any], sources_text: str) -> str:
    template = str(spec.get("prompt_template") or "")
    if "{{sources}}" in template:
        return template.replace("{{sources}}", sources_text)
    return f"{template}\n\nSources:\n{sources_text}"


def _validate_sections(body: str, required_sections: list[str]) -> list[str]:
    found = {match.group("title").strip() for match in _SECTION_RE.finditer(body)}
    missing = [section for section in required_sections if section not in found]
    if missing:
        raise ValueError(f"missing required H2 sections: {', '.join(missing)}")
    return list(required_sections)


def _output_path(spec: dict[str, Any]) -> Path:
    output = Path(str(spec["output"]))
    parts = output.parts
    if len(parts) >= 2 and parts[0] == "vault":
        return get_vault_dir().joinpath(*parts[1:])
    return get_vault_dir() / output


def _state_path() -> Path:
    return get_vault_dir() / "wiki" / ".queries-state.json"


def _record_state(query_id: str, result: RunResult) -> None:
    path = _state_path()
    try:
        state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except json.JSONDecodeError:
        state = {}
    state[query_id] = {
        "last_run": _now_iso(),
        "success": result.success,
        "status": result.status,
        "last_error": result.error,
        "output_path": result.output_path,
        "prompt_path": result.prompt_path,
        "tokens_used": result.tokens_used,
        "sections_validated": result.sections_validated,
        "truncated_sources": result.truncated_sources,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _lock_for(query_id: str) -> threading.Lock:
    with _RUN_LOCKS_GUARD:
        return _RUN_LOCKS.setdefault(query_id, threading.Lock())


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _write_agent_prompt(
    query_id: str,
    spec: dict[str, Any],
    prompt: str,
    source_bundle: SourceResult,
) -> Path:
    run_dir = get_runtime_dir() / "wiki" / "query-runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    safe_query_id = re.sub(r"[^a-zA-Z0-9_.-]+", "-", query_id).strip("-") or "query"
    path = run_dir / f"{_now_iso().replace(':', '').replace('+', 'Z')}-{safe_query_id}.md"
    required_sections = spec.get("required_sections", [])
    section_list = "\n".join(f"- {section}" for section in required_sections) or "- (none)"
    citation_list = "\n".join(f"- {citation}" for citation in source_bundle.citations) or "- (none)"
    content = (
        f"# Wiki Query Agent Handoff: {spec.get('title') or query_id}\n\n"
        f"Query id: `{query_id}`\n\n"
        "## Instructions\n\n"
        "Run the prompt below with the current AI client. Return Markdown only. "
        "Then call `wiki-queries-run` again with the same `id` and the generated Markdown in "
        "`synthesis_markdown`.\n\n"
        "## Required H2 Sections\n\n"
        f"{section_list}\n\n"
        "## Source Citations\n\n"
        f"{citation_list}\n\n"
        "## Prompt\n\n"
        f"{prompt}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


def _agent_instructions(query_id: str) -> str:
    return (
        "Read the prompt_path file, synthesize the requested Markdown in the current AI client, "
        f"then call wiki-queries-run with id='{query_id}' and synthesis_markdown set to the Markdown output."
    )


def _agent_next_steps(query_id: str, prompt_path: Path) -> list[dict[str, Any]]:
    return [
        {
            "id": "read-query-prompt",
            "description": "Read the persisted prompt prepared by the MCP tool.",
            "path": str(prompt_path),
        },
        {
            "id": "synthesize-markdown",
            "description": "Use the current AI agent session to produce Markdown with all required H2 sections.",
        },
        {
            "id": "submit-synthesis",
            "description": "Submit the synthesized Markdown back through the same MCP tool.",
            "tool": "wiki-queries-run",
            "arguments": {"id": query_id, "synthesis_markdown": "<generated markdown>"},
        },
    ]


def _prompt_preview(prompt: str) -> str:
    collapsed = " ".join(prompt.split())
    return collapsed[:237] + "..." if len(collapsed) > 240 else collapsed
