"""Reciprocal Rank Fusion for hybrid search (ADR-739).

RRF is pure rank-fusion math over existing retriever outputs. It owns no index,
database, model call, or provider-specific retrieval behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class RankedHit:
    """One hit from a retriever, with its 1-indexed rank."""

    doc_id: str
    rank: int
    raw_score: float = 0.0
    snippet: str = ""
    payload: dict | None = None


@runtime_checkable
class RetrieverSource(Protocol):
    """A named retriever that returns ranked hits for a query."""

    name: str

    def search(self, query: str, *, limit: int) -> list[RankedHit]: ...


def fuse(ranked_lists: dict[str, list[RankedHit]], *, k: int = 60, top_k: int = 10) -> list[dict]:
    """Fuse per-source ranked lists via RRF.

    Each result contains ``doc_id``, RRF ``score``, sorted ``provenance``, the
    first available ``snippet``, and the first source payload if provided.
    """
    if top_k <= 0:
        return []

    scores: dict[str, float] = {}
    provenance: dict[str, list[str]] = {}
    snippets: dict[str, str] = {}
    payloads: dict[str, dict] = {}

    for source_name, hits in sorted(ranked_lists.items()):
        for hit in hits:
            if not hit.doc_id or hit.rank <= 0:
                continue
            scores[hit.doc_id] = scores.get(hit.doc_id, 0.0) + 1.0 / (k + hit.rank)
            provenance.setdefault(hit.doc_id, []).append(source_name)
            if hit.snippet and hit.doc_id not in snippets:
                snippets[hit.doc_id] = hit.snippet
            if hit.payload is not None and hit.doc_id not in payloads:
                payloads[hit.doc_id] = hit.payload

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [
        {
            "doc_id": doc_id,
            "score": round(score, 6),
            "provenance": sorted(provenance[doc_id]),
            "snippet": snippets.get(doc_id, ""),
            "payload": payloads.get(doc_id, {}),
        }
        for doc_id, score in ranked[:top_k]
    ]
