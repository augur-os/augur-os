<!--
⚠️  AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
Source: docs/agent-topics/CONTEXT.md
Generator: project-brain/capabilities/skills/ai/scripts/sync_agents/__init__.py
-->
# Context Management

> **When to load**: Load this doc when managing MCP tools, context windows, agent teams, or subagent handoffs.

## MCP Tools

### MANDATORY: Use Before Skill Work

Before modifying ANY skill, ALWAYS:

1. **Use `get-context` MCP tool**
   ```
   Tool: get-context
   Args: { "skill_hint": "lifestyle" }
   ```
   Returns: SKILL.md content, related files, recent changes, user preferences.

2. **Read SKILL.md**
   ```
   Read project-brain/capabilities/skills/{skill}/SKILL.md
   ```
   Understand current capabilities before adding new ones.

3. **Check for relevant actions**
   ```
   ls project-brain/capabilities/skills/{skill}/assets/actions/
   ```
   Complex workflows may already have action YAMLs with dispatch modes (fire, oneshot, ide, modal).

### `get-context`
**When**: Before any task to get personalized context about the skill/feature.
```
Tool: get-context
Args: { "skill_hint": "dashboard" }
```
Returns: Relevant files, recent changes, user preferences.

### `discover-augur`
**When**: At session start, or to refresh context when switching tasks.
```
Tool: discover-augur
Args: { "hub": "career" }  // optional, inferred from signals if omitted
```
Returns: Focus-aware manifest with recommended tools, skill list, hub structure.
Replaces `/focus` — context is now inferred automatically from dashboard navigation,
CLI usage, and git signals. Per-session isolation prevents parallel workstreams from contaminating each other.

### CLI: `aug discover`

The `aug` CLI wraps all MCP tools and is installable via `pipx install -e .` (ADR-254 Phase 2).

```bash
aug discover                         # Full JSON manifest
aug discover --hub career --compact  # Filtered tool list
aug discover --tier public           # Public-tier tools only
aug discover --format markdown       # Agent-readable markdown
aug <tool-name> [--param value ...]  # Run any MCP tool
aug --list-tools                     # List all tools
```

For non-editable installs, set `AUGUR_ROOT=/path/to/augur` to locate the project.

## Retrieval Budgets (ADR-739)

Hybrid search fuses ranked `RetrieverSource` outputs with Reciprocal Rank Fusion
in `src/lib/index/rrf.py`. Current core sources are ripgrep full-text and BM25
keyword search; ADR-738's typed graph and any future vector retriever plug in as
additional sources through the same protocol.

The existing `mode` parameter remains the retrieval strategy axis (`keyword`,
`metadata`, `hybrid`, `iterative`). ADR-739 adds an orthogonal `budget` axis for
retrieval depth:

| Budget | Top K | Token Estimate |
|---|---:|---:|
| `conservative` | 5 | ~4K |
| `balanced` | 10 | ~10K |
| `tokenmax` | 20 | ~20K |

Use `search-stats` to inspect BM25 freshness and budget settings. Use
`search-tune` for a recommendation; it never switches budgets automatically.

### `get-design-standards`
**When**: Before making ANY UI changes.
```
Tool: get-design-standards
Args: {}
```
Returns: Color palette, component patterns, spacing rules, anti-patterns.

## Context Window Management

### MCP Limits (Prevents Context Exhaustion)

| Limit | Value | Rationale |
|-------|-------|-----------|
| Max configured MCPs | 20-30 | Beyond this, startup slows significantly |
| Max enabled per session | 10 | Context window pressure |
| Max active tools | 80 | Tool descriptions consume tokens |
| Max tools per page | 30 | Enforced via assembled_tool_config.json (ADR-260) |

### Warning Signs

Watch for these indicators of context exhaustion:
- Slow MCP initialization (>5s)
- Truncated context in responses
- Tool calls failing silently
- Agent "forgetting" earlier context
- Repeated requests for information already provided

### Mitigation Strategies

1. **Scope tools per page** via SKILL.md `x-augur-mcp-tools` frontmatter (auto-assembled by mount-plugins)
2. **Lazy tool loading** (`ENABLE_TOOL_SEARCH: "auto"` in `.claude/settings.json`) defers MCP tool schemas — only tool names loaded at startup (~1K tokens vs ~39K)
3. **Run verification** in a separate process (not in context)
4. **Create checkpoints** before long sessions: `/checkpoint create "session-start"`
5. **Run health check**: `python3 project-brain/capabilities/skills/daemon/scripts/mcp_health_check.py`
6. **Run `/auto-inspect context`** to audit context window footprint and clean stale memory entries

### Token-Efficient Patterns

```python
# INEFFICIENT - loads entire file into context
content = read_entire_large_file()
analyze(content)

# EFFICIENT - targeted reads
relevant_section = grep_for_pattern("error")
analyze(relevant_section)
```

```python
# INEFFICIENT - all tools always loaded
tools: ["*"]

# EFFICIENT - scoped by page/task
tools_by_page:
  control: [system_health, logs, metrics]
  career: [job_search, resume_builder]
```

### Health Check

Run periodically to validate MCP health:
```bash
python3 project-brain/capabilities/skills/daemon/scripts/mcp_health_check.py

# Output example:
# MCP count: 8/30 (OK)
# Tool count: 45/80 (OK)
# Startup time: 4.2s (approaching limit)
# All tools responding
```

## Context Discipline (Agent Teams & Subagents)

### File Loading
- Never glob entire directories (`**/*.ts`). Scope to specific subdirectories (`src/auth/**/*.ts`).
- Before reading a file, check if the information is already in context from a previous tool call.
- Prefer reading specific line ranges (`offset`/`limit`) over full files when you only need a section.
- Use Grep to find relevant files first, then Read only the matches.

### Subagent Handoffs
- When dispatching to a subagent, use a focused payload format.
- Never forward full conversation history to subagents. Build a focused payload.
- Strip all reasoning traces -- send conclusions and decisions, not the thought process.
- Pass exact file paths, not directory globs.

### Session Hygiene
- When approaching 60% context usage, run `/save` to checkpoint.
- Advisory agents should complete and return results promptly -- don't hold context open.
- Executor agents working on multi-file changes should checkpoint after each logical unit.

### Budget Guidelines

| Role | Target Budget | Rationale |
|------|--------------|-----------|
| Advisory agents (advisor, validator) | < 30K tokens | Read-only, no file editing overhead |
| Executor agents (developer, frontend) | < 80K tokens | Need room for reads + edits + test output |
| Orchestrator / parent session | Reserve 40K tokens | Must retain capacity for final synthesis |

### Agent Teams vs Subagents

| Use Agent Teams when... | Use Subagents when... |
|------------------------|----------------------|
| Agents need to debate or exchange findings | Task is self-contained with clear input/output |
| Multiple agents work on interconnected files | Agent works on independent files |
| Sustained reasoning across multiple turns | Single-turn: do task, return result |
| 3+ perspectives needed on the same code | One agent, one focused job |

Agent Teams = parallel processes with src/lib filesystem (expensive, powerful).
Subagents = function calls with own stack (cheap, focused).
Hybrid: Agent Teams for the outer loop, subagents for inner tasks each member dispatches.

**Related commands**: `/orch-audit`, `/save`, `/auto-inspect context`

## Memory System (ADR-164, ADR-429)

### Auto-Loaded Context Per Session

Augur memory is client-neutral at the architecture level. The vault memory store is canonical; client-native files are projections shaped for each AI client. Claude Code loads `~/.claude/projects/.../memory/MEMORY.md` at session start, Codex uses a flat Markdown projection, Gemini uses import-style references, and Cursor/Copilot/Kimi use configured Markdown targets.

### Client-Writer Resolution

When a client has its own writable native memory surface, sync must preserve client-authored entries and merge before overwriting generated projections. No client memory directory is the durable source of truth; durable facts go through the vault memory tools.

### Retention Policy

| Entry Type | Retention | Rationale |
|---|---|---|
| `chore:` | 7 days | Mechanical, no architectural value |
| `fix:` | 30 days | Bug context useful short-term |
| `feat:` / `docs:` | 60 days | Feature context for follow-up ADRs |
| Architectural insights | Forever | Patterns, anti-patterns, design decisions |

### Noise Filtering

Entries matching these patterns are auto-filtered during sync:
- `chore(sync): regenerate` / `chore(sync): update generated` — zero-insight sync commits
- `Session checkpoint created` — session-specific, not persistent knowledge
- Commit-only entries (hash + file count, no insight text)

Run `/auto-inspect context` to audit current context health and trigger cleanup.
