"""Unified RAG search across all indexed content.

Cross-bundle search library extracted from project-brain/capabilities/skills/rag/scripts/mcp/rag_tools.py
in the Track 3a follow-up (2026-04-30). The rag bundle's MCP wrapper consumes
this module rather than defining the function locally — same pattern Track 1
used for the rest of src/lib/index/.

Public surface used by the rag MCP wrapper and the knowledge CLI:
    unified_rag_search(args) -> str (JSON)
        Top-level entry point: takes {"query", "project"} and returns a
        JSON-encoded {"target", "results"} payload.

    iterative_search(query, source_dirs, priority_dirs, rag_dirs) -> list[dict]
        Lower-level scope-resolved search used by the MCP search-skill-knowledge
        tool, which wants to render its own JSON shape.

    resolve_scope_paths(skill) -> tuple[...]
        Resolves a skill name (or "all"/None) to (source_dirs, priority_dirs,
        rag_dirs, label). Public so MCP wrappers can compose it with
        iterative_search and additional metadata.

The internal ripgrep helpers, BM25 cache, and scope plumbing remain module-private
(prefixed with _).
"""

from __future__ import annotations

import fnmatch
import json
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.config.paths import (
    get_documents_dir,
    get_managed_skill_source_dirs,
    get_memory_dir,
    get_project_root,
    get_rag_dir,
    get_skill_data_dir,
    get_skill_documents_dir,
    get_skill_rag_dir,
    get_skill_root,
    get_skills_dir,
    get_vault_dir,
)
from src.logging import get_entity_logger

logger = get_entity_logger("lib.index.unified_search")

_QUERY_STOPWORDS: set[str] = {
    "a",
    "an",
    "am",
    "and",
    "are",
    "for",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
}

_DOCUMENT_QUERY_TERMS: set[str] = {
    "deck",
    "doc",
    "docs",
    "docx",
    "document",
    "file",
    "pdf",
    "pitch",
    "ppt",
    "pptx",
    "presentation",
    "slide",
    "slides",
}


def parse_ripgrep_hit(hit: str) -> dict:
    parts = hit.split(":", 2)
    if len(parts) >= 3:
        parsed = {"file": parts[0], "line": parts[1], "content": parts[2]}
        if "/index/chunks/" in parts[0]:
            parsed["parent_document"] = "Source file referenced in chunk frontmatter"
        return parsed
    return {"raw": hit}


def _to_rg_pattern(query: str) -> str:
    raw_words = re.findall(r"[A-Za-z0-9]+", query.strip())
    words = [word for word in raw_words if word.lower() not in _QUERY_STOPWORDS] or raw_words
    if len(words) <= 1:
        return re.escape(words[0]) if words else query
    return "|".join(re.escape(word) for word in words)


def _query_terms(query: str) -> list[str]:
    raw_words = re.findall(r"[A-Za-z0-9]+", query.strip().lower())
    return [word for word in raw_words if word not in _QUERY_STOPWORDS] or raw_words


def _is_document_query(query: str) -> bool:
    return bool(set(_query_terms(query)) & _DOCUMENT_QUERY_TERMS)


def _search_dirs_for_query(
    query: str,
    search_dirs: list[Path],
    rag_dirs: list[Path],
) -> list[Path]:
    if not _is_document_query(query):
        return search_dirs

    prioritized: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        try:
            key = path.resolve()
        except OSError:
            key = path.absolute()
        if key in seen:
            return
        prioritized.append(path)
        seen.add(key)

    for search_dir in search_dirs:
        matching_rag_dir = next(
            (rag_dir for rag_dir in rag_dirs if _same_directory(search_dir, rag_dir)),
            None,
        )
        if matching_rag_dir is not None:
            documents_dir = matching_rag_dir / "documents"
            if documents_dir.is_dir():
                add(documents_dir)
        add(search_dir)
    return prioritized


def _score_hits(hits: list[dict], query_words: list[str]) -> list[dict]:
    query_words = [word for word in query_words if word.lower() not in _QUERY_STOPWORDS] or query_words
    if len(query_words) <= 1:
        return hits

    lower_words = [word.lower() for word in query_words]

    def _score(hit: dict) -> int:
        text = (hit.get("content", "") + " " + hit.get("file", "")).lower()
        return sum(1 for word in lower_words if word in text)

    return sorted(hits, key=_score, reverse=True)


def _dedup_by_file(hits: list[dict]) -> list[dict]:
    seen_files: set[str] = set()
    deduped: list[dict] = []
    for hit in hits:
        file_path = hit.get("file", "")
        if file_path and file_path not in seen_files:
            seen_files.add(file_path)
            deduped.append(hit)
    return deduped


_EXCLUDE_GLOBS: list[str] = [
    "-g",
    "!*.py",
    "-g",
    "!*.ts",
    "-g",
    "!*.tsx",
    "-g",
    "!*.js",
    "-g",
    "!*.jsx",
    "-g",
    "!*.sh",
    "-g",
    "!*.css",
    "-g",
    "!tests/**",
    "-g",
    "!scripts/**",
    "-g",
    "!.github/**",
    "-g",
    "!node_modules/**",
    "-g",
    "!.next/**",
    "-g",
    "!src/**",
]

_ACTIVE_SEARCH_EXCLUDE_GLOBS: list[str] = [
    *_EXCLUDE_GLOBS,
]

_INACTIVE_VAULT_SCOPE_GLOBS: list[str] = [
    "-g",
    "!drafts/**",
    "-g",
    "!archive/**",
    "-g",
    "!_drafts/**",
]

_INACTIVE_VAULT_RAG_GLOBS: list[str] = [
    "-g",
    "!vault/drafts/**",
    "-g",
    "!vault/archive/**",
    "-g",
    "!vault/_drafts/**",
]

_RAG_INTERNAL_METADATA_GLOBS: list[str] = [
    "-g",
    "!_meta/**",
]


def _same_directory(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left.absolute() == right.absolute()


def _active_search_globs_for_directory(
    directory: Path,
    vault_dir: Path | None = None,
    rag_dirs: list[Path] | None = None,
) -> list[str]:
    globs = list(_ACTIVE_SEARCH_EXCLUDE_GLOBS)
    configured_vault_dir = vault_dir or get_vault_dir()
    if _same_directory(directory, configured_vault_dir):
        globs.extend(_INACTIVE_VAULT_SCOPE_GLOBS)
    if any(_same_directory(directory, rag_dir) for rag_dir in rag_dirs or []):
        globs.extend(_INACTIVE_VAULT_RAG_GLOBS)
        globs.extend(_RAG_INTERNAL_METADATA_GLOBS)
    return globs


def _is_root_inactive_vault_hit(hit: dict, vault_dir: Path) -> bool:
    file_path = hit.get("file")
    if not file_path:
        return False
    try:
        rel = Path(file_path).resolve().relative_to(vault_dir.resolve())
    except (OSError, ValueError):
        return False
    return bool(rel.parts) and rel.parts[0] in {"drafts", "archive", "_drafts"}


def _is_inactive_vault_rag_hit(hit: dict, rag_dirs: list[Path]) -> bool:
    file_path = hit.get("file")
    if not file_path:
        return False
    hit_path = Path(file_path)
    for rag_dir in rag_dirs:
        try:
            rel = hit_path.resolve().relative_to(rag_dir.resolve())
        except (OSError, ValueError):
            continue
        return len(rel.parts) >= 2 and rel.parts[0] == "vault" and rel.parts[1] in {"drafts", "archive", "_drafts"}
    return False


def _is_rag_internal_metadata_hit(hit: dict, rag_dirs: list[Path]) -> bool:
    file_path = hit.get("file")
    if not file_path:
        return False
    hit_path = Path(file_path)
    for rag_dir in rag_dirs:
        try:
            rel = hit_path.resolve().relative_to(rag_dir.resolve())
        except (OSError, ValueError):
            continue
        return bool(rel.parts) and rel.parts[0] == "_meta"
    return False


def _iter_skill_roots() -> list[Path]:
    roots: list[Path] = []
    seen: set[Path] = set()
    for skills_dir in get_managed_skill_source_dirs(get_project_root()):
        if not skills_dir.is_dir():
            continue
        for skill_dir in sorted(path for path in skills_dir.iterdir() if path.is_dir()):
            resolved = skill_dir.resolve()
            if resolved in seen:
                continue
            roots.append(skill_dir)
            seen.add(resolved)
    return roots


def resolve_scope_paths(skill: str | None) -> tuple[list[Path], list[Path], list[Path], str]:
    """Resolve a skill scope to (source_dirs, priority_dirs, rag_dirs, label).

    `skill` may be None or "all" (project-wide), a known skill name, or an
    absolute/relative path. Mirrors the pre-extraction behaviour exactly.
    """
    project_root = get_project_root()
    skills_roots = [path for path in get_managed_skill_source_dirs(project_root) if path.is_dir()]
    skills_root = skills_roots[0] if skills_roots else get_skills_dir()

    if not skill or skill == "all":
        source_dirs = [project_root]
        priority_dirs = [get_vault_dir(), get_documents_dir(), get_memory_dir()]
        rag_dirs = [get_rag_dir()]
        return source_dirs, priority_dirs, rag_dirs, "all"

    candidate = Path(skill)
    if not candidate.is_absolute():
        candidate = next(
            (skills_dir / skill for skills_dir in skills_roots if (skills_dir / skill).exists()),
            skills_root / skill,
        )

    if candidate.exists():
        target = candidate.resolve()
        resolved_skill_roots = {path.resolve() for path in skills_roots}
        if target in resolved_skill_roots:
            return [project_root], [get_vault_dir(), get_documents_dir(), get_memory_dir()], [get_rag_dir()], "all"
        rel = None
        for managed_root in resolved_skill_roots:
            try:
                rel = target.relative_to(managed_root)
                break
            except ValueError:
                continue
        if rel is None:
            return [target], [], [get_rag_dir()], target.as_posix()
        if len(rel.parts) >= 1:
            skill_name = rel.parts[0]
            priority_dirs = [get_skill_data_dir(skill_name), get_skill_documents_dir(skill_name)]
            return (
                [target],
                [path for path in priority_dirs if path.exists()],
                [get_skill_rag_dir(skill_name)],
                skill_name,
            )

    skill_root = get_skill_root(skill)
    return (
        [skill_root],
        [path for path in [get_skill_data_dir(skill), get_skill_documents_dir(skill)] if path.exists()],
        [get_skill_rag_dir(skill)],
        skill,
    )


@lru_cache(maxsize=1)
def _rg_binary() -> str | None:
    """Resolve the ripgrep executable, or None when it is not installed."""
    return shutil.which("rg")


def _exclusion_globs(globs: list[str]) -> list[str]:
    """Extract the `!pattern` exclusion patterns from a ripgrep `-g` arg list."""
    patterns: list[str] = []
    i = 0
    while i < len(globs):
        if globs[i] == "-g" and i + 1 < len(globs):
            value = globs[i + 1]
            if value.startswith("!"):
                patterns.append(value[1:])
            i += 2
        else:
            i += 1
    return patterns


def _is_glob_excluded(rel_posix: str, patterns: list[str]) -> bool:
    parts = rel_posix.split("/")
    name = parts[-1]
    for pat in patterns:
        if "/" not in pat:
            # Unanchored extension/name glob (e.g. "*.py") matches at any depth.
            if fnmatch.fnmatch(name, pat):
                return True
        else:
            # A glob containing "/" is ANCHORED to the search root (gitignore /
            # ripgrep semantics): `drafts/**` excludes only top-level `drafts/`,
            # NOT a nested `notes/project/drafts/`. Match by anchored prefix only.
            # (Previously a single-component dir glob also matched the dir name at
            # ANY depth, which over-excluded nested active paths like
            # vault/notes/project/drafts/active.md — diverging from ripgrep, so
            # the rg-less fallback returned a different, wrong result set.)
            base = pat[:-3] if pat.endswith("/**") else pat
            base_parts = base.split("/")
            if parts[: len(base_parts)] == base_parts:
                return True
    return False


def _looks_binary(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return b"\x00" in handle.read(8192)
    except OSError:
        return True


def _collect_python_hits(pattern: str, globs: list[str], directories: list[Path], max_hits: int = 100) -> list[dict]:
    """Pure-Python full-text fallback used only when the `rg` binary is missing
    (e.g. Windows without ripgrep). Mirrors ripgrep's case-insensitive,
    path-sorted, exclusion-aware behaviour closely enough to keep search working;
    it never runs when ripgrep is installed, so it cannot change those results."""
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error:
        regex = re.compile(re.escape(pattern), re.IGNORECASE)
    exclusions = _exclusion_globs(globs)
    hits: list[dict] = []
    for directory in directories:
        if not directory.exists():
            continue
        for file_path in sorted(p for p in directory.rglob("*") if p.is_file()):
            rel_posix = file_path.relative_to(directory).as_posix()
            if _is_glob_excluded(rel_posix, exclusions):
                continue
            if _looks_binary(file_path):
                continue
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    hits.append({"file": str(file_path.resolve()), "line": str(lineno), "content": line})
                    if len(hits) >= max_hits:
                        return hits
    return hits


def _collect_rg_hits(pattern: str, globs: list[str], directories: list[Path], max_hits: int = 2000) -> list[dict]:
    if _rg_binary() is None:
        return _collect_python_hits(pattern, globs, directories, max_hits=max_hits)
    rg = _rg_binary()
    hits: list[dict] = []
    for directory in directories:
        if not directory.exists():
            continue
        try:
            # `--sort path` forces ripgrep to walk single-threaded in a stable
            # path order. Without it, ripgrep's parallel directory walk returns
            # matches in a non-deterministic order, and the downstream
            # `max_hits` cutoff then keeps a different file set on every run —
            # which makes retrieval (and any eval replay over it, ADR-742)
            # non-reproducible. Deterministic ordering is strictly correct here.
            cmd = [rg, "-n", "-i", "--sort", "path", pattern, *globs, "."]
            output = subprocess.check_output(cmd, cwd=directory, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            continue
        except FileNotFoundError:
            # ripgrep vanished between resolution and call; degrade gracefully.
            return _collect_python_hits(pattern, globs, directories, max_hits=max_hits)
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        for line in output.strip().split("\n"):
            if not line:
                continue
            hit = parse_ripgrep_hit(line)
            file_path = hit.get("file")
            if isinstance(file_path, str) and not file_path.startswith("/") and not Path(file_path).is_absolute():
                hit["file"] = str((directory / file_path).resolve())
            hits.append(hit)
            if len(hits) >= max_hits:
                return hits
    return hits


def _collect_active_search_hits(
    pattern: str,
    directories: list[Path],
    max_hits: int = 2000,
    vault_dir: Path | None = None,
    rag_dirs: list[Path] | None = None,
    extra_globs: list[str] | None = None,
) -> list[dict]:
    hits: list[dict] = []
    for directory in directories:
        remaining = max_hits - len(hits)
        if remaining <= 0:
            break
        globs = [
            *(extra_globs or []),
            *_active_search_globs_for_directory(directory, vault_dir, rag_dirs),
        ]
        collected_hits = _collect_rg_hits(pattern, globs, [directory], max_hits=remaining)
        if rag_dirs:
            collected_hits = [hit for hit in collected_hits if not _is_rag_internal_metadata_hit(hit, rag_dirs)]
        configured_vault_dir = vault_dir or get_vault_dir()
        if _same_directory(directory, configured_vault_dir):
            collected_hits = [
                hit for hit in collected_hits if not _is_root_inactive_vault_hit(hit, configured_vault_dir)
            ]
        hits.extend(collected_hits)
    return hits


def _raw_iterative_search(
    query: str,
    source_dirs: list[Path],
    priority_dirs: list[Path],
    rag_dirs: list[Path],
    include_globs: list[str] | None = None,
) -> list[dict]:
    results = []
    rg_pattern = _to_rg_pattern(query)
    query_words = query.strip().split()

    priority_hits = _collect_active_search_hits(
        rg_pattern,
        priority_dirs,
        extra_globs=include_globs,
    )
    if priority_hits:
        priority_hits = _dedup_by_file(_score_hits(priority_hits, query_words))
        results.append({"type": "user_data", "hits": priority_hits[:50]})

    symbol_hits = _collect_active_search_hits(
        rg_pattern,
        rag_dirs,
        max_hits=50,
        rag_dirs=rag_dirs,
        extra_globs=["-g", "symbols.yaml"],
    )
    if symbol_hits:
        results.append({"type": "symbol", "hits": symbol_hits[:50]})

    index_hits = _collect_active_search_hits(
        rg_pattern,
        rag_dirs,
        max_hits=50,
        rag_dirs=rag_dirs,
        extra_globs=["-g", "*_index.md", "-g", "index.md"],
    )
    if index_hits:
        results.append({"type": "index", "hits": index_hits[:50]})

    if not results:
        fulltext_hits = _collect_active_search_hits(
            rg_pattern,
            [*priority_dirs, *source_dirs, *rag_dirs],
            rag_dirs=rag_dirs,
            extra_globs=["-g", "!symbols.yaml", "-g", "!*_index.md"],
        )
        if fulltext_hits:
            fulltext_hits = [hit for hit in fulltext_hits if not _is_inactive_vault_rag_hit(hit, rag_dirs)]
            fulltext_hits = _dedup_by_file(_score_hits(fulltext_hits, query_words))
            results.append({"type": "fulltext", "hits": fulltext_hits[:50]})

    return results


_bm25_cache: "dict[str, tuple[float, Any]]" = {}  # path → (mtime, BM25Index)


def _load_bm25_cached(rag_dirs: list[Path]) -> "Any":
    """Load BM25 index with mtime-based caching to avoid cold-load per query."""
    try:
        from src.lib.index.bm25_index import BM25Index
    except ImportError:
        return None

    for rag_dir in rag_dirs:
        meta_dir = rag_dir / "_meta"
        index_path = meta_dir / "bm25_index.json"
        if not index_path.exists():
            continue
        mtime = index_path.stat().st_mtime
        cache_key = str(index_path)
        cached = _bm25_cache.get(cache_key)
        if cached and cached[0] == mtime:
            return cached[1]
        candidate = BM25Index.load(meta_dir)
        if candidate.size() > 0:
            _bm25_cache[cache_key] = (mtime, candidate)
            return candidate
    return None


def bm25_available(rag_dirs: list[Path]) -> bool:
    """True when a non-empty BM25 index is loadable for these rag dirs."""
    return _load_bm25_cached(rag_dirs) is not None


def iterative_search(
    query: str,
    source_dirs: list[Path],
    priority_dirs: list[Path],
    rag_dirs: list[Path],
    top_k: int = 10,
    include_globs: list[str] | None = None,
    budget: str | None = None,
    *,
    include_stale_documents: bool = False,
) -> list[dict]:
    from src.lib.index.search_config import load_search_config
    from src.lib.index.sources import BM25Source, GraphSource, RipgrepSource

    cfg = load_search_config()
    per_source_limit = int(cfg["rrf"].get("per_source_limit", 50))
    bm25_index = _load_bm25_cached(rag_dirs)
    search_dirs = _search_dirs_for_query(query, [*priority_dirs, *source_dirs, *rag_dirs], rag_dirs)
    sources = [
        RipgrepSource(
            search_dirs,
            rag_dirs=rag_dirs,
            include_globs=include_globs,
            include_stale_documents=include_stale_documents,
        ),
        BM25Source(bm25_index, include_stale_documents=include_stale_documents),
    ]
    if any(path.exists() for path in rag_dirs):
        sources.append(GraphSource())

    ranked_lists = {}
    for source in sources:
        try:
            ranked_lists[source.name] = source.search(query, limit=per_source_limit)
        except Exception as exc:  # noqa: BLE001 - degraded search beats no search
            logger.warning("search source %s failed: %s", source.name, exc)

    fused = fuse_results(ranked_lists, budget=budget, top_k=top_k)
    return [{"type": "hybrid", "hits": fused}] if fused else []


def fuse_results(
    ranked_lists: dict[str, list[Any]],
    *,
    budget: str | None = None,
    top_k: int | None = None,
) -> list[dict]:
    """Fuse per-source ranked lists via RRF and attach budget/provenance fields."""
    from src.lib.index.rrf import fuse
    from src.lib.index.search_config import (
        budget_top_k,
        load_search_config,
        resolve_budget_name,
    )

    cfg = load_search_config()
    budget_name = resolve_budget_name(cfg, budget)
    resolved_top_k = budget_top_k(cfg, budget_name) if budget is not None or top_k is None else top_k
    fused = fuse(
        ranked_lists,
        k=int(cfg["rrf"].get("k", 60)),
        top_k=resolved_top_k,
    )

    results: list[dict] = []
    for row in fused:
        payload = dict(row.get("payload") or {})
        file_path = str(payload.get("file") or payload.get("path") or row["doc_id"])
        content = str(payload.get("content") or payload.get("snippet") or row.get("snippet") or "")
        result = {
            **payload,
            "doc_id": row["doc_id"],
            "file": file_path,
            "content": content,
            "score": row["score"],
            "budget": budget_name,
            "provenance": row["provenance"],
        }
        results.append(result)
    return results


def unified_rag_search(args: dict) -> str:
    """Top-level cross-bundle search entry.

    Accepts {"query": str, "project": str | None, ...} and returns a
    JSON-encoded {"target": label, "results": [...]} payload. Extra args
    (e.g. max_results) are accepted for forward compatibility.
    """
    query = args.get("query", "")
    project = args.get("project")
    budget = args.get("budget")
    top_k = int(args.get("max_results") or args.get("top_k") or 10)
    include_stale_documents = _truthy(args.get("include_stale_documents"))
    try:
        source_dirs, priority_dirs, rag_dirs, label = resolve_scope_paths(project)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    from src.lib.index.staleness import ensure_fresh_index

    gate = ensure_fresh_index()

    results = iterative_search(
        query,
        source_dirs,
        priority_dirs,
        rag_dirs,
        top_k=top_k,
        budget=budget,
        include_stale_documents=include_stale_documents,
    )
    payload: dict = {"target": label, "results": results}
    if gate["warning"]:
        payload["staleness"] = gate["warning"]
    return json.dumps(payload)


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
