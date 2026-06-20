---
status: Implemented
date: 2026-03-23
deciders:
  - Gur Sannikov
related:
  - ADR-479
  - ADR-430
  - ADR-463
hub: null
tags: [skills, schema, enforcement, agents, standard]
superseded_by: null
---

# ADR-480: Skill Schema Enforcement & Agents Migration

## Context

After ADR-479 flattened all skills into `skills/` at project root, the internal folder structure within each skill was inconsistent: 7 skills used `docs/` instead of `references/`, 74 had `data/` at root, 72 had `augur/seed/` instead of `assets/seeds/`, and 14 agent definitions were disconnected in `.claude/agents/`. No enforcement prevented drift.

The Agent Skills open standard (agentskills.io) defines a portable schema. Claude Code extends it with commands, agents, and plugins. Augur needed to align with both while keeping Augur-specific content separated.

## Decision

### Two-layer skill schema

**Standard layer (portable):** `SKILL.md` (required), `commands/`, `references/`, `scripts/`, `assets/`, `examples/`, `modules/`

**Augur-native layer:** `augur/dashboard/` (Next.js pages only: .tsx/.ts/.css/.js/.jsx), `augur/data/` (runtime config), `augur/tests/`, `augur/lib/`

### Banned patterns

- Root: `docs/` (use `references/`), `data/` (use `augur/data/` or `assets/`), `lib/` (use `scripts/` or `augur/lib/`), `.augur-plugin/`, `node_modules/`, `__pycache__/`
- Inside `augur/`: `seed/` (use `assets/seeds/`)

### Pre-commit enforcement

Extended `.github/scripts/validate_skill_structure.py` with schema validation. Blocks commits with violations.

### Agents at project root

Agents moved from `.claude/agents/` to `agents/` at project root. Stub generator syncs back to `.claude/agents/` with `AUGUR-GENERATED` marker.

## Consequences

### Positive

- Every skill follows a documented, enforceable structure
- Portable dirs work in any Agent Skills-compatible client
- Seeds in `assets/seeds/` are usable without Augur
- Agents collocated with skills as a plugin (per Claude Code plugin spec)
- Pre-commit prevents schema drift

### Negative

- 153 directories migrated in bulk (large commit)
- `augur/data/` ban from ADR-430 superseded (may confuse readers of old ADR)

### Neutral

- Existing valid structures (commands/, modules/) unchanged
- Dashboard mount paths unaffected (reads from augur/dashboard/)

## References

- Spec: `docs/superpowers/specs/2026-03-23-skill-schema-enforcement-design.md`
- Plan: `docs/superpowers/plans/2026-03-23-skill-schema-enforcement.md`
- [Agent Skills Standard](https://agentskills.io/specification)
- [Claude Code Skills](https://code.claude.com/docs/en/skills)
- [Claude Code Plugins](https://code.claude.com/docs/en/plugins)

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - "skills/*/docs/ → skills/*/references/"
    - "skills/*/data/ → deleted (empty) or skills/*/assets/"
    - "skills/*/augur/seed/ → skills/*/assets/seeds/"
    - "skills/ai_bridge/lib/ → skills/ai_bridge/scripts/"
    - ".claude/agents/*.md → agents/*.md (canonical) + .claude/agents/ (generated)"
  patterns_deprecated:
    - "docs/ at skill root"
    - "data/ at skill root"
    - "lib/ at skill root"
    - "augur/seed/ directory"
    - ".augur-plugin/ directory"
  files_affected:
    - ".github/scripts/validate_skill_structure.py (extended)"
    - "scripts/generate_client_stubs.py (agent sync added)"
    - "docs/agent-topics/agent-rules.md (rule 19 added)"
    - "skills/evolve/references/pipeline-steps.md (scaffold updated)"
    - "skills/auto-skill-structure/SKILL.md (checks updated)"
```
