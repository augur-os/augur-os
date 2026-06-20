"""Reflect-context MCP tool — assembles personal context from the vault.

Provides the knowledge substrate for /ask's reflective inner voice.
Searches the full vault via ripgrep text matching, groups hits by domain,
strips technical metadata, and returns content-only context
within a token budget.
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
import asyncio
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.mcp.augur_shared.logging import get_entity_logger
    from src.mcp.augur_shared.annotations import tool_annotations
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        logging = importlib.import_module("logging")
        return logging.getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations

from src.config.paths import (
    get_compiled_wiki_dir,
    get_memory_dir,
    get_project_root,
    get_rag_dir,
    get_runtime_dir,
    get_vault_dir,
)
from src.lib.index.staleness import ensure_fresh_index
from src.lib.index.unified_search import bm25_available, iterative_search

try:
    from skills.knowledge.scripts.mcp.ask_context_pack import (
        build_context_pack,
        candidate_for_search_hit,
        expanded_search_query,
        sort_candidates,
        source_basis_for,
    )
except ImportError:
    from .ask_context_pack import (
        build_context_pack,
        candidate_for_search_hit,
        expanded_search_query,
        sort_candidates,
        source_basis_for,
    )

logger = get_entity_logger("mcp.knowledge.reflect")

# Approximate tokens as chars / 4
_CHARS_PER_TOKEN = 4
_QUALITY_SOURCE_TOKEN_BUDGET = 120

# Patterns to strip from content before returning
_STRIP_PATTERNS = [
    re.compile(r"ADR-\d{3,4}"),                     # ADR references
    re.compile(r"(?:get_\w+_dir\(\)|~/\S+)"),       # Path function calls
    re.compile(r"/Users/\S+"),                       # Absolute paths
    re.compile(r"skills/\S+"),                       # Relative skill paths
    re.compile(r"plugins/\S+"),                      # Relative plugin paths
    re.compile(r"docs/\S+"),                         # Relative doc paths
    re.compile(r"src/\S+"),                          # Relative src paths
    re.compile(r"```[\s\S]*?```"),                   # Code blocks
    re.compile(r"---\n[\s\S]*?\n---\n?"),            # YAML frontmatter
]


def _estimate_tokens(text: str) -> int:
    """Estimate token count from character length."""
    return len(text) // _CHARS_PER_TOKEN


def _truncate_to_budget(text: str, token_budget: int) -> str:
    """Truncate text to fit within a token budget."""
    char_budget = token_budget * _CHARS_PER_TOKEN
    if len(text) <= char_budget:
        return text
    # Truncate at last sentence boundary within budget
    truncated = text[:char_budget]
    last_period = truncated.rfind(".")
    if last_period > char_budget // 2:
        return truncated[: last_period + 1]
    return truncated


def _strip_technical_metadata(text: str) -> str:
    """Remove file paths, ADR numbers, frontmatter, and code blocks."""
    result = text
    for pattern in _STRIP_PATTERNS:
        result = pattern.sub("", result)
    result = re.sub(r"(?m)^#{1,6}\s*", "", result)  # Strip markdown heading markers
    # Clean up leftover artifacts
    result = re.sub(r"\n{3,}", "\n\n", result)  # Collapse multiple blank lines
    result = re.sub(r"  +", " ", result)         # Collapse multiple spaces
    return result.strip()


def _is_low_signal_context(text: str) -> bool:
    """Return True for fragments too thin to help reflective answering."""
    stripped = text.strip()
    if not stripped:
        return True
    if "metadata-only seed page generated from scanned sources" in stripped.lower():
        return True

    flattened = " ".join(stripped.split())
    candidate = re.sub(r"^[\-\*\u2022]+\s*", "", flattened).strip()
    if not candidate:
        return True
    if not re.search(r"[A-Za-z0-9]", candidate):
        return True
    if len(candidate) < 24 and len(candidate.split()) < 5:
        return True
    return False


def _is_low_signal_reflect_visible_context(text: str) -> bool:
    """Return True for sanitized context-pack fragments too thin to expose."""
    stripped = text.strip()
    if not stripped:
        return True
    if "metadata-only seed page generated from scanned sources" in stripped.lower():
        return True

    flattened = " ".join(stripped.split())
    candidate = re.sub(r"^[\-\*\u2022]+\s*", "", flattened).strip()
    if not candidate:
        return True
    if not re.search(r"[A-Za-z0-9]", candidate):
        return True
    if len(candidate) < 8 and len(candidate.split()) < 2:
        return True
    return False


def _flatten_hit_groups(raw_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten iterative search result groups into plain hit dictionaries."""
    hits: list[dict[str, Any]] = []
    for group in raw_results:
        if isinstance(group, dict) and "hits" in group:
            for hit in group["hits"]:
                if isinstance(hit, dict):
                    hits.append(dict(hit))
        elif isinstance(group, dict) and "file" in group:
            hits.append(dict(group))
    return hits


def _split_memory_hits(
    hits: list[dict[str, Any]], *, memory_root: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split hits into (memory, non-memory) by get_memory_dir() containment."""
    memory_hits: list[dict[str, Any]] = []
    non_memory_hits: list[dict[str, Any]] = []
    resolved_root = memory_root.resolve()
    for hit in hits:
        try:
            Path(hit.get("file", "")).resolve().relative_to(resolved_root)
            memory_hits.append(hit)
        except (ValueError, OSError):
            non_memory_hits.append(hit)
    return memory_hits, non_memory_hits


def _read_file_content(path: Path, max_chars: int = 4000) -> str:
    """Read a file, strip metadata, return content-only."""
    try:
        raw = path.read_text(encoding="utf-8")[:max_chars]
        return _strip_technical_metadata(raw)
    except Exception:
        return ""


def _extract_hit_context(hit: dict[str, Any], *, prefer_full_page: bool = False) -> str:
    """Extract the best available text for a search hit."""
    raw_snippet = _strip_technical_metadata(str(hit.get("content", "") or ""))

    if prefer_full_page or _is_low_signal_context(raw_snippet):
        file_path = hit.get("file", "")
        if file_path:
            full_text = _read_file_content(Path(file_path))
            if full_text and not _is_low_signal_context(full_text):
                return full_text

    return raw_snippet


def _collect_context_from_hits(
    hits: list[dict[str, Any]],
    *,
    token_budget: int,
    prefer_full_page: bool = False,
) -> list[str]:
    """Build a de-duplicated context list from ordered search hits."""
    collected: list[str] = []
    seen_normalized: set[str] = set()
    tokens_used = 0

    for hit in hits:
        content = _extract_hit_context(hit, prefer_full_page=prefer_full_page)
        if _is_low_signal_context(content):
            continue

        normalized = " ".join(content.split()).lower()
        if normalized in seen_normalized:
            continue

        estimated = _estimate_tokens(content)
        if tokens_used >= token_budget:
            break

        collected.append(content)
        seen_normalized.add(normalized)
        tokens_used += estimated

    return collected


def _context_key(text: str) -> str:
    """Normalize context text for de-duplication."""
    return " ".join(text.split()).lower()


def _strip_reflect_scaffolding(text: str) -> str:
    """Remove Codex rollout/status scaffolding from reflect-visible text."""
    cleaned = _strip_technical_metadata(text)
    lines: list[str] = []
    scaffold_line = re.compile(
        r"^(?:[-*]\s*)?"
        r"(?:session_meta|turn_context|event_msg|response_item|rollout_path|thread_id|cwd|branch|git_branch)\b\s*[:=]",
        re.IGNORECASE,
    )
    timestamp_value = re.compile(
        r"\b(?:updated_at|updated|captured_at|modified)\s*[:=]\s*"
        r"['\"]?\d{4}-\d{2}-\d{2}(?:[T ][0-9:.+-]+(?:Z|[+-]\d{2}:?\d{2})?)?",
        re.IGNORECASE,
    )
    iso_timestamp = re.compile(
        r"\b\d{4}-\d{2}-\d{2}T[0-9:.+-]+(?:Z|[+-]\d{2}:?\d{2})?\b"
    )
    status_value = re.compile(
        r"\b(?:status|outcome)\s*[:=]\s*"
        r"(?:success|passed|done|failed|blocked|partial|ok)\b",
        re.IGNORECASE,
    )
    scaffold_token = re.compile(
        r"\b(?:session_meta|turn_context|event_msg|response_item|rollout_path|thread_id|cwd|branch|git_branch)\b\s*[:=]?",
        re.IGNORECASE,
    )

    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line or scaffold_line.match(line):
            continue
        line = timestamp_value.sub(" ", line)
        line = iso_timestamp.sub(" ", line)
        line = status_value.sub(" ", line)
        line = scaffold_token.sub(" ", line)
        line = re.sub(r"\S+\.jsonl\b", " ", line, flags=re.IGNORECASE)
        line = re.sub(r"\s{2,}", " ", line).strip(" -:;")
        if _is_low_signal_reflect_visible_context(line):
            continue
        lines.append(line)

    return "\n".join(lines).strip()


def _select_visible_candidate_contexts(
    candidates: list[Any],
    *,
    skip_texts: list[str] | None = None,
    limit: int = 3,
) -> list[tuple[Any, str]]:
    """Return context-pack candidates that should be visible in domain context."""
    seen = {_context_key(item) for item in (skip_texts or []) if item}
    selected: list[tuple[Any, str]] = []
    for candidate in candidates:
        content = _strip_reflect_scaffolding(str(getattr(candidate, "text", "") or ""))
        if _is_low_signal_reflect_visible_context(content):
            continue
        normalized = _context_key(content)
        if any(normalized == item or normalized in item or item in normalized for item in seen):
            continue
        selected.append((candidate, content))
        seen.add(normalized)
        if len(selected) >= limit:
            break
    return selected


def _append_context_with_budget(contexts: list[str], content: str, token_budget: int) -> str:
    """Append content to a context list, truncating so the list stays in budget."""
    if token_budget <= 0:
        return ""
    content = content.strip()
    if _is_low_signal_reflect_visible_context(content):
        return ""
    char_budget = token_budget * _CHARS_PER_TOKEN
    used_chars = len(" ".join(contexts))
    separator_chars = 1 if contexts else 0
    remaining_chars = char_budget - used_chars - separator_chars
    if remaining_chars <= 0:
        return ""
    visible = content
    if len(visible) > remaining_chars:
        visible = _truncate_to_budget(visible, max(1, remaining_chars // _CHARS_PER_TOKEN))
    if _is_low_signal_reflect_visible_context(visible):
        return ""
    contexts.append(visible)
    return visible


def _quality_source_for_visible_candidate(candidate: Any, visible_text: str) -> dict[str, object] | None:
    """Build bounded quality-source metadata for visible context-pack support."""
    text = _strip_reflect_scaffolding(visible_text)
    if _is_low_signal_reflect_visible_context(text):
        return None
    text = _truncate_to_budget(text, _QUALITY_SOURCE_TOKEN_BUDGET)
    if _is_low_signal_reflect_visible_context(text):
        return None
    source = candidate.quality_source()
    source["text"] = text
    return source


def _identity_entry_sort_key(path: Path) -> tuple[int, str]:
    name = path.name.lower()
    if "preference" in name:
        return (0, name)
    if "feedback" in name:
        return (1, name)
    return (2, name)


def assemble_reflection_context(
    query: str,
    conversation_summary: str | None = None,
    token_budget: int = 4000,
) -> dict[str, Any]:
    """Assemble personal context from the vault for reflective responses.

    Searches the full vault via ripgrep text matching, groups results by domain,
    and returns content-only context within the token budget.

    Args:
        query: The user's question
        conversation_summary: Prior conversation context (for multi-turn)
        token_budget: Maximum tokens for the assembled context

    Returns:
        Dict with identity, relevant_memories, domain_context, recent_focus
    """
    vault_dir = get_vault_dir()
    runtime_dir = get_runtime_dir()
    memory_dir = runtime_dir / "memory"
    wiki_dir = get_compiled_wiki_dir()

    # Budget allocation
    identity_budget = min(500, token_budget // 8)
    focus_budget = min(300, token_budget // 13)
    memory_budget = min(1500, token_budget * 3 // 8)
    domain_budget = token_budget - identity_budget - focus_budget - memory_budget

    # --- 1. Identity baseline (preferences + feedback from consolidated entries) ---
    identity_parts: list[str] = []
    entries_dir = memory_dir / "entries"
    if entries_dir.exists():
        for entry_file in sorted(entries_dir.iterdir(), key=_identity_entry_sort_key):
            if not entry_file.suffix == ".md":
                continue
            name = entry_file.stem
            if "preference" in name or "feedback" in name:
                content = _read_file_content(entry_file, max_chars=800)
                if content:
                    identity_parts.append(content)
                if _estimate_tokens("\n".join(identity_parts)) >= identity_budget:
                    break
    identity = _truncate_to_budget("\n\n".join(identity_parts), identity_budget)

    # --- 2. Recent focus (from digest-hot.md) ---
    recent_focus = ""
    digest_path = memory_dir / "digest-hot.md"
    if digest_path.exists():
        recent_focus = _read_file_content(digest_path, max_chars=focus_budget * _CHARS_PER_TOKEN)
        recent_focus = _truncate_to_budget(recent_focus, focus_budget)

    # --- 3. Text search across full vault via ripgrep ---
    search_query = query
    if conversation_summary:
        search_query = f"{query} {conversation_summary}"

    context_pack = build_context_pack(
        search_query,
        vault_dir=vault_dir,
        wiki_dir=wiki_dir,
        vault_memory_dir=get_memory_dir(),
        runtime_dir=runtime_dir,
        project_root=get_project_root(),
    )
    search_query = expanded_search_query(search_query, context_pack)

    extra_warnings: list[str] = []
    gate = ensure_fresh_index()
    if gate["warning"]:
        extra_warnings.append(gate["warning"])
    rag_dir = get_rag_dir()
    if not bm25_available([rag_dir]):
        extra_warnings.append("bm25-index-unavailable: ripgrep-only retrieval")

    vault_hits: list[dict[str, Any]] = []
    try:
        search_roots = [d for d in (wiki_dir, vault_dir) if d.exists()]
        if search_roots:
            raw_results = iterative_search(
                search_query, [], search_roots, [rag_dir], top_k=50
            )
            vault_hits = _flatten_hit_groups(raw_results)
    except Exception as e:
        logger.warning(f"Vault search failed: {e}")
        extra_warnings.append(f"vault-search-failed: {e}")

    # --- 4. Split hits into memory and non-memory buckets while preserving order ---
    memory_hits, non_memory_hits = _split_memory_hits(
        vault_hits, memory_root=get_memory_dir()
    )

    # --- 5. Assemble relevant_memories from memory domain ---
    relevant_memories = _collect_context_from_hits(
        memory_hits[:20],
        token_budget=memory_budget,
    )

    # --- 6. Assemble domain_context from non-memory domains in priority order ---
    broad_domain_context = _collect_context_from_hits(
        non_memory_hits[:50],
        token_budget=domain_budget,
        prefer_full_page=True,
    )

    live_candidates = [
        candidate
        for candidate in context_pack.candidates
        if candidate.text and candidate.family != "repo_evidence"
    ]
    pack_paths = {
        candidate.path.resolve()
        for candidate in context_pack.candidates
        if candidate.path is not None
    }
    for hit in non_memory_hits[:30]:
        candidate = candidate_for_search_hit(
            hit,
            vault_dir=vault_dir,
            wiki_dir=wiki_dir,
            rag_dir=rag_dir,
            query=search_query,
            intent=context_pack.intent,
        )
        if candidate is None or not candidate.text:
            continue
        if candidate.path is not None and candidate.path.resolve() in pack_paths:
            continue
        live_candidates.append(candidate)
    live_candidates = sort_candidates(live_candidates, context_pack.intent, search_query)
    repo_candidates = [
        candidate
        for candidate in context_pack.candidates
        if candidate.text and candidate.family == "repo_evidence"
    ]
    quality_sources: list[dict[str, object]] = []

    domain_context: list[str] = []
    for candidate, content in _select_visible_candidate_contexts(
        live_candidates,
        skip_texts=[identity, recent_focus, *relevant_memories],
    ):
        visible_text = _append_context_with_budget(domain_context, content, domain_budget)
        if not visible_text:
            continue
        quality_source = _quality_source_for_visible_candidate(candidate, visible_text)
        if quality_source is not None:
            quality_sources.append(quality_source)
    for content in broad_domain_context:
        normalized = _context_key(content)
        if any(
            normalized == _context_key(existing)
            or normalized in _context_key(existing)
            or _context_key(existing) in normalized
            for existing in domain_context
        ):
            continue
        _append_context_with_budget(domain_context, content, domain_budget)

    if repo_candidates:
        focus_parts: list[str] = []
        for candidate in repo_candidates:
            content = _strip_reflect_scaffolding(str(candidate.text or ""))
            visible_text = _append_context_with_budget(focus_parts, content, focus_budget)
            if not visible_text:
                continue
            quality_source = _quality_source_for_visible_candidate(candidate, visible_text)
            if quality_source is not None:
                quality_sources.append(quality_source)
        _append_context_with_budget(focus_parts, recent_focus, focus_budget)
        recent_focus = "\n\n".join(focus_parts)

    return {
        "identity": identity,
        "relevant_memories": relevant_memories,
        "domain_context": domain_context,
        "recent_focus": recent_focus,
        "source_basis": list(source_basis_for(live_candidates) or context_pack.source_basis),
        "quality_sources": quality_sources,
        "context_warnings": [*context_pack.warnings, *extra_warnings],
        "retrieval_intent": context_pack.intent,
    }


def _append_ask_history(query: str, result: dict[str, Any]) -> None:
    """Record successful /ask context assembly without storing full answer text."""
    trimmed = " ".join((query or "").split())
    if not trimmed:
        return
    history_path = get_runtime_dir() / "ask-history.jsonl"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "query_hash": hashlib.sha256(trimmed.encode("utf-8")).hexdigest()[:16],
        "query_preview": trimmed[:160],
        "result_keys": sorted(result.keys()),
    }
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def register_reflect_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register the reflect-context MCP tool."""

    @mcp.tool(
        name="reflect-context",
        annotations=tool_annotations(
            {
                "title": "Assemble Reflection Context",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def reflect_context_tool(
        query: str,
        q: str = "",
        conversation_summary: str | None = None,
        token_budget: int = 4000,
    ) -> str:
        """Assemble personal context from the vault for reflective /ask responses.

        Searches the full vault via ripgrep text matching, groups results by life domain,
        and returns content-only context (no file paths, no ADR numbers)
        within a token budget. Used by /ask to speak as the user's inner voice.

        Args:
            query: The user's question (dashboard alias: q)
            q: Dashboard alias for query
            conversation_summary: Summary of prior conversation turns (for multi-turn)
            token_budget: Maximum tokens for assembled context (default 4000)

        Returns:
            str: JSON with identity, relevant_memories, domain_context, recent_focus
        """
        query = query or q
        metrics.track_tool("reflect_context", skill="knowledge")

        # Eval-harness caller tagging (ADR-742): reflect-context IS the /ask
        # retrieval phase. Tag the caller so any allowlisted retrieval MCP tool
        # invoked within this phase records `source: "/ask"`. Best-effort — a
        # missing or broken eval skill must never affect /ask.
        _eval_caller_token = None
        _eval_capture = None
        try:
            import importlib.util as _il

            from src.config.paths import get_project_root

            _cap_path = (
                get_project_root()
                / "project-brain"
                / "capabilities"
                / "skills"
                / "evals"
                / "scripts"
                / "capture.py"
            )
            if _cap_path.is_file():
                _spec = _il.spec_from_file_location("_augur_evals_capture", _cap_path)
                if _spec is not None and _spec.loader is not None:
                    _eval_capture = _augur_sys.modules.get("_augur_evals_capture")
                    if _eval_capture is None:
                        _eval_capture = _il.module_from_spec(_spec)
                        _augur_sys.modules[_spec.name] = _eval_capture
                        _spec.loader.exec_module(_eval_capture)
                    _eval_caller_token = _eval_capture.set_caller("/ask")
        except Exception:  # noqa: BLE001 - capture tagging is best-effort
            _eval_caller_token = None
            _eval_capture = None

        try:
            result = await asyncio.to_thread(
                assemble_reflection_context,
                query=query,
                conversation_summary=conversation_summary,
                token_budget=token_budget,
            )
            await asyncio.to_thread(_append_ask_history, query, result)
        finally:
            if _eval_capture is not None and _eval_caller_token is not None:
                try:
                    _eval_capture.reset_caller(_eval_caller_token)
                except Exception:  # noqa: BLE001
                    pass

        return json.dumps(result, indent=2, default=str)
