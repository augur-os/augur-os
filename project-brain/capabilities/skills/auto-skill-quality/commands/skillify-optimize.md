---
description: "Optimize an existing skill for accuracy + speed/cost via a converge-or-stall loop validated on the skill's replayed real runs (ADR-804)."
visibility: project
mode: operation
---

# /skillify <skill> — optimize mode

Inline-session workflow. You (the AI client) are the orchestrator; Augur makes no LLM call of its own. Improve ONE existing skill's accuracy AND speed/cost together, keeping a change only if the skill's tests pass and a held-out combined score strictly improves; otherwise revert. Stop on convergence/stall.

Optimizer scripts: `project-brain/capabilities/skills/auto-skill-quality/scripts/optimizer/`.

## Contract

1. **Isolate.** Confirm you are in (or create) an isolated worktree off the current branch (goal-loop pattern). Never optimize on `main`.
2. **Baseline.** Run the production runner to measure the skill's current combined score on a held-out validation split of its **replayed real runs** (`collect_replay_cases` — MCP/CLI logs, else curated/seed evals). If the runner reports **not measurable** (no replay cases and no evals), STOP and tell the user to add `evals/evals.json` or example inputs — never optimize blind.
3. **Loop until stall.** Each round:
   - Inspect the train cases + the per-case profiling (wall-time, tokens, accuracy) to find the weakest spot.
   - Propose and apply ONE edit in the worktree — an instruction/prompt change, a config knob (model tier, caching, batch size), or an orchestration/script change. (If the skill has NO tests, restrict to instruction/config edits — do not rewrite scripts without a test gate.)
   - Run `optimize-evaluate` (production runner): it runs the skill's own tests, re-measures the validation combined score, and **accepts (commits a checkpoint) only if tests pass AND the score strictly improves**, else `git revert`.
   - Run `optimize-cli.py status --run <id>`; repeat while verdict is `continue` or `improved`; stop on `stalled` or `exhausted`.
4. **Report + hand off.** Run `optimize-cli.py report --run <id>`. Surface the branch and the before/after combined score, accepted edits, and Δaccuracy/Δtokens/Δtime for `/dev merge`. **Never auto-merge.** Report honestly — if no edit improved the score, say so (a green loop that changed nothing is not "optimized").
