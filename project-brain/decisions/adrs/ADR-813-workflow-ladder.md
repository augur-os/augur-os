---
status: Accepted
date: 2026-06-11
deciders:
  - gsannikov
related:
  - ADR-758
  - ADR-805
  - ADR-806
  - ADR-812
hub: workspace
tags:
  - workflows
  - commands
  - skills
  - routines
  - loop-engineering
superseded_by: null
spec_file: 2026-06-09-augur-category-action-refactor-design.md
plan_file: 2026-06-11-skills-as-the-heart.md
---

# ADR-813: Workflows are sized artifacts on a ladder, never their own taxonomy

## Decision summary

A workflow is a multi-step AI-executed procedure expressed as an existing artifact at the
right size — command, skill, or routine declaration — with one source of truth per
workflow and no separate "workflow" artifact type, scanner, or Browse category.

## Context

Before the category-action refactor, "workflow" existed as five half-wired
representations: `references/workflow*.md` docs, `demos/demo_*.md` runbooks, the
`index_workflows()` Browse scanner and tab, `actions/*.md` entries, and `workflow:*`
capability records. Workstream 2 retired the scanner and tab (spec §3, Model A), which
raised the open question this ADR answers: what *is* the canonical way to implement and
expose a workflow?

Rule 19 already fixes the execution model: agents own judgment and orchestration, MCP
tools own atomic operations, docs/commands own policy, daemons only schedule. The live
proof of the target pattern is `desktop-ingest` (file-manager-augur): one command
callable (`commands/desktop-ingest.md`), one routine registration pointing at it, one
Commands-tab card.

## Decision — the ladder

| Size | Artifact | Criterion | Exposure |
|---|---|---|---|
| Small | **Command** — `{skill}/commands/<name>.md` | A runnable procedure belonging to an existing skill | Slash command + Commands tab card |
| Large | **Skill** — its own `SKILL.md` | The procedure carries its own knowledge, references, tools, or tests — it is a capability (ADR-805 Model A) | Skills tab card |
| Scheduled | **Routine declaration** (ADR-758 registry / `augur/actions.yaml` schedule) pointing at either of the above | The same procedure should also run unattended | Routines tab card |

- **Graduation, not duplication:** a workflow starts as a command; when it accumulates
  references/tooling it graduates to its own `SKILL.md`. The routine declaration is
  orthogonal — it schedules an existing callable, never duplicates its content.
- **One source of truth:** the procedure body lives in exactly one file. A parallel
  `references/workflow-*.md` describing the same procedure is residue — fold it into the
  command/skill body.
- **No workflow taxonomy:** no `workflow` artifact type, no dedicated scanner, no Browse
  category. Exposure rides the existing Commands / Skills / Routines surfaces (rule 32).
- **Demo runbooks are not workflows:** `demos/demo_*.md` is presentation collateral owned
  by its skill; it surfaces (if at all) on the owning skill's card, never as runnable
  workflow entries.

## Consequences

- The Routines Browse tab must index **user-declared routines** from the ADR-758 registry
  (e.g. `desktop-ingest`) alongside system/CI/launchd automation, so it fully answers
  "what runs without me" (follow-up fix tracked with this ADR).
- Staged draft workflows (`drafts/staging/**/references/workflow-*.md` in the private
  vault: daily-briefing, email-triage, advisor, validator, venture ×3, interview-prep)
  are triaged up the ladder when activated — most are command-sized; capability-sized
  ones become skills.
- `references/workflow-desktop-ingest.md` is residue per this ADR — its content belongs
  in the `desktop-ingest` command body.

## Status notes

Accepted 2026-06-11 — model ratified by the user in-session after workstream 2 retired
the Workflows category; codifies the answer to "how do I implement and expose a
workflow now."
