# ADR-756 Implementation Plan — Loop-Skill Consolidation

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. **Prerequisite: ADR-755 must be Implemented and merged before running this plan** — the routine_orchestrator depends on the trust algorithm being in `routine_orchestrator/trust.py`, and that move is ADR-755's Task 2.

**Goal:** Consolidate 11 `loop-*` skills into 5 `routine-*` skills aligned by concern. Move 85 auto-commands across skills without touching their behavior, name, loop-category mapping, or scan/fix contract. Sync_agents regen after each migration. After this plan: 5 `routine-*` skills replace 11 `loop-*` skills; `ls shared-vault/skills/ | grep loop-` returns nothing.

**Architecture:** Per-auto-command `git mv` of `commands/auto-*.md` + `scripts/*_ops.py` from old skill to new. Update both SKILL.md `x-augur-commands` blocks (remove from source, add to destination). Cross-reference updates handled in a final sweep task. The `loop` field in each auto-command's frontmatter (`testing`, `hardening`, etc.) does NOT change — only the *owning skill* changes. Trust state file is keyed by `loop.category`, not by skill path, so trust trajectories survive the migration intact.

**Tech Stack:** git mv, pytest (regression — existing tests must stay green after each migration), `sync_agents sync agents all` (regen after each migration), no new code.

**Spec:** `docs/superpowers/specs/2026-05-16-loop-skill-consolidation-design.md`. **Depends on:** ADR-755 (Implemented; depends on `routine_orchestrator/trust.py` being the canonical trust home). **Independent of:** ADR-757 (journal retirement) — can land before or after.

---

## File Structure

### Create

| Path | Responsibility |
|------|----------------|
| `shared-vault/skills/routine-codebase/SKILL.md` | Concern: codebase correctness — tests, types, code quality, API/MCP/page wiring |
| `shared-vault/skills/routine-codebase/scripts/__init__.py` | Marker |
| `shared-vault/skills/routine-platform/SKILL.md` | Concern: platform health — git, page health, metrics, plugin lint, observability |
| `shared-vault/skills/routine-platform/scripts/__init__.py` | Marker |
| `shared-vault/skills/routine-vault/SKILL.md` | Concern: vault & knowledge hygiene — memory curation, vault repair, doc freshness |
| `shared-vault/skills/routine-vault/scripts/__init__.py` | Marker |
| `shared-vault/skills/routine-coverage/SKILL.md` | Concern: cross-cutting coverage scans — hub coverage + skill usage |
| `shared-vault/skills/routine-coverage/scripts/__init__.py` | Marker |
| `shared-vault/skills/routine-security/SKILL.md` | Concern: security scans |
| `shared-vault/skills/routine-security/scripts/__init__.py` | Marker |
| `docs/migrations/2026-05-16-loop-skill-consolidation-manifest.md` | Per-auto-command audit table produced by Task 0 |

### Move (git mv)

Per the Task 0 audit manifest. Roughly 85 `auto-*.md` files + ~85 `scripts/*_ops.py` files relocate to one of the 5 new skill roots. Exact mapping resolved in Task 0.

### Delete

| Path | Disposition |
|------|------|
| `shared-vault/skills/loop-test/` | Deleted after all its auto-commands move out |
| `shared-vault/skills/loop-quality/` | Same |
| `shared-vault/skills/loop-wiring/` | Same |
| `shared-vault/skills/loop-ops/` | Same |
| `shared-vault/skills/loop-observability/` | Same |
| `shared-vault/skills/loop-repo/` | Same (split across vault + platform) |
| `shared-vault/skills/loop-docs/` | Same (split across vault + coverage) |
| `shared-vault/skills/loop-hub-coverage/` | Same |
| `shared-vault/skills/loop-memory/` | Same |
| `shared-vault/skills/loop-security/` | Same |
| `shared-vault/skills/loop-hygiene/` | Deleted directly (no auto-commands; empty leftover) |

### Modify

| Path | Change |
|------|--------|
| `docs/architecture-daemon.md` | Replace `loop-test` / `loop-quality` / etc. references with `routine-codebase` / `routine-vault` / etc. |
| `docs/architecture-sdlc.md` | Same cross-reference update |
| `config/system/adaptive_loops.yaml` | Any `discover` blocks that hardcode `loop-*` paths get updated (most likely none — discovery walks all `shared-vault/skills/*/SKILL.md` generically; verified during planning) |
| `shared-vault/skills/daemon/scripts/adaptive/discovery.py` | If it hardcodes any `loop-*` prefix filter, update to walk all skills (verified during planning: no such filter; the walker is generic) |

---

## Task 0: Audit and produce the migration manifest

**Files:**
- Create: `docs/migrations/2026-05-16-loop-skill-consolidation-manifest.md`

**Dependencies:** None. This task does no file changes; it produces the manifest the migration tasks consume.

- [ ] **Step 1: Per-auto-command audit**

For each of the 85 auto-commands across all 11 `loop-*` skills:
- Resolve the auto-command name + its owning skill + its `loop` category + its `scripts/*_ops.py` path
- Classify by concern (codebase / platform / vault / coverage / security)
- Record any cross-skill imports the `_ops.py` module makes (grep for `from shared-vault.skills.loop-` patterns; flag any such finding for refactor before move)

Output: a per-auto-command table in the manifest file:

```
| auto-command | source skill | dest skill | loop category | ops module path | cross-skill imports |
|---|---|---|---|---|---|
| auto-test-build | loop-test | routine-codebase | testing | scripts/test_build_ops.py | (none) |
| ... (84 more rows)
```

- [ ] **Step 2: Cross-reference audit**

Grep the repo for every reference to `loop-*` skill paths:
- `grep -rn "loop-test\|loop-quality\|loop-wiring\|loop-ops\|loop-docs\|loop-repo\|loop-hub-coverage\|loop-observability\|loop-memory\|loop-security\|loop-hygiene" --include="*.md" --include="*.py" --include="*.yaml"`
- Tabulate every hit by destination skill.

- [ ] **Step 3: Verify trust state file independence**

Confirm `~/.Library/Application Support/Augur/state/adaptive/trust_state.json` keys by `loop.category` (NOT by skill path). If verified, the migration preserves trust trajectories. If found to key by skill, file a migration-blocking finding and stop the plan.

- [ ] **Step 4: Commit the manifest.**

---

## Task 1–5: Create the 5 new skill scaffolds

**Files (Task 1: routine-codebase):**
- Create: `shared-vault/skills/routine-codebase/SKILL.md` + `scripts/__init__.py`

**Files (Task 2: routine-platform):**
- Create: `shared-vault/skills/routine-platform/SKILL.md` + `scripts/__init__.py`

**Files (Task 3: routine-vault):**
- Create: `shared-vault/skills/routine-vault/SKILL.md` + `scripts/__init__.py`

**Files (Task 4: routine-coverage):**
- Create: `shared-vault/skills/routine-coverage/SKILL.md` + `scripts/__init__.py`

**Files (Task 5: routine-security):**
- Create: `shared-vault/skills/routine-security/SKILL.md` + `scripts/__init__.py`

**Dependencies:** Task 0 (need the manifest to know which auto-commands each new skill will absorb, so SKILL.md frontmatter can list them in `x-augur-commands`).

**Parallelism:** Tasks 1–5 are **parallel-safe** — different files, no overlap. Five teammates.

For each task:

- [ ] **Step 1:** Author SKILL.md with frontmatter (name, hub, type, tags, concern statement, `x-augur-commands` listing the auto-commands the manifest says this skill absorbs — but with `callable:` paths still pointing at the OLD locations; those paths get updated by Tasks 6–10 as the moves happen).
- [ ] **Step 2:** Create empty `scripts/__init__.py`.
- [ ] **Step 3:** Commit.

---

## Task 6–11: Per-source-skill migration (parallel-safe)

Each task migrates all auto-commands out of one source `loop-*` skill into the destination skill(s) per the manifest.

**Files per task: source skill's `commands/` + `scripts/` directories; destination skill(s)' `commands/` + `scripts/` + SKILL.md.**

**Dependencies:** Tasks 1–5 (scaffolds exist).

**Parallelism:** Each task touches files in exactly one source `loop-*` skill (and the destination skill's add). **Parallel-safe with the other Tasks 6–11.** Six teammates can run concurrently.

**Task 6: Migrate `loop-test` (→ routine-codebase, 11 auto-commands).**
**Task 7: Migrate `loop-quality` (→ routine-codebase, 4 auto-commands).**
**Task 8: Migrate `loop-wiring` (→ routine-codebase, 9 auto-commands).**
**Task 9: Migrate `loop-ops` + `loop-observability` (→ routine-platform, 10 auto-commands combined).**
**Task 10: Migrate `loop-repo` (split: git → routine-platform, vault → routine-vault).**
**Task 11: Migrate `loop-docs` + `loop-memory` + `loop-hub-coverage` + `loop-security` (split per manifest).**

For each task:

- [ ] **Step 1:** For each auto-command in the source skill (per manifest):
  - `git mv shared-vault/skills/<source>/commands/<auto-name>.md shared-vault/skills/<dest>/commands/`
  - `git mv shared-vault/skills/<source>/scripts/<ops-module>.py shared-vault/skills/<dest>/scripts/`
  - Remove from source SKILL.md's `x-augur-commands` block
  - Add to destination SKILL.md's `x-augur-commands` block (or verify already present from Task 1–5 scaffold and update `callable:` paths if needed)
  - Fix any imports in the moved Python file per the manifest's cross-skill imports column

- [ ] **Step 2:** Run `/auto-test-pytest` — all existing tests must stay green after the migration.

- [ ] **Step 3:** Run `python3 -m skills.ai.scripts.sync_agents sync agents all` from `shared-vault/` — confirm regen succeeds without errors.

- [ ] **Step 4:** Commit. One commit per source skill.

---

## Task 12: Delete empty `loop-*` directories

**Files:**
- Delete: every `shared-vault/skills/loop-*/` directory that is now empty after Tasks 6–11

**Dependencies:** Tasks 6–11.

- [ ] **Step 1: Verify empty**

For each `loop-*` skill, confirm:
- No `commands/auto-*.md` files remain
- No `scripts/*_ops.py` files remain (just `__init__.py` if any)
- SKILL.md's `x-augur-commands` block is empty

- [ ] **Step 2: Delete**

```bash
git rm -r shared-vault/skills/loop-test/ shared-vault/skills/loop-quality/ shared-vault/skills/loop-wiring/ shared-vault/skills/loop-ops/ shared-vault/skills/loop-observability/ shared-vault/skills/loop-repo/ shared-vault/skills/loop-docs/ shared-vault/skills/loop-hub-coverage/ shared-vault/skills/loop-memory/ shared-vault/skills/loop-security/ shared-vault/skills/loop-hygiene/
```

- [ ] **Step 3:** Run `/auto-test-pytest` + `sync_agents sync agents all`. Confirm green.

- [ ] **Step 4:** Commit.

---

## Task 13: Cross-reference sweep

**Files:** every doc / config / script identified by Task 0 Step 2's cross-reference audit.

**Dependencies:** Task 12.

- [ ] **Step 1: Apply updates per the manifest's cross-reference table**

For each hit:
- Replace `loop-<concern>` skill path with `routine-<new-concern>`
- Replace any documentation references to "loop-test", "loop-quality" etc. with the new names

- [ ] **Step 2: Run `/auto-test-pytest`** and `sync_agents sync agents all` to catch any missed references that break.

- [ ] **Step 3:** Commit.

---

## Task 14: Full registry verification

**Dependencies:** Task 13.

- [ ] **Step 1: Auto-loop registry diff**

```bash
/dev-loops registry > /tmp/registry-after.txt
```

Compare against a snapshot taken at the start of this plan (or against `git show HEAD~N:...` for the pre-migration state). Every auto-command name in the post-migration registry must match the pre-migration registry (same names, same loop-category memberships). If anything is missing or renamed, fix it.

- [ ] **Step 2: Trust state file integrity check**

Read `~/.Library/Application Support/Augur/state/adaptive/trust_state.json`. Confirm every per-category entry has matching `loop.category` keys (same as pre-migration). Trust trajectories must be preserved.

- [ ] **Step 3: One real auto-loop run**

```bash
/dev-loops run hardening
```

Confirm an actual auto-command from a migrated skill runs end-to-end successfully.

- [ ] **Step 4:** Commit any small fixes.

---

## Task 15: ADR-756 status flip

**Dependencies:** Task 14.

- [ ] **Step 1: Flip status** Proposed → Implemented.
- [ ] **Step 2: Run post-write hook**:
  ```bash
  python3 .github/scripts/adr_upsert_live.py
  python3 .github/scripts/generate_adr_index.py
  python3 src/lib/index/unified_indexer.py --category adrs
  python3 -m skills.ai.scripts.sync_agents sync agents all
  ```
- [ ] **Step 3:** Final commit + handoff via `superpowers:finishing-a-development-branch`.

---

## Parallelism Map

- **Task 0** (audit): sequential, must complete first
- **Tasks 1–5** (5 new skill scaffolds): **parallel-safe**, 5 teammates
- **Tasks 6–11** (6 per-source-skill migrations): **parallel-safe** (each touches files in exactly one source skill), 6 teammates
- **Tasks 12, 13, 14, 15**: sequential downstream

Critical path: **Task 0 → {Tasks 1–5 parallel} → {Tasks 6–11 parallel} → Task 12 → Task 13 → Task 14 → Task 15** = 7 sequential steps vs 16 fully-sequential.

---

## Rollback

- Each migration task is one commit. Revert any single commit to back out one source-skill migration.
- The 5 new skill scaffolds are created in their own commits (Tasks 1–5) — revertable independently.
- `git mv` preserves history; reverting a migration commit restores files to their original paths.
- The `loop-*` directory deletions (Task 12) are reversible by `git revert` (files come back with their full history).
- No code changes inside auto-command modules — `scan()` / `fix()` behavior is byte-identical pre/post migration.
- Trust state file is untouched by this plan; trajectories preserved by `loop.category` keying.
