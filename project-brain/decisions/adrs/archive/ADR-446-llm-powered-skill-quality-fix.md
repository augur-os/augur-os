---
status: Implemented
date: 2026-03-19
deciders:
  - Gur Sannikov
related: []
tags: [adaptive, llm, skill-quality, code-generation]
---

# ADR-446: LLM-Powered Skill Quality Fix Phase

## Context

The auto-skill-quality loop plateaued at avg 45.4 (0 tier-A, 15 tier-B, 116 tier-C). File-level fixes (rewrite descriptions, create dirs, generate seeds) extracted all possible value. The remaining gap to tier A requires writing actual code: MCP tool registrations, API routes, and React page components. The Python-based fix phase cannot write code.

Note: This design is superseded at the engine level by ADR-444 (engine-level LLM escalation), which generalizes this approach to all loops. This ADR documents the skill-quality-specific prompt engineering and escalation logic.

## Decision

Upgrade the skill-quality fix phase to dispatch focused LLM sessions via `build_headless_cmd()` at difficulty >= 3. The LLM receives a structured prompt containing the skill's score breakdown, dimension-specific bottleneck instructions, a working example from a high-scoring skill, and explicit scope constraints.

Key design points:
- **Escalation trigger**: `fix()` tries file-level fixes first; if still below tier A at d3+, constructs an LLM prompt
- **Prompt includes**: score breakdown, user journey analysis, bottleneck identification, pattern from high-scoring skill, file scope constraints
- **Dimension-specific instructions**: product bottleneck -> create MCP tool + API route; instruction -> rewrite SKILL.md; UI -> scaffold page component; wiring -> fix toolName refs
- **CLI resolution**: reuses existing chain from `llm_retry.py`
- **Manual trigger**: `/auto-skill-quality --upgrade N` runs on N worst skills with LLM enabled

## Consequences

### Positive

- Breaks past the file-level fix ceiling for skill quality improvement
- Structured prompts with working examples produce consistent, pattern-following code
- Same git revert safety net as file-level fixes

### Negative

- LLM-generated code may not follow all Augur conventions perfectly
- Each LLM fix session costs ~600s and significant token budget
- Prompt quality is critical -- poor prompts waste budget with no score improvement

### Neutral

- File-level fixes at d0-d2 remain unchanged and continue running first
- Trust gate (>0.5) and difficulty gate (>=3) prevent premature LLM escalation

## Alternatives Considered

### Alternative 1: Manual Code Writing

Developers manually write MCP tools and API routes for each skill. Rejected because 116 tier-C skills makes this impractical.

### Alternative 2: Template-Based Code Generation

Generate code from templates without LLM. Rejected because skill domains vary too much for rigid templates.

## References

- Design spec
