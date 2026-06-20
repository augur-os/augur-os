---
status: Implemented
date: '2026-02-02'
deciders:
- Core team
related: []
hub: null
tags:
- rag
- search
- hardening
- security
- staleness
superseded_by: null
---

# ADR-033: RAG Search Hardening — Security, Staleness, Dedup, and Iterative Retrieval

## Context

The Augur RAG system (ADR-004) adopted a Markdown-first, ripgrep-based approach over vector databases. This was the right call — it aligns with Claude Code's own architecture, which also avoids embeddings in favor of iterative grep. However, comparison with Claude Code's approach reveals five concrete flaws in the current `MemorySearcher` implementation that undermine the benefits of the design.

### Flaw 1: `eval()` for JSON parsing (Security)

`plugins/ai/skills/knowledge/augur/memory/search.py:146` uses Python `eval()` with string replacements (`null` → `None`, etc.) to parse ripgrep's `--json` output. This is a code execution vulnerability — any ripgrep match containing Python-valid syntax (e.g., `__import__('os').system('rm -rf /')`) could execute arbitrary code. The fix is trivial: `json.loads()`.

### Flaw 2: Index staleness not detected

`MemorySearcher.build_index()` rebuilds the entire `index.yaml` from scratch every invocation. The config declares `incremental: true` and `auto_rebuild_hours: 24` (`data/knowledge/config.yaml:19-20`) but neither is implemented. The YAML index can silently drift from the actual memory files if someone edits `MEMORY.md` or daily logs without triggering a rebuild. Claude Code avoids this by having no persistent index at all.

### Flaw 3: Hybrid dedup uses raw paths

In `search()` (line 442-449), deduplication keys on `(file_path, line_number)`. But ripgrep returns absolute paths while the YAML index stores paths as set during `build_index()` — potentially relative or with different prefix normalization. Identical results from both sources can appear as duplicates with different relevance scores.

### Flaw 4: Static relevance heuristics

`_calculate_relevance()` (lines 541-559) uses string overlap ratios to score results. This misses the key insight from Claude Code: the LLM itself is the ranking function. Claude Code greps, reads results, decides if it has enough context, and greps again with refined terms. The `rag_reasoning_cli.py` already demonstrates this pattern via a local LLM but it's a disconnected CLI tool, not integrated into the core `MemorySearcher` loop.

### Flaw 5: Search scope limited to memory

`MemorySearcher` only searches `data/core/memory/`. RAG projects live in `plugins/ai/skills/knowledge/data/rag/`. Skill documentation lives in `plugins/`. Knowledge base content lives across `data/`. There is no single search entry point that spans all knowledge sources, unlike Claude Code which searches the entire repository from any query.

### What happens if we do nothing

- The `eval()` vulnerability persists in a tool that processes arbitrary file content
- Index drift causes silent search quality degradation over time
- Hybrid mode returns duplicate results, confusing both users and LLM consumers
- Static scoring returns results ranked by string overlap rather than semantic relevance
- Users must know which search tool to use for which data source

## Decision

### Component 1: Secure JSON Parsing

Replace `eval()` with `json.loads()` in `_ripgrep_search()`.

**File**: `plugins/ai/skills/knowledge/augur/memory/search.py`

**Change**: Lines 142-158

```python
# Before (INSECURE)
data = eval(line.replace("null", "None").replace("true", "True").replace("false", "False"))

# After (SECURE)
import json
data = json.loads(line)
```

No behavioral change. The ripgrep `--json` flag outputs valid JSON; the `eval()` approach was never necessary.

### Component 2: Index Staleness Detection

Add file-level checksums to `index.yaml` so `build_index()` can skip unchanged files. Implement the `incremental` and `auto_rebuild_hours` config flags that are already declared but not wired.

**File**: `plugins/ai/skills/knowledge/augur/memory/search.py`

**New index schema**:
```yaml
version: "2.0"
updated: ISO_TIMESTAMP
entry_count: N
file_checksums:
  "data/core/memory/MEMORY.md": "sha256:abc123..."
  "data/core/memory/daily/2026-02-01.md": "sha256:def456..."
entries:
  - key: string
    content: string
    # ... existing fields
```

**Logic**:
1. On `build_index()`, compute SHA256 of each source file
2. Compare against stored checksums in existing `index.yaml`
3. Only re-parse files whose checksum changed
4. Merge new entries with existing unchanged entries
5. Record last rebuild timestamp
6. On `search()` in HYBRID/METADATA mode, check if `updated` timestamp is older than `auto_rebuild_hours` from config and trigger rebuild if stale

**New method**: `_is_index_stale() -> bool`
- Returns `True` if any source file checksum differs from stored checksum
- Returns `True` if `updated` is older than `auto_rebuild_hours`

**New method**: `_compute_file_checksum(path: Path) -> str`
- Returns `sha256:{hex_digest}` for a file

### Component 3: Path-Normalized Deduplication

Normalize all file paths to absolute, resolved form before using them as dedup keys.

**File**: `plugins/ai/skills/knowledge/augur/memory/search.py`

**Changes to `search()` (around line 442)**:

```python
# Before
key = (r.file_path, r.line_number)

# After
key = (str(Path(r.file_path).resolve()) if r.file_path else None, r.line_number)
```

Also normalize paths in `_ripgrep_search()` output and `_search_index()` output so both sources produce consistent absolute paths.

### Component 4: Iterative Search with LLM Ranking via AI Bridge

Add an `ITERATIVE` search mode that implements the Claude Code pattern: grep → evaluate → refine → grep again. LLM calls route through the **AI bridge** (`plugins/ai/skills/ai_bridge/augur/`) using the user's configured profile from `data/llm.yaml`, consistent with every other LLM interaction in Augur.

**Files modified**:
- `plugins/ai/skills/knowledge/augur/memory/search.py` — New search mode + LLM integration
- `data/knowledge/config.yaml` — Config for iterative search (references AI bridge, not a hardcoded model)

**New SearchMode**:
```python
class SearchMode(Enum):
    KEYWORD = "keyword"
    METADATA = "metadata"
    HYBRID = "hybrid"
    ITERATIVE = "iterative"  # NEW: LLM-in-the-loop via AI bridge
```

**LLM client initialization** — Uses the standard AI bridge pattern:
```python
def _get_llm_client(self) -> LLMClient | None:
    """
    Create an LLM client via the AI bridge, respecting user's llm.yaml config.

    Uses the same pattern as all other Augur LLM consumers:
    1. load_llm_config() reads data/llm.yaml (or AUGUR_LLM_* env vars)
    2. resolve_llm_profile() resolves based on task/context/active_profile
    3. create_llm_client() returns the appropriate client type

    The task "iterative_search" can be mapped to a specific profile in llm.yaml:
        tasks:
          iterative_search: local    # or openai, router, etc.
    """
    try:
        from plugins.services.skills.ai_bridge.lib import (
            load_llm_config,
            resolve_llm_profile,
            create_llm_client,
        )

        config = load_llm_config()
        profile = resolve_llm_profile(
            config,
            task="iterative_search",
            context="services/knowledge",
        )
        return create_llm_client(profile)
    except Exception as e:
        logger.warning(f"AI bridge unavailable for iterative search: {e}")
        return None
```

This means:
- If `data/llm.yaml` has `active_profile: local` pointing to Ollama → uses Ollama
- If user sets `tasks: { iterative_search: openai }` → uses OpenAI for search, local for everything else
- If user has `overrides: { components: { "services/knowledge": { active_profile: router } } }` → uses the router profile
- If AI bridge is not installed or no profiles configured → falls back to static `_calculate_relevance()`
- Works with all provider types: `openai_compatible`, `command`, `agentic_ide`

**New method**: `_iterative_search(query, max_rounds=3, top_k=5) -> list[SearchResult]`

```python
def _iterative_search(self, query: str, max_rounds: int = 3, top_k: int = 5) -> list[SearchResult]:
    """
    Claude Code-style iterative search:
    1. Grep with initial query
    2. Ask LLM (via AI bridge) if results are sufficient
    3. If not, LLM suggests refined query
    4. Repeat up to max_rounds
    5. Fall back to static scoring if AI bridge unavailable
    """
    client = self._get_llm_client()
    if client is None:
        logger.info("AI bridge unavailable, falling back to HYBRID mode")
        return self.search(query, mode=SearchMode.HYBRID, top_k=top_k)

    all_results = []
    current_query = query

    for round_num in range(max_rounds):
        # Step 1: Ripgrep search
        rg_results = self._ripgrep_search(current_query, self._search_root)
        round_results = self._convert_rg_to_search_results(rg_results)
        all_results.extend(round_results)

        # Step 2: Ask LLM if we have enough context
        evaluation = self._evaluate_results(client, query, round_results)

        if evaluation.sufficient:
            break

        # Step 3: Refine query based on LLM feedback
        current_query = evaluation.refined_query

    # Step 4: LLM ranks final results
    return self._rank_results(client, query, all_results, top_k)
```

**LLM interaction methods** — Use `client.generate_json()` from AI bridge:

```python
def _evaluate_results(
    self, client: LLMClient, original_query: str, results: list[SearchResult]
) -> SearchEvaluation:
    """Ask the LLM whether current results answer the query."""
    results_text = "\n".join(f"- {r.content}" for r in results[:20])

    response = client.generate_json(
        system="You evaluate search results for relevance. Return JSON.",
        prompt=(
            f"Original query: {original_query}\n\n"
            f"Search results:\n{results_text}\n\n"
            "Do these results sufficiently answer the query? "
            "Return JSON: {\"sufficient\": bool, \"refined_query\": \"...\", \"reasoning\": \"...\"}\n"
            "If not sufficient, refined_query should be a better ripgrep regex pattern."
        ),
        temperature=0.1,
        max_tokens=200,
    )

    return SearchEvaluation(
        sufficient=response.get("sufficient", True),
        refined_query=response.get("refined_query", original_query),
        reasoning=response.get("reasoning", ""),
    )

def _rank_results(
    self, client: LLMClient, query: str, results: list[SearchResult], top_k: int
) -> list[SearchResult]:
    """Ask the LLM to rank results by relevance."""
    if not results:
        return []

    indexed = [{"idx": i, "content": r.content[:200]} for i, r in enumerate(results[:30])]

    response = client.generate_json(
        system="You rank search results by relevance. Return JSON.",
        prompt=(
            f"Query: {query}\n\n"
            f"Results: {json.dumps(indexed)}\n\n"
            "Return JSON: {\"ranked_indices\": [idx, idx, ...]} "
            "ordered by relevance (most relevant first). Include at most {top_k} indices."
        ),
        temperature=0.1,
        max_tokens=200,
    )

    ranked_indices = response.get("ranked_indices", list(range(min(top_k, len(results)))))
    ranked = []
    for i, idx in enumerate(ranked_indices[:top_k]):
        if 0 <= idx < len(results):
            result = results[idx]
            # LLM rank position becomes the relevance score (1.0 for first, decreasing)
            result = SearchResult(
                content=result.content,
                source=result.source,
                category=result.category,
                date=result.date,
                relevance=1.0 - (i / top_k),
                file_path=result.file_path,
                line_number=result.line_number,
                context=result.context,
            )
            ranked.append(result)
    return ranked
```

**New dataclasses**:
```python
@dataclass
class SearchEvaluation:
    sufficient: bool
    refined_query: str
    reasoning: str
```

**Config integration** (`data/knowledge/config.yaml`):

The iterative search config no longer specifies a model — it defers to the AI bridge:
```yaml
advanced:
  vector_search:
    enabled: false
  iterative_search:
    enabled: true
    max_rounds: 3
    fallback_to_static: true
```

The user controls which model/provider is used via their existing `data/llm.yaml`:
```yaml
# Example: Route iterative search to a specific profile
active_profile: local

profiles:
  local:
    provider: openai_compatible
    base_url: http://localhost:11434/v1
    model: llama3.2
    timeout_s: 60

  openai:
    provider: openai_compatible
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
    model: gpt-4o-mini

# Optional: Route iterative_search to a specific profile
tasks:
  iterative_search: local      # Use local Ollama for search evaluation
  # iterative_search: openai   # Or use OpenAI for better quality
```

If no `tasks.iterative_search` mapping exists, resolution falls through to `active_profile` → `env` → `default` per the standard AI bridge priority chain (`resolve_llm_profile()` in `plugins/ai/skills/ai_bridge/augur/config.py:196-264`).

### Component 5: Unified Search Scope

Extend `MemorySearcher` to accept a configurable search root that can span multiple directories. Add a new `UnifiedSearcher` class that wraps `MemorySearcher` and RAG project search into one entry point.

**New file**: `plugins/ai/skills/knowledge/augur/memory/unified_search.py`

```python
class UnifiedSearcher:
    """
    Single entry point for searching across all Augur knowledge sources.

    Scopes:
    - memory: data/core/memory/ (daily logs, MEMORY.md)
    - knowledge: data/knowledge/ (indexed knowledge base)
    - skills: plugins/*/skills/*/SKILL.md (skill documentation)
    - rag: plugins/ai/skills/knowledge/data/rag/projects/*/  (RAG project content)
    """

    def __init__(self, scopes: list[str] | None = None):
        """
        Args:
            scopes: List of scopes to search. Default: all.
                    Options: "memory", "knowledge", "skills", "rag"
        """
        ...

    def search(self, query: str, scopes: list[str] | None = None, **kwargs) -> list[SearchResult]:
        """Search across configured scopes."""
        ...
```

**MCP tool update**: Add `scope` parameter to `memory-search` tool or add a new `unified-search` MCP tool.

**New MCP tool**:
```python
@mcp.tool(name="unified-search")
async def unified_search_tool(
    query: str,
    scopes: list[str] | None = None,
    mode: str = "hybrid",
    top_k: int = 10,
) -> str:
    """Search across all Augur knowledge sources.

    Args:
        query: Search query (supports regex)
        scopes: Sources to search (memory, knowledge, skills, rag). Default: all.
        mode: Search mode (keyword, metadata, hybrid, iterative)
        top_k: Maximum results
    """
```

### Directory Structure

```
plugins/ai/skills/knowledge/augur/memory/
├── __init__.py                  # Existing (export UnifiedSearcher)
├── search.py                    # MODIFIED: Components 1-4
├── unified_search.py            # NEW: Component 5
├── memory_store.py              # Existing (unchanged)
├── daily_logger.py              # Existing (unchanged)
└── curator.py                   # Existing (unchanged)
```

### Component Responsibility Map

| Component | File | Responsibility |
|-----------|------|----------------|
| JSON fix | `search.py:_ripgrep_search()` | Secure parsing of ripgrep output |
| Staleness detection | `search.py:build_index()`, `_is_index_stale()` | Incremental index with checksums |
| Path normalization | `search.py:search()` | Consistent dedup across sources |
| Iterative search | `search.py:_iterative_search()` | LLM-in-the-loop retrieval |
| Unified search | `unified_search.py:UnifiedSearcher` | Cross-scope search entry point |

### Implementation Order

Components 1-3 are independent bug fixes with no dependencies. Component 4 depends on the `_ripgrep_search` fix (Component 1). Component 5 depends on all others.

1. **Component 1**: JSON fix (standalone, zero risk)
2. **Component 2**: Staleness detection (standalone)
3. **Component 3**: Path normalization (standalone)
4. **Component 4**: Iterative search (after Component 1)
5. **Component 5**: Unified search (after Components 1-4)

## Testing & Verification

### Unit Tests

**File**: `plugins/ai/skills/knowledge/tests/test_search_hardening.py`

#### Component 1: Secure JSON Parsing

| Test | Expected Result |
|------|-----------------|
| `test_ripgrep_json_parsing_valid_output` | Parses standard ripgrep JSON matches correctly |
| `test_ripgrep_json_parsing_null_fields` | Handles JSON `null` values without error |
| `test_ripgrep_json_parsing_empty_output` | Returns empty list for empty ripgrep output |
| `test_ripgrep_json_parsing_malformed_line` | Skips malformed lines, continues parsing valid ones |
| `test_ripgrep_json_parsing_no_eval_execution` | Content containing `__import__` is treated as data, not code |
| `test_ripgrep_json_parsing_unicode_content` | Handles Unicode/multilingual and emoji content in match lines |

#### Component 2: Index Staleness Detection

| Test | Expected Result |
|------|-----------------|
| `test_build_index_creates_file_checksums` | `index.yaml` contains `file_checksums` section with SHA256 per file |
| `test_incremental_build_skips_unchanged_files` | Second build with no changes parses zero files |
| `test_incremental_build_reindexes_changed_file` | Modifying one daily log only re-parses that file |
| `test_is_index_stale_detects_new_file` | Returns `True` when a new daily log exists not in checksums |
| `test_is_index_stale_detects_modified_file` | Returns `True` when file checksum differs |
| `test_is_index_stale_detects_deleted_file` | Returns `True` when indexed file no longer exists |
| `test_is_index_stale_respects_auto_rebuild_hours` | Returns `True` when `updated` is older than configured threshold |
| `test_compute_file_checksum_consistency` | Same file content always produces same checksum |
| `test_search_triggers_rebuild_when_stale` | HYBRID search auto-rebuilds when `_is_index_stale()` returns True |

#### Component 3: Path-Normalized Deduplication

| Test | Expected Result |
|------|-----------------|
| `test_dedup_absolute_vs_relative_paths` | Same file matched via ripgrep (absolute) and index (relative) deduplicates to one result |
| `test_dedup_preserves_higher_relevance` | When duplicates exist, the one with higher relevance score is kept |
| `test_dedup_different_line_numbers_kept` | Same file, different lines are not deduped |
| `test_path_normalization_symlinks` | Symlinked paths resolve to canonical path for dedup |
| `test_dedup_none_file_path_handled` | Results with `None` file_path don't cause KeyError |

#### Component 4: Iterative Search via AI Bridge

| Test | Expected Result |
|------|-----------------|
| `test_iterative_search_single_round_sufficient` | LLM (via mocked AI bridge client) says results are sufficient after round 1, returns immediately |
| `test_iterative_search_refines_query` | LLM provides refined query, second round uses it |
| `test_iterative_search_max_rounds_respected` | Stops after `max_rounds` even if LLM says insufficient |
| `test_iterative_search_fallback_when_bridge_unavailable` | Falls back to HYBRID mode with static `_calculate_relevance()` when AI bridge import fails |
| `test_iterative_search_fallback_when_client_errors` | Falls back to HYBRID mode when `generate_json()` raises RuntimeError |
| `test_iterative_search_accumulates_results` | Results from all rounds are merged and deduplicated |
| `test_iterative_search_config_from_yaml` | Reads `max_rounds` from `data/knowledge/config.yaml` (model comes from AI bridge, not this config) |
| `test_iterative_search_uses_ai_bridge_profile` | `_get_llm_client()` calls `load_llm_config()` → `resolve_llm_profile(task="iterative_search")` → `create_llm_client()` |
| `test_iterative_search_respects_task_mapping` | When `llm.yaml` has `tasks.iterative_search: openai`, the openai profile is used |
| `test_iterative_search_respects_context_override` | When `llm.yaml` has `overrides.components."services/knowledge"`, that profile is used |

#### Component 5: Unified Search

| Test | Expected Result |
|------|-----------------|
| `test_unified_search_all_scopes` | Default search returns results from memory, knowledge, skills, and rag |
| `test_unified_search_single_scope` | `scopes=["memory"]` only returns memory results |
| `test_unified_search_multiple_scopes` | `scopes=["memory", "skills"]` searches both but not others |
| `test_unified_search_invalid_scope` | Raises `ValueError` for unknown scope name |
| `test_unified_search_empty_results` | Returns empty list when no matches across all scopes |
| `test_unified_search_dedup_across_scopes` | Same file found in two scopes is deduplicated |
| `test_unified_search_mcp_tool_integration` | `unified-search` MCP tool calls `UnifiedSearcher.search()` correctly |

### Use Cases

**UC-1: Security — Malicious Content in Indexed Files**
1. Create a daily log file containing the text `__import__('os').system('echo pwned')`
2. Run `memory-search` with a query matching that file
3. **Verify**: Search returns the content as a string result, no code execution occurs
4. **Verify**: `json.loads()` is used in `_ripgrep_search()`, not `eval()`

**UC-2: Incremental Index Rebuild**
1. Build index with 10 daily logs and MEMORY.md (11 files total)
2. Record index build time
3. Add one new daily log, modify MEMORY.md
4. Rebuild index
5. **Verify**: Only 2 files are re-parsed (new log + modified MEMORY.md)
6. **Verify**: 9 unchanged files retain their existing index entries
7. **Verify**: `file_checksums` in `index.yaml` includes all 12 files

**UC-3: Hybrid Search Dedup**
1. Write a decision to MEMORY.md: `"- **RAG Strategy**: Use ripgrep over vector DB"`
2. Build the index (so the entry exists in `index.yaml`)
3. Run `memory-search` with query `"RAG Strategy"` in `hybrid` mode
4. **Verify**: Exactly 1 result returned (not 2 duplicates from ripgrep + index)
5. **Verify**: The result has the highest relevance score from either source

**UC-4: Iterative Search Refinement via AI Bridge**
1. Configure `iterative_search.enabled: true` in `data/knowledge/config.yaml`
2. Ensure `data/llm.yaml` has a working profile (e.g., `active_profile: local` pointing to Ollama)
3. Run `memory-search` with mode `iterative` and query `"what database should I use"`
4. Round 1: ripgrep finds no exact match for "what database should I use"
5. LLM (resolved via AI bridge `resolve_llm_profile(task="iterative_search")`) evaluates: insufficient results, suggests refined query `"database|DB|storage|persistence"`
6. Round 2: ripgrep finds matches for `database`, `DB`, etc.
7. LLM evaluates: sufficient
8. **Verify**: Final results include matches from round 2 ranked by LLM
9. **Verify**: LLM calls went through the AI bridge client, not a hardcoded HTTP call

**UC-4b: Iterative Search with Task-Specific Profile**
1. Configure `data/llm.yaml` with `tasks: { iterative_search: openai }` and `active_profile: local`
2. Run `memory-search` with mode `iterative`
3. **Verify**: The LLM calls use the `openai` profile (not the `local` active profile)
4. **Verify**: Usage tracking (if enabled) records the request under the `openai` provider

**UC-4c: Iterative Search Graceful Fallback**
1. Remove or misconfigure `data/llm.yaml` (no valid profiles)
2. Run `memory-search` with mode `iterative` and query `"PostgreSQL"`
3. **Verify**: Search completes without error, using HYBRID mode fallback
4. **Verify**: Warning logged: "AI bridge unavailable for iterative search"

**UC-5: Unified Cross-Scope Search**
1. Add a decision to memory: `"Use PostgreSQL for analytics"`
2. Create a skill SKILL.md containing `"Supports PostgreSQL and SQLite"`
3. Run `unified-search` with query `"PostgreSQL"`
4. **Verify**: Results include both the memory decision and the skill documentation
5. **Verify**: Results are sorted by relevance across scopes
6. **Verify**: Each result includes its scope label (memory, skills)

**UC-6: Stale Index Auto-Rebuild**
1. Build index at time T
2. Set `auto_rebuild_hours: 0` in config (force immediate staleness)
3. Add a new daily log
4. Run `memory-search` in `hybrid` mode
5. **Verify**: Search triggers automatic index rebuild before returning results
6. **Verify**: New daily log content appears in results

## Consequences

### Positive

- **Security**: Eliminates arbitrary code execution via `eval()` — zero-cost fix
- **Search quality**: Incremental indexing keeps index fresh without full rebuilds
- **Correctness**: Path normalization eliminates phantom duplicates in hybrid mode
- **Relevance**: LLM-in-the-loop ranking matches Claude Code's proven approach, routed through AI bridge so user controls provider/model via `data/llm.yaml`
- **Consistency**: Iterative search follows the same `load_llm_config()` → `resolve_llm_profile()` → `create_llm_client()` pattern as all other Augur LLM consumers (executor, mcp-app-factory, developer, etc.)
- **Usability**: Unified search removes the need to know which tool searches which data
- **Performance**: Incremental indexing avoids re-parsing unchanged files (currently ~54K files)

### Negative

- **Component 4 complexity**: Iterative search depends on the AI bridge (`plugins/ai/skills/ai_bridge/augur/`). If the ai-bridge skill is not installed, iterative mode falls back to HYBRID. No new LLM dependencies are introduced — it uses whatever the user has already configured in `data/llm.yaml`
- **Component 5 scope**: Unified search across `plugins/` could be slow on large plugin sets. Mitigated by scope filtering
- **Index schema change**: `index.yaml` v2.0 with `file_checksums` is not backward-compatible with v1.0. First build after upgrade will do a full rebuild
- **New test surface**: ~30 new tests to maintain

### Migration

1. **`search.py` line 146**: Replace `eval()` with `json.loads()` — no data migration needed
2. **`index.yaml`**: First `build_index()` call after upgrade will detect missing `file_checksums` and do a full rebuild, writing v2.0 format. No manual migration.
3. **`data/knowledge/config.yaml`**: Add `iterative_search` section under `advanced` with `enabled` and `max_rounds` only. No `model` field — model selection is delegated to the AI bridge via `data/llm.yaml`. Defaults to `enabled: false` so no behavior change until explicitly opted in.
3b. **`data/llm.yaml`** (optional): Users can add a `tasks.iterative_search` mapping to route search LLM calls to a specific profile. If omitted, the active profile is used. No migration needed — existing `llm.yaml` files work as-is.
4. **MCP tool registration**: Add `unified-search` tool in `plugins/ai/skills/knowledge/augur/__init__.py`. Existing `memory-search` tool unchanged.
5. **`plugins/ai/skills/knowledge/augur/memory/__init__.py`**: Export `UnifiedSearcher` alongside existing exports.

## Alternatives Considered

### Alternative 1: Remove the YAML Index Entirely (Claude Code Approach)

Drop `index.yaml` and rely solely on ripgrep for every query. This eliminates staleness entirely.

**Rejected because**: The YAML index enables structured metadata queries (filter by category, date range, source) that pure ripgrep cannot do. The index serves a different purpose than Claude Code's use case — Claude Code searches code, we search structured memory with metadata dimensions.

### Alternative 2: Use SQLite Instead of YAML Index

Replace `index.yaml` with a SQLite database for faster structured queries and built-in FTS5.

**Rejected because**: Violates ADR-004's "zero infrastructure" principle. YAML files are human-readable, git-trackable, and portable. SQLite adds a binary dependency and opaque storage.

### Alternative 3: Hardcode LLM Model in Knowledge Config

Put `model: llama3.2` directly in `data/knowledge/config.yaml` and make HTTP calls to `localhost:11434` from `search.py`, bypassing the AI bridge. This is what `rag_reasoning_cli.py` currently does.

**Rejected because**: Violates the AI bridge pattern (ADR-030). Every other LLM consumer in Augur uses `load_llm_config()` → `resolve_llm_profile()` → `create_llm_client()`. Hardcoding the model means:
- User can't switch providers without editing knowledge config
- No usage tracking via the AI bridge's `UsageTracker`
- No support for `tasks` mapping or `overrides` in `llm.yaml`
- Duplicated HTTP client code instead of reusing `OpenAICompatibleClient`
- The existing `rag_reasoning_cli.py` should also be migrated to AI bridge in a follow-up

### Alternative 4: Use Embeddings for Relevance Ranking Instead of LLM-in-the-Loop

Generate local embeddings (sentence-transformers) for relevance scoring instead of calling a local LLM.

**Rejected because**: This reintroduces the staleness and RAM concerns from ADR-004. The LLM-in-the-loop approach uses the model only at query time (no persistent index to maintain) and falls back gracefully when unavailable.

## References

- [ADR-004](./ADR-004-markdown-rag.md) — Markdown RAG over Vector Databases
- [ADR-006](./ADR-006-local-first.md) — Local-first architecture
- [ADR-028](./ADR-028-two-layer-memory-architecture.md) — Two-Layer Memory Architecture
- [ADR-030](./ADR-030-unified-ai-bridge-context-algorithm.md) — Unified AI Bridge Context Algorithm
- `plugins/ai/skills/knowledge/augur/memory/search.py` — Current MemorySearcher
- `plugins/ai/skills/knowledge/scripts/rag_reasoning_cli.py` — Existing LLM search CLI (to be migrated to AI bridge)
- `plugins/ai/skills/ai_bridge/augur/config.py` — `load_llm_config()`, `resolve_llm_profile()`
- `plugins/ai/skills/ai_bridge/augur/client.py` — `create_llm_client()`, `LLMClient` base class
- `plugins/ai/skills/ai_bridge/llm.yaml.example` — Example LLM profile configuration
- `data/knowledge/config.yaml` — RAG configuration
- Claude Code architecture analysis (iterative grep over embeddings)
