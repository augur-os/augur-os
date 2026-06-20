# Strict Notes Folder Depth Design

**Date:** 2026-05-03
**Status:** Approved for strict migration planning, pending written-spec review
**Scope:** `Au-vault/notes/` folder-depth cleanup after the Obsidian-first root migration

## Summary

The vault should stay Obsidian-first not only at the root, but inside `notes/`.
The current layout still contains deep folder chains where several directories
exist only to hold one file. That makes the vault feel like implementation
output instead of a human notes space.

This design introduces a strict `notes/` depth policy:

- default note paths should be shallow
- skinny folder chains should be collapsed
- config-like files should leave `notes/`
- dense collections may keep limited extra depth when the extra folder names
  help browsing

The migration should use explicit move plans and verification checks, not
blind bulk renames.

## Current State

Live scan of `~/Projects/Au-vault/notes` on 2026-05-03:

| Area | Files | Max Depth | Files At Depth 5+ |
| --- | ---: | ---: | ---: |
| `augur` | 7 | 6 | 5 |
| `books` | 19 | 3 | 0 |
| `career` | 30 | 4 | 0 |
| `finance` | 9 | 3 | 0 |
| `health` | 10 | 4 | 0 |
| `lifestyle` | 31 | 5 | 15 |
| `venture` | 76 | 5 | 35 |

Representative problem paths:

| Current Path | Problem |
| --- | --- |
| `notes/augur/advisor/design/docs/architecture/llm_journey_map.md` | five folder labels before a single file |
| `notes/career/notes/learning/scoring-formulas.md` | repeated `notes` layer |
| `notes/career/notes/proposals/2026-04-29-samsung-ai-kickoff-pricing-draft.md` | repeated `notes` layer |
| `notes/lifestyle/ideas/_config/config.yaml` | config data under notes |
| `notes/lifestyle/recipe-manager/config/settings.yaml` | config data under notes |
| `notes/venture/content/linkedin/notes/2026-04-24-firmware-ai-adoption-thesis.md` | extra `notes` layer inside content area |
| `notes/venture/notes/*.md` | repeated `notes` layer |

## Goals

- Make `notes/` easy to browse directly in Obsidian.
- Reduce paths that are five or more levels deep.
- Collapse directories that only exist to hold one file.
- Keep meaningful collections discoverable without over-flattening dense areas.
- Preserve git history through `git mv` where practical.
- Update Augur path contracts and tests when a moved file is read by tools.

## Non-Goals

- Do not move protected root folders such as `skills/`, `memory/`, `wiki/`,
  `sources/`, `drafts/`, or `archive/`.
- Do not rewrite every note title or content body.
- Do not delete notes as part of depth cleanup.
- Do not move runtime state into the vault.
- Do not use compatibility aliases for old paths unless an existing runtime
  contract requires a temporary bridge.

## Depth Policy

### Default Shape

Most notes should fit one of these shapes:

```text
notes/{domain}/{file}
notes/{domain}/{topic}/{file}
```

Examples:

```text
notes/career/scoring-formulas.md
notes/career/proposals/2026-04-29-samsung-ai-kickoff-pricing-draft.md
notes/finance/ideas.md
```

### Strict Collapse Rule

A directory under `notes/` should be collapsed when all are true:

- it has exactly one file descendant
- it has no meaningful sibling collection
- it is not required by a runtime path contract
- its folder name is generic, duplicated, or only restates the file type

Examples of folder names that should usually collapse:

- `notes`
- `docs`
- `design`
- `architecture` when it only holds one architecture note
- `_config`
- `config`

### Allowed Dense Collection Rule

A deeper folder may remain when it is a real collection with multiple sibling
files and the folder hierarchy improves browsing.

Allowed examples from the current scan:

```text
notes/lifestyle/recipe-manager/recipes/perfected/*.md
notes/lifestyle/recipe-manager/recipes/to-try/*.md
notes/venture/content/linkedin/posts/*.md
```

Even these should be capped at the practical depth needed for browsing. Dense
collections are not permission to keep arbitrary implementation nesting.

### Config Separation Rule

Files that are configuration, state, templates, or generated operational data
should not live under `notes/` unless they are intentionally user-authored notes.

Examples:

| Current Path | Target Pattern |
| --- | --- |
| `notes/lifestyle/ideas/_config/config.yaml` | `config/lifestyle/ideas/config.yaml` |
| `notes/lifestyle/recipe-manager/config/settings.yaml` | `config/recipe-manager/settings.yaml` |
| `notes/lifestyle/notes/_templates/idea.md` | `config/lifestyle/templates/idea.md` |

## Migration Approach

### Phase 1: Inventory

Generate a machine-readable move candidate list for:

- files at depth 5 or deeper
- directories with exactly one file descendant
- repeated folder names such as `notes/.../notes/...`
- config-like files under `notes/`

The inventory should include:

- source path
- proposed target path
- reason
- whether a source is read by code
- whether a dense-collection exception applies

### Phase 2: Planned Moves

Apply moves only from the reviewed inventory. Use `git mv` for tracked files
and preserve file content exactly unless a filename normalization is part of
the reviewed move.

Conflicts should be handled by choosing a clearer filename, not by recreating
new nested folders.

### Phase 3: Path Updates

After moving files, update only real references:

- skill metadata `x-augur-data-dir`
- vault path helpers and tests
- MCP readers that load specific files
- Browse inventory expectations
- wiki/search exclusion rules where paths are explicit

Do not add old-path aliases merely to hide stale references. Prefer updating
the caller to the new canonical path.

### Phase 4: Verification

Required checks:

- `git -C ~/Projects/Au-vault status --short`
- `git -C ~/Projects/Au-vault diff --check`
- strict notes-depth scanner reports no unexpected skinny deep folders
- `python3 scripts/check_obsidian_vault_roots.py`
- impacted Augur path/MCP tests
- impacted Au-vault skill tests
- vault hygiene scan reports `verified`

## Initial Move Candidates

These candidates should be reviewed first because they are obvious strict-mode
matches:

| Source | Proposed Target | Reason |
| --- | --- | --- |
| `notes/augur/advisor/design/docs/architecture/llm_journey_map.md` | `notes/augur/advisor/llm-journey-map.md` | single-file deep chain |
| `notes/career/notes/learning/scoring-formulas.md` | `notes/career/learning/scoring-formulas.md` | duplicated `notes` layer |
| `notes/career/notes/proposals/2026-04-29-samsung-ai-kickoff-pricing-draft.md` | `notes/career/proposals/2026-04-29-samsung-ai-kickoff-pricing-draft.md` | duplicated `notes` layer |
| `notes/career/notes/sessions/2026-04-29-samsung-ai-kickoff-proposal.md` | `notes/career/sessions/2026-04-29-samsung-ai-kickoff-proposal.md` | duplicated `notes` layer |
| `notes/venture/content/linkedin/notes/2026-04-24-firmware-ai-adoption-thesis.md` | `notes/venture/content/linkedin/2026-04-24-firmware-ai-adoption-thesis.md` | single-file `notes` folder |
| `notes/venture/notes/*.md` | `notes/venture/*.md` | duplicated `notes` layer |
| `notes/lifestyle/notes/notion-notes.md` | `notes/lifestyle/knowledge/notion-notes.md` | duplicated `notes` layer while preserving the dashboard knowledge grouping |
| `notes/lifestyle/ideas/_config/config.yaml` | `config/lifestyle/ideas/config.yaml` | config file under notes |
| `notes/lifestyle/recipe-manager/config/settings.yaml` | `config/recipe-manager/settings.yaml` | config file under notes |

Dense collection exceptions to keep in the first pass:

| Path | Reason |
| --- | --- |
| `notes/lifestyle/recipe-manager/recipes/perfected/` | dense recipe collection |
| `notes/lifestyle/recipe-manager/recipes/to-try/` | dense recipe collection |
| `notes/venture/content/linkedin/posts/` | dense content collection |
| `notes/venture/content/linkedin/assets/` | content-supporting assets collection |
| `notes/venture/content/linkedin/context/` | structured content context; may later move to config after ownership review |

## Success Criteria

- No folder under `notes/` has exactly one file descendant at depth 3+ unless it
  is explicitly allowlisted.
- No nested folder named `notes` remains inside the `notes/` root.
- Config-like files under `notes/` are either moved or explicitly justified.
- `notes/` max depth decreases where strict-mode candidates were obvious.
- Browse and MCP readers still return migrated data.
- The vault stays clean and git-tracked after the migration.

## Open Implementation Notes

- The strict scanner should be added before file moves so the migration has a
  measurable target.
- The scanner should support an allowlist file or inline constants for dense
  collection exceptions.
- The migration should be one focused vault commit plus one focused Augur code
  commit if code references need updating.
