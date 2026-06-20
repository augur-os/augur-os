# Contextual Retrieval for Augur RAG

**Date:** 2026-04-02
**Status:** Approved
**Scope:** Enhance existing ripgrep-based RAG with LLM-generated chunk context, BM25 scoring, and hybrid retrieval

## Problem

Augur's RAG system is purely keyword-based (ripgrep) with no term relevance scoring, no semantic context in chunks, and weak document retrieval. Pain points:

1. **Documents return no results** — 7,071 indexed document entries but queries don't surface them reliably
2. **Results ranked poorly** — relevant content buried under less relevant matches (no scoring)
3. **Chunks lose context** — heading-based chunks like "Configuration" match too many things without situating context
4. **No partial matching** — "configure notifications" won't find "notification settings"

## Approach

Implement Anthropic's Contextual Retrieval technique adapted for Augur's local-first architecture:

- **Contextual enrichment** via Qwen 3.5 9B (Ollama, local) at index time
- **BM25 scoring** via `rank_bm25` for term relevance
- **Hybrid retrieval** combining ripgrep + BM25 with Reciprocal Rank Fusion
- **Apple MLX OCR** for document extraction
- **Claude API** only for quality validation (small sample) and query-time reranking (existing)

Expected improvement: 49-67% reduction in retrieval failures (per Anthropic's research).

## Design

### 1. Chunking Overhaul

Current: heading-based splits of SKILL.md only (>2KB threshold), no overlap, 50-char minimum.

New chunking strategies by content type:

| Content Type | Strategy | Chunk Size | Overlap |
|---|---|---|---|
| Markdown (SKILL.md, ADRs, vault docs) | Heading-aware sliding window | ~1500 chars | 200 chars |
| Code files (scripts, api-routes, tests) | Function/class boundary detection | ~2000 chars | 100 chars |
| Extracted documents (PDFs, Office) | Paragraph-based sliding window | ~1000 chars | 200 chars |
| Small files (<500 chars) | No chunking — index whole file | Full file | N/A |

Key changes:
- Every category gets chunked, not just large SKILL.md files
- Overlap ensures no information lost at boundaries
- Heading-aware prefers breaks at `##` boundaries, falls back to sliding window for long sections
- Each chunk carries metadata: `source_path`, `chunk_index`, `total_chunks`, `section_heading`, `parent_heading`

### 2. Contextual Enrichment Pipeline

For each chunk, Qwen 3.5 9B generates a 1-2 sentence contextual prefix that situates the chunk within its source document.

**Prompt template:**

```
<document>
{full_document_text_or_first_3000_chars}
</document>

Here is a chunk from that document:
<chunk>
{chunk_text}
</chunk>

Write a short (1-2 sentence) context that situates this chunk within the document.
Include: what document/skill this is from, what section, and what the chunk specifically covers.
Do not repeat the chunk content. Only provide the context sentence(s).
```

**Integration with nightly pipeline:**

| Step | Detail |
|---|---|
| Input | Raw chunks from chunking phase |
| Batching | Process chunks grouped by source document (avoids re-reading same doc per chunk) |
| Ollama call | `POST http://localhost:11434/api/generate` with `model: qwen3.5:9b`, `stream: false` |
| Output | Frontmatter gets `context:` field; body becomes `{context}\n\n{original_body}` |
| Caching | Context tied to chunk checksum — unchanged chunks skip re-contextualization |
| Error handling | Circuit breaker pattern. Ollama down → skip enrichment, log warning, chunks indexed without context |

**Example before/after:**

Before:
```markdown
---
type: skill
name: rag
heading: Configuration
---
- Circuit breaker: 3 failures → 300s cooldown
- Max retries: 5 with exponential backoff
- LLM temperature: 0.1
```

After:
```markdown
---
type: skill
name: rag
heading: Configuration
context: "This chunk is from the RAG skill's search engine configuration section, describing the circuit breaker, retry, and LLM parameter settings used during query-time retrieval."
---
This chunk is from the RAG skill's search engine configuration section, describing the circuit breaker, retry, and LLM parameter settings used during query-time retrieval.

- Circuit breaker: 3 failures → 300s cooldown
- Max retries: 5 with exponential backoff
- LLM temperature: 0.1
```

Context appears in both frontmatter (programmatic access, BM25 weighting) and body (ripgrep full-text, LLM context for agents).

**Throughput:** Qwen 3.5 9B on Apple Silicon ~30-50 tokens/sec. ~40 tokens per context. ~15K chunks × 1.5s = ~6 hours full reindex. Incremental nightly runs: minutes.

### 3. BM25 Index

Builds a local BM25 index over all enriched chunks at index time. Provides TF-IDF-weighted term relevance scoring alongside ripgrep's exact matching.

**Ripgrep vs BM25 complementarity:**

| | Ripgrep | BM25 |
|---|---|---|
| Strength | Exact/regex matches, blazing fast | Term relevance, handles partial matches |
| Weakness | No ranking — all matches equal | Slower, needs pre-built index |
| Misses | "configure notifications" won't find "notification settings" | Won't find regex patterns or substring matches |

**Index storage:**

```
rag/
  _meta/
    manifest.yaml          # existing
    bm25_index.json        # NEW — serialized BM25 corpus
    bm25_chunk_map.json    # NEW — chunk_id → file path mapping
```

- `bm25_index.json`: tokenized corpus (lowercase, strip punctuation, split whitespace, remove stopwords). `rank_bm25` rebuilds scoring matrix on load.
- `bm25_chunk_map.json`: maps corpus position to source chunk path and metadata (skill, hub, category, heading).

**Build:** ~30 seconds for 30K chunks, ~15-25 MB on disk.

**Query-time:** Lazy-load on first search, keep in memory. `BM25Okapi` (k1=1.5, b=0.75). Cold start ~2-3s, subsequent queries <100ms.

**Dependency:** `rank_bm25` — pure Python, no C extensions, 1 file, no transitive deps.

### 4. Hybrid Retrieval & Reranking

**Query pipeline:**

```
User query
    |
    +---> Ripgrep (exact/regex)     -> hits with file paths
    |
    +---> BM25 (term relevance)     -> ranked chunk indices with scores
    |
    +---> Merge & Deduplicate
              |
              +---> Score fusion (RRF)
              |
              +---> LLM Rerank (existing Claude circuit-breaker pattern)
                        |
                        +---> Top-K results returned
```

**Reciprocal Rank Fusion (RRF):**

```
RRF_score(doc) = SUM( 1 / (k + rank_in_source) )
```

Where k=60 (standard constant). Uses rank positions only — no need to normalize disparate score types.

| Step | Detail |
|---|---|
| Ripgrep results | Assign rank by return order (first match = rank 1) |
| BM25 results | Already ranked by score, use position |
| Merge | Union by chunk file path, sum RRF scores |
| Deduplicate | Same chunk from both systems → single entry with combined score |
| Sort | Descending RRF score |
| LLM rerank | Top 20 candidates to existing Claude reranker → final top-K |

**Unchanged:** LLM iterative query refinement (3 rounds), circuit breaker fallback to RRF-only, `search-skill-knowledge` MCP tool interface.

**Latency budget:**

| Step | Latency |
|---|---|
| Ripgrep | ~50-200ms |
| BM25 query | ~50-100ms (in-memory) |
| RRF merge | <10ms |
| LLM rerank | ~1-3s (optional) |
| **Total** | **~200ms without LLM, ~2-3s with** |

### 5. Document Extraction Enhancement

**Changes:**

| Aspect | Current | New |
|---|---|---|
| OCR | External API or basic text extraction | Apple MLX OCR for images/scanned PDFs |
| Chunking | Whole-file or heading-based | Paragraph-based sliding window (1000 chars, 200 overlap) |
| Context | Filename + basic frontmatter | Qwen 3.5 contextual prefix per chunk |
| Metadata | `source_path`, `type` | + `document_title`, `page_number`, `section`, `content_type` |

**Detection logic:**

```
Text-based PDF?     -> pymupdf text extraction
Scanned PDF?        -> page images -> MLX OCR
Image file?         -> MLX OCR directly
Office/HTML?        -> existing document-extractor pipeline
```

Extracted markdown cached in `rag/documents/_extracted/` with checksum — re-extraction only on source file change. Chunks flow into same Phase 2-4 as everything else.

**Dependency:** `mlx-vlm` — Apple-native, optimized for M-series.

### 6. Integration with Existing System

**Unchanged:** `unified_indexer.py` orchestration, checksum detection, markdown+frontmatter format, MCP tool interfaces, dashboard frontend, adaptive loop triggers, manifest structure.

**Modified files:**

| File | Change |
|---|---|
| `skills/rag/scripts/unified_indexer.py` | Add phases 2-4 after category scans: chunker, contextualizer, BM25 builder |
| `skills/rag/scripts/search_engine.py` | Add BM25 retrieval alongside ripgrep, RRF merge before LLM rerank |
| `skills/rag/scripts/_indexer_helpers.py` | New chunking functions |
| `skills/rag/scripts/enrich_descriptions.py` | Tier 0: Ollama contextual enrichment before existing Tier 1/2 |
| `skills/rag/scripts/mcp/rag_tools.py` | `rag-status` returns BM25 stats, `rag-reindex` triggers full pipeline |

**New files:**

| File | Purpose |
|---|---|
| `skills/rag/scripts/chunker.py` | Chunking strategies (sliding window, heading-aware, code-boundary) |
| `skills/rag/scripts/contextualizer.py` | Ollama client, prompt template, batch processing, checksum caching |
| `skills/rag/scripts/bm25_index.py` | BM25 build, serialize, load, query |
| `skills/rag/scripts/retrieval.py` | Hybrid retrieval: ripgrep + BM25, RRF fusion, dedup |
| `skills/rag/scripts/ocr_extractor.py` | Apple MLX OCR pipeline, PDF detection, fallback logic |

**Configuration** (in `config/defaults/config/system/preferences.yaml`):

```yaml
rag:
  chunk_size: 1500
  chunk_overlap: 200
  document_chunk_size: 1000
  bm25_top_k: 50
  rrf_k: 60
  final_top_k: 10
  contextualization:
    enabled: true
    model: qwen3.5:9b
    max_context_tokens: 100
  ocr:
    enabled: true
    backend: mlx
```

**Error handling:** Circuit breaker on Ollama, graceful degradation. Contextualization fails → chunks indexed without context. BM25 missing/corrupt → ripgrep-only fallback. No new failure modes that break existing functionality.

### 7. Quality Validation & Metrics

**Nightly validation gate (post-indexing):**

| Check | Method | Threshold |
|---|---|---|
| Context quality | Sample 50 chunks → Claude API: "Rate 1-5 for accuracy/usefulness" | Average >= 3.5 |
| Context coverage | Chunks with non-empty `context:` / total | >= 95% |
| BM25 index integrity | Load index, run 5 known queries, verify expected docs in top 10 | 5/5 pass |
| Chunk completeness | Verify no source file has 0 chunks | 0 gaps |

**Search quality metrics** (logged per query to `rag/_meta/search_metrics.jsonl`):

```yaml
query: "configure notifications"
timestamp: 2026-04-02T03:15:00Z
ripgrep_hits: 12
bm25_hits: 18
merged_candidates: 24
deduplicated: 19
rrf_top_10:
  - {path: "chunks/channels/...", rrf_score: 0.033, source: "both"}
  - {path: "chunks/attention/...", rrf_score: 0.026, source: "bm25_only"}
llm_reranked: true
latency_ms: 1840
```

**Before/after comparison (rollout):** 20 known pain-point queries, run against old and new pipeline. Compare recall (expected result in top 10), rank position, total relevant in top 10. Stored in `skills/rag/assets/seeds/quality_baseline.yaml`.

**Evolution (CLAUDE.md rule 8):** Once all checks pass at max difficulty, nightly loop reports gaps with specific next actions.

## Nightly Pipeline Summary

| Phase | Engine | Time (full) | Time (incremental) |
|---|---|---|---|
| 1. Extract (OCR) | Apple MLX + pymupdf | ~1-2 hours | Minutes |
| 2. Chunk | Python (no LLM) | ~5 min | ~1 min |
| 3. Contextualize | Qwen 3.5 9B via Ollama | ~6-8 hours | ~20-40 min |
| 4. Build BM25 | `rank_bm25` (Python) | ~30 sec | ~30 sec |
| 5. Enrich descriptions | Ollama + Claude fallback | ~1-2 hours | Minutes |
| 6. Validate | Claude API (50 samples) | ~2 min | ~2 min |

## Storage Impact

| Component | Current | Projected |
|---|---|---|
| RAG directory total | 109 MB | ~160-180 MB |
| Chunks | 4,230 files / 17 MB | ~25-30K files / ~40-50 MB |
| BM25 index | N/A | ~15-25 MB |
| Existing entries | 14,654 files / 92 MB | Unchanged |

## Dependencies

| Package | Purpose | Size/Impact |
|---|---|---|
| `rank_bm25` | BM25 scoring | Pure Python, 1 file, no transitive deps |
| `mlx-vlm` | Apple MLX OCR | Apple-native, M-series optimized |
