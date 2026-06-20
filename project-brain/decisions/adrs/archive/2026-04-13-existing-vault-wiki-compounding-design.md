# Existing Vault Wiki Compounding Design

**Date:** 2026-04-13
**Status:** Draft
**Scope:** Existing-vault onboarding, wiki compounding semantics, `/ask` relationship to wiki, and Browse action meaning

## Summary

Augur already supports an external vault and a separate `wiki/` folder inside that vault, but the current product behavior still treats the wiki too much like an indexed artifact instead of the system's compiled knowledge layer.

This spec defines the intended behavior for users who already have a vault before installing Augur. The wiki model should feel like:

1. point Augur at an existing vault
2. start asking questions immediately
3. let the wiki layer grow and harden over time

The key correction is semantic:

- `Reindex` remains an indexing action and keeps its per-tab meaning in Browse
- wiki intelligence lives under wiki `New` and `Update`
- wiki compounding happens through agent instruction-guided second-brain interactions
- `/ask` remains a second-brain conversation surface, not a search command

## Problem

The current implementation has the right building blocks but misses the core LLM-wiki behavior.

### What exists now

- External vault resolution already exists through `project.yaml` and `get_vault_dir()`
- `vault/wiki/` already exists as a distinct storage location
- wiki CRUD, wiki scan, wiki maintenance, wiki report, and `/ask` retention already exist
- broad RAG indexing already covers documents, vault, skills, pages, and other categories

### What feels wrong today

- `/ask` still draws too directly from raw vault retrieval instead of clearly speaking from the compiled wiki/memory/synthesis layers
- wiki `reindex` currently implies more intelligence than it actually performs
- wiki behavior is described as compounding, but much of the visible product path still feels manual and infrastructure-oriented
- the system is close to the Karpathy-style LLM wiki concept, but not yet behaving like it by default

## Design Principles

1. **Existing vault first.** Assume many users already have an Obsidian or markdown vault before installing Augur.
2. **Wiki is compiled knowledge.** The wiki is not raw storage, not a graph, and not generic chunk-RAG.
3. **`/ask` is conversation, not search.** `/ask` should answer as the user's second brain, not as a file-finder.
4. **Compounding is the real feature.** Rebuild commands are secondary; the main product value is ongoing wiki strengthening during second-brain use.
5. **`Reindex` keeps local meaning.** In Browse, `Reindex` must always mean "refresh this tab's search/index representation," not "run a large knowledge workflow."
6. **Raw markdown stays raw.** Vault markdown is first-class source material for wiki synthesis and should not be flattened into document-style chunking just because infrastructure already exists for it.
7. **Instructions carry the behavior.** Compounding should primarily be a property of the agent's second-brain instructions, with `/ask` carrying stronger and more focused compounding guidance.

## Target Mental Model

The product should read as a three-layer system:

### 1. Sources

Anything Augur can learn from:

- existing vault notes
- new or changed documents
- new or changed dashboard pages
- new or changed skills
- retained `/ask` outcomes

### 2. Compiled Brain

The layers Augur maintains over those sources:

- wiki pages
- topic summaries
- hub summaries
- memory entries
- synthesis notes

### 3. Conversation Surface

`/ask` speaks from the compiled brain, with raw/source lookup used only when needed to fill gaps or validate freshness.

## Current Gap Analysis

### Gap 1: `/ask` is not clearly wiki-first

The current `/ask` implementation uses reflective vault search and memory assembly. That is useful, but it does not yet establish the wiki as the canonical compiled brain for second-brain answers.

**Desired behavior**

- `/ask` should prefer compiled wiki, memory, and synthesis context
- if the wiki is thin or stale, `/ask` may consult raw sources
- if the answer depends on raw source fallback, the system may gently indicate that wiki compounding or update would improve future answers

### Gap 2: Wiki `Reindex` is overloaded conceptually

In Browse, users already understand `Reindex` as a local indexing action. The wiki tab should not redefine it to mean "rebuild the wiki."

**Desired behavior**

- `Reindex` in `Pages` means reindex pages
- `Reindex` in `Vault` means reindex vault search/index entries
- `Reindex` in `Wiki` means reindex existing wiki pages so they are searchable like other content

This action should not synthesize or rewrite wiki content.

### Gap 3: Wiki creation and wiki indexing are mixed together

The system needs a separate user-facing concept for wiki creation and hardening.

**Desired behavior**

- `New` in the wiki page is the bootstrap/repair action
- `Update` in the wiki page is the explicit focused repair/hardening action
- `Reindex` in Browse only refreshes search/index artifacts

### Gap 4: Compounding is not yet a first-class operating behavior

The deepest conceptual miss is that wiki compounding is still too command-shaped. The LLM wiki idea is that once the system has the right rules and surfaces, meaningful second-brain interactions naturally strengthen the wiki over time.

**Desired behavior**

The wiki should be eligible to strengthen from high-quality second-brain interactions that work with knowledge such as:

- new vault note
- changed vault note
- new document
- new page
- new skill
- retained `/ask` synthesis or inferred pattern

`Reindex` should exist, but only for search freshness. Bootstrap belongs to wiki `New`, and deeper repair belongs to wiki `Update`.

## Action Semantics

### Browse `Reindex`

`Reindex` keeps the same meaning everywhere in Browse: refresh the searchable/indexed representation for the current tab's content.

#### Pages tab

- Rebuild page index/search artifacts for pages

#### Vault tab

- Rebuild vault index/search artifacts for vault content

#### Wiki tab

- Rebuild wiki index/search artifacts for existing wiki pages
- Do not create or rewrite wiki pages

### Wiki `New`

Wiki `New` should be smart rather than literal.

If there is no wiki yet:

- bootstrap the wiki from currently known Augur sources

If a wiki already exists:

- repair it
- fill obvious missing foundational pages
- harden links, summaries, and coverage

This action is not "create one page." It is "establish or re-establish the wiki as a usable compiled layer."

It also establishes the operating mode for future wiki compounding by ensuring the system has an initial compiled brain to build on.

### Wiki `Update`

Wiki `Update` is the explicit focused repair and hardening action.

It should:

- inspect where the existing wiki is thin, stale, or structurally weak
- identify which wiki pages should be updated
- create missing pages when warranted
- rewrite pages concisely rather than append blindly
- repair or strengthen coverage on top of the existing wiki

This is not the ordinary path for keeping the wiki current. It is the manual "do focused wiki work now" surface for cases where the user wants stronger repair or hardening.

## Existing Vault Onboarding

For users who already have a vault before installing Augur:

1. Augur points to the existing vault as source of truth
2. `/ask` works immediately
3. the wiki may not yet be comprehensive
4. wiki `New` can bootstrap or repair the wiki layer
5. second-brain interactions keep compounding it, and wiki `Update` provides explicit repair/hardening when needed
6. wiki `Reindex` makes wiki pages searchable after they exist

This keeps onboarding simple while preserving the long-term wiki model.

## Compounding via Agent Instructions

Wiki compounding should primarily happen because the agent is operating under second-brain instructions, not because every source mutation independently triggers a workflow.

### Bootstrap phase

1. User points Augur at an existing vault and known sources.
2. Wiki `New` builds the first usable wiki layer.
3. From that point on, the system is considered to be in wiki-compounding mode.

### Steady-state phase

After bootstrap, compounding behavior is governed by agent instructions:

- global second-brain instructions define that meaningful second-brain interactions may strengthen the wiki
- this applies across second-brain surfaces, not only `/ask`
- the interaction itself is the high-quality signal, while source material remains supporting input

### Focused repair phase

When the user wants stronger wiki work than ordinary interaction-driven compounding provides, wiki `Update` performs explicit repair and hardening on top of the existing wiki.

## Source Coverage for Wiki Compounding

Wiki compounding should be able to draw on inputs from all of these categories:

- vault notes
- documents
- retained `/ask` outcomes
- user-added skills
- user-added or changed pages

These are supporting knowledge inputs, not independent compounding triggers by themselves. This matters because Augur's brain is broader than the vault alone. The wiki should compile understanding across the system, not just over raw notes.

## Relationship to RAG

Augur's broad RAG indexing remains valid and useful. It indexes multiple categories so content is searchable across the product.

But wiki compounding must remain conceptually separate:

- **RAG/indexing** makes content searchable
- **Wiki compounding** turns changing source material into maintained knowledge
- **`/ask`** converses with that maintained knowledge

### Explicit non-goals

- Do not introduce a graph layer as the canonical wiki model
- Do not treat vault markdown like generic document chunks as the main wiki strategy
- Do not turn `/ask` into a search UI

## `/ask` Behavior

`/ask` should behave like a second-brain conversation rooted in the compiled knowledge layers.

### Desired answer strategy

1. Prefer wiki, memory, and synthesis context
2. Use source lookup to validate or fill gaps
3. Answer in reflective voice
4. Retain durable outcomes when appropriate
5. Treat the interaction as a high-value compounding signal, especially for `/ask`

### Important distinction

`/ask` may use retrieval internally, but the user experience should never collapse into "search results with commentary."

`/ask` is not a direct "write wiki page" command. Its primary user-facing job remains conversation. But after bootstrap, `/ask` is the strongest second-brain interaction surface for deciding what should strengthen in the compiled wiki.

### Dedicated `/ask` guidance

Global second-brain instructions should allow compounding across interaction surfaces, but `/ask` should have additional dedicated instructions because it is the highest-signal reflective surface.

Those dedicated instructions should make `/ask` more focused about:

- noticing clarified understanding
- strengthening an existing wiki page when the interaction sharpens it
- identifying a missing concept or page
- surfacing contradictions or gaps worth compiling
- improving cross-links and summaries indirectly through post-interaction compounding

## Implementation Direction

This spec intentionally does not prescribe a graph-based architecture. The needed shift is primarily behavioral and semantic.

The implementation should focus on:

- separating wiki creation/update from wiki indexing
- making instruction-driven compounding first-class
- making `/ask` clearly operate from compiled knowledge
- distinguishing global second-brain compounding rules from `/ask`-specific compounding rules
- preserving Browse `Reindex` semantics across tabs

## Error Handling

- If no wiki exists, wiki `Reindex` should report that there are no wiki pages to index and suggest wiki `New`
- If wiki `Update` finds no meaningful repair or hardening work, it should report that the wiki is already current
- If `/ask` must rely heavily on raw-source fallback because compiled coverage is weak, the system may suggest wiki `New` or `Update`
- If ordinary interaction-driven compounding fails, the failure should surface as wiki debt rather than silently leaving the compiled brain stale

## Testing Strategy

### Product behavior tests

- Existing vault with no wiki: `/ask` works, wiki `New` bootstraps, wiki `Reindex` only indexes after pages exist
- Existing vault with partial wiki: wiki `New` repairs/hardens rather than duplicating
- Existing wiki with changed sources: wiki `Update` revises affected coverage
- Browse tab `Reindex` actions stay tab-local and do not trigger unrelated synthesis

### Semantics tests

- `/ask` remains conversational and does not expose raw search mechanics
- wiki compounding can draw on non-vault inputs such as documents, skills, pages, and retained `/ask` outcomes
- wiki `Reindex` never rewrites page content
- second-brain interaction instructions and `/ask`-specific instructions do not collapse `/ask` into an explicit wiki-writing UI

## Decision

Adopt the following product contract:

- Existing vaults are first-class onboarding path
- The wiki is a continuously maintained compiled brain
- `Reindex` is an indexing action, not a synthesis action
- Wiki `New` bootstraps when absent and repairs/hardens when present
- Wiki `Update` is the explicit focused repair/hardening action
- Wiki compounding should happen through global second-brain agent instructions after bootstrap
- `/ask` should use dedicated instructions because it is the strongest second-brain compounding surface
- `/ask` is a second-brain conversation surface over compiled knowledge, not a search command
