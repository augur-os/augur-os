---
status: Implemented
date: '2025-01-08'
deciders:
- Core team
related: []
hub: null
tags:
- markdown
- rag
- over
- vector
- databases
superseded_by: null
---

# ADR-004: Markdown RAG over Vector Databases

**Implemented**: 2026-01-15

## Context

Augur needs to search across user documents (notes, medical records, contracts, recipes) to provide context to LLM agents. Traditional RAG systems use vector databases (Pinecone, Weaviate, ChromaDB) with embeddings.

Early experiments with vector-based RAG revealed issues:
- **Semantic drift**: Embeddings sometimes retrieved topically related but factually wrong content
- **Infrastructure overhead**: Required running a separate database service
- **Opacity**: Hard to debug why certain results were (or weren't) returned
- **Embedding costs**: Re-indexing large document sets was expensive
- **Multilingual support**: Embedding models had poor support for non-English languages (e.g., Hebrew)
- **Portability**: Vector DBs are hard to migrate between machines

## Decision

Adopt a **Markdown-first RAG system** using full-text search:

### Architecture
```
Level 1: Native Data Repo (augur-data/)
├── Direct markdown/YAML files
├── Searched with ripgrep
└── No indexing required

Level 2: External Documents
├── Converted to markdown via indexer
├── OCR for images/scans (optional)
└── Stored in _indexed/ directories

Level 3: Master Index
├── YAML index of all documents
├── Metadata, checksums, paths
└── Fast lookup without scanning
```

### Search Strategy
- Primary: ripgrep for full-text search (fast, regex-capable)
- Secondary: YAML index for metadata queries
- Tertiary: Multilingual synonym expansion via manual YAML mappings (e.g., Hebrew, Arabic)

### OCR as Horizontal Skill
- OCR (Tesseract) is a separate skill, not core RAG
- Documents are OCR'd once, stored as markdown
- Re-indexing uses checksums to skip unchanged files

## Consequences

### Positive

- **Transparency**: Can see exactly what's indexed (it's just markdown files)
- **Zero infrastructure**: No database to run, just files
- **Debuggability**: Search results are deterministic, easy to trace
- **Portability**: Copy files to new machine, done
- **Multilingual support**: Manual synonym YAML works for any language
- **Cost**: No embedding API calls, no vector DB hosting
- **Speed**: ripgrep is extremely fast on local files

### Negative

- **No semantic search**: Must use exact keywords or synonyms
- **Manual synonym maintenance**: Language-specific synonyms need manual curation
- **Large document handling**: Very large files need chunking strategy
- **No similarity ranking**: Results are match/no-match, not scored by relevance

### Neutral

- PDF/Word documents converted to markdown on import
- Image-heavy documents need OCR preprocessing
- Incremental indexing via SHA256 checksums

## Alternatives Considered

### Alternative 1: ChromaDB (Local Vector DB)

Run ChromaDB locally for embeddings-based search. Rejected because:
- Still requires running a service
- Embedding quality varies by language (especially non-English)
- Debug opacity ("why did this match?")
- Collection management overhead

### Alternative 2: Elasticsearch

Full-featured search engine with ranking. Rejected because:
- Heavy infrastructure for personal use
- JVM memory requirements
- Overkill for document volumes involved
- Complex query language

### Alternative 3: Hybrid (Vector + Keyword)

Use both embeddings and keyword search. Rejected because:
- Combines complexity of both approaches
- Still has embedding costs and opacity
- Unclear when to use which approach
- Higher maintenance burden

### Alternative 4: Cloud RAG (Pinecone, Weaviate Cloud)

Use managed vector database service. Rejected because:
- Violates local-first principle
- Ongoing costs
- Privacy concerns (data leaves machine)
- Internet dependency

## Implementation Notes (2026-01-15)

> **Note (2026-01-27)**: RAG MCP tools were moved to `plugins/ai/skills/knowledge/augur/`.
> The previous `src/mcp/infrastructure/rag.py` has been removed as it referenced non-existent modules.

### Components Implemented
- **MCP tools**: `plugins/ai/skills/knowledge/augur/` (list-rag-projects, create-rag-project)
- **Dashboard services**: `src/dashboard/lib/services/rag-projects.ts`
- **Data storage**: `data/rag/` (indexes, projects)

### MCP Tools Available
| Tool | Purpose |
|------|---------|
| `markdown-rag-index` | Index documents with optional OCR |
| `markdown-rag-search` | Search indexed documents |
| `markdown-rag-stats` | Get indexing statistics |
| `search-augur-data` | Search native data repo (Level 1) |

### Python API
```python
from src/lib.rag import MarkdownIndexer, MarkdownSearcher

# Index documents
indexer = MarkdownIndexer()
indexer.index_directory(Path("/path/to/docs"), project="my_project")

# Search
searcher = MarkdownSearcher()
results = searcher.search("authentication", project="my_project")
```

### Test Coverage
- 84 unit and integration tests
- Tests in `src/rag/tests/`

### Initial Indexing Stats
- **augur code repo**: 34,695 files indexed
- **augur-data repo**: 19,534 files indexed
- **Total**: 54,229 indexed files

## References

- [ADR-006](./ADR-006-local-first.md) - Local-first architecture decision
- `plugins/ai/skills/knowledge/augur/` - RAG MCP tools
- `src/dashboard/lib/services/rag-projects.ts` - Dashboard services
