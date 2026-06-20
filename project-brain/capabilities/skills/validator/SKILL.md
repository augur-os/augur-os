---
name: validator
x-augur-type: skill
x-augur-tags:
- testing
- review
- pre-merge
- ui-qa
- regression
description: Use when verifying changes before a merge or release — heuristic diff
  review of a commit (pr_review), hunting silent-failure patterns in a diff
  (hunt_silent_failures), running a targeted UI QA pass or full-page screenshot
  capture against a dashboard URL, or walking the /validator-verify pre-merge and
  /validator-regression release procedures.
x-augur-group: dev
x-augur-release: mvp
x-augur-license: Apache-2.0
---

# validator

Pre-merge verification and review procedures. The validator skill does not
re-implement Augur's test infrastructure — the sanctioned auto-loops
(`/auto-test-pytest`, `/auto-test-dashboard`, `/auto-test-build`, `/auto-lint`)
and `aug dev build` remain the only way to run suites and builds. What this
skill adds is the layer those loops do not cover:

- **Heuristic diff review** — `scripts/pr_review.py` reviews a commit (or
  range) locally: suppression markers, `shell=True`, `eval`/`exec`,
  hardcoded paths, silent exception handling, code-without-tests.
- **Silent-failure hunting** — `scripts/hunt_silent_failures.py` scans a diff
  for error-swallowing patterns (bare except, empty catch, swallowed promise
  rejections).
- **Targeted UI QA and capture** — `scripts/ui_qa.py` and
  `scripts/capture_ui.py` wrap the shared dashboard engines in
  `apps/dashboard/scripts/skill-scripts/` for one-off checks of a specific
  URL, archiving results outside the repo tree.
- **Procedures** — `/validator-verify` (pre-merge) and `/validator-regression`
  (release) orchestrate the scripts above plus the sanctioned loops; see
  `references/workflow.md`.

## Helper scripts

Run with `uv run python <script> --help` first; all are CLI-only (no MCP tools).

| Script | Purpose |
|--------|---------|
| `scripts/pr_review.py` | Heuristic local PR-style review of a commit/range |
| `scripts/hunt_silent_failures.py` | Detect error-swallowing patterns in a diff |
| `scripts/ui_qa.py` | Targeted UI QA (hydration/alignment/interactivity) for one URL |
| `scripts/capture_ui.py` | Full-page screenshot + metadata for one URL |

## Constraints

- **Advisory only** — review scripts never modify application code.
- **No raw runners** — suites, builds, and lint go through the auto-loops and
  `aug dev build`, never raw `pytest`/`pnpm` (CLAUDE.md rules 19, 29).
- **Artifacts stay out of the repo** — QA archives go to `get_runtime_dir()`,
  captures to `get_logs_dir()/browser-verification/` (never the repo tree).

## References

| Trigger | Load |
|---------|------|
| Pre-merge / regression procedure detail | `references/workflow.md` |
| Playwright browser testing | `references/imported-full-skill.md` |
| Security review checklist | `references/security-checklist.md` |
| Security operating guide | `references/operating-guide.md` |
| Coverage targets | `references/testing-patterns.md` |

## Provenance

Selective port of the staged r3 `validator` draft (third-party-derived
webapp-testing toolkit plus validator-agent workflows). Upstream license:
Apache-2.0 (`LICENSE.txt`). Stale or duplicative staged scripts (raw test
runners, structure enforcer, plugin integration tester, security scanners
already owned by routine-security) were excluded at adoption; see CHANGELOG.
