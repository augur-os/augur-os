---
title: "Retrieval Eval Harness with Contributor Capture"
date: 2026-05-13
status: draft
scope: design
authors:
  - gsannikov
related:
  - ADR-742
  - ADR-738
  - ADR-739
  - ADR-740
  - ADR-741
  - ADR-571
  - docs/superpowers/plans/2026-05-13-gbrain-borrow-slate.md
  - docs/references/surface-decision-matrix.md
  - shared-vault/skills/knowledge/scripts/mcp/rag_search.py
  - src/mcp/augur_shared/mcp_sdk.py
tags:
  - evals
  - retrieval
  - regression
  - quality
  - benchmarking
---

# Retrieval Eval Harness with Contributor Capture

## 1. Problem

Augur has zero retrieval regression coverage today. The product value of the system is **compounded knowledge** — a wiki that "remembers" what the user has read, a `/ask` that draws on memory, a `unified-search` that fuses keyword + metadata + RAG. Once those pipelines ship the typed-graph (ADR-738), RRF fusion (ADR-739), and compiled-truth/timeline (ADR-740) changes, any regression in precision or recall will be invisible until a user notices the wiki "feels worse." That is unacceptable for a system whose only durable advantage is the integrity of its memory.

Existing test suites cover behaviour (a tool returns a list) and correctness (the index is parseable) but not **quality** (the returned list contains the right things in the right order). Quality questions cannot be answered by unit tests against synthetic fixtures — they need a corpus of real user queries with human-labeled ground truth. gbrain's reference implementation calls this the eval harness. The same pattern adapts cleanly to Augur if and only if it respects the slate-wide rules: file-first transparency, no embedded database, no Augur-side LLM calls.

This spec is the **regression contract** that Phase 3 (ADR-738/739) and Phase 4 (ADR-740/744) are tested against. Its measurement schema is the most consequential single decision in the slate.

## 2. Goals

- Add a new skill `shared-vault/skills/evals/` (hub `dev`) that owns the entire eval surface: capture, judgments, replay, reports, auto-loop, MCP tools.
- **Capture**: opt-in via `AUGUR_CONTRIBUTOR_MODE=1`. When set, retrieval-tool invocations append a query record to `get_documents_dir()/evals/queries/<YYYY-MM-DD>.jsonl`. Gated by a first-run consent flow that records user opt-in to `get_documents_dir()/evals/consent.md`.
- **Judgments**: hand-labeled relevance under `get_documents_dir()/evals/judgments/<query-id>.md` with frontmatter listing relevant doc ids. Composable — adding a judgment never rewrites a captured query.
- **Replay**: `aug eval replay [--config <path>]` reruns captured queries against the current (or supplied) retrieval config and scores P@k (k∈{1,5,10}), R@k, MRR, nDCG@10 deterministically. Output: markdown summary + JSONL raw per `get_documents_dir()/evals/reports/<run-id>/`.
- **External corpus**: drop a LongMemEval-format JSONL into `get_documents_dir()/evals/external/<corpus-id>/` and replay scores it the same way, bucketed separately in the report.
- **Auto-loop**: new entry `/loop-evals` runs nightly against the captured + external corpora; emits a delta report vs. the previous run; alerts when any metric drops by more than a configurable absolute threshold (default 5 points).
- **MCP tools** (CLI default per surface-decision-matrix): `eval-replay`, `eval-export`, `eval-stats`, `eval-capture-status`.
- Baseline of ≥ 50 captured queries with hand judgments and a recorded P@5 / R@5 / MRR / nDCG@10 number, locked under `get_documents_dir()/evals/reports/baseline/summary.md`.
- All artifacts pass the `cat <file>` transparency test.

## 3. Non-Goals

- **No automatic retrieval tuning.** The harness reports; humans (or, later, an AI client dispatch) decide what to change.
- **No cloud-hosted corpus.** Everything local. The external-corpus drop is a user-controlled file copy.
- **No vault content captured.** Eval records hold the query text, returned doc ids, ranks, scores, timestamps, and the retrieval config used. They never hold vault prose, document bodies, or LLM responses.
- **No replacement of unit/integration tests.** Eval is for retrieval quality specifically.
- **No embedded database.** All persistence is JSONL or markdown. No SQLite, PGLite, or pgvector — slate-wide rule.
- **No LLM call from Augur during capture or replay.** Capture observes; replay measures. Future label-assist via `oneshot` dispatch to the active AI client is explicitly out of v1 scope.
- **No dashboard page in v1.** v1 ships CLI + nightly loop only. A `/dev` browse card is deferred to v2, after enough captured data exists to make a card meaningful.
- **No graded relevance in v1.** Binary relevance only (0/1). Graded (0/1/2) is a v2 evolution.
- **No A/B branching of live retrieval.** `--config` lets replay swap configurations; live `unified-search` is untouched.

## 4. Design

### 4.1 Skill scaffold

```
shared-vault/skills/evals/
├── SKILL.md                              # x-augur-hub: dev, x-augur-loop, x-augur-mcp-tools
├── commands/
│   └── eval.md                           # /eval command surface (sub-verbs: replay, export, stats, capture-status, capture-consent, import-longmemeval)
├── scripts/
│   ├── __init__.py
│   ├── bootstrap_paths.py                # standard shared-skill bootstrap pattern (see rag_search.py)
│   ├── capture.py                        # capture hook + consent handling
│   ├── eval_ops.py                       # CLI entry point + loop entry
│   ├── metrics.py                        # P@k, R@k, MRR, nDCG@10, bootstrap CI
│   ├── replay.py                         # replay orchestration + determinism
│   ├── report.py                         # markdown + JSONL report writers
│   ├── records.py                        # JSONL schemas + reader/writer helpers
│   ├── longmemeval.py                    # external-corpus adapter
│   └── mcp/
│       ├── __init__.py
│       └── tools_eval.py                 # 4 MCP tools
└── augur/
    └── tests/
        ├── test_capture.py
        ├── test_metrics.py
        ├── test_replay.py
        ├── test_records.py
        ├── test_longmemeval.py
        └── test_report.py
```

`x-augur-hub: dev`. `x-augur-mcp-tools: [eval-replay, eval-export, eval-stats, eval-capture-status]`. `x-augur-loop: { name: evals, tier: 1, trigger: nightly }`. All tests use `importlib.util.spec_from_file_location` per `feedback_skill_test_convention`.

### 4.2 Capture mechanism

**Hook point.** `src/mcp/augur_shared/mcp_sdk.py::mcp_tool_interceptor` wraps every MCP tool registration. The eval skill registers a lightweight observer that the interceptor consults: if the tool name is in the capture allowlist (`unified-search`, `knowledge-project-index-search`, future additions) **and** `AUGUR_CONTRIBUTOR_MODE=1` **and** consent has been recorded, the observer appends a record after the tool returns. If any of those conditions is false, the observer is a no-op.

The observer is registered in `capture.py` and pulled into `mcp_sdk.py` via a single import-time call (`register_capture_observer()`), so the interceptor logic in `mcp_sdk.py` gains one method call and otherwise stays unchanged. The observer never raises into the tool path: any capture failure logs at WARN and is swallowed, so a broken eval skill cannot break live search.

**Caller tagging.** `/ask` is implemented in `plugins/augur/skills/ask/` and dispatches into `unified-search` for its retrieval phase. To avoid double-capture, we capture **only at the retrieval-tool boundary**, and tag the record with a `source` field derived from a contextvar `_ACTIVE_CALLER` that callers (e.g., the `/ask` command body, the dashboard MCP client) may set before invoking the tool. When unset, `source = "direct"`.

**Consent gating.** First call with `AUGUR_CONTRIBUTOR_MODE=1` checks for `get_documents_dir()/evals/consent.md`:
- If present (any non-empty content), capture proceeds.
- If absent, the observer writes a one-line WARNING to stderr describing what would be captured and instructs the user to run `aug eval capture-consent` (which writes `consent.md` with a UTC timestamp and the explicit terms). **No data is captured until consent.md exists.** The contributor-mode env var alone is not enough — explicit file is required.

**Toggle granularity.** The env var is read per-call (not cached at import time), so the user can flip mode mid-session without a daemon restart.

### 4.3 File layouts (the regression contract)

These shapes are normative. Every later ADR that touches retrieval is tested against these formats.

#### 4.3.1 Query record — one JSONL line per call

```json
{
  "_schema": "eval.query.v1",
  "id": "<sha1(query+source)[:12]>",
  "ts": "2026-05-13T03:00:00Z",
  "query": "what did I read about typed knowledge graphs last week",
  "source": "/ask",
  "tool": "unified-search",
  "mode": "hybrid",
  "top_k": 10,
  "scopes": ["memory", "knowledge", "rag"],
  "project": null,
  "returned": [
    {"id": "vault://wiki/typed-knowledge-graphs", "rank": 1, "score": 0.83},
    {"id": "source-cards://2026-05-08/gbrain-borrow-notes", "rank": 2, "score": 0.71}
  ],
  "retrieval_config": {
    "augur_commit": "abc1234",
    "vault_manifest_hash": "deadbeef0123",
    "rrf_k": null,
    "rrf_weights": null
  },
  "duration_ms": 142
}
```

- `id` is a content hash of `query + source`. Same query from the same caller folds into the same id, so adding a judgment for `id=X` covers every future invocation of `X`. Replay deduplicates by id.
- `returned` is ranked, top_k or fewer. `id` strings are stable doc identifiers (`vault://...`, `source-cards://...`, `rag://...`); the field is never document body text.
- `retrieval_config.augur_commit` is the HEAD sha at capture time. `vault_manifest_hash` is `sha256(sorted(<relpath>:<mtime_ns> for each vault file))[:12]`. Together they define the index state for deterministic replay.
- `rrf_k` and `rrf_weights` are reserved for ADR-739; v1 records `null`.

Files: `get_documents_dir()/evals/queries/<YYYY-MM-DD>.jsonl`. Append-only. Daily rotation, no fsync per line — captured queries are recoverable from logs if a tail is corrupted; the file's tail being torn never affects the prefix.

#### 4.3.2 Judgment file — one markdown file per query id

```markdown
---
_schema: eval.judgment.v1
query_id: a1b2c3d4e5f6
query: "what did I read about typed knowledge graphs last week"
relevant_doc_ids:
  - vault://wiki/typed-knowledge-graphs
  - source-cards://2026-05-08/gbrain-borrow-notes
  - source-cards://2026-05-10/gbrain-rrf-design
labeled_by: gsannikov
labeled_at: 2026-05-13T10:00:00Z
notes: "the third hit is the original gbrain RRF derivation"
---

# (free-form notes optional after frontmatter)
```

Files: `get_documents_dir()/evals/judgments/<query-id>.md`. Editable by hand. Replay reads frontmatter only; the markdown body is freeform.

#### 4.3.3 Replay report — directory per run

```
get_documents_dir()/evals/reports/<run-id>/
├── summary.md                # human-readable
├── raw.jsonl                 # per-query result rows
└── manifest.json             # run metadata: timestamp, commit, config, query-set hash
```

`<run-id> = <YYYY-MM-DD-HHMMSS>-<commit[:7]>`. The directory `get_documents_dir()/evals/reports/baseline/` is reserved (a stable symlink the user creates pointing at the chosen baseline run).

`summary.md` includes overall numbers, per-source breakdown (`/ask` vs `unified-search` vs external corpus), and a delta table vs. the prior run when one exists. `raw.jsonl` has one line per scored query — sufficient to recompute aggregates without rerunning replay.

#### 4.3.4 Schema versioning

Every persistent shape carries a `_schema` field. Bumping is a contract change and requires a migration script — never silent.

### 4.4 Metric definitions (the regression contract, continued)

All metrics are computed **per query** then aggregated as the unweighted mean across queries with at least one labeled relevant doc. Queries with zero labeled relevant docs are skipped for P/R/MRR/nDCG (any retrieved doc would be wrong by definition, so they don't measure retrieval quality — they measure a labeling gap, which is surfaced separately as `unlabeled_queries` in the report).

Let `R` = set of relevant doc ids for a query (from the judgment file), `retrieved` = the ranked list of returned doc ids from replay, `top_k = retrieved[:k]`.

#### 4.4.1 Precision at k

```
P@k = |set(top_k) ∩ R| / k
```

Note: denominator is **k**, not `min(k, |retrieved|)`. If the system returns fewer than k results, the missing slots count as non-relevant. This matches gbrain and the IR literature; it also penalizes a retrieval system that returns too few.

#### 4.4.2 Recall at k

```
R@k = |set(top_k) ∩ R| / |R|
```

Undefined when `|R| == 0` → query is skipped (counted under `unlabeled_queries`).

#### 4.4.3 Mean reciprocal rank

```
MRR = 1 / rank_of_first_relevant_in_retrieved
    = 0 if no relevant doc appears in `retrieved`
```

`rank_of_first_relevant` is 1-indexed. MRR is computed over the **full** `retrieved` list, not just top_k — a relevant doc at rank 50 still produces 1/50 rather than 0.

#### 4.4.4 nDCG@10

Binary relevance, gain ∈ {0, 1}:

```
DCG@10 = sum over i in [1..10] of (gain_i / log2(i + 1))
IDCG@10 = sum over i in [1..min(10, |R|)] of (1 / log2(i + 1))
nDCG@10 = DCG@10 / IDCG@10   (1.0 if IDCG@10 == 0, i.e. |R|==0 → query skipped)
```

#### 4.4.5 Aggregation and variance

For each metric, the report records:
- **mean** across non-skipped queries (the headline number)
- **stderr** = stdev / sqrt(n) (cheap, used by the loop alert)
- **bootstrap_ci_95** = (lo, hi) over 1000 resamples (paid only on baseline + nightly summary, not every replay)

#### 4.4.6 Per-bucket breakdown

The summary table is repeated for: overall, per `source` (`/ask` / `unified-search` / `direct`), per `tool` (when more than one), per `mode` (record raw value; ADR-739 introduces semantic meaning), per corpus (captured vs. each external corpus id).

### 4.5 Replay determinism

`aug eval replay`:

1. Loads queries from `get_documents_dir()/evals/queries/*.jsonl`, deduplicated by `id` (last write wins per day; cross-day duplicates collapse to the most recent record).
2. Loads judgments from `get_documents_dir()/evals/judgments/*.md`.
3. For each query, calls the recorded `tool` with the recorded `query`, `mode`, `top_k`, `scopes`, `project` — **not** the same returned set, because the point of replay is to test current retrieval.
4. Scores the new `retrieved` list against `R`.
5. Writes the report.

**Determinism conditions:**
- Same `augur_commit` → same code path.
- Same `vault_manifest_hash` → same index state. If the live manifest differs from the recorded one, replay still runs but the report flags `index_drift: true` and surfaces the diff (added/removed/modified count). Drift is a strong signal that the baseline number is no longer comparable.
- If a retrieval path uses randomness (e.g., a sampled approximation), the path must seed its RNG from `query.id`. This is enforced as a code review check, not a runtime assertion; the spec records the requirement so ADR-738/739 implementers respect it.

`--config <path>` overrides the recorded retrieval params with a YAML config — for A/B testing a tuning change without losing the captured baseline.

### 4.6 LongMemEval import

`scripts/longmemeval.py` reads a LongMemEval-format JSONL (one entry per question, fields `question`, `answer`, `evidence_doc_ids`, `corpus_id`) and emits matching `query.v1` + `judgment.v1` records under `get_documents_dir()/evals/external/<corpus-id>/queries/`, `.../judgments/`. The corpus is replayed alongside captured queries; results are bucketed under `corpus = "<corpus-id>"` in the report. The repo never vendors the corpus — the user drops files in.

A small adapter contract document under `shared-vault/skills/evals/references/longmemeval-format.md` records the expected fields and the mapping, so a future corpus in a different schema gets a parallel adapter rather than mutating the import code.

### 4.7 `/loop-evals` auto-loop

- Registered via `x-augur-loop` in `SKILL.md` — tier 1, trigger nightly.
- Runs `aug eval replay` against the captured corpus + every present external corpus.
- Writes a new report directory under `get_documents_dir()/evals/reports/<run-id>/`.
- Computes a delta vs. the symlinked baseline (or the most recent prior run if no baseline is set).
- **Alert rule (v1):** if any of `P@5_mean`, `R@5_mean`, `MRR_mean`, `nDCG@10_mean` drops by `> 5.0` absolute points vs. baseline, the loop emits an event with severity WARN (configurable per metric in `shared-vault/skills/evals/config.yaml`).
- Loop result stays green in v1 regardless of alert severity (`/loop-evals` is report-only initially; CI-blocking is a v2 evolution after one stabilization release, mirroring the ADR-741 pattern).

### 4.8 MCP tools

All four tools annotate `readOnlyHint: True`. Primary surface CLI per surface-decision-matrix; none default to dashboard exposure in v1.

| Tool | Inputs | Returns |
|---|---|---|
| `eval-capture-status` | (none) | JSON: `{enabled: bool, consent: bool, queries_captured_total: int, queries_today: int, last_capture_ts: iso8601 \| null}` |
| `eval-export` | `since: iso8601 \| null`, `until: iso8601 \| null` | JSON: `{export_path: str, query_count: int, judgment_count: int}` — bundles a date range into a portable zip under `get_documents_dir()/evals/exports/<run-id>.zip` |
| `eval-replay` | `config: str \| null`, `corpus: "captured" \| "external" \| "all" = "all"`, `since: iso8601 \| null` | JSON: `{run_id: str, summary_path: str, scores: {P_at_5_mean: float, ...}}` |
| `eval-stats` | `run_id: str \| null` (default: most recent) | JSON: parsed `summary.md` numbers |

All four tools are entries in `config/system/capability_exposure.yaml` (per `feedback_command_capability_entry`) with `primary_surface: cli`, `export_to: [cli, agents-md]`, `owner_kind: augur`, `management: generated`, `classification_status: approved`.

The `/eval` command surface (sub-verbs above) is also registered in `capability_exposure.yaml` as `command:eval:` with `primary_surface: cli`, `export_to: [cli, agents-md, claude, codex]`.

### 4.9 Bootstrap seeding (so the baseline isn't empty)

The Phase 2 gate requires ≥ 50 captured baseline queries. To reach that without waiting on organic user use:

- The plan includes a one-time script `scripts/seed_baseline.py` that reads a small hand-authored YAML at `shared-vault/skills/evals/references/baseline-seed-queries.yaml` (≥ 50 queries the user expects the system to answer well today), runs each through `unified-search` once with capture mode on, and prompts the user (or the active AI client via `oneshot` — out of v1 scope, manual in v1) to author judgments.
- The seed list is checked into the repo as the canonical "Augur's user expects these to work" reference set. It does not contain vault content — just the query strings.

## 5. Boundary

- Pure Python stdlib + PyYAML. No new runtime dependencies.
- File-only persistence: append-only JSONL for captured queries, markdown for judgments and reports.
- No mutations to the vault, no writes outside `get_documents_dir()/evals/`.
- No LLM calls.
- All paths via `src.config.paths` helpers.
- All tests via `/auto-test-pytest`. No raw `pytest`.
- Capture hook is a no-op when `AUGUR_CONTRIBUTOR_MODE` is unset or consent is missing — the env-var-off path is the default; off-mode has zero observable effect on tool latency beyond a single env-var read and a contextvar lookup.

## 6. Open Questions

| # | Question | Resolution |
|---|---|---|
| 1 | Capture granularity for `/ask` | Once at `unified-search` boundary with `source` tag derived from contextvar. (Resolved in §4.2.) |
| 2 | Query id scheme | Content hash `sha1(query+source)[:12]`. Judgments compose, duplicates merge. (Resolved in §4.3.1.) |
| 3 | Relevance grading | Binary (0/1) in v1; graded (0/1/2) deferred. (Resolved in §3 + §4.4.) |
| 4 | Consent UX | Stderr banner + `aug eval capture-consent` writes file; env var alone is insufficient. (Resolved in §4.2.) |
| 5 | Replay determinism scope | Index manifest hash (mtime-based) + commit; full vault snapshot rejected as too heavy. Drift flagged but not blocking. (Resolved in §4.5.) |
| 6 | External corpus storage | User-supplied drop under `get_documents_dir()/evals/external/`; repo never vendors. (Resolved in §4.6.) |
| 7 | Loop alert threshold | 5 absolute points default per metric, configurable in skill `config.yaml`. (Resolved in §4.7.) |
| 8 | Dashboard surface in v1 | Defer entirely. v2 ADR addendum after enough captured data exists. (Resolved in §3.) |
| 9 | What about `knowledge-project-index-search`? | Allowlist includes it from v1 (it's a real retrieval surface). Captured records carry `tool: "knowledge-project-index-search"` and bucket separately in reports. |
| 10 | What if a query has labeled relevant docs that retrieval can no longer return (deleted from vault)? | Replay's `index_drift` flag surfaces this; query is still scored (relevant doc is simply not retrievable → contributes 0 to P/R/MRR/nDCG). Loop alert is responsible for surfacing drift-driven regressions vs. retrieval-driven regressions; v1 reports them as one number and notes the drift, v2 may separate. |
| 11 | RRF / ADR-739 / ADR-738 forward compat | `mode` is captured raw. `rrf_k`/`rrf_weights` are reserved fields, null in v1. New retrieval params extend `retrieval_config` without bumping `_schema` provided they're additive. Schema bump only required if a captured field's meaning changes. |
| 12 | `aug eval` CLI vs. `/eval` slash command | Both exist. `aug eval <verb>` is the canonical shell command (matches existing `aug <skill>` pattern). `/eval` is the slash-command projection per `capability_exposure.yaml` — same verbs, projected to every client. |

## 7. Acceptance Criteria (mirrored in the plan)

- [ ] New skill `shared-vault/skills/evals/` exists with `SKILL.md`, `commands/eval.md`, scripts, MCP tools, and `augur/tests/`.
- [ ] `AUGUR_CONTRIBUTOR_MODE=1` + `consent.md` present → calls to `unified-search` and `knowledge-project-index-search` append `eval.query.v1` records to `get_documents_dir()/evals/queries/<YYYY-MM-DD>.jsonl`.
- [ ] `AUGUR_CONTRIBUTOR_MODE=0` (or unset) → zero capture, zero file growth, zero observable latency change beyond env-var read.
- [ ] `aug eval capture-consent` writes `consent.md` with timestamp; subsequent capture proceeds. Without the file, capture is suppressed and a one-line stderr instruction appears.
- [ ] `/ask` invocations are captured with `source: "/ask"`; direct dashboard calls with `source: "direct"`; double-capture impossible.
- [ ] Judgment file frontmatter is parseable per `eval.judgment.v1` shape; judgments can be added/edited by hand.
- [ ] `aug eval replay` produces `<report-dir>/summary.md` + `<report-dir>/raw.jsonl` + `<report-dir>/manifest.json` with the schemas in §4.3.3.
- [ ] Replay is deterministic given the same `augur_commit` + `vault_manifest_hash`: two consecutive replays produce byte-identical `raw.jsonl` ordering and identical aggregate numbers.
- [ ] Metrics implementations match §4.4 exactly: P@k uses `k` (not `min(k, |retrieved|)`) as denominator; MRR uses the full retrieved list; nDCG@10 uses binary gain.
- [ ] Bootstrap 95% CI computed for baseline and nightly summary; cheap stderr for every replay.
- [ ] `scripts/seed_baseline.py` produces ≥ 50 captured baseline queries when run against `references/baseline-seed-queries.yaml`.
- [ ] Baseline P@5 / R@5 / MRR / nDCG@10 recorded at `get_documents_dir()/evals/reports/baseline/summary.md`.
- [ ] `/loop-evals` registered and runs nightly in report-only mode; produces a delta report vs. baseline; emits an alert event when any metric drops > 5 absolute points; loop result stays green.
- [ ] LongMemEval adapter converts a sample LongMemEval JSONL into the v1 query/judgment shape and replays it; report buckets external corpus separately.
- [ ] 4 MCP tools registered with `readOnlyHint: True`. CLI default. Entries in `capability_exposure.yaml` for tools and the `command:eval:` surface.
- [ ] Tests cover: capture on/off/consent transitions; each metric calculation against worked examples; replay determinism; record schema validation; LongMemEval adapter; report markdown rendering. All via `/auto-test-pytest`.
- [ ] No embedded DB. No LLM call from Augur during capture or replay. All paths via `src.config.paths`. Off-mode is the default.
- [ ] `/auto-lint` green; `/auto-test-pytest` green; `/dev-build` succeeds (no dashboard changes, so the build is a quick sanity check, not a deep verification).

## 8. Forward compatibility

The slate's later ADRs extend this harness rather than replace it:

- **ADR-738 (typed graph)**: `retrieval_config` gains optional `graph_axis_weight`; `_schema` does not bump.
- **ADR-739 (RRF + modes)**: `mode` values acquire semantic meaning (`conservative`/`balanced`/`tokenmax`); `rrf_k` and `rrf_weights` populate; per-mode breakdown in §4.4.6 starts being interesting.
- **ADR-740 (compiled-truth + timeline)**: a new retrievable doc-id namespace (`timeline://`); replay scoring is unchanged.
- **ADR-744 (dream cycle)**: emits queries via the same capture allowlist, just with a new `source: "dream-cycle"`.

The eval contract is intentionally minimal and additive. Any breaking change is a `_schema` bump and a migration script — never silent.

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Capture hook becomes a hidden global side effect that complicates debugging unrelated retrieval issues | Off-by-default; single import-time registration in `mcp_sdk.py`; observer is a no-op when env unset or consent missing; failures are caught and logged WARN. |
| Baseline numbers ossify and become a ceiling rather than a floor | Baseline is a user-managed symlink, not enforcement; loop alerts on regressions but never blocks merges in v1. |
| Hand-labeling is too costly to reach 50 queries | Seed list is hand-authored once; future label-assist via `oneshot` dispatch is a v2 follow-up. |
| Replay non-determinism from unseeded randomness in retrieval code | Documented requirement in §4.5; ADR-738/739 implementers obligated to seed; replay surfaces variance via `bootstrap_ci_95` so non-det shows up as wide CIs. |
| `vault_manifest_hash` becomes expensive on large vaults | Hash of `(relpath, mtime_ns)` tuples is O(n) file stats, no reads; sub-second on a 10k-file vault. If it ever becomes a bottleneck, switch to a sampled hash. |
| External corpora drift from the LongMemEval format upstream | Adapter is a thin file with one contract doc; new format = new adapter, no impact on core. |

## 10. Rollback

- Revert merge commit(s).
- Remove the four `mcp-tool:eval-*` entries and `command:eval:` from `capability_exposure.yaml`.
- Remove the capture observer registration from `mcp_sdk.py` (one line).
- Delete the skill directory `shared-vault/skills/evals/`.
- Optionally delete `get_documents_dir()/evals/` (the user's captured data is preserved by default — rollback does not destroy data).

No schema migration, no vault touch. Rollback is clean and reversible.
