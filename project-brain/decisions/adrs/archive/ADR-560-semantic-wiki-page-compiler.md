---
status: Superseded
date: '2026-04-20'
deciders:
- Gur Sannikov
related:
- ADR-004
- ADR-404
- ADR-478
- ADR-559
hub: brain
tags:
- wiki
- compiler
- rag
- ask
- semantic-clustering
superseded_by: ADR-561
implemented_date: '2026-04-14'
implementation_commits:
- c7755a2a27
- d44c98cbca
- 29842a6605
- ca0b3c7d79
- a4195b5a4e
- 4c934d922e
- b2f4545246
---



# ADR-560: Semantic Wiki Page Compiler

## Context

The wiki compiler had moved beyond static hub summaries, but early candidate derivation still risked producing weak pages from thin token overlap and literal source slugs. That was not enough for a second-brain wiki. The compiler needed to turn retained `/ask` outcomes and RAG-backed source backlog into durable concept pages with canonical names and richer page types.

The broader LLM wiki architecture design remains the strategic source for compiled wiki behavior. This ADR records the implemented semantic page compiler phase inside that broader direction.

## Decision

Add a semantic page compiler layer that derives reusable concept signals from backlog entries and retained `/ask` outcomes, resolves canonical page identities, and emits richer page kinds.

The compiler now uses:

- `wiki_signal_graph.py` to normalize backlog and `/ask` signal into concept clusters.
- `wiki_page_identity.py` to resolve page slug, title, and page type.
- `wiki_page_candidates.py` to derive, merge, and prioritize semantic page candidates.
- `wiki_compiler.py` and `wiki_page_writer.py` to render topic, entity, comparison, query-output, and source-summary pages.

`/ask` signal is weighted as a first-class page creation and strengthening input. Entity and comparison pages are created only when the signal shape supports them, while generic comparison wording remains a normal topic or query output.

## Consequences

Positive:

- Wiki pages get stable, meaningful identities instead of source-file-shaped slugs.
- Entity and comparison pages become first-class compiled wiki outputs.
- Repeated `/ask` outcomes can promote durable ask-only concepts into topic pages.
- Source-backed topics can merge into canonical entity or comparison pages when the signal supports it.

Negative:

- Semantic candidate derivation is more complex than token overlap.
- Page naming quality now depends on conservative signal heuristics and test coverage.

Neutral:

- The compiler still uses markdown wiki pages with YAML frontmatter.
- The broader wiki architecture spec remains active and is not deleted by this cleanup.

## Implementation Evidence

Key implementation files:

- `skills/ingest/scripts/wiki_signal_graph.py`
- `skills/ingest/scripts/wiki_page_identity.py`
- `skills/ingest/scripts/wiki_page_candidates.py`
- `skills/ingest/scripts/wiki_compiler.py`
- `skills/ingest/scripts/wiki_page_writer.py`
- `skills/ingest/scripts/wiki_article_sections.py`
- `skills/ingest/scripts/wiki_schema.py`
- `skills/ingest/assets/seeds/wiki-schema/page-types.yaml`
- `skills/ingest/assets/seeds/wiki-schema/entity-types.yaml`
- `skills/ingest/assets/seeds/wiki-schema/lint-rules.yaml`

Representative tests:

- `skills/ingest/augur/tests/test_wiki_signal_graph.py`
- `skills/ingest/augur/tests/test_wiki_page_identity.py`
- `skills/ingest/augur/tests/test_wiki_page_candidates.py`
- `skills/ingest/augur/tests/test_wiki_compiler.py`
- `skills/ingest/augur/tests/test_wiki_page_writer.py`
- `skills/ingest/augur/tests/test_wiki_article_sections.py`
- `skills/ingest/augur/tests/test_wiki_schema.py`
- `skills/ingest/augur/tests/test_wiki_quality.py`

## Alternatives Considered

### Keep Thin Token Overlap

Rejected. Token overlap creates pages that mirror filenames and incidental words instead of durable concepts.

### Predefine A Fixed Ontology

Rejected. The wiki should grow from repeated user data and `/ask` signal. Page types are stable, but topics should emerge dynamically.

### Use `/ask` Only As A Source Summary

Rejected. Retained `/ask` outcomes are the strongest second-brain signal and should directly influence page identity, priority, and page strengthening.

## References

Absorbed transient artifact:

- `docs/superpowers/plans/2026-04-14-semantic-wiki-page-compiler.md`

Retained broader design source:

- `docs/superpowers/specs/2026-04-14-llm-wiki-architecture-design.md`

## Impact Manifest

```yaml
paths_renamed: []
apis_changed:
  - skills/ingest/scripts/wiki_page_candidates.py: candidates are derived from signal graph and page identity resolution
  - skills/ingest/scripts/wiki_compiler.py: compiled pages include entity and comparison outputs
patterns_deprecated:
  - wiki page candidates based only on thin token overlap
files_affected:
  - skills/ingest/scripts/wiki_signal_graph.py
  - skills/ingest/scripts/wiki_page_identity.py
  - skills/ingest/scripts/wiki_page_candidates.py
  - skills/ingest/scripts/wiki_compiler.py
  - skills/ingest/scripts/wiki_page_writer.py
  - skills/ingest/scripts/wiki_article_sections.py
  - skills/ingest/scripts/wiki_schema.py
```

## Supersession Note

ADR-561 supersedes this semantic compiler model. The signal graph, page identity, page candidate, deterministic article section, and source-summary compile path should be removed or rewritten as part of the concept-first wiki compiler replacement.
