---
date: 2026-05-14
status: Accepted
adr: ADR-740
deciders:
  - gsannikov
related:
  - ADR-571
  - ADR-731
  - ADR-738
  - ADR-744
---

# Compiled-Truth + Timeline Pattern for Wiki Pages — Design

> Design spec for **ADR-740**. Companion to the thin index ADR at
> `docs/adrs/ADR-740-compiled-truth-and-timeline-wiki-pattern.md`.
> The implementation plan derived from this spec lives at
> `docs/superpowers/plans/2026-05-14-compiled-truth-timeline.md`.

## Goal

Split wiki **concept** pages into a human-owned, proposal-gated **Compiled
truth** zone over an append-only, machine-owned **Timeline** zone. Today every
concept page is fully machine-compiled (`_compiler_version: concept-article-v3`,
8 sections, regenerated each compile) — the user has no place to write an
assessment that survives the next synthesis pass. The split makes synthesis safe
(no silent overwrites), citations enforceable (every timeline entry carries
`_at:` + `_source:`), and the human/machine boundary explicit to both.

## Premise Correction

ADR-740's first draft implied migration could split inline cited and uncited
paragraphs. **Concept pages have no inline citations** — they have a separate
machine-regenerated `## Evidence` section. The real migration (below) converts
`## Evidence` entries → timeline entries and the rest of the article → the
compiled-truth umbrella. The ADR body was corrected in the readiness pass that
accepted this spec.

## Non-Goals

Carried from ADR-740, reaffirmed:

- **No machine writes to compiled truth without approval.** Synthesis is a
  proposal pipeline, not an autonomous editor.
- **No database for the timeline.** Append-only markdown only.
- **No removal of `wiki-update`** — it is refactored, not replaced.
- **No retroactive edit of timeline entries** — corrections are appended, never
  mutated.
- **Concept pages only.** Query pages (`_page_type: query`) and support pages are
  regenerated query *outputs*, not durable knowledge with a human/machine
  boundary — they keep their current schema. Scope is `_page_type: concept`.

## Architecture

### Schema — `concept-article-v3` → `concept-article-v4`

The existing section schema is **preserved, not retired**. The v3 sections become
`###` subsections under a `## Compiled truth` `##` umbrella; `## Evidence` is
replaced by `## Timeline`. The schema YAML that `wiki_schema.py` loads
(`load_wiki_schema()`, `page_schema()`) keeps resolving concept pages by
`page_type: concept`; its required H2 sections move to the v4 wrappers
(`Compiled truth`, `Timeline`). Compiler-version-specific warnings live in
lint/quality logic.

```
---
... frontmatter (including _edges, _entity_tier per ADR-738) ...
_compiler_version: concept-article-v4
---

# <Page Title>

## Compiled truth
   ### Current Thesis
   ### What This Page Knows
   ### Key Dimensions
   ### Recent Shifts
   ### Open Tensions
   ### How to Use This
   ### Open Questions
   ### Source Basis

## Timeline

- _at: 2026-05-14T10:00:00Z  _source: source-card://abc123
  Brief observation in markdown.
- _at: 2026-05-12T09:30:00Z  _source: vault://notes/foo.md
  Earlier observation.
```

New page template: `shared-vault/skills/ingest/assets/templates/wiki-page.md`.

### Write discipline — the core change

The change is not the *shape* (v3 sections survive) — it is **who may write
where**:

- **`## Compiled truth`** and every `###` subsection — human-editable. For an
  existing v4 page, the machine **never writes here directly.** Machine-generated
  assessment updates go through the existing `wiki-rewrite-proposals` flow
  (`build_rewrite_proposals` → `apply_top_rewrite_proposal`, already in
  `wiki_maintenance.py`). The user — or the active AI client via `oneshot` (Rule
  #11) — approves a proposal before it is applied. The proposal flow already
  detects staleness via `_proposal_fingerprint` /
  `_stored_rewrite_signal_fingerprint`; that carries over unchanged. A brand-new
  concept page may receive initial compiled truth because no human-owned section
  exists yet.
- **`## Timeline`** — append-only, machine-owned. Appending a cited observation
  is deterministic and in-process — it is *not* a judgment call, so it needs no
  proposal. `wiki-update` and `wiki-apply-concept-batch` append timeline entries
  directly. Prior entries are never rewritten; a correction is a new entry.

### Refactor of the compiler

`wiki_concept_compiler.py` regenerates the whole page today. After ADR-740 its
concept-extraction output is **split at the write boundary**:

- Factual observations that carry a source → appended to `## Timeline`
  (deterministic, in-process).
- Synthesized assessment (the v3 section content) → a **rewrite proposal**
  against `## Compiled truth`, never a direct write.

`apply_rewrite_proposals` / `apply_top_rewrite_proposal` are scoped to operate
**only on the `## Compiled truth` zone** — they never touch the timeline.

`page_schema(page=..., page_type="concept")` currently resolves schema by
page-type, not compiler version. ADR-740 keeps that simple: the concept schema
requires the v4 wrapper sections (`Compiled truth`, `Timeline`), while the
compiler-version checks and migration warnings live in lint/quality logic.

## Timeline Entry Format

```
- _at: <ISO-8601 timestamp>  _source: <URI>
  <observation, markdown, indented under the bullet>
```

`_source:` URI schemes: `source-card://<id>`, `vault://<path>`, `inbox://<path>`,
and — per ADR-738 — `graph://<edge-id>`. The scheme set is open; the lint rule
checks *presence and shape*, not a closed enum. Entries are ordered newest-first.

## `wiki-lint` v4 Rules

Added to the existing `wiki-lint` (penalties via `wiki_schema.py:lint_penalties()`):

- A `## Timeline` entry missing `_at:` or `_source:` → **fail**.
- A `_source:` line appearing inside `## Compiled truth` → **fail** (citations
  belong in the timeline).
- `## Timeline` entries not in descending `_at:` order → **warn**.
- A `_page_type: concept` page still on `concept-article-v3` → **warn**
  ("migrate to v4") — it still renders, it just flunks v4 lint until migrated.

**On append-only enforcement:** lint cannot see history, so it checks *structure*
(entries well-formed, ordered). The append-only *guarantee* is enforced by the
writer (`wiki-update` only ever appends to the timeline) and, as a backstop, a
git-diff check in the ADR-732 hygiene loop flags any modification to an existing
timeline line. The spec does not claim lint alone proves immutability.

## Migration — v3 → v4

A one-shot, idempotent script in `shared-vault/skills/ingest/scripts/`:

1. For each `_page_type: concept` page on `concept-article-v3`:
   - Wrap the existing v3 sections (`Current Thesis` … `Open Questions`) under a
     `## Compiled truth` umbrella, demoting each from `##` to `###`.
   - Convert each `## Evidence` line into a `## Timeline` entry: `_at:` = the
     page's `_updated` (fallback `created`), `_source:` = the `vault:` URI already
     on that evidence line, observation = the evidence line's description.
   - Bump `_compiler_version` to `concept-article-v4`.
2. Idempotent — a v4 page is left untouched.
3. Query pages and support pages are skipped (out of scope).
4. Emits a diff for review before writing.
5. Before an apply run, copies pre-migration page bodies under
   `get_runtime_dir()/garbage_collector/wiki-pre-740-<timestamp>/`.

## Coexistence

- **ADR-738** — page frontmatter carries `_edges:` / `_entity_tier:`; the
  body-zone split is orthogonal to the frontmatter change, both coexist. Timeline
  entries can cite a typed edge via `_source: graph://<edge-id>`.
- **ADR-744** — the dream cycle's "compiled-truth refresh" phase reads recent
  `## Timeline` entries and emits compiled-truth *proposals* (never direct
  writes). ADR-740 only has to make the timeline readable and the proposal flow
  accept truth proposals — both are satisfied by this design.
- **ADR-731** — memory-synthesis consolidation feeds the same proposal pipeline;
  no conflict.

## Error Handling

- **Malformed timeline entry** — the writer validates `_at:` + `_source:` *before*
  appending, so a malformed entry is never written; `wiki-lint` is the backstop
  for hand-edited pages.
- **v3 page encountered by a v4 consumer** — renders fine (it is just markdown);
  flunks v4 lint with a "migrate" warning; the migration script is idempotent so
  it can be re-run any time.
- **Stale proposal** — a proposal built against a page since hand-edited is
  caught by the existing `_proposal_fingerprint` staleness check; it is dropped,
  not force-applied.
- **Migration partial failure** — a page that fails to parse is skipped, logged
  in the diff, and left on v3; a partial migration is acceptable and re-runnable.

## Testing Strategy

Tests live in `shared-vault/skills/ingest/augur/tests/`, imported via
`importlib.util.spec_from_file_location` per the Augur skill-test convention.
TDD per the writing-plans skill — one focused test file per unit:

- `test_wiki_v4_schema.py` — the v4 page structure parses; `## Compiled truth`
  umbrella with `###` subsections; `## Timeline` recognized; v3 still parses
- `test_timeline_append.py` — append-only append, `_at:` + `_source:` required,
  newest-first ordering, prior entries never rewritten, `graph://` URI accepted
- `test_compiled_truth_gate.py` — a direct machine write to `## Compiled truth`
  is rejected; a write via the proposal flow is accepted; the timeline is never
  touched by `apply_rewrite_proposals`
- `test_wiki_lint_v4.py` — timeline entry missing `_at:`/`_source:` fails;
  `_source:` inside compiled truth fails; out-of-order timeline warns; a v3
  concept page warns
- `test_migration_v3_to_v4.py` — `## Evidence` → `## Timeline`, v3 sections →
  `## Compiled truth` umbrella, `_compiler_version` bumped, idempotent, query
  pages untouched, diff emitted, runtime backup produced on apply

## Implementation Order

1. **v4 schema + template** — update the concept schema to require the v4 wrapper
   sections; write `assets/templates/wiki-page.md`.
2. **Timeline writer** — append-only timeline append with `_at:` + `_source:`
   validation, in the compiler / `wiki-update` path.
3. **Compiled-truth proposal gate** — refactor `wiki_concept_compiler.py` so
   synthesis emits a rewrite *proposal* (never a direct write); scope
   `apply_rewrite_proposals` / `apply_top_rewrite_proposal` to the
   `## Compiled truth` zone only.
4. **`wiki-lint` v4 rules** — the four rules above, wired into the existing lint.
5. **Migration script** — v3 → v4, idempotent, diff-first, backup-before-apply,
   concept pages only.
6. **Wire the commands** — `wiki-update`, `wiki-apply-concept-batch`,
   `wiki-apply-top-rewrite-proposal` to the new write discipline.
7. **Docs** — update `docs/agent-topics/WIKI.md` with the compiled-truth /
   timeline contract; regenerate agent instructions.

Phases 1–4 are a sequential pipeline. Phases 5–6 touch the compiler and the wiki
commands (shared files, sequential). Phase 7 is docs + the ADR body correction.

## Consequences

- Wiki concept pages gain a stable human/machine boundary: `## Compiled truth`
  (human-owned, proposal-gated) over `## Timeline` (append-only, machine-owned).
- The v3 section schema is preserved as the structure *within* compiled truth —
  no working schema is discarded.
- One-time v3 → v4 migration; old pages render but flunk v4 lint until migrated.
- `wiki-lint` gains four v4 rules; the ADR-732 hygiene loop integrates them.
- `wiki-update` and the compiler are refactored — synthesis becomes a proposal,
  evidence becomes an append — not replaced.
- Unblocks ADR-744's compiled-truth-refresh phase, which reads the timeline and
  proposes truth updates.
- ADR-740's body migration heuristic is corrected (pages have a `## Evidence`
  section, not inline citations).
