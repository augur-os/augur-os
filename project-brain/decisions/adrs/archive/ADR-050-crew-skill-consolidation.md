---
status: Implemented
date: '2026-02-07'
deciders:
- Augur Core Team
related:
- ADR-046 (Claude Code Crew Orchestration Bridge)
- ADR-022 (Plugin Standardization)
hub: null
tags:
- crew
- skill
- consolidation
- script
- absorption
superseded_by: null
---

# ADR-050: Crew Skill Consolidation — Script Absorption & Leftover Cleanup

## Context

After ADR-046 unified crew skills with Claude Code orchestration, two legacy skill boundaries remain misaligned:

1. **`librarian` (services/knowledge)** contains scripts that are crew-level work — `audit_skills.py`, `generate_api_docs.py`, `knowledge_manager.py` — executed by chain steps referencing `librarian:*` as if it were a crew agent. But services are not crew agents. They don't have subagent profiles, aren't routed through the chain bridge's agent resolution, and shouldn't need aliases.

2. **`webapp-testing` (validator in crew)** contains scripts that belong to other crew skills — `ui_qa.py`, `capture_ui.py`, `visual_regression.py`, `with_server.py` belong in `frontend`; `precommit_hooks.py` belongs in `devops`. The validator SKILL.md still carries the old name `webapp-testing`.

Additionally, two empty package shells remain from the pre-monorepo era:
- `plugins/claude-plugins/augur-webapp-testing/` — empty, code already in validator
- `plugins/claude-plugins/augur-librarian/` — duplicate of services/knowledge, scripts being absorbed

Chain YAMLs reference the old agent names (`librarian:*`, `webapp-testing:*`), and `chain_executor.py` SCRIPT_PARAM_MAPPING needs updating.

## Decision

Absorb scattered scripts into their natural crew skill owners, update all chain references, and delete leftovers. No alias layer — fix at the source.

### Scripts Absorbed Into Crew

| Script | From | Into Crew Skill | Chain Action Rename |
|--------|------|-----------------|---------------------|
| `audit_skills.py` | knowledge (services) | **plugins** (crew) | `librarian:audit_skills` → `plugins:audit_skills` |
| `generate_api_docs.py` | knowledge (services) | **developer** (crew) | `librarian:generate_api_docs` → `developer:generate_api_docs` |
| `knowledge_manager.py` | knowledge (services) | **analyst** (crew) | `librarian:knowledge_manager` → `analyst:knowledge_manager` |
| `ui_qa.py`, `capture_ui.py`, `visual_regression.py`, `with_server.py` | validator (crew) | **frontend** (crew) | `webapp-testing:ui_qa` → `frontend:ui_qa` |
| `precommit_hooks.py` | validator (crew) | **devops** (crew) | `webapp-testing:precommit_hooks` → `devops:precommit_hooks` |

### What Stays (No Alias Needed)

| Thing | Where | Rationale |
|-------|-------|-----------|
| RAG scripts (`index_docs`, `rag_search_cli`, etc.) | services/knowledge | Not a crew agent. Chain executor calls it as a service directly. |
| `verify_changes`, `enforce`, etc. | validator (crew) | Already a crew agent, no rename needed. |

### Leftovers Deleted

| Leftover | Action |
|----------|--------|
| `plugins/claude-plugins/augur-webapp-testing/` | Delete — empty shell, all code already in validator |
| `plugins/claude-plugins/augur-librarian/` | Delete — duplicate of services/knowledge |
| `plugins/ai/skills/knowledge/scripts/audit_skills.py` | Delete after copy to plugins crew |
| `plugins/ai/skills/knowledge/scripts/generate_api_docs.py` | Delete after copy to developer crew |
| `plugins/ai/skills/knowledge/scripts/knowledge_manager.py` | Delete after copy to analyst crew |
| `audit_structure.py` in validator | Delete — thin wrapper, consolidate into `enforce.py` |

### Fixes

| Item | Fix |
|------|-----|
| validator `SKILL.md` | Change `name: webapp-testing` → `name: validator` |

### Chain YAMLs Updated

All chain YAML files referencing `librarian:*` and `webapp-testing:*` get their agent name + action updated to point to new crew skill owners. `chain_executor.py` SCRIPT_PARAM_MAPPING updated accordingly.

### Implementation Steps

1. Copy scripts to their new crew homes (preserving git history with `git mv` where possible)
2. Update imports and path references within moved scripts
3. Update chain YAMLs to use new agent names
4. Update `chain_executor.py` SCRIPT_PARAM_MAPPING for renamed agents
5. Fix validator SKILL.md naming
6. Consolidate `audit_structure.py` into `enforce.py`
7. Delete the leftovers (empty plugins, original script locations)
8. Regenerate artifacts (`sync_agents.py`)
9. Run tests to verify nothing broke

## Consequences

### Positive

- Every script lives in the crew skill that conceptually owns it
- No ambiguity between services (called directly) and crew agents (routed through chain bridge)
- No alias layer needed — clean, direct references throughout
- Empty legacy plugins removed
- validator finally has its correct name

### Negative

- One-time churn across chain YAMLs and chain_executor mappings
- Git history for moved scripts requires `git log --follow` to trace

### Neutral

- RAG/knowledge service scripts untouched — they were correctly placed all along
- Validator's core scripts (`verify_changes`, `enforce`) stay put
- Generated artifacts (`.claude/agents/`, `.claude/commands/`) regenerated automatically

## Alternatives Considered

### Alternative 1: Alias Layer in Chain Bridge

Add an alias map (`librarian:audit_skills` → `plugins:audit_skills`) in the chain bridge so old YAML files keep working. Rejected because it adds indirection, makes the system harder to reason about, and perpetuates the wrong mental model that `librarian` is a crew agent.

### Alternative 2: Keep Scripts in Place, Just Fix Names

Rename the chain references but leave scripts in their current locations. Rejected because the whole point is that crew scripts should live in crew skills — having the code in services/knowledge while the chain bridge thinks it belongs to `plugins` creates a lie.

### Alternative 3: Create a Dedicated `librarian` Crew Skill

Promote librarian to a full crew agent. Rejected because it would duplicate services/knowledge capabilities and the scripts naturally belong to existing crew skills (plugins for auditing, developer for docs, analyst for knowledge management).

## References

- ADR-046: Claude Code Crew Orchestration Bridge
- ADR-022: Plugin Standardization
- `plugins/orchestration/skills/executor/scripts/chain_executor.py` — SCRIPT_PARAM_MAPPING
- `plugins/dev/skills/validator/SKILL.md` — needs name fix
- `plugins/ai/skills/knowledge/scripts/` — source of librarian scripts
