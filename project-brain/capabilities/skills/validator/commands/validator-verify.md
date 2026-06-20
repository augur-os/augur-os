---
name: validator-verify
description: "Pre-merge verification walkthrough — heuristic diff review, silent-failure hunt, sanctioned test loops, acceptance-criteria verdict. Usage: /validator-verify [commit|range] [--base <ref>]"
visibility: dev
x-augur-tags:
  - testing
  - review
  - pre-merge
x-augur-export-command: false
---

# /validator-verify

Verify a change set before merge: review the diff, run the suites through the
sanctioned loops, check acceptance criteria, and deliver a PASS/FAIL verdict.
Detailed procedure: `project-brain/capabilities/skills/validator/references/workflow.md`.

If invoked with `--help`, display this usage and stop — do not execute.

## Usage

- `/validator-verify` — verify `HEAD` against its parent
- `/validator-verify abc1234` — verify a specific commit
- `/validator-verify --base main` — verify everything since `main`

## Workflow

1. **Scope.** Resolve the commit/range from `$ARGUMENTS` (default `HEAD`).
   Collect acceptance criteria from the user request, governing spec/plan, or
   commit message; if none exist, say so and review against repository rules
   only.
2. **Heuristic diff review.** Run
   `uv run python project-brain/capabilities/skills/validator/scripts/pr_review.py --commit <commit> [--base <ref>] --json`
   and read the findings. High-severity findings (suppressions, `shell=True`,
   `eval`/`exec`, disabled TLS verification) block until fixed or explicitly
   accepted by the user (CLAUDE.md rule 5).
3. **Silent-failure hunt.** Run
   `uv run python project-brain/capabilities/skills/validator/scripts/hunt_silent_failures.py --commit <commit> [--base <ref>] --json`
   and triage error-swallowing patterns the diff introduces.
4. **Suites via sanctioned loops only** (rules 19, 29) — scope to what the
   diff touches and state what was skipped and why:
   - Python: `/auto-test-pytest`
   - Dashboard build: `/auto-test-build` (use `aug dev build` when the dev
     server must be rebuilt and browser-verified)
   - Dashboard pages: `/auto-test-dashboard`
   - Lint: `/auto-lint`
5. **Acceptance criteria.** For each criterion, name the concrete evidence
   that proves it (rule 34). UI-touching changes additionally need a
   client-side load check (rule 28) — target the affected page with
   `uv run python project-brain/capabilities/skills/validator/scripts/ui_qa.py --url <page>`
   or capture it with `scripts/capture_ui.py`.
6. **Verdict.** Report PASS or FAIL with findings per step, criteria
   evidence, and residual risk. On FAIL, list the exact blockers and fix them
   before handoff (rule 9) — never downgrade the claim.
