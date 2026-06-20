---
status: Implemented
date: 2026-03-23
deciders:
  - Gur Sannikov
related: [481, 270, 416]
hub: adaptive
tags: [vault, docs, naming, enforcement]
superseded_by: null
---

# ADR-482: Directory Alignment to Skill Names

## Context

External directories (`Au-vault`, `Au-docs`) accumulate first-level folders that don't match any Augur skill name — typos (`consulting` instead of `consulting-template`), orphaned folders (`professional`, `reports`), or undocumented structural dirs (`dashboard`). There was no enforcement, so drift was silent and permanent. With 184 skills and 49+ vault dirs, manual auditing doesn't scale.

## Decision

Enforce a simple rule: **every first-level subdirectory in a managed external location must either exactly match a skill name from `skills/` or appear in that location's `.augur-reserved` file.**

Three enforcement layers:

1. **Runtime guard** — `get_skill_vault_dir()` and `get_skill_documents_dir()` in `paths.py` call `validate_dir_name()` and raise `ValueError` for unknown names. Replaces the hardcoded `_RESERVED_VAULT_NAMES` set.

2. **CI check** — `scripts/check_dir_alignment.py` scans all managed locations and exits non-zero on violations.

3. **Auto-loop** — `skills/auto-dir-alignment/` runs nightly with difficulty-gated behavior: d0 reports, d1 auto-renames fuzzy matches, d2 scaffolds new skills, d3 prompts user.

Managed locations are read from `project.yaml` via `get_project_paths()` (ADR-481). Reserved names are decentralized — each location owns its own `.augur-reserved` plain-text dotfile rather than a centralized config.

Violation classification uses prefix-aware fuzzy matching (`difflib.SequenceMatcher` + prefix detection) with a 0.85 threshold to identify trivial renames. Directories with >= 3 files or >= 1 subdirectory and no close match are flagged as new-skill-candidate. Remainder is classified as unknown for user triage.

## Consequences

### Positive
- No more orphaned or misnamed directories accumulating silently
- Reserved names are decentralized (`.augur-reserved` per location, not a centralized set)
- `_RESERVED_VAULT_NAMES` hardcoded set eliminated — single source of truth
- Reserved names are now allowed through the guard (behavioral improvement — `config`, `dev`, `memory` can be vault targets for tools that need them)
- Skill name cache (`lru_cache`) avoids repeated filesystem scans in hot loops

### Negative
- `get_skill_vault_dir("config")` no longer raises — code that relied on the old rejection behavior must be updated
- `.augur-reserved` files must be maintained in external repos — without them, previously-allowed reserved names (`config`, `dev`, `memory`) will raise `ValueError` in test/CI environments that lack the external vault
- `get_skill_names()` cache is process-scoped — won't pick up skills added mid-session

### Neutral
- Auto-loop follows existing scan-fix protocol — no new infrastructure needed
- CI script is a thin standalone wrapper — no ops_protocol dependency

## Alternatives Considered

1. **Centralized YAML allowlist** — rejected: violates decentralization principle (CLAUDE.md rule #2), creates another centralized config to maintain.

2. **Guard-only enforcement (no auto-loop)** — rejected: doesn't fix existing violations or help with ongoing drift detection. The guard prevents new bad dirs but can't rename existing ones.

3. **Distributed enforcement with shared config** — rejected: three implementations to keep in sync, config file is centralized.

## References

- Spec: `docs/superpowers/specs/2026-03-23-dir-alignment-design.md`
- Plan: `docs/superpowers/plans/2026-03-23-dir-alignment.md`
- ADR-481: Centralized Path Configuration (provides `get_project_paths()`)
- ADR-270: Folder Restructure — Layer Separation
- ADR-416: Vault Hygiene Cleanup

## Impact Manifest

```yaml
files_added:
  - src/lib/dir_alignment.py
  - scripts/check_dir_alignment.py
  - skills/auto-dir-alignment/SKILL.md
  - skills/auto-dir-alignment/scripts/dir_alignment_ops.py

files_modified:
  - src/config/paths.py  # removed _RESERVED_VAULT_NAMES, rewrote get_skill_vault_dir + get_skill_documents_dir

symbols_removed:
  - _RESERVED_VAULT_NAMES  # from src/config/paths.py

behavioral_changes:
  - get_skill_vault_dir("config")  # was: ValueError, now: returns vault/config (if in .augur-reserved)
  - get_skill_documents_dir("dev")  # was: ValueError, now: returns docs/dev (if in .augur-reserved)
```
