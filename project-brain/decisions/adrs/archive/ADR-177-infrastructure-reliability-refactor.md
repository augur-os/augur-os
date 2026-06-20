---
status: Implemented
date: '2026-02-28'
deciders:
- Augur Team
related:
- ADR-076 (Self-Healing)
- ADR-126 (Plugin Template)
- ADR-163 (Config Decentralization)
- ADR-175 (Command Naming)
hub: null
tags:
- infrastructure
- reliability
- refactor
superseded_by: null
---

# ADR-177: Infrastructure Reliability Refactor

## Context

A 7-day retrospective of 344 learnings across daily logs reveals six recurring infrastructure failure areas consuming disproportionate firefighting effort:

| Area | Score | Fix Commits | What Keeps Breaking |
|------|-------|-------------|---------------------|
| **self-heal** | 153 | 49 | Scanner false positives flood fix pipeline — HTTP logs, Mock warnings, INFO-level degradation match broad `ERROR\|Exception` patterns |
| **agent-config** | 68 | 56 | Every code change requires manual `sync_agents.py --all` + separate chore(sync) commit because pre-commit hook blocks but won't auto-fix |
| **path-resolution** | 23 | 13 | Stale path references survive merges — dual Python/TS resolution, 15 hardcoded `SPECIAL_DATA_PATHS` overrides, nightly-only scanning |
| **plugin-lifecycle** | 20 | 6 | Skills declaring `contributions.pages` without dashboard files cause 404 tabs; hub.id collisions warn but don't fail |
| **build-cache** | 19 | 5 | Turbopack `.next/dev` corruption: classifier rule ordering is fragile (first-match tuple list), shell fix targets wrong subdirectory |
| **mount-system** | 18 | 6 | Tab registry doesn't validate tabs resolve to real page files; plugin rebuild SSE pipeline gaps |

These are not new features — they are reliability gaps in existing infrastructure that cause the same classes of bugs to recur weekly. The cost is ~80 reactive commits per week that fix symptoms instead of root causes.

## Decision

Six targeted refactors, each independent, ordered by impact score.

### 1. Self-Heal Scanner Pre-Filter Pipeline

**Problem**: `_probe_file_for_errors()` in `ai_self_healer.py:608` uses broad regex `ERROR|FATAL|CRITICAL|Traceback|Exception` that matches non-actionable log content. 49 fix commits in 7 days were band-aids adding pattern-by-pattern exclusions to `SEVERITY_HINTS`.

**Changes**:

- **Add structured pre-filter** in `ai_self_healer.py` before `_probe_file_for_errors()`:
  1. Skip lines matching `_is_info_level_log()` (already exists but only called in some paths)
  2. Skip lines containing `WARNING` log level when structured JSON (already partial)
  3. Add `_is_mock_client_line()` check: match `MagicMock`, `<Mock `, `unittest.mock` — structural detection, not just `[MagicMock]` string
  4. Add `_is_http_response_line()`: extend `_HTTP_ACCESS_LOG_RE` to match Next.js-style `POST /api/... 200 in 17ms` format

- **Add circuit breaker** to `run_pipeline()` in `ai_self_healer.py:1049`:
  - If same `dedup_key` has `fix_attempts >= 3` AND last fix result is `"failed"`, set status to `wont_fix` and stop retrying
  - Currently entries cycle between `"new"` → `"fixing"` → `"failed"` → `"new"` indefinitely

- **Convert `SEVERITY_HINTS` from ordered list to priority-keyed dict** in `classifier.py:52`:
  - Current: `list[tuple[Pattern, str, str]]` — first match wins, order-dependent
  - New: `dict[str, list[tuple[Pattern, str, str]]]` keyed by priority tier (`dismiss`, `transient`, `actionable`)
  - Dismiss tier evaluated first (Mock, HTTP, INFO), then transient, then actionable
  - Eliminates rule-ordering bugs (e.g., commit e3206d28 that moved Turbopack rule above ENOENT)

**Files**:
- `plugins/observability/skills/daemon/scripts/ai_self_healer.py` — pre-filter pipeline, circuit breaker
- `plugins/observability/skills/daemon/scripts/self_heal/classifier.py` — tiered SEVERITY_HINTS

### 2. Auto-Fix Pre-Commit Sync Hook

**Problem**: `.pre-commit-config.yaml:62` runs `sync_agents.py --check` which blocks commits but doesn't auto-fix. This forces the workflow: edit code → pre-commit block → run sync manually → commit sync files as separate chore(sync) commit. Result: 56 rote regeneration commits in 7 days.

**Changes**:

- **Add `--fix` mode** to `sync_agents.py`:
  - If `--check` detects drift, automatically run `--all` and stage the generated files
  - Pre-commit hook changes from `--check` to `--fix`
  - Generated files (CLAUDE.md, AGENTS.md, .cursorrules, etc.) get auto-staged into the current commit
  - Eliminates separate chore(sync) commits

- **Update `.pre-commit-config.yaml`**:
  ```yaml
  - id: validate-agent-instructions
    entry: python plugins/ai/skills/ai_bridge/scripts/sync_agents.py --fix
  ```

**Files**:
- `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` — add `--fix` mode
- `.pre-commit-config.yaml` — switch from `--check` to `--fix`

### 3. Eliminate SPECIAL_DATA_PATHS Hardcodes

**Problem**: `src/dashboard/lib/paths.ts:357-374` has 15 hardcoded path overrides (`SPECIAL_DATA_PATHS`) that bypass dynamic discovery. When skills move or restructure, these hardcodes go stale. Python's `paths.py` already uses full auto-discovery — TypeScript lags behind.

**Changes**:

- **Replace `SPECIAL_DATA_PATHS` with augur.yaml discovery**:
  - Read `data_dir` from each skill's `augur.yaml` (same pattern as Python's `_discover_skill_to_bundle_mapping()`)
  - The 15 entries map to 5 skills — each should declare its sub-paths in augur.yaml `contributions.data_paths`
  - Remove `SPECIAL_DATA_PATHS` dict entirely
  - `getSpecialDataPath()` → `getSkillSubPath(skill, subpath)` using augur.yaml lookup

- **Add stale path scanner to pre-commit hook**:
  ```yaml
  - id: stale-path-check
    entry: python .github/scripts/scan_stale_paths.py --ci --quick
    stages: [commit]
  ```
  `--quick` mode: only scan files in the current commit diff, not the full repo

- **Deprecate `getSkillDataPath` confusion**:
  - Rename to `getSkillAugurDataPath()` to make the return value obvious (`plugins/{bundle}/skills/{skill}/augur/data/`)
  - Add JSDoc warning on old name with `@deprecated` tag

**Files**:
- `src/dashboard/lib/paths.ts` — remove SPECIAL_DATA_PATHS, add augur.yaml discovery
- `.pre-commit-config.yaml` — add stale-path-check hook
- `.github/scripts/scan_stale_paths.py` — add `--quick` diff-only mode
- Skills augur.yaml files (5 skills) — add `contributions.data_paths` sections

### 4. Build-Time Contribution Validation

**Problem**: Skills declaring `contributions.pages` in augur.yaml without corresponding dashboard files cause 404 tabs that only surface at runtime. `detectHubIdCollisions()` in `resolver.ts:85` warns but doesn't fail on collisions.

**Changes**:

- **Add page file validation** in `mount-plugins.ts` after discovery:
  - For each `contributions.pages` entry, verify the referenced dashboard file exists in `plugins/{bundle}/skills/{skill}/dashboard/`
  - Missing files → hard error with actionable message: "Skill X declares page Y but no dashboard file exists"

- **Make collision detection fail hard**:
  - `detectHubIdCollisions()` → throw instead of `console.warn` when two plugins resolve to same mountPath
  - Add `--warn-only` flag for backwards compat during migration

- **Add tab-to-page validation** in `generate-tab-registry.mjs`:
  - After generating tab registry, validate every tab `href` resolves to an actual `page.tsx` file
  - Orphan tabs → build warning (hard error after migration period)

**Files**:
- `src/dashboard/scripts/mount-plugins.ts` — add page file validation after discovery
- `src/dashboard/scripts/mount/resolver.ts` — make `detectHubIdCollisions()` throw
- `src/dashboard/scripts/generate-tab-registry.mjs` — add tab-to-page validation

### 5. Structured Classifier Rules

**Problem**: `SEVERITY_HINTS` in `classifier.py:52-112` is an ordered tuple list where first match wins. Rule ordering bugs caused 3 commits (e3206d28, 6a4f299b, 556d622a) where Turbopack rules had to be manually reordered above generic ENOENT rules.

**Changes** (partially overlaps with Refactor 1, but focused on testability):

- **Add unit tests for classifier rules**:
  - Test each `SEVERITY_HINTS` pattern against known inputs
  - Test ordering invariants: "Turbopack ENOENT must classify as transient, not high"
  - Test `SHELL_ACTIONS` pattern matching

- **Add health check for `.next/dev` integrity**:
  - Proactive check in dashboard monitor: verify `.next/dev/` directory exists and has recent files
  - If stale (>30min old `.sst` files), trigger cache clear before HTTP 500 manifests
  - Integrates with existing `start-dev.sh` corruption guard

**Files**:
- `plugins/observability/skills/daemon/scripts/self_heal/classifier.py` — tiered rules (from Refactor 1)
- `tests/plugins/observability/test_classifier.py` — new unit tests
- `src/dashboard/scripts/start-dev.sh` — add `.next/dev` integrity check

### 6. End-to-End Mount Validation

**Problem**: Plugin rebuild SSE pipeline, duplicate tab bars, and query-param drill-down failures stem from mount-plugins + tab-registry not validating end-to-end. After `generate-tab-registry`, no check verifies registered tabs resolve to real page files.

**Changes**:

- **Post-mount validation pass** in `mount-plugins.ts`:
  - After all plugins mounted + tab registry generated, scan `src/app/{hub}/` for page.tsx files
  - Cross-reference against tab registry — flag orphan tabs (registered but no page) and orphan pages (page exists but not in registry)
  - Print summary: "Mounted: N plugins, M tabs, P pages. Orphans: X"

**Files**:
- `src/dashboard/scripts/mount-plugins.ts` — add post-mount validation
- `src/dashboard/scripts/generate-tab-registry.mjs` — add orphan detection

## Consequences

### Positive

- Self-heal noise reduced by ~80% — Mock, HTTP, INFO lines filtered before entering pipeline
- Sync commits eliminated — ~50 fewer chore(sync) commits per week
- Stale paths caught at commit time instead of nightly scan
- Build fails on invalid plugin contributions instead of producing 404s at runtime
- Classifier rule ordering bugs prevented by tiered evaluation and unit tests

### Negative

- Pre-commit hook runs slightly longer (~2-3s for sync --fix + stale path check)
- Hard-fail on hub.id collisions may break existing builds if undiscovered collisions exist — needs migration scan first
- Removing `SPECIAL_DATA_PATHS` requires 5 skills to add `contributions.data_paths` to augur.yaml

### Neutral

- Self-heal pipeline architecture unchanged — same scan → classify → fix flow, just better filtering
- mount-plugins API unchanged — validation is additive, not restructuring

## Implementation Order

```
Phase 1: Self-Heal Pre-Filter (highest impact, independent)
├── Step 1.1: Add _is_mock_client_line() and extended HTTP filter to ai_self_healer.py
├── Step 1.2: Add circuit breaker (wont_fix after 3 failed attempts) to run_pipeline()
├── Step 1.3: Convert SEVERITY_HINTS to tiered dict in classifier.py
└── Step 1.4: Add classifier unit tests

Phase 2: Auto-Fix Sync Hook (quick win, independent)
├── Step 2.1: Add --fix mode to sync_agents.py (run --all + git add generated files)
└── Step 2.2: Update .pre-commit-config.yaml to use --fix

Phase 3: Path Resolution Cleanup (independent)
├── Step 3.1: Add contributions.data_paths to 5 skill augur.yaml files
├── Step 3.2: Replace SPECIAL_DATA_PATHS with augur.yaml discovery in paths.ts
├── Step 3.3: Add --quick mode to scan_stale_paths.py
└── Step 3.4: Add stale-path-check to .pre-commit-config.yaml

Phase 4: Build Validation (depends on nothing, but lower priority)
├── Step 4.1: Add page file validation to mount-plugins.ts
├── Step 4.2: Make detectHubIdCollisions() throw in resolver.ts
├── Step 4.3: Add tab-to-page validation in generate-tab-registry.mjs
└── Step 4.4: Add post-mount orphan detection

Phase 5: Verification
├── Step 5.1: Run full test suite (pytest + npm run build)
├── Step 5.2: Run stale path scanner
├── Step 5.3: Verify self-heal pipeline with known false positive inputs
└── Step 5.4: Verify pre-commit hook auto-fixes sync drift
```

## Alternatives Considered

### Alternative 1: Rewrite Self-Heal in TypeScript

Move the entire self-heal pipeline to Node.js to share code with the dashboard. Rejected because: 1) 2000+ lines of Python with complex state management, 2) Python's subprocess/file handling is more natural for log scanning, 3) ADR-279 already rejected Python→Node.js migration for MCP.

### Alternative 2: Remove Pre-Commit Hooks Entirely

Replace with CI-only validation. Rejected because: the whole point is catching issues before they hit main. CI validation is too late — stale paths and sync drift would accumulate between PRs.

### Alternative 3: Unified Path Resolution Service

Build a single path resolution microservice that both Python and TypeScript call via MCP. Rejected as over-engineering — the real fix is making TypeScript match Python's auto-discovery pattern, not adding a new runtime dependency.

## References

- ADR-076: Daemon AI-Powered Self-Healing
- ADR-126: Generic Plugin Template (data path consolidation)
- ADR-163: Config Decentralization
- Refactor Priority Report: `docs/memory/daily/2026-02-28.md`
- Self-heal classifier: `plugins/observability/skills/daemon/scripts/self_heal/classifier.py`
- Sync agents: `plugins/ai/skills/ai_bridge/scripts/sync_agents.py`
- Path resolution: `src/dashboard/lib/paths.ts`, `src/config/paths.py`
- Mount system: `src/dashboard/scripts/mount-plugins.ts`, `src/dashboard/scripts/mount/resolver.ts`

## Impact Manifest

```yaml
impact:
  apis_changed:
    - function: getSkillDataPath
      module: src/dashboard/lib/paths.ts
      breaking: false  # deprecated alias preserved
    - function: SPECIAL_DATA_PATHS
      module: src/dashboard/lib/paths.ts
      breaking: true  # removed entirely
    - function: detectHubIdCollisions
      module: src/dashboard/scripts/mount/resolver.ts
      breaking: true  # changes from warn to throw
  patterns_deprecated:
    - grep: "SPECIAL_DATA_PATHS"
      replacement: "augur.yaml contributions.data_paths + getSkillSubPath()"
    - grep: "getSkillDataPath"
      replacement: "getSkillAugurDataPath (renamed for clarity)"
  files_affected:
    - glob: "plugins/*/skills/*/augur.yaml"
    - glob: "src/dashboard/lib/paths.ts"
    - glob: "src/dashboard/scripts/mount-plugins.ts"
    - glob: "src/dashboard/scripts/mount/resolver.ts"
    - glob: "plugins/observability/skills/daemon/scripts/ai_self_healer.py"
    - glob: "plugins/observability/skills/daemon/scripts/self_heal/classifier.py"
    - glob: ".pre-commit-config.yaml"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-177: Infrastructure Reliability Refactor**.

Read the full ADR: `docs/decisions/ADR-177-infrastructure-reliability-refactor.md`

### Team Orchestration

1. **Create team**: `TeamCreate(team_name="adr-177-infra-reliability", description="Implementing ADR-177: Infrastructure Reliability Refactor")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-177-infra-reliability", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-177 team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-177-infra-reliability`

#### Phase 1: Self-Heal Pre-Filter Pipeline
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer-1 | medium | Add `_is_mock_client_line()` (match MagicMock, `<Mock `, unittest.mock) and extend `_HTTP_ACCESS_LOG_RE` to match Next.js-style response lines. Call both in `_probe_file_for_errors()` before pattern matching | `plugins/observability/skills/daemon/scripts/ai_self_healer.py` |
| 1.2 | developer-1 | medium | Add circuit breaker to `run_pipeline()`: if `fix_attempts >= 3` and last result is `"failed"`, set `status = "wont_fix"` and skip | `plugins/observability/skills/daemon/scripts/ai_self_healer.py` |
| 1.3 | developer-1 | medium | Convert `SEVERITY_HINTS` from ordered list to tiered dict with keys `dismiss`, `transient`, `actionable`. Evaluate dismiss first, then transient, then actionable. Update `pre_classify()` to iterate tiers in order | `plugins/observability/skills/daemon/scripts/self_heal/classifier.py` |
| 1.4 | developer-1 | low | Add unit tests for classifier: test each pattern against known inputs, test ordering invariant (Turbopack ENOENT → transient not high), test Mock detection | `tests/plugins/observability/test_classifier.py` |

#### Phase 2: Auto-Fix Sync Hook
**Strategy**: PARALLEL (independent of Phase 1)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer-2 | medium | Add `--fix` mode to `sync_agents.py`: when `--check` detects drift, run `--all` regeneration then `git add` all generated targets. Exit 0 so pre-commit passes | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |
| 2.2 | developer-2 | low | Update `.pre-commit-config.yaml` line 62: change `--check` to `--fix` | `.pre-commit-config.yaml` |

#### Phase 3: Path Resolution Cleanup
**Strategy**: PIPELINE (3.1 before 3.2)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer-3 | medium | Add `contributions.data_paths` to augur.yaml for 5 skills: career, lifestyle, executor, apple (voice-memos). Map current SPECIAL_DATA_PATHS keys to sub-paths relative to skill augur/data/ | `plugins/career/skills/career/augur.yaml`, `plugins/lifestyle/skills/lifestyle/augur.yaml`, `plugins/core/skills/executor/augur.yaml`, `plugins/integrations/skills/apple/augur.yaml` |
| 3.2 | developer-3 | high | Replace `SPECIAL_DATA_PATHS` dict with augur.yaml `contributions.data_paths` discovery in `paths.ts`. Add `getSkillSubPath(skill, subpath)`. Deprecate `getSkillDataPath` → `getSkillAugurDataPath` with `@deprecated` JSDoc | `src/dashboard/lib/paths.ts` |
| 3.3 | developer-3 | medium | Add `--quick` mode to `scan_stale_paths.py`: only scan files in `git diff --cached --name-only` output. Add `--ci` exit code (non-zero on HIGH findings) | `.github/scripts/scan_stale_paths.py` |
| 3.4 | developer-3 | low | Add `stale-path-check` hook to `.pre-commit-config.yaml` using `--quick --ci` | `.pre-commit-config.yaml` |

#### Phase 4: Build Validation
**Strategy**: PARALLEL (independent of Phases 1-3)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer-2 | medium | Add page file validation to mount-plugins.ts: after discovery, verify each `contributions.pages` entry has a corresponding dashboard/ file. Hard error on missing files | `src/dashboard/scripts/mount-plugins.ts` |
| 4.2 | developer-2 | medium | Change `detectHubIdCollisions()` from `console.warn` to `throw new Error`. Add `--warn-only` CLI flag for migration | `src/dashboard/scripts/mount/resolver.ts` |
| 4.3 | developer-2 | medium | Add tab-to-page validation in generate-tab-registry: verify each tab href resolves to a page.tsx. Add post-mount summary: "Mounted: N plugins, M tabs, P pages" | `src/dashboard/scripts/generate-tab-registry.mjs` |

#### Phase 5: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 5.1 | validator | low | Run `pytest tests/` and `cd src/dashboard && npm run build` — verify no regressions |
| 5.2 | validator | low | Run `python3 .github/scripts/scan_stale_paths.py --ci` — verify zero HIGH findings |
| 5.3 | validator | low | Test self-heal pre-filter with known false positives: HTTP access log, MagicMock warning, INFO-level JSON log. Verify all dismissed |
| 5.4 | validator | low | Test pre-commit hook: modify agent-rules.md, commit, verify sync runs automatically and generated files are included |
| 5.5 | architect | low | Verify ADR-177 intent matches implementation. Check Impact Manifest: zero `SPECIAL_DATA_PATHS` references remain, `detectHubIdCollisions` throws |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/`, `npm run build`)
- [ ] No orphaned files or broken references
- [ ] Stale path scanner clean
- [ ] Impact Manifest validated — zero `SPECIAL_DATA_PATHS` references, `getSkillDataPath` deprecated
- [ ] Self-heal circuit breaker tested with mock data
- [ ] Pre-commit hook auto-fixes sync drift (no manual sync needed)
- [ ] ADR status updated to "Accepted" or "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-177-infrastructure-reliability-refactor.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
