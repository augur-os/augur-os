---
status: Implemented
date: 2026-05-16
deciders:
  - gsannikov
related:
  - ADR-727
  - ADR-743
  - ADR-744
  - ADR-755
  - ADR-756
  - ADR-757
hub: command
tags:
  - routines
  - unification
  - convergence
  - naming
  - registry
superseded_by: null
spec_file: 2026-05-16-routines-unification-design.md
plan_file: 2026-05-16-routines-unification.md
---

# ADR-758: Routines Unification — One System, One Surface

## Status

**Implemented.** The prerequisite gates were satisfied before implementation and
the unified routine surface is now live:

1. **ADR-755 Implemented** — auto-loop runner modernization shipped, orchestrator stable in production
2. **ADR-756 Implemented** — `loop-*` → `routine-*` skill consolidation shipped
3. **ADR-757 Implemented** — `journal.jsonl` retired, ledger is sole observability substrate (through Phase 3 completion + soak)
4. **Dream cycle production evidence** — at least **10 dream cycle runs** are visible in the ADR-743 ledger (`aug dream status --history-limit 20` shows ≥10 historical entries), AND the recent `git log --oneline shared-vault/skills/dream/` shows no architectural changes for at least one release cycle (the routine prompt and `dream-*` MCP tool surface have stabilized).

Implementation completed on 2026-05-16. `/routines list` now reports the flat
routine registry, `aug routine status` reads the ledger-backed status surface
for both tiered and inline-session routines, Codex routine automation projection
comes from the registry, and `/dev-loops` plus `/dream` remain deprecated
transition aliases.

## Context

ADR-755+756+757 modernize auto-loops in three independent steps. After all three land, the auto-loop side of Augur has:

- A modern subagent-driven runner (`routine_orchestrator/`)
- A clean concern-aligned skill organization (5 `routine-*` skills)
- One observability substrate (the ADR-743 ledger)

ADR-744 (Implemented) introduced the **Dream Cycle**, which uses a fundamentally different execution shape: a multi-phase prompt rendered inline in the client's session, deterministic MCP calls interleaved with judgment phases. Dream proved that the "inline-session" execution model works for compounding work — a pattern auto-loops can't use because their work is fix-and-verify rather than reason-and-propose.

After 755+756+757, the system has **shared infrastructure but parallel surfaces**:

| What's shared | What's still parallel |
|---|---|
| ADR-743 ledger | Two slash commands (`/dev-loops`, `/dream`) |
| Subagent dispatch primitive | Two Codex seed yamls (identical schema, different files) |
| Trust algorithm (extracted) | Two adapter methods (`_sync_dev_loop_automations`, `_sync_dream_automations`) |
| Ledger view translator (ADR-757) | Two status surfaces (`/dev-loops status`, `aug dream status`) |
| `routine-*` naming convention | Two discovery mechanisms (`x-augur-commands` vs `commands/dream.md`) |

The residue is real cognitive overhead: a new contributor learns two systems for one conceptual thing ("recurring AI-orchestrated work"). This ADR is the convergence step that collapses the residue into one mechanism.

## Decision

After the prerequisite gate passes, unify the two surfaces under a single **Routines** mechanism:

1. **One slash command** — `/routines` with verbs (`list`, `status`, `run <id>`, `report <id>`). `/dev-loops` and `/dream` become deprecated aliases for **one release cycle**; then retired (per the same staging discipline as ADR-757's journal retirement).

2. **One declarative discovery** — every routine-providing skill (auto-loops and dream alike) declares an `x-augur-routine:` block in its SKILL.md:

```yaml
x-augur-routine:
  id: testing                    # flat namespace: testing, hardening, dream, ...
  execution: tiered              # tiered | inline-session
  policy: adaptive               # adaptive | oneshot | observability-only
  callable: scripts/orchestrator_entry.py  # or commands/dream.md for inline-session
  loop: testing                  # legacy loop name for backwards compat
```

Dream's `SKILL.md` gains: `x-augur-routine: { id: dream, execution: inline-session, policy: oneshot, callable: commands/dream.md }`.

3. **One Codex projection method** — `_sync_dev_loop_automations` + `_sync_dream_automations` in the Codex adapter collapse into one `_sync_routine_automations` that walks every skill with an `x-augur-routine:` block and emits a Codex automation per declared `client:codex` schedule binding. The current centralized seed yaml (`codex-dev-loop-schedules.yaml`) is dismantled; each skill carries its own `assets/seeds/routine-schedule.yaml` (per Rule #2). Dream's existing `codex-dream-schedules.yaml` is renamed to match the convention.

4. **One status surface** — `/routines status` (and `aug routine status`) reads the ADR-757 `ledger_view.py` translator and shows every routine regardless of execution model. `/dev-loops status` and `aug dream status` become aliases mapping to the unified surface.

5. **Per-routine reports stay routine-owned** — dream keeps writing to `<documents>/reports/dream/`, auto-loops keep writing to `<documents>/reports/<routine-id>/`. Report content is not unified; only the discovery + status + scheduling layers are.

6. **Dream stays at `shared-vault/skills/dream/`** — no directory rename. The `x-augur-routine: { id: dream }` declaration is what unifies it with `routine-codebase`, `routine-vault`, etc. at the registry level. Renaming the directory would force every reference (capability_exposure, sync_agents, MCP tools, CLI) to migrate for purely cosmetic naming consistency. (Open design Q surfaced in spec; recommended: stay at `dream/`.)

After this ADR ships: `/routines list` returns one flat list of every routine (testing, hardening, code-quality, knowledge-enrichment, dream, ...); each entry shows its execution model + policy + last run from the ledger; activating or scheduling any routine goes through the same unified surface regardless of whether it's a fix-it routine or a compounding routine.

## Non-Goals

- **Not rewriting orchestrator internals.** ADR-755's `routine_orchestrator/` is preserved. This ADR adds a routine *registry layer* above it; the runner itself doesn't change.
- **Not changing dream's runtime behavior.** The dream routine prompt, the 9 `dream-*` MCP tools, the report format, the Codex daily-at-04:00 schedule — all preserved exactly. Only the discovery + projection layers change.
- **Not unifying report formats.** Each routine owns its report shape (per-skill concern); only the *index* of where reports live is unified.
- **Not renaming `shared-vault/skills/dream/` to `routine-dream/`.** Directory rename has high cost and zero functional value once `x-augur-routine: { id: dream }` is the registry-level identifier.
- **Not collapsing execution models.** Tiered and inline-session are genuinely different patterns; the registry just declares which one each routine uses. The unification is in *surface*, not in *runtime behavior*.
- **Not deleting `/dev-loops` or `/dream` slash commands in this ADR.** Aliases stay for one release cycle for ergonomic continuity; retirement is a follow-up.
- **Not changing the ADR-743 ledger schema or the ADR-757 `ledger_view.py` translator.** Both are already designed to serve every routine type.

## Consequences

- One mental model for "recurring AI-orchestrated work in Augur." New contributors learn one mechanism.
- `/routines list` becomes the discoverability surface — every routine, every execution model, every schedule, one view.
- Per-client routine projection has one code path instead of two; future client additions (Gemini routines, etc.) don't have to think about "is this a dream-class or auto-loop-class routine?" — every routine projects the same way.
- Skill-local `assets/seeds/routine-schedule.yaml` honors Rule #2 (decentralization) — each routine's schedule lives next to the routine. The centralized `codex-dev-loop-schedules.yaml` retires (mechanical migration).
- Dream's directory stays at `dream/`; the registry-level convergence happens via the `x-augur-routine:` block, not via directory rename.
- One release cycle of `/dev-loops` and `/dream` as documented aliases gives users a soft landing.
- After alias retirement, anyone with personal scripts that invoke `/dev-loops run X` will need to migrate to `/routines run X`. Mitigation: documented in CHANGELOG; the alias period gives a full release for surface bugs.
- Adds the `x-augur-routine` field to every routine-providing skill's SKILL.md — small additive change per skill.

## Alternatives Considered

1. **Stay with two systems forever.** Rejected — fails the original "one system" goal. The cognitive cost of two parallel surfaces compounds with every new contributor and every new routine added in either bucket.

2. **Bundle this convergence into ADR-755/756/757.** Considered and rejected during the prior ADR-write session. Reintroduces the "too many concurrent variables" problem the three-ADR split was designed to avoid. Each of 755/756/757 has independent shippability today; bundling unification into one of them couples its release to dream's production evidence, which 755 (runner rewrite) does not actually need.

3. **Unify before 755/756/757 land.** Rejected — the convergence design depends on having a stable orchestrator (755), a clean skill organization (756), and a single observability substrate (757). Unifying before these settle would absorb their churn into the unification and end up rewriting it.

4. **Rename `shared-vault/skills/dream/` to `routine-dream/` for naming consistency.** Rejected — pure cosmetic change with high migration cost (capability_exposure, sync_agents projections, MCP tool registrations, CLI surface, docs). Registry-level identity via `x-augur-routine: { id: dream }` achieves the conceptual unification without the cost.

5. **Make `/routines run <id>` the only surface and delete `/dev-loops` + `/dream` immediately.** Rejected — too jarring; one-release alias period is cheap insurance.

## Related

- ADR-727 (Background Routines — Unified Discovery and Browse Category — this ADR finishes that ADR's unification at the runtime layer)
- ADR-743 (File-Based Job Ledger — the substrate that already serves both routine types)
- ADR-744 (Dream Cycle — the architectural origin of the inline-session execution model)
- ADR-755 (Auto-Loop Runner Modernization — must land first)
- ADR-756 (Loop-skill consolidation — must land first)
- ADR-757 (Journal retirement — must land first)

---

## Implementation

Implementation completed on 2026-05-16 from the active ADR-758 worktree. The
implementation followed the linked `plan_file`, verified the prerequisite gates,
introduced the unified registry and `/routines` command surface, kept
`/dev-loops` and `/dream` as deprecated transition aliases, and validated both
real routine ledger data and a real dream-cycle alias execution.
