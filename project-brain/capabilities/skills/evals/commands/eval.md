---
name: eval
description: "Retrieval eval harness — replay captured queries against current retrieval and score P@k / R@k / MRR / nDCG@10, manage opt-in query capture, import external corpora, and seed the baseline. The regression safety net for the retrieval stack (ADR-742). File-first: JSONL + markdown on disk, no database, no model calls."
dispatch: ide
visibility: dev
x-augur-tags:
  - evals
  - retrieval
  - regression
  - quality
  - benchmarking
x-augur-export-command: false
---

# /eval Command Execution

`/eval` drives the retrieval eval harness. Every sub-verb maps to an
`aug eval <verb>` shell command — the command body's job is to parse the
sub-verb, run it, and present the result.

This command is **observation + measurement only**. It never alters how
retrieval behaves: capture observes, replay measures, the loop reports. No
Augur-side model calls anywhere in this surface (per CLAUDE.md Rule #11 and
ADR-742 spec §3).

## Dispatch

The argument-after-slash is in `ARGUMENTS`. Parse it before doing anything else.

1. If `ARGUMENTS` is `--help` or `-h`: print this command's `description` from
   the frontmatter and stop without executing any verb (per CLAUDE.md Critical
   Rule #15).
2. Otherwise, the first token of `ARGUMENTS` is the sub-verb. Dispatch it to the
   matching `aug eval <verb>` shell command and present the JSON result.
3. If the first token is not a known sub-verb, print the verb list below and stop.

## Sub-verbs

| Verb | Shell command | What it does |
|---|---|---|
| `replay` | `aug eval replay [--config <path>] [--corpus captured\|external\|all] [--since <iso>] [--with-ci]` | Rerun captured queries against current retrieval, score them, write a report directory (`summary.md` + `raw.jsonl` + `manifest.json`). |
| `export` | `aug eval export [--since <iso>] [--until <iso>]` | Bundle a date range of captured queries + judgments into a portable zip under `<documents>/evals/exports/`. |
| `stats` | `aug eval stats [--run-id <id>]` | Print the parsed metric numbers for a replay run (default: the most recent run). |
| `capture-status` | `aug eval capture-status` | Show contributor mode, consent state, and captured-query counts. |
| `capture-consent` | `aug eval capture-consent` | Write `<documents>/evals/consent.md` to opt in to retrieval-query capture. Capture stays off until this file exists *and* `AUGUR_CONTRIBUTOR_MODE=1`. |
| `import-longmemeval` | `aug eval import-longmemeval --path <jsonl> [--corpus-id <id>]` | Convert a LongMemEval-format JSONL into the v1 query + judgment shape under `<documents>/evals/external/<corpus-id>/`. |
| `command-record` | `aug eval command-record --command <name> --client <client> --input-class <class> --chosen-route <route> [--duration-ms N] [--phases JSON] [--quality-flags JSON] [--warnings JSON] [--outputs JSON] [--run-id <id>]` | Append a private `command.run.v1` envelope for a main command run. |
| `command-aggregate` | `aug eval command-aggregate [--run-id <id>]` | Read private human command scorecards and write a repo-safe aggregate report under private documents. |
| `command-template` | `aug eval command-template` | Print the command scorecard template path. |
| `command-kpi-bootstrap` | `aug eval command-kpi-bootstrap [--run-id <id>]` | Create a private actual-data scenario pack for automatic KPI runs. |
| `command-kpi-run` | `aug eval command-kpi-run [--scenario-path <path>] [--run-id <id>] [--command <command>]` | Run automatic command KPI scenarios, optionally scoped to one canonical command, and write run envelopes, auto scorecards, and aggregate reports. |
| `command-kpi-gate` | `aug eval command-kpi-gate [--required-consecutive-passes 3]` | Fail unless the latest automatic command KPI runs meet the demo bar. |
| `command-kpi-report` | `aug eval command-kpi-report [--run-id <id>]` | Summarize the latest command KPI aggregate, slowest scenario, and failing dimensions. |
| `seed-baseline` | `aug eval seed-baseline` | Run the hand-authored seed query set (`references/baseline-seed-queries.yaml`) through retrieval once so the captured baseline isn't empty. |

Command eval artifacts use actual private data and stay under the configured
documents eval root. Commit only schema/code changes and aggregate summaries
that contain no private source content.

For `command-record`, JSON flags must match the envelope schema: `--phases`
is a list of objects, `--quality-flags` and `--warnings` are lists of strings,
and `--outputs` is an object.

For `command-kpi-*`, the runner creates `reviewer: auto` scorecards from
deterministic assertions: expected facts, required source refs, forbidden
routes, artifact existence, dry-run preservation, and duration thresholds.
Human review can still happen after the automated gate, but it is not required
to execute the KPI loop. `--command <command>` is for a scoped developer loop
such as `keep`; scoped runs write reports but do not update full-suite gate
state. Use `command-kpi-report` to inspect latest speed and failure details.

## Layering invariants for this command

- This command sits at **L2 POLICY** in the surface decision matrix. It tells the
  AI client which `aug eval` verb to run; the client (L3) presents the result;
  the atomic ops (L4) read/replay queries and write report artifacts.
- No Augur-side model calls. Capture observes; replay measures; the loop reports.
- File-first: every artifact is JSONL or markdown under `<documents>/evals/`.
  No database.
- Capture is **off by default** — a no-op unless `AUGUR_CONTRIBUTOR_MODE=1` AND
  `consent.md` exists.

## Notes

- `aug eval <verb>` is the canonical shell command; `/eval <verb>` is the
  slash-command projection — same verbs, projected to every client.
- The nightly `/loop-evals` auto-loop runs `replay` automatically and emits a
  delta report vs. the baseline; it is report-only in v1 (stays green).
- Relevance judgments are hand-authored markdown under
  `<documents>/evals/judgments/<query-id>.md` — `/eval` does not write them.
