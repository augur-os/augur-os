"""
BM25 sparse retrieval index for the RAG pipeline.

Wraps rank_bm25.BM25Okapi with tokenization, serialization, and
a clean query interface returning scored chunk references.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Optional

try:
    from rank_bm25 import BM25Okapi
except ImportError:

    class BM25Okapi:  # type: ignore[override]
        """Lightweight BM25-compatible fallback when rank_bm25 is unavailable."""

        def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
            self._corpus = corpus
            self._k1 = k1
            self._b = b
            self._doc_freqs: list[dict[str, int]] = []
            self._idf: dict[str, float] = {}
            self._doc_lens = [len(doc) for doc in corpus]
            self._avgdl = sum(self._doc_lens) / len(self._doc_lens) if self._doc_lens else 0.0

            term_doc_counts: dict[str, int] = {}
            for doc in corpus:
                freqs: dict[str, int] = {}
                for token in doc:
                    freqs[token] = freqs.get(token, 0) + 1
                self._doc_freqs.append(freqs)
                for token in freqs:
                    term_doc_counts[token] = term_doc_counts.get(token, 0) + 1

            doc_count = len(corpus)
            for token, freq in term_doc_counts.items():
                self._idf[token] = math.log(1 + (doc_count - freq + 0.5) / (freq + 0.5))

        def get_scores(self, query_tokens: list[str]) -> list[float]:
            scores: list[float] = []
            for freqs, doc_len in zip(self._doc_freqs, self._doc_lens):
                score = 0.0
                norm = self._k1 * (1 - self._b + self._b * doc_len / self._avgdl) if self._avgdl else self._k1
                for token in query_tokens:
                    tf = freqs.get(token, 0)
                    if tf <= 0:
                        continue
                    idf = self._idf.get(token, 0.0)
                    score += idf * (tf * (self._k1 + 1)) / (tf + norm)
                scores.append(score)
            return scores


# Bootstrap project root so src.lib.tokenizer is importable
_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.lib.tokenizer import tokenize as _tokenize  # noqa: E402

# BM25Okapi tuning parameters — shared between build() and load()
_BM25_K1 = 1.5
_BM25_B = 0.75


# ---------------------------------------------------------------------------
# BM25Index
# ---------------------------------------------------------------------------


class BM25Index:
    """BM25 index over a list of text chunks."""

    def __init__(
        self,
        bm25: Optional[BM25Okapi],
        chunk_map: list[dict],
        corpus: Optional[list[list[str]]] = None,
    ) -> None:
        self._bm25 = bm25
        self._chunk_map = chunk_map  # list of {path, meta}
        self._corpus: list[list[str]] = corpus if corpus is not None else []

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def build(cls, chunks: list[dict]) -> "BM25Index":
        """Build from list of {path, text, meta} dicts."""
        if not chunks:
            return cls(bm25=None, chunk_map=[], corpus=[])

        corpus = [_tokenize(c["text"]) for c in chunks]
        bm25 = BM25Okapi(corpus, k1=_BM25_K1, b=_BM25_B)
        chunk_map = [{"path": c["path"], "meta": c.get("meta", {})} for c in chunks]
        return cls(bm25=bm25, chunk_map=chunk_map, corpus=corpus)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def size(self) -> int:
        return len(self._chunk_map)

    def query(self, query: str, top_k: int = 50) -> list[dict]:
        """Return list of {path, score, meta} sorted by score descending.

        Stops including results where score <= 0.
        """
        if not query or self._bm25 is None:
            return []

        tokens = _tokenize(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)

        results = []
        for i, score in enumerate(scores):
            if score > 0:
                results.append(
                    {
                        "path": self._chunk_map[i]["path"],
                        "score": float(score),
                        "meta": self._chunk_map[i]["meta"],
                    }
                )

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def save(self, directory: Path) -> None:
        """Save bm25_index.json (tokenized corpus) and bm25_chunk_map.json."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        (directory / "bm25_index.json").write_text(
            json.dumps(self._corpus, ensure_ascii=False, indent=None),
            encoding="utf-8",
        )
        (directory / "bm25_chunk_map.json").write_text(
            json.dumps(self._chunk_map, ensure_ascii=False, indent=None),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path) -> "BM25Index":
        """Load from directory. Returns empty index if files missing."""
        directory = Path(directory)
        index_file = directory / "bm25_index.json"
        chunk_map_file = directory / "bm25_chunk_map.json"

        if not index_file.exists() or not chunk_map_file.exists():
            return cls(bm25=None, chunk_map=[], corpus=[])

        corpus: list[list[str]] = json.loads(index_file.read_text(encoding="utf-8"))
        chunk_map: list[dict] = json.loads(chunk_map_file.read_text(encoding="utf-8"))

        if not corpus:
            return cls(bm25=None, chunk_map=chunk_map, corpus=[])

        bm25 = BM25Okapi(corpus, k1=_BM25_K1, b=_BM25_B)
        return cls(bm25=bm25, chunk_map=chunk_map, corpus=corpus)
