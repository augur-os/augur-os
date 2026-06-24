---
name: evals
x-augur-type: autoloop
x-augur-group: augur_autoloops
x-augur-release: mvp
x-augur-license: MIT
x-augur-tags: []
description: Retrieval eval harness — captures real queries opt-in (with consent), replays them against current retrieval, and scores P@k / R@k / MRR / nDCG@10. The regression safety net for the retrieval stack. File-first — captured queries, judgments, and reports are JSONL + markdown on disk, no database, no LLM calls. Use this to measure whether a retrieval change improved or regressed quality.
x-augur-callable: project-brain/capabilities/skills/evals/scripts/eval_ops.py
x-augur-mcp-tools:
- eval-replay
- eval-export
- eval-stats
- eval-capture-status
x-augur-loop:
  id: evals
  skill: evals
  automation:
    trigger: nightly
    runner: auto
    discover: ../daemon/scripts/routine_orchestrator/orchestrator.py
  loop_name: evals
  memory:
    trust: observability-only
x-augur-data-dir: evals
x-augur-config:
  commands:
  - id: loop-evals
    type: workflow
    visibility: auto
    description: Nightly retrieval-quality replay against the captured + external corpora; emits a delta report vs. baseline and alerts on metric drops. Report-only in v1.
    callable: scripts/eval_ops.py
    protocol: scan-fix
    loop:
      name: evals
      tier: 1
      trigger: nightly
  - id: command-kpi
    type: workflow
    visibility: auto
    description: Automatic no-human-in-the-loop KPI gate for Augur's canonical command surface; writes private run envelopes, auto scorecards, and aggregate reports.
    callable: scripts/command_kpi_ops.py
    protocol: scan-fix
    loop:
      name: evals
      tier: 1
      trigger: manual
---

# evals

Augur's retrieval regression safety net. The harness **observes** retrieval (opt-in
capture, with consent) and **measures** it (replay + scoring) — it never alters how
retrieval behaves. Implements ADR-742.

## Standard core

Portable workflow guidance for this capability lives in:

- `retrieval-evals/retrieval-eval-harness`

This skill remains the Augur adapter. It owns MCP tools, dashboard/Browse/routine
projection, path-helper access, runtime state, and real-data verification for
Augur.

Three non-negotiable principles, inherited from the gbrain borrow slate:

1. **File-first.** Every artifact is append-only JSONL or markdown under
   `get_documents_dir()/evals/`. The `cat <file>` test passes everywhere. No SQLite,
   no PGLite, no pgvector.
2. **No Augur-side LLM calls.** Capture observes; replay measures. Neither calls a model.
3. **Off by default.** Capture is inert unless `AUGUR_CONTRIBUTOR_MODE=1` *and* an
   explicit `consent.md` file exists.

## Capture

When `AUGUR_CONTRIBUTOR_MODE=1` and `get_documents_dir()/evals/consent.md` exists,
calls to allowlisted retrieval tools (`unified-search`, `knowledge-project-index-search`)
append an `eval.query.v1` record to `get_documents_dir()/evals/queries/<YYYY-MM-DD>.jsonl`.

- The capture observer rides on `mcp_tool_interceptor` via a single import-time
  registration. It is a no-op when the env var is unset, consent is missing, or the
  tool is not allowlisted.
- The observer never raises into the tool path: any capture failure logs at WARN and
  is swallowed. A broken eval skill cannot break live search.
- The env var is read **per call**, so contributor mode can be toggled mid-session.
- `/ask` dispatches into `unified-search` internally, so capture happens once — at the
  retrieval-tool boundary — tagged with a `source` field via a contextvar. Never
  double-captured.

First call with `AUGUR_CONTRIBUTOR_MODE=1` but no `consent.md` writes a one-line stderr
banner explaining what would be captured and instructs the user to run
`aug eval capture-consent`. **No data is captured until `consent.md` exists.**

## Judgments

Relevance labels live in `get_documents_dir()/evals/judgments/<query-id>.md` —
`eval.judgment.v1` frontmatter listing `relevant_doc_ids`. Hand-labeled, editable,
composable: the query id is `sha1(query + source)[:12]`, so one judgment covers every
future invocation of that query. Binary relevance only (0/1) in v1.

## Replay

`aug eval replay [--config <path>] [--corpus captured|external|all] [--since <iso>]`
reloads captured queries (deduped by id), reruns each query's recorded `tool` against
**current** retrieval, and scores it against its judgment. Output is a report directory:

```
get_documents_dir()/evals/reports/<run-id>/
├── summary.md      # human-readable: overall + per-bucket + delta vs. baseline
├── raw.jsonl       # one scored-query row per line — recompute aggregates without rerun
└── manifest.json   # run metadata: timestamp, commit, config, query-set hash
```

`<run-id> = <YYYY-MM-DD-HHMMSS>-<commit[:7]>`. Queries with no labeled relevant docs
are skipped (counted under `unlabeled_queries`) — they measure a labeling gap, not
retrieval quality. Replay is deterministic given the same `augur_commit` +
`vault_manifest_hash`; a manifest mismatch flags `index_drift: true`.

## Metrics (the regression contract — spec §4.4)

- **P@k** — `|set(top_k) ∩ R| / k`. Denominator is `k`, not `min(k, |retrieved|)`:
  returning too few results is penalized.
- **R@k** — `|set(top_k) ∩ R| / |R|`. Undefined when `|R| == 0` → query skipped.
- **MRR** — `1 / rank_of_first_relevant`, over the **full** retrieved list (1-indexed),
  0 if no relevant doc appears.
- **nDCG@10** — binary gain ∈ {0, 1}; `IDCG@10` over `min(10, |R|)`.
- Aggregation: unweighted mean across non-skipped queries, plus `stderr` (cheap, every
  run) and `bootstrap_ci_95` (baseline + nightly summary only).

## External corpus

Drop a LongMemEval-format JSONL into `get_documents_dir()/evals/external/<corpus-id>/`
and `aug eval import-longmemeval` converts it into `eval.query.v1` + `eval.judgment.v1`
files. Replay scores it alongside captured queries, bucketed separately under
`corpus = "<corpus-id>"`. See `references/longmemeval-format.md`.

## Demo Case Evals

Demo case evals score real rehearsal outputs before demo day without model calls.
`deck-slide-critique` checks grounding, specificity, judge readiness, and speed
against deck/slide evidence; `meeting-transcript` applies the same dimensions to
transcript, meeting-memory, and ask-from-transcript outputs. Private records live
under `get_documents_dir()/evals/demo-runs/`.

## `/loop-evals` auto-loop

Tier 1, nightly. Runs `aug eval replay` against the captured + external corpora, writes
a report dir, computes a delta vs. the baseline symlink (or the most recent prior run),
and emits a WARN alert event when any of `P@5`, `R@5`, `MRR`, `nDCG@10` drops by more
than the configured absolute threshold (default 5.0 points, see `config.yaml`).
**Report-only in v1** — the loop result stays green regardless of alert severity.
CI-blocking is a v2 evolution after one stabilization release.

## Commands

- `aug eval replay` — rerun captured queries against current retrieval, score, write report
- `aug eval export` — bundle a date range into a portable zip
- `aug eval stats` — print the parsed numbers for a run (default: most recent)
- `aug eval capture-status` — show capture mode / consent / counts
- `aug eval capture-consent` — write `consent.md` to opt in to capture
- `aug eval import-longmemeval` — convert a LongMemEval JSONL into the v1 corpus shape
- `aug eval seed-baseline` — run the hand-authored seed query set through retrieval once

## Command Evals

Command evals extend the retrieval eval harness with human-reviewed actual-data
scorecards for the canonical command set. Use:

- `references/command-scorecard-template.md` for one run review.
- `references/demo-command-scorecard-pack.md` for the first demo scenario set.
- `aug eval command-record` to append a private command run envelope.
- `aug eval command-aggregate` to summarize private human scorecards.

## Command KPI Loop

`aug eval command-kpi-bootstrap` creates private actual-data scenarios under
`<documents>/evals/commands/scenarios/`.

`aug eval command-kpi-run` executes those scenarios automatically, writes
`command.run.v1` envelopes, writes `command.scorecard.v1` scorecards with
`reviewer: auto`, and writes a private aggregate report. Add
`--command <command>` for a scoped developer loop such as `keep`; scoped runs
do not update the full-suite consecutive-pass gate state.

`aug eval command-kpi-report` prints the latest aggregate summary plus the
slowest scenario and failed dimensions from the details file.

`aug eval command-kpi-gate` checks the latest aggregate against the demo KPI
bar: all canonical commands covered, no warnings or failures, speed thresholds
met, and three consecutive passing iterations.

## MCP tools

`eval-replay`, `eval-export`, `eval-stats`, `eval-capture-status` — all `readOnlyHint`,
CLI-primary per the surface-decision-matrix. No dashboard exposure in v1.
