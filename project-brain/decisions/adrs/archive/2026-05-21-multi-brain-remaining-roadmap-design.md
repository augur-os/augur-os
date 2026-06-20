# Multi-Brain Remaining Roadmap Design

Date: 2026-05-21

## Context

ADR-754 implemented the first registry foundation for multiple brains. The
later project-brain migration work moved the product model away from the old
"shared vault as team brain" framing and toward three brain types:
personal, team, and project.

The remaining work needs to be formalized as independent implementation ADRs.
The goal is to let future sessions execute one phase at a time with a concrete
command such as `/adr implement ADR-770`, while preserving one roadmap that
keeps vocabulary, ordering, and migration boundaries stable.

## Decision

Use a split ADR model:

1. Roadmap ADR: owns phase ordering and canonical vocabulary.
2. One implementation ADR per remaining phase: each phase has its own spec,
   plan, verification gates, and archive lifecycle.

Phase 2 is already implemented in code and should be recorded as an
implemented post-facto ADR. Phases 3 through 5 remain future implementation
work.

## Canonical Phase Map

| Phase | ADR | Status | Purpose |
| --- | --- | --- | --- |
| 1 | ADR-754 | Implemented | Registry foundation and minimal brain identity. |
| 2 | ADR-769 | Implemented | Project-brain foundation, root `BRAIN.yaml`, cwd discovery, and `aug init`. |
| 3 | ADR-770 | Accepted | Physical migration from `shared-vault/` into `project-brain/`. |
| 4 | ADR-771 | Accepted | Brain-owned AI-client projections, canonical instructions/capabilities, and write routing. |
| 5 | ADR-772 | Accepted | Brain discovery/federation UI and memory review product. |

## Canonical Vocabulary

- **Brain:** durable, git-trackable knowledge/capability root with
  `BRAIN.yaml`.
- **Personal brain:** attached to the person.
- **Team brain:** attached to a cross-project shared operating context.
- **Project brain:** attached to one repo/project.
- **Attached project:** code/project root associated with a project brain.
- **Mapped source:** git-tracked project material that belongs to a brain but
  remains in an established repo path such as `docs/adrs/` while the brain
  stores an explicit pointer or manifest entry.
- **Generated projection:** ignored client-native files generated from brain
  canonical sources.
- **Runtime/cache/logs:** OS-managed state outside brain roots.

`shared-vault/` is a legacy physical name. It is not the canonical future name
for Augur project knowledge.

## Phase Boundaries

### Phase 2: Project-Brain Foundation

Phase 2 gives Augur the primitives needed before moving content:

- three brain types only: personal, team, project
- root `BRAIN.yaml`
- `project-brain/` skeleton and discovery
- active context with `active_brain` and `attached_project`
- idempotent `aug init`
- existing client projection sync triggered after init

Phase 2 does not move `shared-vault/` content.

### Phase 3: Physical Migration

Phase 3 moves durable Augur project-brain content from `shared-vault/` to
`project-brain/` and updates path helpers/discovery to the new physical roots.
It must be exhaustive and reference-search driven.

Phase 3 does not change AI-client canonical projection semantics beyond what
is needed to keep existing behavior working.

### Phase 4: AI-Client Projections And Write Routing

Phase 4 makes project-brain instructions and capabilities canonical for
generated AI-client projections. It also wires write operations through
explicit destination and active-context rules.

Phase 4 does not build the full dashboard federation UI.

### Phase 5: UI Federation And Memory Review

Phase 5 gives users visible control: known/discovered brains, projection
status, brain badges, filters, and a memory review surface. It also formalizes
client-native memory as an input/review source rather than a canonical store.

## Non-Goals

- Do not combine all phases into one implementation ADR.
- Do not keep `shared-vault/` as a long-term compatibility layer.
- Do not move runtime state, cache, logs, search indexes, or generated client
  caches into a brain folder.
- Do not make `AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `GEMINI.md`, or native
  client memory files canonical.
- Do not make team brain central to v1 onboarding.
- Do not implement multi-repo project brains in this roadmap.

## Completion Criteria

The roadmap is complete when:

- ADR-769 records the already-implemented project-brain foundation.
- ADR-770, ADR-771, and ADR-772 exist as implementation-ready ADRs.
- Every future ADR names its verification gates and real-data proof.
- `docs/adrs/adrs-index.json`, `docs/generated/adr-index.md`, ADR RAG index,
  and generated agent instructions are regenerated.
