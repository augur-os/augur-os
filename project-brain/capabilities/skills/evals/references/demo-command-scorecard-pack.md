# Demo Command Scorecard Pack

This reference lists the first actual-data command eval scenarios. The demo gate
is automatic: `aug eval command-kpi-run` writes `reviewer: auto` scorecards from
deterministic assertions. Human-reviewed scorecards can still be added after the
run, but they are not required for the no-human-in-the-loop KPI gate. Scenario
inputs, outputs, and completed scorecards stay in private documents or private
vault locations.

## Storage

- Scenario definitions: `<documents>/evals/commands/scenarios/`
- Run envelopes: `<documents>/evals/commands/runs/`
- Auto and human scorecards: `<documents>/evals/commands/scorecards/`
- Aggregates: `<documents>/evals/commands/reports/`

## Required Scenarios

### `/ask`

- Ask one real project-brain question.
- Ask one real personal-vault question.
- Mark weak-context answers as pass only when the response explicitly says
  the context is weak and avoids unsupported claims.

### `/keep`

- Capture one local file from the current machine.
- Capture one freeform thought.
- Capture one URL.
- Persist one generated artifact with `/keep --save`.
- Fail routing correctness if a cloud route is selected without explicit user
  intent.

### `/discover`

- Run `/discover`.
- Pass only if it returns useful capabilities/system state rather than generic
  help text or empty sections.

### `/adr`

- Inspect or create one ADR through the canonical workflow.
- Pass only if ADR state and next action are clear.

### `/dev`

- Run a safe bounded dev verb such as `/dev debug` or `/dev build` according
  to current repo rules.
- Pass only if the command reports real blockers or verified results honestly.

### `/a-loops`

- Run `/a-loops status` or a bounded routine status/report command.
- Pass only if routine state comes from the canonical orchestrator or ledger.

### `/sweep`

- Run a dry-run or guarded sweep scenario on real stale-version artifacts.
- Pass only if active data is preserved and recovery information is clear.

## Automatic KPI Commands

- `aug eval command-kpi-bootstrap [--run-id <id>]`
- `aug eval command-kpi-run [--scenario-path <path>] [--run-id <id>] [--command <command>]`
- `aug eval command-kpi-gate [--required-consecutive-passes 3]`
- `aug eval command-kpi-report [--run-id <id>]`
