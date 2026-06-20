---
status: Implemented
date: '2026-02-07'
deciders:
- User
- Claude
related: []
hub: null
tags:
- slash
- command
- restructure
superseded_by: null
---

# ADR-053: Slash Command Restructure

## Context

58 slash commands were exposed across the augur — overwhelming, inconsistent naming. Chains had `chain-` prefix, swarms had `swarm-`, but 28 workflows had no prefix and mixed daily-use commands with internal tooling. Users couldn't find the commands they needed in autocomplete.

## Decision

Restructure all slash commands into a tiered system:

### Tiers

| Tier | Prefix/Rule | Count | Purpose |
|------|-------------|-------|---------|
| **Core** | none | 12 | Daily use, short memorable names |
| **Ops** | `ops-` | 8 | Maintenance & DevOps |
| **Meta** | none | 2 | `/chain` and `/swarm` dispatchers |
| **Hidden** | `_` prefix on filename | 8 | Reference docs, internal, rare |

### Core Commands (12)

| Command | Original | Description |
|---------|----------|-------------|
| `/build` | `/rebuild-ui` | Clean caches, rebuild UI |
| `/check` | `/ci-check` | Run CI pipeline locally |
| `/coverage` | `/run-coverage` | Test coverage analysis |
| `/debug` | `/debug-protocol` | 6-phase debugging protocol |
| `/deploy` | `/sync-repos` | Sync and push repositories |
| `/fix` | `/file-bug` | File a bug report |
| `/learn` | `/learn` | Capture learnings |
| `/nightly` | `/nightly` | Full nightly CI cycle |
| `/reload` | `/reload-dashboard` | Quick dashboard reload |
| `/review` | `/code-review` | Deep code review |
| `/start` | `/load-context` | Load project context |
| `/tidy` | `/review-markers` | Review TODO markers |

### Ops Commands (8)

| Command | Original |
|---------|----------|
| `/ops-audit` | `/dependency-audit` |
| `/ops-cleanup` | `/structure-cleanup` |
| `/ops-docs` | `/documentation-sync` |
| `/ops-kill` | `/kill-augur` |
| `/ops-perf` | `/performance-profiling` |
| `/ops-rollback` | `/rollback-recovery` |
| `/ops-sync` | `/sync-agents` |
| `/ops-debt` | `/tech-debt-triage` |

### Meta Commands (2, replace 29)

| Command | Replaces | Behavior |
|---------|----------|----------|
| `/chain` | 23 `chain-*` commands | Lists chains by category; `/chain <name>` executes |
| `/swarm` | 6 `swarm-*` commands | Lists presets; `/swarm <name>` executes |

### Hidden Commands (8)

Still work if typed directly, but use `_` prefix on filename to exclude from autocomplete:

`/git-guidelines`, `/thread-hardening`, `/ai-bridge-update`, `/gitignore-inspect`, `/memory-sync`, `/retrospective`, `/onboarding`, `/guide-task-lifecycle`

### Implementation

- Workflow YAML frontmatter gets `visibility: core|ops|hidden` and optional `alias:` fields
- `discovery.py` extracts metadata via `extract_workflow_metadata()`
- `sync_agents.py` applies alias renaming, `_` prefix for hidden, generates meta-commands
- Non-Claude adapters filter out hidden workflows entirely
- `_generate_workflows_table()` shows tiered table in CLAUDE.md

## Consequences

### Positive

- 58 commands → ~22 visible (62% reduction)
- Consistent naming: Core = short verbs, Ops = `ops-` prefix
- `/chain` and `/swarm` are discoverable dispatchers instead of 29 individual commands
- Hidden commands still accessible for power users

### Negative

- Users familiar with old names need to learn new aliases (mitigated by underscore aliases)
- Meta-commands add one extra step to execute a specific chain/swarm

### Neutral

- Source workflow files in `data/ai-bridge/agent-workflows/` keep their original names
- Only the generated output (`.claude/commands/`) uses the new naming

## Alternatives Considered

### Alternative 1: Flat renaming without tiers

Rename all commands but keep them all visible. Rejected because 28 commands is still too many for autocomplete.

### Alternative 2: Nested command groups

Use `/ops/kill` style nesting. Rejected because Claude Code slash commands don't support `/` in names.

## References

- ADR-046: Claude Code Crew Orchestration Bridge (introduced chain-* and swarm-* commands)
- `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` (generator)
- `plugins/ai/skills/ai_bridge/augur/discovery.py` (metadata parsing)
