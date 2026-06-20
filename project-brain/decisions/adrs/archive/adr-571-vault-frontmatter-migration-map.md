---
title: ADR-571 Vault Frontmatter Migration Map
status: active
adr: ADR-571
generated_at: 2026-05-03
---

# ADR-571 Vault Frontmatter Migration Map

## Scope

Vault root scanned: `~/Projects/Au-vault`

In-scope vault notes exclude `**/SKILL.md`, `config.yaml`, generated command and agent markdown, `.obsidian`, and git internals. Code-side `x-augur-*` frontmatter remains out of scope.

## Dry-Run Result

- Markdown files scanned: 424
- Frontmatter files parsed: 325
- In-scope vault-note `x-augur-*` keys found: 0
- Migration map: empty
- Sample diff: no in-scope changes; the migration is a no-op for existing vault notes

One malformed note frontmatter was skipped by YAML parsing during the inventory:

- `notes/career/learning/scoring-formulas.md`

A literal anchored grep for `^x-augur-` across in-scope non-`SKILL.md` vault markdown returned no matches, so the parse failure does not hide a vault-side `x-augur-*` migration candidate.

## Excluded Matches

All observed `x-augur-*` frontmatter matches were in excluded skill definition surfaces, primarily staged `SKILL.md` files under `drafts/staging/**/skills/**/SKILL.md`. ADR-571 keeps those code-side skill fields unchanged.
