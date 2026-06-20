---
name: augur-core
x-augur-type: skill
x-augur-group: augur_core
x-augur-release: mvp
x-augur-license: MIT
description: Core command pack for session control, knowledge capture, focus management,
  local-mode operations, and agent orchestration. Owns the small set of high-frequency
  workflows that span all skills and do not fit inside any single domain skill boundary.
x-augur-tags:
- core
- command-pack
x-augur-commands:
- id: airplane
  type: workflow
  visibility: core
  description: Toggle airplane mode and inspect local backend readiness
- id: ask
  type: workflow
  visibility: core
  description: Ask your second brain with reflective context, optional retention, and
    structured index search (absorbs /search)
- id: keep
  type: workflow
  visibility: core
  description: Capture or persist anything — unified /note + /save surface
- id: focus
  type: workflow
  visibility: core
  description: Narrow active context and tools to a specific skill
- id: orchestration
  type: workflow
  visibility: core
  description: Coordinate multi-agent execution, backlog dispatch, and chain-based
    workflows
- id: project
  type: workflow
  visibility: core
  description: Current-folder project router for init, status, project-scoped ask,
    keep, skillify, routines, ADR, dev, and sweep work
- id: workflows
  type: workflow
  visibility: ops
  description: Inspect and validate cross-skill workflow definitions
- id: freeze
  type: workflow
  visibility: core
  description: Restrict write operations to a specific directory for the current session
- id: local
  type: workflow
  visibility: core
  description: Manage the local Ollama backend, models, and client routing overrides
- id: kill-augur
  type: workflow
  visibility: core
  description: Force-stop Augur MCP servers and the dashboard when the runtime is
    wedged and needs a clean restart
- id: orch-audit
  type: workflow
  visibility: ops
  description: Audit context-window usage and load the orchestration audit workflow
    in isolated context
- id: discover
  type: workflow
  visibility: core
  description: Print the Augur capability manifest for CLI and agent bootstrapping
---

# Augur Core

Internal command pack for the small set of core session-control workflows that do
not need separate top-level skill boundaries. These commands are the primary
day-to-day interface for knowledge capture, retrieval, project work, and runtime
management across every other Augur skill.

## Commands

| Command | Purpose |
|---------|---------|
| `/ask` | Second-brain query with reflective context and structured index search |
| `/keep` | Capture or persist anything — unified note/save surface |
| `/project` | Current-folder router for init, status, ADR, dev, and sweep work |
| `/focus` | Narrow active context and tools to a specific skill |
| `/discover` | Print the Augur capability manifest for CLI and agent bootstrapping |
| `/airplane` | Toggle offline/airplane mode and inspect local backend readiness |
| `/freeze` | Restrict write operations to a specific directory for the session |
| `/local` | Manage the local Ollama backend and client routing overrides |
| `/orchestration` | Coordinate multi-agent execution and chain-based workflows |
| `/orch-audit` | Audit context-window usage in isolated context |
| `/kill-augur` | Force-stop MCP servers and dashboard when the runtime is wedged |
| `/workflows` | Inspect and validate cross-skill workflow definitions |

Full command contracts live under `commands/`, one Markdown file per command id.

## Workflow

Use augur-core commands for all high-frequency session tasks before reaching into
domain skills. The typical session process:

- Step 1: `/ask` to retrieve relevant memory, vault entries, or index records.
- Step 2: `/keep` to capture new information from the conversation.
- Step 3: `/project` for any current-directory project management needs (ADR, dev cycle).
- Step 4: `/focus <skill>` to narrow context when a single domain skill is the target.
- Step 5: `/discover` to refresh the agent's view of available capabilities after skill changes.

## Examples

```bash
# Ask the second brain about a recent architectural decision
/ask "what was the vault reorg decision?"

# Capture a durable note to the vault
/keep "ADR-802 removed hubs; use x-augur-dashboard-pages instead"

# Start project work in the current directory
/project status

# Switch to offline mode with local Ollama backend
/airplane on

# Force a clean restart when MCP or the dashboard is wedged
/kill-augur
```

## References

- Command bodies: `commands/` (one `.md` per command id) — references/session-control.md for multi-step context patterns
- Session control guide: `docs/agent-topics/WORKFLOWS.md`
- Context management: `docs/agent-topics/CONTEXT.md`
- Path resolution: `src/config/paths.py`

## Constraints

- These commands are session-scoped; they do not own persistent state beyond what
  they delegate to the vault, runtime, or domain skills.
- `/ask` absorbs the retired `/search` command (ADR-766 consolidation).
- `/keep` absorbs the retired `/note` and `/save` commands.
- `/project` is a router; domain sub-commands dispatch to the owning skill.
