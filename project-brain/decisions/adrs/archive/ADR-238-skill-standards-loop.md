---
status: Implemented
date: '2026-03-05'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- skill
- standards
- loop
- skill
- standardization
superseded_by: null
---

# ADR-238: Skill Standards Loop — SKILL.md Standardization and augur.yaml Decentralization

**Related ADRs**: ADR-163 (Plugin Decentralization), ADR-176 (Adaptive Loop Engine), ADR-200 (Ops-Loops / Auto-Commands Separation), ADR-216 (Unified Loop Configuration)

## Context

Augur skills lack standardized `SKILL.md` files per the [Claude Code skills open standard](https://code.claude.com/docs/en/skills). Metadata lives exclusively in `augur.yaml`, making skills incompatible with vanilla Claude Code. There is no automated enforcement of skill folder structure or frontmatter compliance.

The Claude Code standard defines a clear contract: every skill is a directory with `SKILL.md` as the entrypoint, YAML frontmatter for metadata (`name`, `description`, `disable-model-invocation`, etc.), and optional supporting files in `scripts/`, `examples/` subdirectories. Augur's skills follow none of this — they use `augur.yaml` as the sole metadata source and `commands/*.md` for slash command content.

This creates three problems:

1. **No portability** — Augur skills cannot be used as standard Claude Code skills outside the Augur ecosystem
2. **Centralization** — Rich metadata (hub assignment, loop config, page contributions) lives only in `augur.yaml`, not in a standards-compliant format
3. **No enforcement** — Skill folder structure, naming conventions, and frontmatter validity are never validated

## Decision

### New Loop Category: `skill-standards`

Add a sixth adaptive loop category alongside `self-heal`, `code-quality`, `hardening`, `knowledge-enrichment`, and `command-evolution`. Registered in `config/system/adaptive_loops.yaml` with budget 10, trigger `nightly`.

### Three Auto-Commands at Progressive Tiers

All live in `plugins/observability/skills/daemon/scripts/ops/`.

#### `auto-skill-md` (Tier 0) — SKILL.md Validation & Generation

Scans every `plugins/*/skills/*/` directory. Auto-fixes:

- Missing SKILL.md: generates from `augur.yaml` description and existing `commands/*.md`
- Missing/mismatched `name` field: sets to directory name
- Invalid name characters: normalizes to lowercase/hyphens
- Missing `description`: pulls from `augur.yaml`
- Unknown frontmatter fields: moves to `x-augur-*` namespace
- Empty markdown body: generates from command docs

Difficulty escalation: d0 = missing SKILL.md, d1 = frontmatter validation, d2 = name normalization, d3-4 = content quality.

#### `auto-skill-migrate` (Tier 1) — augur.yaml to x-augur-* Migration

Progressively copies `augur.yaml` metadata into SKILL.md frontmatter using namespaced fields:

| augur.yaml | SKILL.md frontmatter |
|---|---|
| `description` | `description` (standard) |
| `contributes_to` | `x-augur-hub` |
| `contributions.commands` | `x-augur-commands` |
| `contributions.pages` | `x-augur-pages` |
| `contributions.api_routes` | `x-augur-api-routes` |
| `contributions.mcp_tools` | `x-augur-mcp-tools` |
| `commands[].loop.*` | `x-augur-loop` |
| `dependencies` | `x-augur-dependencies` |

Does NOT modify `augur.yaml` — both coexist during migration. Adds `x-augur-migrated: true` markers to copied fields.

Difficulty escalation: d0 = scalars, d1 = commands, d2 = contributions, d3 = MCP tools, d4 = consistency audit.

#### `auto-skill-refs` (Tier 2) — Supporting Files & Folder Structure

Validates and fixes:

- Broken file references in SKILL.md body
- Loose scripts at skill root → moves to `scripts/`
- SKILL.md over 500 lines → flags for splitting
- Orphaned files not referenced from SKILL.md → adds reference section

Difficulty escalation: d0 = broken refs, d1 = folder restructuring, d2 = content splitting, d3 = orphan detection, d4 = cross-skill refs.

### Shared Library

`plugins/observability/skills/daemon/scripts/ops/skill_standards_lib.py` provides:

- `SkillMdInfo` / `AugurYamlInfo` data types
- `parse_skill_md()` / `parse_augur_yaml()` parsers
- `validate_name()` / `validate_frontmatter()` / `validate_folder_structure()` validators
- `compute_migration_delta()` for augur.yaml → SKILL.md field diff
- `write_skill_md()` / `update_frontmatter()` / `move_file_with_refs()` fixers
- `iter_all_skills()` discovery iterator

### Valid SKILL.md Frontmatter Fields

Standard (Claude Code open standard): `name`, `description`, `argument-hint`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `model`, `context`, `agent`, `hooks`

Augur extensions (namespaced): `x-augur-hub`, `x-augur-commands`, `x-augur-loop`, `x-augur-pages`, `x-augur-api-routes`, `x-augur-mcp-tools`, `x-augur-dependencies`, `x-augur-migrated`

### Migration Roadmap

**Phase 1 (this ADR)**: Establish loop, validate SKILL.md, migrate fields to `x-augur-*` frontmatter. Write-only — `augur.yaml` is never modified (except migration markers).

**Phase 2 (future ADR)**: Update `discovery.py` to read `x-augur-*` frontmatter as primary source with `augur.yaml` fallback. New `auto-skill-shrink` command (tier 3) removes migrated fields. Eventually `augur.yaml` becomes optional.

## Consequences

### Positive

- Every Augur skill becomes a valid Claude Code skill — portable outside the ecosystem
- Automated enforcement catches drift before it accumulates
- `x-augur-*` namespacing keeps Augur extensions clean and standards-compliant
- Zero engine changes — existing discovery, dashboard, CLI pick up the new loop automatically
- Progressive tiers allow safe rollout with independent trust tracking per command

### Negative

- Dual-source period: `augur.yaml` and SKILL.md both contain metadata until Phase 2
- Auto-generated SKILL.md files may need manual polish for quality
- Migration adds `x-augur-*` fields that are non-standard (though namespaced per convention)

### Neutral

- Existing `augur.yaml` files remain untouched during Phase 1
- Discovery continues reading `augur.yaml` as primary source until Phase 2

## Implementation Order

### Phase 1: Shared Library (Tasks 1-2)
1. Create `skill_standards_lib.py` with data types, parsers, validators, fixers
2. Write comprehensive tests for all library functions

### Phase 2: Auto-Commands (Tasks 3-5) — PARALLEL
3. `auto-skill-md` (tier 0) — SKILL.md validation & generation + tests
4. `auto-skill-migrate` (tier 1) — augur.yaml migration + tests
5. `auto-skill-refs` (tier 2) — reference & structure validation + tests

### Phase 3: Wiring (Task 6) — PIPELINE after Phase 2
6. Register loop in `adaptive_loops.yaml` and commands in daemon `augur.yaml`

### Phase 4: Verification (Tasks 7-8)
7. Integration smoke test — discovery, dry-run scan, ops-loops status
8. Update ops-loops command documentation

## Alternatives Considered

### A: Single Auto-Command with Difficulty Escalation
One `auto-skill-standards` command handling everything, using difficulty 0-4 for depth control. Rejected: single module gets too large, impossible to independently track trust per concern, harder to test.

### B: Plugin-Self-Validating (Fully Decentralized)
Each plugin declares its own `auto-skill-validate` command with shared library. Maximum decentralization but 22+ duplicate command declarations, harder to enforce consistency, discovery overhead.

### C: SKILL.md as Generated Artifact
Generate SKILL.md from `augur.yaml` at build time. Rejected: makes SKILL.md a second-class citizen, doesn't move toward augur.yaml shrinking, no portability benefit.

## References

- [Claude Code Skills Standard](https://code.claude.com/docs/en/skills)
- [Agent Skills Open Standard](https://agentskills.io)
- Design doc: `docs/plans/2026-03-05-skill-standards-loop-design.md`
- Implementation plan: `docs/plans/2026-03-05-skill-standards-loop-plan.md`
- ADR-163: Plugin Decentralization
- ADR-176: Adaptive Loop Engine
- ADR-200: Ops-Loops / Auto-Commands Separation
- ADR-216: Unified Loop Configuration

## Implementation Prompt

### Team: skill-standards-impl

**Phase 1: Shared Library** (PIPELINE — must complete before Phase 2)

| Step | Task | Files | Model |
|------|------|-------|-------|
| 1.1 | Create skill_standards_lib.py with SkillMdInfo, AugurYamlInfo, parsers, validators, migration delta, fixers, discovery | `plugins/observability/skills/daemon/scripts/ops/skill_standards_lib.py` | medium |
| 1.2 | Write tests for all library functions | `plugins/observability/skills/daemon/tests/test_skill_standards_lib.py` | medium |

**Phase 2: Auto-Commands** (PARALLEL — all depend on Phase 1)

| Step | Task | Files | Model |
|------|------|-------|-------|
| 2.1 | Implement auto-skill-md scan/fix with tests | `scripts/ops/skill_standards_md.py`, `tests/test_skill_standards_md.py` | medium |
| 2.2 | Implement auto-skill-migrate scan/fix with tests | `scripts/ops/skill_standards_migrate.py`, `tests/test_skill_standards_migrate.py` | medium |
| 2.3 | Implement auto-skill-refs scan/fix with tests | `scripts/ops/skill_standards_refs.py`, `tests/test_skill_standards_refs.py` | medium |

**Phase 3: Wiring** (PIPELINE — after Phase 2)

| Step | Task | Files | Model |
|------|------|-------|-------|
| 3.1 | Add skill-standards loop to adaptive_loops.yaml | `config/system/adaptive_loops.yaml` | low |
| 3.2 | Register 3 auto-commands in daemon augur.yaml | `plugins/observability/skills/daemon/augur.yaml` | low |

**Phase 4: Verification** (PIPELINE — after Phase 3)

| Step | Task | Files | Model |
|------|------|-------|-------|
| 4.1 | Integration smoke test: discovery, dry-run scan, ops-loops status | n/a (manual) | high |
| 4.2 | Update ops-loops.md with skill-standards loop documentation | `plugins/observability/skills/daemon/commands/ops-loops.md` | low |
