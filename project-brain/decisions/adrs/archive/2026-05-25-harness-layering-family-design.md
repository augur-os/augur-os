# Harness Layering — ADR Family Design Spec

**Status:** Design (brainstormed 2026-05-25) — canonical record is the ADR family under ADR-781.
**Goal:** Land Augur's core multi-brain harness layering — the merge and projection of all agent context (instructions, commands, skills, subagents, MCP, CLI, memory, profile, knowledge) across Global ⊏ User ⊏ Project brains into every AI client — as a carefully-decomposed family of individually-reviewable ADRs, each proving itself on real clients before it's done.

**Non-negotiable safety envelope (user-selected):** **(1) Cross-client correctness** — no client ever receives a broken, empty, or mis-merged harness; precedence is deterministic and effective/shadowed is always inspectable. **(2) Data safety** — zero loss of skills / memory / profile during migrations and cross-client memory ingest; every mutation reversible + auditable. *Backward-compat and gated rollout were explicitly NOT selected → a clean cutover is acceptable (no long-lived compat shims, per rule 14), and correctness is enforced by a parity gate rather than parallel code paths.*

---

## 1. The model (ADR-781 parent, recap)

- **Three tiers** mapped to the AI-client pattern: `Global = Augur core` ⊏ `User = personal brain` ⊏ `Project = project brain`. **Most-specific wins.**
- **Two axes:** Tier × Ownership (`client-native` vs `Augur-managed`); **promotion** = client-native → Augur-managed at the matching tier (personal promotions cap at User; Global is platform-managed/read-only).
- **Cardinality:** 1 Global, 1 User, N Projects per machine (registry-enforced).
- **Active-stack resolution:** Global + User always present; the Project tier is cwd-resolved. `resolve_active_stack()` returns the ordered stack; `resolve_active_context()` is retained as the most-specific accessor.
- **3-into-2 client projection:** Augur pre-merges Global⊕User → client **HOME** (`~/.claude`, `~/.codex`, `~/.gemini`); Project → client **REPO** (`./.claude`, repo `.mcp.json`); the client enforces repo ⊐ home, yielding Project ⊐ User ⊐ Global.
- **Cross-client vision (A2):** memory/profile are **bidirectional** — INGEST client-native memory → Augur (review-gated) and PROJECT Augur's aggregate → all clients, so every client is aware of what the user did in the others. Augur is the cross-client hub.

The parent ADR-781 folds Amendments A1/A2 into this model, retains the shipped foundation (below), and becomes the index pointing at C1–C5.

---

## 2. Safety mechanisms (cross-cutting, parent-owned shared infra)

Two utilities are built once under the parent and reused by every child:

### 2a. `verify-harness` — the cross-client correctness gate
A command/MCP that, for each enabled client (Claude/Codex/Gemini/…), diffs **expected-effective** (from the pure effective/shadowed resolver) against **what the client actually received** (its real projected config). Asserts: non-empty, correctly-merged, precedence honored, and the page/skill/command actually loads (rules 28/34). **No child is "done" until `verify-harness` passes on real clients with real data.**

### 2b. Migration harness — the data-safety gate
A dry-run-first wrapper for every layout/path/config migration: (i) **dry-run** lists exactly what moves where; (ii) apply via reversible ops (`git mv`, review queue); (iii) **count-check** asserts skills/memory/profile count before == after; (iv) **reference scan** (rule 23) proves no consumer points at a moved location. Nothing is deleted until the post-move discovery check confirms zero loss.

### 2c. Parity-gated cutover
The flip from single-brain → layered projection happens only after a **parity check** proves the layered projection yields a **superset-or-equal** harness for the current active brain. The old single-brain path is deleted *after* parity passes — a correctness safeguard, not a compat shim.

### 2d. Effective/shadowed resolver (pure function)
`name → (winning tier, shadowed[])` per capability type, computed once and shared by projection (C1), the manager UI (C4), and `verify-harness`. Single source of truth for "why did this client get X from tier Y."

---

## 3. The ADR family

| ADR | Owns | Maps to | Primary guarantee | Depends on |
|---|---|---|---|---|
| **781 (parent)** | The model + index + shared infra (2a–2d) | model + A1/A2 + shipped foundation | both | — |
| **C1 · Capability Projection & Client Sync** | Consume merge engine → project instructions/commands/skills/subagents/MCP into client config; 3→2 collapse (G⊕U→HOME, P→REPO); effective/shadowed; sync-safety (never clobber non-Augur); gated home-dir writes; parity-gated cutover | rest of 2b (2b-wire) + 2c | Cross-client correctness | 781 infra |
| **C2 · CLI & MCP Tier-Scoping** | Tier-aware `aug` subcommand discovery; tier-scoped `capability_exposure.yaml` + `mcp_servers.yaml` (`scope: global\|user\|project`); project-level `.mcp.json` | Phase 3 | Cross-client correctness | C1 |
| **C3 · Cross-Client Data (Memory · Profile · Knowledge)** | Bidirectional model (A2): INGEST client→Augur (review-gated) + PROJECT Augur→all clients; tier-keyed memory (read-union ↑ / write-most-specific); profile overlay merge; knowledge federation across tiers | Phase 4 + A2 | Data safety | C1 (projection), 781 infra |
| **C4 · Harness Manager Surface** | VS-Code-settings-style manager (tier filter, effective/shadowed view, promote/demote actions); extends `build_discovery_snapshot` for the full stack; rule-32 manager exception | Phase 5 | (visualizes C1–C3) | C1–C3 |
| **C5 · Migration Verification & Closeout** | Whole-family verification: every migration (vault canonicalization, C1–C4 path/config moves, cutover, cross-client memory model) verified correct — no data loss, no orphaned refs, every client/tier correct, parity holds. End-to-end real-data + real-client run. | new (replaces old "Phase 6") | both (final proof) | C1–C4 |

**Build order:** C1 → C2 → C3 → C4 → C5 (dependency-driven; UI after the data it shows; verification last).

---

## 4. Shipped foundation (already under 781, this session)

- `BrainType.GLOBAL` + `read_only` write policy; registry cardinality gate (≤1 personal, ≤1 global).
- `resolve_global_brain` (core brain root + dedupe), `BrainStack`, `resolve_active_stack`.
- Stack-aware context envelope (`render_augur_stack_envelope`, `get_active_brain_stack`); generated CLAUDE.md shows the 3-tier `stack:` block.
- Vault skill canonicalization (`capabilities/skills/` uniform layout; 3 personal skills migrated, history preserved).
- Layered merge engine `resolve_layered_projection` + coincident-root dedupe (real run: global 21 + personal 3 + project 21 → deduped roots).

---

## 5. Per-child contracts (interfaces + completion gates)

Each child is independently reviewable and testable. Each MUST pass `verify-harness` (2a) on real clients and, where it migrates data, the migration harness (2b) before "done."

### C1 · Capability Projection & Client Sync
- **Interface in:** `resolve_layered_projection(stack)` (done) + the effective/shadowed resolver (2d).
- **Interface out:** every adapter projects from the shared merged sources; HOME vs REPO targets per the 3→2 collapse.
- **Key decisions:** refactor `sync_agents/constants.py` module-level single-brain constants → per-call multi-tier resolution; unify the two skill-source resolvers (`resolve_brain_projection_sources` + `get_managed_skill_source_dirs`); home-dir writes are **gated** (explicit opt-in/confirm — outward-facing).
- **Gate:** parity-gated cutover passes; `verify-harness` green on Claude/Codex/Gemini with real data; non-Augur entries untouched.

### C2 · CLI & MCP Tier-Scoping
- **Interface in:** the active stack (tiers).
- **Key decisions:** `discover_subcommands` merges global+user+project (most-specific name wins); `capability_exposure.yaml`/`mcp_servers.yaml` gain a tier `scope`; project `.mcp.json` generated for the project tier.
- **Gate:** `aug` resolves tier-correct subcommands; `verify-harness` covers MCP/exposure.

### C3 · Cross-Client Data (Memory · Profile · Knowledge)
- **Interface in:** existing `_feed_memory_review_queue()` (ingest) + `adapter.sync_memory()` (project); the tier model.
- **Key decisions:** tier-keyed memory store (read-union ↑ / write-most-specific); profile overlay (Global defaults ← User identity ← Project role); knowledge federation with per-result provenance; INGEST stays review-gated (ADR-772), auditable provenance (source client + timestamp).
- **Gate:** round-trip proof — memory written in client A surfaces (review-gated) in client B; zero loss; migration harness on any store move.

### C4 · Harness Manager Surface
- **Interface in:** `build_discovery_snapshot` (extended) + the effective/shadowed resolver (2d).
- **Key decisions:** tier filter + Effective view; promote/demote actions; rule-32 manager-surface exception (not a Browse card tab).
- **Gate:** real-browser client-load verification (rule 28); shows correct effective/shadowed for the real stack.

### C5 · Migration Verification & Closeout
- **Interface in:** all of C1–C4 + the migration harness (2b) + `verify-harness` (2a).
- **Key decisions:** an end-to-end verification run across all tiers + all real clients + all migrated data; asserts no orphaned references (rule 23 family-wide), count integrity, parity, cross-client memory awareness round-trip. Produces a closeout report.
- **Gate:** the family is "landed" only when C5's whole-system run is green on real data + real clients.

---

## 6. Risks / open items
- **Home-dir writes (C1) are outward-facing** — modify the user's global client config across all repos. Ship behind explicit opt-in/confirm; never silent default. (Tracked as a C1 gate, not deferred.)
- **Two-resolver unification (C1)** is the largest single refactor; the migration harness + parity gate de-risk it.
- **Knowledge federation (C3)** scope: start with federated search + provenance; ranking/dedup across tiers may need a follow-up.
- **Vault repo push** for the already-done skill move is the user's action (private `augur-vault` repo).

---

## 7. Next steps (after spec approval)
1. Create the child ADRs (C1–C5) from this spec and reframe parent ADR-781 as model+index (Augur rule 12 — ADRs are canonical).
2. `writing-plans` for **C1** (the first to build), including the parent-owned shared infra (2a/2b) it depends on.
3. Build C1 → … → C5, each gated by `verify-harness` (+ migration harness where it moves data).
