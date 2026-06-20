---
title: The Wiki Compounding Engine (LLM-Wiki Pattern)
summary: Augur's wiki engine turns ingest events into durable compiled-truth
  concept pages through a tiered extraction pipeline — source inventory, state
  reconciliation, batch extraction, and concept compilation — all governed by a
  schema that enforces required sections and cross-links per page type.
tags:
- wiki
- compounding
- knowledge
- architecture
aliases:
- wiki compounding engine
- LLM wiki pattern
- wiki concept compiler
related:
- '[[overnight-synthesis-dream-routine]]'
created: '2026-05-31T00:00:00Z'
_page_type: concept
_hub: dev
_sources:
- repo:project-brain/capabilities/skills/ingest/scripts/mcp/wiki_tools.py
- repo:project-brain/capabilities/skills/ingest/assets/seeds/wiki-schema/page-types.yaml
_cites:
- '[[repo:project-brain/capabilities/skills/ingest/scripts/mcp/wiki_tools.py]]'
- '[[repo:project-brain/capabilities/skills/ingest/assets/seeds/wiki-schema/page-types.yaml]]'
_compiler_version: concept-article-v4
_updated: '2026-05-31T00:00:00Z'
---

# The Wiki Compounding Engine (LLM-Wiki Pattern)

## Compiled truth

The wiki engine is Augur's implementation of the LLM-Wiki pattern (popularized by
Karpathy's April 2026 post): a knowledge base that a language model continuously
enriches through structured extraction becomes exponentially more useful than raw
retrieval. The pipeline has four distinct phases owned by separate modules. First,
`wiki_source_inventory` builds a source inventory of all ingest events eligible for
extraction. Second, `wiki_concept_state` (WikiCompilerState) reconciles compiler
state against the compiled wiki directory — tracking which sources are already bound,
which need extraction, and which extractions are stale. Third, `wiki_concept_compiler`
prepares extraction batches, runs them, summarizes results, and writes batch output
files. Fourth, tier logic (`wiki_tier`, `wiki_tier_caps`) gates which sources proceed
based on surface type and tier filter — a lightweight capacity control that prevents
low-signal sources from diluting the compiled knowledge.

The page-types schema (`page-types.yaml`) enforces structural contracts per page type.
A `concept` page requires exactly two sections — `Compiled truth` and `Timeline` —
with a minimum of two tags and one cross-link. An `overview` page requires four
sections. A `comparison` page requires `Where They Differ` and `Where They Overlap`.
The schema is seed data: it ships with the skill and is loaded at runtime to validate
every page that the compiler writes. This means the compounding engine self-enforces
quality standards — the LLM cannot emit a concept page that lacks its required
sections, and the state reconciler detects stale compiled truths and re-queues them
for refresh on the next dream cycle.

## Timeline

- 2026-04 — Karpathy's LLM Wiki public post validates the compounding pattern.
- 2026-05-31 — Concept seeded from wiki_tools.py and page-types.yaml.
