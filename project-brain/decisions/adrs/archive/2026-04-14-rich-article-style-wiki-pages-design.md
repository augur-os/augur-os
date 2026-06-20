# Rich Article-Style Wiki Pages Design

**Date:** 2026-04-14  
**Status:** Draft  
**Scope:** Upgrade Augur's wiki compiler from summary-style pages to richer article-style pages that behave like a real LLM-maintained wiki

## Summary

The current wiki is meaningfully better than raw retrieval, but most pages still read like compiled notes or structured indexes rather than real wiki articles. They usually contain one thesis, one or two short supporting sections, and a thin evidence list. That is not enough context density for the wiki to act as the primary knowledge layer.

This design introduces a richer page-composition model. Instead of writing one summary and a few support bullets, the compiler should build article-style pages from multiple claim buckets: stable understanding, recent shifts, tensions, subtopics, entities, and evidence. The goal is not longer pages for their own sake. The goal is pages that can actually answer future questions without rediscovering the source set from scratch.

## Problem

The current compiler has four strengths:

1. it can create and update first-class wiki pages
2. it can prioritize `/ask`-aligned material
3. it can merge some recompiles into existing pages
4. it can write cleaner titles and sections than earlier overview templates

But it still has three major limits:

### 1. Pages are too thesis-thin

Most pages contain:
- one thesis
- one short supporting section
- one evidence section

That produces something closer to a good note than a wiki article.

### 2. Context is not accumulated deeply enough

Pages rarely expose:
- internal sub-concepts
- named tensions
- alternative framings
- related entities
- durable structure inside a domain

This means the wiki still lacks the feeling of a real knowledge base.

### 3. Evidence is present but not editorialized enough

Evidence often appears as:
- raw excerpt bullets
- one-sentence retained asks
- light source lists

The wiki is compiling sources, but not yet turning them into sufficiently rich article structure.

## Design Goal

Make overview and topic pages feel like real wiki articles:

- richer than a note
- more structured than a chat summary
- denser than an index
- still concise enough to maintain automatically

A strong compiled page should be able to stand on its own as an answer source for future `/ask` turns.

## Design Principles

1. **Wiki pages should be articles, not inventories.**  
   The page should teach the reader what is true here now, not just describe the source set.

2. **Sections are the main unit of synthesis.**  
   The compiler should compose a page from several section-level claim buckets, not one global paragraph.

3. **Context density matters more than length.**  
   The goal is not maximal verbosity. The goal is enough structured context that the page becomes re-usable.

4. **Stable claims and recent shifts must be separated.**  
   A page should distinguish durable understanding from what changed recently.

5. **Evidence should support claims, not replace them.**  
   Evidence belongs in the article, but claims should be editorialized first.

6. **Pages should name tensions explicitly.**  
   A real wiki article tracks contradictions, open questions, and competing interpretations.

7. **Related concepts belong inside the page body, not only in `See Also`.**  
   The page should expose its internal map of nearby ideas.

## Target Page Model

The default article-style page model for `overview` and `topic` pages should be:

1. `What This Page Is`
2. `Current Thesis`
3. `What This Page Knows`
4. `Key Dimensions`
5. `Recent Shifts`
6. `Open Tensions`
7. `Related Concepts`
8. `Evidence`
9. `Source Basis`

Not every page must include every section, but article-style pages should rarely have fewer than five meaningful sections.

### Section meanings

#### `What This Page Is`

A short orienting paragraph:
- what this page covers
- why it exists
- what kind of object it is in the wiki

This replaces the current vague overview boilerplate.

#### `Current Thesis`

The strongest current synthesized claim.

This should be:
- short
- editorial
- stable enough to anchor the rest of the page

#### `What This Page Knows`

The durable core understanding in this domain.

This is where the compiler should group the most stable claims across the source set. It should usually be a short paragraph or 2-4 curated bullets, not a raw dump.

#### `Key Dimensions`

This is the biggest missing section today.

It should break the page into internal dimensions such as:
- positioning
- workflow
- implementation
- founder story
- management style
- learning loop
- planning system

The exact dimensions should emerge from the source material. This is how a page starts feeling like an article rather than a summary.

#### `Recent Shifts`

Material that changed recently because of:
- fresh vault/doc sources
- retained `/ask` outcomes
- new workflow signals
- recent shipped work or planning changes

This section should make change visible without rewriting the whole page around the latest turn.

#### `Open Tensions`

Named tensions and contradictions, for example:
- old positioning vs new positioning
- consultancy framing vs product framing
- simplicity vs flexibility
- local-first ownership vs ease-of-use tradeoffs

This section should become first-class, not optional cleanup.

#### `Related Concepts`

This is more than `See Also`.

It should name the nearby ideas that matter inside the article itself, for example:
- how this page connects to another topic
- what entities or comparisons matter here
- what subtopics deserve their own page later

#### `Evidence`

Short, curated support for the page's major claims.

Evidence bullets should be:
- specific
- relevant
- compressed
- grouped when possible

They should not just restate the entire page.

#### `Source Basis`

This remains the provenance section:
- actual source paths
- retained `/ask` outcomes when no source path exists

This stays useful, but it should be the least interesting part of the page.

## Section Composition Model

The compiler should stop building pages from one undifferentiated candidate blob and instead build section inputs from claim buckets.

Recommended buckets:

### 1. Stable claims

Derived from:
- repeated ideas across vault/docs
- durable page-linked sources
- older but still consistent retained `/ask` outcomes

Feeds:
- `Current Thesis`
- `What This Page Knows`

### 2. Dimension claims

Derived from:
- repeated subthemes in source bodies
- strong headings and paragraph clusters
- recurring tags/categories/entities

Feeds:
- `Key Dimensions`

### 3. Change claims

Derived from:
- newly compiled backlog items
- fresh `/ask` outcomes
- recent source modifications
- recent git/project signals where relevant

Feeds:
- `Recent Shifts`

### 4. Tension claims

Derived from:
- contradictory retained asks
- competing phrasing across sources
- old-vs-new framing conflicts
- unresolved tradeoffs

Feeds:
- `Open Tensions`

### 5. Relationship claims

Derived from:
- linked entities
- comparisons
- nearby page clusters
- repeated concept co-occurrence

Feeds:
- `Related Concepts`

### 6. Evidence snippets

Derived from:
- strongest source excerpts
- strongest retained ask summaries
- concise grouped source notes

Feeds:
- `Evidence`

## Richness Rules

To prevent pages from collapsing back into index-like output, article-style pages should follow minimum richness rules.

### Overview/topic page minimums

A page should be considered article-ready only if it has:

- one non-placeholder thesis
- one non-trivial `What This Page Knows` section
- at least one of:
  - `Key Dimensions`
  - `Recent Shifts`
  - `Open Tensions`
- an evidence section with at least 2 meaningful items when source material exists

### Escalation rule

If the compiler cannot produce enough richness, it should not fake article depth with scaffolding. It should instead:

- write the best honest page it can
- mark the page as `needs_richer_article`
- let that become maintenance debt for a later deepening pass

This is better than pretending thin pages are complete.

## Page-Type Rules

Not all page types need the full article schema.

### `topic`

Should use the full article-style model most often.

### `overview`

Should use the full article-style model, but with more synthesis and less evidence density.

### `entity`

Should use a lighter structure:
- `What This Entity Is`
- `Current Role`
- `Key Signals`
- `Open Questions`
- `Related Concepts`
- `Source Basis`

### `comparison`

Should use:
- `Comparison Thesis`
- `Where They Differ`
- `Where They Overlap`
- `Decision Pressure`
- `Evidence`
- `Source Basis`

### `query-output`

Should remain lighter, but still feel like preserved knowledge rather than a chat transcript:
- `Current Thesis`
- `Ask Context`
- `What This Clarified`
- `Related Concepts`
- `Source Basis`

### `source-summary`

Should remain thin by design, but should still inherit cleaned titles and slightly better summarization.

## Content Extraction Rules

The new article model requires deeper extraction than path-label summaries.

The compiler should prioritize:

1. section headings in source files
2. first meaningful paragraphs
3. repeated nouns/phrases across files
4. retained `/ask` summaries
5. page/entity/comparison linkage already present in the wiki

It should de-prioritize:

- path names alone
- folder names alone
- generated README text treated as canonical
- generic list bullets with no semantics

## Relationship To `/ask`

`/ask` remains the strongest signal for what the wiki should become.

In the richer page model, `/ask` should especially influence:
- `Recent Shifts`
- `Open Tensions`
- `Related Concepts`

But `/ask` should not dominate page identity when the page already has a stable canonical title or entity.

That means:
- `/ask` can deepen an article
- `/ask` should not arbitrarily rename a stable page

## Relationship To Current Implementation

This design is the next step after the current phase-four work:

- compile worker
- merge logic
- writer module
- compile status surfaces

The current system can already:
- create better titles
- write better theses
- expose compile state

The next jump is to make the writer article-aware rather than title/body aware only.

## Implementation Direction

This should be implemented as a writer/composer upgrade, not as a whole new wiki subsystem.

Recommended evolution:

1. extend `wiki_page_writer.py` from simple page rendering to section composition
2. add claim-bucket extraction helpers
3. generate richer sections for `topic` and `overview` pages first
4. keep `entity`, `comparison`, and `query-output` lighter but structured
5. add a quality rule for `needs_richer_article`

## Non-Goals

- do not introduce a graph database
- do not require manual taxonomy design first
- do not make every page long by default
- do not turn wiki pages into raw source dumps
- do not let generated scaffolding masquerade as richness

## Success Criteria

This design is successful when:

1. the best wiki pages read like short articles, not summary cards
2. pages expose internal dimensions of a domain, not just one thesis
3. tensions and contradictions are visible inside the page
4. related concepts are described in the body, not only in `See Also`
5. future `/ask` answers can rely on these pages as primary knowledge sources

## Recommendation

The next implementation phase should be:

**rich section composition for topic and overview pages**

That is the shortest path from “better compiled notes” to “real wiki articles.”
