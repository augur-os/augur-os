# Testing Patterns

In Augur, suites always run through the sanctioned loops — `/auto-test-pytest`,
`/auto-test-build`, `/auto-test-dashboard`, `/auto-lint` — never raw
`pytest`/`pnpm`/`vitest` (CLAUDE.md rules 19, 29). The notes below are
review-time expectations, not commands to run by hand.

## Coverage expectations

- Minimum: 80% line coverage on new code
- Target: 90% line coverage
- Critical paths (security, data integrity): 100%

## Review heuristics

- Prefer task-provided test commands and the loops that own them; document
  any deviation.
- Code changes without accompanying tests are a finding
  (`pr_review.py` flags this automatically).
- Skill code is tested in the skill's own `augur/tests/` suite, picked up by
  the pytest loop alongside repo `tests/`.
- The full test surface spans three runners (repo pytest, skill-owned
  `augur/tests` pytest, dashboard jest) — "all tests pass" must cover all
  three.

## Type checking

`tsc --noEmit` runs inside the dashboard build loop; Python type checking via
the lint loop. Treat new type suppressions (`@ts-ignore`, `# type: ignore`)
as review findings.
