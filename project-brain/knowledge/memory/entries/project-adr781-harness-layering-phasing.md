---
title: project-adr781-harness-layering-phasing
name: project-adr781-harness-layering-phasing
description: ADR-781 multi-brain harness layering — phasing status and the plan-per-phase
  convention
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_adr781_harness_layering_phasing.md
source_hash: fd8d5b133bc73123
---


ADR-781 (Accepted, 2026-05-25) defines multi-brain **harness layering**: 3 tiers `Global=Augur core ⊏ User=personal ⊏ Project` (most-specific wins), a 2-axis model (Tier × Ownership: client-native vs Augur-managed) with a promotion ladder, Global is platform-managed/read-only, cardinality 1 global / 1 user / N projects, 3-into-2 client projection (G⊕U→client home, P→client repo), and data caps (memory/profile/knowledge) merged at the Augur-MCP runtime.

**Convention chosen:** each of the 6 phases gets its OWN placeholder-free plan under `docs/superpowers/plans/`, written only after exploring that phase's code surface — do NOT write one giant mega-plan, do NOT skip surface exploration.

**ADR FAMILY (decided via brainstorming 2026-05-25, user-approved):** ADR-781 is the PARENT/index (model + shared safety infra) with child ADRs. Canonical family spec: `docs/superpowers/specs/2026-05-25-harness-layering-family-design.md`. Safety envelope user-selected = **cross-client correctness + data safety** (NOT backward-compat, NOT gated-rollout → clean **parity-gated cutover** OK, no compat shims). Shared parent-owned infra: `verify-harness` (cross-client correctness gate), dry-run/count-check **migration harness** (data-safety gate), parity-gated cutover, pure effective/shadowed resolver. Children + build order:
- **C1 = ADR-782** Capability Projection & Client Sync (3→2 collapse G⊕U→HOME/P→REPO, two-resolver unification, effective/shadowed, sync-safety, GATED home-dir writes, parity cutover) — biggest refactor, build FIRST.
- **C2 = ADR-783** CLI & MCP Tier-Scoping.
- **C3 = ADR-784** Cross-Client Data (memory/profile/knowledge, implements A2 bidirectional).
- **C4 = ADR-785** Harness Manager UI.
- **C5 = ADR-786** Migration Verification & Closeout (whole-family proof; user explicitly requested this final verification ADR).
Each child gated by `verify-harness` (+ migration harness where it moves data). Build order C1→C2→C3→C4→C5.

**ALL PLANS WRITTEN (2026-05-25) — every child ADR is now `/adr implement`-able** (plan_file populated). Plans under `docs/superpowers/plans/`:
- **C1 (ADR-782)**: C1a DONE (`brain_effective.py`); run order C1b→C1c→C1d in one session — `harness-c1b-verify-harness.md` (plan_file/next), `harness-c1c-source-unification-parity.md`, `harness-c1d-collapse-gated-home-writes.md` (OUTWARD-FACING, home writes gated OFF by default via AUGUR_HOME_SYNC).
- **C2 (ADR-783)**: `harness-c2-cli-mcp-tier-scoping.md`.
- **C3 (ADR-784)**: `harness-c3-cross-client-data.md` (memory tier-keying + bidirectional A2 + profile overlay; knowledge federation = follow-on).
- **C4 (ADR-785)**: `harness-c4-manager-surface.md` (data layer groundable; UI needs real-browser verify).
- **C5 (ADR-786)**: `harness-c5-migration-verification-closeout.md` (whole-family closeout).
Each plan is TDD + grounded in current code + real-data completion gate. Dependency order C1→{C2,C3}→C4→C5; only C2‖C3 are mutually parallel (after C1), and only in separate git worktrees (rule 33). Downstream plans (esp. C4) may need a light refresh once their predecessor lands (they hook APIs the predecessor creates). Also: ADR-787 = "Dual Compilation" (other laptop, renumbered from colliding 781); other laptop must `git pull` for index resync (commit 4b75c8d0a). **C1a DONE** (pushed): `src/lib/brain_effective.py` — pure `compute_effective_skills`/`effective_summary` over `LayeredProjection`, most-specific-wins + D10 coincident-root dedupe. Real-data run: 23 effective skills (20 global core deduped + 3 personal: books/file-manager/vault), 0 shadowed. Plan: `docs/superpowers/plans/2026-05-25-harness-c1a-effective-shadowed-resolver.md`. NEXT: C1b verify-harness (diff expected-effective vs what each real client received).

**Status:**
- **Phase 1 DONE** (committed to main, pushed): added `BrainType.GLOBAL` + `read_only` write policy, `src/lib/brain_stack.py` (`resolve_global_brain`, `BrainStack`, `resolve_active_stack`), and registry cardinality enforcement in `BrainRegistry.__post_init__`. `resolve_active_context()` is RETAINED and delegated to — nothing was removed. Plan: `docs/superpowers/plans/2026-05-25-harness-layering-phase1-stack-resolution.md`.
- **Phase 2a DONE** (committed, pushed): stack-aware context envelope. Added `get_active_brain_stack()` (paths.py) + `render_augur_stack_envelope()` (brain_projection.py, a SUPERSET — keeps `active_brain`=most-specific for back-compat, adds `stack:` block). Switched the one call site `render_rules_projection` (sync_agents/templates.py). Old `render_augur_context_envelope` + its exact-payload test left intact. Generated CLAUDE.md now shows the 3-tier `stack:` block. Plan: `docs/superpowers/plans/2026-05-25-harness-layering-phase2a-stack-envelope.md`.
- **Phase 2 is decomposed:** 2a (envelope, DONE), **2b** (multi-tier projection sources + 3→2 collapse — IN PROGRESS), **2c** (effective/shadowed computation + reporting — PENDING).

**Phase 2b exploration findings (IMPORTANT — 2b is bigger than the ADR sketch):**
- There are TWO skill-source resolvers: (1) `resolve_brain_projection_sources(brain)` is tier-aware but reads only `<data_root>/capabilities/skills`; (2) `get_managed_skill_source_dirs()` (src/config/paths.py:664) is what the skill-stub sync ACTUALLY uses and already unions project-brain skills + `get_vault_skills_dir()` (=`Au-vault/skills/`) + configured vault skills. 2b's real work is UNIFYING these into one tier-aware model — not a one-line tweak.
- The generation pipeline writes skills/commands/agents to REPO only today (only rules+MCP go HOME for codex/antigravity). 2b's 3→2 collapse (User→client HOME like `~/.claude`) is a NEW outward-facing behavior that writes the user's real home client config — gate it.
- Source discovery is MODULE-LEVEL constants in `constants.py` (`SOURCE_RULES/SKILLS/WORKFLOWS/TOPICS`) computed once from ONE active brain — needs refactor to per-call multi-tier resolution.
- Sync-safety today = AUTO-GENERATED header marker + per-adapter `get_managed_files()`; cleanup only deletes managed files. Non-Augur entries untouched.

**Phase 2b design decisions (user-confirmed 2026-05-25):**
- **Personal skill layout → MIGRATE to `capabilities/skills/`** (uniform across all tiers). Move the 3 real vault skills (`books`, `file-manager`, `vault`) from `Au-vault/skills/` → `Au-vault/capabilities/skills/` and update path helpers (`get_vault_skills_dir`, `get_configured_vault_skills_dir`, `get_managed_skill_source_dirs`) + docs (CLAUDE.md "private-vault skills/{skill}") — exhaustive (rule 23). Touches REAL vault data (vault is a git repo, commit there).
- **Global root → core brain root + dedupe** (DONE in commit c88c5d526): `resolve_global_brain` default data_root = `<repo>/project-brain`. In the Augur repo this == project-augur (D10 coincidence) → the layered merge must DEDUPE coincident roots. NOTE: this REVERSES the earlier "distinct tiers" framing.

**Remaining 2b sub-steps:** 2b-vaultmig (canonicalize personal skills — DONE), 2b-merge (layered merge engine `resolve_layered_projection` with dedupe — DONE), 2b-wire (pipeline consumes merge + home/repo split — OUTWARD-FACING home-dir writes, gate before running — PENDING).

**ADR-781 Amendment A2 (user correction, 2026-05-25): MEMORY is bidirectional cross-client, NOT "Augur-only/no client slot" (D4 was wrong).** Every AI client HAS native memory (Claude/ChatGPT/Cursor/Gemini/Copilot). Memory is dual-ownership + bidirectional: INGEST (client→Augur, review-gated per ADR-772; promote to most-specific writable tier) via existing `sync_agents` `_feed_memory_review_queue()`, + PROJECT (Augur→all clients, read-union of tiers) via existing `adapter.sync_memory()`. Goal = cross-client AWARENESS: what the user does in one client becomes visible to all, with Augur as the cross-client memory hub. Profile follows the same pattern; knowledge stays Augur-native. **Phase 4 (data-cap runtime merges) implements this bidirectional model on top of the existing ingest/project machinery.**

**2b-vaultmig DONE:** vault repo (`Au-vault`) commit `dfba56f` moved books/file-manager/vault to capabilities/skills (NOT pushed — user to push vault repo). Path helpers `get_vault_skills_dir`/`get_configured_vault_skills_dir` repointed to capabilities/skills. Real merge now yields global(21)+personal(3)+project(21)→deduped to 2 roots.
- **Phases 3–6 PENDING** (no plans yet): P3 tier-aware `aug` subcommand discovery + tier-scoped `capability_exposure.yaml`/`mcp_servers.yaml` + `aug brain init` friendly cardinality error; P4 data-cap runtime merges (memory read-union/write-most-specific, profile overlay, federated knowledge); P5 harness manager dashboard surface (VS-Code-settings-style, rule-32 manager exception); P6 real-data validation across global+personal+≥2 projects.

Key gotcha confirmed on the real machine: the synthesized Global brain's `data_root` = repo install root (`~/Projects/Augur`) while `project-augur`'s = `…/project-brain` — distinct tiers (the D10 self-hosting duality). See [[project-venture-content-layout]] for the broader brain/store split.
