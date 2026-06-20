# Harness Layering — C3: Cross-Client Data (Memory · Profile · Knowledge) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax. **Prerequisite: C1 (ADR-782) landed** (projection to clients). Implements ADR-784 + ADR-781 Amendment A2. **Data-sensitive: every store move goes through the migration harness (dry-run + count-check); ingest stays review-gated (ADR-772).**

**Goal:** Make memory a **tier-keyed, bidirectional cross-client** capability: read = union across Global+User+Project (most-specific wins), write = most-specific writable tier; INGEST client-native memory → Augur (review-gated) + PROJECT Augur's union → every client — so each client is aware of what the user did in the others. Add a profile overlay (Global ← User ← Project) and federated knowledge search with provenance.

**Architecture:** `brain_write_routing.resolve_write_target()` already gives a per-brain `memory_dir` (project: `knowledge/memory`, personal: `root/memory`). C3 adds `tier_memory_dirs(stack)` (the per-tier memory dirs, general→specific) and `read_memory_union` / `resolve_memory_write_target` on top, replacing the `get_memory_dir()` singleton assumption in `memory_store`. The ingest (`_feed_memory_review_queue`) and project (`adapter.sync_memory`) machinery already exists and is review-gated (ADR-772, queue at `<runtime>/memory_review/<brain_id>/`); C3 makes both tier-aware. Profile uses a 3-layer overlay; knowledge federates per-tier indexes with a `source_brain` tag.

**Tech Stack:** Python 3.11+, `src/lib/brain_write_routing.py`, `src/lib/knowledge/memory_store.py`, `src/lib/memory_review.py`, `sync_agents` memory ops, `src/lib/brain_stack.py`. Implements ADR-784. TDD inner loop `uv run pytest <nodeid>`.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `src/lib/brain_memory_tiers.py` | **NEW** — `tier_memory_dirs`, `read_memory_union`, `resolve_memory_write_target` | Create |
| `tests/unit/test_brain_memory_tiers.py` | **NEW** | Create |
| `src/lib/knowledge/memory_store.py` | memory read/write | Route reads through `read_memory_union`, writes through `resolve_memory_write_target` |
| `src/lib/brain_profile_overlay.py` | **NEW** — `resolve_profile_overlay(stack)` | Create |
| `tests/unit/test_brain_profile_overlay.py` | **NEW** | Create |

> Knowledge federation (federated search + `source_brain` provenance) landed in the ADR-784 gap closeout after memory + profile, using the same tier-resolution model as `tier_memory_dirs`.

---

## Task 1: `tier_memory_dirs(stack)` + read-union / write-target

**Files:** Create `src/lib/brain_memory_tiers.py`. Test: `tests/unit/test_brain_memory_tiers.py`.

- [ ] **Step 1: failing test** — create `tests/unit/test_brain_memory_tiers.py`: build a stack with per-tier memory dirs each holding a `MEMORY.md`-style entry file; assert `tier_memory_dirs(stack)` returns dirs general→specific; `read_memory_union(stack)` returns entries from all tiers with the most-specific winning a duplicate key; `resolve_memory_write_target(stack)` returns the project (most-specific writable) dir, or the user dir when no project, and never the global (read-only) dir.

```python
def test_read_memory_union_and_write_target(tmp_path):
    from src.lib.brain_memory_tiers import read_memory_union, resolve_memory_write_target, tier_memory_dirs
    # ... build stack with global/user/project memory dirs holding keyed entries ...
    dirs = tier_memory_dirs(stack)
    assert [d.name for d in dirs]  # general -> specific
    union = read_memory_union(stack)
    assert union["shared-key"].tier.value == "project"   # most-specific wins
    assert resolve_memory_write_target(stack) == project_memory_dir
    # no-project stack -> writes to user, never global
```

- [ ] **Step 2: Run → FAIL**.
- [ ] **Step 3: Implement** — `tier_memory_dirs(stack)`: for each `brain` in `stack.ordered()`, resolve its memory dir via `brain_write_routing` (reuse `resolve_write_target`'s memory-dir logic per brain). `read_memory_union(stack)`: parse each tier's memory entries, accumulate name→entry with most-specific winning + `tier` recorded. `resolve_memory_write_target(stack)`: `stack.most_specific()` unless it's read-only (Global) → fall back to User; raise/return None if no writable tier.
- [ ] **Step 4: Run → PASS**. **Step 5: Commit** `feat(brain): tier-keyed memory dirs + read-union/write-target (ADR-784 C3)`

---

## Task 2: Route `memory_store` through the tier model

**Files:** Modify `src/lib/knowledge/memory_store.py`. Test: existing `tests/unit/test_*memory*` + a new tier test.

- [ ] **Step 1: failing test** — assert `memory_store.read_memory()` (or its public read) returns the union across tiers for an active stack, and `memory_store.write_memory(entry)` lands in the most-specific writable tier dir (not the global singleton). Use a tmp stack + monkeypatched registry/state dir.
- [ ] **Step 2: Run → FAIL** (today it reads/writes the single `get_memory_dir()/MEMORY.md`).
- [ ] **Step 3: Implement** — replace the `get_memory_dir()` singleton calls in `memory_store`'s read path with `read_memory_union(stack)` and the write path with `resolve_memory_write_target(stack)`. Keep the file format (MEMORY.md) unchanged. Any store relocation runs through the **migration harness** (dry-run + count-check) — assert before==after entry counts.
- [ ] **Step 4: Run → PASS** + `uv run pytest tests/unit -q`.
- [ ] **Step 5: Commit** `feat(memory): tier-keyed read-union / write-most-specific (ADR-784 A2 / C3)`

---

## Task 3: Bidirectional cross-client wiring (ingest review-gated ↑ / project union ↓)

**Files:** Modify `sync_agents` memory ops (`vault.py` `_feed_memory_review_queue`, adapters' `sync_memory`). Test: `sync_agents/tests/test_memory_sync_ops.py` (extend).

- [ ] **Step 1: failing test** — assert (a) `_feed_memory_review_queue` records the **source client** + timestamp as provenance for each ingested entry and routes promotion to the most-specific writable tier (not a global singleton); (b) `adapter.sync_memory` projects the **union** (`read_memory_union`) to each client, so a memory written in client A's review-approved store appears in client B's projected memory. (Round-trip via fixtures.)
- [ ] **Step 2: Run → FAIL**.
- [ ] **Step 3: Implement** — make `_feed_memory_review_queue` tier-aware (promotion target = `resolve_memory_write_target`; provenance = source client id + ts; stays review-gated, no auto-promote per ADR-772). Make `adapter.sync_memory` project `read_memory_union(stack)` instead of the singleton. No auto-promotion; the review queue remains the gate.
- [ ] **Step 4: Run → PASS**. **Step 5: Commit** `feat(memory): bidirectional cross-client ingest/project, tier-aware (ADR-784 A2 / C3)`

---

## Task 4: Profile overlay (Global ← User ← Project)

**Files:** Create `src/lib/brain_profile_overlay.py`. Test: `tests/unit/test_brain_profile_overlay.py`.

- [ ] **Step 1: failing test** — `resolve_profile_overlay(stack)` merges per-tier profile dicts: Global defaults overlaid by User identity overlaid by Project role; a key set at Project wins; keys only at Global persist. Assert the merged dict.
- [ ] **Step 2: Run → FAIL**. **Step 3: Implement** — read each tier's profile (from its brain root `profile/`), deep-merge general→specific (most-specific wins per key). **Step 4: PASS**. **Step 5: Commit** `feat(brain): profile overlay merge across tiers (ADR-784 C3)`

---

## Completion Gate (C3)
- [ ] `uv run pytest tests/unit "project-brain/capabilities/skills/ai/scripts/sync_agents/tests/" -q` green.
- [ ] **Real-data round-trip (rule 34):** write a memory entry to the user tier, run the project step, and show it surfaces in a second client's projected memory; confirm tier precedence on read (a project-tier entry overrides a same-key user entry); confirm **zero entry loss** (migration harness count before==after) and provenance recorded. Report the real entry, the tiers, and both clients.

## Self-Review
**Spec coverage (ADR-784 / A2):** tier-keyed memory (T1–T2), bidirectional review-gated ingest + union project (T3), profile overlay (T4), and tier-federated knowledge search with `source_brain` provenance. **Placeholder scan:** none (T2/T3 reference real existing call sites: `memory_store` read/write, `_feed_memory_review_queue`, `adapter.sync_memory`; knowledge federation wires the existing `UnifiedSearcher`). **Type consistency:** `tier_memory_dirs(stack)->tuple[Path,...]`; `read_memory_union(stack)->dict[str,Entry]` (Entry has `.tier`); `resolve_memory_write_target(stack)->Path|None`; `resolve_profile_overlay(stack)->dict`.

## Follow-on
- Cross-tier ranking/dedup can be refined after real usage; ADR-784 now tags tier search results with `source_brain` and dedupes coincident roots to the most-specific brain.
- C4 surfaces memory/profile/knowledge tiers in the manager; C5 verifies the round-trip cross-client.
