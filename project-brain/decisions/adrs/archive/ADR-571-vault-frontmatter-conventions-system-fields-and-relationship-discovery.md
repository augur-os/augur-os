---
status: Implemented
date: '2026-05-03'
deciders:
- Gur Sannikov
related:
- ADR-404
- ADR-504
- ADR-560
- ADR-563
hub: brain
tags:
- vault
- frontmatter
- obsidian
- wiki
- conventions
superseded_by: null
---


# ADR-571: Vault Frontmatter Conventions — System Fields and Relationship Discovery

## Context

Augur's vault is now Obsidian-native (ADR-563, obsidian-first root migration). Vault notes carry YAML frontmatter that mixes two unrelated concerns:

1. **User-facing properties** the user enters and expects to see in Obsidian's Properties panel (`status`, `tags`, `goal`, dates, etc.).
2. **System metadata** written by Augur's wiki compiler, ingest pipeline, and skill data writers (`x-augur-*`, source provenance, hashes, indexing markers, retention flags).

Today the two are interleaved. Users see machinery in their Properties panel; programmatic writers risk clobbering user fields; there is no shared rule for "which keys are mine to manage." `src/lib/frontmatter_utils.py` already special-cases `x-augur-config-file` sidecar merging but has no general convention for system-vs-user separation.

Separately, vault relationships are currently encoded in two places that don't talk to each other:

- **Body wikilinks** (`[[Page]]`) — handled bidirectionally by `skills/ai/scripts/markdown_flavors.py` for Obsidian/standard-markdown round-trips.
- **Frontmatter relations** — encoded ad hoc per skill (e.g. a `belongs_to:` field, a `topics:` list). Each consumer (wiki compiler, brain inbox, ingest router) hardcodes the field names it knows about. New relationship vocabularies require code changes.

Tolaria (refactoringhq/tolaria) addresses both pain points with two small conventions:

- Any frontmatter key prefixed with `_` is **system/hidden** infrastructure (`_pinned_properties`, `_icon`, `_color`). Hidden in the user properties UI, editable only in raw mode.
- Relationships are **discovered dynamically**: the parser scans every frontmatter value for `[[wikilink]]` tokens and populates a relationships map. No schema, no allowlist — `Topics: [[A]] [[B]]` and `Mentors: [[X]]` both work without code changes.

These are cheap, vault-scoped conventions that compose with existing Obsidian-native frontmatter and would simplify both wiki compilation and Augur's interaction with user-authored notes.

## Decision

Adopt two paired conventions for **vault notes only** (skill SKILL.md frontmatter, ADR frontmatter, and other code-side YAML are out of scope and continue to use `x-augur-*`).

### 1. `_field` system-property convention

- Any vault-frontmatter key beginning with `_` is treated as **system metadata** owned by Augur tooling (compilers, ingest, daemons).
- `src/lib/frontmatter_utils.py` gains a public predicate `is_system_field(key) -> bool` and a pair of partition helpers `split_system_user(meta)` and `merge_system_user(system, user)`.
- Existing `x-augur-*` keys remain valid for skill/code frontmatter (SKILL.md, `config.yaml`, ADRs). A migration helper renames vault-side `x-augur-*` to `_*` only where the key is documented as vault-only; code-side `x-augur-*` keys are not touched.
- Obsidian property visibility is controlled in the obsidian skill's vault config (hide all `_`-prefixed keys from Properties view); raw editor still shows them.
- Writers that mutate user notes MUST use `merge_system_user(...)` so they can never clobber user keys; the helper is the single write path for system metadata.

### 2. Dynamic relationship discovery from wikilink-bearing frontmatter values

- Add `extract_relationships(meta) -> dict[str, list[str]]` to `src/lib/frontmatter_utils.py`. It scans every frontmatter value (string, list of strings, or nested dict leaf) for `[[Target]]` and `[[Target|Alias]]` tokens and returns `{field_name: [target, ...]}`.
- The function is field-name agnostic: any field whose value contains wikilinks becomes a relationship edge, indexed by its key.
- A small `RelationshipIndex` view (in-memory, rebuilt per scan; cache keyed off git HEAD where the vault is a repo) is exposed to wiki compiler and brain inbox so they can stop hardcoding field-name lists.
- Body-text wikilinks remain owned by `markdown_flavors.py`. Frontmatter wikilink discovery is additive, not a replacement.
- Field names are humanized at render time (`belongs_to` → "Belongs to", `key_people` → "Key people"); raw on-disk keys are preserved.

### Scope boundaries

- **In scope**: vault notes under `get_vault_dir()`; wiki concept/query pages; `/ingest-url` source cards.
- **Out of scope**: SKILL.md, config.yaml, ADR frontmatter, generated agent markdown, dashboard manifests. These keep `x-augur-*`.
- **Not changed**: Obsidian flavor conversion in `markdown_flavors.py`; vault directory layout; ADR-560 wiki compiler invariants.

## Consequences

### Positive

- Clean separation between user properties and Augur machinery in the Obsidian UI — Properties panel stops showing implementation details.
- New relationship vocabularies (e.g. user adds `Mentors: [[X]]` to a note) flow through wiki compiler, brain inbox, and graph views with zero code change.
- Single write path (`merge_system_user`) eliminates a class of "writer overwrote user field" bugs.
- Aligns vault frontmatter with widely-understood conventions (Tolaria, Bear, several Obsidian community plugins use leading-underscore for system fields).

### Negative

- One-time migration of existing vault-side `x-augur-*` keys to `_*`. Risk of breakage if any writer is missed.
- `extract_relationships` adds a per-parse cost on full vault scans (mitigated by git-HEAD cache, see ADR-560 invariants and the separate caching idea in the Tolaria comparison).
- Two coexisting prefix conventions (`_` for vault, `x-augur-*` for code-side) require a clear documented boundary; risk of agent confusion if the boundary slips.

### Neutral

- Body wikilinks are unchanged. Existing Obsidian users see no behavior change in their notes.
- Skills that already use `x-augur-*` in vault data files continue to work during the migration window via a back-compat read in `parse_frontmatter`.

## Alternatives Considered

### Alternative 1: Keep `x-augur-*` everywhere, add UI hiding rule

Tag `x-augur-*` as system in the Obsidian properties config and call it done. Rejected: only solves visibility, not the dynamic-relationship problem. Also leaves the prefix verbose for hand-edited vault notes (`x-augur-pinned: true` vs `_pinned: true`).

### Alternative 2: Schema-registered relationships per skill

Each skill declares its relationship fields in `SKILL.md` (`x-augur-relationships: [topics, mentors]`). Rejected: re-introduces the registration step the dynamic-discovery approach is meant to remove. Users adding ad-hoc relationship fields would still be invisible to consumers until a schema update.

### Alternative 3: Split system metadata into a sidecar `.augur.yaml` per note

Move all system fields out of the note's frontmatter into a sibling file. Rejected: breaks Obsidian-native principle (ADR-563), doubles file count, complicates git diffs, and creates a sync-divergence class of bug.

## References

- ADR-404 — Frontmatter migration (origin of `frontmatter_utils.py`)
- ADR-504 — Obsidian markdown flavor module
- ADR-560 — Semantic Wiki Page Compiler (consumer of relationship index)
- ADR-563 — Vault-Owned User Skills, Pages, and Draft Staging
- Tolaria docs/ABSTRACTIONS.md — `_field` convention and dynamic relationships (https://github.com/refactoringhq/tolaria/blob/main/docs/ABSTRACTIONS.md)
- Tolaria docs/ARCHITECTURE.md — frontmatter and relationship model (https://github.com/refactoringhq/tolaria/blob/main/docs/ARCHITECTURE.md)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "src/lib/frontmatter_utils.py: add is_system_field(), split_system_user(), merge_system_user(), extract_relationships()"
  patterns_deprecated:
    - "Hardcoded relationship field-name lists in wiki compiler and brain inbox consumers"
    - "Vault-side x-augur-* keys (replaced by _*); code-side x-augur-* unchanged"
  files_affected:
    - "src/lib/frontmatter_utils.py"
    - "skills/ai/scripts/markdown_flavors.py (no change, documented as adjacent)"
    - "plugins/augur/skills/wiki/* (compiler consumes RelationshipIndex)"
    - "plugins/augur/skills/obsidian/* (properties hide rule for _* keys)"
    - "plugins/obsidian/* (vault config: hide _-prefixed properties)"
    - "Vault note migration: rename documented vault-only x-augur-* keys to _*"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-571-vault-frontmatter`

### Phase 0: Worktree setup
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 0.1 | devops | low | Commit ADR-571, create worktree `adr-571-vault-frontmatter`, switch cwd | `.worktrees/adr-571-vault-frontmatter` |
| 0.2 | architect | medium | Enumerate every vault-only `x-augur-*` key in current vault notes; produce a migration map (key → `_key`); flag any code-side reads to update | `migration-map.md` |

### Phase 1: Library — system-field convention
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Add `is_system_field`, `split_system_user`, `merge_system_user` to `frontmatter_utils.py`; preserve key order on write | `src/lib/frontmatter_utils.py` |
| 1.2 | developer | medium | Unit tests: round-trip preservation, merge does not clobber user keys, `_`-prefixed keys partition correctly | `src/lib/test_frontmatter_utils.py` |

### Phase 2: Library — relationship discovery
**Strategy**: PARALLEL with Phase 1

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Add `extract_relationships(meta)` scanning string/list/dict leaves for `[[target]]` and `[[target\|alias]]`; return `dict[field, list[target]]` | `src/lib/frontmatter_utils.py` |
| 2.2 | developer | medium | Unit tests: nested lists, aliased links, mixed content, non-string values ignored, empty meta returns `{}` | `src/lib/test_frontmatter_utils.py` |
| 2.3 | developer | medium | Add `RelationshipIndex` builder over a vault scan; integrate git-HEAD cache key if vault is a repo | `src/lib/relationship_index.py` |

### Phase 3: Consumer migration
**Strategy**: PIPELINE (after Phases 1–2)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | high | Replace hardcoded relation field-name lookups in wiki compiler with `RelationshipIndex` queries | `plugins/augur/skills/wiki/scripts/**` |
| 3.2 | developer | medium | Same migration in brain inbox / source-card readers | `plugins/augur/skills/obsidian/scripts/**`, `skills/ingest/scripts/**` |
| 3.3 | developer | medium | All vault writers route system-metadata writes through `merge_system_user` | wiki compiler, ingest router, daemon writers |

### Phase 4: Vault migration + Obsidian visibility
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | devops | medium | Run vault migration script using map from 0.2; rewrite `x-augur-*` → `_*` in vault notes only; preserve other frontmatter | vault notes under `get_vault_dir()` |
| 4.2 | developer | low | Update Obsidian skill / vault config to hide `_`-prefixed properties from the Properties panel | `plugins/obsidian/**`, `plugins/augur/skills/obsidian/**` |
| 4.3 | validator | medium | Smoke check: open vault in Obsidian, verify Properties panel shows only user fields, raw editor still shows `_` fields | manual + screenshot |

### Phase 5: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | validator | medium | Full test suite green; no regressions in wiki compiler outputs; spot-check 5 vault notes pre/post migration | — |
| 5.2 | validator | medium | Wiring verification: zero remaining hardcoded relation field-name lists; all writers use `merge_system_user` | grep audit |
| 5.3 | validator | low | Update `docs/agent-topics/SKILLS.md` and any vault-related docs referencing the old convention | docs |

### Completion Criteria

- [ ] All phases executed
- [ ] `frontmatter_utils.py` exports the four new helpers with tests
- [ ] `RelationshipIndex` integrated in wiki compiler and at least one other consumer
- [ ] Vault migration applied; no vault-only `x-augur-*` keys remain
- [ ] Obsidian Properties panel hides `_`-prefixed keys; raw editor preserves them
- [ ] No code-side `x-augur-*` keys touched (SKILL.md, config.yaml, ADR frontmatter unchanged)
- [ ] Existing tests green; new helpers covered by unit tests
- [ ] Wiring verification: zero hardcoded relation field-name lists in consumers
- [ ] `docs/agent-topics/SKILLS.md` updated
- [ ] ADR status updated to Implemented
