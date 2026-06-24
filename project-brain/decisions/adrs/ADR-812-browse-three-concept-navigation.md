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

## Amendment (2026-06-23): Loops rename + full loop anatomy

- The `background-routines` category is renamed `loops` (label "Routines" → "Loops").
  Old `?category=background-routines` and `scheduled-executions` URLs alias to `loops`.
- The `loop` ("LOOP ENGINEERING") journey group now bundles the full loop anatomy:
  Loops · Agents · Skills · Integrations · MCP Tools · MCP Servers. `skills` moves
  out of `prompt`, `mcp-tools` out of `capabilities`, `mcp-servers` out of
  `diagnostics` (one-group-per-tab model). This consciously overrides the original
  "skills = prompt engineering" and "MCP = dev capabilities/diagnostics" placement:
  in loop-engineering, skills and connectors are loop components, and surfacing them
  together teaches the anatomy. The "How it runs without you" subtitle is unchanged.
- See spec `docs/superpowers/specs/2026-06-23-browse-loops-rename-regroup-design.md`.
