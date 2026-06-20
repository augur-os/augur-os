from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config.paths import get_rag_dir, get_vault_dir
from src.lib.index.unified_search import iterative_search as rag_iterative_search


def _normalized_path(value: str) -> str:
    return value.replace("\\", "/").lower()


def _matches_expected_file(file_path: str, expected_files: list[str]) -> bool:
    normalized = _normalized_path(file_path)
    for expected in expected_files:
        expected_normalized = _normalized_path(expected)
        expected_name = expected_normalized.rsplit("/", 1)[-1]
        if (
            normalized == expected_normalized
            or normalized.endswith(expected_normalized)
            or normalized.endswith(f"/{expected_name}")
        ):
            return True
    return False


def _flatten_search_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for group in groups:
        if isinstance(group, dict) and "hits" in group:
            group_type = str(group.get("type", "rag"))
            for hit in group["hits"]:
                if not isinstance(hit, dict):
                    continue
                hit_dict = dict(hit)
                hit_dict.setdefault("scope", "rag")
                hit_dict.setdefault("result_type", group_type)
                hits.append(hit_dict)
        elif isinstance(group, dict) and "file" in group:
            hit_dict = dict(group)
            hit_dict.setdefault("scope", "rag")
            hits.append(hit_dict)
    return hits


def _demo_rag_priority_dirs(expected_files: list[str]) -> list[Path]:
    dirs: list[Path] = []
    seen: set[str] = set()
    for value in expected_files:
        path = Path(value)
        candidate = path.parent if path.suffix else path
        key = _normalized_path(str(candidate))
        if key in seen or not candidate.exists():
            continue
        dirs.append(candidate)
        seen.add(key)
    vault_dir = get_vault_dir()
    vault_key = _normalized_path(str(vault_dir))
    if vault_key not in seen:
        dirs.append(vault_dir)
    return dirs


def _dedupe_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for hit in hits:
        key = (
            str(hit.get("file", "")),
            str(hit.get("line", "")),
            str(hit.get("content", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hit)
    return deduped


def _search_expected_file_hits(
    query: str,
    expected_files: list[str],
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for expected_file in expected_files:
        file_hits = _flatten_search_groups(
            rag_iterative_search(
                query,
                [],
                _demo_rag_priority_dirs([expected_file]),
                [get_rag_dir()],
                top_k=top_k,
                include_globs=[Path(expected_file).name],
            )
        )
        hits.extend(hit for hit in file_hits if _matches_expected_file(str(hit.get("file", "")), [expected_file]))
    return _dedupe_hits(hits)


def verify_demo_rag(
    query: str,
    top_k: int = 5,
    *,
    expected_files: list[str] | None = None,
) -> dict[str, Any]:
    search_top_k = max(top_k, 50) if expected_files else top_k
    if expected_files:
        hits = _search_expected_file_hits(query, expected_files, top_k=search_top_k)
    else:
        hits = _flatten_search_groups(
            rag_iterative_search(
                query,
                [],
                _demo_rag_priority_dirs([]),
                [get_rag_dir()],
                top_k=search_top_k,
                include_globs=[],
            )
        )
    compact = [
        {
            "file": str(hit.get("file", "")),
            "line": str(hit.get("line", "")),
            "content": str(hit.get("content", ""))[:240],
            "scope": str(hit.get("scope", "rag")),
        }
        for hit in hits
    ]
    return {
        "query": query,
        "hit_count": len(compact),
        "hits": compact,
        "ready": len(compact) > 0,
    }
