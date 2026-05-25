# sync_agents Architecture

`sync_agents` is the projection engine that turns Augur's canonical rules, skills, commands, subagents, memory, hooks, and MCP server manifest into client-native files for Claude Code, Codex, Gemini, Cursor, Copilot, and other supported clients.

In the layered architecture, `sync_agents` consumes the effective brain stack rather than a single source directory. Global, User, Team, and Project capabilities are resolved with most-specific-wins precedence, then emitted into the client surfaces each vendor expects. Team is a commercial tier; OSS projection documents the same architectural slot without claiming enterprise governance is bundled into the personal runtime.

```
Brain stack (Global/User/Team/Project)
  -> agent rules
  -> capabilities/skills/*/SKILL.md
  -> commands/*.md
  -> agents/*.md
  -> config/system/mcp_servers.yaml
  -> config/system/capability_exposure.yaml
          |
          v
project-brain/capabilities/skills/ai/scripts/sync_agents/
  engine.py -> adapters/* -> generators.py -> skill_sync.py
          |
          +--> Claude Code: CLAUDE.md, .claude/skills, .claude/agents
          +--> Codex: CODEX.md, AGENTS.md, .codex/skills, .codex/agents
          +--> Gemini: .gemini/GEMINI.md, .gemini/skills, settings
          +--> Cursor: .cursorrules, .cursor/rules, .cursor/agents
          +--> Copilot: .github/copilot-instructions.md, skill packs
```

## Source to renderer to output

The effective source set is client-neutral. The renderer layer understands Augur concepts such as skills, commands, subagents, MCP servers, memory, and capability policy. Adapters translate those concepts into each client's native files.

The main entry point is `PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents`. The package supports `sync all`, `sync agents`, `sync skills`, `sync prompts`, `sync commands`, `check`, `fix`, `validate`, `clean`, and hygiene modes.

The generated client files named in this document are runtime outputs. The MVP release evidence is the generator source, adapters, policies, and tests; an installed workspace regenerates the client-native files for the user's local clients.

## Per-client output mapping

Each adapter owns its managed files. Examples:

| Client | Rules and instruction outputs | Capability outputs |
|---|---|---|
| Claude Code | `CLAUDE.md`, `.claude/skills/`, `.claude/agents/` | settings, commands, plugin cache integration |
| Codex | `CODEX.md`, repo `AGENTS.md`, global `~/.codex/AGENTS.md` | `.codex/config.toml`, `.codex/skills/`, `.codex/prompts/`, `.codex/agents/` |
| Gemini | `.gemini/GEMINI.md`, `.gemini/skills/` | `.gemini/settings.json`, extension support |
| Cursor | `.cursorrules`, `.cursor/rules/` | Cursor MCP and agent surfaces |
| Copilot | `.github/copilot-instructions.md` | Copilot skill packs |

Additional adapters exist for Claude Desktop, Cline, Windsurf, OpenCode, Kimi, Antigravity, Cowork, Codex plugin, and Gemini plugin targets.

## Generated vs hand-edited boundary

Generated files are marked and should not be hand-edited. The canonical edits happen in source docs, source skills, command docs, agent definitions, and config manifests. Running `sync_agents` rewrites the generated targets.

This boundary is what prevents instruction drift. A user or agent can inspect a client-specific file, but durable changes belong in the brain-owned sources that feed all clients.

## Hooks sync

Cross-agent git hooks and per-client tool hooks are part of the Harness. Git hooks live at repo level so every client gets the same commit-time enforcement. Per-client hooks fill tool-time gaps where a client can block a command before it runs.

`sync_agents` keeps hook and instruction surfaces aligned so a policy change in the source rules reaches the active clients.

## Settings sync

Client settings derive from `config/system/mcp_servers.yaml`, path helpers, and adapter-specific formatters. The MCP entries include the client id and a `PYTHONPATH` that exposes `project-brain`, the repo root, and `src/mcp`.

Codex, for example, receives worktree-aware MCP entries in `~/.codex/config.toml` and project-local `.codex/config.toml` settings. The adapter also keeps the local plugin marketplace entry enabled.

## Reverse direction

The flow is not only source to clients. Clients call MCP tools, MCP tools write to the vault, and the vault becomes shared memory for later clients. Imported plugin agents and external skills can also be discovered and distributed when allowed by policy.

Reverse writes still go through bounded surfaces. Client-specific generated folders are not treated as canonical user edits.

## Instruction precedence

Repository-local generated instructions take precedence over global bootstrap files. Global files should be small and should tell the client to prefer repo-local `CODEX.md`, `AGENTS.md`, `CLAUDE.md`, or equivalent project files when present.

This lets one machine have Augur installed globally while each checked-out Augur worktree still carries the rules that match that branch.

## Implementation pointers

- `project-brain/capabilities/skills/ai/scripts/sync_agents/__init__.py` defines the CLI contract.
- `project-brain/capabilities/skills/ai/scripts/sync_agents/engine.py` orchestrates adapters.
- `project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/` contains per-client renderers.
- `config/system/mcp_servers.yaml` is the MCP topology source.
- See [architecture-mcp-gateway.md](./architecture-mcp-gateway.md) for the broader Connection Layer.
