<!--
⚠️  AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
Source: docs/agent-topics/AGENTS.md
Generator: project-brain/capabilities/skills/ai/scripts/sync_agents/__init__.py
-->
# Agents & Mode System

> **When to load**: Load this doc when working in agent teams, checking mode system, or understanding agent tiering.

See also [architecture-agents.md](../architecture-agents.md) for the contributor-facing agent coordination architecture.

## Terminology

| Term | Definition |
|------|------------|
| **Augur** | This project -- a personal knowledge/automation system ("second brain") |
| **Skill** | A modular capability with its own SKILL.md, scripts, and optional UI |
| **Bundle** | A collection of related skills (e.g., `adaptive`, `ai`, `career`, `core`) |
| **Action** | A trigger defined in skill assets or vault overrides (`assets/actions/*.yaml`, external data `actions/*.yaml`) with a dispatch mode (fire, oneshot, ide, modal) |
| **App** | A dashboard section grouping related skills (sidebar label, formerly "Hub"). Internal code still uses "hub" as the routing/config concept. |
| **Dev Mode** | Building/enhancing the augur (writing code, creating skills, modifying actions) |
| **Operation Mode** | Using the augur for life tasks (health queries, career prep, email triage) |
| **Mode-Aware** | Components that filter themselves based on current mode |
| **Context Commands** | Slash commands filtered by current dashboard page and mode |

## Mandatory Session Protocol

**At the start of EVERY session, you MUST:**
1. **Load Context**: Check Augur MCP status by calling `list-mcp-tools` through the active Augur MCP server.
2. **Review Capabilities**: See available tools from MCP tool listing.
3. **Check Mode**: Verify if you are in Dev or Operation mode via `get-chat-session` when that tool is available.

## Mode System (Bundle = Mode)

The augur operates in two modes. Project/team skills live in `project-brain/capabilities/skills/` and private user skills live in the configured private-vault `skills/` root. Mode is derived from the skill's bundle/group assignment, not the directory path:

| Group | Mode | Purpose | Examples |
|-------|------|---------|----------|
| dev | **Dev** | Skills that BUILD the brain | developer, advisor, validator, devops |
| orchestration | **Dev** | Workflow orchestration | workflows, devops |
| ai | **Operation** | Horizontal capabilities | knowledge, organizer, daemon, channels |
| career | **Operation** | Career management | career, coach |

### Two-Level Dev Gating

Dev pages require BOTH conditions:
1. **Core plugin enabled** (user has dev capabilities installed)
2. **Dev mode toggle ON** (user actively wants to see dev features)

```
Dev Plugin Disabled -> No dev pages, no toggle button
Dev Plugin Enabled + Toggle OFF -> Operation mode (dev pages hidden)
Dev Plugin Enabled + Toggle ON -> Dev mode (all pages visible)
```

### Mode-Aware Filtering

| Component | Operation Mode | Dev Mode |
|-----------|---------------|----------|
| **Navigation** | Hides dev pages (/observe, /dev) | Shows all pages |
| **Action Hub** | Operation buttons only | All buttons |
| **Actions Menu** | Hidden | Visible |
| **Commands** | Operation commands only | All commands |
| **MCP `get-context`** | Filters dev items | Returns all items |

## Agent Tiering (ADR-019)

| Tier | Cost | Use For |
|------|------|---------|
| Fast (0.1x) | Low | Simple tasks, file reads, quick lookups |
| Standard (1x) | Medium | Balanced work, most implementation tasks |
| Deep (5x) | High | Architecture decisions, security audits |

Auto-escalation triggers move tasks up tiers when complexity is detected.

## Git Commit Protocol for Team Agents (MANDATORY)

**When working as a teammate (spawned via Task with team_name), you MUST commit after completing each task.**

Multiple agents share the same working directory. Uncommitted edits to tracked files are destroyed when any agent (or concurrent session) switches branches or merges.

### Rules
1. **Commit after every task** -- not at the end of all tasks, after EACH one
2. **Stage only your files** -- `git add <specific files>`, never `git add -A` or `git add .`
3. **Conventional commit message** -- `feat|fix|refactor|chore(scope): description`
4. **Never amend** -- always create new commits
5. **Never push** -- only commit locally; the team lead handles push
6. **Never switch branches** -- stay on whatever branch you were started on
7. **If staging fails** (file changed by another agent) -- report conflict to team lead via SendMessage

### When This Applies
- You are a teammate spawned with `team_name` parameter
- You are working alongside other agents in the same repo
- You have write access (not in advisory/read-only mode)

### When This Does NOT Apply
- You are the only agent working (solo session)
- You are in advisory mode (read-only, no file edits)
- The team lead explicitly says "do not commit"

## Context Discipline for Agent Teams

### Subagent Handoffs
- Never forward full conversation history to subagents. Build a focused payload.
- Strip all reasoning traces -- send conclusions and decisions, not the thought process.
- Pass exact file paths, not directory globs.

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

**Related commands**: `/save`
