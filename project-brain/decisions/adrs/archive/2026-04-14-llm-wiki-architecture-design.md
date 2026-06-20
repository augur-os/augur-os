# LLM Wiki Compiler Architecture Design

> **Superseded by ADR-561.** This artifact describes the retired RAG-backed wiki compile-state model. It remains historical context only. Do not implement or extend the `source-summary`, `wiki_compile_status`, `wiki_targets`, or `wiki-compile-*` backlog semantics from this document.

**Date:** 2026-04-14
**Status:** Draft
**Scope:** Source priorities, compiler architecture, `/ask` compounding, RAG-backed import state, and phased rollout for Augur's compiled wiki

## Summary

Augur's current wiki has the right building blocks but the wrong center of gravity. It still behaves too much like a generated layer of hub summaries over indexed files. The intended product is different: a persistent compiled wiki that sits between indexed user data and query-time answers.

This spec defines that pivot.

The wiki should compile durable knowledge from existing indexed sources, not duplicate those sources. The highest-priority inputs are user data and user behavior signals: retained `/ask` outcomes, vault notes, documents, user-created pages, `SKILL.md`, actions, commands, and integrations. ADRs and repo docs remain important, but mainly as architecture context rather than the primary knowledge surface. Direct code summarization is a fallback, not the default strategy.

RAG remains the indexed-source substrate and search layer. The wiki compiler consumes RAG entries directly, rewrites wiki pages as a maintained knowledge layer, and records wiki compile state back onto those same RAG entries. This avoids inventing a parallel inventory layer while still allowing backlog management, freshness checks, and rate-limited bootstrapping across large existing corpora.

`/ask` is the strongest compounding signal in the system. It should read the compiled wiki first, use indexed sources to fill gaps, and feed durable outcomes back into the wiki through retention and compiler prioritization. Over time, page topics should emerge dynamically from repeated signals rather than being constrained to a fixed ontology.

## Problem

### What exists today

- Broad RAG indexing already covers vault, documents, wiki, pages, actions, commands, integrations, skills, ADRs, and other categories.
- The wiki already has CRUD, tag manifests, maintenance helpers, reporting, and rewrite proposal infrastructure.
- `/ask` already has reflective answering and retention routing.

### What feels wrong today

- The wiki still reads too much like a refined index instead of authored compiled knowledge.
- Hub overview pages are doing too much of the visible work.
- Important user knowledge is flattened into broad hubs instead of emerging as first-class pages.
- `/ask` helps the second brain but does not yet clearly dominate what the wiki learns next.
- The system can tell that files exist, but it does not yet have a disciplined compile backlog over those indexed sources.

## Design Principles

1. **User data first.** The wiki should primarily learn from what the user stores, writes, changes, asks, and uses.
2. **RAG is the source inventory.** Do not create a duplicate raw-source inventory. Reuse existing RAG entry files and metadata.
3. **Compiled wiki, not generated index.** Wiki pages should express what is true, what changed, what tensions remain, and how ideas connect.
4. **`/ask` is the strongest signal.** Repeated `/ask` outcomes should shape page creation and strengthening more strongly than background source noise.
5. **Dynamic ontology.** Page types are stable, but page topics emerge from repeated signal over time.
6. **Rewrite, do not append blindly.** Wiki pages are compiled artifacts that should be rewritten to stay coherent.
7. **Fast usefulness beats first-pass completeness.** Large existing corpora should be bootstrapped incrementally and rate-limited.
8. **Support files are support files.** `index.md` and `log.md` help navigation and chronology, but they are not substitutes for the wiki itself.

## Source Priority

The compiler should prioritize sources in this order:

1. retained `/ask` outcomes
2. vault notes
3. documents
4. user-created pages
5. `SKILL.md`, actions, commands, integrations
6. ADRs and repo docs
7. direct code summaries only when the architecture or behavior is not already represented elsewhere

This keeps the wiki centered on the user's actual work and evolving intent rather than expensive repo introspection.

## System Layers

### 1. Source layer

The source layer is the existing user and system knowledge already indexed by Augur:

- vault
- documents
- user-created pages
- `SKILL.md`
- actions
- commands
- integrations
- ADRs and repo docs

No duplicate raw-source mirror is introduced.

### 2. Retrieval layer

RAG remains the retrieval substrate.

Its job is to:

- detect indexed sources
- store source metadata
- provide search and lookup
- support freshness and backlog decisions

It is not the wiki.

### 3. Compile layer

The compiler reads relevant RAG entries, extracts durable claims and tensions, and updates wiki pages.

### 4. Wiki layer

The wiki is the persistent markdown knowledge artifact.

It should contain:

- durable syntheses
- concept pages
- comparisons
- query-derived knowledge
- connections
- contradictions and open questions when relevant

### 5. Support layer

Support artifacts include:

- `index.md`
- `log.md`
- wiki tags manifest
- lint reports
- rewrite proposals
- search metadata

These help the wiki operate but are not the main knowledge layer.

## RAG As Indexed-Source Inventory

The current RAG system already stores useful metadata in per-entry markdown files under `get_rag_dir()`, including:

- `type`
- `source_path`
- `checksum`
- `modified`
- `indexed_at`
- `hub`
- `name`

Some categories also already include richer metadata, such as:

- documents: `format`, `size_bytes`, `created`, `sub_dir`, `extraction_error`
- pages: `route`, `pageType`, `state`, `skill`, `related`
- actions: `dispatch`, `label`, `bundle`, `tags`
- integrations: `integration_type`, `scope`, `tool_count`, `cli_tools`

The top-level manifest at `get_rag_dir()/_meta/manifest.yaml` is useful for global stats and recent indexing, but it is intentionally thin. The per-entry markdown files are the canonical indexed-source inventory the wiki compiler should consume.

### New required semantics

The missing semantic is not a new registry. It is compile status on the existing RAG entries.

Each relevant RAG entry should be able to carry fields such as:

- `wiki_compiled_at`
- `wiki_compiled_checksum`
- `wiki_targets`
- `wiki_compile_status`

`wiki_compile_status` values should be lightweight and explicit:

- `pending`
- `compiled`
- `needs-recompile`
- `deferred`
- `failed`

This keeps source indexing and wiki compilation in the same inventory model.

## Compiler Model

The compiler should work over RAG entries rather than raw file scanning.

For each cycle:

1. load candidate RAG entries from prioritized categories
2. rank them by freshness, user importance, and `/ask` alignment
3. decide what concept or page each item should strengthen
4. rewrite affected wiki pages
5. write compile-state fields back to the consumed RAG entries
6. refresh wiki support artifacts

### Core compile decisions

For each cluster of signal, the compiler should decide whether to:

- update an existing page
- create a new page
- create a comparison page
- file a durable query output
- record a contradiction or open question
- link pages together
- defer low-value material for a later cycle

## Dynamic Page Growth

The wiki should not start from a rigid topic taxonomy.

Stable page types:

- `overview`
- `topic`
- `entity`
- `comparison`
- `query-output`
- `source-summary`

Dynamic page topics:

- emerge from repeated concepts in `/ask`
- emerge from repeated themes across vault and documents
- emerge from workflow signals in actions, commands, integrations, and skills
- emerge from recurring tensions, not only recurring certainties

This means the wiki may grow pages like:

- `management-style`
- `startup-ideas`
- `learning-system`
- `founder-positioning`
- `local-first-execution`
- `agent-workflow-patterns`

without those being predefined in configuration.

## Page Creation And Strengthening Rules

A concept should become or strengthen a page when one or more of these conditions hold:

- it repeats across multiple high-priority sources
- it repeats across retained `/ask` outcomes
- it appears in multiple operational surfaces such as commands, actions, and integrations
- it expresses a durable preference, principle, or behavior pattern
- it forms a meaningful contradiction or unresolved tension

This rule applies across hubs. Hubs are context, not the final ontology.

## `/ask` As The Strongest Compounding Signal

`/ask` is not just another source category. It is the highest-value prioritization signal for what the wiki should care about next.

### `/ask` flow

1. Read compiled wiki first
2. Use indexed sources only to fill gaps or validate freshness
3. Answer the user
4. Classify the outcome
5. Retain durable outcomes
6. Feed those outcomes into compiler prioritization and wiki updates

### Outcome classes

- `decision`
- `preference`
- `insight`
- `inferred-pattern`
- `contradiction`
- `open-question`
- `ephemeral`

### Wiki implications

Retained `/ask` outcomes should be able to:

- strengthen an existing page
- create a new topic candidate
- create or strengthen a comparison page
- add an open tension to a page
- create a `query-output` page when an answer is durable enough to reuse
- increase the priority score of related RAG entries during compile backlog selection

Repeated `/ask` topics should outrank old, cold background files when deciding what the wiki deepens next.

## Import And Compile Flow

The import mechanism should be defined as a compiler workflow over RAG detection, not as a second ingestion database.

### Standard flow

1. a file is added or changed in vault, documents, pages, or another indexed source surface
2. RAG indexes it and writes or updates the corresponding entry file
3. the compiler sees that the entry is `pending` or `needs-recompile`
4. the compiler reads the source through its indexed path and metadata
5. relevant wiki pages are created or rewritten
6. the entry is marked `compiled` for the current checksum

### Example: document drop

When the user drops a new file into `documents/`:

1. RAG indexes the file and creates or updates its document entry
2. the compiler recognizes that the current checksum has not yet been compiled into the wiki
3. the compiler reads the document
4. it updates or creates the relevant wiki pages
5. if import policy allows it, the document may be renamed or moved to a better location within `documents/`
6. the RAG entry is updated with the compile result and new source path if relocation occurred

### Optional relocation

Relocation is part of import policy, not a mandatory step for every source.

The compiler may:

- leave a file in place
- propose a better location
- move and rename it automatically when the target context is clear and safe

This is especially useful for user-dropped documents that arrive in generic or temporary locations.

## Backlog, Rate Limits, And Large Existing Corpora

First-time bootstrap must handle large existing corpora honestly.

The system should be able to say:

- how many files are indexed
- how many have been compiled into the wiki
- how many are pending
- how many are deferred or failed

It should not try to compile everything equally in one pass.

### Priority scoring

Pending compile candidates should be ranked roughly by:

1. direct `/ask` relevance or repeated `/ask` themes
2. recently changed user files
3. high-signal vault and document sources
4. user-created pages
5. operational surfaces such as skills, actions, commands, integrations
6. ADRs and docs
7. old low-signal backlog

### Rate limits

Each compile loop should cap:

- maximum source entries consumed
- maximum wiki pages rewritten
- maximum page creations
- optional token or model budget

This keeps the wiki useful while avoiding low-quality large-batch synthesis.

### Bootstrap phases

#### Phase A: inventory and prioritization

- index the full corpus through existing RAG flows
- mark entries as `pending` where no matching wiki compile exists
- compute the initial backlog

#### Phase B: usable compiled base

- compile the highest-priority concepts and sources
- create a small number of real topic pages and overviews
- avoid spending the first pass on exhaustive long-tail material

#### Phase C: background deepening

- continue draining the backlog over repeated cycles
- prioritize fresh user activity and `/ask` pressure over old cold files
- keep refining pages as better source clusters appear

## Wiki Page Model

The wiki should stop behaving like folder summaries and start behaving like authored compiled knowledge.

Default page sections should move toward:

- `Current Thesis`
- `What This Page Knows`
- `Recent Additions`
- `Open Questions / Tensions`
- `Related Pages`
- `Source Basis`

Page types may tailor this structure, but the key behavior should stay the same:

- express stable understanding
- show what changed
- keep tensions visible
- ground claims in source basis

## `index.md`, `log.md`, And The RAG Index

These three artifacts should have distinct roles.

### `index.md`

Readable wiki map for humans and agents.

It should contain:

- page links
- one-line summaries
- type or category context

It is navigation, not retrieval infrastructure.

### `log.md`

Append-only chronology of:

- compiles
- filed query outputs
- lint passes
- major restructures

It is timeline, not knowledge.

### RAG index

Invisible retrieval infrastructure over indexed sources and wiki pages.

It should remain conceptually separate from `index.md`.

## Lint

Lint should be a first-class maintenance layer over the compiled wiki.

It should detect:

- contradictions between pages
- stale claims superseded by newer compiled evidence
- orphan pages
- weak or missing links
- important repeated concepts without a page
- thin pages that still read like indexes
- pages that should split because they are carrying multiple durable concepts

Lint output should drive future rewrite and creation work rather than pretending the wiki is complete.

## Operational Commands

The current command semantics stay broadly valid but should be understood within this architecture:

- `wiki-reindex`
  - refresh searchable/indexed representation for existing wiki pages
  - does not compile new knowledge
- `wiki-rebuild`
  - establish or repair a usable compiled wiki from current indexed sources
  - can consume the pending compile backlog in a rate-limited way
- `wiki-update`
  - strengthen existing pages, create missing pages, and deepen weak or stale areas

## Non-Goals

- Do not add a second indexed-source inventory beside RAG.
- Do not duplicate raw sources into another mirror layer.
- Do not treat README files as canonical truth just because they exist.
- Do not make code summarization the main way the wiki understands Augur.
- Do not let hub overviews remain the main visible artifact of the wiki.
- Do not force a fixed topic taxonomy up front.

## Phased Rollout

### Chunk 1: RAG-backed compile state

- add wiki compile fields to existing RAG entries
- compute pending and stale compile candidates from RAG metadata
- report backlog honestly

### Chunk 2: Dynamic page candidate extraction

- derive page candidates from `/ask`, vault, documents, pages, skills, actions, commands, integrations, and ADRs/docs
- prioritize by repeated signal and user relevance

### Chunk 3: True page taxonomy

- strengthen first-class `topic`, `entity`, `comparison`, `query-output`, and `source-summary` behavior
- reduce reliance on hub overviews as the primary compiled artifact

### Chunk 4: Compiler rewrite flow

- decide update/create/link/tension actions per concept cluster
- rewrite pages as compiled knowledge artifacts

### Chunk 5: `/ask` filing loop

- let durable `/ask` outcomes drive page creation, strengthening, and `query-output` filing systematically

### Chunk 6: Rate-limited backlog processing and relocation policy

- process large pending corpora incrementally
- optionally normalize document placement when the target context is clear

### Chunk 7: Lint and health layer

- detect contradictions, orphans, thin pages, and missing high-signal concepts
- turn health gaps into explicit maintenance work

## Recommendation

Augur should pivot from a hub-overview rewrite system to a true compiled wiki architecture over existing indexed user data.

The critical design choices are:

- reuse RAG as the indexed-source inventory
- record wiki compile state on existing RAG entries
- prioritize `/ask` over background source noise
- let page topics emerge dynamically
- rate-limit large backlogs instead of attempting full immediate coverage

This gives Augur a real path to the intended LLM-wiki model: a persistent, compounding knowledge base that grows from what the user stores, asks, and actually uses.
