---
status: Implemented
date: 2026-04-27
deciders:
  - Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
---

# ADR-593: Augur OS Architecture Deep Dives

## Context

The public `augur-os` repo has an `architecture-overview.md` that names the major subsystems but does not explain in depth the two strongest claims in the investor pitch: **autoloops** as the continuous-improvement-and-trust moat, and the **LLM Wiki** as the concept-compounding-and-portability moat.

Investors and developers reaching the overview need a one-click path into a deeper explanation that visibly answers *what is it*, *how does it work*, and *why is it defensible* without rewriting the overview itself. ROADMAP, the gateway-internal doc, and the README must remain coherent and not over-claim.

The `Augur` main repo is untouched by this work — only the public `augur-os` repo and (one-off) the spec land here.

## Decision

Add two architecture deep-dive documents to `~/Projects/augur-os/docs/`, each ~800–1200 words with diagrams, plus minimal cross-link edits:

1. `architecture-autoloops.md` — covers scan-fix protocol, loop anatomy (Mermaid flowchart), current catalog (T0/T1/T2/T4 cadences), security autoloop as worked example (S1–S5 + Tank CLI), and the two-claim hook (continuous improvement + trust-through-automation as moat).
2. `architecture-llm-wiki.md` — covers the concept-first compiler pipeline (Mermaid flowchart), concept page lifecycle (`pending → thin → durable → merged` Mermaid stateDiagram-v2), worked compounding example, and the two-claim hook (concept-compounding + local-first MCP-exposed as moat).
3. Three small edits to `architecture-overview.md` (`→ See` arrows at end of Subsystems §2 and §5; expanded "Where to go next" list).
4. Single-sentence addition to `README.md` after the existing "deeper dive" line.

Catalog and pipeline-phase claims are reconciled before commit against `ls skills/loop-*`, `tier:`/`trigger:` fields in SKILL.md, and existing `skills/ingest/scripts/wiki_*.py` scripts. ADR-560 phrased as "superseded" rather than "retired" for public-repo tone.

## Consequences

### Positive
- Investor read-path has a credible technical deep-dive on the two strongest claims.
- Subsystem diagrams render natively on github.com (Mermaid).
- Overview stays concise; depth lives one click below.
- Cross-links discoverable from README without a new section header.

### Negative
- `stateDiagram-v2` rendering on github.com is the riskiest syntax; if it fails, the lifecycle diagram needs a fallback to `flowchart LR`.
- Catalog table is a snapshot in time and will drift if loops are added/removed without updating the table.

### Neutral
- ROADMAP, gateway doc, and main repo are untouched.

## Alternatives Considered

### Alternative 1: Per-loop / per-script reference docs
Rejected: spec-grade depth was explicitly out of scope; overview-plus-two-deep-dives covers the investor read-path without committing to maintaining reference docs.

### Alternative 2: New "Architecture deep-dives" section in README
Rejected: parallel sentence under existing "deeper dive" line keeps README flow intact; new section header would over-emphasize.

## References
- Plan: docs/superpowers/plans/2026-04-27-augur-os-architecture-deep-dives.md
- Spec: docs/superpowers/specs/2026-04-27-augur-os-architecture-deep-dives-design.md
