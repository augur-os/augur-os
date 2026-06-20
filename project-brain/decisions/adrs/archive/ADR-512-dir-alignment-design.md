---
id: ADR-512
title: Directory Alignment to Skill Names
status: Implemented
date: 2026-03-24
deciders: [Gur Sannikov]
tags: [vault, alignment, enforcement, naming, ci]
related: []
---

# ADR-512: Directory Alignment to Skill Names

## Context

External directories (Au-vault, Au-docs) accumulated first-level folders that didn't match any skill name — typos (`consulting` instead of `consulting-template`), orphaned folders (`professional`, `reports`), or undocumented structural dirs (`dashboard`). No enforcement existed, so drift was silent and permanent.

## Decision

Enforce that every first-level subdirectory in managed external locations must either:
1. Exactly match a skill name from `skills/` (filesystem is source of truth), OR
2. Appear in that location's `.augur-reserved` file

Shared validation module `src/lib/dir_alignment.py` provides:
- `get_managed_locations()` — reads paths from `project.yaml`
- `validate_dir_name()` — checks against skill names and reserved list
- `classify_violation()` — returns `trivial-rename` (SequenceMatcher >= 0.85), `new-skill-candidate` (3+ files), or `unknown`

Auto-fix for trivial renames. Autoloop and CI pre-commit hook for enforcement.

## Consequences

### Positive
- Silent naming drift eliminated — violations caught immediately
- Trivial renames auto-fixed without user intervention
- `.augur-reserved` provides escape hatch for structural directories

### Negative
- Users creating experimental vault folders need to add to `.augur-reserved` or create a skill

## References

- Spec: `docs/superpowers/specs/2026-03-23-dir-alignment-design.md`
- Module: `src/lib/dir_alignment.py`
