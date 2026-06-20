---
status: Implemented
date: 2026-05-13
deciders:
  - gsannikov
related:
  - ADR-738
  - ADR-739
  - ADR-740
  - ADR-741
  - ADR-571
hub: dev
tags:
  - evals
  - retrieval
  - quality
  - benchmarking
  - regression
superseded_by: null
spec_file: docs/superpowers/specs/2026-05-13-eval-harness-design.md
plan_file: docs/superpowers/plans/2026-05-13-eval-harness.md
---

# ADR-742: Retrieval Eval Harness with Contributor Capture

## Status

Implemented (2026-05-14). The eval-harness skill `shared-vault/skills/evals/`
ships capture, replay, report, the LongMemEval adapter, seed-baseline, four
read-only MCP tools, the `/eval` command, and the `/loop-evals` nightly
report-only loop. 79 skill tests pass. Phase 2 gate met: 57 baseline queries
captured with 32 hand judgments; baseline recorded under
`get_documents_dir()/evals/reports/baseline/`. Phase 2 verification surfaced a
pre-existing non-determinism in the `UnifiedSearcher` retrieval stack — the
harness's own determinism is proven by the mocked-retrieval unit tests; two
strictly-correct retrieval fixes (`rg --sort path`, sorted skill-scope glob)
landed alongside, and the residual cross-process churn is recorded as a
Phase 3 retrieval-debugging follow-up.

## Context

Augur currently has zero retrieval regression coverage. As the typed graph (ADR-738), RRF fusion (ADR-739), and compiled-truth/timeline schema (ADR-740) ship, any regression in `unified-search` precision/recall will be invisible until a user notices the wiki "feels worse." That is not acceptable for a system whose value is compounded knowledge.

A reference implementation (gbrain) ships `eval export` / `eval replay` / `eval longmemeval` with an opt-in **contributor mode** that captures real queries (with consent) for offline A/B testing of retrieval changes. The same pattern, adapted to file-first transparency, gives Augur a real regression safety net.

## Decision

Build a retrieval eval harness as a new skill `shared-vault/skills/evals/` (hub: `dev`). The harness supports opt-in query capture, replay against arbitrary retrieval configurations, and a precision/recall@k regression report. **All captured data is markdown / JSONL on disk** — no database.

Concretely:

1. **Capture** — gated by env var `AUGUR_CONTRIBUTOR_MODE=1`. When enabled, `/ask` and `unified-search` calls are appended to `get_documents_dir()/evals/queries/<date>.jsonl`. A first-run consent banner explains what is captured (the query text + retrieved doc ids + timestamps; never the user's full vault).
2. **Judgments** — relevance labels live in `get_documents_dir()/evals/judgments/<query-id>.md` with frontmatter listing the relevant doc ids. Initially hand-labeled; later, dispatchable via `oneshot` to the active AI client to propose labels (which the user then confirms).
3. **Replay** — `aug eval replay [--config <path>]` reruns captured queries against the current retrieval config and scores P@5, R@5, MRR, nDCG@10. Output is markdown + JSONL.
4. **External corpus** — optional LongMemEval-style import. The user can drop a LongMemEval JSONL into `get_documents_dir()/evals/external/` and replay scores it the same way.
5. New auto-loop entry `/loop-evals` runs nightly on the captured corpus and alerts when scores drop more than a configured threshold.
6. New MCP tools: `eval-replay`, `eval-export`, `eval-stats`, `eval-capture-status`. All default to CLI per surface-decision-matrix.

## Non-Goals

- No automatic retrieval tuning. The harness reports; humans (or active AI client) decide changes.
- No cloud-hosted eval corpus. Everything local.
- No replacement of existing test suites — eval is for retrieval quality specifically, complementary to unit/integration tests.
- No capture of vault content in eval files — only query text + returned ids + scores. Vault content stays in the vault.

## Consequences

- New skill with auto-loop entry, MCP tools, and config schema.
- `get_documents_dir()/evals/` becomes a new top-level documents subtree (user-controlled, deletable).
- ADR-738 / ADR-739 / ADR-740 each get a defensible regression baseline before shipping.
- Contributor mode is **off by default**; the user must opt in.
- Foundation for future A/B of retrieval recipes without guessing.

## Related

- ADR-738 (graph adds a retrieval axis to evaluate)
- ADR-739 (RRF tuning needs measurement)
- ADR-740 (timeline citations are an eval anchor)
- ADR-741 (skill coverage report is one ground-truth signal)
- ADR-571 (eval files use vault frontmatter conventions)
