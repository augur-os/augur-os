# ADR-758 Implementation Plan — Routines Unification

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax. TDD per task. Augur skill-test convention: `importlib.util.spec_from_file_location`. **Task 0 is a hard gate — if any of the four prerequisites fails, abort the plan and surface the failing gate to the user.**

**Goal:** Collapse the two parallel surfaces (post-755+756+757 auto-loops + ADR-744 dream) into one Routines mechanism: one slash command, one declarative discovery via `x-augur-routine:` SKILL.md blocks, one Codex projection method, one status surface. Execution models (`tiered`, `inline-session`) stay genuinely different at the runtime layer; only registry / surface / projection / status unify.

**Architecture:** New `routine_orchestrator/registry.py` walks every SKILL.md with an `x-augur-routine:` block and produces a flat routine list. New `/routines` slash command + `aug routine <verb>` CLI dispatch through the registry. New `_sync_routine_automations` collapses the two existing Codex adapter methods. Per-skill `routine-schedule.yaml` files replace the centralized `codex-dev-loop-schedules.yaml` (per Rule #2). `/dev-loops` and `/dream` stay as documented aliases for one release cycle.

**Tech Stack:** Python 3.11 stdlib + PyYAML; pytest with `importlib.util.spec_from_file_location`; ADR-743 ledger as the data source via ADR-757's `ledger_view.py` translator (already shared); no new external dependencies.

**Spec:** `docs/superpowers/specs/2026-05-16-routines-unification-design.md`. **Depends on (all must be Implemented):** ADR-744, ADR-755, ADR-756, ADR-757. **Additional gate:** Dream production evidence (≥10 ledger-visible dream runs over a sustained period).

---

## File Structure

### Create

| Path | Responsibility |
|------|----------------|
| `shared-vault/skills/daemon/scripts/routine_orchestrator/registry.py` | Walks SKILL.md `x-augur-routine` declarations; returns `list[Routine]`. Public API: `list_routines()`, `get_routine(id)`, `dispatch(id, **kwargs)`. |
| `shared-vault/skills/daemon/commands/routines.md` | New `/routines` slash command source — verbs: `list`, `status`, `run`, `report`, `schedule` |
| `shared-vault/skills/daemon/augur/tests/test_routines_registry.py` | Tests: routine discovery, id collision detection, schema validation, missing-field error paths |
| `shared-vault/skills/daemon/augur/tests/test_routines_cli.py` | Tests: `aug routine <verb>` argparse + dispatch |
| `shared-vault/skills/daemon/augur/tests/fixtures/routine-skills/` | Synthetic skills with `x-augur-routine` declarations: one tiered + one inline-session + one with collision (negative test) |
| `docs/migrations/2026-05-16-routines-unification-manifest.md` | Task 1 audit: every routine that will be registered + its declared execution model + its current schedule binding |

### Per-skill: add `x-augur-routine` block + move schedule entries

| Skill | Routine declarations | Schedule migration |
|------|------------------------|--------------------|
| `dream/` | `x-augur-routine: { id: dream, execution: inline-session, policy: oneshot, callable: commands/dream.md }` | rename `assets/seeds/codex-dream-schedules.yaml` → `assets/seeds/routine-schedule.yaml` |
| `routine-codebase/` | `x-augur-routines:` list (testing, code-quality, wiring) | move corresponding entries from centralized yaml → `assets/seeds/routine-schedule.yaml` |
| `routine-platform/` | `x-augur-routines:` list (hardening platform parts, observability) | same |
| `routine-vault/` | `x-augur-routines:` list (knowledge-enrichment, vault-hygiene) | same |
| `routine-coverage/` | `x-augur-routines:` list (hub-coverage, skill-usage) | same |
| `routine-security/` | `x-augur-routines:` (security-scan) | same |

### Modify

| Path | Change |
|------|--------|
| `shared-vault/skills/ai/scripts/sync_agents/adapters/codex.py` | Add `_sync_routine_automations` (walks registry + emits per-routine Codex automations). Keep `_sync_dev_loop_automations` + `_sync_dream_automations` as `@deprecated` thin shims that delegate to the new method for one release cycle, then remove. |
| `shared-vault/skills/daemon/scripts/mcp/__init__.py` | Add `register_subcommands` clause for `aug routine <verb>` (mirror the existing `aug dream` pattern). |
| `shared-vault/skills/dream/commands/dream.md` | Add a deprecation footnote: "Activated as `/routines run dream`. The `/dream` alias retires after release X.Y." |
| `shared-vault/skills/daemon/commands/dev-loops.md` | Same deprecation footnote pattern for `/dev-loops run X` → `/routines run X`. |
| `config/system/capability_exposure.yaml` | Add `command:routines:` entry (per memory `feedback-command-capability-entry`); add `mcp-tool:routines-status` if MCP exposure is wanted; mark `command:dev-loops:` and `command:dream:` as `status: deprecated`. |
| `shared-vault/skills/daemon/SKILL.md` | Document the new `routines` command + the registry; reference ADR-758. |

### Delete (post-release-cycle, NOT in this plan's scope — follow-up cleanup)

- `shared-vault/skills/daemon/assets/seeds/codex-dev-loop-schedules.yaml` (after per-skill migration completes)
- Legacy `_sync_dev_loop_automations` + `_sync_dream_automations` methods (after one release cycle of the unified method being live)
- `/dev-loops` and `/dream` slash command projections (after one release cycle of aliases)

---

## Task 0: Verify the four implementation gates (MANDATORY HARD GATE)

**Files:** None modified. Verification-only task.

**Dependencies:** None.

- [ ] **Gate 1: ADR-755 status**

```bash
python3 -c "import json; data=json.load(open('docs/adrs/adrs-index.json')); a=[e for e in data if e['adr_number']=='ADR-755'][0]; assert a['status']=='Implemented', f'ADR-755 status={a[\"status\"]!r}, expected Implemented'; print('Gate 1 PASS')"
```

If this fails: abort the plan. The runner modernization must be in place before unification can absorb it.

- [ ] **Gate 2: ADR-756 status**

```bash
python3 -c "import json; data=json.load(open('docs/adrs/adrs-index.json')); a=[e for e in data if e['adr_number']=='ADR-756'][0]; assert a['status']=='Implemented', f'ADR-756 status={a[\"status\"]!r}, expected Implemented'; print('Gate 2 PASS')"
```

- [ ] **Gate 3: ADR-757 status**

```bash
python3 -c "import json; data=json.load(open('docs/adrs/adrs-index.json')); a=[e for e in data if e['adr_number']=='ADR-757'][0]; assert a['status']=='Implemented', f'ADR-757 status={a[\"status\"]!r}, expected Implemented'; print('Gate 3 PASS')"
```

- [ ] **Gate 4: Dream production evidence**

```bash
aug dream status --history-limit 20 > /tmp/dream-history.json
python3 -c "import json; d=json.load(open('/tmp/dream-history.json')); n=len(d.get('history',[])); assert n>=10, f'Only {n} dream runs in ledger; need >=10 before unification'; print(f'Gate 4 PASS — {n} historical dream runs')"
```

Also verify dream prompt + tools have stabilized:

```bash
RECENT_CHANGES=$(git log --since='1 month ago' --oneline shared-vault/skills/dream/commands/ shared-vault/skills/dream/scripts/mcp/ | wc -l)
echo "Recent architectural changes to dream prompt/MCP surface: $RECENT_CHANGES"
# Should be 0 or near-0 — if dream is still architecturally churning, unification will absorb the churn
```

If recent changes > 3: pause and ask the user to confirm dream has stabilized before continuing. The unification embeds the current dream surface; if it's still moving, the unification will need rework.

- [ ] **Step 5: Commit the gate verification log** (for audit trail).

If any gate fails → ABORT the plan, report the failing gate, and do NOT proceed to Task 1.

---

## Task 1: Audit routines + produce migration manifest

**Files:** Create `docs/migrations/2026-05-16-routines-unification-manifest.md`.

**Dependencies:** Task 0.

- [ ] **Step 1:** For every routine-providing skill (post-756: dream + 5 routine-*), enumerate:
  - Skill root
  - Routine(s) it owns
  - Execution model (tiered for routine-*; inline-session for dream)
  - Current scheduled bindings (from existing seed yamls)
  - Current `x-augur-commands` declarations (for tiered routines — the per-auto-command list)

Output: a table mapping each routine to its declaration + schedule binding.

- [ ] **Step 2:** Verify routine id flat namespace has no collisions. Each loop category becomes one routine id; dream is `dream`. List all proposed ids; flag any collision.

- [ ] **Step 3:** Commit the manifest.

---

## Task 2: Build the registry + fixtures (sequential)

**Files:**
- Create: `shared-vault/skills/daemon/scripts/routine_orchestrator/registry.py`
- Create: `shared-vault/skills/daemon/augur/tests/test_routines_registry.py`
- Create: `shared-vault/skills/daemon/augur/tests/fixtures/routine-skills/{tiered-skill,inline-skill,colliding-skill}/SKILL.md`

**Dependencies:** Task 1 (manifest).

- [ ] **Step 1: Write failing tests**

`test_routines_registry.py`:
- `test_list_routines_walks_all_skill_md_blocks` — fixture: 2 skills with `x-augur-routine`; registry returns both
- `test_singular_and_plural_schema_both_supported` — `x-augur-routine:` (dict) and `x-augur-routines:` (list of dicts) both parse
- `test_get_routine_by_id_returns_resolved_record` — resolves callable path, execution model, policy
- `test_id_collision_raises_loud` — two skills with same id → `RoutineIdCollision` raised
- `test_missing_required_field_raises_validation_error` — `id`, `execution`, `policy`, `callable` are required
- `test_unknown_execution_model_raises` — only `tiered` and `inline-session` allowed
- `test_unknown_policy_raises` — only `adaptive`, `oneshot`, `observability-only` allowed

- [ ] **Step 2: Implement `registry.py`**

`Routine` dataclass with required + optional fields per spec. `list_routines()` walks `shared-vault/skills/*/SKILL.md`, parses YAML frontmatter, extracts `x-augur-routine` or `x-augur-routines` blocks. `get_routine(id)` does the lookup with `RoutineNotFound`. `dispatch(id, **kwargs)` is a stub for Task 4 (returns `NotImplementedError` for now — orchestrator integration in Task 4).

- [ ] **Step 3:** Run tests green; commit.

---

## Task 3a–3f: Add `x-augur-routine` block to each routine-providing skill (PARALLEL-SAFE)

Six teammates: one per skill (`dream`, `routine-codebase`, `routine-platform`, `routine-vault`, `routine-coverage`, `routine-security`).

**Files per task:**
- Modify: `shared-vault/skills/<skill>/SKILL.md` (add `x-augur-routine` or `x-augur-routines` block per the manifest)
- Move: `shared-vault/skills/<skill>/assets/seeds/codex-*-schedules.yaml` → `shared-vault/skills/<skill>/assets/seeds/routine-schedule.yaml` (when present)

For tiered skills (5 routine-* skills): also move the schedule entries from `shared-vault/skills/daemon/assets/seeds/codex-dev-loop-schedules.yaml` for routines owned by this skill.

**Dependencies:** Tasks 1 + 2. **Parallel-safe** — each touches files in exactly one skill.

For each task (3a, 3b, ..., 3f):

- [ ] **Step 1:** Add the `x-augur-routine` block per the manifest. For multi-routine skills (codebase, platform, vault, coverage), use `x-augur-routines:` list.
- [ ] **Step 2:** Move/rename schedule yamls per the manifest. For dream: `git mv assets/seeds/codex-dream-schedules.yaml assets/seeds/routine-schedule.yaml`. For routine-*: extract relevant entries from the centralized yaml and write to per-skill `assets/seeds/routine-schedule.yaml`.
- [ ] **Step 3:** Run `aug routine list` (after Task 4 adds the CLI) OR a manual test that loads the registry and verifies the new routine shows up correctly.
- [ ] **Step 4:** Commit. One commit per skill.

---

## Task 4: `aug routine` CLI + `/routines` slash command + registry dispatch

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/mcp/__init__.py` (add `register_subcommands` for `routine`)
- Create: `shared-vault/skills/daemon/commands/routines.md` (the slash command source)
- Modify: `shared-vault/skills/daemon/scripts/routine_orchestrator/registry.py` (implement `dispatch()`)
- Create: `shared-vault/skills/daemon/augur/tests/test_routines_cli.py`

**Dependencies:** Tasks 2, 3a–3f.

- [ ] **Step 1: Write failing tests**

`test_routines_cli.py`:
- `test_aug_routine_list_returns_all_registered` — uses fixture registry; lists every routine declared in any skill
- `test_aug_routine_run_tiered_delegates_to_orchestrator` — fixture tiered routine; dispatch calls into `routine_orchestrator.orchestrator.orchestrate_run`
- `test_aug_routine_run_inline_session_renders_prompt` — fixture inline-session routine; dispatch renders the routine's prompt file in the current session context (mocked)
- `test_aug_routine_status_reads_ledger_view` — uses ADR-757's `ledger_view.read_recent_runs`; returns recent runs filtered by routine id

- [ ] **Step 2: Implement `dispatch()` in registry.py**

```python
def dispatch(routine_id, **kwargs):
    routine = get_routine(routine_id)
    if routine.execution == "tiered":
        from .orchestrator import orchestrate_run
        return orchestrate_run(loop_name=routine.loop or routine_id, **kwargs)
    elif routine.execution == "inline-session":
        # The slash command rendering happens at the client surface; this
        # function returns the routine prompt content for the client to render.
        return {"render_prompt": routine.callable_path.read_text()}
```

- [ ] **Step 3: Implement `aug routine <verb>`** in `mcp/__init__.py`. Mirror the existing `aug dream` pattern from ADR-744. Verbs: `list`, `status`, `run`, `report`, `schedule`.

- [ ] **Step 4: Author `routines.md`** slash command doc — declares verbs, examples, and the per-routine list rendered from the registry.

- [ ] **Step 5:** Run tests green via `/auto-test-pytest`.

- [ ] **Step 6: Real-data smoke**

```bash
aug routine list   # must show every routine including dream
aug routine status # must show ledger-derived history
aug routine run testing  # must successfully dispatch into the orchestrator
aug routine run dream    # must dispatch the inline-session path
```

- [ ] **Step 7:** Commit.

---

## Task 5: Codex adapter — `_sync_routine_automations` (unified projection)

**Files:**
- Modify: `shared-vault/skills/ai/scripts/sync_agents/adapters/codex.py`
- Create: `tests/sync_agents/test_codex_routine_automation.py`

**Dependencies:** Task 4.

- [ ] **Step 1: Write failing test**

`test_codex_routine_automation.py`:
- `test_walks_registry_and_emits_per_routine_automation` — fixture: 3 skills with routines + schedule bindings; the unified method emits one Codex automation per binding
- `test_legacy_dev_loop_method_still_works_as_thin_shim` — old `_sync_dev_loop_automations` delegates to the new method
- `test_legacy_dream_method_still_works_as_thin_shim` — same for `_sync_dream_automations`

- [ ] **Step 2: Implement**

Add `_sync_routine_automations` method that walks `registry.list_routines()`, finds each routine's `assets/seeds/routine-schedule.yaml`, and dispatches the existing `_sync_codex_seed` helper per schedule binding.

Mark `_sync_dev_loop_automations` and `_sync_dream_automations` as `@deprecated`; they now delegate to `_sync_routine_automations` filtered by routine id (the legacy callers' contract — but warn on every invocation).

Call `_sync_routine_automations` from `generate_mcp_config()` alongside the existing per-method calls (so all three run during this transition release).

- [ ] **Step 3:** Run tests green.

- [ ] **Step 4: End-to-end sync verification**

```bash
python3 -m skills.ai.scripts.sync_agents sync agents codex
# Confirm each routine's automation lands in ~/.codex/automations/
# Compare against pre-758 sync: must be byte-identical (the materialized
# TOML files don't change — only the code path emitting them does)
```

- [ ] **Step 5:** Commit.

---

## Task 6: Slash command aliases — `/dev-loops` and `/dream`

**Files:**
- Modify: `shared-vault/skills/daemon/commands/dev-loops.md`
- Modify: `shared-vault/skills/dream/commands/dream.md`
- Modify: `shared-vault/skills/daemon/scripts/mcp/_loops.py` (alias dispatch)
- Modify: `shared-vault/skills/dream/scripts/mcp/__init__.py` (alias dispatch)

**Dependencies:** Task 4.

- [ ] **Step 1: Add alias dispatch logic**

`/dev-loops run X` and `/dev-loops status` translate to `/routines run X` and `/routines status` respectively at the CLI dispatcher level. Print a one-line deprecation notice on every alias invocation.

`/dream` translates to `/routines run dream`. Same deprecation notice.

- [ ] **Step 2: Update slash command docs**

Each alias doc gains a header banner: "**DEPRECATED — use `/routines run X` instead. This alias retires after release X.Y.**"

- [ ] **Step 3:** Run tests green; commit.

---

## Task 7: Status surface unification

**Files:**
- Modify: `shared-vault/skills/dream/scripts/mcp/__init__.py` (the `dream-status` MCP tool delegates to the unified surface)
- Modify: `shared-vault/skills/daemon/scripts/adaptive_loop_executor.py` (if its status output uses the journal — should already be on `ledger_view` post-757)

**Dependencies:** Task 4.

- [ ] **Step 1: Verify `ledger_view.read_recent_runs` accepts a `routine_id` filter** (it should, post-757; if not, this is a small extension).

- [ ] **Step 2: `dream-status` MCP tool** now calls `ledger_view.read_recent_runs(routine_id="dream", limit=10)` instead of its own per-job scanner. Output shape is preserved (legacy callers see the same JSON).

- [ ] **Step 3:** Same for the `/dev-loops status` path.

- [ ] **Step 4:** Run tests green; commit.

---

## Task 8: Capability exposure + sync_agents regen

**Files:**
- Modify: `config/system/capability_exposure.yaml`

**Dependencies:** Tasks 4–7.

- [ ] **Step 1: Add `command:routines:` entry** projecting `/routines` to client surfaces.
- [ ] **Step 2: Mark `command:dev-loops:` and `command:dream:` as `status: deprecated`** with a `deprecation_release: ...` annotation.
- [ ] **Step 3:** Run `sync_agents sync agents all` and confirm every client surface receives the new command + the deprecation annotations.
- [ ] **Step 4:** Commit.

---

## Task 9: Full real-data validation (Rule #34)

**Dependencies:** Tasks 4–8.

- [ ] **Step 1:** `/routines list` — quote actual routines registered. Should include dream + every loop category (testing, hardening, code-quality, knowledge-enrichment, ...).
- [ ] **Step 2:** `/routines run testing` — runs an actual auto-loop end-to-end via the unified surface; trust state mutates correctly; ledger captures.
- [ ] **Step 3:** `/routines run dream` — runs the actual dream cycle; produces a report; ledger captures.
- [ ] **Step 4:** `/routines status` — shows both runs from Steps 2–3.
- [ ] **Step 5:** Verify aliases still work — `/dev-loops run testing` and `/dream` invocations dispatch correctly and print the deprecation notice.
- [ ] **Step 6:** Run `sync_agents sync agents all` end-to-end; confirm every Codex automation file under `~/.codex/automations/` is byte-identical to the pre-758 state (only the code emitting them changed).
- [ ] **Step 7:** Commit any small fixes from the real-data run.

---

## Task 10: Documentation update

**Files:**
- Modify: `docs/architecture-daemon.md` (rewrite the "Compounding routines" section to describe the unified mechanism)
- Modify: `docs/agent-topics/agent-rules.md` (if Rule #19's wording needs aligning with the unified noun)

**Dependencies:** Tasks 4–9.

- [ ] **Step 1: Rewrite architecture-daemon.md** — replace the post-744 (and post-755 if updated by ADR-755's Task 14) section with a description of the unified Routines mechanism. One table for execution models, one for policies, one diagram for the registry-based dispatch flow.

- [ ] **Step 2:** Commit.

---

## Task 11: ADR-758 status flip + post-write hook

**Dependencies:** Tasks 0–10.

- [ ] **Step 1: Flip status** Proposed → Implemented.
- [ ] **Step 2: Post-write hook:**
  ```bash
  python3 .github/scripts/adr_upsert_live.py
  python3 .github/scripts/generate_adr_index.py
  python3 src/lib/index/unified_indexer.py --category adrs
  python3 -m skills.ai.scripts.sync_agents sync agents all
  ```
- [ ] **Step 3:** Final commit + handoff via `superpowers:finishing-a-development-branch`.

---

## Parallelism Map

- **Task 0** (gate verification): sequential, must complete first
- **Task 1** (manifest): sequential after Task 0
- **Task 2** (registry + fixtures): sequential after Task 1
- **Tasks 3a–3f** (per-skill `x-augur-routine` declarations + schedule moves): **parallel-safe, 6 teammates**
- **Tasks 4, 5, 6, 7** (CLI/dispatch, Codex adapter, slash aliases, status surface): partial parallelism possible — Tasks 4 + 5 are sequential (5 needs 4's registry dispatch); Tasks 6 + 7 depend on Task 4 but are independent of each other and of Task 5 → **Tasks 5, 6, 7 can run as 3 parallel teammates after Task 4**
- **Task 8** (capability exposure): sequential after Tasks 4–7
- **Task 9** (real-data validation): sequential after Task 8
- **Task 10** (docs): sequential after Task 9
- **Task 11** (status flip): sequential after Task 10

Critical path: **Task 0 → 1 → 2 → {3a–3f parallel} → 4 → {5, 6, 7 parallel} → 8 → 9 → 10 → 11** = 9 sequential steps vs 16 fully-sequential.

---

## Rollback

- Each migration task is one commit. Revert any single commit to back out one skill's routine declaration or one component of the unification.
- Tasks 3a–3f are additive (new SKILL.md fields + schedule yaml moves); revert any single one to restore that skill to its pre-758 state.
- Task 4's `aug routine` CLI is purely additive; legacy `/dev-loops` and `/dream` keep working unchanged in this plan (Tasks 6 adds alias dispatch but doesn't remove the original commands).
- Task 5's `_sync_routine_automations` runs alongside the legacy methods (not replacing them); both populate Codex automations during the transition. Reverting Task 5 leaves only the legacy methods active.
- The centralized `codex-dev-loop-schedules.yaml` deletion is NOT in this plan's scope — it's a follow-up cleanup after one release cycle of the unified projection being live and verified.
- The legacy `_sync_dev_loop_automations` + `_sync_dream_automations` deprecation shims remain in place after this plan completes; their full removal is a follow-up cleanup.
- No vault data mutated. No user-facing slash command broken (aliases preserve invocation paths).
- Trust state file untouched.
- ADR-743 ledger schema untouched.
