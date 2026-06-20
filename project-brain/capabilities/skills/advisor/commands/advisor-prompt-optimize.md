---
name: advisor-prompt-optimize
description: "Prompt optimization walkthrough — baseline a target prompt, command, or skill description, draft variants, and define an A/B evaluation plan. Usage: /advisor-prompt-optimize <path-to-prompt|skill|command> [goal]"
visibility: dev
x-augur-tags:
  - prompts
  - optimization
  - evaluation
x-augur-export-command: false
---

# /advisor-prompt-optimize

Optimize the wording of a real prompt surface — a skill description, a
command body, an agent instruction file, or a reusable prompt — with an
explicit baseline and an A/B evaluation plan. Advisory: the revised text is
proposed, not written; applying it is a separate user-approved edit.

If invoked with `--help`, display this usage and stop — do not execute.

## Usage

- `/advisor-prompt-optimize project-brain/capabilities/skills/graph/SKILL.md` — sharpen a skill description for triggering accuracy
- `/advisor-prompt-optimize commands/validator-verify.md "reduce tokens"` — slim a command with a stated goal

## Workflow

Procedure detail:
`project-brain/capabilities/skills/advisor/references/prompt-optimization.md`
and `references/ab-testing-framework.md`.

1. **Target.** Resolve the prompt file from `$ARGUMENTS` and read it. If the
   target is ambiguous (multiple prompt surfaces in one skill), list them and
   ask which one.
2. **Baseline.** State current metrics from real evidence available now:
   token estimate of the prompt text, observed triggering/confusion incidents
   from this session or git history of the file, explicit constraints the
   prompt must preserve (tool names, trigger phrases, `--help` stop clause,
   frontmatter contract).
3. **Weakness analysis.** Name concrete defects: ambiguity, redundant
   context already present elsewhere, missing output format, weak trigger
   phrases, stale references.
4. **Variants.** Draft 1-2 revised versions (concise vs. detailed) as full
   replacement text, each preserving the constraints from step 2.
5. **A/B evaluation plan.** Define the experiment per the framework:
   hypothesis, primary metric (triggering accuracy, task success), guardrail
   metrics (token count, regression risk), sample window, and decision rule.
   If the prompt affects **retrieval** quality, hand measurement to the
   `evals` skill (capture/replay harness) — do not re-invent scoring here.
6. **Recommendation.** Present the preferred variant with rationale and the
   evaluation plan. Do not edit the target file.

## Boundaries

- Measurable retrieval experiments → `evals` skill (P@k/MRR/nDCG harness).
- Skill quality tiers and description rewrites at catalog scale →
  `auto-skill-quality`.
- Usage-frequency evidence → `routine-coverage` signals, when present; never
  fabricate usage numbers (base recommendations on data, not assumptions).
