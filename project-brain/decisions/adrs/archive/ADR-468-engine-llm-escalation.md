---
status: Implemented
date: 2026-03-22
deciders:
  - Gur Sannikov
related: []
hub: adaptive
tags:
  - adaptive-engine
  - llm-escalation
  - headless-dispatch
superseded_by: null
---

# ADR-468: Engine-Level LLM Escalation

## Context

Adaptive loops plateau when file-level `fix()` operations cannot resolve complex issues. The engine has no mechanism to escalate to LLM-powered fixes, leaving difficult problems unfixed even when a CLI agent is available.

## Decision

Add LLM escalation as a first-class engine capability:

1. Add `SessionContext` dataclass to `ops_protocol.py` tracking runtime capabilities (`has_tool_access`, `has_llm`, `cli_path`, `cli_name`)
2. Detect the runtime environment at engine startup (agent session env vars, CLI resolution via `resolve_cli()`)
3. Wire LLM escalation into `engine_fix_phase.py` -- when `fix()` returns empty and the module provides `llm_fix()`, dispatch a headless LLM subprocess via `build_headless_cmd()`
4. Gate escalation on: enabled config, minimum difficulty level (d3), minimum trust score (0.5), and LLM availability
5. Individual loops opt in by adding an `llm_fix()` function that returns a prompt string

`auto-skill-quality` serves as the first adopter, with `llm_fix()` generating dimension-specific improvement prompts targeting the worst-scoring skill.

## Consequences

### Positive
- Breaks through plateaus where file-level fixes are insufficient
- CLI-agnostic -- works with Claude Code, Codex, Gemini via `resolve_cli()`
- Opt-in per loop -- no changes needed for loops that don't want LLM escalation

### Negative
- Subprocess dispatch adds latency (up to 600s timeout)
- LLM fixes are non-deterministic and harder to predict
- Requires a CLI agent available on PATH

### Neutral
- Config in `adaptive_loops.yaml` under `engine.llm_escalation`
- Session detection clears nesting env vars to prevent recursive dispatch

## Alternatives Considered

### Alternative 1: In-process LLM API calls
Rejected to avoid coupling the engine to specific LLM providers and to reuse existing CLI infrastructure.

## References
- Plan: `docs/superpowers/plans/2026-03-18-engine-llm-escalation.md`
- Spec: `docs/superpowers/specs/2026-03-18-engine-llm-escalation-design.md`
