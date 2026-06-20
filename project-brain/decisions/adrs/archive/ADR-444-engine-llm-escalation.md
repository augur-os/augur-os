---
status: Implemented
date: 2026-03-19
deciders:
  - Gur Sannikov
related: []
tags: [adaptive, llm, engine, escalation, automation]
---

# ADR-444: Engine-Level LLM Escalation for Adaptive Loops

## Context

All adaptive loops plateau when their Python-based `fix()` functions exhaust file-level operations (string manipulation, directory creation, config edits). The remaining issues require writing actual code -- MCP tools, API routes, page components, complex refactors -- which needs an LLM. Currently only the self-healer has LLM dispatch capability. Every other loop hits a ceiling.

## Decision

Add LLM escalation as a first-class engine capability available to all adaptive loops. The engine detects the runtime environment (in-session vs headless daemon) via `SessionContext`, and individual loops opt in by providing an `llm_fix()` function that returns a prompt string. The engine handles dispatch, safety, and trust gating uniformly.

Key design points:
- **SessionContext** dataclass added to `OpsContext` with `has_tool_access`, `has_llm`, `cli_path`, `cli_name`, `max_turns`, `timeout`
- **Detection** runs once at engine init, checking environment variables and PATH for available CLIs
- **Opt-in**: loops define `llm_fix()` returning a prompt string; engine handles dispatch
- **Dispatch**: both in-session and headless use `build_headless_cmd()` from `llm_retry.py`
- **Safety**: git snapshot before, build verify after, revert on failure, trust penalty, budget multiplier (3x), turn limit, timeout
- **No model hardcoding**: whatever CLI is resolved uses its own configured model

## Consequences

### Positive

- Any loop can break past the file-level fix ceiling by adding a single `llm_fix()` function
- Uniform safety guarantees (git revert, build verify, trust gating) for all LLM-powered fixes
- CLI-agnostic and model-agnostic -- works with Claude, Gemini, Codex, or any future CLI

### Negative

- LLM fixes are expensive (3x budget multiplier) and slow (up to 600s timeout)
- Prompt quality becomes the bottleneck -- poor prompts produce poor fixes
- Adds complexity to the engine dispatch path

### Neutral

- Loops without `llm_fix()` are completely unaffected (backward compatible)
- Supersedes the skill-quality-specific LLM fix design (ADR-446) by generalizing it to all loops

## Alternatives Considered

### Alternative 1: Per-Loop LLM Integration

Each loop implements its own LLM dispatch. Rejected because it duplicates safety logic, CLI resolution, and git revert handling across every loop.

### Alternative 2: Agent Subagent Dispatch

Use Claude Code's Agent tool for in-session dispatch. Deferred as a future optimization -- current `build_headless_cmd()` works in both modes.

## References

- Design spec
