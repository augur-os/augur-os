# `check-resolvable` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax. Implements ADR-741 per the design spec.

**Goal:** Ship a skill-coverage auditor that detects unrouted intents, routing collisions, orphaned skills, and stale capability entries across the Augur skill catalog. Run nightly inside `auto-skill-quality`. Report-only in v1; CI-blocking in v2 (next release).

**Architecture:** Pure Python audit script under `shared-vault/skills/auto-skill-quality/scripts/`. New MCP tool wraps the script. JSON report writes to `get_runtime_dir()/quality/resolvable-report.json`. Dashboard `/dev` card consumes the report via `useMcpQuery`.

**Tech Stack:** Python 3.11 stdlib + PyYAML; FastMCP for the tool wrapper; Next.js / TypeScript for the dashboard card; `src.config.paths` for path resolution.

**Spec:** `docs/superpowers/specs/2026-05-13-check-resolvable-design.md`
**ADR:** `docs/adrs/ADR-741-skill-resolvability-and-mece-audit.md`
**Slate plan:** `docs/superpowers/plans/2026-05-13-gbrain-borrow-slate.md`

---

## Boundary Rules

- Read-only auditor. No mutations to skills, capability yaml, or anywhere else.
- No LLM call. Deterministic string + tag analysis.
- Report path resolves via `get_runtime_dir()` — never the repo or vault.
- MCP tool defaults `primary_surface: cli` per surface-decision-matrix. Opt in to `mcp via dashboard` only for the dashboard card.
- Dashboard card uses `useMcpQuery` per Rule #11 — no direct script execution from dashboard code.
- Verification via `/auto-test-pytest`, `/auto-lint`, `/auto-skill-quality`, `/dev-build`. No raw `pytest` / `pnpm dev`.

## File Structure

### Backend

- Create `shared-vault/skills/auto-skill-quality/scripts/check_resolvable.py`
  - Public function `run_audit() -> dict` returns the report JSON shape from spec §4.2.
  - Internal: `_scan_skills(roots) -> list[SkillFacts]`, `_scan_capability_yaml(path) -> list[SurfaceFacts]`, `_detect_unrouted(skills, surfaces)`, `_detect_collisions(skills, surfaces)`, `_detect_orphans(skills, surfaces)`, `_detect_stale(skills, surfaces)`, `_compose_report(...)`.
  - Writes via `src.lib.generated_artifacts.write_stable_text` or a JSON-equivalent helper if one exists; otherwise plain `json.dump` to `get_runtime_dir()/quality/resolvable-report.json` after `mkdir -p`.

- Create `shared-vault/skills/auto-skill-quality/scripts/mcp/resolvable.py`
  - `@mcp.tool` named `skill-resolvable-report`. Returns the latest report content. Re-runs the audit if the report file is older than 1 hour (so the dashboard always sees fresh data without forcing a full loop run).

### Auto-loop integration

- Modify `shared-vault/skills/auto-skill-quality/SKILL.md`
  - Append `skill-resolvable-report` to `x-augur-mcp-tools`.
- Modify `shared-vault/skills/auto-skill-quality/scripts/auto_skill_quality.py` (or wherever the loop's step list lives)
  - Add a new step that calls `check_resolvable.run_audit()` and emits the report. Loop result stays green regardless of findings in v1.

### Capability registration

- Modify `config/system/capability_exposure.yaml`
  - Add entry for `mcp-tool:skill-resolvable-report` with `primary_surface: mcp via dashboard`, `export_to: [cli, agents-md, browse]`, `owner_kind: augur`, `management: generated`, classification approved.

### Dashboard

- Create `apps/dashboard/features/components/dev/SkillCoverageCard.tsx`
  - React component, uses `useMcpQuery('skill-resolvable-report', 'skill-resolvable-report', 'static')`.
  - Renders summary numbers + a detail drawer/modal with the four finding categories.
- Modify `apps/dashboard/app/dev/[[...slug]]/page.tsx` (or the dev browse category root, whichever owns the dev hub assembly)
  - Mount `SkillCoverageCard` in the `dev` browse category.

### Backend tests

- Create `shared-vault/skills/auto-skill-quality/augur/tests/test_check_resolvable.py`
  - Test fixtures: synthetic SKILL.md files in a tmpdir + a synthetic capability_exposure.yaml.
  - `test_unrouted_intent_detected()`
  - `test_routing_collision_detected()`
  - `test_orphan_detected()`
  - `test_stale_capability_detected()`
  - `test_clean_catalog_produces_empty_findings()`
  - `test_report_schema_matches_spec()` — assert the produced JSON matches spec §4.2 shape
  - Use `importlib.util.spec_from_file_location` for the import per `feedback_skill_test_convention`.

### Dashboard tests

- Create `apps/dashboard/features/components/dev/SkillCoverageCard.test.tsx`
  - Mocks `useMcpQuery`; asserts summary numbers render; asserts each finding category renders when present.

### Docs

- Modify `shared-vault/skills/auto-skill-quality/SKILL.md`
  - Update the description to mention coverage auditing alongside per-skill linting.
- No other docs.

---

## Tasks

### Setup

- [ ] Confirm worktree for ADR-741 (per ADR-101 worktree registry).
- [ ] Confirm `get_runtime_dir()` returns the expected platform path.
- [ ] Read `auto-skill-quality/SKILL.md` for current step structure and frontmatter shape.

### Backend audit module

- [ ] Implement `_scan_skills(roots)` — walks both shared-vault and private-vault skill roots, parses SKILL.md frontmatter.
- [ ] Implement `_scan_capability_yaml(path)` — parses yaml and returns surface facts.
- [ ] Implement phrase extraction (bigrams + tags, lowercased, stop-word filtered).
- [ ] Implement `_detect_unrouted` — declared triggers without matching surface entries.
- [ ] Implement `_detect_collisions` — phrases mapping to ≥2 skills, no explicit ownership.
- [ ] Implement `_detect_orphans` — zero surfaces, zero entries.
- [ ] Implement `_detect_stale` — capability entries pointing to non-existent skills/tools.
- [ ] Implement `_compose_report` per spec §4.2 schema.
- [ ] Implement `run_audit()` — orchestrates scanning, detection, report write.

### MCP tool wrapper

- [ ] Implement `mcp/resolvable.py` with `@mcp.tool` decoration.
- [ ] Implement the 1-hour staleness check + auto-refresh.
- [ ] Register tool in `capability_exposure.yaml`.

### Auto-loop integration

- [ ] Add the audit step to `auto-skill-quality` loop runner.
- [ ] Confirm step failure mode is `report-only` (loop stays green).
- [ ] Confirm step runs in `<3` seconds on the current catalog.

### Dashboard

- [ ] Implement `SkillCoverageCard.tsx`.
- [ ] Mount it in the `dev` browse category.
- [ ] Verify with `/dev-build` and a real browser per Rule #28 (client-side verification — HTTP 200 is not enough).

### Backend tests

- [ ] Write all six test cases per the spec.
- [ ] Run via `/auto-test-pytest`. Three consecutive runs, no flakes.

### Dashboard tests

- [ ] Write component test.
- [ ] Run via `/auto-test-dashboard`.

### Real-catalog smoke

- [ ] Run `aug skill-resolvable-report` (or whatever the CLI invocation resolves to).
- [ ] Inspect the report manually. The current catalog should produce at least one finding (sanity check that the auditor isn't always-empty).
- [ ] Open `/dev` in a real browser; confirm the card renders with real numbers.

### Final verification

- [ ] `/auto-lint` green for all touched files.
- [ ] `/auto-test-pytest` green for the new test file.
- [ ] `/auto-test-dashboard` green.
- [ ] `/dev-build` succeeds; browser verification of `/dev` page per Rule #28.
- [ ] `/auto-skill-quality` invocation includes the new step and produces a report.

### Closeout

- [ ] Update ADR-741 status from Accepted → Implemented in JSON index via upsert helper.
- [ ] Re-run `.github/scripts/generate_adr_index.py`.
- [ ] Re-run `sync_agents sync agents`.
- [ ] Update slate plan Phase 1 checkbox (`ADR-741 Implemented`).
- [ ] Note in the slate plan that ADR-745 (Skillify) step 9 can now reference `skill-resolvable-report` as the active tool, not the fallback.

---

## Rollback

- [ ] Revert merge commit(s).
- [ ] Remove `capability_exposure.yaml` entry for `skill-resolvable-report`.
- [ ] Remove the audit step from `auto-skill-quality` loop runner.
- [ ] Delete the runtime-dir report file (optional — it's rebuildable so no risk to leave it).
- [ ] Flip ADR-741 back to Proposed.

No schema migration, no vault touch — rollback is clean.

---

## Verification commands (Augur-canonical)

```bash
# Test
/auto-test-pytest
/auto-test-dashboard

# Lint
/auto-lint

# Build (dashboard touched, so /dev-build is required)
/dev-build

# Audit
/auto-skill-quality

# Real-world smoke
aug skill-resolvable-report

# Sync after status flip
sync agents all
python3 .github/scripts/generate_adr_index.py
```

Never `pnpm test`, `pytest`, `pnpm dev`. Per Rule #19/#29.
