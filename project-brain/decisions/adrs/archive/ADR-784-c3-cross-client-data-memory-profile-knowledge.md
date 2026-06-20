---
status: Implemented
date: 2026-05-25
deciders:
  - gsannikov
related: [781, 782, 783, 785, 786, 772]
hub: null
tags: [multi-brain, harness, memory, profile, knowledge, cross-client, bidirectional]
superseded_by: null
spec_file: 2026-05-25-harness-layering-family-design.md
plan_file: 2026-05-25-harness-c3-cross-client-data.md
---

# ADR-784: C3 — Cross-Client Data (Memory · Profile · Knowledge)

> Child of the **ADR-781** harness-layering family. Canonical design: [`2026-05-25-harness-layering-family-design.md`](../superpowers/specs/2026-05-25-harness-layering-family-design.md). Implements ADR-781 Amendment A2.

## Decision summary

Make memory and profile **bidirectional cross-client** capabilities and federate knowledge across tiers: INGEST each client's native memory → Augur (review-gated), aggregate across Global+User+Project (read-union ↑ / write-most-specific), and PROJECT the aggregate back to every client — so each client is aware of what the user did in the others, with Augur as the cross-client hub.

## Status notes

Implemented 2026-05-25. The tier-keyed memory/profile/knowledge layer is live:
memory reads union Global+User+Project, writes route to the most-specific
writable tier, profile data overlays by tier, and knowledge search federates
across tiered sources with provenance. Closeout verification reported 40 real
memory records, non-empty rendered projection bytes, Codex and Gemini memory
targets containing the sampled memory record, and no parity drops in the
assembled harness family.

## Context

ADR-781 D4 originally mislabeled memory as "Augur-only / no client slot." Amendment A2 corrected this: **every AI client has native memory**; the user-facing goal is **cross-client awareness**. The ingest/project machinery partly exists (`_feed_memory_review_queue()` ingest, `adapter.sync_memory()` project), and promotion is review-gated per ADR-772. Memory store is currently a vault singleton, not tier-keyed.

## Decision

1. **Tier-keyed memory store** — read = union bottom-up (Global+User+Project, most-specific wins on conflict); write = most-specific writable tier (active Project, else User; Global read-only).
2. **Bidirectional flow** — INGEST client-native memory → review queue (records source client + timestamp) → approved → Augur (no auto-promotion, ADR-772); PROJECT Augur's tier-union back into every client's native memory/context.
3. **Profile overlay merge** — Global defaults ← User identity ← Project role overlay.
4. **Knowledge federation** — search across per-tier indexes; each result tagged with source brain (provenance). (Cross-tier ranking/dedup is a noted follow-up.)

## Completion gate

Round-trip proof on real clients: memory written in client A surfaces (review-gated) in client B; tier precedence honored on reads; **zero data loss** (migration harness, 781 §2b, on any store move); provenance auditable.

## Consequences

**Positive:** true cross-client awareness — the headline user value; Augur becomes the durable cross-client memory hub. **Negative:** memory store refactor (singleton → tier-keyed) is data-sensitive (mitigated: migration harness + review gate + git-backed reversibility). **Neutral:** ingest stays review-gated (no behavior regression vs ADR-772).

## Dependencies

C1 (projection to clients), ADR-781 shared infra, ADR-772 (review-gated promotion). Blocks C5.

## References

- ADR-781 (parent) + Amendment A2 · ADR-772 (review-gated memory promotion) · family spec
- `src/lib/knowledge/memory_store.py`, `src/lib/memory_review.py`, `sync_agents` `_feed_memory_review_queue` / `adapter.sync_memory`
