---
name: validator-regression
description: "Release regression procedure — full three-runner test sweep, build verification, heuristic review of the release range, APPROVED/BLOCKED verdict. Usage: /validator-regression [--base <last-release-ref>]"
visibility: dev
x-augur-tags:
  - testing
  - regression
  - release
x-augur-export-command: false
---

# /validator-regression

Release-level validation: run the full test surface, review the cumulative
release range, and end with an APPROVED or BLOCKED verdict. Detailed
procedure: `project-brain/capabilities/skills/validator/references/workflow.md`.

If invoked with `--help`, display this usage and stop — do not execute.

## Usage

- `/validator-regression` — full sweep, review `HEAD` against its parent
- `/validator-regression --base v0.9.0` — review the whole range since the
  last release ref

## Workflow

1. **Full test sweep — all three runners** (rules 19, 29; "all tests pass"
   must cover all three):
   - `/auto-test-pytest` — repo `tests/` plus skill-owned `augur/tests` suites
   - `/auto-test-build` — dashboard production build
   - `/auto-test-dashboard` — dashboard pages/jest surface
2. **Heuristic review of the release range.** Run
   `uv run python project-brain/capabilities/skills/validator/scripts/pr_review.py --base <ref> --json`
   and
   `uv run python project-brain/capabilities/skills/validator/scripts/hunt_silent_failures.py --base <ref> --json`
   so the cumulative range is reviewed, not just the tip commit.
3. **Verdict.**
   - Any failing suite, build break, or unresolved high-severity finding →
     **BLOCKED**, listing the blocking issues.
   - Otherwise → **APPROVED**, naming the real evidence per runner (counts,
     loop output, finding totals).
   - Performance-regression baselines are not implemented — do not claim
     performance coverage.
