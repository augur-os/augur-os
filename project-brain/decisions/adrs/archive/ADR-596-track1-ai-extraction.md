---
status: Implemented
date: 2026-04-29
deciders:
  - Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
---

# ADR-596: Track 1 AI Extraction

## Context

The cross-client bundle architecture migration (Layer 1/Layer 4 specs) calls for moving the canonical LLM library from `skills/ai/augur/lib/` to `src/lib/ai/`. Libraries 1–4 (document-extractor → `src/lib/extraction/`, knowledge memory → `src/lib/knowledge/`, daemon runtime → `src/lib/runtime/`, rag → `src/lib/index/`) already landed. Library 5 — the `ai` bundle — is the broadest-reach library, hosting `LLMConfig`, `LLMClient`, profiles, IDE integrations, prompt registry, and usage tracking.

An audit of `skills/ai/scripts/` found it is mostly CLI tools, sync engines, and ops scripts (75 .py files) — not a library. The actual library is `skills/ai/augur/lib/` (22 .py files), which matches the four architecture-test allowlist entries' expectations. The fourth allowlist entry (`("ingest", "ai")`) is coupled to `skills/ai/scripts/sync_agents/`, which is out of narrow Library 5 scope and stays.

Consumers of the library are spread across 3 skills (`file-manager`, `onboard`, `platform-admin`), 2 `.github/scripts/`, 2 `src/lib/` internal modules (`extraction/ollama_client.py`, `llm_retry.py`), one unit test (`tests/test_llm_retry_config.py`), and ai's own tests (~42 references).

## Decision

Migrate `skills/ai/augur/lib/` (22 files) to `src/lib/ai/` using rename-via-overlap across six sequential PRs in a `track1-ai` worktree:

1. **PR 1 (additive):** copy 21 .py files verbatim to `src/lib/ai/`, add a new `__init__.py` exposing the public API (`LLMClient`, `LLMConfig`, `LLMProfile`, `create_llm_client`, `get_llm_client`, `load_llm_config`, `resolve_llm_profile`), convert `ide_health.py`'s self-package absolute imports to relative form (cross-package imports into `adapters/` stay absolute since `adapters/` is not moving), add smoke tests at `tests/lib/ai/`.
2. **PR 2:** migrate `file-manager`, `onboard`, `platform-admin` consumers to `src.lib.ai`.
3. **PR 3:** migrate `.github/scripts/validate_command_parity.py` and `verify_schema.py`.
4. **PR 4:** migrate `src/lib/extraction/ollama_client.py`, `src/lib/llm_retry.py`, and `tests/test_llm_retry_config.py` (bulk substitution).
5. **PR 5:** migrate ai's own tests via bulk sed substitution.
6. **PR 6:** delete the 22 skill-side library files; retire 3 architecture-test allowlist entries (`onboard`, `platform-admin`, `file-manager`); keep `("ingest", "ai")` with a comment noting `sync_agents` scope deferral.

Scope explicitly excludes `skills/ai/augur/adapters/`, `augur/actions/`, `augur/config/`, and `skills/ai/scripts/` — only `lib/` moves.

## Consequences

### Positive
- Track 1 (library extraction) is complete: 5/5 libraries migrated to `src/lib/`.
- 3 of 4 architecture-test allowlist entries retired; 1 remains with documented narrow-scope deferral.
- Consumers import from a stable `src/lib/ai` path with a documented public API surface.
- Rename-via-overlap means each PR is independently reviewable and revertable.

### Negative
- Six PRs across one worktree adds coordination overhead versus a single mega-PR.
- The `("ingest", "ai")` allowlist entry remains, deferred to a future `sync_agents` track.

### Neutral
- The `ai` bundle keeps its adapter shims, slash command handlers, config wiring, tests, and scripts — only the LLM library moves.
- Public API origins shift from `skills.ai.augur.lib.client` to `src.lib.ai.client` for module introspection.

## Alternatives Considered

### Alternative 1: Move all of `skills/ai/scripts/` along with `lib/`
Rejected: most of `scripts/` is CLI/ops/sync, not a library; the four allowlist entries' coupling is to `lib/`, not `scripts/`. Including `scripts/` would broaden scope without retiring more allowlist entries.

### Alternative 2: Single mega-PR
Rejected: rename-via-overlap with one consumer group per PR keeps each change small and the test cascade focused. A single PR would risk masking import regressions across consumer groups.

### Alternative 3: Retire `("ingest", "ai")` in this track
Rejected: ingest's coupling is to `skills/ai/scripts/sync_agents/`, not `augur/lib/`. Retiring it requires a separate `sync_agents` extraction.

## References
- Plan: docs/superpowers/plans/2026-04-29-track1-ai-extraction.md
- Layer 1 spec: docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md
- Layer 4 spec: docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md
