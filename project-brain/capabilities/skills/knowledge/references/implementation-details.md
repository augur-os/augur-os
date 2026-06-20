# Knowledge Implementation Details

## Implemented Capabilities

1. **Unified Search (memory + docs + project)**
   - API: `/api/knowledge/search` (MCP-backed `unified-search`)
   - API: `/api/knowledge/memory/search` (MCP-backed `memory-search`)
   - API: `/api/knowledge/project-index/search` (project index lookup)
2. **Memory Curation**
   - API: `/api/knowledge/memory/curate` (MCP-backed `memory-curate`)
3. **Project Index Rebuild**
   - API: `/api/knowledge/project-index/rebuild` (MCP-backed `knowledge-project-index-rebuild`)
4. **Memory Index Rebuild**
   - Action-backed MCP tool: `memory-rebuild-index`
5. **OCR Ingestion (Beta)**
   - Page is available for workflow exploration
   - API currently returns beta response until backend extraction is fully wired

## Dashboard Pages

- `/browse?view=wiki`: semantic search UI with memory/doc/project sections
- `/workspace/memory`: memory stats, curation, profile, daily logs
- `/workspace/insights`: index status and project index controls
- `/browse?view=documents`: linked external files
- `/workspace/inbox`: OCR upload UI (explicit beta)

## Action Map (Current)

| Action | Dispatch | Backend |
|---|---|---|
| `curate-memory` | `fire` | MCP tool `memory-curate` |
| `reindex-all` | `fire` | MCP tool `knowledge-project-index-rebuild` |
| `refresh-graph` | `fire` | MCP tool `memory-rebuild-index` |
| `smart-search` | `oneshot` | IDE agents (`advisor`, `developer`) |
| `analyze-knowledge-gaps` | `oneshot` | IDE agents (`advisor`, `validator`) |
| `ocr-scan` | `modal` | `/api/knowledge/ocr` (beta response today) |

## Core User Journeys

### 1. Find Past Decisions
1. Open `/browse?view=wiki`
2. Enter query
3. Review memory + docs + project sections
4. Open cited files or navigate to relevant page

### 2. Curate Memory Weekly
1. Open `/workspace/memory`
2. Run **Curate Memory**
3. Validate updated stats and recent decisions

### 3. Rebuild Index After Large Changes
1. Open `/workspace/insights`
2. Run **Rebuild Project Index**
3. Re-run a search query to confirm new content appears

## Architecture Constraints

1. **MCP-first API routes**: dashboard routes must call MCP tools, not direct Python execution.
2. **Plugin-local ownership**: actions, APIs, pages, and MCP tools live in this plugin.
3. **No direct LLM in dashboard**: AI execution must use IDE dispatch modes (`oneshot`/`ide`) and MCP-mediated context.
4. **Explicit beta labeling**: non-production OCR behavior must remain clearly marked in UI and API.

## Data Inputs

- `get_memory_dir()/MEMORY.md`
- `get_memory_dir()/daily/*.md`
- `~/Library/Application Support/Augur/rag/project-index.yaml`
- linked files managed through `/api/knowledge/hub-files`
