---
name: auto-skill-quality
x-augur-type: autoloop
x-augur-group: augur_autoloops
x-augur-release: mvp
x-augur-license: MIT
description: Adaptive loop that improves skill quality scores toward tier A across all 4 dimensions (instruction, product, UI, wiring) with user-journey awareness. Generates seed data, rewrites descriptions, scaffolds product files, and fixes wiring — with git revert on build failure or score regression. Also runs the ADR-741 check-resolvable catalog audit that detects unrouted intents, routing collisions, orphaned skills, and stale capability entries. Use this when skills are scoring below tier A and need automated quality improvement.
x-augur-tags: []
x-augur-callable: project-brain/capabilities/skills/auto-skill-quality/scripts/skill_quality_ops.py
x-augur-mcp-tools:
- scan-skill-structure
- skill-resolvable-report
x-augur-loop:
  id: skill-quality
  skill: auto-skill-quality
  automation:
    trigger: nightly
    runner: auto
    discover: ../daemon/scripts/routine_orchestrator/orchestrator.py
  loop_name: skill-quality
  memory:
    trust: adaptive
x-augur-commands:
- id: skillify
  type: workflow
  visibility: dev
  description: Convert an incident, recurring bug, or persistent gap into a durable Augur skill via a 10-step canonical workflow (ADR-745).
  callable: commands/skillify.md
  protocol: guide
x-augur-config:
  commands:
  - id: auto-seed-data
    type: workflow
    visibility: auto
    description: Seed empty skill data directories from packaged templates and seed manifests.
    callable: scripts/seed_data_ops.py
    protocol: scan-fix
  - id: auto-skill-migrate
    type: workflow
    visibility: auto
    description: Audit skill directory structure and repair banned or deprecated paths.
    callable: scripts/skill_migrate_ops.py
    protocol: scan-fix
  - id: auto-skill-structure
    type: workflow
    visibility: auto
    description: Scan skill directories for structure violations and expose the structure MCP diagnostic.
    callable: scripts/scan_structure.py
    protocol: scan-fix
x-augur-evolution:
  last_updated: 2026-04-01 21:53:24.475754+00:00
  improvements_applied: 1
---













<!-- ADR-102 Evolution: 2026-04-01T21:53:24.475754+00:00 - fix_error_pattern: Self-repair needed for auto-skill-quality -->



# auto-skill-quality

Nightly adaptive loop that scores all skills via the unified scorer and aggressively
improves them toward tier A. Operates across all 4 scoring dimensions with user-journey
awareness — every fix considers what problem the skill solves and how the user consumes
the data on the dashboard.

It also owns the absorbed hardening workflows that used to live in separate shells:

- [commands/auto-seed-data.md](commands/auto-seed-data.md)
- [commands/auto-skill-migrate.md](commands/auto-skill-migrate.md)
- [commands/auto-skill-structure.md](commands/auto-skill-structure.md)
- [commands/skillify.md](commands/skillify.md) — bug-to-skill creation workflow (ADR-745)

## Flags

| Flag | Description |
|------|-------------|
| `--upgrade N` | Force d3+ difficulty and target the N worst-scoring skills. Pass via `ctx.config.upgrade_n`. Overrides `max_skills_per_cycle`. |

## Difficulty Levels

- **d0**: Scan only — report tier distribution, worst skills, user journey gaps
- **d1**: Fix instruction dimension — rewrite descriptions, expand bodies, add examples
- **d2**: Fix instruction + product — create dirs, generate seeds, scaffold actions
- **d3**: Fix instruction + product + UI — promote page states, add page contributions; LLM escalation when file fixes plateau
- **d4**: Fix all dimensions including wiring — fix toolName refs, remove fs bypasses; LLM escalation when file fixes plateau

## Type-Aware Scoring (ADR-463)

When `x-augur-type` is present, apply type-specific scoring criteria in addition to the base 4-dimension scoring:

| Type | Extra Scoring Criteria |
|------|----------------------|
| `library-reference` | Gotchas section depth (count + quality), reference doc count in `references/` |
| `autoloop` | ops_protocol compliance (scan/fix functions), difficulty levels present (d0-d2 minimum) |
| `domain` | Dashboard page completeness (page.tsx exists, blocks defined), MCP tool coverage (tools listed vs implemented) |
| `command` | Usage docs completeness (flags, examples), clear arguments/options section |
| `runbook` | Step-by-step procedure present, prerequisites listed |
| `template` | Example output shown, customization points documented |
| `meta` | Cross-references to related skills, scope description |

Type-specific scores are weighted at 20% of the instruction dimension. A skill with correct type-specific content scores higher than one without, even if base dimensions are equal.

## LLM Escalation (ADR-446)

At d3+, when file-level fixes cannot reach tier A (plateau), `fix()` calls `llm_fix()`
internally and emits an `llm_escalation` action. The engine (`engine_fix_phase.py`)
detects this sentinel and dispatches the pre-built prompt via CLI subprocess with the
ADR-444 safety harness (budget limit, timeout, build verify, git revert on failure).

Use `--upgrade N` to force this path for the N worst-scoring skills without waiting for
the engine to raise difficulty organically.

## Safety

- Every fix cycle creates a git commit
- Runs `npm run build` after each skill fix
- If build fails or score regresses, `git revert HEAD` automatically
- Respects `dry_run` flag (scan only, no changes)

## User Journey Awareness

Before fixing any skill, the loop reads:
1. SKILL.md body — what problem does this solve?
2. Hub context — what's the user persona?
3. Page components — what data does the page display?
4. Data directory — what files exist? What's missing?

## Eval Framework

### Two-Phase Scoring

Skills are scored in two phases. Phase 1 always runs; Phase 2 upgrades the tier if behavioral evals exist.

**Phase 1 — Structural** (produces `evals/rank.json`):
Scores 4 dimensions (instruction, product, UI, wiring) on 0-100, weighted by rubric type based on `x-augur-type`. Composite score maps to base tier.

**Phase 2 — Behavioral** (optional, upgrades B to B+/A/S):
Requires `evals/evals.json` (test cases) + `evals/benchmark.json` (run results). **B is the ceiling without evals.**

### Tier Thresholds

| Tier | Requirement |
|------|-------------|
| **S** | structural >= 75, pass_rate >= 0.80, confidence = "verified" |
| **A** | structural >= 65, pass_rate >= 0.60 |
| **B+** | eval_count > 0 (low pass_rate or unverified) |
| **B** | structural >= 55 (capped here without evals) |
| **C** | structural >= 35 |
| **D** | structural >= 15 |
| **F** | structural < 15 |

### Rubric Weights (by skill type)

| Type | Instruction | Product | UI | Wiring |
|------|------------|---------|-----|--------|
| `command` | 50% | 25% | 0% | 25% |
| `autoloop` | 20% | 30% | 5% | 45% |
| `library-reference` | 60% | 20% | 0% | 20% |
| `domain-high` (8+ tools or 3+ pages) | 25% | 35% | 20% | 20% |
| `domain-low` | 35% | 40% | 5% | 20% |
| default | 30% | 40% | 15% | 15% |

### Eval Files (per skill)

Each skill stores eval artifacts in `evals/`:

| File | Written by | Contents |
|------|-----------|----------|
| `rank.json` | `scan()` on every cycle | Structural + behavioral scores, tier, rubric type, dimension breakdown |
| `evals.json` | `fix()` at d2+ or advisor evaluation scripts | Test cases with prompts and expected behavior |
| `benchmark.json` | advisor evaluation scripts | Full run results with pass_rate and metadata |

### rank.json Structure

```json
{
  "tier": "B",
  "score": 57.5,
  "rubric": "command",
  "structural": {
    "score": 57.5,
    "dimensions": {
      "instruction": {"score": 80, "weight": 0.5, "weighted": 40.0, "signals": {...}},
      "product": {"score": 45, "weight": 0.25, "weighted": 11.25, "signals": {...}},
      "ui": {"score": 0, "weight": 0.0, "weighted": 0.0, "signals": {...}},
      "wiring": {"score": 25, "weight": 0.25, "weighted": 6.25, "signals": {...}}
    }
  },
  "behavioral": null,
  "computed_at": "2026-03-23T20:31:55Z"
}
```

### Confidence Levels

| Level | Source | Max Tier |
|-------|--------|----------|
| `"seed"` | Auto-generated by d2+ fix cycle | A |
| `"verified"` | Manually tested via advisor evaluation scripts | S |

### How Evals Are Triggered

| Trigger | When | What Happens |
|---------|------|--------------|
| **Nightly loop** | 3 AM via daemon | `scan()` scores all skills, writes `rank.json`; `fix()` at d2+ generates seed `evals.json` if missing |
| **Post-fix seed gen** | After product fixes at d2+ | `generate_seed_evals()` bootstraps `evals.json` with `confidence: "seed"` |
| **Manual advisor eval** | User-triggered | Full eval run, writes `benchmark.json` with pass_rate results |

### Dimension Signals

**Instruction** (0-100): description word count (0-25pts) + body line count (0-30pts) + section count (0-20pts) + richness signals (25pts: examples, references, workflow, checklist)

**Product** (0-100): binary signals — data_dir (+20), mcp_tools (+25), api_routes (+20), actions (+15), scripts (+10), references (+10)

**UI** (0-100): page_count x 5 + mature_pages x 40 + custom_pages x 15 + state_quality x 15

**Wiring** (0-100): binary signals — api_route (+30), no_fs_bypasses (+25), mcp_tool (+25), no_fallback_masking (+20)

## Usage

Invoked automatically by the adaptive loop engine, or manually:

```
/a-loops run skill-quality              # Run one cycle at current difficulty
/a-loops run skill-quality --upgrade 5  # Force-improve the 5 worst skills
```

Via Python CLI:

```bash
python project-brain/capabilities/skills/auto-skill-quality/scripts/skill_quality_ops.py
```

## Examples

- `/a-loops run skill-quality` — run one scoring + fix cycle
- `/a-loops run skill-quality --upgrade 5` — force d3+ on 5 worst skills
- `/a-loops pending` — check for pending skill-quality findings
- Behavioral eval runners must resolve through the owning shared/private skill root; there is no repo-root `skills/` fallback.

## Integration

- **Depends on**: `skill-standards` loop (structural hygiene runs first)
- **Includes**: seed-data, skill-migrate, and skill-structure hardening workflows
- **Structure MCP tool**: `scan-skill-structure` (registered in `scripts/mcp/__init__.py`)
- **Eval runner**: owning shared/private skill evaluation script
- **Cache**: 60s TTL in-memory, invalidated on config mtime change
  - The legacy `skill-score` MCP tool was retired in Track 3a PR 2;
    structural quality is owned by the `scan-skill-structure` tool.

## Additional resources
- [references/.gitkeep](references/.gitkeep)
- [assets/seeds/example-auto-skill-quality.yaml](assets/seeds/example-auto-skill-quality.yaml)
- [evals/rank.json](evals/rank.json)


### Known Issue (ADR-102)

**Pattern:** self-repair plan from skill-quality--auto-skill-quality.json; stagnation_streak=3; module=project-brain/capabilities/skills/auto-skill-quality/scripts/skill_quality_ops.py; fingerprints=4503ab30e4b1b218, 4d70b4fb64966898, 5658bf0eb879d96c, 6bd280b71ee43484, a8bae82af48840ab

**Resolution:** inspect recurring actionable fingerprints for stale heuristics
