---
name: advisor
x-augur-type: skill
x-augur-tags:
- architecture
- prompts
- optimization
- vision
- strategy
description: Use when exploring a codebase's architecture to produce a decisive
  implementation blueprint (/advisor-architecture), optimizing a prompt, command,
  or skill description with a baseline and an A/B evaluation plan
  (/advisor-prompt-optimize), or assessing an initiative's alignment and strategic
  drift against the product vision (vision-framework / alignment-scoring /
  drift-detection references).
x-augur-group: augur_core
x-augur-release: mvp
x-augur-license: MIT
---

# advisor

Advisory judgment procedures and methodology references: architecture
exploration and blueprinting, prompt optimization with A/B evaluation
planning, and product-vision alignment/drift assessment. The advisor is
**read-only** — it analyzes, scores, and recommends; it never edits
application code, generates background suggestions, or runs on a schedule.

## What advisor does NOT own

Advisor's domain borders several active skills — duplicated intent is a
defect, so these boundaries are hard:

- **Retrieval evaluation** — the `evals` skill owns the retrieval eval
  harness (capture/replay, P@k / MRR / nDCG scoring). Advisor's A/B framework
  covers prompt/behavior experiments only; measurable retrieval experiments
  are handed to `evals`.
- **Skill quality scoring** — `auto-skill-quality` owns skill quality
  scores, tier audits, and the ADR-741 catalog audit. Advisor does not score
  skills.
- **Usage analytics** — `routine-coverage` owns skill-usage signals and
  over/under-use detection; `knowledge` owns memory/usage analytics surfaces.
  Advisor does not aggregate telemetry.
- **Backlog and debt scanning** — `TODO_` markers, hygiene scans, and the
  routine loops own backlog/debt discovery. Advisor has no backlog store.
- **External repo adaptation** — skill adoption/porting methodology belongs
  to `skillify` and the port-release contract, not advisor.

## Commands

| Command | Purpose |
|---------|---------|
| `/advisor-architecture` | Explore how a feature/subsystem works (discovery → tracing → mapping → analysis) and optionally produce a decisive blueprint for a proposed change |
| `/advisor-prompt-optimize` | Baseline a target prompt, draft variants, and define an A/B evaluation plan |

## References

| Trigger | Load |
|---------|------|
| Exploring an unfamiliar codebase/feature | `references/codebase-exploration.md` |
| Writing an architecture blueprint | `references/blueprint-template.md` |
| Optimizing prompt wording | `references/prompt-optimization.md` |
| Designing a prompt/behavior experiment | `references/ab-testing-framework.md` |
| Drafting or refreshing a vision statement | `references/vision-framework.md` |
| Scoring an initiative against the vision | `references/alignment-scoring.md` |
| Detecting strategic/scope drift | `references/drift-detection.md` |

## Constraints

- **Advisory only** — never modifies source files; recommendations are
  dispatched to the user or an implementing session.
- **No background generators** — no scheduled suggestion machinery, no
  speculative improvement queues (the retired insight-scanner saga, ADR-078).
- **Judgment over scripts** — procedures run inline in the AI client against
  real repo data (git history, ADRs, real prompts); no MCP tools, no scripts.

## Provenance

Selective port of the staged r3 `advisor` draft (r3 manifest license: MIT;
the only Apache-2.0-marked files, Company-in-a-Box-derived agent modules,
were excluded). The draft's script tree (telemetry generators,
self-improvement backlog ingestion, vision-keeper runtime store, bug sync,
eval runners) was excluded wholesale as speculative-generator machinery,
stale pre-ADR-802 layout, or duplication of `evals` / `auto-skill-quality` /
`routine-coverage` / `routine-vault`; see CHANGELOG.
