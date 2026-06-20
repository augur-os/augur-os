"""Core RetrieverSource implementations for RRF fusion (ADR-739)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.index.rrf import RankedHit

FRESH_DOCUMENT_STATUSES = {"", "synced"}
SEARCHABLE_DOCUMENT_STATUSES = FRESH_DOCUMENT_STATUSES | {"summary_stale"}


def bm25_query_limit(limit: int) -> int:
    return max(limit * 5, limit + 20)


def document_index_status(meta: dict[str, Any]) -> str:
    return str(meta.get("index_status") or "").strip()


def document_status_is_searchable(
    index_status: str,
    *,
    include_stale_documents: bool = False,
) -> bool:
    return include_stale_documents or index_status in SEARCHABLE_DOCUMENT_STATUSES


def document_status_warning(index_status: str) -> str:
    return "" if index_status in FRESH_DOCUMENT_STATUSES else index_status


def bm25_hit_is_document(hit: dict[str, Any]) -> bool:
    meta = hit.get("meta", {}) or {}
    category = meta.get("category")
    return category == "documents" or str(hit.get("path") or "").startswith("chunks/documents/")


def _ripgrep_document_pointer_path(
    hit: dict[str, Any],
    rag_dirs: list[Path],
) -> Path | None:
    file_path = str(hit.get("file") or "")
    if not file_path or not rag_dirs:
        return None
    path = Path(file_path)
    try:
        resolved = path.resolve(strict=False)
    except OSError:
        resolved = path.absolute()
    for rag_dir in rag_dirs:
        documents_dir = rag_dir / "documents"
        try:
            resolved.relative_to(documents_dir.resolve(strict=False))
        except (OSError, ValueError):
            continue
        return resolved if resolved.suffix.lower() == ".md" else None
    return None


def _ripgrep_document_pointer_meta(
    hit: dict[str, Any],
    rag_dirs: list[Path],
) -> dict[str, Any] | None:
    path = _ripgrep_document_pointer_path(hit, rag_dirs)
    if path is None:
        return None
    try:
        meta, _body = parse_frontmatter(path, include_sidecar_config=False)
    except OSError:
        return {}
    return meta


def _filter_ripgrep_document_hits(
    hits: list[dict[str, Any]],
    rag_dirs: list[Path],
    *,
    include_stale_documents: bool = False,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for hit in hits:
        meta = _ripgrep_document_pointer_meta(hit, rag_dirs)
        if meta is None:
            filtered.append(hit)
            continue
        index_status = document_index_status(meta)
        if not document_status_is_searchable(
            index_status,
            include_stale_documents=include_stale_documents,
        ):
            continue
        enriched = dict(hit)
        if index_status:
            enriched["index_status"] = index_status
        warning = document_status_warning(index_status)
        if warning:
            enriched["stale_source_warning"] = warning
        filtered.append(enriched)
    return filtered


class BM25Source:
    """RetrieverSource over the existing BM25Index."""

    name = "bm25"

    def __init__(
        self,
        bm25_index: Any | None,
        *,
        include_stale_documents: bool = False,
    ) -> None:
        self._index = bm25_index
        self._include_stale_documents = include_stale_documents

    def search(self, query: str, *, limit: int) -> list[RankedHit]:
        if self._index is None or limit <= 0 or not query.strip():
            return []
        hits = self._index.query(query, top_k=bm25_query_limit(limit))
        ranked: list[RankedHit] = []
        for hit in hits:
            path = str(hit.get("path", ""))
            if not path:
                continue
            meta = hit.get("meta", {}) or {}
            if bm25_hit_is_document(hit):
                index_status = document_index_status(meta)
                if not document_status_is_searchable(
                    index_status,
                    include_stale_documents=self._include_stale_documents,
                ):
                    continue
            else:
                index_status = ""

            payload = {
                "file": path,
                "content": f"BM25 score: {float(hit.get('score', 0.0)):.3f}",
                "score": float(hit.get("score", 0.0)),
                **meta,
            }
            warning = document_status_warning(index_status)
            if warning:
                payload["stale_source_warning"] = warning
            ranked.append(
                RankedHit(
                    doc_id=path,
                    rank=len(ranked) + 1,
                    raw_score=float(hit.get("score", 0.0)),
                    snippet=str(meta.get("snippet", "")),
                    payload=payload,
                )
            )
            if len(ranked) >= limit:
                break
        return ranked


class RipgrepSource:
    """RetrieverSource over the existing ripgrep full-text helpers."""

    name = "ripgrep"

    def __init__(
        self,
        search_dirs: list[Path],
        rag_dirs: list[Path] | None = None,
        *,
        include_globs: list[str] | None = None,
        include_stale_documents: bool = False,
    ) -> None:
        self._search_dirs = search_dirs
        self._rag_dirs = rag_dirs or []
        self._include_globs = include_globs
        self._include_stale_documents = include_stale_documents

    def search(self, query: str, *, limit: int) -> list[RankedHit]:
        if not query.strip():
            return []

        from src.lib.index.unified_search import (
            _collect_active_search_hits,
            _dedup_by_file,
            _score_hits,
            _to_rg_pattern,
        )

        # Collect a deep candidate pool, decoupled from `limit`. ripgrep walks in
        # `--sort path` order, so capping collection at `limit` truncates by file
        # path position before scoring — a strong filename-slug match in a large
        # folder (sorting late) never gets scored. Collect wide, let _score_hits
        # (which counts query terms in the file path too) pick the top `limit`.
        raw_hits = _collect_active_search_hits(
            _to_rg_pattern(query),
            self._search_dirs,
            max_hits=max(limit * 20, 1000),
            rag_dirs=self._rag_dirs,
            extra_globs=self._include_globs,
        )
        raw_hits = _filter_ripgrep_document_hits(
            raw_hits,
            self._rag_dirs,
            include_stale_documents=self._include_stale_documents,
        )
        scored = _dedup_by_file(_score_hits(raw_hits, query.strip().split()))[:limit]
        return [
            RankedHit(
                doc_id=str(hit.get("file", "")),
                rank=index + 1,
                raw_score=float(hit.get("score", 0.0)),
                snippet=str(hit.get("content", "")),
                payload=dict(hit),
            )
            for index, hit in enumerate(scored)
            if hit.get("file")
        ]


class GraphSource:
    """RetrieverSource over the ADR-738 rebuildable typed-graph cache."""

    name = "graph"

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._cache_dir = cache_dir

    def _resolve_cache_dir(self) -> Path:
        if self._cache_dir is not None:
            return self._cache_dir
        from src.config.paths import get_cache_dir

        return get_cache_dir() / "graph"

    def search(self, query: str, *, limit: int) -> list[RankedHit]:
        terms = [term.lower() for term in query.strip().split() if term.strip()]
        if not terms:
            return []

        cache_dir = self._resolve_cache_dir()
        edges = _load_jsonl(cache_dir / "edges.jsonl")
        entities = _load_jsonl(cache_dir / "entities.jsonl")
        if not edges and not entities:
            return []

        matches: dict[str, dict[str, Any]] = {}

        for entity in entities:
            entity_id = str(entity.get("id") or "")
            if not entity_id:
                continue
            entity_text = entity_id.lower()
            term_hits = sum(1 for term in terms if term in entity_text)
            if term_hits == 0:
                continue
            tier = int(entity.get("tier") or 3)
            inbound = int(entity.get("inbound_count") or 0)
            score = float(term_hits * 10 + inbound + max(0, 4 - tier))
            _merge_graph_match(
                matches,
                entity_id,
                score,
                f"Graph entity tier {tier}: {entity_id} ({inbound} inbound edges)",
                {"graph_kind": "entity", "tier": tier, "inbound_count": inbound},
            )

        for edge in edges:
            src = str(edge.get("src") or "")
            dst = str(edge.get("dst") or "")
            edge_type = str(edge.get("type") or "")
            edge_text = f"{src} {dst} {edge_type}".lower()
            term_hits = sum(1 for term in terms if term in edge_text)
            if term_hits == 0:
                continue
            doc_id = src or dst
            if not doc_id:
                continue
            score = float(term_hits * 5)
            _merge_graph_match(
                matches,
                doc_id,
                score,
                f"Graph edge: {src} -[{edge_type}]-> {dst}",
                {"graph_kind": "edge", "edge_type": edge_type, "dst": dst},
            )

        ranked = sorted(matches.items(), key=lambda item: (-float(item[1]["score"]), item[0]))
        return [
            RankedHit(
                doc_id=doc_id,
                rank=index + 1,
                raw_score=float(match["score"]),
                snippet=str(match["content"]),
                payload={
                    "file": doc_id,
                    "content": str(match["content"]),
                    "score": float(match["score"]),
                    **dict(match.get("metadata") or {}),
                },
            )
            for index, (doc_id, match) in enumerate(ranked[:limit])
        ]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _merge_graph_match(
    matches: dict[str, dict[str, Any]],
    doc_id: str,
    score: float,
    content: str,
    metadata: dict[str, Any],
) -> None:
    current = matches.get(doc_id)
    if current is None:
        matches[doc_id] = {"score": score, "content": content, "metadata": metadata}
        return
    current_score = float(current["score"])
    current["score"] = current_score + score
    if score > current_score:
        current["content"] = content
        current["metadata"] = metadata
