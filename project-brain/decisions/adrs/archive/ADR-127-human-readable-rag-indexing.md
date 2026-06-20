---
status: Implemented
date: '2026-02-20'
deciders:
- Core team
related:
- ADR-004
- ADR-033
- ADR-085
- ADR-126
hub: null
tags:
- human
- readable
- plugin
- specific
- rag
superseded_by: null
---

# ADR-127: Human-Readable, Plugin-Specific RAG Indexing via Hierarchical Markdown and Symbol Extraction

## Context

Augur's current RAG system executes searches across markdown and YAML indices using `ripgrep`, completely avoiding binary vector databases to strictly follow the Unix Philosophy (ADR-004, ADR-085). We recently enhanced this with Claude Code-like iterative search loops via the AI bridge (ADR-033). Furthermore, ADR-126 decentralizes RAG indexing so that every skill maintains its own isolated `augur/rag/` index to align with open, Claude-native skill standards.

However, iterating over large repositories or imported plugin knowledge with raw keyword search lacks structural geometry. As the amount of indexed projects and external files grows, full-text `ripgrep` queries can yield noisy results unless heavily refined. 

Drawing inspiration from Claude Code design patterns, we need to provide the iterative search loop with a "map" of the codebase or knowledge base before it dives into the contents. To maintain our commitment to human-readable text formats instead of binary embeddings, we must express codebase topology and semantic document chunking entirely in Markdown and YAML within each plugin's `augur/rag/` directory.

Crucially, the orchestrating logic for building these structures and performing the search will NOT be baked into the Augur core (`src/mcp/`). Instead, all RAG capabilities are encapsulated within a dedicated `rag` plugin (e.g., `plugins/ai/skills/rag/`). This ensures that users or organizations can completely swap out the RAG implementation (e.g., replacing `ripgrep` with a localized vector database or an external API) simply by replacing the RAG plugin, provided the new plugin adheres to the standard RAG MCP tool definitions.

## Decision

We will implement a Human-Readable RAG Indexing enhancement focusing on semantic mappings through simple text files:

### 1. Hierarchical Directory Summaries (`_index.md`)
Indexers will generate an `_index.md` file in each directory. This file will contain an LLM-generated summary (via AI Bridge) of the directory's purpose and a high-level list of its contents. Iterative searches can first scan these `_index.md` files to quickly zero in on relevant subtrees without grepping all raw files.

### 2. Code Symbol Extraction (`symbols.yaml`)
We will parse codebase files (Python, TypeScript) to extract critical symbols (classes, functions, interfaces, type definitions). We will store this signature mapping in a flat `symbols.yaml` file next to the source code. This creates an extremely fast "Go To Symbol" capability using raw text search.

### 3. Smart Markdown Chunking (`augur/rag/index/chunks/`)
Very large text documents parsing will produce semantic chunks saved individually to a `chunks/` subfolder within the skill's specific `augur/rag/index/` directory (e.g., `augur/rag/index/chunks/doc-part1.md`). Each chunk gets a YAML frontmatter header linking back to its original document. This guarantees that `ripgrep` matches always return right-sized context windows for LLM evaluations.

### 4. Search Loop Optimization
We will upgrade `UnifiedSearcher` to apply Claude's iterative pattern: 
1. Search `symbols.yaml` and `_index.md` first.
2. Evaluate which directories or files are likely to contain the answer. 
3. Execute targeted `ripgrep` commands strictly on those high-probability paths.

### 5. Dedicated RAG Plugin
In alignment with open standards (ADR-126) and the Unix philosophy of swappable components, RAG indexing logic is entirely encapsulated within a dedicated `rag` plugin (`plugins/ai/skills/rag/`). This plugin is responsible for exposing the standard `search-{skill}-knowledge` and indexing MCP tools. Because this is just a standard plugin, users can swap out this default ripgrep-based `rag` plugin for a completely different implementation (e.g., an external vector DB) as long as it exposes the same standard MCP tool interfaces.

## Consequences

**Positive**:
- Immensely improves RAG result precision for large codebases. 
- Fast "zooming" functionality for Claude Code-like iterative searches.
- No binary vector DBs; every index and chunk is directly readable and debuggable.
- Caching logic (via existing file checksums) ensures fast incremental reconstructs.

**Negative**:
- Initial indexing time increases due to AI-driven summarization for `_index.md`.
- Increased file count due to `_chunks/` directories (manageable with `.gitignore` and file exclusions).

**Neutral**:
- Modifies how `plugins/ai/skills/rag/scripts/rag_indexer.py` behaves, taking slightly longer on first runs.

## Implementation Order

Phase 1: Symbol Extraction
├── Step 1: Create `symbol_extractor.py` inside the `rag` plugin to parse `.py` and `.ts` files, generating `symbols.yaml`
└── Step 2: Integrate `symbols.yaml` lookup into the start of Iterative Search queries in `plugins/ai/skills/rag/mcp/rag_tools.py`

Phase 2: Directory Summarization
├── Step 3: Create `dir_summarizer.py` inside the `rag` plugin to request a concise summary via AI Bridge, writing `_index.md` inside `augur/rag/`
└── Step 4: Update indexing scripts (`plugins/ai/skills/rag/scripts/rag_indexer.py`) to orchestrate these summarizations.

Phase 3: Smart Chunking for External Docs
├── Step 5: Enhance `rag_indexer.py` inside the `rag` plugin to chunk large parsed documents into `augur/rag/index/chunks/`
└── Step 6: Ensure `rag_tools.py` inside the `rag` plugin normalizes chunk hit logic to reference the parent file accurately

Phase 4: Search Optimization and Verification
├── Step 7: Modify `rag_tools.py` so that Iterative mode specifically queries `_index.md` and `symbols.yaml` first
└── Step 8: Validate ripgrep limits and pipeline stability

## Alternatives Considered

### Alternative 1: Local Embeddings (Vector DB)
We could spin up a lightweight vector database or chunked embedding store (like ChromaDB or an FAISS index) instead of flat YAML files. **Rejected** because it heavily violates the Unix Philosophy and our local Markdown-native mandates, making debugging index states difficult without specialized tooling.

### Alternative 2: ctags / etags
We could use the classic `ctags` binary to generate code symbols. **Rejected** because its raw output format isn't easily human-readable compared to a cleanly formatted YAML list, and introduces a native binary dependency we prefer to avoid for simplicity.

## References

- ADR-004: Markdown RAG over Vector Databases
- ADR-033: RAG Search Hardening — Security, Staleness, Dedup, and Iterative Retrieval
- ADR-085: RAG Three-Tier Index
- ADR-126: Generic Plugin Template Refactor — Claude-Native Skill Standard

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-127: Human-Readable, Plugin-Specific RAG Indexing via Hierarchical Markdown and Symbol Extraction**.

Read the full ADR: `docs/decisions/ADR-127-human-readable-rag-indexing.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-127-rag-indexing", description="Implementing ADR-127: Human-Readable, Plugin-Specific RAG Indexing")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-127-rag-indexing", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-127-rag team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-127-rag-indexing`

#### Phase 1: Symbol Extraction
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create `symbol_extractor.py` to parse `.py` and `.ts` files using regex or ast to extract classes and functions. Generate a `symbols.yaml` in matching directories. | `plugins/ai/skills/rag/scripts/symbol_extractor.py` |
| 1.2 | developer | medium | Update `plugins/ai/skills/rag/mcp/rag_tools.py` Iterative Mode to preferentially grep `symbols.yaml` files before jumping into full-text matching for the `search-{skill}-knowledge` tool. | `plugins/ai/skills/rag/mcp/rag_tools.py` |

#### Phase 2: Directory Summarization
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create `dir_summarizer.py` that lists files in a directory and uses the AI Bridge LLM client to generate a concise summary of the directory's purpose, saved to `_index.md` in `augur/rag/`. | `plugins/ai/skills/rag/scripts/dir_summarizer.py` |
| 2.2 | developer | medium | Modify `plugins/ai/skills/rag/scripts/rag_indexer.py` so it calls `dir_summarizer.py` and `symbol_extractor.py` dynamically during the main caching run. Ensure file checksums skip unchanged directories. | `plugins/ai/skills/rag/scripts/rag_indexer.py` |

#### Phase 3: Smart Chunking for External Docs
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Modify `plugins/ai/skills/rag/scripts/rag_indexer.py` to add smart markdown chunking logic for large files. If a file is large, chunk it by headings into `augur/rag/index/chunks/` with backlinks in YAML frontmatter. | `plugins/ai/skills/rag/scripts/rag_indexer.py` |
| 3.2 | developer | medium | Enhance the SearchResult mappings in `plugins/ai/skills/rag/mcp/rag_tools.py` to correctly map chunk ripgrep hits back to their original parent document references. | `plugins/ai/skills/rag/mcp/rag_tools.py` |

#### Final Phase: Verification
**Strategy**: PIPELINE
**Agents**:
| Step | Agent | Tier | Task |
|------|-------|------|------|
| 4.1 | validator | low | Run tests in `plugins/ai/skills/rag/tests/` to verify structural integrity |
| 4.2 | architect | low | Verify ADR intent matches symbol extraction execution logic and aligns with ADR-126 open standards |
| 4.3 | devops | low | Run tests locally with a pilot skill to ensure it successfully generates `symbols.yaml` and `_index.md` inside `augur/rag/`. Run stale path scanner if applicable |

### Completion Criteria
- [ ] All phases executed
- [ ] `symbols.yaml` and `_index.md` files are properly created by the indexer
- [ ] Search correctly processes large external markdown files in chunks
- [ ] No orphaned files or broken references
- [ ] ADR status updated to "Accepted" or "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-127-human-readable-rag-indexing.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
