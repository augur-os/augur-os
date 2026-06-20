---
status: Implemented
date: 2026-06-11
hub: workspace
tags:
  - browse
  - navigation
  - category-refactor
  - prompt-engineering
  - context-engineering
  - loop-engineering
related:
  - ADR-802
  - ADR-805
  - ADR-809
---

# ADR-812: Browse navigation groups around three AI-engineering concepts

## Context

Browse grouped categories by content lifecycle (incoming/knowledge/reuse/system/state).
The category-action refactor spec (2026-06-09, amended 2026-06-11) replaces that rubric
with the three AI-engineering concepts — prompt engineering, context engineering, loop
engineering (prompt → context → loop progression,
https://www.louisbouchard.ai/loop-engineering/). Augur has first-class artifacts for all
three; navigation should teach that model.

## Decision

- `journey_group` values are `context` / `prompt` / `loop` (+ dev `capabilities` /
  `diagnostics` / `reference`), labeled "Context Engineering" / "Prompt Engineering" /
  "Loop Engineering" with one-line subtitles (what the AI knows / how you instruct it /
  how it runs without you).
- Prompts becomes a real Browse category (scanner-backed, replacing the retired
  notes-filter redirect). Commands, background-routines (label "Routines"), and
  agent-profiles (label "Agents") promote out of the dev tier into the concept groups.
- Category ids never change; labels/groups only — no deep-link migration.
- Group headers are navigation chrome only (rule 32): every tab renders the same
  BrowseItem card grid; no bespoke concept landing views.

## Consequences

- 11 user-facing tabs in 3 concept groups; dev tier shrinks to 8 categories in 3 groups
  (amends the dev-tier-collapse membership).
- Workflows and Extensions ride the Loop Engineering group transitionally until their
  spec workstreams (ADR-805 fold; deletion) land; Profile and Drafts likewise ride the
  Context Engineering "More" tier until their fold/removal workstreams land.

Relates to: ADR-802 (two surfaces), ADR-805 (workflows fold), the 2026-06-09 category
refactor spec §3/§3.1.
