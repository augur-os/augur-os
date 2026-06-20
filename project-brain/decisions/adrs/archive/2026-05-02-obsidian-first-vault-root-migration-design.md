---
title: Obsidian-First Vault Root Migration Design
date: 2026-05-02
status: proposed
scope: design
related:
  - 2026-04-23-vault-user-surfaces-phase1-design.md
  - 2026-04-30-vault-browse-surface-refactor-design.md
---

# Obsidian-First Vault Root Migration Design

## Purpose

The vault root should read like an Obsidian knowledge workspace, not like a skill runtime dump. Current root folders such as `career-ops/`, `books/`, `apple/`, `finance/`, and `health/` are mostly data, config, notes, or personal material. They should not remain root folders just because their names match skills.

This design defines the long-term vault root contract, the inactive draft/archive behavior, and the migration rules for moving root-level leftovers into human-facing locations while preserving Augur runtime safety.

## Decisions

- Use `drafts/`, not `_drafts/`.
- Keep `drafts/` and `archive/` tracked in git.
- Ignore `drafts/` and `archive/` for normal operation, discovery, `/ask`, wiki compounding, dashboards, MCP registration, commands, actions, agents, prompts, and workflows.
- Expose `drafts/` and `archive/` only through explicit Browse tabs.
- Do not introduce `_system/` for this migration.
- Runtime state, caches, generated indexes, sessions, and histories belong in `get_runtime_dir()`, not in the vault.
- Keep only durable, human-editable, non-secret configuration in `config/`.
- Keep active private skill implementations in `skills/`.
- Keep inactive implementation bundles under `drafts/staging/`.

## Final Root Contract

After migration, the vault root is limited to:

```text
Au-vault/
  inbox/
  notes/
  sources/
  wiki/
  skills/
  drafts/
  archive/
  config/
```

Any other top-level folder is temporary migration debt unless explicitly approved as a first-class Obsidian domain.

## Root Semantics

| Root | Meaning | Default Operation | Browse |
| --- | --- | --- | --- |
| `inbox/` | Unsorted captures and review queue | Active intake/review | Inbox |
| `notes/` | Human domain knowledge and personal data | Active knowledge | Notes |
| `sources/` | Durable raw source cards | Active source material | Sources |
| `wiki/` | Compiled concept/query synthesis | Active compiled knowledge | Wiki |
| `skills/` | Active private skill implementations | Active skill discovery/export | Skills |
| `drafts/` | Inactive drafts, staged implementations, draft pages, draft prompts, draft workflows | Excluded | Drafts only |
| `archive/` | Inactive historical material kept for reference | Excluded | Archive only |
| `config/` | Durable human-editable non-secret config | Loaded only by explicit owner | Config/admin only |

## Notes Layout

`notes/` uses shallow domain folders. The first pass should use:

```text
notes/
  augur/
  books/
  career/
  content/
  finance/
  health/
  home/
  learning/
  personal/
  venture/
```

The migration should prefer domain meaning over old folder names. For example, `career-ops/`, relevant `growth/` material, and job-facing writing belong under `notes/career/` or `notes/venture/content/` depending on the content, not under root `career-ops/`.

## Migration Buckets

| Current Material | Target |
| --- | --- |
| `SKILL.md`, `commands/`, `scripts/`, `augur/`, `evals/`, `references/` for an active private capability | `skills/<skill>/` |
| Inactive skill/page/source implementation draft | `drafts/staging/<release>/...` |
| Markdown notes, CVs, plans, goals, story banks, ideas | `notes/{domain}/...` |
| Raw imported/captured source cards | `sources/...` |
| Compiled wiki concepts and query pages | `wiki/...` |
| Durable non-secret user-editable settings | `config/{owner}/...` |
| Generated runtime state, caches, indexes, sessions, and generated histories | `get_runtime_dir()` outside the vault |
| Old but meaningful material that should not affect active workflows | `archive/{domain}/...` |

## First-Pass Folder Mapping

| Current Root | Migration Target |
| --- | --- |
| `_drafts/staging/` | `drafts/staging/` |
| `career-ops/` | `notes/career/`, with durable config under `config/career-ops/` |
| `books/` | `notes/books/` |
| `reading-list/` | `notes/books/` |
| `finance/` | `notes/finance/`, with durable config under `config/finance/` when present |
| `health/` | `notes/health/` |
| `growth/` | `notes/career/growth/` or `notes/personal/growth/` after item review |
| `venture-augur/` | `notes/venture/` |
| `linkedin-writer/` | `notes/venture/content/linkedin/` |
| `content/` | `notes/content/` or `notes/venture/content/` after item review |
| `advisor/` | `notes/augur/advisor/` |
| `apple/` | Split by note meaning under `notes/`; durable config under `config/apple/` |
| `attention/` | `config/attention/` unless files are human notes |
| `dashboard/` | `config/dashboard/` when files are durable and human-editable |
| `google-workspace/` | `config/google-workspace/` for non-secret durable config |
| `updater/` | `config/updater/` for durable config; generated history to runtime or archive after review |
| `file-manager/` | `config/file-manager/` for workspace profile/config |
| `remote-access/` | Runtime dir if generated; `config/remote-access/` only for durable human-editable config |
| `memory/` | Review separately: active memory index should not become a generic root if it is runtime-generated |

## Discovery And Operation Rules

- Skill discovery scans `skills/` only for active private vault skills.
- Skill discovery does not scan `drafts/`, `archive/`, `notes/`, `sources/`, `wiki/`, or `config/`.
- `drafts/` may contain `SKILL.md`, scripts, pages, commands, prompts, and workflows, but all are inactive.
- `archive/` may contain old notes, old source material, old configs, or old implementation material, but all are inactive.
- Browse may index `drafts/` and `archive/` only under explicit inactive tabs.
- Draft and archive Browse results must be visibly marked inactive.
- Normal `/ask`, wiki compounding, recommendations, dashboards, MCP tools, commands, actions, agents, prompts, and workflows exclude `drafts/` and `archive/`.
- `config/` is never a broad discovery root. Individual features may load explicit paths such as `config/google-workspace/config.yaml`.

## Promotion And Restoration

Draft promotion is a physical move:

```text
drafts/staging/<release>/skills/<skill>/ -> skills/<skill>/
```

Archive restoration is also a physical move:

```text
archive/<domain>/<item> -> notes/<domain>/<item>
archive/sources/<item> -> sources/<item>
```

Moving a file out of `archive/` or `drafts/` is the opt-in signal that it can influence active behavior again.

## Migration Phases

### Phase 1: Guards Before Moves

- Add or verify path helpers for `drafts/`, `drafts/staging/`, `archive/`, `notes/`, and `config/`.
- Update discovery, sync/export, dashboard route generation, MCP registration, and wiki/RAG indexing to ignore `drafts/` and `archive/` by default.
- Add Browse inactive scopes for Drafts and Archive.
- Add tests proving `drafts/` does not register skills, tools, commands, pages, prompts, agents, or workflows.

### Phase 2: Rename Draft Staging

- Move `_drafts/staging/` to `drafts/staging/`.
- Update all references to the staging path.
- Fail or report if old `_drafts/` is repopulated after the migration.

### Phase 3: Move Obvious Root Data

- Move obvious human notes and personal data into `notes/{domain}/`.
- Move obvious durable non-secret config into `config/{owner}/`.
- Move runtime-generated state out of the vault.
- Keep ambiguous files in place until reviewed rather than bulk-moving by folder name.

### Phase 4: Item Review

For each ambiguous item, classify it as:

- active note -> `notes/{domain}/`
- source card -> `sources/`
- durable config -> `config/{owner}/`
- inactive historical material -> `archive/{domain}/`
- runtime state -> `get_runtime_dir()`
- delete only after explicit review evidence

### Phase 5: Enforcement

- Add a vault-root audit that fails on unapproved root folders.
- Add a `SKILL.md` placement audit:
  - allowed in `skills/`
  - allowed in `drafts/`
  - disallowed in `notes/`, `sources/`, `wiki/`, `archive/`, and `config/`
- Add a discovery audit proving no inactive draft/archive material contributes active runtime surfaces.

## Acceptance Criteria

- Vault root contains only the final root contract, plus any explicitly approved temporary migration roots.
- `drafts/` is tracked in git and ignored by normal operation.
- `archive/` is tracked in git and ignored by normal operation.
- Browse has explicit Drafts and Archive scopes.
- Normal `/ask` and wiki compounding exclude Drafts and Archive by default.
- Skill discovery and client export read active private skill implementations only from `skills/`.
- Runtime-generated state is not stored in the vault.
- Durable human-editable config is under `config/` and secrets are excluded.
- No `SKILL.md` appears under `notes/`, `sources/`, `wiki/`, `archive/`, or `config/`.
- Root folders named after old skill/data domains are removed or explicitly retained by documented exception.
- Augur repo changes and Au-vault content moves are committed separately.

## Risks

### Draft leakage

If a scanner still treats `drafts/` as a skill root, inactive tools and pages may become active. Discovery and generated-surface tests must land before the path move.

### Personal data misclassification

Folder names are not enough to classify personal data. Ambiguous files must be reviewed item-by-item.

### Runtime state pollution

Generated histories, caches, and indexes can look like useful YAML or Markdown. The migration needs source checks before deciding that these belong in `config/` or `notes/`.

### Browse confusion

Drafts and Archive should be searchable but visibly inactive. If Browse presents them like active knowledge, users may not understand why results do not affect `/ask` or dashboards.

## Non-Goals

- Do not activate every staged skill.
- Do not move all root data into `drafts/`.
- Do not introduce `_system/`.
- Do not make `config/` a broad discovery root.
- Do not delete ambiguous personal data in the first pass.
- Do not change the runtime directory contract.
