# Validator — Detailed Workflows

Two procedures. Both are agent-orchestrated: the AI client reads the command
body, runs the sanctioned loops and the validator scripts, and owns the
verdict. Scripts never orchestrate each other.

## Verify Changes Workflow (`/validator-verify`)

Pre-merge verification of a change set: review the diff, run the suites,
check acceptance criteria, deliver a PASS/FAIL verdict.

### Step 1: Establish scope

- Identify the commit or range under review (`HEAD`, a branch range, or a
  specific commit the user names).
- Collect the stated acceptance criteria: from the user request, the
  governing spec/plan, or the commit message. If none exist, say so and
  review against repository rules only.

### Step 2: Heuristic diff review

```
uv run python project-brain/capabilities/skills/validator/scripts/pr_review.py --commit HEAD --json
```

Flags suppression markers, `shell=True`, `eval`/`exec`, disabled TLS
verification, hardcoded absolute paths, debug logging, and code changes that
arrive without tests. High-severity findings mean REQUEST_CHANGES until
resolved or explicitly accepted by the user (CLAUDE.md rule 5).

### Step 3: Silent-failure hunt

```
uv run python project-brain/capabilities/skills/validator/scripts/hunt_silent_failures.py --commit HEAD --json
```

Flags bare excepts, `except: pass`, empty catch blocks, and swallowed promise
rejections added by the diff.

### Step 4: Run the suites (sanctioned loops only)

- Python: `/auto-test-pytest`
- Dashboard build: `/auto-test-build` (or `aug dev build` when the dev server
  must be rebuilt and verified)
- Dashboard pages: `/auto-test-dashboard`
- Lint: `/auto-lint`

Never invoke raw `pytest`/`pnpm` (rules 19, 29). Scope to the loops the diff
actually touches; say which were skipped and why.

### Step 5: Verify acceptance criteria

For each criterion, name the concrete evidence (test, script output, page
state) that proves it — passing suites alone do not prove a criterion
(rule 34). UI-touching changes additionally need a client-side load check
(rule 28); `scripts/ui_qa.py` / `scripts/capture_ui.py` can target the
affected page.

### Step 6: Verdict

Report PASS or FAIL with: findings per step, criteria evidence, and any
residual risk. FAIL lists the exact blockers; fix them before handoff
(rule 9) instead of downgrading the claim.

## Regression Testing Workflow (`/validator-regression`)

Release-level validation: full sweep across all three runners plus build
verification, ending in APPROVED or BLOCKED.

### Step 1: Full test sweep

Augur's test surface spans three runners — all must be covered before
claiming "all tests pass":

1. `/auto-test-pytest` (repo `tests/` plus skill-owned `augur/tests` suites)
2. `/auto-test-build` (dashboard production build)
3. `/auto-test-dashboard` (dashboard pages/jest surface)

### Step 2: Heuristic review of the release range

Run `pr_review.py` and `hunt_silent_failures.py` with `--base <last-release>`
to review the cumulative range, not just the tip commit.

### Step 3: Verdict

- Any failing suite, build break, or high-severity finding → **BLOCKED**,
  with the blocking issues listed.
- Otherwise → **APPROVED**, naming the real evidence per runner.

Performance-regression baselines are not implemented; do not claim
performance coverage.

## Error handling

1. **Tests fail** — report failures and fix or escalate; never approve.
2. **Heuristic findings** — high severity blocks; medium/low are reported
   with a recommendation.
3. **A loop itself breaks** — recovering it is part of the task (rule 36);
   follow the runbooks in `docs/agent-topics/DEBUGGING.md`.
