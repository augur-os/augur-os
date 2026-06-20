---
status: Implemented
date: '2026-03-06'
deciders:
- Augur maintainers
related: []
hub: null
tags:
- command
- registry
- parity
- generated
- central
superseded_by: null
---

# ADR-251: Command Registry Parity and Generated Central Views

## Context

Augur command definitions are now decentralized across plugin manifests (`contributions.commands`) and plugin-local command docs. Central agent instruction files (`AGENTS.md`, `CODEX.md`, `CLAUDE.md`) are generated summaries.

Recent command sync runs surfaced drift:
- Commands declared in `augur.yaml` without corresponding `commands/*.md` files.
- Duplicate command entries in generated central summaries when distributed and fallback sources overlap.

This creates a reliability gap:
- Discovery emits warnings and can skip expected commands.
- Generated central files can become inaccurate.
- Teams lose confidence in command inventory and automation behavior.

The architecture target from ADR-163 and plugin decentralization rules is clear: plugin-owned source data with generated central outputs. The missing piece is strict parity enforcement and duplicate prevention.

## Decision

Adopt a strict two-tier model:

1. **Decentralized source of truth (authoring layer)**
   - Command metadata is authored only in plugin manifests:
     - `plugins/{hub}/skills/{skill}/augur.yaml` -> `contributions.commands`
   - Command behavior documentation is authored only in plugin command files:
     - Workflow command: `plugins/{hub}/skills/{skill}/commands/{id}.md`
     - Skill command: `plugins/{hub}/skills/{skill}/commands/{id}/SKILL.md`

2. **Generated central views (distribution layer)**
   - `AGENTS.md`, `CODEX.md`, `CLAUDE.md`, and adapter outputs are generated artifacts only.
   - No manual edits to central command lists.

3. **Mandatory parity and uniqueness gates**
   - Add CI/pre-commit validation that hard-fails on:
     - Manifest command declared without matching source file.
     - Duplicate command IDs across distributed manifests.
     - Invalid command type/visibility combinations.
   - Keep renderer-side dedupe as defensive fallback only, not policy.

4. **Deterministic conflict policy**
   - Project policy becomes: duplicate command IDs are invalid and must fail validation.
   - If global uniqueness becomes too restrictive, move to explicit namespacing (e.g., `{hub}.{skill}.{id}`) as a planned migration, not silent runtime shadowing.

5. **Regeneration contract**
   - Central instruction files must be regenerated from source (`sync_agents.py --rules`) after command changes.
   - CI must fail when generated artifacts are stale.

## Consequences

### Positive

- Prevents declaration/file drift from reaching generated outputs.
- Preserves plugin decentralization while keeping central docs accurate.
- Makes command inventory deterministic across adapters and IDE clients.
- Reduces operational warnings and debugging time.

### Negative

- Introduces stricter CI failures that may block merges until command docs exist.
- Requires migration cleanup for existing drift before fully green CI.

### Neutral

- Central files remain present but become strictly read-only generated artifacts.
- Existing sync pipeline stays in place; governance around it becomes stricter.

## Implementation Order

### Phase 1: Validation Foundations

1. Add `validate_commands` checks for declaration/file parity and duplicate IDs.
2. Integrate checks into CI and pre-commit.

### Phase 2: Drift Cleanup

1. Add missing command source files for all currently declared commands.
2. Run validation and resolve all failures.

### Phase 3: Generator Hardening

1. Keep dedupe in template rendering as a safety net.
2. Ensure generated command counts and lists are derived from validated source only.

### Phase 4: Governance and Docs

1. Document command-authoring contract in workflow/docs.
2. Add “generated-only” warning for central command sections where needed.

## Alternatives Considered

### Alternative 1: Keep central command registry as primary source

Rejected. This conflicts with plugin decentralization and recreates central bottlenecks ADR-163 aims to remove.

### Alternative 2: Allow duplicates and rely on runtime dedupe/shadowing

Rejected. Silent conflict resolution is nondeterministic for authors and causes hidden behavior differences across generated outputs.

## References

- `docs/decisions/ADR-098-unify-commands-and-skills-output.md`
- `docs/decisions/ADR-163-config-decentralization.md`
- `plugins/ai/skills/ai_bridge/scripts/sync_agents/discovery.py`
- `plugins/ai/skills/ai_bridge/scripts/sync_agents/templates.py`

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - function: _get_all_workflow_metadata
      module: plugins.ai.skills.ai_bridge.scripts.sync_agents.discovery
      breaking: false
    - function: _generate_workflows_table
      module: plugins.ai.skills.ai_bridge.scripts.sync_agents.templates
      breaking: false
  patterns_deprecated:
    - grep: "manual edits to AGENTS.md|manual edits to CODEX.md|manual edits to CLAUDE.md"
      replacement: "edit plugin command sources and regenerate via sync_agents"
  files_affected:
    - glob: "plugins/*/skills/*/augur.yaml"
    - glob: "plugins/*/skills/*/commands/**/*.md"
    - glob: "plugins/ai/skills/ai_bridge/scripts/sync_agents/**/*.py"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `/adr write`. Edit if needed before running.

**Team name**: `adr-249-command-parity`

### Phase 1: Build Validation Gates
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Add command parity validator (declared command must have matching source file by type). | `plugins/ai/skills/ai_bridge/scripts/sync_agents/discovery.py`, `plugins/ai/skills/ai_bridge/scripts/sync_agents/engine.py` |
| 1.2 | developer | medium | Add duplicate command ID detection with hard-fail behavior in check mode. | `plugins/ai/skills/ai_bridge/scripts/sync_agents/discovery.py`, `plugins/ai/skills/ai_bridge/scripts/sync_agents/__init__.py` |
| 1.3 | devops | low | Wire validator into CI/pre-commit check path. | `.pre-commit-config.yaml`, CI workflow files |

### Phase 2: Fix Existing Drift
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | low | Add missing devops command docs for declared IDs. | `plugins/dev/skills/devops/commands/*.md` |
| 2.2 | developer | low | Add missing daemon command docs for declared IDs. | `plugins/observability/skills/daemon/commands/*.md` |
| 2.3 | validator | low | Run parity checks and ensure zero missing/duplicate errors. | validation outputs |

### Phase 3: Regenerate and Verify
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | devops | low | Regenerate instruction artifacts from validated sources. | `CODEX.md`, `CLAUDE.md`, generated adapters |
| 3.2 | validator | low | Verify command lists are unique, counts match, and no discovery warnings remain. | generated outputs, sync logs |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all relevant tests/checks and confirm no regressions |
| V.2 | architect | low | Confirm decentralization policy and central-generated contract are preserved |

### Completion Criteria
- [ ] Command declaration/file parity check exists and fails on mismatch
- [ ] Duplicate command IDs fail validation
- [ ] Existing missing command docs are restored
- [ ] `sync_agents --check` passes cleanly
- [ ] Central command summaries are generated-only and accurate
