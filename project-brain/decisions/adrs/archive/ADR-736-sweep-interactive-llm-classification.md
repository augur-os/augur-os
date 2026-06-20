---
status: Implemented
date: 2026-05-12
deciders:
  - gsannikov
related:
  - ADR-732
hub: adaptive
tags:
  - hygiene
  - retention
  - artifacts
  - interactive
  - q-and-a
  - llm-classifier
  - mcp
  - slash-command
superseded_by: null
spec_file: 2026-05-12-sweep-interactive-llm-design.md
plan_file: 2026-05-12-sweep-interactive-llm.md
---

# ADR-736: Sweep Interactive LLM Classification with Tiered Q&A and Cached Group Decisions

> **ADR-736 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Extend the `/sweep-stores` slash command (delivered in ADR-732) with a three-tier confidence rubric — Tier 1 autonomous, Tier 2 interactive Q&A via `AskUserQuestion`, Tier 3 content-inspection-then-Q&A — and persist the user's group/canonical decisions in a new `known_groups[]` section of `.augur-lifecycle.yaml` so subsequent sweeps short-circuit the question path. The change stays vendor-neutral (the agent-in-session remains the classifier), introduces no new MCP tools, and extends `hygiene-scan`/`hygiene-apply` with additive schema only.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-12-sweep-interactive-llm-design.md`](../superpowers/specs/2026-05-12-sweep-interactive-llm-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-12-sweep-interactive-llm.md`](../superpowers/plans/2026-05-12-sweep-interactive-llm.md) — 12 tasks (T1 `KnownGroup` dataclass + parser, T2 `known_groups.py` matcher with 3 canonical_strategy branches, T3 `lifecycle_writer.py` atomic temp-rename writer with name-collision refusal, T4 `hygiene-scan` emits `known_groups` in output, T5 `hygiene-apply` accepts optional `lifecycle_updates[]` and writes YAML before moves, T6 rewrite `sweep-rubric.md` with tier rubric, T7 update `sweep-stores.md` workflow with Q&A protocol + 4-question batch cap, T8 update `lifecycle_schema.yaml`, T9 six new fixtures, T10 e2e cache round-trip, T11 SKILL.md bump + lint gate, T12 manual `/sweep-stores` ritual against real `Au-docs/venture-augur/IntelSubmit/`). TDD throughout; agent-side reasoning only (no LLM SDK imports anywhere).

## Status notes

Implemented 2026-05-12. The loop-hygiene implementation now includes the `KnownGroup` reader model, cached-group matcher, atomic lifecycle writer, additive `hygiene-scan`/`hygiene-apply` schema wiring, tiered sweep rubric, updated `/sweep-stores` workflow, lifecycle schema docs, fixtures, and cached known-group E2E coverage.

The destructive real-data `/sweep-stores ... --apply` ritual in the plan remains a user-driven operational verification step; the implementation gate verified the cache round-trip with the loop-hygiene E2E fixture instead.

Driver: the 2026-05-12 sweep of `Au-docs/venture-augur/` (47 moves applied to `websites/`) exposed five categories of staleness the MVP-v2 rubric of ADR-732 cannot detect: renamed iterations, variant suffixes, mixed version schemes, format siblings where one is abandoned, and conceptual supersession. Today the user has to disambiguate these verbally every sweep. This ADR shifts the work from "user disambiguates every run" to "user answers once, cache short-circuits next run."

Load-bearing claims:

- **Pure agent-side rubric extension.** Tier classification + content inspection (via Read tool on text files ≤ 10 per sweep) + question batching (via `AskUserQuestion`, max 4 per sweep) all live in `commands/sweep-stores.md` + `references/sweep-rubric.md`. Zero new MCP tools, zero LLM SDK imports. Same vendor-neutral stance as ADR-732.
- **Single new persistence surface.** `.augur-lifecycle.yaml` gains one new top-level key: `known_groups[]`. Three canonical strategies (`highest_version`, `explicit`, `not_a_group`) are read into a frozen `KnownGroup` dataclass; appends are atomic via temp-rename in a new `lifecycle_writer.py` module. The writer refuses name-collisions; the reader emits warnings on malformed entries.
- **YAML write happens before moves.** `hygiene-apply` writes `lifecycle_updates[]` to per-folder `.augur-lifecycle.yaml` first, then performs the file moves. Cached decisions persist independently of whether physical archival later succeeds — a re-run converges to the same proposal without re-asking.
- **Two MCP contracts gain additive fields only.** `hygiene-scan` output emits `lifecycle_config.known_groups[]`. `hygiene-apply` input accepts optional `lifecycle_updates[]` and returns per-update results with `lifecycle_collision` / `lifecycle_malformed` / `folder_missing` / `outside_store` / `malformed_update` refusal categories. Callers that omit the new field behave identically to today.

Distinction from ADR-732: that ADR shipped the deterministic sweep primitives and the agent-as-classifier model with a flat name-pattern rubric. This ADR replaces the rubric with a tier-based one and adds the cache + Q&A layers. Phase 5b of ADR-732's roadmap (unattended LLM classification via `llm.yaml`) remains deferred — this enhancement still requires an interactive session for any Tier 2/3 ambiguity.

## Related

- ADR-732 — base loop-hygiene skill that this ADR extends.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "hygiene-scan output schema: lifecycle_config.known_groups[] (additive)"
    - "hygiene-apply input schema: lifecycle_updates[] (additive, optional)"
    - "hygiene-apply output schema: lifecycle_updates[] (additive)"
  patterns_deprecated:
    - "Flat name-pattern rubric in references/sweep-rubric.md — replaced by three-tier rubric"
  files_affected:
    - shared-vault/skills/loop-hygiene/scripts/lifecycle_config.py
    - shared-vault/skills/loop-hygiene/scripts/lifecycle_writer.py
    - shared-vault/skills/loop-hygiene/scripts/known_groups.py
    - shared-vault/skills/loop-hygiene/scripts/hygiene_scan.py
    - shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py
    - shared-vault/skills/loop-hygiene/references/sweep-rubric.md
    - shared-vault/skills/loop-hygiene/commands/sweep-stores.md
    - shared-vault/skills/loop-hygiene/augur/data/lifecycle_schema.yaml
    - shared-vault/skills/loop-hygiene/SKILL.md
```
