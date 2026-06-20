---
status: Implemented
date: 2026-05-03
deciders:
  - Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
---

# ADR-602: Strict Notes Folder Depth Migration

## Context

After the Obsidian-first vault root migration, the vault should stay Obsidian-first inside `notes/` too. A live scan of `Au-vault/notes` on 2026-05-03 showed that several areas still contained deep folder chains where directories existed only to hold one file, repeated `notes/` layers, and config/template files mixed into notes:

| Area | Files | Max Depth | Files At Depth 5+ |
| --- | ---: | ---: | ---: |
| `augur` | 7 | 6 | 5 |
| `lifestyle` | 31 | 5 | 15 |
| `venture` | 76 | 5 | 35 |

Representative problem paths included `notes/augur/advisor/design/docs/architecture/llm_journey_map.md` (five labels before a single file), repeated `notes/career/notes/...` and `notes/venture/notes/...` layers, and config files like `notes/lifestyle/recipe-manager/config/settings.yaml` that belonged outside `notes/`.

The vault should feel like a human notes space, not implementation output. The migration must preserve git history through `git mv`, must not move protected runtime roots (`skills/`, `memory/`, `wiki/`, `sources/`, `drafts/`, `archive/`), and must update real path references rather than introduce compatibility aliases.

## Decision

Adopt a strict notes-depth policy and migrate the obvious matches in two repos:

**Policy:**
- Default note shapes: `notes/{domain}/{file}` or `notes/{domain}/{topic}/{file}`.
- A directory under `notes/` collapses when it has exactly one file descendant, no meaningful sibling collection, no runtime path contract, and a generic name (`notes`, `docs`, `design`, single-architecture `architecture`, `_config`, `config`).
- Dense collections may keep extra depth when they hold multiple sibling files and the hierarchy aids browsing (e.g., `notes/lifestyle/recipe-manager/recipes/perfected/`, `notes/venture/content/linkedin/posts/`).
- Configuration, state, templates, and generated operational data move out of `notes/` to `config/`.

**Implementation:**
- Add `scripts/check_notes_depth.py` (Augur-owned scanner) plus `tests/scripts/test_check_notes_depth.py`. The scanner reports `skinny_deep_dir`, `repeated_notes_layer`, `config_under_notes`, and `missing_notes_root` issues with an allowlist for dense collections (`augur/platform-admin/setup/ollama`, `health/virtual-doctor/medications`, `health/virtual-doctor/symptoms`, `lifestyle/recipe-manager/recipes/{perfected,to-try}`, `venture/content/linkedin/{assets,context,posts}`).
- Apply a reviewed move set in Au-vault using `git mv`: collapse repeated `notes` layers (career, venture, eisenhower, books, linkedin), flatten the advisor design chain, and relocate config/templates (`config/lifestyle/ideas/config.yaml`, `config/recipe-manager/settings.yaml`, `config/lifestyle/templates/idea.md`).
- Update real references (skill metadata `x-augur-data-dir`, MCP readers, browse expectations, vault docs) but do not add old-path aliases.
- Verify with the new scanner, the Obsidian-first vault root scanner, impacted Augur and Au-vault tests, generated agent/registry checks, and the loop-repo vault hygiene scan.

## Consequences

### Positive
- Notes browse cleanly in Obsidian; no folder exists only to hold one file (outside the allowlist).
- Config files leave `notes/` for `config/`, matching their actual ownership.
- The scanner becomes a durable hygiene check that catches regressions automatically.
- Git history is preserved through `git mv`.

### Negative
- One Au-vault commit moves many tracked files; reviewers must trust the planned move set.
- Live readers in `skills/lifestyle` and similar locations may need updates if they hardcoded old config paths — those are caught by the impacted-test sweep.
- Compiled wiki source citations may temporarily point at old source paths until the wiki compiler/reindex re-runs.

### Neutral
- Some root temporary review folders (`apple`, `content`, `growth`, `updater`, `remote-access`) remain by design as known intentional leftovers.

## Alternatives Considered

### Alternative 1: Bulk rename without an allowlist
Rejected. Dense collections (recipes, linkedin assets) genuinely benefit from extra depth. Blind flattening would damage real browsing affordances.

### Alternative 2: Keep config files under `notes/` with a `_config` convention
Rejected. Config and templates are not user-authored notes; mixing them obscures vault intent and breaks the Obsidian-first surface.

### Alternative 3: Leave the depth issue for a later session
Rejected. Without the strict scanner in place, future deep paths reappear silently. The scanner-first approach gives a measurable target.

## References
- Plan: docs/superpowers/plans/2026-05-03-strict-notes-folder-depth-migration.md
- Spec: docs/superpowers/specs/2026-05-03-strict-notes-folder-depth-design.md
