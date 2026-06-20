---
status: Implemented
date: 2026-03-23
deciders:
- Gur Sannikov
related:
- ADR-447
- ADR-470
superseded_by: null
supersedes:
- ADR-447
- ADR-470
hub: adaptive
tags:
- skill-quality
- scoring
- mcp-tool
- evals
- behavioral-gates
---

# ADR-492: Type-Aware Skill Scoring with Behavioral Tier Gates

## Context

ADR-447 and ADR-470 both defined a "unified skill scorer" with 4 dimensions and a single flat weight set (instruction 30%, product 40%, UI 15%, wiring 15%). The tier system was 4-level (A/B/C/D/F) with fixed numeric thresholds and no behavioral signal.

Two problems emerged in practice:

1. **Type blindness** — A flat weight set penalizes skills unfairly. A `command` skill has no dashboard page, so a 15% UI weight will always drag its score down. A `library-reference` skill has no MCP tools, so a 40% product weight is misleading. Scores were noisy and not comparable across types.

2. **No behavioral signal** — A score of 75 on a skill that has never been tested in practice is not the same as a score of 75 on a skill with a verified 90% pass rate. The old tier system had no way to express this distinction, so the "A" tier was essentially a structural estimate.

ADR-470 also proposed configurable weights via vault YAML, but this has not been implemented. Thresholds are currently hardcoded; vault-based configuration remains a future enhancement.

## Decision

Replace the single-weight scorer with a **type-aware rubric system** and add a **two-phase tier computation** that gates the top tiers behind behavioral evidence.

### 1. Type-Aware Rubrics (RUBRICS dict)

Each skill type gets its own weight vector. The type is read from `x-augur-type` in SKILL.md frontmatter. For skills of type `domain`, scope is auto-detected: `domain-high` if the skill declares 8+ MCP tools or 3+ dashboard pages, `domain-low` otherwise.

| Type | Instruction | Product | UI | Wiring |
|------|------------|---------|-----|--------|
| domain (high-scope) | 25% | 35% | 20% | 20% |
| domain (low-scope) | 35% | 40% | 5% | 20% |
| command | 50% | 25% | 0% | 25% |
| autoloop | 20% | 30% | 5% | 45% |
| library-reference | 60% | 20% | 0% | 20% |
| runbook | 55% | 25% | 0% | 20% |
| template | 40% | 35% | 10% | 15% |
| meta | 50% | 30% | 0% | 20% |
| integration | 35% | 35% | 10% | 20% |

### 2. Two-Phase Tier Computation

Tier assignment is a two-phase process: structural baseline first, behavioral gate second.

**Phase 1 — Structural baseline** (based on weighted score across 4 dimensions):

- Score >= 55 → structural ceiling of B
- Score >= 35 → C
- Score >= 15 → D
- Score < 15 → F

Skills with a structural score below 55 stay at C/D/F regardless of behavioral results. Behavioral data cannot compensate for a poor structural foundation.

**Phase 2 — Behavioral gate** (applied only when structural score >= 55):

| Tier | Structural | Behavioral |
|------|-----------|-----------|
| S | >= 75 | `confidence == "verified"`, `pass_rate >= 80%` |
| A | >= 65 | evals exist, `pass_rate >= 60%` (seed or verified) |
| B+ | >= 55 | evals exist, `pass_rate < 60%` |
| B | >= 55 | no evals (structural ceiling) |
| C | >= 35 | — |
| D | >= 15 | — |
| F | < 15 | — |

S is the only tier that requires `confidence == "verified"`. A can be reached with seed evals.

### 3. Behavioral Source of Truth

`evals/benchmark.json` is the source of truth for pass rate. Its structure is:

```json
{
  "metadata": { "timestamp": "..." },
  "run_summary": {
    "with_skill": {
      "pass_rate": { "mean": 0.85 }
    }
  },
  "runs": [...]
}
```

`evals/evals.json` provides the confidence level. If all entries in the `evals` array carry `"confidence": "verified"`, the behavioral result is `"verified"`; otherwise it is `"seed"`. This distinction controls whether tier S is reachable.

### 4. rank.json Sidecar

After every `scan()` run, `skill_quality_ops.scan()` writes a `rank.json` sidecar to `skills/{skill}/evals/rank.json`. This file is the stable computed artifact:

```json
{
  "tier": "A",
  "score": 68.4,
  "rubric": "domain-low",
  "structural": {
    "score": 68.4,
    "dimensions": { "instruction": {...}, "product": {...}, "ui": {...}, "wiring": {...} }
  },
  "behavioral": {
    "confidence": "seed",
    "pass_rate": 0.72,
    "eval_count": 14,
    "last_run": "2026-03-22T14:00:00Z"
  },
  "computed_at": "2026-03-23T09:00:00Z"
}
```

`rank.json` is written via `write_stable_json(path, data, volatile_keys=["computed_at"])`. The `volatile_keys` parameter means `computed_at` is excluded from the diff comparison, preventing unnecessary git churn when nothing substantive changed.

### 5. Seed Eval Generation

At difficulty d2+, `fix()` in `skill_quality_ops.py` generates seed evals for skills that have no `evals/evals.json`. Generation uses per-type strategies (derived from `x-augur-type`) and produces entries in the skill-creator schema:

```json
{
  "skill_name": "my-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "...",
      "expected": "...",
      "expectations": ["..."],
      "confidence": "seed"
    }
  ]
}
```

Seed evals are written to `skills/{skill}/evals/evals.json`. They allow a skill to reach tier A (with pass_rate >= 60%) but not tier S. Tier S requires `confidence == "verified"` entries produced by running the skill-creator benchmark tool.

### 6. Feedback Hook

`skills/auto-skill-quality/scripts/feedback_hook.py` implements a PostToolUse hook. After a skill executes, it has a 20% chance to prompt the user for thumbs up/down feedback, subject to a 7-day cooldown. Feedback is written to `skills/{skill}/evals/feedback.json`:

```json
{
  "skill_name": "my-skill",
  "entries": [
    {
      "timestamp": "2026-03-23T09:00:00Z",
      "result": "positive",
      "note": "worked as expected",
      "prompt_summary": "..."
    }
  ]
}
```

The feedback file is capped at 50 entries (oldest entries are dropped). The hook also nudges users toward running `/skill-creator eval {skill}` for full verified benchmarking. `feedback.json` is informational — it does not feed directly into tier computation in the current implementation.

The feedback prompt is suppressed when:
- No `evals.json` exists yet (a prompt would be premature)
- A feedback entry was written within the last 7 days

### 7. Import Metadata

Skills imported from external sources (skill store, community packs) are stamped with import provenance via `stamp_import_metadata()` in `src/lib/frontmatter_utils.py`. This writes four fields to SKILL.md frontmatter:

- `x-augur-source` — human-readable source name
- `x-augur-source-url` — canonical URL of the source
- `x-augur-source-version` — version string at time of import
- `x-augur-imported-at` — ISO 8601 timestamp of import

These fields do not affect scoring but are surfaced in the browse page and skill health views.

### 8. Hardcoded Thresholds

Tier thresholds and rubric weights are currently hardcoded in `src/lib/skill_scorer.py`. Configurable thresholds via vault YAML (proposed in ADR-470) is a future enhancement — the infrastructure for loading from `~/Vault/Augur/config/skill-score-weights.yaml` exists (`_load_weights()`) but the rubric and behavioral thresholds are not yet exposed through that mechanism.

## Consequences

### Positive

- Scores are now comparable within a type — a `command` skill at tier A means something specific about command skills, not about how many dashboard pages it has
- Tier S is a meaningful signal: it requires both structural quality and empirical evidence
- `rank.json` gives every consumer (dashboard, loops, CLI) a single pre-computed artifact with no additional filesystem walks
- Seed eval generation at d2+ bootstraps the behavioral pipeline for new skills automatically

### Negative

- Introducing type-awareness means a skill's score can change when its `x-augur-type` is corrected — teams must set `x-augur-type` accurately
- `domain-high` vs `domain-low` auto-detection (threshold: 8 tools or 3 pages) is a heuristic — edge cases exist
- Tier S is practically hard to reach today; most skills have no verified evals

### Neutral

- The `_load_weights()` function in `src/lib/skill_scorer.py` still reads vault YAML for instruction/product/ui/wiring weights — user customization of those weights continues to work
- `feedback.json` entries are collected but not yet aggregated into tier computation — this is intentional (too noisy for direct scoring)

## Alternatives Considered

### Alternative 1: Configurable Rubrics via Vault YAML

Allow users to define per-type rubrics in `skill-score-weights.yaml`. Rejected for now because the type taxonomy is still stabilizing. Hardcoded rubrics are easier to reason about and change atomically via ADR.

### Alternative 2: Single Behavioral Tier Gate (pass/fail)

Instead of S/A/B+ gradations, use a single binary gate: behavioral evidence promotes to A+, absence stays at B. Rejected because the S tier communicates verified excellence to the user, which is qualitatively different from seed-eval "probably good."

### Alternative 3: Keep ADR-447 / ADR-470 Flat Weights, Add Behavioral Override

Retain the single weight set but add behavioral override on top. Rejected because type blindness was the root cause — behavioral gates on top of an unfair structural score would not fix the comparability problem.

## References

- `src/lib/skill_scorer.py` — RUBRICS, `_resolve_rubric()`, `_read_behavioral()`, `_compute_tier()`
- `skills/auto-skill-quality/scripts/skill_quality_ops.py` — `scan()` rank.json writer, `fix()` seed eval generation
- `skills/auto-skill-quality/scripts/feedback_hook.py` — PostToolUse feedback
- `src/lib/frontmatter_utils.py` — `stamp_import_metadata()`
- `skills/*/evals/` — `evals.json`, `benchmark.json`, `feedback.json`, `rank.json`

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - skill-score MCP tool: now returns rubric field and behavioral breakdown
    - tier values expanded from A/B/C/D/F to S/A/B+/B/C/D/F
  patterns_deprecated:
    - flat single-weight scoring (ADR-447, ADR-470)
    - configurable weights via vault YAML for rubrics (not yet implemented)
  files_affected:
    - src/lib/skill_scorer.py
    - skills/auto-skill-quality/scripts/skill_quality_ops.py
    - skills/auto-skill-quality/scripts/feedback_hook.py
    - src/lib/frontmatter_utils.py
    - skills/*/evals/rank.json
```
