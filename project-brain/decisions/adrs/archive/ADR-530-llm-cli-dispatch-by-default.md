---
status: Implemented
date: 2026-04-02
deciders:
  - gsannikov
related:
  - ADR-137
  - ADR-528
  - ADR-521
hub: adaptive
tags:
  - llm
  - cli
  - dispatch
  - airplane-mode
superseded_by: null
---

# ADR-530: LLM CLI Dispatch by Default

## Context

ADR-528 unified all LLM generation calls through `LLMClient` with profile-based routing. However, the default dispatch method was HTTP (`OpenAICompatibleClient` calling Ollama or remote APIs). This created problems:

1. **Running inside Claude Code** — the user already has an LLM via `claude --print`, but the system ignored it and called Ollama over HTTP instead
2. **No Ollama available remotely** — when running Claude Code without `--local`, the `active_profile: local` config forced Ollama HTTP calls that failed silently
3. **Misalignment with MCP patterns** — other MCP tools detect the AI client context and use it; the LLM provider should do the same
4. **Thinking model incompatibility** — Qwen 3.5 via OpenAI-compatible endpoint can't disable thinking (`think: false` only works on Ollama's native `/api/generate`)

The `CommandLLMClient` (subprocess dispatch via `claude --print`, `codex exec`, `ollama run`) was already implemented but never used as the default.

## Decision

### 1. Auto-detect CLI at config load time

`load_llm_config()` detects the user's preferred CLI binary after reading `llm.yaml`:

1. Reads `external.preferred_cli` from `config/system/llm.yaml`
2. Falls back to `cli_agents.yaml` ordered list of known CLIs
3. Finds the first available via `shutil.which()`
4. Injects a synthetic `cli` profile with `provider: "command"` and the bare command string
5. Sets `active_profile = "cli"` if no explicit profile is configured in the file

Detection logic lives in `skills/ai/augur/lib/cli_detect.py` — extracted from `llm_retry.py`'s `resolve_cli()` into a shared, non-raising helper.

### 2. Bare command format per CLI

| CLI | Command |
|---|---|
| `claude` | `claude --print` |
| `codex` | `codex exec` |
| `ollama` | `ollama run <model>` |
| Unknown | bare path |

No advanced flags (model selection, max-turns, tool allowlists). Callers that need those can explicitly configure a `command` profile in `llm.yaml`.

### 3. Airplane mode uses Ollama CLI (not HTTP)

When airplane mode is active, `resolve_llm_profile` returns a `cli-offline` profile with `ollama run <model>` instead of the HTTP `local` profile. Falls back to HTTP `local` only when Ollama CLI isn't on PATH.

This keeps airplane mode aligned with the general dispatch pattern — CLI subprocess everywhere.

### 4. HTTP profiles remain for explicit override

The `local`, `remote`, `vision-local` profiles stay in `llm.yaml`. Setting `active_profile: local` in the config file forces HTTP Ollama. The auto-detection only kicks in when no explicit `active_profile` is set.

### 5. Thinking model support via native API fallback

Added `disable_thinking: bool` to `LLMProfile` and `OpenAICompatibleClient`. When set and base URL is Ollama, `_post_completion` falls back to `/api/generate` with `think: false`. This is only needed for explicit HTTP Ollama use — CLI dispatch via `ollama run` handles it natively.

## Consequences

### Positive

- Zero-config LLM dispatch — works out of the box if any supported CLI is installed
- Running inside Claude Code uses Claude's own API (via `claude --print`), not a separate Ollama instance
- Airplane mode uses the same CLI dispatch pattern, just with `ollama run` instead of `claude --print`
- 58 tests covering all paths (CLI detection, profile injection, airplane mode, HTTP fallback)

### Negative

- CLI dispatch is slower than HTTP for high-volume batch operations (subprocess overhead per call). The contextualizer processing 2,436 chunks at ~18s/call via `claude --print` would take ~12 hours. For batch workloads, explicitly setting `active_profile: local` (HTTP Ollama) is faster.

### Neutral

- `config/system/llm.yaml` gains `external.preferred_cli` field aligned with existing `resolve_cli()` in `llm_retry.py`
- The `CommandLLMClient` is now the most-used client type in practice (was least-used before)

## Alternatives Considered

### Alternative 1: Rewrite resolve_llm_profile to prefer CLI

Change resolution order to always try CLI first. Rejected: would ignore explicit HTTP config and break users who intentionally configured remote profiles.

### Alternative 2: Add `provider: auto` type

New provider that resolves at `create_llm_client` time. Rejected: detection would run on every `create_llm_client` call instead of once at config load.

## References

- [ADR-528: Unified LLM Provider Abstraction](ADR-528-unified-llm-provider-abstraction.md) — the HTTP-first abstraction this builds on
- [ADR-137: Eliminate Direct LLM Calls from Scripts](ADR-137-eliminate-direct-llm-calls.md) — established the three dispatch patterns
- [ADR-521: Local Mode: Ollama Integration](ADR-521-local-mode-ollama-integration.md) — airplane mode design
- Design spec: `docs/superpowers/specs/2026-04-02-llm-cli-dispatch-design.md`
- Implementation plan: `docs/superpowers/plans/2026-04-02-llm-cli-dispatch.md`

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "load_llm_config() now auto-injects 'cli' profile from detected CLI"
    - "resolve_llm_profile() airplane mode returns CLI profile instead of HTTP"
    - "New module: skills/ai/augur/lib/cli_detect.py"
  patterns_deprecated:
    - "Requiring explicit active_profile in llm.yaml for basic operation"
    - "Airplane mode defaulting to HTTP local profile"
  files_affected:
    - "skills/ai/augur/lib/cli_detect.py"
    - "skills/ai/augur/lib/config.py"
    - "config/system/llm.yaml"
```

## Completion Criteria

- [x] `detect_cli()` finds preferred CLI from user config
- [x] `load_llm_config()` injects `cli` profile when CLI found
- [x] `active_profile` defaults to `cli` when no explicit config
- [x] Explicit `active_profile` in file overrides auto-detection
- [x] Airplane mode returns `ollama run` CLI profile
- [x] Airplane mode falls back to HTTP `local` when no Ollama CLI
- [x] 58 tests pass
- [x] Browser verification passes
- [x] `config/system/llm.yaml` has no `active_profile` line
