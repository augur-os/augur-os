---
status: Implemented
date: '2026-02-26'
deciders:
- Project lead
related:
- ADR-004 (Markdown RAG)
- ADR-005 (MCP as Execution Gateway)
- ADR-033 (Unified Search)
- ADR-127 (RAG Search Engine)
- ADR-028 (Two-Layer Memory)
hub: null
tags:
- live
- knowledge
- query
- ask
- command
superseded_by: null
---

# ADR-166: Live Knowledge Query (`/ask`) Command

## Context

Augur is a second-brain system with knowledge distributed across 165+ ADRs, 35+ skills, curated memory (`MEMORY.md`), plugin data directories, and RAG indices. During investor presentations, the user needs instant, authoritative answers to ad-hoc questions about any aspect of the project — architecture, business model, financial decisions, development patterns, or plugin capabilities.

Currently, retrieving this information requires knowing which tool or command to use:
- `/rag search <skill> <query>` for RAG content
- `/focus <skill>` then manual exploration for skill context
- Reading `docs/decisions/ADR-NNN-*.md` for architectural decisions
- Reading `docs/memory/MEMORY.md` for curated knowledge

There is no single command that searches across **all** knowledge sources and synthesizes a concise answer. Additionally, the `unified-search` MCP tool covers 4 scopes (memory, knowledge, skills, rag) but does **not** index `docs/decisions/` — the most comprehensive knowledge source in the project (165 documents covering every architectural decision).

**Presentation requirement**: The user types `/ask <question>` during a live investor demo, and the second brain responds with a clear, sourced answer in under 15 seconds.

## Decision

### Component 1: Add `decisions` Scope to UnifiedSearcher

Extend `UnifiedSearcher` in `plugins/ai/skills/knowledge/augur/mcp/memory/unified_search.py` to include a `decisions` scope that searches `docs/decisions/`.

**Changes**:
- Add `"decisions"` to `VALID_SCOPES`
- Add `_get_scope_paths` handler returning `[docs/decisions/]`
- The existing `unified-search` MCP tool automatically picks up the new scope (no registration change needed)

This makes all 165+ ADRs searchable via the same MCP tool that searches memory, skills, and RAG content.

### Component 2: Create `/ask` Workflow

Create a new workflow file at `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/ask.md` with visibility `core`.

**The workflow instructs the agent to**:

1. **Parse** the user's question from arguments
2. **Search broadly** — call `unified-search` with all 5 scopes (`memory`, `knowledge`, `skills`, `rag`, `decisions`) for maximum coverage
3. **Deep-read** — read the top 2-3 most relevant files identified by search for full context
4. **Synthesize** — produce a concise, presentation-ready answer with source attribution
5. **Format** — short paragraphs, no code blocks unless technical, cite source files

**Answer format**: Direct, confident, 2-5 sentences. Sources listed at the bottom. Optimized for a live audience watching over the user's shoulder.

### Component 3: Sync to Claude Code

Run `sync_agents.py --workflows` to propagate the new workflow to `.claude/skills/ask/SKILL.md` where Claude Code discovers it.

## Consequences

**Positive**:
- Single entry point for any project knowledge query — architecture, business, finance, development
- Investor demo-ready: type `/ask`, get a sourced answer in seconds
- ADRs become searchable via `unified-search` (fixes a gap — 165 documents were invisible to the search tool)
- No new MCP tools or infrastructure — leverages existing `unified-search`, just adds a scope and a workflow
- Useful beyond presentations — daily knowledge retrieval during development

**Negative**:
- Answer quality depends on search result relevance — poor keyword overlap may miss relevant ADRs
- Adding the `decisions` scope increases `unified-search` latency by ~1 scope worth of search time
- Business/financial knowledge must exist as files in the knowledge base to be findable (Augur can't answer questions about data it doesn't have)

**Neutral**:
- No dashboard changes required — this is CLI-only (Claude Code)
- No new Python dependencies
- RAG index quality for ADRs depends on existing indexing infrastructure

## Implementation Order

```
Phase 1: UnifiedSearcher decisions scope
├── Step 1: Add "decisions" to VALID_SCOPES and _get_scope_paths
└── Step 2: Verify via unified-search MCP tool call

Phase 2: /ask workflow (depends on Phase 1)
├── Step 3: Create ask.md workflow file
├── Step 4: Run sync_agents.py to propagate to .claude/skills/
└── Step 5: Test /ask with sample questions across all domains

Phase 3: Verification
├── Step 6: End-to-end test — /ask architectural question → gets ADR-sourced answer
├── Step 7: End-to-end test — /ask business question → gets memory-sourced answer
└── Step 8: End-to-end test — /ask skill question → gets SKILL.md-sourced answer
```

## Alternatives Considered

### 1. Dedicated `ask-knowledge` MCP tool with built-in synthesis

Create a new MCP tool that accepts a question, searches all sources, and returns a synthesized answer.

**Rejected because**: Would require LLM calls inside the MCP tool (violates the pattern of keeping LLM synthesis in the agent layer). The existing `unified-search` + agent synthesis is the right separation of concerns. Also, the agent (Claude Code) already has the full LLM capability — no need to duplicate it in MCP.

### 2. Pre-built answer index (FAQ/knowledge base)

Pre-generate answers to common investor questions and store them as searchable documents.

**Rejected because**: Fragile — new decisions and changes require manual FAQ updates. The dynamic search + synthesis approach handles any question, including ones we didn't anticipate. Also defeats the "second brain" demo — the magic is that it searches live knowledge, not canned answers.

### 3. Workflow-only (no UnifiedSearcher change)

Have the `/ask` workflow use Grep to search ADRs directly instead of adding a `decisions` scope.

**Rejected because**: Using agent-level Grep for ADR search is slower (sequential file reads) and doesn't benefit from RAG's iterative search ranking. Adding the scope is a 5-line change that makes ADRs a first-class search source for all consumers of `unified-search`, not just `/ask`.

## References

- ADR-004: Markdown RAG over Vector Databases
- ADR-005: MCP as Execution Gateway
- ADR-028: Two-Layer Memory
- ADR-033: Unified Search (Component 5)
- ADR-127: RAG Search Engine
- `plugins/ai/skills/knowledge/augur/mcp/memory/unified_search.py` — UnifiedSearcher
- `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/` — Workflow source directory

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-166: Live Knowledge Query (`/ask`) Command**.

Read the full ADR: `docs/decisions/ADR-166-live-knowledge-query-ask-command.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-166-ask", description="Implementing ADR-166: /ask live knowledge query command")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-166-ask", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-166-ask team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-166-ask`

#### Phase 1: UnifiedSearcher decisions scope
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Add `"decisions"` to `VALID_SCOPES` and add `decisions` handler in `_get_scope_paths` returning `[self._project_root / "docs" / "decisions"]` | `plugins/ai/skills/knowledge/augur/mcp/memory/unified_search.py` |
| 1.2 | validator | low | Call `unified-search` MCP tool with `scopes=["decisions"]` and `query="local-first architecture"` — verify ADR hits are returned | — |

#### Phase 2: /ask workflow
**Strategy**: PIPELINE (depends on Phase 1)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create the `/ask` workflow file. Follow the format of existing workflows (`focus.md`, `rag.md`). Visibility: `core`. The workflow must instruct the agent to: (1) parse question from `$ARGUMENTS`, (2) call `unified-search` with all 5 scopes, (3) read top 2-3 matching files, (4) synthesize a concise answer with source attribution, (5) format for live presentation — short paragraphs, confident tone, sources at bottom | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/ask.md` |
| 2.2 | devops | low | Run `python3 plugins/ai/skills/ai_bridge/scripts/sync_agents.py --workflows` to propagate to `.claude/skills/ask/SKILL.md` | `.claude/skills/ask/SKILL.md` |
| 2.3 | validator | low | Test `/ask` with 3 sample questions: (1) "What is Augur's architecture?" (architecture), (2) "How many plugins does Augur have?" (project scope), (3) "What is the MCP-first pattern?" (development pattern). Verify each returns a sourced answer | — |

#### Phase 3: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 3.1 | validator | low | Run `pytest tests/src/` — verify no regressions from UnifiedSearcher change |
| 3.2 | validator | low | Run `npm run build` — verify dashboard build passes |
| 3.3 | architect | low | Verify ADR intent matches implementation — `/ask` returns concise sourced answers from all knowledge domains |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] `unified-search` returns ADR results when `decisions` scope is used
- [ ] `/ask` workflow exists at `.claude/skills/ask/SKILL.md`
- [ ] `/ask` returns sourced answers for architecture, business, and development questions
- [ ] ADR status updated to "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-166-live-knowledge-query-ask-command.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
