---
name: advisor-architecture
description: "Read-only architecture analysis — four-phase codebase exploration (discovery, tracing, mapping, implementation analysis) producing a decisive blueprint checked against governing ADRs. Usage: /advisor-architecture <feature|path|question> [--blueprint]"
visibility: dev
x-augur-tags:
  - architecture
  - analysis
  - blueprint
x-augur-export-command: false
---

# /advisor-architecture

Explore how a feature or subsystem works and report its architecture; with
`--blueprint`, additionally produce a decisive implementation blueprint for a
proposed change. Strictly read-only — findings and blueprints are advisory;
implementation happens in a separate, user-approved step.

If invoked with `--help`, display this usage and stop — do not execute.

## Usage

- `/advisor-architecture browse progressive render` — explain how a feature works
- `/advisor-architecture src/lib/index/` — map a subsystem
- `/advisor-architecture add per-skill rate limits --blueprint` — design a change

## Workflow

1. **Scope.** Resolve the target feature, path, or question from
   `$ARGUMENTS`. State the working assumption if ambiguous.
2. **Four-phase exploration.** Follow
   `project-brain/capabilities/skills/advisor/references/codebase-exploration.md`:
   discovery (entry points, boundaries), tracing (execution chains), mapping
   (layers, patterns), implementation analysis (algorithms, error handling,
   debt). Use read-only surfaces only: `rg`, file reads, `git log`/`git blame`.
3. **ADR check.** Cross-check observed patterns against governing decisions —
   `docs/generated/adr-index.md` and the ADR files in `docs/adrs/` (CLAUDE.md
   rules 12, 22). Name the ADRs that explain (or contradict) what the code does.
4. **Report.** Deliver the phase outputs with file:line references. Flag
   real debt found along the way as candidates for `TODO_` markers — do not
   edit files; marker placement belongs to the implementing session
   (advisor is read-only).
5. **Blueprint (only with `--blueprint`).** Produce a decisive blueprint per
   `references/blueprint-template.md`: patterns found, single architecture
   decision with rationale, component design, implementation map,
   data flow, build sequence, critical details. Prefer the smallest
   sufficient change; no alternatives menu.

## Boundaries

- Architectural *decisions* still go through ADRs (rule 12) — a blueprint
  proposes; it does not decide.
- Skill quality scoring belongs to `auto-skill-quality`; this command does
  not score skills.
- For multi-step implementation planning with execution intent, prefer the
  plan workflow (rule 20); use this command for understanding and design.
