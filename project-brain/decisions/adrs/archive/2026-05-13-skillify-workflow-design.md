---
title: "Skillify — Bug-to-Skill Workflow Command"
date: 2026-05-13
status: draft
scope: design
authors:
  - gsannikov
related:
  - ADR-745
  - ADR-741
  - docs/superpowers/plans/2026-05-13-gbrain-borrow-slate.md
  - docs/references/surface-decision-matrix.md
  - shared-vault/skills/auto-skill-quality
tags:
  - skills
  - workflows
  - slash-commands
  - quality
  - lifecycle
---

# Skillify — Bug-to-Skill Workflow Command

## 1. Problem

When an incident, repeated bug, recurring workflow, or persistent gap surfaces in Augur, the durable fix is sometimes a **new skill**. But the path from "incident occurred" to "skill exists and is reachable" has no codified workflow.

Today the user (or an AI client) has to remember to:

1. Scaffold the skill directory in the right place
2. Author `SKILL.md` with the right `x-augur-*` frontmatter
3. Decide hub assignment correctly
4. Place scripts following the layering conventions
5. Add tests under `augur/tests/` using the correct import idiom
6. Register MCP tools in `capability_exposure.yaml`
7. Confirm reachability
8. Update changelog and run quality audits

Each step is small. Missing any one leaves debt: an unreachable tool, a SKILL.md without the right tags, a test that doesn't follow the project's import idiom (see `feedback_skill_test_convention`), a hub assignment that breaks the dashboard.

The gbrain reference implementation ships a `skillify` workflow as a 10-item checklist. The shape fits Augur as a slash command that the active AI client walks through. **No automation — a guide.**

## 2. Goals

- Author a `/skillify` slash command that the active AI client invokes when a candidate incident is identified.
- 10-step checklist captures the canonical sequence from incident to durable skill.
- Each step references the relevant Augur convention (`feedback_skill_test_convention`, `surface-decision-matrix`, hub list from `architecture-overview.md`, `check-resolvable` from ADR-741).
- Dispatch mode is `ide` (multi-step judgment work in the client's own session).
- Discoverable via `/commands` listing.

## 3. Non-Goals

- No automation of any step. The command is a **guide**, walked manually (or by the AI client) one step at a time.
- No replacement of `auto-skill-quality` audit — that lints existing skills. `/skillify` creates them.
- No mandatory adoption. Skillify is an offered path; users may scaffold by hand if they prefer.
- No direct LLM calls from Augur. The command body runs entirely in the active AI-client session per Rule #11.
- No new MCP tool — this is pure workflow capture, not a new atomic operation.
- No new dashboard surface. `/skillify` lives in the AI client's slash-command surface only.

## 4. Design

### 4.1 Command location

`shared-vault/skills/auto-skill-quality/commands/skillify.md`

Reason: `auto-skill-quality` is the skill that owns "skill lifecycle" (audit, hygiene, quality). `/skillify` is the **creation** counterpart to that skill's audit role. Placing it here keeps the two halves of the lifecycle in one place.

### 4.2 Frontmatter

```yaml
---
name: skillify
description: Convert an incident, recurring bug, or persistent gap into a durable skill via a 10-step canonical workflow.
dispatch: ide
visibility: dev
x-augur-tags:
  - skill-lifecycle
  - quality
  - workflow
  - lifecycle
---
```

### 4.3 Command body — the 10 steps

Each step has: title, intent, "what to do", "where to look", "exit criterion."

**Step 1: Capture the incident**
- Intent: Anchor the new skill in concrete evidence.
- Do: Note the commit SHA / log line / `/ask` session id / `TODO_BUG` marker that started this.
- Look: Recent git log; runtime logs in `get_logs_dir()`; the incident itself.
- Exit: One sentence + one link.

**Step 2: Define the durable behavior**
- Intent: State what the skill makes possible that did not exist before.
- Do: Write one paragraph: what the user can do post-skill that they couldn't do pre-skill.
- Look: User pain in step 1.
- Exit: Paragraph approved by user (or judgment call by client).

**Step 3: Determine hub assignment**
- Intent: Pick the right hub so the dashboard mounts correctly.
- Do: Pick from the hub list in `docs/architecture-overview.md`. Document why.
- Look: `architecture-overview.md` hub catalog; existing skills in candidate hubs to validate fit.
- Exit: Hub id chosen + one-sentence rationale.

**Step 4: Scaffold skill directory**
- Intent: Create the standard layout so subsequent steps have somewhere to land.
- Do: Create `shared-vault/skills/<skill>/` with subdirs `scripts/`, `assets/`, `augur/` (including `augur/tests/`), and an empty `SKILL.md`.
- Look: An existing skill (e.g. `shared-vault/skills/auto-skill-quality/`) as template.
- Exit: Directory tree present; no SKILL.md content yet.

**Step 5: Author SKILL.md frontmatter**
- Intent: Make the skill discoverable by the harness.
- Do: Fill `x-augur-*` fields: hub (object form `{id, owner}`), type, group, release, tags, description, mcp-tools (empty for now), dashboard-pages (empty for now).
- Look: Existing SKILL.md examples in the chosen hub. Note: `x-augur-config.hub` must be an object, not a bare string. Avoid naming the skill the same as its hub (causes route doubling).
- Exit: `SKILL.md` frontmatter passes YAML parse; description includes triggering verbs that the user would actually say.

**Step 6: Implement logic**
- Intent: Make the skill do its one thing.
- Do: Write the atomic operations as `@mcp.tool`-decorated functions in `scripts/mcp/`. Each tool is bounded (per `docs/references/agent-vs-mcp-checklist.md`): one operation, structured return, never orchestrates other tools.
- Look: `agent-vs-mcp-checklist.md`, `agent-vs-mcp-examples.md`, the surface-decision-matrix.
- Exit: Tool runs locally with stubbed inputs; returns shape matches contract.

**Step 7: Add tests**
- Intent: Make the skill safe to evolve.
- Do: Place tests under `shared-vault/skills/<skill>/augur/tests/`. Import scripts via `importlib.util.spec_from_file_location` — NEVER via dotted module path (per `feedback_skill_test_convention`).
- Look: `feedback_skill_test_convention` memory; existing skill test files for the import idiom.
- Exit: Tests pass via `/auto-test-pytest`.

**Step 8: Register capability**
- Intent: Make the tool reachable from the surfaces it should be on.
- Do: Add entry to `config/system/capability_exposure.yaml`. Default `primary_surface: cli` per surface-decision-matrix. Opt in to MCP exposure only with a documented use case.
- Look: `surface-decision-matrix.md`; existing entries in `capability_exposure.yaml` matching the same use case.
- Exit: Entry committed; `aug <tool-name> --help` shows the tool.

**Step 9: Run `check-resolvable` (ADR-741)**
- Intent: Confirm the new skill is reachable and does not collide with an existing skill.
- Do: Trigger the resolvability audit via `/auto-skill-quality` or directly via the `skill-resolvable-report` MCP tool.
- Look: The audit report under `get_runtime_dir()/quality/resolvable-report.json`.
- Exit: Report shows the new skill as routed, no orphan, no collision.

**Step 10: Audit + changelog**
- Intent: Compound the workflow into project memory.
- Do: Run `/auto-skill-quality` audit on the new skill. Add a line to the project changelog noting the new skill and the incident that birthed it.
- Look: `auto-skill-quality` output; `CHANGELOG.md`.
- Exit: Audit green; changelog updated.

### 4.4 Command body framing

The command opens with a short preamble that names the workflow's purpose and the user's role: "You're about to convert an incident into a durable skill. This is a 10-step workflow. Walk it step by step. Do not skip steps. If you get stuck on a step, stop and ask for clarification rather than guessing."

Each step is fenced as a sub-heading so the AI client can clearly track progress.

### 4.5 Interactions with ADR-741

Step 9 of the workflow consumes `check-resolvable` (ADR-741). If `/skillify` ships before ADR-741, step 9 falls back to "run `/auto-skill-quality` and inspect output manually." The user-visible flow stays the same; only the verification rigor varies.

## 5. Boundary

- No code changes outside the single command file (and possibly `auto-skill-quality/SKILL.md` if the new command is enumerated there).
- No MCP tool registration.
- No dashboard surface.
- No direct LLM call. The slash command runs in the active AI-client session.

## 6. Open Questions

| # | Question | Tentative answer |
|---|---|---|
| 1 | Should step 9 hard-fail if ADR-741 hasn't shipped? | No — provide a fallback (manual `/auto-skill-quality` inspection). The workflow gradually tightens as the slate ships. |
| 2 | Should the command auto-detect candidate incidents from logs? | No — that would be automation. Skillify is intentionally manual triage. A separate ADR can address auto-detection later. |
| 3 | Should hub assignment offer a curated picker UI? | No for v1. The hub list in `architecture-overview.md` is the picker. |

## 7. Acceptance criteria (mirrored in the plan)

- [ ] `shared-vault/skills/auto-skill-quality/commands/skillify.md` exists with the 10 steps as designed.
- [ ] Frontmatter validates per Augur's command schema.
- [ ] `/commands` listing shows `/skillify`.
- [ ] `--help` against `/skillify` returns usage and does not execute.
- [ ] One end-to-end manual walkthrough succeeds: pick a fake incident, walk all 10 steps, end with a tiny dummy skill that passes `auto-skill-quality`.
