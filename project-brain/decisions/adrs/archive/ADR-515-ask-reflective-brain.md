---
status: Implemented
date: 2026-03-25
deciders:
  - Gur Sannikov
related:
  - ADR-028
  - ADR-033
  - ADR-510
hub: brain
tags:
  - ask
  - memory
  - reflection
superseded_by: null
---

# ADR-515: /ask Reflective Brain — Inner Voice from Consolidated Memories

## Context

`/ask` and `/search` are functionally identical — both search knowledge sources and summarize results with file paths and ADR citations. The user wants `/ask` to feel like talking to their own self-reflection: an inner voice that knows their history, decisions, preferences, career, health, and daily life. No technical artifacts — just personal, contextual awareness.

The memory consolidation pipeline (ADR-510, auto-memory-sync, auto-agent-digest) now produces rich structured context: 82 consolidated entries, hot directives, warm ADR digests. This knowledge substrate exists but `/ask` doesn't leverage it as a reflective identity — it treats it as search fodder.

## Decision

Transform `/ask` from search-and-synthesize into a reflective inner voice using two components:

### 1. `reflect-context` MCP Tool

New tool at `skills/knowledge/scripts/mcp/tools_reflect.py` that assembles a budget-controlled personal context payload:

- Searches the full vault (`get_vault_dir()`) via ripgrep text matching
- Groups results by vault top-level directory (career/, health/, memory/, etc.)
- Always includes identity baseline: user preferences/feedback from `memory/entries/`, recent focus from `memory/digest-hot.md`
- Allocates token budget proportionally to domain relevance (~4000 tokens default)
- Strips all file paths, ADR numbers, frontmatter, and code blocks from output — returns content only

Output shape: `{ identity, relevant_memories, domain_context, recent_focus }`

### 2. SKILL.md Rewrite

Complete rewrite from search-and-synthesize to reflective voice:

- Persona: "You are the user's inner voice — a reflection of everything they've learned, decided, experienced, and care about"
- Speaks in first/second person, never cites sources or technical metadata
- Adaptive depth: single-turn for simple recall, multi-turn for deep/ambiguous questions
- Memory formation: offers to remember insights at conversation end via existing `memory-log-decision`/`memory-log-preference` tools

### Files Changed

| File | Action |
|------|--------|
| `skills/knowledge/scripts/mcp/tools_reflect.py` | Create |
| `skills/knowledge/scripts/mcp/tools_rag.py` | Modify (wire registration) |
| `src/mcp/augur_mcp/client_surface.py` | Modify (add visibility) |
| `skills/ask/SKILL.md` | Rewrite |

## Consequences

### Positive

- `/ask` becomes a distinct, valuable tool — no longer redundant with `/search`
- Consolidated memories get a consumer that makes them tangible to the user
- Works across all synced clients (Claude Code, Codex, Gemini) via MCP tool + SKILL.md

### Negative

- Ripgrep text matching is not true semantic search — relevance depends on keyword overlap
- Token budget allocation is heuristic — may over/under-weight domains for some queries

### Neutral

- `/search` remains unchanged as the technical search tool
- Memory consolidation pipeline unchanged — no new write paths
- No new vault directories or file formats

## Alternatives Considered

### Alternative 1: Prompt-Only Rewrite

Rewrite SKILL.md to load memories directly without a dedicated MCP tool. Rejected because context assembly logic (budget control, domain routing, metadata stripping) would be embedded in prompt instructions rather than deterministic code.

### Alternative 2: Dedicated Reflection Agent

Build `/ask` as a full subagent with persistent state and conversation loop. Rejected as overkill — the adaptive single-to-multi-turn model works with native agent session state, no new infrastructure needed.

## References

- Design spec: `docs/superpowers/specs/2026-03-25-ask-reflective-brain-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-25-ask-reflective-brain.md`
- ADR-028: Two-Layer Memory Architecture
- ADR-033: RAG Search Hardening
- ADR-510: Agent Digest Nightly Autoloop
