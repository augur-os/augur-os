---
status: Implemented
date: 2026-05-13
deciders:
  - gsannikov
related:
  - ADR-741
hub: dev
tags:
  - skills
  - workflows
  - quality
  - slash-commands
  - lifecycle
superseded_by: null
spec_file: 2026-05-13-skillify-workflow-design.md
plan_file: 2026-05-13-skillify-workflow.md
---

# ADR-745: Skillify — Bug-to-Skill Workflow Command

## Status

Implemented (2026-05-13).

## Context

When an incident, repeated bug, or recurring workflow surfaces in Augur, the durable fix is sometimes a **new skill** — but the path from "incident occurred" to "skill exists and is reachable" has no codified workflow. The user (or an AI client) has to remember to scaffold the skill, write SKILL.md frontmatter, add tests, register the capability, and confirm reachability. Each step is small; missing any one leaves debt.

A reference implementation (gbrain) ships a `skillify` workflow as a 10-item checklist (scaffold → logic → tests → audit). The structure is a good fit for Augur as a slash-command body run in the active AI-client session.

## Decision

Add a `/skillify` slash command, defined in `shared-vault/skills/auto-skill-quality/commands/skillify.md`. The command body is a 10-item checklist the active AI client walks through. Dispatch mode is `ide` (multi-step judgment work).

Concretely, the checklist:

1. **Capture incident** — link to the originating commit, log line, `/ask` session, or `TODO_` marker.
2. **Define the durable behavior** — one paragraph: what the skill makes possible that did not exist before.
3. **Determine hub assignment** — pick from `architecture-overview.md` hub list; document why.
4. **Scaffold skill directory** — run the existing scaffolding script (creates `shared-vault/skills/<skill>/{SKILL.md,scripts/,assets/,augur/}`).
5. **Write SKILL.md frontmatter** — fill `x-augur-*` fields: hub, type, tags, description (intent triggers), commands.
6. **Implement logic** — atomic operations in `scripts/`; orchestration in commands or agents.
7. **Add tests** — under `augur/tests/`, importing scripts via `importlib.util.spec_from_file_location` per `feedback_skill_test_convention`.
8. **Register capability** — add MCP tool entries to `config/system/capability_exposure.yaml` (default `primary_surface: cli` per surface-decision-matrix; opt in to MCP only with justification).
9. **Run `check-resolvable`** (ADR-741) — confirm the new skill is reachable from at least one command surface and does not collide with an existing skill.
10. **Run `auto-skill-quality` audit + update changelog** — confirm hygiene; record the addition.

The command is **a guide, not an automation**. Every step is a human (or dispatched client) decision. No auto-merge, no auto-register.

## Non-Goals

- No automatic skill creation. The command walks the checklist; the AI client (or user) does each step.
- No replacement of `auto-skill-quality` — that audits existing skills; this *creates* skills.
- No mandatory adoption. Skillify is an offered path; users are free to scaffold by hand.
- No direct LLM call from Augur. The command body runs inside the active AI-client session per Rule #11.

## Consequences

- One new slash command file: `shared-vault/skills/auto-skill-quality/commands/skillify.md`.
- Pairs naturally with ADR-741 (`check-resolvable` is step 9).
- Documents the canonical "incident → durable skill" path; reduces ad-hoc skill creation drift.
- No new MCP tools; no new infrastructure. Pure workflow capture.

## Related

- ADR-741 (`check-resolvable` is the validation step)
- surface-decision-matrix.md (CLI-default for new MCP tools)
- `feedback_skill_test_convention` (test layout)
