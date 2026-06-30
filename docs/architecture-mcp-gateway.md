# The Connection Layer (MCP Gateway, sync_agents, CLI, Plugin Packages)

The Connection Layer is every channel by which the effective [Harness](./architecture-overview.md#the-harness) reaches your AI clients. Augur resolves brain layers (Global/User/Team/Project), computes the effective harness, and projects client-native output for each supported AI client. The same MCP server, vault-backed memory, and local execution boundary are shared by every client in the active session.

This document specifies the seven channels of the Connection Layer.

> Filename note: this doc is named `architecture-mcp-gateway.md` for URL stability with the public release allowlist. Its scope is broader than MCP — it covers every channel the Harness uses to reach a client. The MCP server is one of those channels; not the only one.

## The Connection Layer in one diagram

```
              Brain layers: Global + User + Team + Project
                                     │
              Canonical sources: agent rules, skills, commands, agents,
                       MCP policy, memory/profile
                                     │
                            Connection Layer
                                     │
   ┌──────────────┬──────────────┬───┴────┬──────────────┬──────────────┬─────────────┐
   │              │              │        │              │              │             │
 MCP        sync_agents      Augur CLI  Plugin      Hooks sync    Settings sync   Reverse
 server      (per-client     (shell      package     (cross-agent  (per-client    direction
 (atomic     instruction      entry      adapters    git hooks +    config gen)   (clients
 tool       files)           point)      (effective  per-client                  write back
 surface)                                source →    tool hooks)                  to vault)
                                         packages)
   │              │              │        │              │              │             │
   ▼              ▼              ▼        ▼              ▼              ▼             ▼
 Claude Code   Codex CLI   Gemini CLI   Cursor       Copilot     (Antigravity, Windsurf,
                                                                  OpenCode, Cline)
```

## 1. MCP server

The local MCP servers under `src/mcp/` — `augur_core` and `augur_framework` (each a Python module sharing `src/mcp/augur_shared/`), plus `augur-vault` and `augur-ingest` — expose every Augur skill as atomic tools callable from any MCP-aware client. This is the shared execution surface — the "wrapping all five layers" callout from the Harness model.

Key properties:
- **One trust boundary**: every client connects to the same local servers.
- **Skill-declared tool surface**: skills declare their MCP tools in SKILL.md frontmatter (`x-augur-mcp-tools`); the server discovers them dynamically.
- **Dashboard parity**: Dashboard data flows through this same MCP server — there is no parallel REST API for skill data (see ADR-490 for the dashboard-MCP boundary).
- **Unified history**: every tool call goes through one path, so the audit trail is complete regardless of whether the trigger was a dashboard click, a CLI invocation, or an AI-client agent command.
- **No hidden reasoning layer**: MCP tools do not become the LLM. If a tool needs judgment or synthesis, it returns an agent handoff or validates agent-supplied output. Direct model/API access is a rare, explicit exception approved by the governing ADR/command/config.

See the **MCP Server — Implementation Reference** section at the bottom of this doc for the detailed Component Flow, Context-Aware Tool Loading, API Route Pattern, Debugging, and Anti-Patterns.

## 2. sync_agents

`sync_agents` (in `project-brain/capabilities/skills/ai/scripts/sync_agents/`) is the per-client instruction-file generator. It reads the canonical sources (the agent rules, project rules, capability policy) and writes each client's native format:

- **Claude Code**: `CLAUDE.md`, `.claude/skills/`, `.claude/commands/`, `.claude/agents/`
- **Codex CLI**: `CODEX.md`, `AGENTS.md`, `.codex/skills/`, `.codex/prompts/`
- **Gemini CLI**: `.gemini/GEMINI.md`, `.gemini/skills/`, `.gemini/settings.json`
- **Cursor**: `.cursor/rules/augur.mdc`, `.cursor/skills/`, `.cursor/agents/`
- **GitHub Copilot**: `.github/copilot-instructions.md`, `.github/skills/`
- **Also supported**: Antigravity, Windsurf, OpenCode, Cline (each has its own adapter)

This is the Constitution layer of the Harness, in motion.

## 3. Augur CLI

`src/cli.py` is the shell-side entry point. It exposes the skill registry without requiring an AI client to be running — useful for headless operations, scripts, CI, and the daemon. The CLI shares the registry with the MCP server, so a tool callable from Claude Code is also callable from `augur` on the shell.

## 4. Plugin Package Adapters

Per ADR-522 and ADR-553, the package adapters take the effective skill set from the resolved brain layers and produce client-native installable packages. In the current MVP release, those adapters live with the AI skill's `sync_agents` implementation under `project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/` and `project-brain/capabilities/skills/ai/augur/adapters/`.

- **Claude plugin package** (`.claude-plugin/plugin.json`)
- **Codex plugin package** (`.codex-plugin/plugin.json`)
- **Gemini extension**
- **Cowork DXT bundle** — Claude Desktop / Cowork onboarding (see ADR-576)

One install per client, whole project inherits. This is the Plugins layer of the Harness, in motion.

## 5. Hooks sync

Hooks fire deterministically — they're shell, not AI. The Hooks layer of the Harness has two scopes:

- **Cross-agent**: `.githooks/` and `.pre-commit-config.yaml` fire for every client because they're git-time, not tool-time. Pre-commit auto-lint, conflict-marker blockers, dashboard-shortcut guards, worktree-leak detectors. One commit, every agent honored the rule.
- **Per-client**: tool-time enforcement. `.claude/settings.json` PreToolUse/PostToolUse hooks; `.codex/hooks.json` equivalent. These let Claude Code or Codex block a destructive command before it runs.

Cross-agent hooks are the default because they enforce uniformly. Per-client hooks fill in tool-time gaps that git can't see (e.g., a destructive command that doesn't touch the filesystem).

## 6. Settings sync

Generated, not hand-authored:

- `.claude/settings.json` (Claude Code)
- `.codex/config.toml` (Codex CLI)
- `.cursor/mcp.json` (Cursor)
- `.gemini/settings.json` (Gemini CLI)
- `.windsurf/mcp.json` (Windsurf)

The settings sync writes the MCP server config, hook config, and per-client preferences. The user never hand-edits these — they regenerate from the effective harness sources.

## 7. The reverse direction (shared memory)

The Connection Layer is bidirectional. Clients write to the MCP server, the MCP server writes to the vault (your local second brain), and the vault is shared back across every client in the same session.

A `/ask` query in Claude Code retains its answer in the vault. The next session in Codex sees the same retained answer. The wiki compounding signal fires from one client's session; the next client's session loads the updated wiki context at the next session start.

This is what makes "same memory across clients" real — not a marketing claim, but the result of every client writing to and reading from the same local vault through the same MCP server.

---

# MCP Server — Implementation Reference

The remainder of this document is the implementation reference for channel 1 (MCP server). It pre-dates the Connection Layer reframe and is preserved as the canonical detailed reference for the MCP-specific channel.

## Implementation map

The MCP layer is a small set of local servers, not one monolith:

| Server | Launch | Surface |
|---|---|---|
| `augur-core` | `python -m augur_core` (`src/mcp/augur_core/`) | core session, brain, and read tools |
| `augur-framework` | `python -m augur_framework` (`src/mcp/augur_framework/`) | broader framework and infrastructure tools |
| `augur-vault`, `augur-ingest` | `config/system/mcp_servers.yaml` | vault access and inbox ingestion |

All servers share `src/mcp/augur_shared/` — the SDK, the `mcp_tool_interceptor`, the unified logger, and `tool_controller.py`. Each client's MCP config is generated from `config/system/mcp_servers.yaml` by the settings sync, with `PYTHONPATH` covering the project root and `src/mcp`.

Tools are discovered, not hand-wired: a skill declares its tools in `SKILL.md` frontmatter (`x-augur-mcp-tools`) and the owning server registers them. Which tools reach which client — or the dashboard — is governed by `config/system/capability_exposure.yaml`, not by a dashboard page; see [architecture-capability-exposure.md](./architecture-capability-exposure.md).

## Dashboard data path

The dashboard owns no parallel tool registry and no per-page tool loading. Every dashboard data call posts `{tool, args}` to `apps/dashboard/app/api/mcp/tool/route.ts`, which calls `callMCPTool` server-side and returns JSON. The dashboard has exactly two surfaces — Browse and Workspace — so there is no `/brain` or `/workforce` page driving tool context (see [architecture-dashboard.md](./architecture-dashboard.md)).

## Logging

Every tool call is logged centrally under `get_logs_dir()`:

```bash
python -c "from pathlib import Path; from src.config.paths import get_logs_dir; print(Path(get_logs_dir()) / 'mcp.log')"
```

## API route pattern

Dashboard API routes forward a single MCP tool call — they do not run workflows or scripts directly:

```typescript
// apps/dashboard/app/api/mcp/tool/route.ts forwards { tool, args } to callMCPTool
const result = await mcpClient.callTool('skill_action', params);
```

The former `lib/server/pythonRunner.ts` "python runner" transition pattern has been removed; routes that need Python go through an MCP tool.

## Anti-patterns

Bypassing MCP loses logging, context, and the single trust boundary:

```typescript
// WRONG — direct subprocess, no logging, no context
import { spawn } from 'child_process';
spawn('python', ['script.py']);

// RIGHT — through MCP
const result = await mcpClient.callTool('skill_action', params);
```

A server-side `spawn`/`exec`/`fs` call in the dashboard is rule-11 debt unless it carries an `@spawn-exempt`/`@fs-exempt` marker (ADR-817); see [architecture-dashboard.md](./architecture-dashboard.md).

## Related documents

- ADR-005: MCP Execution Gateway
- ADR-490: dashboard ↔ MCP boundary
- [architecture-capability-exposure.md](./architecture-capability-exposure.md): which tools surface where
