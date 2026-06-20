# RAG Simplification: Three-Tier Knowledge System

## Problem

The current RAG system costs ~27% of Claude API quota nightly (1,031 `claude --print` sessions) for a search path called 11 times across 2,982 sessions. AI clients use Grep (10,554 calls) and Read (29,584 calls) instead. The system chunks 9,355 markdown files that are already natively readable, contextualizes each with an LLM call, and builds a BM25 index that adds marginal value over ripgrep.

## Design

Replace the monolithic RAG pipeline with three tiers matched to content type.

### Tier 1: Simple (ripgrep on source files)

**Content:** Skills, vault notes, scripts, pages, blocks, MCP tools, API routes, tests, workflows, prompts, agents, integrations, CLI commands.

**How it works:** Category scanners write index entries (pointer .md files with frontmatter). `index.md` (Karpathy catalog) generated statically from these entries. Search uses ripgrep on original source files. No chunking, no BM25, no LLM.

**Categories:** skills, vault, scripts, pages, blocks, mcp-tools, api-routes, tests, workflows, prompts, agents, integrations, cli-commands

**Cost:** $0. Instant.

### Tier 2: Extract (document pipeline)

**Content:** Binary documents -- PDFs, Office docs, images with OCR. Source: `~/Documents` (558 PDFs, 60 docx, 28 pptx, 24 xlsx, 28 doc).

**How it works:** Document extractor converts to markdown. Content chunked (~1500 tokens, heading-aware). BM25 index built over document chunks only. Search uses BM25 + ripgrep on extracted text. No LLM contextualization.

**Categories:** documents

**Output:** `rag/chunks/documents/` (~3,000-5,000 chunk files), `_meta/bm25_index.json` (documents only)

**Cost:** $0. Minutes for extraction on first run, incremental via mtime cache.

### Tier 3: Wiki (Karpathy LLM Wiki pattern)

**Content:** ADRs, memory, logs, docs/ guides, chat session learnings.

**How it works:** Adapted directly from [Karpathy's LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). No batch pipeline or nightly compiler. AI clients (Claude Code, Codex) maintain the wiki during normal conversations using the schema prompt.

**Three operations:**
- **Ingest**: User drops a source or AI client encounters new knowledge → reads it, writes/updates wiki pages, updates index.md, appends log.md
- **Query**: User asks question → AI reads wiki/index.md → finds relevant pages → answers with citations. Good answers filed back as wiki pages (compounding).
- **Lint**: Periodic health check for contradictions, orphans, stale claims, missing cross-refs.

**Wiki directory:**

```
rag/wiki/
├── index.md              # Content catalog of all wiki pages
├── log.md                # Append-only chronological operation log
├── overview.md           # System-wide summary (entry point)
├── architecture/         # Compiled from ADRs
│   ├── dashboard.md
│   ├── skills-system.md
│   ├── data-flow.md
│   └── ...
├── decisions/            # Active vs superseded decisions
│   ├── active.md
│   └── superseded.md
├── user/                 # Compiled from memory entries
│   ├── preferences.md
│   └── workflows.md
└── operations/           # Compiled from logs
    ├── health.md
    └── incidents.md
```

**Wiki sources (what feeds the wiki, not stored in wiki/):**

| Source | Location | What the wiki captures |
|--------|----------|----------------------|
| ADRs | vault/dev/adrs/ | Bottom-line architectural decisions, what supersedes what |
| Memory | ~/.claude/projects/*/memory/ | User preferences, project context, feedback patterns |
| Logs | ~/Library/Logs/Augur/ | System health trends, recurring issues |
| Docs | docs/ folder | How things work, guides, references |
| Chat sessions | Session history | Learnings, decisions made during conversations |

**Implementation:** The wiki is maintained by AI clients during conversations, not a batch process. The schema prompt (adapted from Karpathy's gist) is added to CLAUDE.md or a dedicated skill. When an AI client reads ADRs, processes memory, or handles questions, it updates wiki pages as a side effect.

**Cost:** $0 incremental (wiki maintenance happens within existing conversations). Initial seeding of wiki pages from existing ADRs/memory can be done in one session.

**"Every conversation makes the system smarter":** Session learnings → memory entries → AI client updates wiki pages → next session starts with compiled knowledge in wiki/overview.md.

### Dashboard: Browse Page Tabs

| Tab | Source | Tier |
|-----|--------|------|
| Skills (existing) | skills/*/SKILL.md | Tier 1 |
| Documents (existing) | ~/Documents | Tier 2 |
| Wiki (new) | rag/wiki/ | Tier 3 |

### Search Flow

```
/search <query>
  │
  ├─ Tier 1: ripgrep on vault, skills, docs (source files)
  ├─ Tier 2: BM25 on document chunks
  └─ Tier 3: ripgrep on wiki/ pages
  │
  └─ AI client reasons over combined results
```

### Strategy Router

Categories mapped to tiers in config, not code:

```yaml
strategies:
  simple:    [skills, vault, scripts, pages, blocks, mcp-tools,
              api-routes, tests, workflows, prompts, agents,
              integrations, cli-commands]
  extract:   [documents]
  wiki:      [adrs, memory, logs, docs, sessions]
```

Moving a category between tiers = one config line change.

## Phase 1: Kill the Waste

Ship in days. Zero new features, pure deletion.

### Delete

| Component | File | Why |
|-----------|------|-----|
| Contextualizer | `skills/rag/scripts/contextualizer.py` | 1,031 Claude calls/night, 11 total searches |
| Circuit breaker | `skills/rag/scripts/_circuit_breaker.py` | Only used by contextualizer |
| Markdown chunking | `_chunk_all()` in `unified_indexer.py` for non-document categories | 9,200 chunk files for content that's already greppable |
| Markdown BM25 | BM25 build from markdown chunks | Keep only for documents |
| RRF merge | `retrieval.py::hybrid_search()` | No BM25 for markdown means no merge |
| LLM reranking | `search_engine.py` LLM path | More Claude calls for marginal quality |
| Context cache | `rag_context_cache.json` | No contextualizer |
| Auto-enrich-metadata | `skills/rag/scripts/ops/enrich_metadata.py` | No markdown chunks to enrich |
| `contextualize` param | All callers of `reindex_all()` | No longer exists |

### Modify

| File | Change |
|------|--------|
| `unified_indexer.py` | Remove `_chunk_all()` for markdown categories, remove `_contextualize_chunks()`, keep `index_documents()` + document chunking + BM25 for documents only |
| `mcp/rag_tools.py` | Simplify search: ripgrep tiers for markdown + BM25 for documents. Remove hybrid/RRF. |
| `retrieval.py` | Remove `hybrid_search()`, keep BM25 query for documents |
| `search_engine.py` | Remove LLM reranking path |
| `rag/SKILL.md` | Remove `auto-enrich-metadata` auto-command, update description |
| `skills/ai/scripts/ops/rag_reindex.py` | Remove `contextualize` param |
| `skills/auto-rag-reindex/scripts/rag_reindex_ops.py` | Simplify validation |
| `llm.yaml` | Add `active_profile: local` as safety net |

### Config

- Update `project.yaml` documents_dir to point to `~/Documents` (was `Au-docs`)

### Cleanup

- Delete `~/Library/Application Support/Augur/rag/chunks/` (all non-documents dirs)
- Delete `~/Library/Application Support/Augur/rag/_meta/bm25_index.json` (rebuild for documents only)
- Delete `~/Library/Application Support/Augur/state/adaptive/rag_context_cache.json`
- Run `/search reindex` once to rebuild clean state

### Result

- Nightly cost: **$0** (down from ~27% quota)
- Chunk files: **~150 documents only** (down from 9,355)
- Search quality: **Same or better** for markdown (ripgrep on originals), same for documents (BM25)

## Phase 2: Wiki Tier

Requires ADR. Separate planning cycle.

### New Components

| Component | What |
|-----------|------|
| `rag/wiki/` directory | Wiki pages maintained by AI clients |
| Wiki schema prompt | Adapted from Karpathy gist, added to CLAUDE.md or skill |
| Wiki dashboard tab | Shows wiki/ contents in browse page |
| Session learning hook | Extracts learnings from conversations → feeds wiki |
| `/search reindex --wiki` | On-demand wiki seeding from existing ADRs/memory |
| Lint command | `/wiki lint` for contradiction/orphan detection |

### Compounding Loop

```
Conversation → learnings extracted → memory updated
    → AI client updates wiki pages → next conversation 
    starts with compiled knowledge → smarter conversation
```

### Wiki Location

Wiki pages live in **`Au-vault/wiki/`** (git-tracked), not in the RAG runtime directory.

Rationale: Wiki is curated knowledge, not generated cache. It needs version history, portability across machines, and persistence across cache clears. The vault is the source of truth for all user knowledge.

The RAG runtime dir (`~/Library/Application Support/Augur/rag/`) keeps only generated/regeneratable artifacts: index.md, _meta/, chunks/documents/, category index entries.

### Wiki as Cross-Client Memory

Per-client memory (`.claude/memory/`, Codex memory, etc.) remains as short-term session scratch. The wiki becomes the **shared long-term knowledge layer** across all AI clients.

```
Claude Code → updates Au-vault/wiki/
Codex       → updates Au-vault/wiki/
Local LLM   → updates Au-vault/wiki/
                      │
                      ▼
              Next session (any client)
              reads wiki/overview.md
              starts with compiled context
```

This replaces the need for a separate cross-client memory sync system. Each client writes to the wiki during conversations. The vault is already accessible to all clients. The wiki schema prompt (in CLAUDE.md/AGENTS.md/CODEX.md) instructs every client to maintain the same wiki conventions.

### Documents Directory

`Au-docs/` remains as-is for Phase 1. Documents relevant for search are in Au-docs, pointed to by `project.yaml` documents_dir. The move to `~/Documents` is a separate future step.

### Source Map

| Location | Git? | Role in new system |
|----------|------|--------------------|
| `skills/` | Yes | Tier 1 source (ripgrep) |
| `docs/` | Yes | Tier 1 source (ripgrep) |
| `config/` | Yes | Tier 1 source (ripgrep) |
| `Au-vault/` | Yes | Tier 1 source (vault notes) + Wiki source (ADRs, memory) |
| `Au-vault/wiki/` | Yes | **Tier 3 output** (compiled knowledge, cross-client) |
| `Au-docs/` | ? | Tier 2 source (binary documents) |
| `.claude/memory/` | No | Per-client scratch (Claude Code only) |
| `~/Library/.../rag/` | No | Generated artifacts: index.md, document chunks, BM25, metadata |
| `~/Library/Logs/Augur/` | No | Wiki source (logs, incidents) |
| `~/.claude/projects/*.jsonl` | No | Wiki source (session learnings) |

## Website Messaging Updates

File: `Au-docs/venture-augur/website-working/index.html`

The website currently describes the old monolithic RAG system. Three areas need updating to reflect the three-tier architecture and the Karpathy wiki pattern.

### 1. Comparison Table Row (line ~838)

Current:
```
RAG / search | Basic AI search | Plugin-dependent | Per-project file context... | BM25 + ripgrep hybrid, content-aware chunking
```

Updated:
```
RAG / search | Basic AI search | Plugin-dependent | Per-project file context. No unified index across all your documents. | Three-tier: ripgrep for code, BM25 for documents, LLM Wiki for compiled knowledge
```

### 2. Knowledge Philosophy Row (line ~800)

Current messaging is already strong -- keep as-is:
```
AI creates, you curate. Knowledge compounds across every conversation.
```

But now this is actually true via the wiki tier. The "compounds across every conversation" claim was aspirational before -- with the wiki, it's the real mechanism: session learnings flow into wiki pages that the next session reads.

### 3. Knowledge Section (line ~752)

Current:
```
Obsidian and Notion assume you write your notes. Augur assumes AI writes them —
and you curate. Your AI clients compile knowledge from conversations, research,
and workflows into markdown files.
```

Add after this paragraph:
```
Under the hood, Augur maintains a living wiki — inspired by Karpathy's LLM Wiki
pattern. Every conversation distills what was learned into interlinked wiki pages
stored in your vault. Cross-references are pre-built, contradictions flagged,
synthesis already done. The next AI session starts where the last one left off —
regardless of which client you use.
```

### 4. Architecture Tag (line ~953)

Current:
```
<span class="arch-tag">Plain text RAG</span>
```

Updated:
```
<span class="arch-tag">LLM Wiki + document search</span>
```

### 5. Skills Description (line ~1003)

Current:
```
RAG indexes connect everything. Browse, search, and install from the dashboard or CLI.
```

Updated:
```
A living wiki compiles your knowledge. Documents are searchable via BM25.
Browse, search, and install from the dashboard or CLI.
```

### 6. FAQ (line ~1190)

Current:
```
Augur is personal AI infrastructure that runs on your PC. It connects your notes,
code, memory, skills, and workflows into one system...
```

No change needed -- this framing still works. The wiki is an implementation detail under "memory".

### Open Questions for Phase 2

1. How much of the Karpathy schema prompt to adapt vs use verbatim?
2. Should wiki seeding (initial build from 500+ ADRs) be a one-time batch or incremental?
3. How to handle wiki page staleness when source ADRs change but no conversation triggers an update?
4. Where does the schema prompt live -- CLAUDE.md, a skill, or wiki/schema.md itself?
5. Should per-client memory entries be auto-promoted to wiki pages when they reach a maturity threshold?
