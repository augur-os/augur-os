# Root `llms.txt` + `llms-full.txt` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax. This plan implements ADR-746 per the design spec.

**Goal:** Generate, ship, and lint two repo-root files (`llms.txt`, `llms-full.txt`) that give any AI client a client-neutral doc map. Generator lives inside `sync_agents`; lint enforces freshness like other harness-generated files.

**Architecture:** Pure Python stdlib + PyYAML generator inside `shared-vault/skills/ai/scripts/sync_agents/`. Header content lives in two template files in `shared-vault/skills/ai/assets/templates/`. Generator composes header + auto-extracted file index + (for full variant) inlined bodies, and writes via the existing `write_stable_text` helper. `sync_agents check` gains the new files in its diff set.

**Tech Stack:** Python 3.11 stdlib, PyYAML, `src.lib.generated_artifacts.write_stable_text`, `src.config.paths` helpers. No external dependencies.

**Spec:** `docs/superpowers/specs/2026-05-13-root-llms-txt-design.md`
**ADR:** `docs/adrs/ADR-746-root-llms-txt-for-repo-self-description.md`
**Slate plan:** `docs/superpowers/plans/2026-05-13-gbrain-borrow-slate.md`

---

## Boundary Rules

- Use `src.config.paths.get_project_root()` for the repo root path; do not hardcode.
- Use `write_stable_text` from `src.lib.generated_artifacts` for both file writes (matches the stable-output discipline of every other generated surface).
- No external HTTP. No LLM calls. Pure text composition.
- Touch only the files listed below. Do not modify per-client constitution generators in the same change.
- Templates are committed; the generated files are also committed (same lifecycle as `CLAUDE.md`).
- Verification uses `/auto-test-pytest` and `python3 -m shared-vault.skills.ai.scripts.sync_agents check`, never raw `pytest`.

## File Structure

### Backend

- Create `shared-vault/skills/ai/scripts/sync_agents/llms_txt.py`
  - Public function `generate_llms_files(project_root: Path) -> tuple[Path, Path]` returns paths to both written files.
  - Internal helpers: `_load_header(template_path)`, `_enumerate_agent_topics(docs_dir)`, `_extract_purpose(md_path)`, `_compose_concise()`, `_compose_full(concise_text)`.
  - All file writes via `write_stable_text`.
- Modify `shared-vault/skills/ai/scripts/sync_agents/__init__.py`
  - Add `generate_llms_files()` call in the `sync agents` pipeline, after per-client constitution generators run.
  - Add both file paths to the managed-artifact registry so `sync_agents purge --confirm` removes them and `sync_agents check` diffs them.
- Modify `shared-vault/skills/ai/scripts/sync_agents/engine.py` (if the artifact registry lives there)
  - Register the new files with their generators so `check` knows how to regenerate-and-diff.

### Templates

- Create `shared-vault/skills/ai/assets/templates/llms-txt-header.md`
  - One paragraph: Augur identity, BYO-AI-client model, "where to look next."
- Create `shared-vault/skills/ai/assets/templates/llms-full-txt-header.md`
  - Slightly fuller version of the concise header, ending with "Full agent rules and architecture follow below."

### Generated artifacts (committed to repo)

- Create `llms.txt` at repo root (generated)
- Create `llms-full.txt` at repo root (generated)

### Tests

- Create `shared-vault/skills/ai/scripts/sync_agents/tests/test_llms_txt.py`
  - `test_concise_includes_header()`
  - `test_concise_enumerates_agent_topics()` — confirms every `docs/agent-topics/*.md` appears
  - `test_full_inlines_agent_rules()` — confirms `agent-rules.md` body appears verbatim
  - `test_full_inlines_architecture_overview()`
  - `test_full_inlines_what_is_augur()`
  - `test_stable_output()` — two consecutive generations produce byte-identical output
  - `test_size_sanity_concise()` — concise file under 5KB (warning threshold)
  - `test_size_sanity_full()` — full file under 50KB (warning threshold)
  - `test_check_detects_drift()` — mutate disk file, confirm `sync_agents check` flags it stale

### Docs

- Modify `docs/agent-topics/ARCHITECTURE.md` (if it documents the harness generator surface) — append one paragraph noting `llms.txt` is now part of the generated bundle.
- No other docs touched. The ADR is canonical.

---

## Tasks

### Setup

- [ ] Confirm worktree is created for this ADR (via ADR-101 worktree registry) or work proceeds in main if no parallelism conflict.
- [ ] Confirm `_record_from_adr_file` / sync_agents helpers import cleanly.
- [ ] Confirm header template directory exists; create if not.

### Templates

- [ ] Author `llms-txt-header.md` content (one paragraph; reviewed by gsannikov).
- [ ] Author `llms-full-txt-header.md` content.

### Generator module

- [ ] Implement `_load_header(path) -> str`. Test: missing file raises.
- [ ] Implement `_enumerate_agent_topics(docs_dir) -> list[tuple[Path, str, str]]` returning (path, title, one-line purpose). Reuse or sibling `_first_prose_paragraph` from `src.lib.adr_utils` if shape allows.
- [ ] Implement `_compose_concise(header, agent_topics, reference_docs)` -> str. Order matches spec §4.2.
- [ ] Implement `_compose_full(concise_text, inlined_paths)` -> str. Inlined paths: `agent-rules.md`, `architecture-overview.md`, `what-is-augur.md`.
- [ ] Implement `generate_llms_files(project_root)` -> tuple[Path, Path]. Both writes through `write_stable_text`.

### Sync pipeline integration

- [ ] Add `generate_llms_files()` to the `sync agents` flow in `__init__.py`. Place it after constitution generators.
- [ ] Register the two output files in the managed-artifact registry consumed by `check` and `purge`.

### Tests

- [ ] Write the test cases listed above. Each test passes individually.
- [ ] Run via `/auto-test-pytest`. Confirm no flakes across 3 consecutive runs.

### First real generation

- [ ] Run `python3 -m shared-vault.skills.ai.scripts.sync_agents sync agents` and inspect the generated files manually.
- [ ] Verify both files render reasonably when opened in a plain text viewer (eyeball test).
- [ ] Confirm concise file is under 5KB and full file is under 50KB.

### Lint integration

- [ ] Run `python3 -m shared-vault.skills.ai.scripts.sync_agents check`. Expect green (just-regenerated).
- [ ] Hand-edit `llms.txt` (delete a line). Re-run `check`. Expect non-zero exit and a diff in the report.
- [ ] Revert the hand-edit. Re-run `check`. Expect green.

### Final verification

- [ ] `/auto-lint` reports green for all touched files.
- [ ] `/auto-test-pytest` reports green for `test_llms_txt.py`.
- [ ] `git diff --stat` shows: 2 generated artifacts at repo root, 2 templates, 1 new module, 1 new test file, modified `__init__.py` (and possibly `engine.py`).
- [ ] No changes outside the file structure listed.

### Closeout

- [ ] Update ADR-746 status from Accepted → Implemented in the JSON index via the upsert helper.
- [ ] Re-run `python3 .github/scripts/generate_adr_index.py` to refresh `docs/generated/adr-index.md`.
- [ ] Re-run `sync_agents sync agents` to refresh CLAUDE.md ADR footer.
- [ ] Update slate plan Phase 1 checkbox (`ADR-746 Implemented`).

---

## Rollback

If verification fails irrecoverably or the file design proves wrong:

- [ ] Revert the merge commit (single commit reverts all changes since all files are new or additively modified).
- [ ] Re-run `sync_agents sync agents` to confirm registry is clean.
- [ ] Flip ADR-746 back to Proposed in the JSON index.
- [ ] No data loss possible — the only generated artifacts are pointer/index files.

---

## Verification commands (Augur-canonical only)

```bash
# Test
/auto-test-pytest

# Lint
/auto-lint

# Build (no dashboard impact expected, but run to be safe)
/dev-build

# Sync verification
python3 -m shared-vault.skills.ai.scripts.sync_agents check
```

Never invoke `pnpm test`, `pytest`, or `pnpm dev` directly per Rule #19/#29.
