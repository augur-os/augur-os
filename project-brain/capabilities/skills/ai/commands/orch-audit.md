---
description: Audit context usage across agents — map costs, flag waste, recommend execution modes
visibility: orch
---

# /context-audit

Audit the current project's context allocation across all agent profiles. Maps context cost per agent, flags wasteful file loading patterns, and recommends Agent Teams vs subagent execution mode.

## Usage

- `/context-audit` — Full audit of all agents
- `/context-audit developer` — Audit a specific agent
- `/context-audit "pre-swarm check"` — Full audit with explicit label

## Workflow

1. **Check current usage**: Note the current token consumption from the status bar.

2. **Inventory agent profiles**: Read `.claude/agents/registry.json` to get the full agent list with tiers, models, and capabilities. Categorize each as:
   - **Advisory** (read-only): agents with `mode: advisory` — architect, security, analyst, validator
   - **Executor** (read-write): agents with `mode: executor` — developer, frontend, devops, mcp-app-factory

3. **Estimate context cost per agent**: For each agent:
   - Read the agent profile (`.claude/agents/{name}.md`) and count lines (each line ≈ 4 tokens)
   - Check `max_files` from `registry.json` tier config
   - Identify file loading patterns from the agent's instructions — flag broad globs (`**/*.ts`) vs scoped ones (`src/auth/*.ts`)

4. **Output a context budget table**:

| Agent | Type | Profile (lines) | Max Files | Typical Load Pattern | Risk |
|-------|------|-----------------|-----------|---------------------|------|
| ... | advisory/executor | ... | ... | broad/scoped | low/medium/high |

Risk levels:
- **Low**: < 20 files, scoped globs, advisory mode
- **Medium**: 20-50 files or moderate globs
- **High**: 50+ files or `**/*` patterns

5. **Recommend execution mode per agent**:
   - **Low** context needs → spawn as **subagent** (`Task` tool with focused prompt, `model: haiku`)
   - **High** context needs or sustained reasoning → spawn as **Agent Teams member** (`TeamCreate` + `Task` with `team_name`)
   - Agents that need to debate or exchange findings → **Agent Teams** (they need `SendMessage`)

6. **Suggest optimizations**:
   - Agent profiles that should tighten file scope
   - Agents loading redundant files across dispatches
   - Whether advisory agents can be downgraded to haiku tier
   - MCP context stats via `get-mcp-context-stats` tool if available

7. **Persist audit results**:

Save the audit as a JSON file to `state/context-audits/`:

1. Create directory if missing: `mkdir -p "$(python3 scripts/resolve-runtime-dir.py --state)/context-audits"`
2. Derive filename slug:
   - Scope: `full` for full audit, agent name for filtered (e.g., `developer-only`)
   - Optional user label from `/context-audit "pre-swarm check"` — prepend to slug
   - Examples: `full`, `developer-only`, `full-pre-swarm`
3. Filename: `{YYYY-MM-DD}-{slug}.json` (e.g., `2026-02-11-full-pre-swarm.json`)
4. Slug rules: lowercase, spaces to hyphens, max 40 chars, strip special characters

Write JSON with this schema:
```json
{
  "id": "{filename without .json}",
  "type": "audit",
  "timestamp": "{ISO 8601}",
  "label": "{user label or scope description}",
  "scope": "full|{agent_name}",
  "agent_filter": null,
  "token_usage_estimate": 145000,
  "token_limit": 200000,
  "usage_percent": 72.5,
  "agents": [
    {
      "name": "developer",
      "type": "executor",
      "profile_lines": 120,
      "max_files": 50,
      "load_pattern": "scoped",
      "risk": "medium",
      "recommended_mode": "team_member"
    }
  ],
  "optimizations": ["Optimization suggestions"],
  "summary": "One-line summary of audit results."
}
```

## Notes

- This command reads from `registry.json` — the source of truth for agent configuration
- Run after adding new agents or before complex multi-agent workflows
- Pairs with `/dispatch-subagent` for acting on recommendations
- Audit results are saved to the external state `context-audits/` directory and viewable in the Observe hub Sessions tab
- Related: `python3 project-brain/capabilities/skills/daemon/scripts/mcp_health_check.py` for MCP-level health
