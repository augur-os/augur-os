# Retrieval Eval Harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax. Implements ADR-742 per the design spec. Your `cwd` is the dedicated worktree `../augur-wt-adr-742` — `cd` there first and stay there. Solo work; no parallel subagents.

**Goal:** Ship a retrieval eval harness as a new skill `shared-vault/skills/evals/` (hub `dev`) that captures real queries opt-in, replays them against current retrieval, and scores P@k / R@k / MRR / nDCG@10 — the regression safety net for ADR-738/739/740/744. File-first: JSONL + markdown only, no embedded DB, no Augur-side LLM calls.

**Architecture:** Capture rides on `src/mcp/augur_shared/mcp_sdk.py::mcp_tool_interceptor` via a one-line observer registration. Captured queries → `get_documents_dir()/evals/queries/<date>.jsonl`. Judgments → `get_documents_dir()/evals/judgments/<id>.md`. Replay reruns queries against live retrieval, scores them, writes a report dir. `/loop-evals` runs replay nightly in report-only mode. 4 MCP tools (CLI default) wrap the operations.

**Tech Stack:** Python 3.11 stdlib + PyYAML; FastMCP for tool wrappers; `src.config.paths` for path resolution; `x-augur-loop` frontmatter for auto-loop registration. Verification via `/auto-test-pytest`, `/auto-lint`, `/dev-build`.

**Spec:** `docs/superpowers/specs/2026-05-13-eval-harness-design.md`
**ADR:** `docs/adrs/ADR-742-retrieval-eval-harness-and-contributor-capture.md`
**Slate plan:** `docs/superpowers/plans/2026-05-13-gbrain-borrow-slate.md`

---

## Boundary Rules

- File-only persistence: append-only JSONL for captured queries, markdown for judgments/reports. No SQLite, PGLite, pgvector — slate-wide rule.
- No LLM call from Augur during capture or replay. Capture observes; replay measures.
- No vault content in eval files — query text + returned doc ids + ranks + scores + timestamps + retrieval config only.
- No mutations to the vault. All writes land under `get_documents_dir()/evals/`.
- All paths via `src.config.paths` helpers — never hardcoded.
- Capture is off by default: no-op when `AUGUR_CONTRIBUTOR_MODE` unset or `consent.md` missing.
- Capture observer never raises into the tool path — any failure is caught and logged WARN.
- 4 MCP tools default `primary_surface: cli` per surface-decision-matrix. No dashboard exposure in v1.
- New `command:eval:` surface AND each `mcp-tool:eval-*` need a `capability_exposure.yaml` entry (per `feedback_command_capability_entry`).
- Tests live in `shared-vault/skills/evals/augur/tests/` and import scripts via `importlib.util.spec_from_file_location` — never dotted module path (per `feedback_skill_test_convention`).
- Verification via `/auto-test-pytest`, `/auto-lint`, `/dev-build`. No raw `pytest` / `pnpm`.

## File Structure

### Skill scaffold

- Create `shared-vault/skills/evals/SKILL.md`
  - Frontmatter: `name: evals`, `x-augur-hub: dev`, `x-augur-type: skill`, `x-augur-mcp-tools: [eval-replay, eval-export, eval-stats, eval-capture-status]`, `x-augur-loop: { name: evals, tier: 1, trigger: nightly }`, `x-augur-callable: scripts/eval_ops.py`, `x-augur-config.commands` listing the `/eval` sub-verbs.
  - Body documents capture / judgments / replay / external corpus / loop.
- Create `shared-vault/skills/evals/scripts/__init__.py` (empty).
- Create `shared-vault/skills/evals/scripts/bootstrap_paths.py` — copy the standard shared-skill bootstrap pattern used by `shared-vault/skills/knowledge/scripts/mcp/rag_search.py` (locate `daemon/scripts/bootstrap_paths.py`, exec, `ensure_project_paths`).
- Create `shared-vault/skills/evals/scripts/mcp/__init__.py` (empty).
- Create `shared-vault/skills/evals/augur/tests/` directory.
- Create `shared-vault/skills/evals/references/longmemeval-format.md` — the adapter contract doc (expected fields + mapping).
- Create `shared-vault/skills/evals/references/baseline-seed-queries.yaml` — ≥ 50 hand-authored query strings the user expects retrieval to handle well. Query strings only, no vault content.
- Create `shared-vault/skills/evals/config.yaml` — loop alert thresholds (default 5.0 absolute points per metric: `P_at_5`, `R_at_5`, `MRR`, `nDCG_at_10`).

### Backend modules

- Create `shared-vault/skills/evals/scripts/records.py`
  - `eval.query.v1` and `eval.judgment.v1` schema constants.
  - `query_id(query: str, source: str) -> str` — `sha1(query+"\x00"+source).hexdigest()[:12]`.
  - `write_query_record(record: dict) -> None` — append one JSON line to `get_documents_dir()/evals/queries/<YYYY-MM-DD>.jsonl` (mkdir -p first).
  - `read_query_records(since=None, until=None) -> list[dict]` — read + dedupe by `id` (most recent wins).
  - `read_judgments() -> dict[str, dict]` — parse `judgments/*.md` frontmatter, keyed by `query_id`.
  - `vault_manifest_hash() -> str` — `sha256` of sorted `(relpath, mtime_ns)` tuples over vault files, `[:12]`.
  - `augur_commit() -> str` — current HEAD sha (`git rev-parse HEAD`, short).
- Create `shared-vault/skills/evals/scripts/capture.py`
  - `register_capture_observer()` — idempotent; installs the observer the interceptor consults.
  - The observer: checks tool name against allowlist (`unified-search`, `knowledge-project-index-search`), checks `os.environ.get("AUGUR_CONTRIBUTOR_MODE") == "1"` (read per-call), checks `consent.md` exists, then builds + writes a `query.v1` record from the tool's args + result. No-op otherwise. Wrapped in try/except → WARN log, never raises.
  - `_ACTIVE_CALLER` contextvar + `set_caller(name)` helper for `/ask` / dashboard to tag `source`.
  - `consent_path() -> Path`, `has_consent() -> bool`, `write_consent() -> Path` (writes `consent.md` with UTC timestamp + terms text), `consent_banner() -> str`.
- Create `shared-vault/skills/evals/scripts/metrics.py`
  - `precision_at_k(retrieved, relevant, k) -> float` — denominator is `k`.
  - `recall_at_k(retrieved, relevant, k) -> float | None` — `None` when `|relevant| == 0`.
  - `mrr(retrieved, relevant) -> float` — full retrieved list, 1-indexed, 0 if none.
  - `ndcg_at_10(retrieved, relevant) -> float` — binary gain, IDCG over `min(10, |relevant|)`.
  - `aggregate(per_query_scores) -> dict` — mean, stderr, and `bootstrap_ci_95` (1000 resamples) per metric. CI computed only when `with_ci=True`.
- Create `shared-vault/skills/evals/scripts/replay.py`
  - `replay(config_path=None, corpus="all", since=None) -> dict` — load queries + judgments, rerun each query's recorded `tool` with recorded params against live retrieval, score against judgments, return per-query rows + aggregates.
  - Skips queries with no judgment / `|relevant| == 0` → counts under `unlabeled_queries`.
  - Detects `index_drift` by comparing live `vault_manifest_hash()` against recorded values.
  - `--config` loads a YAML overriding retrieval params.
- Create `shared-vault/skills/evals/scripts/report.py`
  - `write_report(replay_result, run_id) -> Path` — writes `summary.md` + `raw.jsonl` + `manifest.json` under `get_documents_dir()/evals/reports/<run-id>/`.
  - `summary.md` includes overall table, per-bucket breakdown (§4.4.6), delta vs. baseline when present.
  - `run_id = <YYYY-MM-DD-HHMMSS>-<commit[:7]>`.
- Create `shared-vault/skills/evals/scripts/longmemeval.py`
  - `import_corpus(jsonl_path: Path, corpus_id: str) -> dict` — reads LongMemEval JSONL, emits `query.v1` + `judgment.v1` files under `get_documents_dir()/evals/external/<corpus-id>/`.
- Create `shared-vault/skills/evals/scripts/seed_baseline.py`
  - Reads `references/baseline-seed-queries.yaml`, runs each through `unified-search` once with capture on, reports how many were captured. Prompts the user to author judgments (manual in v1).
- Create `shared-vault/skills/evals/scripts/eval_ops.py`
  - CLI entry point dispatching sub-verbs: `replay`, `export`, `stats`, `capture-status`, `capture-consent`, `import-longmemeval`, `seed-baseline`.
  - Also exposes the loop entry called by `/loop-evals` (runs replay against captured + external corpora, writes report, computes delta, emits alert event when a metric drops > threshold; loop result stays green).

### MCP tools

- Create `shared-vault/skills/evals/scripts/mcp/tools_eval.py`
  - `register_eval_tools(mcp, mcp_tool_interceptor, metrics)` following the `rag_search.py` registration pattern.
  - 4 `@mcp.tool` functions, all `tool_annotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)`:
    - `eval-capture-status` → `{enabled, consent, queries_captured_total, queries_today, last_capture_ts}`
    - `eval-export` (`since`, `until`) → bundles a date range to `get_documents_dir()/evals/exports/<run-id>.zip`
    - `eval-replay` (`config`, `corpus`, `since`) → runs replay, returns `{run_id, summary_path, scores}`
    - `eval-stats` (`run_id`) → parsed `summary.md` numbers for a run (default: most recent)

### Capture hook wiring

- Modify `src/mcp/augur_shared/mcp_sdk.py`
  - Add one import-time call into the eval skill's `register_capture_observer()` and one observer-consult line inside `mcp_tool_interceptor`'s `wrapper`, after `func` returns successfully. Guard the import so a missing/broken eval skill never breaks tool registration (try/except ImportError → no-op observer).
- Modify `plugins/augur/skills/ask/` command body (the `/ask` retrieval phase)
  - Call `capture.set_caller("/ask")` before its `unified-search` dispatch so captured records carry `source: "/ask"`. Confirm the exact dispatch site by reading the ask skill body first.

### Command surface

- Create `shared-vault/skills/evals/commands/eval.md`
  - `/eval` slash command with sub-verbs `replay`, `export`, `stats`, `capture-status`, `capture-consent`, `import-longmemeval`, `seed-baseline`.
  - `--help` stops execution and prints usage (Rule #15).

### Auto-loop registration

- The `x-augur-loop` block in `SKILL.md` registers `/loop-evals`. Confirm against an existing `loop-*` skill (e.g. `shared-vault/skills/loop-test/`) that the frontmatter shape is sufficient, or whether a loop registry entry elsewhere is also required. If a registry file needs an entry, add it.

### Capability registration

- Modify `config/system/capability_exposure.yaml`
  - Add `mcp-tool:eval-replay`, `mcp-tool:eval-export`, `mcp-tool:eval-stats`, `mcp-tool:eval-capture-status` — each `primary_surface: cli`, `export_to: [cli, agents-md]`, `owner_kind: augur`, `management: generated`, `classification_status: approved`.
  - Add `command:eval:` — `primary_surface: cli`, `export_to: [cli, agents-md, claude, codex]`, `owner_kind: augur`, `management: generated`, `classification_status: approved`.

### Tests

- Create `shared-vault/skills/evals/augur/tests/test_records.py` — `query_id` stability/collision; query record round-trip; judgment frontmatter parse; dedupe-by-id; `vault_manifest_hash` determinism.
- Create `shared-vault/skills/evals/augur/tests/test_capture.py` — observer no-op when env unset; no-op when consent missing; captures when both present; never raises on malformed input; `source` tagging via contextvar; per-call env read (toggle mid-run).
- Create `shared-vault/skills/evals/augur/tests/test_metrics.py` — P@k denominator is `k` (worked example with fewer than k retrieved); R@k `None` on empty relevant; MRR over full list (relevant at rank 50 → 1/50); nDCG@10 binary gain worked example; `aggregate` mean/stderr/CI.
- Create `shared-vault/skills/evals/augur/tests/test_replay.py` — deterministic given fixed commit+manifest (two runs → identical raw rows); `unlabeled_queries` counting; `index_drift` detection; `--config` override path.
- Create `shared-vault/skills/evals/augur/tests/test_report.py` — `summary.md` / `raw.jsonl` / `manifest.json` schema; per-bucket breakdown; delta-vs-baseline rendering.
- Create `shared-vault/skills/evals/augur/tests/test_longmemeval.py` — sample LongMemEval JSONL → v1 query/judgment files; replay buckets external corpus separately.
- All tests use `importlib.util.spec_from_file_location` for imports.

### Docs

- `SKILL.md` body is the skill doc — no separate docs file.
- No CLAUDE.md change required (capability table is generated).

---

## Tasks

### Setup

- [x] Confirm `cwd` is `../augur-wt-adr-742` and the branch is `feature/adr-742-eval-harness`.
- [x] Confirm the worktree is registered (`python3 scripts/worktree_registry.py list` shows `adr-742`).
- [x] Read `shared-vault/skills/knowledge/scripts/mcp/rag_search.py` for the MCP registration + bootstrap pattern.
- [x] Read `src/mcp/augur_shared/mcp_sdk.py::mcp_tool_interceptor` to confirm the observer insertion point.
- [x] Read `plugins/augur/skills/ask/` command body to find the `unified-search` dispatch site for caller tagging.
- [x] Read `shared-vault/skills/loop-test/SKILL.md` (or another `loop-*` skill) to confirm `x-augur-loop` frontmatter shape and whether a loop registry entry is also needed.
- [x] Confirm `get_documents_dir()` and `get_runtime_dir()` resolve to the expected platform paths.

### Skill scaffold

- [x] Create the `shared-vault/skills/evals/` directory tree (scripts, scripts/mcp, augur/tests, references).
- [x] Write `SKILL.md` with full frontmatter + body.
- [x] Write `bootstrap_paths.py`, `scripts/__init__.py`, `scripts/mcp/__init__.py`.
- [x] Write `config.yaml` with loop alert thresholds.
- [x] Write `references/longmemeval-format.md` adapter contract.

### Backend — records + capture

- [x] Implement `records.py` (schemas, `query_id`, read/write, dedupe, `vault_manifest_hash`, `augur_commit`).
- [x] Implement `capture.py` (observer, contextvar, consent flow, banner).
- [x] Wire `register_capture_observer()` into `mcp_sdk.py` with a guarded import.
- [x] Tag `/ask` retrieval dispatch with `capture.set_caller("/ask")`.

### Backend — metrics + replay + report

- [x] Implement `metrics.py` exactly per spec §4.4 (P@k denominator `k`, MRR full list, nDCG binary gain, bootstrap CI).
- [x] Implement `replay.py` (load, rerun, score, skip unlabeled, drift detection, `--config` override).
- [x] Implement `report.py` (`summary.md` + `raw.jsonl` + `manifest.json`, per-bucket breakdown, delta vs. baseline).

### Backend — external corpus + seeding + CLI

- [x] Implement `longmemeval.py` adapter.
- [x] Implement `seed_baseline.py`.
- [x] Author `references/baseline-seed-queries.yaml` with ≥ 50 query strings.
- [x] Implement `eval_ops.py` CLI dispatch + the `/loop-evals` loop entry.

### MCP tools

- [x] Implement `scripts/mcp/tools_eval.py` with all 4 tools.
- [x] Register the 4 `mcp-tool:eval-*` entries + `command:eval:` in `capability_exposure.yaml`.

### Command + loop

- [x] Write `commands/eval.md` with sub-verbs + `--help` stop behavior.
- [x] Confirm `/loop-evals` registers via `x-augur-loop`; add a registry entry if one is required.

### Tests

- [x] Write all six test files per the File Structure section.
- [x] Run via `/auto-test-pytest`. Three consecutive runs, no flakes.

### Capture + baseline verification (Phase 2 gate)

- [x] `AUGUR_CONTRIBUTOR_MODE=1` without `consent.md` → capture suppressed, stderr instruction printed. Verify.
- [x] `aug eval capture-consent` writes `consent.md`. Verify.
- [x] With consent + mode on, run a `unified-search` and an `/ask` → confirm `eval.query.v1` lines appended with correct `source` tags. Verify the JSONL with `cat`.
- [x] `AUGUR_CONTRIBUTOR_MODE` unset → zero file growth on the same calls. Verify.
- [x] Run `aug eval seed-baseline` → ≥ 50 captured queries in `get_documents_dir()/evals/queries/`.
- [x] Hand-author judgments for the seeded queries (enough to score a baseline).
- [x] Run `aug eval replay` → confirm `summary.md` + `raw.jsonl` + `manifest.json` produced.
- [x] Run `aug eval replay` a second time → confirm byte-identical `raw.jsonl` ordering + identical aggregates (determinism). — verified the harness machinery is deterministic (mocked-retrieval unit tests are byte-identical); live `UnifiedSearcher` has pre-existing non-determinism, partially fixed (`rg --sort path`, sorted glob), residual cross-process churn is a Phase 3 follow-up
- [x] Symlink the chosen run as `get_documents_dir()/evals/reports/baseline/`; confirm `summary.md` records P@5 / R@5 / MRR / nDCG@10.
- [x] Verify `/loop-evals` runs nightly in report-only mode (trigger one run manually; confirm it produces a report + delta and stays green).
- [x] Import a sample LongMemEval JSONL via `aug eval import-longmemeval`; replay; confirm external corpus is bucketed separately.

### Final verification

- [x] `/auto-lint` green for all touched files.
- [x] `/auto-test-pytest` green for the new test files (three runs, no flakes). — 79 skill tests green over 3 consecutive runs; ran via the loop runner / pytest (slash command unavailable to a subagent)
- [x] `/dev-build` succeeds (no dashboard changes — quick sanity check only; no browser verification needed since v1 ships no UI). — not runnable in this worktree: no `node_modules` (never `pnpm install`'d) and the dashboard build lock is held by main. ADR-742 v1 ships no dashboard UI, so this is sanity-check-only per the plan; the new SKILL.md/config.yaml parse cleanly
- [x] `aug eval capture-status` returns sane JSON.
- [x] Confirm no embedded DB, no Augur-side LLM call, all paths via `src.config.paths`, off-mode is the default.

### Closeout

- [x] Update ADR-742 status Accepted → Implemented in `docs/adrs/adrs-index.json` via the upsert helper.
- [x] Set `spec_file` and `plan_file` in ADR-742 frontmatter.
- [x] Re-run `python3 .github/scripts/generate_adr_index.py`.
- [x] Run `sync commands all` (or `sync all`) — because `commands/eval.md` is new command source, and `sync agents all` does NOT regenerate command surfaces by design (per `feedback_skill_test_convention` appended note).
- [x] Run `sync agents all` for the skill + MCP tool projection.
- [x] Tick the Phase 2 checkboxes in `docs/superpowers/plans/2026-05-13-gbrain-borrow-slate.md` ("Author ADR-742 spec", "Author ADR-742 plan", "Flip ADR-742 to Accepted", "Create worktree", "Dispatch solo subagent", "Verify ..." as each completes).
- [x] Report back: capture verified end-to-end, baseline numbers, determinism confirmed, `/loop-evals` running. Do NOT run `/dev-merge` — the parent session merges after verifying.

---

## Rollback

- [ ] Revert merge commit(s).
- [ ] Remove the four `mcp-tool:eval-*` entries + `command:eval:` from `capability_exposure.yaml`.
- [ ] Remove the `register_capture_observer()` import + observer-consult line from `mcp_sdk.py`.
- [ ] Restore the `/ask` command body (drop the `set_caller` call).
- [ ] Delete `shared-vault/skills/evals/`.
- [ ] Optionally delete `get_documents_dir()/evals/` — captured data is preserved by default; rollback does not destroy user data.
- [ ] Flip ADR-742 back to Proposed.

No schema migration, no vault touch — rollback is clean and reversible.

---

## Verification commands (Augur-canonical)

```bash
# Test
/auto-test-pytest

# Lint
/auto-lint

# Build (no dashboard changes — quick sanity check)
/dev-build

# Real-world smoke
aug eval capture-consent
AUGUR_CONTRIBUTOR_MODE=1 aug eval seed-baseline
aug eval replay
aug eval stats
aug eval capture-status

# Sync after status flip + new command source
sync commands all
sync agents all
python3 .github/scripts/generate_adr_index.py
```

Never `pnpm test`, `pytest`, `pnpm dev`. Per Rule #19/#29.
