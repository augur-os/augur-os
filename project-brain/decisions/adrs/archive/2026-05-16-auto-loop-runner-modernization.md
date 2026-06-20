# ADR-755 Implementation Plan — Auto-Loop Runner Modernization

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. One failing test first, then implementation, then commit per task. Augur skill-test convention: load target modules via `importlib.util.spec_from_file_location`, never via dotted module path (memory: `feedback-skill-test-convention`).

**Goal:** Land the `routine_orchestrator/` module under `shared-vault/skills/daemon/scripts/`, give it parity coverage with the existing adaptive engine's dispatch path, cut over one low-risk auto-command (`loop-docs/auto-frontmatter-lint`) to it, and prove end-to-end against real data. The legacy `adaptive_loop_executor.py` continues to handle every auto-command without the `x-augur-runner: orchestrator` frontmatter marker. No headless CLI dispatch is removed in this plan — that's Phase 4 (separate ADR), only after every auto-command has the marker.

**Architecture:** New module `shared-vault/skills/daemon/scripts/routine_orchestrator/` is a sibling to `adaptive/`, not a replacement. It owns the new dispatch primitives (scan_phase, fix_phase_mechanical, bucket_planner, escalation_queue, budget, subagent_dispatch, orchestrator). It re-uses the existing trust+reward algorithm and session detection via lightweight extracted modules (`trust.py`, `session_detect.py`). The trust state file at `get_runtime_dir()/adaptive/trust_state.json` is shared between legacy and orchestrator engines so partial-migration states stay coherent. Subagent dispatch goes through the active client's native subagent surface (Claude Code `Task` tool first; Codex / Gemini / Cursor / Copilot stubbed with adapter contract but full implementation deferred to follow-up ADRs as Codex / Gemini subagent semantics get validated). Cursor / Copilot degrade to sequential inline.

**Tech Stack:** Python 3.11 stdlib + PyYAML; pytest with `importlib.util.spec_from_file_location` per Augur skill-test convention; ADR-743 ledger as observability substrate (already shared); `src.config.paths` for runtime / cache / documents paths; no new external dependencies. Subagent dispatch contract is client-aware but does NOT spawn subprocesses — orchestrator runs in the calling session and uses the session's native subagent primitive.

**Spec:** `docs/superpowers/specs/2026-05-16-auto-loop-runner-modernization-design.md`. **Depends on (all Implemented):** ADR-176/181/216/405/412 (adaptive engine internals — preserved as-is), ADR-444 (the dispatch primitive being replaced), ADR-743 (job ledger — observability substrate). **Related (not blocking):** ADR-744 (Dream cycle — architectural shape borrowed), ADR-727 (background routines noun).

**Important finding during planning (folded into Phase 2 scope):** A grep across all `shared-vault/skills/loop-*/scripts/` and `shared-vault/skills/daemon/scripts/` showed **zero production `llm_fix()` implementations**. The `_dispatch_llm_fix` path in `engine_fix_phase.py` exists but is unreachable in production. Consequence: Phase 2 cutover only needs to prove the scan + mechanical-fix path end-to-end. The subagent dispatch path is exercised by tests only (with a mocked Claude Code `Task` primitive) until a real auto-command opts into `llm_fix()`. This significantly reduces Phase 2 production risk.

---

## File Structure

### Create

| Path | Responsibility |
|------|----------------|
| `shared-vault/skills/daemon/scripts/routine_orchestrator/__init__.py` | Public entry: `orchestrate_run(loop_name, ...)` + `scan_only(loop_name, ...)` |
| `shared-vault/skills/daemon/scripts/routine_orchestrator/orchestrator.py` | Top-level coordinator — wires scan → bucket → mechanical → escalation queue → subagent dispatch |
| `shared-vault/skills/daemon/scripts/routine_orchestrator/scan_phase.py` | Deterministic scan dispatch — reads `protocol: scan-fix` discovery, calls `command.scan()`, returns findings |
| `shared-vault/skills/daemon/scripts/routine_orchestrator/fix_phase_mechanical.py` | Pure-Python mechanical-fix application — calls `command.fix()` for `MECHANICAL` findings |
| `shared-vault/skills/daemon/scripts/routine_orchestrator/bucket_planner.py` | Groups `LOCAL_SEMANTIC` findings into subagent buckets by `(auto_command, primary_file)`; honors `fan_out_threshold` |
| `shared-vault/skills/daemon/scripts/routine_orchestrator/escalation_queue.py` | Read/write `pending.jsonl` with TTL semantics; bridges no-session ↔ session-bound runs |
| `shared-vault/skills/daemon/scripts/routine_orchestrator/budget.py` | Per-subagent budget enforcement (`max_turns`, soft timeout) |
| `shared-vault/skills/daemon/scripts/routine_orchestrator/subagent_dispatch.py` | Client-aware dispatch via active client's native subagent surface; degraded sequential-inline mode |
| `shared-vault/skills/daemon/scripts/routine_orchestrator/session_detect.py` | Wraps existing `adaptive/engine_context.SessionContext`; canonical "is a session present?" check |
| `shared-vault/skills/daemon/scripts/routine_orchestrator/trust.py` | Trust+reward algorithm extracted from `adaptive/trust_ledger.py` (TrustLedger class). `record_success` / `record_failure` are simultaneously the reward and trust mutation — one cohesive algorithm, not two. |
| `shared-vault/skills/daemon/augur/tests/test_orchestrator_scan_phase.py` | Tests for `scan_phase` — fixture loop with three auto-commands |
| `shared-vault/skills/daemon/augur/tests/test_orchestrator_bucket_planner.py` | Tests for bucketing rules + `fan_out_threshold` behavior |
| `shared-vault/skills/daemon/augur/tests/test_orchestrator_mechanical_fix.py` | Tests for the pure-Python fix path; no LLM, no session |
| `shared-vault/skills/daemon/augur/tests/test_orchestrator_escalation_queue.py` | Tests for `pending.jsonl` read/write/TTL + race tolerance |
| `shared-vault/skills/daemon/augur/tests/test_orchestrator_budget.py` | Tests for budget enforcement: max_turns cap, soft timeout |
| `shared-vault/skills/daemon/augur/tests/test_orchestrator_subagent_dispatch.py` | Tests with a mocked Claude Code `Task` primitive — dispatch contract, allowlist, result parsing |
| `shared-vault/skills/daemon/augur/tests/test_orchestrator_session_detect.py` | Tests for degraded-mode behavior when no client surface available |
| `shared-vault/skills/daemon/augur/tests/test_orchestrator_trust_parity.py` | Tests that trust mutations from the new orchestrator match what the legacy engine would emit for the same finding |
| `shared-vault/skills/daemon/augur/tests/test_orchestrator_end_to_end.py` | Full fixture-loop round-trip — three auto-commands, mocked subagent, real trust state mutation |
| `shared-vault/skills/daemon/augur/tests/_fixtures.py` | Shared fixture builders for the orchestrator test suite (per `feedback-skill-test-convention` — NOT a conftest.py to avoid pytest collision) |
| `shared-vault/skills/daemon/augur/tests/fixtures/toy_loop/` | Synthetic loop with three auto-commands: one MECHANICAL (always succeeds), one LOCAL_SEMANTIC (needs subagent), one STRUCTURAL (defers to ADR design gate) |
| `shared-vault/skills/daemon/commands/routine.md` | New `aug routine` CLI subcommand documentation — `scan-only`, `orchestrate`, `pending-escalations` verbs |

### Modify

| Path | Change |
|------|--------|
| `shared-vault/skills/daemon/scripts/adaptive/trust_ledger.py` | Add re-exports so legacy adaptive engine imports of `TrustLedger`, `record_success`, `record_failure` continue to resolve to the extracted `routine_orchestrator/trust.py` implementation; no behavior change |
| `shared-vault/skills/daemon/scripts/mcp/__init__.py` | Add `register_subcommands(subparsers)` clause for `aug routine <verb>` — wires the new CLI surface |
| `shared-vault/skills/daemon/scripts/adaptive_loop_executor.py` | Phase 2 only: routing logic — for each auto-command in the requested loop, check frontmatter for `x-augur-runner: orchestrator`. If present, delegate the *fix phase* (scan stays in the legacy path for now to minimize variables) to `routine_orchestrator.orchestrator.fix_one_command()`. Otherwise legacy path unchanged. |
| `shared-vault/skills/loop-docs/commands/auto-frontmatter-lint.md` | Phase 2 only: add `x-augur-runner: orchestrator` frontmatter marker |
| `config/system/capability_exposure.yaml` | Add `command:routine:` entry projecting the new `/routine` CLI surface to client surfaces (per memory `feedback-command-capability-entry`) |
| `shared-vault/skills/daemon/SKILL.md` | Add `routine` to `x-augur-commands` declaring the new CLI surface and a one-line description of the orchestrator's role |

---

## Task 1: Scaffold `routine_orchestrator/` module + shared fixture builders

**Files:**
- Create: `shared-vault/skills/daemon/scripts/routine_orchestrator/__init__.py` (with stub `orchestrate_run` / `scan_only` raising NotImplementedError)
- Create: `shared-vault/skills/daemon/augur/tests/_fixtures.py`
- Create: `shared-vault/skills/daemon/augur/tests/fixtures/toy_loop/__init__.py`
- Create: `shared-vault/skills/daemon/augur/tests/fixtures/toy_loop/auto_mech.py` (toy MECHANICAL auto-command — `scan()` returns one finding, `fix()` returns one applied change)
- Create: `shared-vault/skills/daemon/augur/tests/fixtures/toy_loop/auto_semantic.py` (toy LOCAL_SEMANTIC auto-command — `scan()` returns one finding flagged for LLM)
- Create: `shared-vault/skills/daemon/augur/tests/fixtures/toy_loop/auto_struct.py` (toy STRUCTURAL auto-command — `scan()` returns finding requiring ADR design gate)

- [ ] **Step 1: Write the import smoke test**

```python
# shared-vault/skills/daemon/augur/tests/test_orchestrator_scaffold.py
import importlib.util
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts" / "routine_orchestrator" / "__init__.py"
)
_SPEC = importlib.util.spec_from_file_location("routine_orchestrator", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def test_module_exposes_public_api():
    assert hasattr(mod, "orchestrate_run")
    assert hasattr(mod, "scan_only")


def test_stub_raises_not_implemented():
    import pytest
    with pytest.raises(NotImplementedError):
        mod.orchestrate_run(loop_name="testing")
    with pytest.raises(NotImplementedError):
        mod.scan_only(loop_name="testing")
```

- [ ] **Step 2: Implement the scaffold + fixtures**

`__init__.py`: define `orchestrate_run` and `scan_only` raising `NotImplementedError`. Public API placeholders, real implementations land in Tasks 4-11.

Toy auto-commands in `fixtures/toy_loop/`: each implements `scan(ctx)` + `fix(ctx, issues)` per the `OpsCommand` protocol. Returns deterministic findings keyed to the band (MECHANICAL / LOCAL_SEMANTIC / STRUCTURAL).

`_fixtures.py`: builder functions `build_toy_loop()`, `build_fixture_runtime_dir(tmp_path)`, `build_trust_state_file(tmp_path)`. NOT a pytest conftest — per memory `feedback-skill-test-convention`'s implications, conftest.py at this level collides with the project-root conftest.

- [ ] **Step 3: Run scaffold test green via `/auto-test-pytest`.**

- [ ] **Step 4: Commit.**

```bash
git commit -m "$(cat <<'EOF'
feat(orchestrator): scaffold routine_orchestrator + toy-loop fixtures (ADR-755 task 1)

[body explaining scaffold-only, no behavior]

Skip-Verify: no dashboard touch.
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Extract trust+reward into `routine_orchestrator/trust.py` (zero behavior change)

> **Finding from ADR-write grep**: trust and reward are the same algorithm in `adaptive/trust_ledger.py`. `record_success` / `record_failure` are simultaneously the reward mutations and the trust updates — there's no separate `reward.py` to extract. The original plan's separate Tasks 2 + 3 collapse cleanly into this one task. Cluster A drops from 8 → 7 parallel teammates.

**Files:**
- Create: `shared-vault/skills/daemon/scripts/routine_orchestrator/trust.py`
- Create: `shared-vault/skills/daemon/augur/tests/test_orchestrator_trust_parity.py`
- Modify: `shared-vault/skills/daemon/scripts/adaptive/trust_ledger.py` (add re-exports for backwards compatibility; ensure all call sites in `adaptive/` still resolve)

**Dependencies:** Task 1.

- [ ] **Step 1: Write parity test**

For five representative trust transitions (success, failure, consecutive-success-promotes-difficulty, consecutive-failure-disables, clean-scan-streak), assert that the new `routine_orchestrator/trust.py` produces byte-identical state mutations to what `adaptive/trust_ledger.TrustLedger` produces for the same input. Tests load both modules side by side via `importlib.util` and compare resulting `CategoryState` + `LoopState` dataclasses field-by-field.

- [ ] **Step 2: Extract the algorithm**

Move the `TrustLedger` class (and its dependency on `CategoryState` / `LoopState` dataclasses from `trust_state.py`) to `routine_orchestrator/trust.py`. Re-export from the original `adaptive/trust_ledger.py` so the legacy engine's imports continue to work. **No call-site changes in the legacy engine.** Both `record_success` and `record_failure` come with the move — they are the reward and trust mutation in one cohesive algorithm.

- [ ] **Step 3: Run parity tests green; confirm existing adaptive engine tests still pass.**

```bash
/auto-test-pytest shared-vault/skills/daemon/augur/tests/
```

- [ ] **Step 4: Commit.**

---

## Task 3: `session_detect.py` (wraps existing SessionContext)

**Files:**
- Create: `shared-vault/skills/daemon/scripts/routine_orchestrator/session_detect.py`
- Create: `shared-vault/skills/daemon/augur/tests/test_orchestrator_session_detect.py`

**Dependencies:** Task 1.

**Independence:** Parallel-safe with Tasks 2/3/5/6/7/8/9.

- [ ] **Step 1: Write failing tests** for three contexts:
  - `test_in_session_with_claude_code_detects_subagent_capability` — fixture env has Claude Code CLI on PATH, returns a `SessionContext` with `subagent_surface="claude-code"`, `has_llm=True`
  - `test_headless_environment_returns_no_session_context` — no client CLI on PATH, returns `SessionContext` with `has_llm=False`, `subagent_surface=None`
  - `test_cursor_returns_degraded_mode_marker` — Cursor CLI detected but no subagent surface, returns `subagent_surface="degraded-inline"`

- [ ] **Step 2: Implement**

Thin wrapper around the existing `adaptive/engine_context.SessionContext`. Adds a `subagent_surface` field derived from the detected CLI: `claude-code` → `"claude-code"`, `codex` → `"codex"` (stub for now), `gemini` → `"gemini"` (stub), `cursor` / `copilot` → `"degraded-inline"`, none → `None`.

- [ ] **Step 3: Run green; commit.**

---

## Task 4: `scan_phase.py` — deterministic scan dispatch

**Files:**
- Create: `shared-vault/skills/daemon/scripts/routine_orchestrator/scan_phase.py`
- Create: `shared-vault/skills/daemon/augur/tests/test_orchestrator_scan_phase.py`

**Dependencies:** Task 1 (fixture loop available).

**Independence:** Parallel-safe with Tasks 2/3/4/6/7/8/9.

- [ ] **Step 1: Write failing tests**
  - `test_scan_phase_runs_all_commands_in_loop` — toy loop with three commands; scan runs all three, returns flat list of findings
  - `test_scan_phase_continues_on_command_failure` — when one command's `scan()` raises, the others still run; the failure is recorded as a finding with `kind="scan-error"` instead of being lost
  - `test_scan_phase_no_session_required` — scan runs successfully with a SessionContext where `has_llm=False`

- [ ] **Step 2: Implement**

Discovers auto-commands the same way `adaptive_loop_executor` discovers them (reuses `adaptive/discovery.py:discover_auto_commands`, filtered to the requested loop). For each command, calls `command.scan(ctx)` with a fresh `OpsContext`. Returns a list of `Finding` dicts annotated with `auto_command` (the source command's name) and `loop` (the parent loop name).

Findings from a command that crashed during scan are recorded as one synthetic finding with `kind="scan-error"`, `band="MECHANICAL"` (so they get reported but never escalated to LLM), `error_message` set.

- [ ] **Step 3: Run green; commit.**

---

## Task 5: `fix_phase_mechanical.py` — pure-Python mechanical fix

**Files:**
- Create: `shared-vault/skills/daemon/scripts/routine_orchestrator/fix_phase_mechanical.py`
- Create: `shared-vault/skills/daemon/augur/tests/test_orchestrator_mechanical_fix.py`

**Dependencies:** Task 1; ideally after Task 4 to use real scan outputs as test input (but the test can build them inline).

**Independence:** Parallel-safe with Tasks 2/3/4/5/7/8/9.

- [ ] **Step 1: Write failing tests**
  - `test_mechanical_fix_applies_pure_python_only` — toy auto-command's `fix()` runs; no subagent dispatch attempted
  - `test_mechanical_fix_invokes_verify_command` — after `fix()` returns, the auto-command's `verify_command` is run; success commits, failure reverts
  - `test_mechanical_fix_skips_non_mechanical_findings` — a LOCAL_SEMANTIC finding passed in is left untouched (returned in `deferred`)
  - `test_mechanical_fix_records_trust_success_on_commit` — trust state mutates on verified commit; matches Task 2's trust algorithm

- [ ] **Step 2: Implement**

For each MECHANICAL finding: call `command.fix(ctx, [finding])`. If returned with changes, run `verify_command`. If verify passes, `git add` the changed files + `git commit` with a templated message. Update trust ledger via `routine_orchestrator/trust.py`. If verify fails, `git checkout` the file (revert). LOCAL_SEMANTIC and STRUCTURAL findings are returned in the `deferred` list for bucket_planner to handle in Task 6.

- [ ] **Step 3: Run green; commit.**

---

## Task 6: `bucket_planner.py` — group findings into subagent buckets

**Files:**
- Create: `shared-vault/skills/daemon/scripts/routine_orchestrator/bucket_planner.py`
- Create: `shared-vault/skills/daemon/augur/tests/test_orchestrator_bucket_planner.py`

**Dependencies:** Task 1.

**Independence:** Parallel-safe with Tasks 2/3/4/5/6/8/9.

- [ ] **Step 1: Write failing tests**
  - `test_buckets_group_by_command_and_file` — findings get grouped by `(auto_command, primary_file)`; one bucket per pair
  - `test_below_threshold_returns_single_dispatch_strategy` — when `len(buckets) <= fan_out_threshold` (default 8), strategy = `inline-sequential`
  - `test_above_threshold_returns_fan_out_strategy` — above threshold, strategy = `parallel-fan-out`
  - `test_threshold_is_configurable_per_loop` — per-loop override from `config/system/adaptive_loops.yaml`
  - `test_structural_findings_never_bucketed` — STRUCTURAL findings produce design-gate buckets, not dispatch buckets

- [ ] **Step 2: Implement**

Group `LOCAL_SEMANTIC` findings into buckets keyed by `(auto_command_name, primary_file_path)`. Return a `BucketPlan` dataclass: `{buckets: list[FindingBucket], strategy: Literal["inline-sequential", "parallel-fan-out"], design_gate_findings: list[Finding]}`.

`fan_out_threshold` is per-loop config (read from `config/system/adaptive_loops.yaml:loops.<loop>.fan_out_threshold`), default 8.

- [ ] **Step 3: Run green; commit.**

---

## Task 7: `escalation_queue.py` — pending.jsonl with TTL

**Files:**
- Create: `shared-vault/skills/daemon/scripts/routine_orchestrator/escalation_queue.py`
- Create: `shared-vault/skills/daemon/augur/tests/test_orchestrator_escalation_queue.py`

**Dependencies:** Task 1.

**Independence:** Parallel-safe with Tasks 2/3/4/5/6/7/9.

- [ ] **Step 1: Write failing tests**
  - `test_enqueue_writes_to_pending_jsonl` — call `enqueue(finding)`, file has one JSON line with the right schema
  - `test_dequeue_returns_entries_under_ttl` — three entries; one is older than TTL, two fresh; dequeue returns two fresh
  - `test_dequeue_drops_stale_entries_and_records_ledger_event` — stale entry is dropped, ledger event captures the drop
  - `test_pick_up_marks_entry_in_progress_atomically` — concurrent pickups don't double-dispatch the same finding (file-lock semantics)
  - `test_malformed_line_is_skipped_not_fatal` — a corrupted JSON line in `pending.jsonl` is logged and skipped; other lines process normally

- [ ] **Step 2: Implement**

File: `get_runtime_dir()/jobs/_escalations/pending.jsonl`. Append-only writes (atomic single-line append). Reads take a file-lock snapshot. TTL default 14 days (configurable). `pick_up()` marks an entry by writing a sibling `picked_up.jsonl` with the entry's id + pickup timestamp; double-pickup detection reads both files. Successful processing removes the entry from `pending.jsonl` (rewrite without the line); failure leaves it for retry (TTL preserved).

- [ ] **Step 3: Run green; commit.**

---

## Task 8: `budget.py` — per-subagent budget enforcement

**Files:**
- Create: `shared-vault/skills/daemon/scripts/routine_orchestrator/budget.py`
- Create: `shared-vault/skills/daemon/augur/tests/test_orchestrator_budget.py`

**Dependencies:** Task 1.

**Independence:** Parallel-safe with Tasks 2/3/4/5/6/7/8.

- [ ] **Step 1: Write failing tests**
  - `test_budget_default_max_turns_20` — `Budget.default(loop="testing")` returns `max_turns=20`
  - `test_budget_per_loop_override_from_config` — config `loops.testing.subagent_max_turns: 30` makes the default 30
  - `test_budget_soft_timeout_default_600s` — soft timeout 10 minutes by default
  - `test_check_remaining_returns_false_when_exhausted` — turn counter exceeds max → returns False
  - `test_budget_×3_multiplier_for_llm_dispatch_preserved` — ADR-444's 3× multiplier for LLM work survives (mechanical fixes don't get the multiplier)

- [ ] **Step 2: Implement**

`Budget` dataclass: `max_turns`, `soft_timeout_s`, `consumed_turns`, `start_time`. `default(loop)` reads `config/system/adaptive_loops.yaml`. `consume(turns=1)` decrements; `check_remaining()` returns whether subagent should continue. The ×3 LLM multiplier is applied at construction time when `kind="llm"` is passed.

- [ ] **Step 3: Run green; commit.**

---

## Task 9: `subagent_dispatch.py` — client-aware fan-out

**Files:**
- Create: `shared-vault/skills/daemon/scripts/routine_orchestrator/subagent_dispatch.py`
- Create: `shared-vault/skills/daemon/augur/tests/test_orchestrator_subagent_dispatch.py`

**Dependencies:** Tasks 4 (session_detect), 9 (budget).

- [ ] **Step 1: Write failing tests**
  - `test_dispatch_via_claude_code_task_tool_with_mocked_primitive` — fixture mocks the Claude Code `Task` invocation; assert the prompt structure (description + bucket findings + tool allowlist + budget hint)
  - `test_subagent_result_parsing` — mocked subagent returns `{"status": "success", "commit_hash": "abc", "diagnostic": "..."}`; orchestrator parses correctly
  - `test_subagent_failure_returned_as_structured_result` — mocked subagent returns failure; orchestrator returns structured failure (no exception)
  - `test_degraded_inline_mode_for_cursor` — SessionContext with `subagent_surface="degraded-inline"` → dispatch falls back to sequential inline call (no subagent fan-out); test asserts the fallback path is taken
  - `test_no_session_raises_explicit_error` — SessionContext with `subagent_surface=None` → dispatch raises `NoSessionAvailable` (caller should have routed to escalation queue instead)

- [ ] **Step 2: Implement**

`dispatch_bucket(bucket, auto_command, session_context, budget)`:
- Reads `session_context.subagent_surface` to pick the primitive
- `claude-code`: invokes the active session's `Task` tool with the constructed prompt; in tests, this is mocked via a module-level `_TASK_INVOKER` hook
- `codex` / `gemini`: stubs that raise `NotImplementedError` with a TODO comment pointing at the follow-up validation work
- `degraded-inline`: calls `command.fix(ctx, bucket.findings)` directly + verify + commit (loses subagent isolation; works on Cursor/Copilot)
- `None`: raises `NoSessionAvailable`

Returns a structured `DispatchResult` dataclass: `{status, commit_hash, diagnostic, budget_consumed}`.

The `CLIENT_SUBAGENT_MAP` defines per-auto-command-skill → subagent_type defaults (e.g. `loop-test` → `general-purpose`, `loop-security` → would be `security-reviewer` if it existed; falls back to `general-purpose`).

- [ ] **Step 3: Run green; commit.**

---

## Task 10: `orchestrator.py` — top-level coordinator

**Files:**
- Create: `shared-vault/skills/daemon/scripts/routine_orchestrator/orchestrator.py`

**Dependencies:** Tasks 2, 3, 4, 5, 6, 7, 8, 9, 10 (everything).

- [ ] **Step 1: Write failing test (end-to-end fixture round-trip)**

`test_orchestrator_end_to_end.py`:
- Build toy loop (Task 1 fixtures), build fixture runtime dir + trust state file
- Mock the Claude Code `Task` invoker
- Call `orchestrator.orchestrate_run(loop_name="toy-loop")`
- Assert:
  - All three toy auto-commands' `scan()` ran (deterministic scan phase)
  - MECHANICAL finding was fixed via pure Python; trust+
  - LOCAL_SEMANTIC finding was dispatched to mocked subagent; subagent returned success; trust+
  - STRUCTURAL finding was deferred to ADR design gate (no fix, no trust mutation)
  - Trust state file reflects the two successes
  - ADR-743 ledger captured per-phase events

- [ ] **Step 2: Implement**

`orchestrate_run(loop_name, ...)`:
1. Detect session via `session_detect.detect()`
2. Discover auto-commands for loop via existing `adaptive/discovery.py`
3. Call `scan_phase.run_scan(commands, ctx)` → flat findings list
4. Load pending escalations via `escalation_queue.load_pending()`; merge with new findings
5. Call `fix_phase_mechanical.apply(findings, ctx)` → returns `(applied, deferred)`
6. For `deferred` (LOCAL_SEMANTIC) findings:
   - If session present: bucket via `bucket_planner.plan()`, dispatch via `subagent_dispatch.dispatch_bucket()`
   - If session absent: `escalation_queue.enqueue()` each finding
7. STRUCTURAL findings → ADR design gate (no orchestrator action; same as today's adaptive engine)
8. Write per-phase events to ADR-743 ledger throughout
9. Return `OrchestrateResult` dataclass with counts + bucket dispositions

`scan_only(loop_name)`:
- Steps 1-5 only (no subagent dispatch, no escalation queue write — just scan + mechanical fix)
- Session-agnostic; runs without a client

- [ ] **Step 3: Run green via `/auto-test-pytest`.**

- [ ] **Step 4: Commit.**

---

## Task 11: `aug routine <verb>` CLI surface

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/mcp/__init__.py` (add `register_subcommands` for `routine`)
- Create: `shared-vault/skills/daemon/commands/routine.md`
- Modify: `config/system/capability_exposure.yaml` (add `command:routine:` entry)
- Modify: `shared-vault/skills/daemon/SKILL.md` (declare the new `routine` command)

**Dependencies:** Task 10.

- [ ] **Step 1: Write failing test**

`test_routine_cli_subcommand.py`:
- `test_aug_routine_verbs_parse` — `scan-only`, `orchestrate`, `pending-escalations` parse cleanly
- `test_aug_routine_scan_only_invokes_orchestrator_scan_only` — argparse → `routine_orchestrator.scan_only()` is called with correct loop name (orchestrator mocked)
- `test_aug_routine_no_verb_prints_help_with_exit_code_2`

- [ ] **Step 2: Implement**

Mirror the `aug dream` CLI pattern from `shared-vault/skills/dream/scripts/mcp/__init__.py`. Three verbs:
- `scan-only --loop <name>` — invokes `orchestrate_run(scan_only=True)` (session-agnostic); prints findings JSON
- `orchestrate --loop <name>` — invokes `orchestrate_run()` (session-bound); refuses if no session detected
- `pending-escalations [--show|--clear-stale]` — reads `pending.jsonl`, prints summary; optional `--clear-stale` removes TTL-expired entries

Add `command:routine:` to `capability_exposure.yaml` per memory `feedback-command-capability-entry`.

- [ ] **Step 3: Run green via `/auto-test-pytest`.**

- [ ] **Step 4: Real-data validation against the live repo:**

```bash
aug routine scan-only --loop testing
```

Quote the actual findings the scan returns. Confirm they're real (not empty, not error-filled). If the findings shape is wrong against a real loop, that's a finding to fix.

- [ ] **Step 5: Commit.**

---

## Task 12: Phase 2 — Routing logic in `adaptive_loop_executor.py`

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/adaptive_loop_executor.py`
- Create: `shared-vault/skills/daemon/augur/tests/test_legacy_executor_routes_to_orchestrator.py`

**Dependencies:** Tasks 1-12 complete.

- [ ] **Step 1: Write failing test**

`test_legacy_executor_routes_to_orchestrator.py`:
- Build a loop with two auto-commands: one with `x-augur-runner: orchestrator` frontmatter, one without
- Mock both the orchestrator and the legacy fix path
- Run the loop via `adaptive_loop_executor.main(["run", "<loop>"])`
- Assert: marked command's fix went through orchestrator; unmarked command's fix went through legacy path

- [ ] **Step 2: Implement**

In `adaptive_loop_executor`, after scan + finding-band classification, check each auto-command's frontmatter for `x-augur-runner: orchestrator`. If present, delegate the fix phase for that command's findings to `routine_orchestrator.orchestrator.fix_one_command()`. If absent, legacy fix path unchanged.

**Note:** *Scan* stays in the legacy path for all commands in this phase to minimize variables; only the *fix* dispatch routes through the orchestrator. Full orchestrator-driven scan dispatch happens in Phase 3 (per-command opt-in).

- [ ] **Step 3: Run green; commit.**

---

## Task 13: Phase 2 — Cut over `loop-docs/auto-frontmatter-lint`

**Files:**
- Modify: `shared-vault/skills/loop-docs/commands/auto-frontmatter-lint.md` (add `x-augur-runner: orchestrator` frontmatter)

**Dependencies:** Task 12.

- [ ] **Step 1: Verify the candidate is safe**

Confirm `auto-frontmatter-lint`:
- Has no `llm_fix()` (verified during planning — none exist in production)
- Has both `scan()` and `fix()` (verified — `shared-vault/skills/loop-docs/scripts/frontmatter_lint.py:79,158`)
- Is in the `hardening` loop (verified — `commands/auto-frontmatter-lint.md`)

- [ ] **Step 2: Add the marker**

One-line frontmatter addition:

```diff
+---
+x-augur-runner: orchestrator
+---
 # auto-frontmatter-lint
```

(if the command doesn't already have YAML frontmatter, this is the only frontmatter; otherwise add the field)

- [ ] **Step 3: Real-data validation**

Run the actual hardening loop with the cutover command:

```bash
/dev-loops run hardening
```

Capture the orchestrator-routed run's output. Compare trust state mutation for `auto-frontmatter-lint` before vs after the cutover (snapshot `trust_state.json[loops.hardening.categories.auto-frontmatter-lint]` before, run, compare). Mutation shape must match what legacy would have produced for the same findings.

- [ ] **Step 4: If mutation matches → commit the marker. If not → debug + fix orchestrator parity; do NOT commit the marker until parity proven.**

---

## Task 14: Documentation update

**Files:**
- Modify: `docs/architecture-daemon.md` (rewrite "Compounding routines" section to reflect orchestrator)
- Modify: `shared-vault/skills/daemon/SKILL.md` (declare orchestrator as a callable + role description)

**Dependencies:** Tasks 1-14.

- [ ] **Step 1: Rewrite the architecture-daemon.md "Compounding routines" section**

Remove the previously incorrect content (two corrections: launchd does NOT fire loops; loops DO use LLM via headless CLI today). Document the new orchestrator-based dispatch as the canonical pattern, with the legacy `_dispatch_llm_fix` flagged for retirement in the follow-up ADR.

- [ ] **Step 2: Update SKILL.md** — add the orchestrator to `x-augur-callable` and document its role.

- [ ] **Step 3: Commit.**

---

## Task 15: Run all Completion Gates

**Dependencies:** Tasks 1-15.

- [ ] **Step 1: Run `/auto-test-pytest`** on the full daemon test suite. All new orchestrator tests + all existing adaptive engine tests must pass. Trust algorithm parity is the critical gate.

- [ ] **Step 2: Run `/auto-lint`** — no new lint failures.

- [ ] **Step 3: Per-skill smoke**

```bash
aug routine scan-only --loop testing     # session-agnostic; quote real findings
aug routine scan-only --loop hardening   # quote real findings
aug routine pending-escalations --show   # show queue state (likely empty)
```

- [ ] **Step 4: Session-bound smoke**

In the active Claude Code session:

```bash
/dev-loops run hardening
```

Observe that `auto-frontmatter-lint` finishes via the orchestrator path. Confirm trust state mutated correctly.

- [ ] **Step 5: Cross-check no headless CLI was invoked** during the smoke runs (grep the run logs for `build_headless_cmd` invocations — there must be zero for any orchestrator-routed command).

- [ ] **Step 6: Verify no regressions in the existing adaptive engine** by running a different non-cutover loop (e.g. `/dev-loops run testing`) and confirming it still routes through the legacy path successfully.

- [ ] **Step 7: Verify pending-escalation queue file location is correct** by writing a synthetic escalation via `escalation_queue.enqueue()` from a Python REPL, then reading back via `aug routine pending-escalations --show`. The file at `get_runtime_dir()/jobs/_escalations/pending.jsonl` should reflect the entry.

---

## Task 16: ADR-755 status flip + post-write hook

**Dependencies:** Task 15.

- [ ] **Step 1: Flip ADR-755 frontmatter** `status: Proposed` → `status: Implemented`. Add a Status section note summarizing the cutover (one auto-command on orchestrator path, parity confirmed against trust mutations, real-data validation evidence).

- [ ] **Step 2: Run post-write hook**

```bash
python3 .github/scripts/adr_upsert_live.py
python3 .github/scripts/generate_adr_index.py
python3 src/lib/index/unified_indexer.py --category adrs
python3 -m skills.ai.scripts.sync_agents sync agents all
```

- [ ] **Step 3: Final commit** consolidating status flip + index regen.

- [ ] **Step 4: Hand off** via `superpowers:finishing-a-development-branch` for merge / PR / cleanup per the user's chosen integration path.

---

## Parallelism Map (for `/adr implement` Phase 3 — Team primitives)

Tasks that touch **disjoint files** and can run as parallel teammates:

**Cluster A (after Task 1, all parallel-safe — each touches its own scripts file + its own test file):**
- Task 2 (`trust.py` — combined trust+reward extraction + parity test + `adaptive/trust_ledger.py` re-exports)
- Task 3 (`session_detect.py` + tests)
- Task 4 (`scan_phase.py` + tests)
- Task 5 (`fix_phase_mechanical.py` + tests)
- Task 6 (`bucket_planner.py` + tests)
- Task 7 (`escalation_queue.py` + tests)
- Task 8 (`budget.py` + tests)

Cluster A's seven independent modules can land in parallel as separate teammates.

**Strictly sequential** (downstream):
- Task 9 (`subagent_dispatch.py` — needs Tasks 3 + 8)
- Task 10 (`orchestrator.py` — needs all of Cluster A + Task 9)
- Task 11 (CLI surface — needs Task 10)
- Task 12 (routing in legacy executor — needs Task 10; touches `adaptive_loop_executor.py` which is shared with no other task)
- Task 13 (Phase 2 cutover — needs Task 12; touches a single frontmatter file)
- Task 14 (docs — needs all prior tasks)
- Tasks 15 (gates), 16 (status flip + closeout) — sequential at the end

So the parallel-safe shape is: **Task 1 → Cluster A in parallel (7 teammates) → Task 9 → Task 10 → Task 11 → Task 12 → Task 13 → Tasks 14..16 sequential.**

**Additional parallel opportunity within sequential downstream:** Tasks 11 (CLI surface), 12 (routing patch), and 14 (docs) are independent of each other once Task 10 (orchestrator) is done. They can run as 3 parallel teammates. This drops the critical path from 5 sequential tasks (10 → 11 → 12 → 13 → 14 → 15 → 16) to ~4 (10 → {11,12,14} parallel → 13 → 15 → 16).

---

## Rollback

- Each task commits independently; revert any single commit to back out one module / one cutover.
- The new `routine_orchestrator/` directory is self-contained — `git rm -rf shared-vault/skills/daemon/scripts/routine_orchestrator/` rolls the whole module back.
- The legacy `adaptive_loop_executor` routing change in Task 12 is purely additive (new code path, gated by frontmatter marker). Reverting the routing patch restores 100% legacy dispatch.
- The Task 13 frontmatter marker is one line; removing it restores `auto-frontmatter-lint` to the legacy path.
- The trust + reward extractions in Tasks 2/3 are re-exported from the original `adaptive/` location; the legacy engine's imports continue to work after a revert.
- The pending-escalation queue file (`pending.jsonl`) is rebuildable from the next scan; deleting it loses no production data (it only holds findings already waiting for a session, and the next scan will resurface them).
- No vault data is mutated. No user-facing config is changed beyond `capability_exposure.yaml` (additive entries) and the one frontmatter marker on `auto-frontmatter-lint`.
- No headless CLI dispatch is removed in this plan. `build_headless_cmd` and `_dispatch_llm_fix` stay intact; the orchestrator just doesn't invoke them. Phase 4 (separate ADR after every auto-command has the marker) is where the actual code deletion happens.
