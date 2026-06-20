# AI Client Execution Model

Augur is a harness layer around native AI clients, not the default LLM executor. All normal reasoning work in Augur runs inside an AI client session. There are no background processors, no standalone job executors, no daemon-owned pipelines. Every trigger — CLI, web dashboard, scheduled — results in the same thing: an AI client session (Claude Code, Codex, Gemini CLI) with an agent that orchestrates work via MCP tools.

## The Principle

```
Trigger → AI Client Session → Agent orchestrates → MCP tools execute
```

The **agent** (LLM) is the orchestrator. It receives instructions, decides how to process them, calls MCP tools, handles parallelism, and uses its LLM capabilities for classification, summarization, and decision-making.

The **MCP tools** are the agent's hands. They perform atomic, stateless operations: read files, write files, extract content, index documents, query data. They never orchestrate multi-step workflows — that's the agent's job.

Direct model/API access from Augur code is the exception, not the product model. It requires explicit user approval in the governing ADR, command, or config, a clear credential boundary, and a reason native-agent handoff is not the right execution shape.

## Three Trigger Sources

All three produce the same result: an AI client session running.

| Trigger | How the session starts | What happens inside |
|---------|----------------------|---------------------|
| **CLI** | Already running — user types a command | Agent calls MCP tools directly |
| **Web (Dashboard)** | Dashboard dispatches via `useActionRunner({dispatch: 'ide'})`, opens/connects to AI client | Same agent, same MCP tools. Dashboard opened the session. |
| **Daemon / Nightly** | Daemon triggers a scheduled AI client session | Same agent, same MCP tools. Daemon triggered the session. |

## Why This Matters

1. **Stateless MCP tools** — tools don't need background threads, job queues, or process management. They do one thing and return.
2. **Agent handles intelligence** — classification, summarization, parallelism decisions all happen at the native AI-client agent level where the LLM is already available. No need to plumb hidden LLM access into MCP tools.
3. **Unified execution path** — the same code path runs regardless of trigger source. No "this works from CLI but not from dashboard" bugs.
4. **Batch is natural** — when the agent receives "process 100 files", it decides how to parallelize (Claude's batch command, parallel tool calls, sequential). The MCP tool just needs to handle single items; the agent handles the batch.

## Anti-Patterns

These all violate the execution model:

| Anti-pattern | Why it's wrong | Correct approach |
|-------------|---------------|------------------|
| Background threads in MCP server | MCP server is a subprocess of the AI client, not a long-running service | Agent orchestrates, MCP tools are synchronous |
| Daemon-owned job queue | Creates a separate executor outside AI client sessions | Daemon triggers an AI client session that processes the queue |
| `spawn`/`exec` for processing | Bypasses the agent + MCP architecture | Call an MCP tool instead |
| MCP tool deciding parallelism | Tool doesn't know the agent's context or capabilities | Return results, let the agent decide |
| Dual executor model | "Agent processes when active, daemon processes when not" splits responsibility | One model: always an AI client session |
| Hidden direct model call in MCP/dashboard/daemon code | Moves reasoning and credentials out of the native AI client | Use agent handoff, or document an explicit approved exception |

## Where This Is Enforced

- **AGENTS.md / CLAUDE.md / CODEX.md Rule 11**: Dashboard data flows through MCP and never owns direct local execution or LLM execution
- **AGENTS.md / CLAUDE.md / CODEX.md Rule 19**: Agents own judgment and orchestration; MCP tools own atomic operations; daemons schedule only
- **Dispatch escalation pattern** (`docs/references/dispatch-escalation-pattern.md`): Three tiers that all route to agent sessions
- **LLM-assisted MCP pattern** (`docs/references/llm-assisted-mcp-pattern.md`): Mode 1 (inside AI client) vs Mode 2 (spawns CLI session) — even Mode 2 creates an AI client session

## Applying to New Features

When designing a new feature, ask:
1. **Who orchestrates?** → The AI agent. Always.
2. **What do the MCP tools do?** → Atomic operations. Read, write, extract, index, query.
3. **Where does intelligence happen?** → In the agent. Classification, summarization, decision-making.
4. **How does batch work?** → MCP tool handles one item. Agent handles many items by calling the tool multiple times, with parallelism it decides.
5. **How does the dashboard trigger it?** → `dispatch: 'ide'` → AI client session → same agent, same tools.
