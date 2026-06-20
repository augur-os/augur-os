---
status: Accepted
date: 2026-06-11
hub: workspace
tags:
  - project-brain
  - adr-architecture
  - memory
  - visibility
related:
  - ADR-608
  - ADR-642
  - ADR-794
supersedes:
  - ADR-608 (ADR location clause)
  - ADR-642 (zip archive + JSON-only-bodies model)
---

# ADR-811: Decisions Move into the Brain; Brain Visibility Model; Client-Memory Sweep; Fed-Folder Rule

## Context

The project brain looked "almost empty" despite daily work. Root causes:
(1) no visibility boundary inside `project-brain/` — venture/pitch content
landed beside product knowledge; (2) the decisions layer was a README pointer
while ADR bodies lived in archive zips and `adrs-index.json` (ADR-642), so no
RAG/Browse/wiki/agent surface could read them; (3) no inbound path moved
client-native memories (40+ entries in Claude's per-project memory dir) into
the brain, breaking cross-client memory (rule 38); (4) ~10 brain folders were
README-only stubs with no write path.

The public docs-only release tree already forbids `project-brain/**` and
`docs/adrs/**` (`scripts/guard_public_release_tree.py`), so this decision does
not change public release exposure of ADRs.

## Decision

1. **Visibility model.** Everything under `project-brain/` is treated as
   public-when-released. Placement test: "would you publish this on the public
   docs site?" If no → Au-vault (personal brain) or Au-docs (collateral). No
   visibility flags, no private subtrees.
2. **Decisions move into the brain.** Canonical ADR home is
   `project-brain/decisions/adrs/`. `get_adr_dir()` points there. Live ADRs
   are plain `ADR-*.md` files; archived ADRs are plain `ADR-*.md` files under
   `decisions/adrs/archive/`. The zip archive model and the "live bodies only
   in JSON" clause of ADR-642 are retired; `adrs-index.json` remains the
   generated metadata index (kept in sync by the existing tooling), no longer
   the only home of any body.
3. **Memory: system of record + sweep.** Augur does not build a memory engine
   (no embeddings/salience/retrieval — clients own that). A deterministic
   daily sweep mirrors client-native memory entries into the brain stores
   routed by tier (`type: project` → project brain `knowledge/memory/entries/`,
   other types → personal brain), with provenance and content-hash dedupe.
   Brain `MEMORY.md` files are generated indexes of `entries/`. The existing
   outbound handoff projection is unchanged.
4. **Fed-folder rule.** A project-brain folder exists only when a named
   workflow writes to it. Stub folders (`activity/`, `inbox/`, `plans/`,
   `policies/`, `specs/`, `workflows/`, `drafts/`, `archive/`, `profile/`,
   `reports/`, `instructions/`) are removed; logical mapped-sources entries
   (specs, plans, instructions/topics, workflows, capabilities/agents) remain
   as mappings. Re-adding a folder requires naming its writer here.

## Consequences

- All ~574 historical decisions become readable by RAG, Browse, wiki, and
  agents as plain markdown.
- Venture/pitch content moves to Au-vault; the project brain passes the
  publish test file-by-file.
- Memory born in any client reaches every other client via brain →
  handoff projection.
- `docs/adrs/` ceases to exist; all references migrate (rule 23).
