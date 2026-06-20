---
status: Implemented
date: 2026-04-02
deciders:
  - gsannikov
related:
  - ADR-137
  - ADR-521
  - ADR-525
hub: adaptive
tags:
  - llm
  - provider
  - airplane-mode
superseded_by: null
---

# ADR-528: Unified LLM Provider Abstraction

## Context

Five components bypassed the existing `LLMClient` abstraction in `skills/ai/augur/lib/` with hardcoded provider calls:

| Component | File | Hardcoded to |
|---|---|---|
| RAG Contextualizer | `skills/rag/scripts/contextualizer.py` | Ollama `localhost:11434` via `httpx.post` |
| Document Extractor | `skills/document-extractor/scripts/ollama_client.py` | Ollama via `openai.OpenAI()` |
| Action Evals | `skills/advisor/scripts/analytics/run_action_evals.py` | Anthropic SDK |
| LLM CLI | `src/lib/llm_cli.py` | `claude`/`ollama` subprocess |
| LLM Retry | `src/lib/llm_retry.py` | Own CLI resolution |

This meant:
- Airplane mode (local-only) required per-component handling instead of one toggle
- Swapping providers required editing multiple files with different config formats
- Vision and tool-use capabilities were locked to specific providers
- No unified usage tracking across components

Two components (RAG SearchEngine, Memory Iterative Search) already used the abstraction correctly via ADR-137.

## Decision

### 1. Extend `LLMClient` with vision and tools

Added `generate_with_vision(prompt, images, ...)` and `generate_with_tools(prompt, tools, ...)` to the `LLMClient` base class. `OpenAICompatibleClient` implements both using the standard OpenAI `/chat/completions` protocol — which Ollama, OpenAI, Groq, and other providers all support.

`CommandLLMClient` and `BridgedIdeClient` raise `NotImplementedError` (text-only).

### 2. Shared HTTP and tracking helpers

Extracted `_post_completion(payload)`, `_resolve_temperature(temperature)`, `_provider` property, and `_track_usage(model, ...)` on `OpenAICompatibleClient`. All three generate methods (`generate_text`, `generate_with_vision`, `generate_with_tools`) use the same HTTP transport and error handling.

### 3. Ollama via OpenAI-compatible endpoint only

All Ollama calls use `/v1/chat/completions` (not the native `/api/generate`). One protocol for all providers. Ollama-specific params like `num_predict` map to standard `max_tokens`.

### 4. Task-based profile routing via `llm.yaml`

Each component registers a task name. `resolve_llm_profile(config, task="contextualizer")` routes to the correct profile. Config lives in `config/system/llm.yaml`:

```yaml
profiles:
  local:
    provider: openai_compatible
    base_url: http://localhost:11434/v1
    model: qwen3.5:9b
  remote:
    provider: openai_compatible
    base_url: https://api.groq.com/openai/v1
    api_key_env: GROQ_API_KEY
    model: llama-3.3-70b
  vision-local:
    provider: openai_compatible
    base_url: http://localhost:11434/v1
    model: llava-llama3

tasks:
  contextualizer: local
  search_ranking: remote
  document_ocr: vision-local
  action_evals: remote
  file_summarization: local
  retry_diagnosis: local
```

### 5. `get_llm_client(task)` convenience function

One-liner replaces the 3-line `load_llm_config / resolve_llm_profile / create_llm_client` pattern. Exported from `skills.ai.augur.lib`.

### 6. Airplane mode at config layer

`_is_airplane_mode()` checks `AUGUR_AIRPLANE_MODE` env var and `preferences.yaml`. When active, `resolve_llm_profile` returns the `local` profile before task/context resolution. 30-second TTL cache prevents repeated YAML reads.

### 7. Component migrations

- **Contextualizer**: `httpx.post` → `client.generate_text()`, injectable client, circuit breaker preserved
- **Document Extractor**: `openai.OpenAI()` → `get_llm_client("document_ocr")`, caller uses `generate_with_vision()`
- **Action Evals**: `anthropic.Anthropic()` → `get_llm_client("action_evals")`, tools converted to OpenAI format
- **LLM CLI**: Deprecated and deleted. Callers use `get_llm_client(task)` directly
- **LLM Retry**: Stays subprocess-based (lightweight constraint), but resolves CLI from `llm.yaml` profiles first

### 8. Cleanup

- Removed `src/lib/llm_cli.py` and `tests/test_llm_cli.py`
- Removed dead `enterprise` provider type
- Fixed `BridgedIdeClient` unbound `filepath` and moved backup to `get_cache_dir()`
- Fixed usage tracker import path (`from lib.` → `from .`)
- Added 10k cache cap with FIFO eviction to Contextualizer
- Fixed O(N^2) summary parser in file-manager autoloop

## Consequences

### Positive

- Single config change (`active_profile` or airplane toggle) switches all components between local and remote
- Per-task routing allows mixing cheap local models for high-volume work with smarter remote models for ranking
- Vision and tool-use are provider-agnostic — swap Ollama for GPT-4o with one config line
- Unified usage tracking across all LLM calls
- 41 new tests covering all extensions and migrations

### Negative

- Temperature parameter changed from `float = 0.2` default to `float | None = None` — callers passing explicit `0.2` now get that value honored rather than the instance default (behavior change, more correct)
- `llm_cli.yaml` vault config is orphaned — callers that read it directly need migration

### Neutral

- The `CommandLLMClient` and `BridgedIdeClient` cannot support vision or tools — they raise `NotImplementedError`. This matches their nature (text-only transports).

## Alternatives Considered

### Alternative 1: Provider SDK Abstraction

Keep using native SDKs (`anthropic`, `openai`) but wrap them behind a factory. Each provider gets its own adapter class.

Rejected: Maintaining N SDK wrappers defeats the "one config change swaps everything" goal. Adding a new provider means writing a new adapter class instead of just adding a profile entry.

### Alternative 2: Ollama Native API

Keep using Ollama's `/api/generate` endpoint for features like `num_predict` and `think: false`.

Rejected: Requires maintaining two HTTP protocols (OpenAI + Ollama native). The features used (`num_predict` = `max_tokens`, `think: false` = don't request reasoning) map cleanly to the OpenAI protocol. One protocol is simpler.

### Alternative 3: Thin Convergence (No Interface Extension)

Route all generation through existing `generate_text`/`generate_json` only, without adding vision or tools methods.

Rejected: Document Extractor needs vision (image input) and Action Evals need tool-use — these don't fit the text-only interface without losing functionality.

## References

- [ADR-137: Eliminate Direct LLM Calls from Scripts](ADR-137-eliminate-direct-llm-calls.md) — established the LLMClient abstraction
- [ADR-521: Local Mode: Ollama Integration](ADR-521-local-mode-ollama-integration.md) — airplane mode design
- [ADR-525: Hybrid BM25 + Contextual Retrieval](ADR-525-hybrid-bm25-contextual-retrieval.md) — the contextualizer that was migrated
- Design spec: `docs/superpowers/specs/2026-04-02-unified-llm-provider-design.md`
- Implementation plan: `docs/superpowers/plans/2026-04-02-unified-llm-provider.md`

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "LLMClient.generate_text temperature default: float=0.2 → float|None=None"
    - "LLMClient gains generate_with_vision() and generate_with_tools()"
    - "skills.ai.augur.lib exports get_llm_client(task)"
  patterns_deprecated:
    - "Direct httpx/urllib calls to Ollama /api/generate"
    - "Direct anthropic.Anthropic() SDK usage for generation"
    - "Direct openai.OpenAI() SDK usage for generation"
    - "src.lib.llm_cli module (deleted)"
    - "ProviderType 'enterprise' (removed)"
  files_affected:
    - "skills/ai/augur/lib/client.py"
    - "skills/ai/augur/lib/config.py"
    - "skills/ai/augur/lib/__init__.py"
    - "skills/rag/scripts/contextualizer.py"
    - "skills/document-extractor/scripts/ollama_client.py"
    - "skills/advisor/scripts/analytics/run_action_evals.py"
    - "skills/file-manager/scripts/autoloop.py"
    - "src/lib/llm_retry.py"
    - "config/system/llm.yaml"
```

## Completion Criteria

- [x] All generation calls route through `LLMClient` subclasses
- [x] No file outside `skills/ai/augur/lib/` makes direct HTTP calls to any LLM endpoint
- [x] No file imports `anthropic` or `openai` SDKs for generation
- [x] `llm.yaml` is the single source of truth for provider configuration
- [x] Changing `active_profile` or toggling airplane mode switches all components
- [x] 41 tests pass covering all extensions and migrations
- [x] `src/lib/llm_cli.py` deleted with zero remaining references
