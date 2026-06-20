# Command Quality Score in Browse — Design

**Date:** 2026-05-24
**Status:** Approved (brainstorming) — ready for implementation plan
**Author:** session (gsannikov)

## Problem

Browse already scores **skills** end-to-end: `skill_scorer.score_all_skills()` →
`browse/index.py` enriches each skill card with `qualityTier` + `qualityScore` →
`BrowseCard` renders a colored tier badge, the detail panel shows tier+score,
`pinOrdering` sorts by it, and the skills view's tag-filter is keyed to
`qualityTier`. So skills are already filterable by score.

**Commands are unscored.** `skill_scorer` only scores skills, so command cards
carry no score, no badge, and no score filter. The user wants every command to
show a health score in Browse and be filterable by it — a single overall health
view at a glance.

## Goal

A blended **command health score** on every command card in Browse, filterable by
score, mirroring the skills experience and reusing the existing card/badge/detail/
filter mechanics (ADR/rule 32: signals ride existing cards — no bespoke panel).

## Decisions (locked during brainstorming)

1. **Single overall health view** — one score per command at a glance.
2. **Score = docs + wiring** — both signals are available for all ~114 commands,
   so scores stay comparable on one scale.
3. **KPI is a side signal, not blended** — only 7 commands have real-run
   command-KPI data; blending it would make those 7 incomparable or require a
   fabricated value for the other ~107. Instead KPI rides the 7 as a separate
   `KPI ✓/✗` chip + optional filter. Honest: KPI shown only where measured.
4. **Reuse existing UI** — the `qualityTier` badge, detail panel, sort, and the
   skills-style tag-filter; commands get the same treatment, no new view mode.

## Architecture

### 1. `src/lib/command_scorer.py` (new; mirrors `skill_scorer.py`)

Pure library module, process-cached (~60s like the skill scorer), no LLM calls.

```
score_command(cmd: CommandInfo) -> {
    "id": str,
    "score": float,        # 0-100
    "tier": str,           # A-F
    "dimensions": {"docs": {...}, "wiring": {...}},
}
score_all_commands() -> {"commands": [ ...score_command... ]}
```

- **docs (60% weight)** — read the command's `.md` at `CommandInfo.path` and score
  the same shape as `skill_scorer._score_instruction`:
  - description ≥20 words (frontmatter `description` / `CommandInfo.description`),
  - a Usage/help section,
  - Examples (heading or fenced ``` block),
  - an argument contract / dispatch table.
- **wiring (40% weight)** — structural health of the command's registration:
  - `command:<id>:` entry exists in `config/system/capability_exposure.yaml`,
  - `classification_status: approved`,
  - non-empty `export_to`,
  - **not** flagged as an unrouted intent or routing collision by the ADR-741
    check-resolvable audit.
- **tier** — map 0-100 → A–F via thresholds shared with / analogous to the skill
  scorer's structural thresholds (exact cutoffs finalized in the plan).
- **KPI overlay** — read the latest `command-KPI` aggregate
  (`command_kpi_runner` / `command_records`) and derive a per-command
  `kpiStatus` ∈ {pass, fail, untested}. Attached separately, never folded into
  `score`.

### 2. Browse enrichment — `browse/index.py`

Add `_populate_command_enrichment()` as a sibling of `_populate_skill_enrichment()`:
- call `score_all_commands()`,
- for each command item attach `qualityTier`, `qualityScore`, `kpiStatus`, and a
  compact `docs`/`wiring` breakdown to the served metadata.
- Hook into the existing command-category enrichment path so the served
  `commands` BrowseItems carry the fields `transforms.ts` already maps.

### 3. Dashboard surfaces (reuse + small additions)

- **Card badge** — `BrowseCard` already renders the `qualityTier` badge; it works
  for commands automatically once metadata is present. Add a small `KPI ✓/✗` chip
  rendered only when `kpiStatus` ∈ {pass, fail}.
- **Detail panel** — `BrowseDetailPanel` already shows tier+score; add docs /
  wiring / KPI breakdown rows.
- **Filter** — add `case "commands": return "qualityTier"` in `useBrowseState`
  so the commands view gets the same score tag-filter the skills view has. Add an
  optional "KPI: passing" chip filter.

## Data flow

```
command .md + capability_exposure + check-resolvable + command-KPI aggregate
   → command_scorer.score_all_commands()        (src/lib, cached)
   → browse/index.py _populate_command_enrichment()  (attach metadata)
   → MCP browse serve → transforms.ts (maps qualityTier/qualityScore)
   → BrowseCard badge + KPI chip / BrowseDetailPanel breakdown / tag-filter
```

## Units & boundaries

- `command_scorer` — does: compute per-command health from files+config; depends
  on: `command_discovery`, `capability_exposure`, check-resolvable output,
  command-KPI records. Testable in isolation with fixtures.
- `_populate_command_enrichment` — does: map scores onto served command items;
  depends on: `command_scorer`. Thin.
- Dashboard components — unchanged contracts; consume `qualityTier`/`qualityScore`/
  `kpiStatus` metadata already (skills path), plus the new KPI chip.

## Error handling

- Scorer never raises into the Browse path: any per-command failure logs WARN and
  yields a neutral/`untested` entry (a broken scorer must not empty the commands
  view). Mirrors the skill enrichment's `try/except pass`.
- Missing capability_exposure entry → wiring score reflects the gap (low), not a
  crash.
- No command-KPI aggregate present → all `kpiStatus = untested` (no chip).

## Testing

- Unit tests for `command_scorer`: docs scoring (rich vs thin .md), wiring signals
  (entry present/approved/export, unrouted penalty), tier mapping, KPI overlay
  (pass/fail/untested). Managed pytest wrapper.
- Real-data run: `score_all_commands()` over the real catalog → sane tier
  distribution (not all-zero, not all-A).
- Browser verification (rules 28/31): commands Browse view renders tier badges +
  KPI chips, the score tag-filter works, detail panel shows the breakdown.

## Non-goals (YAGNI)

- No new Browse view/tab/panel.
- No blending KPI into the numeric score.
- No scoring of non-command surfaces beyond what already exists for skills.
- No change to the skills scoring path (already works).
