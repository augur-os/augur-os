---
status: Implemented
date: 2026-05-13
deciders:
  - gsannikov
related:
  - ADR-571
  - ADR-731
  - ADR-738
  - ADR-744
hub: brain
tags:
  - wiki
  - ingest
  - schema
  - citations
  - synthesis
superseded_by: null
spec_file: 2026-05-14-compiled-truth-timeline-design.md
plan_file: 2026-05-14-compiled-truth-timeline.md
---

# ADR-740: Compiled-Truth + Timeline Pattern for Wiki Pages

## Status

Implemented (2026-05-15). The wiki compiler now writes `concept-article-v4`
concept pages with separate `## Compiled truth` and append-only `## Timeline`
sections, rewrite-proposal application is scoped to compiled truth, and the
v3-to-v4 migration is exposed through the wiki command surface as a dry-run-first
operation.

Verification: focused ADR-740 wiki tests pass through the auto-test harness
(`38 passed`), auto-lint reports no issues, the real vault migration dry-run was
reviewed before apply, and the apply migrated 37 real concept pages with a
runtime backup under `get_runtime_dir()/garbage_collector/wiki-pre-740-*`.
Post-apply validation confirmed all 37 migrated concept pages are v4, contain
compiled truth plus cited timeline entries, have no malformed timeline quality
flags, and the migration is idempotent on a second dry-run.

## Context

Wiki pages today mix two kinds of content in a single body:

- **Human-curated assessment** (what we believe is true about this concept/entity)
- **Machine-appended evidence** (what was observed, when, from where)

When the wiki-update flow runs, it edits the same body the human edits. Citations and provenance are inconsistent. The user has no safe place to write a clean assessment without it being overwritten by the next synthesis pass.

A reference implementation (gbrain) splits each page into **compiled truth** (top, editable, human-owned) over an **append-only timeline** (bottom, machine-owned, every entry carries a source citation). This makes synthesis safer, citations enforceable, and the human/machine boundary obvious to both.

## Decision

Wiki pages adopt a two-section schema:

```
---
... frontmatter (including _edges, _entity_tier per ADR-738) ...
---

# <Page Title>

## Compiled truth

<human-editable summary. machine writes here only as a proposal, never directly.>

## Timeline

- _at: 2026-05-13T10:00Z  _source: source-card://<id>
  Brief observation in markdown.
- _at: 2026-05-12T09:30Z  _source: vault://notes/<file>.md
  Brief observation in markdown.
```

Concretely:

1. New page template at `shared-vault/skills/ingest/assets/templates/wiki-page.md`.
2. **Compiled-truth section**: free markdown, human-editable, no automated machine writes for existing v4 pages. Machine-generated truth updates land as **proposals** in the existing `wiki-rewrite-proposals` flow, which the user (or the active AI client via `oneshot`) approves. Initial creation of a brand-new concept page may write the first compiled truth because no human-owned zone exists yet.
3. **Timeline section**: append-only entries. Each entry MUST carry `_at:` (ISO timestamp) and `_source:` (URI: `source-card://`, `vault://`, `inbox://`). Editing prior timeline entries is forbidden by lint; correction goes via a new entry that supersedes.
4. `wiki-update`, `wiki-apply-concept-batch`, and `wiki-apply-top-rewrite-proposal` are refactored to:
   - Append to timeline (deterministic, in-process)
   - Propose truth-section diffs (judgment, dispatched via `oneshot` to the active AI client per Rule #11)
5. `wiki-lint` gains new rules:
   - Timeline entries missing `_source` or `_at` fail lint
   - Compiled truth must not contain `_source:` lines (those belong in the timeline)
6. **Migration**: existing concept pages get split via a one-shot script in `shared-vault/skills/ingest/scripts/`. Concept pages have no inline citations — they have a machine-regenerated `## Evidence` section; migration converts each `## Evidence` entry into a `## Timeline` entry (`_at:` from the page's `_updated`, `_source:` from the evidence line's URI) and moves the rest of the article under `## Compiled truth`, preserving the `concept-article-v3` sections as `###` subsections (schema bumps to v4). Scope is `_page_type: concept`. Migration runs dry-run first, produces a diff for review, backs up pre-migration page bodies under `get_runtime_dir()/garbage_collector/wiki-pre-740-<timestamp>/`, and is idempotent.

## Non-Goals

- No machine writes to compiled truth without explicit user or dispatched-client approval. Synthesis is a proposal pipeline, not an autonomous editor.
- No database for the timeline. Append-only markdown only.
- No removal of `wiki-update` — it is refactored, not replaced.
- No retroactive edit of timeline entries — corrections are appended, never mutated.

## Consequences

- Wiki schema change requires a one-time migration; old pages still render but flunk lint until migrated.
- `wiki-lint` rules tighten; ADR-732 hygiene loops integrate the new rules.
- ADR-738 graph edges can be cited from timeline entries (`_source: graph://<edge-id>`).
- Dream cycle (ADR-744) consumes the timeline to synthesize compiled-truth proposals.

## Related

- ADR-571 (vault frontmatter system keys)
- ADR-731 (memory synthesis consolidation)
- ADR-738 (typed graph)
- ADR-744 (dream cycle compiles truth from timeline)

## Impact Manifest

```yaml
paths_renamed: []
apis_changed:
  - "concept wiki pages move from compiler_version concept-article-v3 to concept-article-v4"
  - "wiki-update and wiki-apply-concept-batch append timeline entries instead of overwriting existing compiled truth"
  - "wiki-apply-top-rewrite-proposal is scoped to the ## Compiled truth section for v4 concept pages"
patterns_deprecated:
  - "machine-regenerated ## Evidence section on concept pages"
  - "whole-body rewrites of existing concept wiki pages"
files_affected:
  - shared-vault/skills/ingest/assets/seeds/wiki-schema/page-types.yaml
  - shared-vault/skills/ingest/assets/seeds/wiki-schema/lint-rules.yaml
  - shared-vault/skills/ingest/assets/templates/wiki-page.md
  - shared-vault/skills/ingest/scripts/wiki_timeline.py
  - shared-vault/skills/ingest/scripts/wiki_v4_migration.py
  - shared-vault/skills/ingest/scripts/wiki_concept_state.py
  - shared-vault/skills/ingest/scripts/wiki_concept_pages.py
  - shared-vault/skills/ingest/scripts/wiki_quality.py
  - shared-vault/skills/ingest/scripts/wiki_maintenance.py
  - shared-vault/skills/ingest/scripts/mcp/wiki_tools.py
  - docs/agent-topics/WIKI.md
```
