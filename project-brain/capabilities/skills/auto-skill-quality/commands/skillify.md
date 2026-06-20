---
name: skillify
description: "Convert an incident, recurring bug, or persistent gap into a durable Augur skill via a 10-step canonical workflow. Walks the active AI client through scaffold, frontmatter, logic, tests, capability registration, and quality audit. Use after an incident postmortem when the durable fix is a new skill."
dispatch: ide
visibility: dev
x-augur-tags:
  - skill-lifecycle
  - quality
  - workflow
  - lifecycle
x-augur-export-command: true
---

# /skillify Command Execution

You're about to convert an incident into a durable Augur skill. This is a **10-step workflow**. Walk it step by step. Do not skip steps. If you get stuck on a step, stop and ask for clarification rather than guessing.

This command is a **guide, not an automation**. Every step is a judgment call you (or the user) make. Augur does not auto-create skills, auto-register capabilities, or auto-merge anything as part of this command. See ADR-745 for the full rationale.

## Dispatch

The argument-after-slash is in `ARGUMENTS`. Parse it before doing anything else.

1. If `ARGUMENTS` is `--help` or `-h`: print this command's `description` from the frontmatter and stop without executing any step (per CLAUDE.md Critical Rule #15).
2. If `ARGUMENTS` is a single token naming an existing skill directory under `project-brain/capabilities/skills/` (or the configured private vault), follow `skillify-optimize.md` (optimize mode) instead of the create flow.
3. Otherwise treat `ARGUMENTS` as an optional skill-name hint or one-line incident summary, then proceed to **Step 1**.

The skill name is not required up front — Step 2 derives the durable behavior, and the name falls out of that.

## Layering invariants for this command

- This command sits at **L2 POLICY** in the [surface decision matrix](../../../../docs/references/surface-decision-matrix.md). It tells the AI client what to do; the client (L3) judges each step; atomic ops (L4) only persist.
- No Augur-side LLM calls. The 10 steps run inside the active AI-client session per CLAUDE.md Rule #11.
- No automation. Every step is acknowledged out loud and verified by the user (or the dispatched client's own judgment) before proceeding.

---

## Step 1 — Capture the incident

**Intent.** Anchor the new skill in concrete evidence so a future reader knows why it exists.

**Do.**
- Note the commit SHA, log line, `/ask` session id, or `TODO_BUG` marker that motivated this skill.
- Capture one sentence summarizing what went wrong (or what's missing).

**Where to look.**
- Recent `git log` for the failing commit.
- Runtime logs under `get_logs_dir()` (`~/Library/Logs/Augur/`).
- Any `TODO_BUG` / `TODO_OUTDATED` markers the incident generated.
- The original `/ask` conversation or incident postmortem.

**Exit criterion.** One sentence describing the incident, plus one link or identifier (SHA, log path, session id). Record it in a scratch note — you'll cite it in Step 10.

---

## Step 2 — Define the durable behavior

**Intent.** State what the skill makes possible that did not exist before.

**Do.**
- Write one paragraph: what can the user (or another agent) do *after* this skill exists that they could not do *before*?
- Phrase it as a capability, not as a fix. "Skill X lets the user/agent do Y" — not "Skill X fixes bug Z."

**Where to look.**
- The user pain captured in Step 1.
- Existing skills in `project-brain/capabilities/skills/` to make sure this capability is genuinely new.

**Exit criterion.** A one-paragraph capability statement, approved by the user (or judged sufficient by the dispatched client). The skill name should now be obvious — pick a short kebab-case identifier.

---

## Step 3 — Determine hub assignment

**Intent.** Pick the right hub so the dashboard mounts the skill correctly.

**Do.**
- Pick from the hub catalog. The canonical hub list lives at the top of `docs/agent-topics/ARCHITECTURE.md` (referred to elsewhere as `architecture-overview.md`): `adaptive, brain, business, career, command, dev, life, studio, websites`.
- Briefly justify the choice in one sentence — what user journey does the skill belong to?
- Validate fit by inspecting one or two existing skills in the candidate hub.

**Where to look.**
- `docs/agent-topics/ARCHITECTURE.md` for the hub list.
- `project-brain/capabilities/skills/<peer-skill>/SKILL.md` for hub frontmatter examples in the candidate hub.

**Exit criterion.** Hub id chosen plus one-sentence rationale. Avoid naming the skill the same word as its hub (causes route doubling — `dev/dev` etc.).

---

## Step 4 — Scaffold skill directory

**Intent.** Create the standard layout so subsequent steps have somewhere to land.

**Do.**
- Create the directory tree at `project-brain/capabilities/skills/<skill-name>/`:
  - `SKILL.md` (empty for now — filled in Step 5)
  - `scripts/` (Python atomic ops live here)
  - `scripts/mcp/` (created only if Step 6 produces MCP-decorated tools)
  - `assets/` (seed data, templates, fixtures)
  - `augur/` and `augur/tests/` (project-specific harness data + tests)

**Where to look.**
- An existing skill of similar shape as a template — `project-brain/capabilities/skills/auto-skill-quality/` is a fully-featured reference; smaller skills like `project-brain/capabilities/skills/ingest/` show a leaner shape.

**Exit criterion.** Directory tree exists. `SKILL.md` is empty (no frontmatter yet). No scripts or tests yet.

---

## Step 5 — Author `SKILL.md` frontmatter

**Intent.** Make the skill discoverable by the harness, the dashboard, and the sync_agents pipeline.

**Do.** Author the **native Claude Agent Skill contract first**, then add Augur wiring only if the skill needs it.

1. **Required native frontmatter** (this is the whole contract for an instruction/workflow skill):
   - `name` — the kebab-case identifier from Step 2.
   - `description` — one paragraph stating WHEN to use the skill, in the words a user/agent would actually say. This is the primary trigger surface for Claude's `Skill` tool. Lead with "Use when…".
   - `allowed-tools` (optional) — restrict tools if the skill should not have full access.
2. **Body** — write the skill body using native progressive disclosure: a focused `SKILL.md`, with deep material in `references/` and runnable helpers in `scripts/`. Do not encode behavior in `x-augur-*`.
3. **Augur wiring (`x-augur-*`) — ADD ONLY IF NEEDED.** These extend the native skill; they are NOT required for it to work as a Claude skill:
   - Add `x-augur-mcp-tools`, `x-augur-config.contributions`, or `x-augur-dashboard-pages` ONLY if the skill ships MCP tools / dashboard surfaces (Step 6/8).
   - Add `x-augur-loop` / `x-augur-routine` ONLY if the skill is a scheduled routine.
   - Add `x-augur-type`, `x-augur-group`, `x-augur-release`, `x-augur-tags` for catalog placement.
   - A pure instruction/workflow skill needs NONE of these — `name` + `description` + body is sufficient, and it will be projected to `~/.claude/skills/` by sync_agents (see ADR-805).

**Where to look.**
- Peer skills' `SKILL.md` files in the chosen hub.
- `docs/references/design-standards.md` for naming conventions.

**Exit criterion.**
- Frontmatter parses cleanly AND includes `name` + a trigger-style `description` (verify: `python3 -c "import yaml,sys; d=yaml.safe_load(open('<SKILL.md>').read().split('---')[1]); assert d.get('name') and d.get('description'), 'native contract missing'"`).
- `description` reads as a "Use when …" trigger, not a feature list.
- Any `x-augur-*` field present has a concrete reason (MCP tool, dashboard page, routine, or catalog placement) — no speculative wiring.
- Skill name is not identical to its hub id.

---

## Step 6 — Implement logic

**Intent.** Make the skill do its one thing, layered correctly.

**Do.**
- Write atomic operations as Python functions in `scripts/`.
- If a function should be reachable from MCP, decorate it with `@mcp.tool` and place it in `scripts/mcp/` (consult `scripts/mcp/__init__.py` patterns in peer skills).
- Each atomic op must be **bounded**: one operation, structured return, no orchestrating other tools. Orchestration belongs in commands or agents, not in atomic ops.
- Use `src.config.paths` helpers (`get_vault_dir`, `get_runtime_dir`, etc.) instead of hardcoding paths (CLAUDE.md Rule #3).

**Where to look.**
- `docs/references/agent-vs-mcp-checklist.md` — when to make something an atomic op vs an agent step.
- `docs/references/agent-vs-mcp-examples.md` — worked examples of layering.
- `docs/references/surface-decision-matrix.md` — which surface (skills / commands / MCP / CLI) for which kind of operation.

**Exit criterion.** The atomic operation runs locally on stubbed inputs and returns the documented shape. No fallback masking of broken behavior (Rule #1, #5).

---

## Step 7 — Add tests

**Intent.** Make the skill safe to evolve.

**Do.**
- Place tests under `project-brain/capabilities/skills/<skill-name>/augur/tests/`.
- **Import the script under test via `importlib.util.spec_from_file_location` — NEVER via dotted module path.** This is a project-wide Augur convention captured in `feedback_skill_test_convention`. Skill directories are not Python packages by design.

Example test header:

```python
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "my_ops.py"
spec = importlib.util.spec_from_file_location("my_ops", SCRIPT)
my_ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(my_ops)

def test_my_op():
    result = my_ops.do_thing()
    assert result["ok"] is True
```

**Where to look.**
- `feedback_skill_test_convention` memory.
- Existing skill test files (e.g. under `project-brain/capabilities/skills/auto-skill-quality/augur/tests/`) for the import idiom.

**Exit criterion.** Tests pass via `/auto-test-pytest`. Do not bypass with skip-markers or assertion rewrites (Rule #5).

---

## Step 8 — Register capability

**Intent.** Make the new tool reachable from the surfaces it should be on, and only those surfaces.

**Do.**
- If the skill ships one or more `@mcp.tool` functions, add an entry per tool to `config/system/capability_exposure.yaml`.
- **Default `primary_surface: cli`** per `docs/references/surface-decision-matrix.md`. CLI is the cheapest, lowest-risk surface — every new MCP tool starts there.
- Opt in to `mcp` or `mcp via dashboard` exposure **only with a documented use case** (dashboard page consumes it; agent flow depends on it). Record the justification in the YAML entry's comment.
- If the skill is a workflow-only command (no atomic op), no capability entry is needed — slash-command discovery handles it.
- **Native Claude exposure (ADR-805):** add `claude` to the skill's `export_to` in `config/system/capability_exposure.yaml` (the `skill:<name>` entry) so its `SKILL.md` projects to repo-local `.claude/skills/<name>/` as a clean native Agent Skill (`x-augur-*` stripped; `name`/`description`/`allowed-tools` kept), invokable by Claude's `Skill` tool. The same clean native render reaches Codex/Gemini/OpenCode when they are in `export_to`. Omit `claude` only if the skill must stay client-private.

**Where to look.**
- `docs/references/surface-decision-matrix.md` for the canonical CLI-first rule.
- Existing entries in `config/system/capability_exposure.yaml` matching a similar use case (knowledge-* tools, books-* tools, etc.).

**Exit criterion.**
- The capability entry is committed.
- `aug <tool-name> --help` (or the equivalent CLI shell wrapper) shows the tool.
- If MCP exposure was selected, the justification is recorded.
- For native Claude exposure: `export_to` includes `claude`, and after `aug sync skills all` the skill appears at `.claude/skills/<name>/SKILL.md` with clean native frontmatter (no `x-augur-*`).

---

## Step 9 — Run check-resolvable (ADR-741)

**Intent.** Confirm the new skill is reachable from at least one command surface and does not collide with an existing skill.

**Do.**
- Run the `skill-resolvable-report` MCP tool (introduced by ADR-741). It writes a resolvability audit under `get_runtime_dir()/quality/resolvable-report.json`.
- Inspect the report for the new skill:
  - It should appear as **routed** (reachable from at least one surface).
  - It should have **no orphan** flag.
  - It should have **no collision** with an existing skill name, command, or capability id.

**Fallback (pre-ADR-741 environments).** If `skill-resolvable-report` is not yet available (ADR-741 hasn't shipped in this checkout):
- Run `/auto-skill-quality` and inspect the output for the new skill.
- Manually confirm: `grep -rn "<skill-name>" project-brain/capabilities/skills/*/SKILL.md` does not surface a name collision.
- Manually confirm the skill appears in `docs/generated/skill-manifest.json` after the next sync.

**Where to look.**
- ADR-741 (`project-brain/decisions/adrs/archive/ADR-741-skill-resolvability-and-mece-audit.md`) for the tool contract.
- `get_runtime_dir()/quality/resolvable-report.json` for the audit output.

**Exit criterion.** Report shows the new skill as routed, with no orphan or collision warnings. If you fell back to manual inspection, the equivalent manual checks pass.

---

## Step 10 — Run auto-skill-quality audit and update changelog

**Intent.** Compound the workflow into project memory so the next incident triage knows this path was walked.

**Do.**
- Run `/auto-skill-quality` against the new skill. Confirm it scores at least tier B (structural floor) — tier A is the long-term goal but is not gating for a brand-new skill.
- Append a line to `CHANGELOG.md` (or the active changelog surface) noting the new skill **and the originating incident from Step 1**.
- If the skill was born from a `TODO_BUG` or `TODO_OUTDATED` marker, remove or update the marker now that the durable fix exists.

**Where to look.**
- `/auto-skill-quality` output for tier + dimension breakdown.
- `CHANGELOG.md` at the repo root.

**Exit criterion.**
- `/auto-skill-quality` audit reports tier B or higher with no `F`-tier dimensions.
- Changelog updated with one line citing the new skill and the Step-1 incident reference.
- Any obsolete `TODO_` markers cleared.

---

## Done

If all 10 steps are checked:

1. Run `/auto-skill-quality` one more time on the full repo — confirm the new skill is included in the report.
2. Run `/auto-lint` on touched files.
3. Use `/dev-merge` to commit and merge per the standard merge workflow.

Do not skip the merge step. A skill that is not merged is not durable.

## Related

- ADR-745 (this workflow's decision record)
- ADR-741 (Step 9's verification tool)
- `docs/references/surface-decision-matrix.md` (Step 8's CLI-first rule)
- `feedback_skill_test_convention` memory (Step 7's import idiom)
- `project-brain/capabilities/skills/auto-skill-quality/SKILL.md` (the audit half of the skill lifecycle; `/skillify` is the creation half)
