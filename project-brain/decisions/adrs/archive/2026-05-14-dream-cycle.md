# ADR-744 Implementation Plan — Dream Cycle (cross-client overnight synthesis routine)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. One failing test first, then implementation, then commit per task.

**Goal:** Land the Dream Cycle as a new `shared-vault/skills/dream/` skill that owns nine `dream-*` MCP tools (orphans, stale-pages, merge-candidates, dead-citations, cache-gc, report-write, last-report, status, config), authors the routine once in `commands/dream.md`, and projects a per-client scheduled-routine artifact through a new `sync_agents` artifact class. Augur owns no scheduling, makes no LLM call — Rule #11/#19 enforced by construction. Every phase opens a job against the ADR-743 ledger. The cycle produces a human-readable report at `get_documents_dir()/reports/dream/<YYYY-MM-DD>.md`.

**Architecture:** A new `command`-hub skill `shared-vault/skills/dream/` owns the genuinely-new code; it **delegates** for the rest. Aggregators read ADR-738 inbound edges + ADR-740 timeline data; `dream-merge-candidates` delegates similarity logic to `shared-vault/skills/ingest/scripts/wiki_concept_merge.py`; entity-tier-recompute is **not** wrapped (the routine calls ADR-738's `entity-tier-recompute` directly). Per-client projection follows the existing Codex schedule-seed precedent: dream emits `shared-vault/skills/dream/assets/seeds/codex-dream-schedules.yaml`, and the Codex adapter at `shared-vault/skills/ai/scripts/sync_agents/adapters/codex.py` gains a `_sync_dream_automations()` method that mirrors `_sync_dev_loop_automations()` exactly. Claude Code / Gemini get a projected routine doc plus a documented one-time `/schedule` (or equivalent) registration step. Cursor / Copilot get a "run dream now" manual command (graceful degradation; no native routine surface).

**Tech Stack:** Python 3.11 stdlib + PyYAML; FastMCP for new tool registration (pattern: `shared-vault/skills/daemon/scripts/job_ledger/mcp/__init__.py`); pytest with `importlib.util.spec_from_file_location` per Augur skill-test convention (memory `feedback-skill-test-convention`); verification through `/auto-test-pytest` and `/auto-lint` (Rule #19/#29 — never raw `pytest`).

**Spec:** `docs/superpowers/specs/2026-05-14-dream-cycle-design.md`. **Depends on (all Implemented):** ADR-738 (`entity-tier-recompute`, inbound-edge counts), ADR-740 (timeline + compiled-truth + `_source:` URIs), ADR-743 (`jobs-submit` job ledger), ADR-670 (cross-client bundle projection). **Related:** ADR-731 (synthesis consolidation), ADR-742 (eval harness — A/B retrieval before/after dream cycles).

**Spec corrections folded into this plan:**

1. ADR-744 body says config lives at `config/system/dream.yaml` — wrong per Rule #2. Dream config is **skill-local** (`shared-vault/skills/dream/config.yaml`). Same correction was already noted in the spec; this plan implements it and updates the ADR body in Task 17.
2. ADR-744 body lists `dream-tier-recompute` as a new tool — wrong. Tier recompute is **delegated** to ADR-738's existing `entity-tier-recompute`. No wrapper. Routine calls it directly.
3. ADR-744 spec says `dream-cache-gc` is "a thin delegate to the `cache-control` capability". This is **inaccurate**: `cache-control` (in `src/mcp/augur_core/tools/core/health.py`) is the in-memory **skill-cache** invalidator, not a `get_cache_dir()` filesystem GC. `dream-cache-gc` owns its own filesystem-GC logic against `get_cache_dir()` with a retention threshold (default 30 days, configurable in `config.yaml`). It opportunistically calls `cache_control_impl(action="invalidate")` for skill-cache invalidation after purging files — but the bulk of the work is its own.

---

## File Structure

### Create

| Path | Responsibility |
|------|----------------|
| `shared-vault/skills/dream/SKILL.md` | Skill manifest (hub: command, type: routine, `x-augur-mcp-tools` listing nine `dream-*`, `x-augur-cli` `aug dream <verb>`, no dashboard pages) |
| `shared-vault/skills/dream/config.yaml` | Skill-local config: phase order, retries, skips, cache-gc retention days, paths to dependencies |
| `shared-vault/skills/dream/commands/dream.md` | The routine — multi-step prompt with deterministic MCP calls + inline judgment prompts, every phase wrapped in `jobs-submit` |
| `shared-vault/skills/dream/scripts/__init__.py` | Empty marker |
| `shared-vault/skills/dream/scripts/bootstrap_paths.py` | Path-helper imports for the skill (mirrors `shared-vault/skills/graph/scripts/bootstrap_paths.py`) |
| `shared-vault/skills/dream/scripts/aggregators.py` | Pure logic for `dream-orphans` / `dream-stale-pages` / `dream-merge-candidates` |
| `shared-vault/skills/dream/scripts/dead_citations.py` | Pure logic for `dream-dead-citations` (scan timeline `_source:` URIs for dead targets) |
| `shared-vault/skills/dream/scripts/dream_report.py` | `dream-report-write` + `dream-last-report` — consolidate phase results into `get_documents_dir()/reports/dream/<date>.md` |
| `shared-vault/skills/dream/scripts/dream_status.py` | `dream-status` — read latest dream job from the ADR-743 ledger |
| `shared-vault/skills/dream/scripts/cache_gc.py` | `dream-cache-gc` — filesystem GC of rebuildable indexes under `get_cache_dir()` past retention; opportunistic skill-cache invalidation via `cache_control_impl` |
| `shared-vault/skills/dream/scripts/dream_config.py` | `dream-config` — read/show skill-local `config.yaml` |
| `shared-vault/skills/dream/scripts/projection.py` | Per-client routine projection: writes Codex seed yaml; emits Claude Code routine doc; writes Gemini equivalent or graceful-degradation artifact for Cursor/Copilot |
| `shared-vault/skills/dream/scripts/mcp/__init__.py` | Register all nine `dream-*` MCP tools + `register_subcommands(subparsers)` for `aug dream <verb>` |
| `shared-vault/skills/dream/assets/seeds/codex-dream-schedules.yaml` | Codex schedule-seed entries for the dream routine (mirrors `codex-dev-loop-schedules.yaml`) |
| `shared-vault/skills/dream/augur/tests/__init__.py` | Empty marker |
| `shared-vault/skills/dream/augur/tests/conftest.py` | Shared fixtures: fixture vault root with synthetic wiki pages, timeline entries, source-cards |
| `shared-vault/skills/dream/augur/tests/test_aggregators.py` | Tests for `dream-orphans`, `dream-stale-pages`, `dream-merge-candidates` — flag-only, never deletes |
| `shared-vault/skills/dream/augur/tests/test_dead_citations.py` | Tests for `dream-dead-citations` against fixture timeline entries with mixed dead/live `_source:` URIs |
| `shared-vault/skills/dream/augur/tests/test_dream_report.py` | Tests for `dream-report-write` / `dream-last-report` — rendering, proposal links, idempotent re-runs |
| `shared-vault/skills/dream/augur/tests/test_dream_status.py` | Tests for `dream-status` — reads ADR-743 ledger correctly, handles missing ledger gracefully |
| `shared-vault/skills/dream/augur/tests/test_cache_gc.py` | Tests for `dream-cache-gc` — respects retention, skips non-rebuildable paths, dry-run mode |
| `shared-vault/skills/dream/augur/tests/test_dream_config.py` | Tests for `dream-config` — reads skill-local config, returns canonical dict |
| `shared-vault/skills/dream/augur/tests/test_projection.py` | Tests for `projection.py` — Codex seed entry, Claude Code routine doc, graceful degradation, idempotent re-projection |
| `shared-vault/skills/dream/augur/tests/fixtures/vault/` | Synthetic vault tree (wiki pages with `## Timeline`, source-cards, sample graph cache) |

### Modify

| Path | Change |
|------|--------|
| `docs/adrs/ADR-744-dream-cycle-overnight-synthesis-auto-loop.md` | Set `plan_file: 2026-05-14-dream-cycle.md`; in body, correct the three spec drifts (Task 17): config path → skill-local; dream-tier-recompute → delegation note; cache-control characterization → filesystem GC |
| `shared-vault/skills/ai/scripts/sync_agents/adapters/codex.py` | Add `_sync_dream_automations()` method that mirrors `_sync_dev_loop_automations()` exactly — reads `shared-vault/skills/dream/assets/seeds/codex-dream-schedules.yaml` via `load_codex_schedule_seed` and writes via `sync_codex_automations`. Call it from `sync()` alongside the existing call |
| `shared-vault/skills/ai/scripts/sync_agents/adapters/claude_code.py` | Project the dream routine doc to the Claude Code surface — `commands/dream.md` becomes a `/dream` slash command and the adapter emits a one-line activation hint (user runs `/schedule /dream` once) |
| `shared-vault/skills/ai/scripts/sync_agents/adapters/gemini.py` | Project the equivalent Gemini routine artifact, or — if Gemini has no native routine surface — emit a documented manual command |
| `shared-vault/skills/ai/scripts/sync_agents/adapters/cursor.py` | Graceful degradation: project a manual "run dream now" command artifact |
| `shared-vault/skills/ai/scripts/sync_agents/adapters/copilot.py` | Same graceful degradation |
| `config/system/capability_exposure.yaml` | Add `mcp-tool:dream-orphans`, `mcp-tool:dream-stale-pages`, `mcp-tool:dream-merge-candidates`, `mcp-tool:dream-dead-citations`, `mcp-tool:dream-cache-gc`, `mcp-tool:dream-report-write`, `mcp-tool:dream-last-report`, `mcp-tool:dream-status`, `mcp-tool:dream-config` — all CLI-default per the surface-decision-matrix; routine-callable always |
| `config/system/command_surfaces.yaml` | Add `command:dream:` entry projecting the `/dream` slash command to client surfaces per Rule #30 cross-OS surface declaration + memory `feedback-command-capability-entry` |
| `docs/agent-topics/architecture-daemon.md` (or `docs/architecture-daemon.md` — confirm during Task 16) | New section "Compounding Routines" distinguishing Augur-scheduled auto-loops (launchd / Task Scheduler / daemon) from client-scheduled routines (dream cycle); explicit pointer to ADR-744 |

---

## Task 1: Skill scaffold

**Files:**
- Create: `shared-vault/skills/dream/SKILL.md`
- Create: `shared-vault/skills/dream/config.yaml`
- Create: `shared-vault/skills/dream/scripts/__init__.py`
- Create: `shared-vault/skills/dream/scripts/bootstrap_paths.py`
- Create: `shared-vault/skills/dream/scripts/mcp/__init__.py` (stub — full registration in Task 10)
- Create: `shared-vault/skills/dream/augur/tests/__init__.py`
- Create: `shared-vault/skills/dream/augur/tests/conftest.py`

- [ ] **Step 1: Author `SKILL.md` with frontmatter**

Use the `command`-hub skill convention. Frontmatter must include `x-augur-hub: command`, `x-augur-mcp-tools` listing the nine `dream-*` tools, `x-augur-cli: aug dream`. Body documents the routine's purpose, the deterministic-vs-judgment split, the dependency on ADR-738/740/743, the graceful-degradation policy, and a "Run dream now" pointer (`/dream` slash command).

- [ ] **Step 2: Author `config.yaml`**

```yaml
# Skill-local — only the dream routine reads this. Per Rule #2, NOT in central config.
phases:
  order:
    - orphans
    - dead-citations
    - cache-gc
    - tier-recompute    # delegates to ADR-738 entity-tier-recompute
    - stale-pages       # judgment
    - pattern-extraction  # judgment
    - merge-candidates  # judgment
  skips: []             # phase ids to skip
  retries:
    default: 0
    cache-gc: 1
cache_gc:
  retention_days: 30
  paths:
    # Rebuildable index caches — purge when older than retention_days
    - "graph"           # ADR-738 graph cache
    # Additional cache subdirs added as more skills land
report:
  output_dir: "reports/dream"  # under get_documents_dir()
```

- [ ] **Step 3: Author `bootstrap_paths.py`**

Mirror `shared-vault/skills/graph/scripts/bootstrap_paths.py`. Adds project root to `sys.path` so the skill can `from src.config.paths import get_documents_dir, get_cache_dir`.

- [ ] **Step 4: Create empty `__init__.py` markers and a stub MCP module**

`shared-vault/skills/dream/scripts/mcp/__init__.py` contains a `register_tools(mcp)` stub returning `[]` and a `register_subcommands(subparsers)` stub that registers `aug dream` with no verbs yet. Tasks 2–9 add tools; Task 10 wires the registration.

- [ ] **Step 5: Author `conftest.py` with a fixture vault**

Build a synthetic vault at `shared-vault/skills/dream/augur/tests/fixtures/vault/` containing:
- 3 wiki pages: one with strong inbound edges + a fresh `## Timeline`, one with zero inbound edges and a stale timeline (orphan candidate), one with a high-similarity twin
- 1 timeline entry with a dead `vault://nonexistent.md` `_source:` URI and 1 with a live `vault://wiki/x.md` URI
- A minimal graph cache jsonl

The fixture's vault root is exposed as a pytest fixture `fixture_vault` that monkey-patches `src.config.paths.get_vault_dir` for the test session.

- [ ] **Step 6: Commit the scaffold**

```bash
git add shared-vault/skills/dream/
git commit -m "$(cat <<'EOF'
feat(dream): scaffold dream skill — SKILL.md, config, fixtures (ADR-744 task 1)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `dream-orphans` aggregator

**Files:**
- Create: `shared-vault/skills/dream/scripts/aggregators.py`
- Create: `shared-vault/skills/dream/augur/tests/test_aggregators.py` (the `dream-orphans` portion; Tasks 3 and 4 append to the same test file)

**Dependencies:** Task 1 scaffold.

**Independence:** No file overlap with Tasks 3, 4, 5, 6, 7, 8, 9. Parallel-safe — can be spawned as a teammate in the same Team alongside Tasks 3 / 4 / 5 / 6 / 7 / 8 / 9.

- [ ] **Step 1: Write failing test `test_dream_orphans_flags_pages_with_no_inbound_edges_and_low_timeline`**

```python
# In test_aggregators.py
import importlib.util
from pathlib import Path

_MODULE = Path(__file__).resolve().parents[2] / "scripts" / "aggregators.py"
_SPEC = importlib.util.spec_from_file_location("dream_aggregators", _MODULE)
mod = importlib.util.module_from_spec(_SPEC); _SPEC.loader.exec_module(mod)


def test_dream_orphans_flags_pages_with_no_inbound_edges_and_low_timeline(fixture_vault):
    result = mod.dream_orphans(vault_root=fixture_vault, min_timeline_entries=3)
    # The "orphan" fixture page has 0 inbound edges and 1 timeline entry → flagged.
    # The "anchor" fixture page has 5 inbound edges → not flagged.
    flagged_slugs = {entry["slug"] for entry in result["flagged"]}
    assert "wiki-orphan" in flagged_slugs
    assert "wiki-anchor" not in flagged_slugs
    # Flag-only — no fs writes
    assert (fixture_vault / "wiki" / "wiki-orphan.md").exists()
```

Run, confirm it fails (`ModuleNotFoundError` / `AttributeError`).

- [ ] **Step 2: Implement `dream_orphans()` in `aggregators.py`**

Read inbound edges from the ADR-738 graph cache (delegate to `shared-vault/skills/graph/scripts/graph_query.py` via `importlib`-loaded helper if importing the package isn't viable from a skill; otherwise import directly). Count timeline entries per page (parse `## Timeline` sections in vault wiki pages). Return `{"flagged": [{"slug": ..., "inbound_edges": int, "timeline_entries": int}, ...]}`. Flag-only. Never deletes.

- [ ] **Step 3: Run the test green**

```bash
/auto-test-pytest shared-vault/skills/dream/augur/tests/test_aggregators.py::test_dream_orphans_flags_pages_with_no_inbound_edges_and_low_timeline
```

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/dream/scripts/aggregators.py shared-vault/skills/dream/augur/tests/test_aggregators.py
git commit -m "$(cat <<'EOF'
feat(dream): dream-orphans aggregator with TDD coverage (ADR-744 task 2)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `dream-stale-pages` aggregator

**Files:**
- Modify: `shared-vault/skills/dream/scripts/aggregators.py`
- Modify: `shared-vault/skills/dream/augur/tests/test_aggregators.py`

**Dependencies:** Task 1 scaffold. Touches the same file as Task 2 — **sequential after Task 2** in the same teammate's worktree, or strictly sequential if Tasks 2/3/4 are run as a single teammate.

- [ ] **Step 1: Write failing test `test_dream_stale_pages_flags_when_timeline_recent_but_compiled_truth_old`**

Compare each wiki page's compiled-truth `_last_compiled_at:` (or equivalent timestamp from ADR-740) against the newest `_at:` in the page's `## Timeline`. If the gap exceeds the stale threshold (default 14 days, configurable in `config.yaml`), flag the page.

- [ ] **Step 2: Implement `dream_stale_pages()` in `aggregators.py`**

Delegate timeline parsing to `shared-vault/skills/ingest/scripts/wiki_pages.py` (or the actual ADR-740 timeline reader — confirm during implementation). Return `{"flagged": [{"slug": ..., "last_compiled_at": ..., "latest_timeline_at": ..., "gap_days": int}]}`. Flag-only.

- [ ] **Step 3: Run the test green** via `/auto-test-pytest`.

- [ ] **Step 4: Commit.**

---

## Task 4: `dream-merge-candidates` aggregator

**Files:**
- Modify: `shared-vault/skills/dream/scripts/aggregators.py`
- Modify: `shared-vault/skills/dream/augur/tests/test_aggregators.py`

**Dependencies:** Task 1 scaffold; ideally after Tasks 2/3 in the same teammate.

- [ ] **Step 1: Write failing test `test_dream_merge_candidates_uses_ingest_concept_merge_similarity`**

Set up two near-duplicate concept fixtures. Assert that `dream_merge_candidates()` returns the pair flagged by `shared-vault/skills/ingest/scripts/wiki_concept_merge.py:_are_near_duplicate_concepts`.

- [ ] **Step 2: Implement `dream_merge_candidates()`**

Import `_are_near_duplicate_concepts` from `wiki_concept_merge` (use `importlib.util` to load the sibling skill's module; don't refactor `wiki_concept_merge.py` to be importable as a package — that's out of scope). Iterate over wiki page pairs in the vault, return high-similarity pairs as `{"candidates": [{"left_slug": ..., "right_slug": ..., "score": float}]}`.

- [ ] **Step 3: Run test green; commit.**

---

## Task 5: `dream-dead-citations`

**Files:**
- Create: `shared-vault/skills/dream/scripts/dead_citations.py`
- Create: `shared-vault/skills/dream/augur/tests/test_dead_citations.py`

**Dependencies:** Task 1 scaffold. **Parallel-safe** with Tasks 2/3/4/6/7/8/9 — different files.

- [ ] **Step 1: Write failing test `test_dream_dead_citations_flags_unresolvable_source_uris`**

Fixture timeline entries reference `vault://nonexistent.md`, `source-card://missing-id`, `graph://gone-entity`. Test asserts each is flagged as dead, while live entries are not.

- [ ] **Step 2: Implement `dream_dead_citations()` in `dead_citations.py`**

Walk all wiki pages' `## Timeline` sections, extract each `_source:` URI, resolve by scheme:
- `vault://path` → check `get_vault_dir() / path` exists
- `source-card://id` → check the source-card lookup (delegate to the existing source-card resolver in ingest)
- `graph://entity_id` → check graph cache for the entity

Return `{"flagged": [{"page_slug": ..., "timeline_at": ..., "source_uri": ..., "scheme": ..., "reason": "missing"}]}`. Flag-only.

- [ ] **Step 3: Run test green; commit.**

---

## Task 6: `dream-report-write` + `dream-last-report`

**Files:**
- Create: `shared-vault/skills/dream/scripts/dream_report.py`
- Create: `shared-vault/skills/dream/augur/tests/test_dream_report.py`

**Dependencies:** Task 1. **Parallel-safe** with Tasks 2/3/4/5/7/8/9.

- [ ] **Step 1: Write failing tests**
  - `test_dream_report_write_creates_dated_markdown_with_proposal_links`
  - `test_dream_last_report_returns_most_recent`
  - `test_dream_report_write_idempotent_within_same_day_overwrites`

- [ ] **Step 2: Implement**

`dream_report_write(phase_results: dict, run_date: date | None = None) -> Path`: write `{get_documents_dir()/reports/dream/<YYYY-MM-DD>.md`. Body: one section per phase, with counts, flagged items as wiki-linked bullets (proposals link into the user's normal proposal-review flow), and a footer with the job-ledger run id.

`dream_last_report() -> dict`: `{"path": str | None, "date": "YYYY-MM-DD" | None}`.

- [ ] **Step 3: Run tests green; commit.**

---

## Task 7: `dream-status`

**Files:**
- Create: `shared-vault/skills/dream/scripts/dream_status.py`
- Create: `shared-vault/skills/dream/augur/tests/test_dream_status.py`

**Dependencies:** Task 1; ADR-743 job ledger is Implemented. **Parallel-safe.**

- [ ] **Step 1: Write failing tests**
  - `test_dream_status_returns_latest_dream_job_from_ledger`
  - `test_dream_status_handles_missing_ledger_gracefully`
  - `test_dream_status_distinguishes_in_progress_vs_completed_vs_failed`

- [ ] **Step 2: Implement**

Read the ADR-743 ledger via `shared-vault/skills/daemon/scripts/job_ledger/jobs_ops.py` (or the public function exposed for reads — `list_jobs` / `get_latest_by_kind`). Filter to `kind == "dream"`. Return `{"latest": {"job_id", "started_at", "state", "phases": [...]}, "history": [...]}`.

- [ ] **Step 3: Run tests green; commit.**

---

## Task 8: `dream-config`

**Files:**
- Create: `shared-vault/skills/dream/scripts/dream_config.py`
- Create: `shared-vault/skills/dream/augur/tests/test_dream_config.py`

**Dependencies:** Task 1. **Parallel-safe.**

- [ ] **Step 1: Write failing tests**
  - `test_dream_config_reads_skill_local_yaml`
  - `test_dream_config_returns_canonical_dict_with_phase_order`

- [ ] **Step 2: Implement** — simple PyYAML read of `shared-vault/skills/dream/config.yaml`. Returns the parsed dict. No mutation API in this task.

- [ ] **Step 3: Run tests green; commit.**

---

## Task 9: `dream-cache-gc`

**Files:**
- Create: `shared-vault/skills/dream/scripts/cache_gc.py`
- Create: `shared-vault/skills/dream/augur/tests/test_cache_gc.py`

**Dependencies:** Task 1. **Parallel-safe.**

> **Spec correction folded in here:** `cache-control` in `src/mcp/augur_core/tools/core/health.py` is the in-memory skill-cache invalidator, not a filesystem cache GC. This task implements the filesystem GC; it opportunistically also calls `cache_control_impl(action="invalidate")` after the purge.

- [ ] **Step 1: Write failing tests**
  - `test_dream_cache_gc_purges_files_older_than_retention`
  - `test_dream_cache_gc_skips_files_inside_retention`
  - `test_dream_cache_gc_dry_run_reports_without_deleting`
  - `test_dream_cache_gc_respects_config_paths_allowlist`

- [ ] **Step 2: Implement**

Read `cache_gc.paths` allowlist + `cache_gc.retention_days` from skill config. Walk each allowlisted subdir of `get_cache_dir()`. Purge files whose mtime is older than `now - retention_days`. Support `dry_run: bool = False`. Return `{"purged": [...paths], "kept": int, "bytes_freed": int}`. After a non-dry-run purge with any files removed, call `cache_control_impl(action="invalidate")` from `src.mcp.augur_core.tools.core.health` to flush the in-memory skill cache too.

- [ ] **Step 3: Run tests green; commit.**

---

## Task 10: MCP tool registration + `aug dream` CLI subcommand

**Files:**
- Modify: `shared-vault/skills/dream/scripts/mcp/__init__.py`

**Dependencies:** Tasks 2–9. Strictly sequential after them.

- [ ] **Step 1: Write the MCP-registration test**

Add `shared-vault/skills/dream/augur/tests/test_dream_mcp.py`:
- `test_mcp_registers_all_nine_dream_tools` — load the module, call `register_tools(mock_mcp)`, assert all nine tool names are registered with the correct annotations
- `test_cli_register_subcommands_exposes_aug_dream_verbs` — argparse-level test that `aug dream orphans`, `aug dream stale-pages`, `aug dream merge-candidates`, `aug dream dead-citations`, `aug dream cache-gc`, `aug dream report-write`, `aug dream last-report`, `aug dream status`, `aug dream config` all parse without error

- [ ] **Step 2: Implement registration**

Mirror `shared-vault/skills/daemon/scripts/job_ledger/mcp/__init__.py` exactly. Each tool is a thin async wrapper that calls the matching `aggregators.py` / `dead_citations.py` / etc function and JSON-dumps the result. Annotations: orphans / stale-pages / merge-candidates / dead-citations / last-report / status / config are `READ`; report-write / cache-gc are `WRITE`. All metrics-tracked via `metrics.track_tool(name, skill="dream")`.

Also implement `register_subcommands(subparsers)`: `dream` parser with a `dream_verb` subparser per tool. Each verb forwards to the same underlying function and prints JSON to stdout.

- [ ] **Step 3: Run tests green via `/auto-test-pytest`.**

- [ ] **Step 4: Commit.**

---

## Task 11: `capability_exposure.yaml` entries

**Files:**
- Modify: `config/system/capability_exposure.yaml`
- Modify: `config/system/command_surfaces.yaml`

**Dependencies:** Task 10. Per memory `feedback-command-capability-entry`: new commands need a `command:<name>:` entry; per memory `feedback-vendor-neutral-design`: no vendor naming.

- [ ] **Step 1: Add nine `mcp-tool:dream-*` entries** mirroring the `entity-tier-recompute` template — `classification_status: approved`, `owner_kind: augur`, `preferred_client: shell`, `primary_surface: mcp`, `scope: project`, `export_to: [cli, agents-md, browse]`. Routine-callable always.

- [ ] **Step 2: Add `command:dream:` entry** projecting `/dream` to client surfaces.

- [ ] **Step 3: Commit** (no tests — config file).

---

## Task 12: `commands/dream.md` routine

**Files:**
- Create: `shared-vault/skills/dream/commands/dream.md`

**Dependencies:** Tasks 2–10 (the routine calls each tool).

- [ ] **Step 1: Author the multi-step prompt**

Sections:
1. Header — purpose, "runs inside the client's own session", how to invoke (`/dream` or via the scheduled routine)
2. **Phase 1 — Open the run.** Call `jobs-submit kind=dream name=<routine-name>` once; capture `job_id`. Heartbeat after every phase.
3. **Deterministic phases (sequential):**
   - `dream-orphans` — record flagged count
   - `dream-dead-citations` — record flagged count
   - `dream-cache-gc` — record purged count
   - `entity-tier-recompute` — **delegated to ADR-738 graph skill** (the routine calls it directly; no dream wrapper)
4. **Judgment phases (the client reasons inline; no Augur LLM call):**
   - **Compiled-truth refresh** — `dream-stale-pages` returns flagged pages; for each, the client reads recent timeline entries (via `wiki-*` MCP tools), then writes a *proposal* (never an automatic compiled-truth write — ADR-740 forbids that)
   - **Pattern extraction** — the client surveys recent ingestions and proposes new wiki seeds
   - **Wiki concept merging** — `dream-merge-candidates` returns high-similarity pairs; the client reviews each and proposes a merge (or rejects)
5. **Closeout.** Call `dream-report-write` with the consolidated phase results. Heartbeat job to `completed`. Print path to the freshly-written report.
6. **Failure handling.** Failure of any deterministic phase does **not** block subsequent deterministic phases — log the failure to the report and continue. Judgment phases that produce weak proposals are fine (the user rejects).

- [ ] **Step 2: Commit.**

---

## Task 13: `projection.py` and per-client adapters

**Files:**
- Create: `shared-vault/skills/dream/scripts/projection.py`
- Create: `shared-vault/skills/dream/assets/seeds/codex-dream-schedules.yaml`
- Create: `shared-vault/skills/dream/augur/tests/test_projection.py`
- Modify: `shared-vault/skills/ai/scripts/sync_agents/adapters/codex.py` — add `_sync_dream_automations()`
- Modify: `shared-vault/skills/ai/scripts/sync_agents/adapters/claude_code.py` — emit `/dream` command + one-time `/schedule` hint
- Modify: `shared-vault/skills/ai/scripts/sync_agents/adapters/gemini.py` — emit equivalent routine artifact or graceful-degradation manual command
- Modify: `shared-vault/skills/ai/scripts/sync_agents/adapters/cursor.py` — graceful degradation
- Modify: `shared-vault/skills/ai/scripts/sync_agents/adapters/copilot.py` — graceful degradation

**Dependencies:** Task 12 (routine doc exists to project). This task is **the novel infrastructure** — most of the architectural risk lives here.

- [ ] **Step 1: Author `codex-dream-schedules.yaml`** mirroring the existing `codex-dev-loop-schedules.yaml` entry shape exactly:

```yaml
schedules:
  - id: codex-dream-overnight
    title: Dream Cycle
    loop: dream
    source: codex
    rrule: "RRULE:FREQ=DAILY;BYHOUR=4;BYMINUTE=0"
    prompt: "/dream"
    workspace: "__PROJECT_ROOT__"
    model: "gpt-5.4"
    reasoning_effort: "high"
    runs_in: local
```

(Daily at 04:00 — overnight, no overlap with the weekly dev-loop schedule. Model and reasoning are configurable later; the schedule seed mirrors what the Codex adapter already understands.)

- [ ] **Step 2: Write failing test `test_projection.py`**

- `test_projection_codex_seed_picked_up_by_existing_adapter` — point the existing Codex adapter at a tmp `CODEX_HOME` and confirm a `codex-dream-overnight` automation is materialized
- `test_projection_claude_code_emits_dream_command_artifact` — confirm the Claude Code adapter projects `commands/dream.md` to its surface as `/dream`
- `test_projection_cursor_emits_graceful_degradation_manual_command` — confirm Cursor / Copilot adapters emit the documented manual artifact (no schedule)
- `test_projection_idempotent` — running the projection twice with no input changes makes no fs changes

- [ ] **Step 3: Implement `projection.py`**

Thin façade module: each function returns metadata about what *would* be projected. The actual per-client writes live in the adapter `.py` files (consistent with the existing `_sync_dev_loop_automations` pattern). `projection.py` exposes:
- `dream_codex_seed_path() -> Path` (returns the YAML path)
- `dream_routine_doc_path() -> Path` (returns `commands/dream.md`)
- `dream_manual_command_template() -> str` (returns the Markdown body used by Cursor / Copilot)

- [ ] **Step 4: Modify the Codex adapter** — add `_sync_dream_automations()` mirroring `_sync_dev_loop_automations()` line-for-line, but reading the dream seed yaml. Call it from `sync()` alongside the existing dev-loop call.

- [ ] **Step 5: Modify Claude Code / Gemini / Cursor / Copilot adapters** — each emits its surface-appropriate artifact. Activation hints (the one-time `/schedule` registration) are surfaced in the post-sync report, not silent.

- [ ] **Step 6: Run all tests green via `/auto-test-pytest`.**

- [ ] **Step 7: Commit.**

---

## Task 14: Wire dream projection into `sync_agents` engine

**Files:**
- Modify: `shared-vault/skills/ai/scripts/sync_agents/engine.py` (or wherever artifact classes are orchestrated — confirm during implementation)
- Modify: `shared-vault/skills/ai/scripts/sync_agents/__init__.py` (if a registry hook is needed)

**Dependencies:** Task 13.

- [ ] **Step 1: Write failing test `test_sync_agents_invokes_dream_projection_for_each_supported_client`**

The test stubs each adapter and confirms `sync_agents sync agents all` invokes the dream projection step for every supported client.

- [ ] **Step 2: Implement the wiring**

In most cases the per-adapter calls in Task 13 are sufficient (the adapter's own `sync()` already runs). Add an engine-level guard that the dream seed yaml exists; if absent, log and skip (matches existing dev-loop sync's behavior).

- [ ] **Step 3: Run `sync_agents sync agents all` end-to-end** against the current repo. Confirm:
- A Codex automation file lands under `~/.codex/automations/`
- A Claude Code `/dream` command projection lands in the expected output directory
- The post-sync report mentions the one-time `/schedule /dream` activation hint

- [ ] **Step 4: Commit.**

---

## Task 15: Value validation against real data (Rule #34)

**Dependencies:** Tasks 1–14.

> Per Rule #34 and memory `feedback_long_session_drift`: green tests are not value. Run dream against the real vault and prove it produces useful output before declaring done.

- [ ] **Step 1: Run `aug dream orphans` against the real vault.** Capture the output. Quote the first 3 flagged pages (slugs + inbound-edge counts + timeline counts). Confirm the flagged pages are *plausibly* orphans on inspection (or capture the finding that they are not — that's a real bug, not a "works mechanically" pass).

- [ ] **Step 2: Run `aug dream dead-citations`.** Quote the first 3 dead citations. Confirm each by spot-checking the target.

- [ ] **Step 3: Run `aug dream cache-gc --dry-run`.** Quote the bytes that would be freed.

- [ ] **Step 4: Run the routine end-to-end inline** — invoke `/dream` in this Claude Code session, let it iterate phases, and capture the generated report path. Open the report and verify it has real content (not template placeholders).

- [ ] **Step 5: Run `aug dream status`.** Confirm it shows the run from Step 4 with the right phase counts.

- [ ] **Step 6: Run `aug dream last-report`.** Confirm it points at the Step 4 report.

- [ ] **Step 7: Record findings.** Any phase that produced empty / weak output is a finding to fix or surface honestly — never downgrade the "works" claim to "ran without error".

- [ ] **Step 8: Commit any small fixes** from the real-data run.

---

## Task 16: `architecture-daemon.md` "Compounding Routines" section

**Files:**
- Modify: `docs/agent-topics/architecture-daemon.md` (confirm path during implementation; if it doesn't exist, create `docs/architecture-daemon.md` per spec wording)

**Dependencies:** none functional; cosmetic placement only.

- [ ] **Step 1: Add the section**

Distinguish:
- **Augur-scheduled auto-loops** — launchd / Task Scheduler / the daemon's `/dev-loops` registry — scheduled by Augur, runs Python, no LLM in the loop
- **Client-scheduled routines** — the dream cycle — scheduled by the client (Codex `automations.toml`, Claude Code `/schedule`, etc.), runs in the client's session, LLM-aware, calls Augur MCP tools for atomic work

Cross-link to ADR-744 and the dream skill's SKILL.md.

- [ ] **Step 2: Commit.**

---

## Task 17: Correct the ADR-744 body (three drifts)

**Files:**
- Modify: `docs/adrs/ADR-744-dream-cycle-overnight-synthesis-auto-loop.md`

**Dependencies:** none functional (the body is documentation).

- [ ] **Step 1: Correct config path** — the body's "Routine source lives in a dedicated `dream/` skill" section already implies skill-local config, but the spec corrections section calls out that an earlier draft of the ADR pointed at `config/system/dream.yaml`. Add an explicit "Config lives at `shared-vault/skills/dream/config.yaml` (skill-local per Rule #2)" note to the Decision section.

- [ ] **Step 2: Correct tier-recompute language** — replace "`dream-tier-recompute`" wherever it appears with "`entity-tier-recompute` (delegated to ADR-738; not a new dream tool)".

- [ ] **Step 3: Correct `dream-cache-gc` characterization** — replace "thin delegate to the `cache-control` capability" with: "filesystem GC of rebuildable indexes under `get_cache_dir()` with a retention threshold (default 30 days, skill-local config). Opportunistically calls the in-memory `cache-control` skill-cache invalidator after a non-empty purge."

- [ ] **Step 4: Set `plan_file: 2026-05-14-dream-cycle.md`** in the frontmatter.

- [ ] **Step 5: Commit.**

---

## Task 18: Final post-write hook + ADR status flip

**Dependencies:** all prior tasks green; Task 15 value validation passed.

- [ ] **Step 1: Run the ADR post-write hook**

```bash
python .github/scripts/adr_upsert_live.py
python .github/scripts/generate_adr_index.py
python src/lib/index/unified_indexer.py --category adrs
python3 -m skills.ai.scripts.sync_agents sync agents all
```

- [ ] **Step 2: Flip status** — `/adr set 744 Implemented`. (Or edit frontmatter directly and rerun the hook.)

- [ ] **Step 3: Re-run the hook** (status changed; index needs regen).

- [ ] **Step 4: Final commit** consolidating index regen + status flip.

- [ ] **Step 5: Hand off** — defer to `superpowers:finishing-a-development-branch` for merge / PR / worktree cleanup per the user's chosen integration path (current worktree is `wt-20260516-012950`; user already chose "continue in current worktree" for the implementation phase).

---

## Parallelism Map (for `/adr implement` Phase 3 — Team primitives)

Tasks that touch **disjoint files** and can run as parallel teammates in one Team:

**Cluster A (after Task 1):**
- Task 5 (`dead_citations.py` + its tests)
- Task 6 (`dream_report.py` + its tests)
- Task 7 (`dream_status.py` + its tests)
- Task 8 (`dream_config.py` + its tests)
- Task 9 (`cache_gc.py` + its tests)

Each touches its own scripts file and its own test file → safe to parallelize.

**Cluster B (after Task 1, but sequential within the cluster):**
- Tasks 2 → 3 → 4 — all touch `aggregators.py` + `test_aggregators.py`. One teammate, three tasks, sequential.

**Strictly sequential** (shared-file or downstream):
- Task 10 (needs Tasks 2–9)
- Task 11 (needs Task 10)
- Task 12 (needs Task 10)
- Task 13 (needs Task 12; the per-client adapter modifies are the riskiest cross-file change in the slate)
- Task 14 (needs Task 13)
- Tasks 15 / 16 / 17 / 18 — sequential closeout

So the parallel-safe shape is: **Task 1 → (Cluster B + Cluster A in parallel) → Task 10 → Task 11 → Task 12 → Task 13 → Task 14 → Tasks 15..18 sequential.**

---

## Rollback

- Each task commits independently; revert any single commit to back out one tool / one adapter change.
- The new `shared-vault/skills/dream/` directory is self-contained — `git rm -rf shared-vault/skills/dream/` rolls the skill back wholesale.
- `config/system/capability_exposure.yaml` and `config/system/command_surfaces.yaml` additions are pure additions; remove the `dream-*` and `command:dream:` blocks to undo.
- The Codex / Claude Code / Gemini / Cursor / Copilot adapter changes in Task 13 are additive (new methods, new artifact emissions); deleting the new methods restores the prior adapter behavior.
- No data migration: nothing in the user vault is mutated by dream — every phase is flag-only or proposal-only.
- Activation rollback: if a user already ran `/schedule /dream`, they unschedule it via the same client surface. Augur owns no scheduling state.
