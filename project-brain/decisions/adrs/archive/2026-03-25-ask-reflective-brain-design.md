# /ask Reflective Brain — Design Spec

**Date:** 2026-03-25
**Status:** Draft
**Scope:** Transform `/ask` from a search-and-synthesize command into a reflective inner voice that speaks from the user's vault, consolidated memories, and life context.

## Problem

`/ask` and `/search` are functionally identical — both search knowledge sources and summarize results. The user wants `/ask` to feel like talking to their own self-reflection: an inner voice that knows their history, decisions, preferences, career, health, and daily life. No ADR numbers, no file paths, no technical citations — just personal, contextual awareness.

## Requirements

| Requirement | Detail |
|---|---|
| Core identity | Inner voice / self-reflection, not a search tool |
| Knowledge substrate | Full vault (life, career, health, finance, lifestyle, projects) + consolidated memories + digests |
| Tone | Personal, first/second person, no technical artifacts |
| Scope | Fluid — decisions, self-awareness, knowledge recall, whatever feels natural |
| Unknown territory | Blend gracefully from known memories, acknowledge gaps honestly |
| Turn structure | Adaptive — single-turn default, multi-turn when depth warrants it |
| Memory formation | Optional — offer to remember if something meaningful surfaced |
| Client support | All synced clients (Claude Code, Codex, Gemini) get full experience via MCP tool + SKILL.md |

## Approach

**Approach B: Context Assembly MCP Tool + Prompt Rewrite.** A new MCP tool handles "what does the brain know about this?" and the SKILL.md prompt handles "how does the brain speak?"

## Design

### Component 1: `reflect-context` MCP Tool

**Location:** `skills/knowledge/scripts/mcp/tools_reflect.py`
**Registration:** MCP tool `reflect-context` alongside existing `unified-search` and `memory-search`

**Input:**
```python
{
  "query": str,              # The user's question
  "conversation_summary": str | None,  # For multi-turn: summary of prior turns
  "token_budget": int        # Default: 4000
}
```

**Logic:**
1. Run a single RAG search across the full vault (`get_vault_dir()`) with the user's query
2. Group results by vault top-level directory (career/, health/, memory/, etc.)
3. Rank domains by aggregate relevance score of their hits — domains with stronger matches get more token budget
4. Always include identity baseline regardless of search results:
   - User preferences and feedback from `memory/entries/` (type: preference, feedback)
   - Recent focus from `memory/digest-hot.md`
5. Assemble context within token budget, allocated proportionally:
   - Identity/preferences: ~500 tokens (always)
   - Recent focus (digest): ~300 tokens (always)
   - Relevant memories: ~1500 tokens (RAG-ranked consolidated entries)
   - Domain context: ~1700 tokens (from top-scoring vault directories)
6. Strip all file paths, ADR numbers, and technical metadata from output — return content only

**Output shape:**
```python
{
  "identity": str,              # Who the user is — preferences, patterns, style
  "relevant_memories": list[str],  # Top consolidated entries matching the query (content only)
  "domain_context": list[str],     # Vault content from semantically matched domains
  "recent_focus": str              # What they've been doing lately (from digests)
}
```

**Key design decisions:**
- **Semantic domain routing, not keyword mapping.** The RAG search results themselves reveal which vault domains are relevant. No keyword-to-domain map to maintain. New vault directories become searchable automatically.
- **Content-only output.** File paths, frontmatter metadata, ADR numbers are stripped before returning. The reflective voice prompt should never see technical artifacts.
- **Budget-controlled.** The tool respects a token budget, preventing context window bloat. Budget is allocated proportionally to domain relevance.

### Component 2: SKILL.md Rewrite

**Location:** `skills/ask/SKILL.md`

Complete rewrite from search-and-synthesize to reflective voice.

**Persona preamble:**
- "You are the user's inner voice — a reflection of everything they've learned, decided, experienced, and care about."
- Speak in first person plural ("we") or second person ("you") naturally
- Never cite sources, file paths, ADR numbers, or technical metadata
- If you don't have memory of something, say so naturally: "I don't have a clear sense of that"
- Don't fabricate memories or pad with generic knowledge

**Workflow:**
1. Parse the question from `$ARGUMENTS`
2. Call `reflect-context` MCP tool with the question
3. If the payload is thin (few matches), acknowledge honestly rather than padding
4. Respond in the reflective voice
5. If multi-turn seems warranted (question is deep, ambiguous, or context reveals tension), ask a follow-up rather than giving a shallow answer
6. At end of conversation, if meaningful insights surfaced, offer: "Want me to hold onto anything from this?"
7. If yes, call `memory-log-decision` or `memory-log-preference` to write to daily log layer (nightly consolidation picks it up)

**Tone examples:**

| User says | Response style |
|---|---|
| "What do I know about leadership?" | "You've been thinking about this — especially the deep work angle and that AI-age leadership material. Your instinct has been that leadership is less about managing people and more about creating focus." |
| "Am I ready for interviews?" | "You've got the foundation — multiple angles on your CV, a solid first STAR story. But honestly? One story isn't enough. You tend to undersell the hands-on technical work." |
| "What should I eat today?" | "You've got those perfected breakfast recipes — the French toast, the zaatar pita. For something new, there's that chicken breast and the arais tortilla you've been meaning to try." |
| "Should I take this job?" | Pulls career profile, salary requirements, growth notes. Reflects on patterns in what the user values. May ask: "What's pulling you toward it?" |

### Component 3: Multi-Turn Behavior

- The agent assesses depth after assembling context. If the question is broad, ambiguous, or context reveals conflicting past decisions, ask one follow-up rather than giving a surface answer.
- On follow-up turns, call `reflect-context` again with the refined question + conversation summary, so new vault context can surface as the topic narrows.
- The agent decides when to go deeper — the user can always answer and move on, or keep pulling the thread.
- No special infrastructure needed — multi-turn uses the agent's native session state.

### Component 4: Memory Formation

- When the topic wraps up, if the conversation produced a new insight, decision, or self-awareness moment, offer: "Want me to hold onto anything from this?"
- If yes, call existing `memory-log-decision` or `memory-log-preference` MCP tools to write to the daily log layer
- The nightly consolidation pipeline (auto-memory-sync + auto-agent-digest) picks it up — no new write infrastructure needed
- If nothing meaningful surfaced, say nothing. Don't ask every time.

## Files to Create/Modify

| File | Action | Purpose |
|---|---|---|
| `skills/knowledge/scripts/mcp/tools_reflect.py` | Create | New `reflect-context` MCP tool |
| `skills/ask/SKILL.md` | Rewrite | Reflective voice workflow replacing search-and-synthesize |
| `src/mcp/augur_mcp/client_surface.py` | Modify | Register `reflect-context` in tool visibility |

## What This Does NOT Change

- `/search` remains unchanged — it's the technical search tool
- `unified-search` and `memory-search` MCP tools remain unchanged
- The memory consolidation pipeline (auto-memory-sync, auto-agent-digest) remains unchanged
- The vault structure remains unchanged
- No new vault directories, no new file formats

## Success Criteria

1. `/ask "What do I know about leadership?"` responds with personal reflection drawing from growth notes and memory, with zero file paths or ADR numbers in the output
2. `/ask "Am I ready for interviews?"` pulls from career profile, STAR stories, and learning notes to give an honest assessment
3. `/ask "What should I eat?"` surfaces recipes from lifestyle vault naturally
4. Multi-turn: `/ask "Should I change careers?"` asks a follow-up rather than giving a shallow answer
5. Memory formation: After a meaningful conversation, the brain offers to remember — and if accepted, the insight appears in consolidated memory after the next nightly sync
6. Works identically across Claude Code, Codex, and Gemini
