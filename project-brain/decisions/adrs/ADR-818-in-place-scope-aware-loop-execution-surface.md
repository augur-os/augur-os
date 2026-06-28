---
status: Accepted
date: 2026-06-27
deciders:
  - Gur
related:
  - ADR-755
  - ADR-758
  - ADR-793
  - ADR-810
  - ADR-816
  - ADR-817
hub: null
tags:
  - loops
  - daemon
  - orchestrator
  - execution-surface
  - architecture
superseded_by: null
---

# ADR-818: In-place, scope-aware execution surface for non-worktree loop families

## Status

Accepted. **Phase 1 (routing) implemented 2026-06-27.**

Phase 1 ships the unambiguous core: `isolation.mode` is now a retained,
routed field. `registry.Routine` carries `isolation_mode` (computed from the
loop's raw declaration, defaulting to `worktree` so undeclared code loops keep
fanning out), and `goal_ops._default_orchestrator_loops()` excludes
`isolation.mode: in-place` loops from the `/a-loops all` worktree fan-out. The
three fundamentally-in-place loops are declared in-place: `self-heal`,
`observability`, `knowledge-enrichment`. Triage now reports them under a new
`in_place_loops` field (routed to the daemon, never silently dropped).

**Phase 2 (runner) implemented 2026-06-28.** Surface schema (`ALLOWED_SURFACE`),
`registry.Routine.execution_surface`, surface declarations (self-heal/
observability → `runtime`; knowledge-enrichment → `vault`), and the in-place
runner `goal_ops.op_run_inplace` (CLI `goal-run-inplace`) with surface-tiered
guardrails: `runtime` auto-applies via the loop's own sanctioned tools with **no
git commit**; `repo` commits the code repo; `mixed` → code-repo. Triage emits
`in_place_loops` + `in_place_surfaces`; the `/a-loops all` contract runs them via
`goal-run-inplace`. Validated on real data (vault scan+escalate: 5 deferred;
self-heal runtime scan: 74 deferred, no git commit).

**Vault gate LIFTED 2026-06-28 (ADR-816 Alternative 3, ratified by Gur).**
Rather than block on the unimplemented ADR-816 remote lease, `op_run_inplace`'s
`vault` surface now auto-applies aggressively and commits + pushes the vault via
`vault_sync_run` under the ADR-195 **machine-local merge lock** — the SAME
coordination the daemon already uses nightly. It is conflict-safe (pull ff/merge,
abort on conflict, never force) and only commits when fixes actually landed
(`applied > 0`); the CODE repo is never touched (`commit_runner=_no_repo_commit`).
Cross-machine collisions are made *cheap* (push-rebase-retry), not *eliminated* —
eliminating them is what the ADR-816 remote advisory lease would do, and that
remains the open follow-up if the collision rate proves high (the ADR suggests
measuring first). Validated on real data: aggressive knowledge-enrichment run
applied 0 mechanical fixes (all semantic/deferred) so it correctly skipped the
vault commit, leaving the vault pristine.

Still pending: implement the ADR-816 remote lease (full cross-machine
elimination); `hardening` per-finding `mixed` routing (stays worktree today);
an explicit report-only bound for runtime self-heal (currently difficulty-gated
like the daemon).

## Context

`/a-loops all` drives every tiered loop through a parallel **worktree fan-out**:
`op_fanout_plan` (`project-brain/capabilities/skills/daemon/scripts/routine_orchestrator/goal_ops.py`)
asks `_default_orchestrator_loops()` for the loop set, then each loop is scanned and
fixed inside its own throwaway git worktree off `main`. Inside the worktree,
`op_scan_loop` partitions every finding with `_finding_in_worktree(finding, root)`:
a finding whose path resolves *outside* the worktree root is removed from the
mutating mechanical-fix phase and reported only as a count
(`out_of_worktree`) plus a small sample (`out_of_worktree_sample`).

This isolation is **correct** for in-repo code loops — `code-quality`, `testing`,
`duplication`, `ui-quality`, `page-health` — whose findings are repo files and
whose fixes must land as an isolated, ff-mergeable checkpoint.

It is **structurally wrong** for whole loop *families* whose findings live outside
the repo by design (per ADR-270 path helpers — `get_vault_dir`, `get_runtime_dir`,
`get_logs_dir` — and per the external client-config surface):

| Family | Where findings live |
|---|---|
| `self-heal` | runtime health + external client MCP configs (`~/Library/Application Support/Augur`, `~/.codex`, `~/.claude`, …) |
| `hardening`, `auto-vault-hygiene`, `auto-frontmatter-lint`, `auto-markdowns` | the **vault** (a separate repo outside the code checkout) |
| `observability` | daemon / runtime logs |
| `knowledge-enrichment` | the vault + gitignored generated projections |

For these loops, **every** finding is out-of-worktree. The in-scope set is empty,
so the mechanical phase mutates nothing, the worktree produces **0 commits**, and
the loop reports "converged" — a green-but-empty result that violates rule 8
(auto-loops must be honest) and rule 34 (a mechanical pass is not user value). The
worktree is pure overhead; the real work never happens through `/a-loops all`.

Two facts make this fixable without inventing a new subsystem:

1. **The destination surface already exists.** These same loops *already* run
   in-place via the daemon's adaptive engine
   (`daemon/scripts/adaptive_loop_executor.py` → `adaptive/engine.py`), on the live
   main checkout / vault / runtime, on a nightly schedule, with vault writes guarded
   by `external_commit=True` (`routine-vault/scripts/vault_hygiene_ops.py`) and
   semantic escalation gated at `min_difficulty` (`config/system/adaptive_loops.yaml`).
   The gap is not "there is no in-place runner" — it is "`/a-loops all` refuses to
   use it and forces a worktree instead."

2. **The routing key already exists but is dropped.** `loop_model.StandardLoop`
   parses `isolation.mode ∈ {worktree, in-place}` (default `in-place`) from each
   loop's `x-augur-loop` frontmatter and *validates* it
   (`ALLOWED_ISOLATION`). But the registry's `Routine` dataclass
   (`routine_orchestrator/registry.py`) never copies `isolation` onto the resolved
   routine, and `_default_orchestrator_loops()` selects loops purely by
   `execution != "inline-session"` — it **never consults `isolation.mode`**. So a
   loop can declare `isolation: {mode: in-place}` and still be fanned into a worktree.

This ADR decides how the non-worktree families get an in-place, scope-aware
execution surface with safety appropriate to the user data / external config they
touch.

## Decision

Make the **already-parsed-but-ignored `isolation.mode` the orchestrator routing
key**, and add a finer **`surface` sub-classifier** that selects the in-place write
target and its guardrail policy. Route in-place loops to the **existing** daemon
adaptive engine, run inline in the `/a-loops all` session — never into a throwaway
worktree.

Concretely:

1. **Loop classification (Option D, minimally).** Keep `isolation.mode ∈
   {worktree, in-place}` as the binary *routing* primitive. Add an optional
   `surface ∈ {repo, vault, runtime, mixed}` on the loop declaration that names the
   in-place *write target* and guardrail policy. `worktree` loops need no `surface`.
   Loops omitting `surface` default to `mixed`, which routes each finding by where
   its path lands (reusing the existing `_finding_in_worktree` partition).

2. **Propagate the field.** `Routine` (registry) carries `isolation` and a derived
   `execution_surface`; `_routine_from_loop` copies them from the parsed
   `StandardLoop`.

3. **Split the orchestrator routing.** `_default_orchestrator_loops()` — the
   `/a-loops all` worktree fan-out set — includes **only** `isolation.mode ==
   "worktree"` loops. `in-place` loops are dispatched to an **in-place runner** that
   reuses the daemon adaptive engine's scan → mechanical → escalate phases against
   the live target named by `surface`, inline in the current session (like the
   ADR-793 inline-session loops, but driving the mechanical engine rather than a
   prompt). No worktree is created; no code-repo commit is made for `vault`/`runtime`
   surfaces.

4. **Per-surface guardrail policy** (the safety model, honoring CLAUDE.md rules
   24–26 and the configure-mcp work):

   | `surface` | Write target | Commit policy | Guardrails |
   |---|---|---|---|
   | `repo` | live main checkout | commit to code repo via the daemon on-main gate | existing project verify gate |
   | `vault` | the vault repo | `external_commit=True` — **never** the code repo | ADR-816 cross-machine vault write lock; rules 24–26 (vault writes need care; `/dev merge full` covers vault) |
   | `runtime` | runtime / logs / external client MCP configs | **no commit** — corrected live state + report only | external-config writes go **only** through `configure-mcp-server` / `repair-mcp-configs` (never raw `fs`); self-heal restarts stay instance-scoped per ADR-810/817 `scoped_restart` |
   | `mixed` | per finding | per finding (above) | partition by `_finding_in_worktree`; each finding inherits its target's policy |

5. **Make the triage signal route, not just report.** During `op_fanout_plan`
   triage (which already scans every loop once), compute issue #1's
   `loops_with_out_of_scope_work` by partitioning each loop's findings with
   `_finding_in_worktree`. The signal becomes a **drift check** validating the static
   `surface` classification against observed finding locations: a `worktree`-classified
   loop emitting all-out-of-scope findings (or an `in-place` loop emitting all
   in-scope findings) is a misclassification to fix, not a silent stall. The plan
   reports three buckets — `worktree_loops`, `in_place_loops`, and
   `loops_with_out_of_scope_work` (classification-vs-observation mismatches) — instead
   of one undifferentiated `loops_with_work`.

The daemon's nightly in-place execution of these loops is unchanged and independent;
this ADR only changes how `/a-loops all` *reaches* the same in-place surface on demand.

## Options considered

### Option A — A new standalone "in-place loop runner"
A separate non-worktree runner operating on the live repo/vault/runtime with its own
per-scope guardrails.
- **Rejected as primary.** It duplicates the daemon adaptive engine, which already
  does exactly in-place scan → mechanical → escalate with the vault `external_commit`
  and difficulty-gated escalation. A second parallel execution path is debt
  (rule 14, canonical cleanup over parallel systems) and a second place for the
  vault/runtime safety model to drift. The chosen decision *reuses* the adaptive
  engine as the in-place runner rather than building a new one.

### Option B — Route these loops to the existing daemon/in-place path
Recognize that the real gap is that `/a-loops all` should not drive in-place loops at
all, and route them to the daemon adaptive engine.
- **Adopted, in synthesis with D.** This is the smallest sufficient change. On its
  own, B answers "where does the work run" but not "how does the orchestrator know
  which loops are in-place" or "what is the per-target safety policy" — that is what D
  supplies.

### Option C — A scoped worktree that mounts the vault
Create a worktree but bind/symlink the vault into it so vault findings resolve
in-scope.
- **Rejected.** The vault is a *separate* git repo (ADR-816 / `config/system/vault.yaml`),
  so a code worktree cannot cleanly own vault commits. More fundamentally, the
  `runtime` family (self-heal, observability) must act on the **live** runtime state
  and **live** external client configs — a copy is meaningless: self-heal repairing a
  worktree-local copy of `~/.codex` heals nothing. Mounting cannot rescue loops whose
  value is in mutating the live, un-versioned thing.

### Option D — Execution-surface classification metadata
Declare each loop's execution surface so the orchestrator routes correctly.
- **Adopted, in synthesis with B.** D is the generalization of the existing binary
  `isolation.mode`. We keep the binary as the routing primitive (the fan-out filter
  only needs worktree-vs-not) and add `surface` to carry the write target + guardrail,
  which the binary cannot express. This is the minimal schema delta: the field is
  already declared and validated; we propagate it and add one optional sibling.

## Consequences

**Positive**

- The seven non-worktree families stop reporting false "converged / 0 commits" and
  actually do their work through `/a-loops all`, satisfying rules 8 and 34.
- No new subsystem: the in-place runner is the existing daemon adaptive engine; the
  routing key is the existing `isolation.mode`. The net new surface is one optional
  `surface` field plus a routing split.
- The vault/runtime safety model lives in exactly one place (shared with the nightly
  daemon path), so it cannot drift between `/a-loops all` and the scheduler.
- Issue #1's `loops_with_out_of_scope_work` signal becomes actionable: a
  classification-vs-observation drift check rather than a passive count.
- Worktree headroom is conserved — in-place loops no longer consume a worktree slot
  they cannot use.

**Negative / risks**

- Running `runtime`/`vault` loops **inline** during an interactive session mutates
  live user data and external configs while the user may be active. Mitigated by the
  per-surface guardrails (sanctioned configure-mcp path; ADR-816 vault lock;
  instance-scoped restarts) and by keeping these loops report-first where a write is
  destructive.
- Concurrency: an on-demand inline `/a-loops all` in-place run can race the nightly
  daemon run and another machine (ADR-816). The vault write lock must cover the inline
  path, not only the daemon path.
- `mixed`-surface loops (e.g. `hardening` emits both code-repo and vault findings)
  add per-finding routing complexity; the existing `_finding_in_worktree` partition is
  reused to contain it.

**Neutral**

- The `x-augur-loop` schema gains one optional field. Existing worktree loops need no
  change (they already behave as `isolation.mode: worktree` once it is honored;
  loops that silently relied on the old "everything fans into a worktree" behavior
  must declare `isolation.mode: worktree` explicitly — a one-line migration per loop).

## Interplay

- **With the worktree fan-out (this issue, #3):** the fan-out keeps owning in-repo
  code loops unchanged; it simply stops adopting loops that declare (or are observed
  to be) non-worktree. `_finding_in_worktree` remains the in-repo safety boundary for
  worktree loops *and* becomes the per-finding router for `mixed` loops.
- **With issue #1 (`loops_with_out_of_scope_work` triage signal):** #1 supplies the
  *detector*; this ADR supplies the *destination* (the in-place surface) and turns the
  detector into a routing + drift-validation signal. They are complementary: #1 alone
  would keep surfacing stalls; this ADR routes them so they no longer stall.
- **With ADR-793 (inline-session loops):** the in-place runner runs inline in the
  active client session, in the same spirit as inline-session loops — but it drives the
  adaptive mechanical/escalation engine against a live `surface` target rather than
  rendering a prompt. `dream` / `inbox-triage` / `goal-loop` remain inline-session and
  out of the fan-out as today.

## Implementation sketch (not implemented in this ADR)

1. **Schema:** add optional `surface ∈ {repo, vault, runtime, mixed}` to the
   `x-augur-loop` declaration; validate in `loop_model.parse_standard_loop`
   (mirror `ALLOWED_ISOLATION` with `ALLOWED_SURFACE`). Default `mixed` when
   `isolation.mode == in-place` and unset.
2. **Propagate:** add `isolation` + `execution_surface` to `registry.Routine` and set
   them in `_routine_from_loop`.
3. **Route:** in `goal_ops._default_orchestrator_loops()`, filter to
   `isolation.mode == "worktree"`. Add `_default_inplace_loops()` for
   `isolation.mode == "in-place"` (still excluding inline-session + `goal-loop`).
4. **In-place runner:** add an `op_run_inplace(loop, surface, …)` that calls the
   daemon adaptive engine's scan → mechanical → escalate against the live target,
   selecting the guardrail policy from `surface`; no worktree, commit policy per the
   table. Reuse `vault_hygiene_ops`' `external_commit=True` for `vault`; route
   `runtime` external-config writes through `configure-mcp-server` /
   `repair-mcp-configs`; acquire the ADR-816 vault lock for `vault`.
5. **Triage:** in `op_fanout_plan`, partition each loop's already-scanned findings
   with `_finding_in_worktree` and emit `worktree_loops`, `in_place_loops`, and
   `loops_with_out_of_scope_work` (drift). `/a-loops all` then fans worktree loops
   out and runs in-place loops via `op_run_inplace`.
6. **Declare surfaces** on the seven families' `x-augur-loop` blocks:
   `self-heal`/`observability` → `runtime`; `auto-vault-hygiene`/`auto-frontmatter-lint`/
   `auto-markdowns`/`knowledge-enrichment` → `vault`; `hardening` → `mixed`.
7. **Tests:** routing unit tests (worktree vs in-place partition honors
   `isolation.mode`); guardrail tests (vault loop never stages the code repo; runtime
   loop never commits; external-config write goes through the sanctioned tool); a
   real-data run of one `vault` loop and `self-heal` proving non-empty user-facing
   output per rule 34.

## Open questions

1. **Inline vs deferred for `/a-loops all`.** Recommendation: inline in-session (the
   user asked for it now). Confirm we do not instead enqueue to the daemon and return.
2. **Vault write coordination scope.** The ADR-816 lock must cover the inline in-place
   path so on-demand `/a-loops all` cannot race the nightly daemon or another machine.
3. **`hardening` granularity.** Confirm per-finding `mixed` routing is sufficient, or
   whether `hardening` should be split into two declared loops (code + vault).
4. **Runtime self-heal during an active session.** Bound which self-heal actions may
   run inline while the user is editing live runtime state (report-only vs auto-apply
   threshold).
